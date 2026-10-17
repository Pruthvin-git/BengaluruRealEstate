#!/usr/bin/env python3
"""Build explorer assets from the same K-RERA cache as krera.py reports.

- public/projects.csv — full Urban listing + unit quarters from data/details/
- public/data/scraped-index.json — parking + unit series keyed by Action ID (report parity)
- public/data/krera-reports/*.json — copies of data/reports/
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

KRERA_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KRERA_ROOT))

from parse import (  # noqa: E402
    parse_listing,
    parse_unit_filings,
    quarter_csv_suffix,
    quarter_label,
)
from store import latest_filing, merge_year_snapshots  # noqa: E402

EXPLORER_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CSV = EXPLORER_ROOT / "public" / "projects.csv"
SCRAPED_INDEX = EXPLORER_ROOT / "public" / "data" / "scraped-index.json"
LISTING = KRERA_ROOT / "data" / "listings" / "bengaluru_urban.html"
DETAILS = KRERA_ROOT / "data" / "details"
REPORTS_DIR = KRERA_ROOT / "data" / "reports"

QUARTER_SUFFIXES = (
    "Q3_FY25-26",
    "Q4_FY25-26",
    "Q1_FY26-27",
    "Q2_FY26-27",
)

CSV_FIELDS = [
    "Registration Number",
    "Action ID",
    "Builder",
    "Promoter Name",
    "Project Name",
    "District",
    "Taluka",
    "Project Type",
    "Approved On",
    "Proposed Completion Date",
    "Proposed Completion Date At Registration",
    "Project Address",
    "Latitude",
    "Longitude",
    "Total Units",
    "Has Quarterly Update",
    "Units Booked (Q3_FY25-26)",
    "Units Available (Q3_FY25-26)",
    "Units Booked (Q4_FY25-26)",
    "Units Available (Q4_FY25-26)",
    "Units Booked (Q1_FY26-27)",
    "Units Available (Q1_FY26-27)",
    "Units Booked (Q2_FY26-27)",
    "Units Available (Q2_FY26-27)",
    "Parking Supply (latest)",
    "Parking Booked (latest)",
    "Parking Available (latest)",
    "Parking Quarter (latest)",
    "Has Parking QPR",
]


def _na(value: int | None) -> str:
    return "NA" if value is None else str(value)


def _approved_on_iso(approved: str) -> str:
    approved = (approved or "").strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(approved, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return approved


def _load_previous_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        by_reg: dict[str, dict[str, str]] = {}
        for row in reader:
            reg = (row.get("Registration Number") or "").strip()
            if reg:
                by_reg[reg] = row
        return by_reg


def _unit_columns_from_html(html: str) -> tuple[dict[str, str], str, str | None]:
    booked_cols: dict[str, str] = {s: "NA" for s in QUARTER_SUFFIXES}
    available_cols: dict[str, str] = {s: "NA" for s in QUARTER_SUFFIXES}
    has_update = "No"
    latest_total: int | None = None
    latest_key = (-1, -1)

    for filing in parse_unit_filings(html):
        suffix = quarter_csv_suffix(filing.get("quarter"), filing.get("fy"))
        if suffix not in QUARTER_SUFFIXES:
            continue
        booked, available = filing.get("booked"), filing.get("available")
        if booked is None and available is None:
            continue
        has_update = "Yes"
        booked_cols[suffix] = _na(booked)
        available_cols[suffix] = _na(available)
        fy = filing.get("fy") or ""
        q = filing.get("quarter") or ""
        try:
            start = int(str(fy).split("-")[0])
        except ValueError:
            start = 0
        qn = int(q[1]) if len(q) > 1 and q[1].isdigit() else 0
        key = (start, qn)
        if key >= latest_key and filing.get("total_units") is not None:
            latest_key = key
            latest_total = filing["total_units"]

    merged: dict[str, str] = {}
    for suffix in QUARTER_SUFFIXES:
        merged[f"Units Booked ({suffix})"] = booked_cols[suffix]
        merged[f"Units Available ({suffix})"] = available_cols[suffix]
    total_units = _na(latest_total) if latest_total is not None else "NA"
    return merged, has_update, total_units


def _parking_quarters(project: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for filing in project.get("filings") or []:
        if filing.get("supply") is None:
            continue
        suffix = quarter_csv_suffix(filing.get("quarter"), filing.get("fy"))
        if not suffix:
            continue
        out[suffix] = {
            "label": quarter_label(filing.get("fy"), filing.get("quarter")),
            "supply": filing.get("supply"),
            "demand": filing.get("demand"),
            "inventory": filing.get("inventory"),
            "submitted_on": filing.get("submitted_on"),
        }
    return out


def _unit_quarters_from_cols(unit_cols: dict[str, str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for suffix in QUARTER_SUFFIXES:
        booked = unit_cols.get(f"Units Booked ({suffix})", "NA")
        available = unit_cols.get(f"Units Available ({suffix})", "NA")
        if booked == "NA" and available == "NA":
            continue
        out[suffix] = {
            "booked": int(booked) if booked != "NA" else None,
            "available": int(available) if available != "NA" else None,
        }
    return out


def _snapshot_by_id(district: str) -> tuple[dict[str, dict], dict]:
    snap = merge_year_snapshots(district)
    by_id: dict[str, dict] = {}
    for project in snap.get("projects") or []:
        pid = str(project.get("project_id") or "").strip()
        if pid:
            by_id[pid] = project
    return by_id, snap.get("meta") or {}


def export_projects_csv(
    *,
    district: str = "Bengaluru Urban",
    listing_path: Path = LISTING,
    details_dir: Path = DETAILS,
    dest: Path = PUBLIC_CSV,
) -> dict[str, int]:
    if not listing_path.exists():
        raise FileNotFoundError(
            f"Listing not found: {listing_path}. Run: python krera.py scrape --district \"{district}\""
        )
    snapshot_by_id, snap_meta = _snapshot_by_id(district)
    html = listing_path.read_bytes()
    projects = parse_listing(html.decode("utf-8", errors="ignore"), year=None, district=district)
    previous = _load_previous_rows(dest)

    rows: list[dict[str, str]] = []
    scraped_index: dict[str, dict] = {}
    parsed_details = 0
    with_unit_data = 0
    with_parking = 0
    listing_ids = set()

    for project in projects:
        pid = str(project["project_id"])
        listing_ids.add(pid)
        reg = project.get("reg") or ""
        snap = snapshot_by_id.get(pid)
        prev = previous.get(reg, {}) if reg else {}

        unit_cols: dict[str, str] = {f"Units Booked ({s})": "NA" for s in QUARTER_SUFFIXES}
        unit_cols.update({f"Units Available ({s})": "NA" for s in QUARTER_SUFFIXES})
        has_update = "No"
        total_units = "NA"

        detail_path = details_dir / f"{pid}.html"
        if detail_path.exists():
            parsed_details += 1
            parsed_unit_cols, has_update, parsed_total = _unit_columns_from_html(
                detail_path.read_text(encoding="utf-8", errors="ignore")
            )
            unit_cols.update(parsed_unit_cols)
            if has_update == "Yes":
                with_unit_data += 1
            if parsed_total != "NA":
                total_units = parsed_total

        parking_cols = {
            "Parking Supply (latest)": "NA",
            "Parking Booked (latest)": "NA",
            "Parking Available (latest)": "NA",
            "Parking Quarter (latest)": "NA",
            "Has Parking QPR": "No",
        }
        parking_q: dict[str, dict] = {}
        if snap:
            parking_q = _parking_quarters(snap)
            latest = latest_filing(snap)
            if latest:
                with_parking += 1
                parking_cols = {
                    "Parking Supply (latest)": _na(latest.get("supply")),
                    "Parking Booked (latest)": _na(latest.get("demand")),
                    "Parking Available (latest)": _na(latest.get("inventory")),
                    "Parking Quarter (latest)": quarter_label(
                        latest.get("fy"), latest.get("quarter")
                    ),
                    "Has Parking QPR": "Yes",
                }

        name = (snap or project).get("name") or prev.get("Project Name", "NA")
        promoter = (snap or project).get("promoter") or prev.get("Promoter Name", "NA")
        reg_no = (snap or project).get("reg") or reg or prev.get("Registration Number", "NA")
        approved_raw = (snap or project).get("approved_on") or project.get("approved_on") or ""
        approved = _approved_on_iso(approved_raw) or prev.get("Approved On", "NA")

        row = {
            "Registration Number": reg_no,
            "Action ID": pid,
            "Builder": prev.get("Builder", promoter if promoter != "NA" else "NA"),
            "Promoter Name": promoter,
            "Project Name": name,
            "District": project.get("district") or district,
            "Taluka": (snap or project).get("taluk") or prev.get("Taluka", "NA"),
            "Project Type": (snap or project).get("project_type")
            or project.get("project_type")
            or prev.get("Project Type", "NA"),
            "Approved On": approved,
            "Proposed Completion Date": prev.get("Proposed Completion Date", "NA"),
            "Proposed Completion Date At Registration": prev.get(
                "Proposed Completion Date At Registration", "NA"
            ),
            "Project Address": prev.get("Project Address", "NA"),
            "Latitude": prev.get("Latitude", "NA"),
            "Longitude": prev.get("Longitude", "NA"),
            "Total Units": total_units,
            "Has Quarterly Update": has_update,
            **unit_cols,
            **parking_cols,
        }
        rows.append(row)

        scraped_index[pid] = {
            "action_id": pid,
            "reg": reg_no,
            "name": name,
            "promoter": promoter,
            "taluk": row["Taluka"],
            "project_type": row["Project Type"],
            "approved_on": approved,
            "launch_year": snap.get("launch_year") if snap else None,
            "in_listing": True,
            "in_snapshot": snap is not None,
            "parking_quarters": parking_q,
            "unit_quarters": _unit_quarters_from_cols(unit_cols),
            "parking_latest": (
                {
                    "supply": int(parking_cols["Parking Supply (latest)"])
                    if parking_cols["Parking Supply (latest)"] != "NA"
                    else None,
                    "demand": int(parking_cols["Parking Booked (latest)"])
                    if parking_cols["Parking Booked (latest)"] != "NA"
                    else None,
                    "inventory": int(parking_cols["Parking Available (latest)"])
                    if parking_cols["Parking Available (latest)"] != "NA"
                    else None,
                    "quarter": parking_cols["Parking Quarter (latest)"],
                }
                if parking_cols["Has Parking QPR"] == "Yes"
                else None
            ),
        }

    for pid, snap in snapshot_by_id.items():
        if pid in listing_ids:
            continue
        reg = snap.get("reg") or ""
        prev = previous.get(reg, {}) if reg else {}
        unit_cols = {f"Units Booked ({s})": "NA" for s in QUARTER_SUFFIXES}
        unit_cols.update({f"Units Available ({s})": "NA" for s in QUARTER_SUFFIXES})
        has_update = "No"
        total_units = "NA"
        detail_path = details_dir / f"{pid}.html"
        if detail_path.exists():
            parsed_unit_cols, has_update, parsed_total = _unit_columns_from_html(
                detail_path.read_text(encoding="utf-8", errors="ignore")
            )
            unit_cols.update(parsed_unit_cols)
            if parsed_total != "NA":
                total_units = parsed_total

        parking_q = _parking_quarters(snap)
        latest = latest_filing(snap)
        parking_cols = {
            "Parking Supply (latest)": "NA",
            "Parking Booked (latest)": "NA",
            "Parking Available (latest)": "NA",
            "Parking Quarter (latest)": "NA",
            "Has Parking QPR": "No",
        }
        if latest:
            parking_cols = {
                "Parking Supply (latest)": _na(latest.get("supply")),
                "Parking Booked (latest)": _na(latest.get("demand")),
                "Parking Available (latest)": _na(latest.get("inventory")),
                "Parking Quarter (latest)": quarter_label(
                    latest.get("fy"), latest.get("quarter")
                ),
                "Has Parking QPR": "Yes",
            }

        row = {
            "Registration Number": snap.get("reg") or prev.get("Registration Number", "NA"),
            "Action ID": pid,
            "Builder": prev.get("Builder", snap.get("promoter", "NA")),
            "Promoter Name": snap.get("promoter") or "NA",
            "Project Name": snap.get("name") or "NA",
            "District": snap.get("district") or district,
            "Taluka": snap.get("taluk") or "NA",
            "Project Type": snap.get("project_type") or "NA",
            "Approved On": _approved_on_iso(snap.get("approved_on") or ""),
            "Proposed Completion Date": prev.get("Proposed Completion Date", "NA"),
            "Proposed Completion Date At Registration": prev.get(
                "Proposed Completion Date At Registration", "NA"
            ),
            "Project Address": prev.get("Project Address", "NA"),
            "Latitude": prev.get("Latitude", "NA"),
            "Longitude": prev.get("Longitude", "NA"),
            "Total Units": total_units,
            "Has Quarterly Update": has_update,
            **unit_cols,
            **parking_cols,
        }
        rows.append(row)
        scraped_index[pid] = {
            "action_id": pid,
            "reg": row["Registration Number"],
            "name": row["Project Name"],
            "promoter": row["Promoter Name"],
            "taluk": row["Taluk"],
            "project_type": row["Project Type"],
            "approved_on": row["Approved On"],
            "launch_year": snap.get("launch_year"),
            "in_listing": False,
            "in_snapshot": True,
            "parking_quarters": parking_q,
            "unit_quarters": _unit_quarters_from_cols(unit_cols),
            "parking_latest": None
            if parking_cols["Has Parking QPR"] != "Yes"
            else {
                "supply": int(parking_cols["Parking Supply (latest)"]),
                "demand": int(parking_cols["Parking Booked (latest)"]),
                "inventory": int(parking_cols["Parking Available (latest)"]),
                "quarter": parking_cols["Parking Quarter (latest)"],
            },
        }

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    SCRAPED_INDEX.parent.mkdir(parents=True, exist_ok=True)
    SCRAPED_INDEX.write_text(
        json.dumps(
            {
                "meta": {
                    "district": district,
                    "source": "krera.py snapshots + data/details unit tables",
                    "scraped_at": snap_meta.get("scraped_at"),
                    "launch_years": snap_meta.get("launch_years"),
                    "listing_projects": len(projects),
                    "snapshot_projects": len(snapshot_by_id),
                },
                "by_action_id": scraped_index,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _sync_parking_reports()
    return {
        "projects": len(rows),
        "details_parsed": parsed_details,
        "with_unit_quarterly": with_unit_data,
        "with_parking_qpr": with_parking,
        "snapshot_projects": len(snapshot_by_id),
    }


def _sync_parking_reports() -> None:
    dest_dir = EXPLORER_ROOT / "public" / "data" / "krera-reports"
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not REPORTS_DIR.is_dir():
        return
    for path in sorted(REPORTS_DIR.glob("Bengaluru_Urban*.json")):
        dest_dir.joinpath(path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> None:
    stats = export_projects_csv()
    print(
        f"wrote {PUBLIC_CSV} and {SCRAPED_INDEX} · {stats['projects']} projects · "
        f"snapshot {stats['snapshot_projects']} · "
        f"{stats['with_unit_quarterly']} unit QPR · {stats['with_parking_qpr']} parking QPR",
        flush=True,
    )


if __name__ == "__main__":
    main()
