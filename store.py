"""Snapshot files and QoQ aggregates (overall + taluk + project type)."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parse import approved_year, quarter_label, quarter_sort_key

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "snapshots"
LISTINGS = DATA / "listings"
DETAILS = DATA / "details"
REPORTS = DATA / "reports"

KIND_ORDER = ("apartments", "plots", "other")
KIND_META: dict[str, dict[str, str]] = {
    "apartments": {
        "label": "Apartments",
        "portal": "Residential/Group Housing, Mixed Development",
    },
    "plots": {
        "label": "Plots / villas",
        "portal": "Plotted Development",
    },
    "other": {
        "label": "Other",
        "portal": "Commercial and other K-RERA types",
    },
}


def housing_kind(project_type: str | None) -> str:
    """Map K-RERA project_type to Apartments / Plots / villas / Other."""
    raw = " ".join((project_type or "").strip().lower().split())
    if "plotted" in raw:
        return "plots"
    if "mixed" in raw or "residential" in raw or "group housing" in raw:
        return "apartments"
    return "other"


def kind_label(kind: str) -> str:
    return KIND_META.get(kind, KIND_META["other"])["label"]


def ensure_dirs() -> None:
    for d in (SNAPSHOTS, LISTINGS, DETAILS, REPORTS):
        d.mkdir(parents=True, exist_ok=True)


def save_snapshot(
    projects: list[dict[str, Any]],
    *,
    district: str,
    approved_year: int,
    scraped_at: str | None = None,
    capture: str = "all_filings",
) -> Path:
    ensure_dirs()
    ts = scraped_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = {
        "meta": {
            "district": district,
            "approved_year": approved_year,
            "scraped_at": ts,
            "source": "https://rera.karnataka.gov.in/projectViewDetails",
            "project_count": len(projects),
            "capture": capture,
        },
        "projects": projects,
    }
    day = ts[:10]
    path = SNAPSHOTS / f"{district.replace(' ', '_')}_{approved_year}_{day}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    latest = SNAPSHOTS / f"{district.replace(' ', '_')}_{approved_year}_latest.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_snapshot(district: str, approved_year: int) -> Path | None:
    p = SNAPSHOTS / f"{district.replace(' ', '_')}_{approved_year}_latest.json"
    return p if p.exists() else None


def list_latest_snapshots(district: str) -> list[tuple[int, Path]]:
    slug = district.replace(" ", "_")
    found: list[tuple[int, Path]] = []
    suffix = "_latest.json"
    for path in SNAPSHOTS.glob(f"{slug}_*{suffix}"):
        stem = path.name[: -len(suffix)]
        prefix = slug + "_"
        if not stem.startswith(prefix):
            continue
        tail = stem[len(prefix) :]
        if tail.isdigit():
            found.append((int(tail), path))
    return sorted(found)


def launch_year_of(project: dict[str, Any], snapshot: dict[str, Any] | None = None) -> int:
    raw = project.get("launch_year")
    if raw is not None and str(raw).isdigit():
        return int(raw)
    parsed = approved_year(str(project.get("approved_on") or ""))
    if parsed:
        return parsed
    meta_y = ((snapshot or {}).get("meta") or {}).get("approved_year")
    if isinstance(meta_y, int):
        return meta_y
    if isinstance(meta_y, str) and meta_y.isdigit():
        return int(meta_y)
    return 0


def merge_year_snapshots(district: str) -> dict[str, Any]:
    """Combine every *_latest.json for a district into one all-launch-years snapshot."""
    found = list_latest_snapshots(district)
    projects: list[dict[str, Any]] = []
    seen: set[str] = set()
    captures: dict[str, str] = {}
    scraped: list[str] = []
    for year, path in found:
        snap = load_snapshot(path)
        meta = snap.get("meta") or {}
        captures[str(year)] = str(meta.get("capture") or "")
        if meta.get("scraped_at"):
            scraped.append(str(meta["scraped_at"]))
        for p in snap.get("projects") or []:
            pid = str(p.get("project_id") or "")
            key = pid or f"{year}:{(p.get('reg') or p.get('name') or '')}"
            if key in seen:
                continue
            seen.add(key)
            row = dict(p)
            row["launch_year"] = year
            projects.append(row)
    uniq_cap = {c for c in captures.values() if c}
    capture = "mixed" if len(uniq_cap) > 1 else (next(iter(uniq_cap)) if uniq_cap else "")
    years = [y for y, _ in found]
    title = (
        f"{years[0]}–{years[-1]} launches"
        if len(years) > 1
        else (str(years[0]) if years else "all")
    )
    return {
        "meta": {
            "district": district,
            "approved_year": "all",
            "title_year": title,
            "launch_years": years,
            "project_count": len(projects),
            "source": "https://rera.karnataka.gov.in/projectViewDetails",
            "scraped_at": max(scraped) if scraped else None,
            "capture": capture,
            "captures": captures,
        },
        "projects": projects,
    }


def import_legacy_rows(
    rows: list[dict[str, Any]],
    *,
    district: str,
    approved_year: int,
    scraped_at: str,
) -> Path:
    """Turn a latest-only parking JSON (one filing per project) into a snapshot."""
    projects = []
    for r in rows:
        filing = None
        if r.get("supply") is not None:
            filing = {
                "quarter": r.get("quarter"),
                "fy": r.get("fy"),
                "submitted_on": r.get("submitted_on"),
                "supply": r.get("supply"),
                "demand": r.get("demand"),
                "inventory": r.get("inventory"),
                "parking_tables": r.get("parking_tables") or 0,
            }
        projects.append(
            {
                "project_id": str(r.get("project_id")),
                "ack": r.get("ack"),
                "reg": r.get("reg"),
                "name": r.get("name"),
                "promoter": r.get("promoter"),
                "status": r.get("status"),
                "district": r.get("district") or district,
                "taluk": r.get("taluk"),
                "project_type": r.get("project_type"),
                "approved_on": r.get("approved_on"),
                "filings": [filing] if filing else [],
                "note": r.get("note"),
            }
        )
    return save_snapshot(
        projects,
        district=district,
        approved_year=approved_year,
        scraped_at=scraped_at,
        capture="latest_only",
    )


def _add(bucket: dict[str, int], supply: int, demand: int, inventory: int) -> None:
    bucket["supply"] += supply
    bucket["demand"] += demand
    bucket["inventory"] += inventory
    bucket["projects"] += 1


def _empty_series_bucket() -> dict[str, int]:
    return {"supply": 0, "demand": 0, "inventory": 0, "projects": 0}


def _empty_market() -> dict[str, int]:
    return {
        "projects_approved": 0,
        "projects_with_qpr": 0,
        "unreported": 0,
        "supply": 0,
        "demand": 0,
        "inventory": 0,
    }


def _empty_taluk() -> dict[str, int]:
    return {
        "approved": 0,
        "n": 0,
        "unreported": 0,
        "supply": 0,
        "demand": 0,
        "inventory": 0,
    }


def aggregate_qoq(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    One row per (quarter, FY) overall, per taluk, per housing kind, per launch year.
    A project that filed Q4 and Q1 is counted in both — that is QoQ.
    """
    overall: dict[str, dict[str, int]] = defaultdict(_empty_series_bucket)
    taluk: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_series_bucket)
    )
    kind_overall: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_series_bucket)
    )
    kind_taluk: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(_empty_series_bucket))
    )
    year_overall: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_series_bucket)
    )
    year_taluk: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(_empty_series_bucket))
    )
    year_kind: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(_empty_series_bucket))
    )
    year_kind_taluk: dict[str, dict[str, dict[str, dict[str, dict[str, int]]]]] = (
        defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(lambda: defaultdict(_empty_series_bucket))
            )
        )
    )
    labels_meta: dict[str, tuple[str | None, str | None]] = {}
    kinds_seen: set[str] = set()
    years_seen: set[str] = set()

    for p in snapshot.get("projects") or []:
        t = (p.get("taluk") or "Unknown").strip() or "Unknown"
        k = housing_kind(p.get("project_type"))
        ly = str(launch_year_of(p, snapshot) or "unknown")
        kinds_seen.add(k)
        years_seen.add(ly)
        for f in p.get("filings") or []:
            if f.get("supply") is None:
                continue
            label = quarter_label(f.get("fy"), f.get("quarter"))
            labels_meta[label] = (f.get("fy"), f.get("quarter"))
            supply = int(f["supply"])
            demand = int(f["demand"] or 0)
            inventory = int(f["inventory"] or 0)
            _add(overall[label], supply, demand, inventory)
            _add(taluk[t][label], supply, demand, inventory)
            _add(kind_overall[k][label], supply, demand, inventory)
            _add(kind_taluk[k][t][label], supply, demand, inventory)
            _add(year_overall[ly][label], supply, demand, inventory)
            _add(year_taluk[ly][t][label], supply, demand, inventory)
            _add(year_kind[ly][k][label], supply, demand, inventory)
            _add(year_kind_taluk[ly][k][t][label], supply, demand, inventory)

    quarters = sorted(
        labels_meta.keys(),
        key=lambda lab: quarter_sort_key(*labels_meta[lab]),
    )

    def series_for(bucket: dict[str, dict[str, int]]) -> dict[str, list[int]]:
        return {
            "supply": [bucket.get(q, {}).get("supply", 0) for q in quarters],
            "demand": [bucket.get(q, {}).get("demand", 0) for q in quarters],
            "inventory": [bucket.get(q, {}).get("inventory", 0) for q in quarters],
            "projects": [bucket.get(q, {}).get("projects", 0) for q in quarters],
        }

    taluk_order = sorted(
        taluk.keys(),
        key=lambda name: -sum(taluk[name][q]["supply"] for q in quarters if q in taluk[name]),
    )

    def pack_scope(
        ov: dict[str, dict[str, int]],
        tk: dict[str, dict[str, dict[str, int]]],
        k_ov: dict[str, dict[str, dict[str, int]]] | None = None,
        k_tk: dict[str, dict[str, dict[str, dict[str, int]]]] | None = None,
        *,
        with_kind: bool,
    ) -> dict[str, Any]:
        block: dict[str, Any] = {
            "overall": series_for(ov),
            "taluks": {
                name: series_for(tk.get(name) or {})
                for name in taluk_order
                if name in tk
            },
        }
        if with_kind:
            by_kind: dict[str, Any] = {}
            for kind in KIND_ORDER:
                if kind not in kinds_seen:
                    continue
                kt = (k_tk or {}).get(kind) or {}
                by_kind[kind] = {
                    "overall": series_for((k_ov or {}).get(kind) or {}),
                    "taluks": {
                        name: series_for(kt.get(name) or {})
                        for name in taluk_order
                        if name in kt
                    },
                }
            block["by_kind"] = by_kind
        return block

    meta = dict(snapshot.get("meta") or {})
    meta["quarter_count"] = len(quarters)
    meta["qoq"] = len(quarters) >= 2
    launch_years = sorted(
        (y for y in years_seen if y.isdigit()),
        key=int,
    )
    if "launch_years" not in meta or not meta.get("launch_years"):
        meta["launch_years"] = [int(y) for y in launch_years]
    if not meta.get("title_year"):
        ys = meta.get("launch_years") or []
        if len(ys) > 1:
            meta["title_year"] = f"{ys[0]}–{ys[-1]} launches"
        elif ys:
            meta["title_year"] = str(ys[0])
        else:
            meta["title_year"] = str(meta.get("approved_year") or "")

    by_kind: dict[str, Any] = {}
    for k in KIND_ORDER:
        if k not in kinds_seen:
            continue
        k_taluks = kind_taluk.get(k) or {}
        by_kind[k] = {
            "overall": series_for(kind_overall.get(k) or {}),
            "taluks": {
                name: series_for(k_taluks.get(name) or {})
                for name in taluk_order
                if name in k_taluks
            },
        }

    by_year = {
        y: pack_scope(
            year_overall[y],
            year_taluk[y],
            year_kind[y],
            year_kind_taluk[y],
            with_kind=True,
        )
        for y in launch_years
    }

    return {
        "meta": meta,
        "quarters": quarters,
        "overall": series_for(overall),
        "taluks": {name: series_for(taluk[name]) for name in taluk_order},
        "by_kind": by_kind,
        "by_year": by_year,
    }


def report_stem(payload: dict[str, Any]) -> str:
    meta = payload.get("meta") or (payload.get("qoq") or {}).get("meta") or {}
    district = str(meta.get("district") or "K-RERA").replace(" ", "_")
    year = meta.get("approved_year") or "report"
    return f"{district}_{year}"


def write_qoq_json(agg: dict[str, Any]) -> Path:
    ensure_dirs()
    path = REPORTS / f"{report_stem(agg)}.json"
    path.write_text(json.dumps(agg, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _submitted_key(d: str | None) -> tuple[int, int, int]:
    if not d:
        return (0, 0, 0)
    try:
        dd, mm, yy = str(d).split("-")
        y = int(yy)
        if y < 100:
            y += 2000
        return (y, int(mm), int(dd))
    except Exception:
        return (0, 0, 0)


def latest_filing(project: dict[str, Any]) -> dict[str, Any] | None:
    filings = [f for f in (project.get("filings") or []) if f.get("supply") is not None]
    if not filings:
        return None
    return max(
        filings,
        key=lambda f: (
            _submitted_key(f.get("submitted_on")),
            quarter_sort_key(f.get("fy"), f.get("quarter")),
        ),
    )


def unreported_names(snapshot: dict[str, Any]) -> list[str]:
    return [r["name"] for r in unreported_rows(snapshot)]


def unreported_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for p in snapshot.get("projects") or []:
        if latest_filing(p) is not None:
            continue
        kind = housing_kind(p.get("project_type"))
        ly = launch_year_of(p)
        rows.append(
            {
                "name": (p.get("name") or "").strip() or f"project {p.get('project_id')}",
                "kind": kind,
                "kind_label": kind_label(kind),
                "type": (p.get("project_type") or "").strip(),
                "taluk": (p.get("taluk") or "").strip(),
                "launch_year": ly or None,
            }
        )
    kind_rank = {k: i for i, k in enumerate(KIND_ORDER)}
    rows.sort(
        key=lambda r: (
            r.get("launch_year") or 0,
            kind_rank.get(r["kind"], 99),
            r["name"].lower(),
        )
    )
    return rows


def write_unreported_list(rows: list[Any], stem: str | None = None) -> Path:
    ensure_dirs()
    name = f"{stem}_unreported.txt" if stem else "unreported.txt"
    path = REPORTS / name
    path.write_text(_format_unreported(rows), encoding="utf-8")
    return path


def _format_unreported_kinds(rows: list[dict[str, Any]]) -> str:
    groups: dict[str, list[str]] = defaultdict(list)
    labels: dict[str, str] = {}
    for r in rows:
        k = r.get("kind") or "other"
        labels[k] = r.get("kind_label") or kind_label(k)
        groups[k].append(r.get("name") or "")
    parts: list[str] = []
    for k in KIND_ORDER:
        names = groups.get(k) or []
        if not names:
            continue
        if parts:
            parts.append("")
        parts.append(f"{labels[k]} ({len(names)})")
        parts.extend(names)
    return "\n".join(parts)


def _format_unreported(rows: list[Any]) -> str:
    if not rows:
        return ""
    if isinstance(rows[0], str):
        return "\n".join(rows) + "\n"
    typed = [r for r in rows if isinstance(r, dict)]
    years = sorted(
        {str(r.get("launch_year")) for r in typed if r.get("launch_year")},
        key=lambda x: int(x) if x.isdigit() else x,
    )
    if len(years) > 1:
        parts: list[str] = []
        for y in years:
            subset = [r for r in typed if str(r.get("launch_year")) == y]
            if not subset:
                continue
            if parts:
                parts.append("")
            parts.append(f"{y} launches ({len(subset)})")
            body = _format_unreported_kinds(subset)
            if body:
                parts.append(body)
        return "\n".join(parts) + "\n"
    body = _format_unreported_kinds(typed)
    return body + ("\n" if body else "")


def _finish_market_block(
    counts: dict[str, int],
    taluk_map: dict[str, dict[str, int]],
    *,
    kind: str | None = None,
) -> dict[str, Any]:
    taluk_order = sorted(taluk_map.keys(), key=lambda n: (-taluk_map[n]["supply"], n))
    block: dict[str, Any] = {
        **counts,
        "taluks": {name: dict(taluk_map[name]) for name in taluk_order},
    }
    if kind:
        meta = KIND_META[kind]
        block["kind"] = kind
        block["label"] = meta["label"]
        block["portal"] = meta["portal"]
    return block


def build_report_data(
    snapshot: dict[str, Any],
    default_view: str = "market",
    default_kind: str = "all",
) -> dict[str, Any]:
    """QoQ series + latest-filing market/project stats + unreported names."""
    qoq = aggregate_qoq(snapshot)
    projects: list[dict[str, Any]] = []
    unreported: list[dict[str, Any]] = []
    all_counts = _empty_market()
    all_taluks: dict[str, dict[str, int]] = defaultdict(_empty_taluk)
    kind_counts: dict[str, dict[str, int]] = defaultdict(_empty_market)
    kind_taluks: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_taluk)
    )
    year_counts: dict[str, dict[str, int]] = defaultdict(_empty_market)
    year_taluks: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_taluk)
    )
    year_kind_counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(_empty_market)
    )
    year_kind_taluks: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(_empty_taluk))
    )

    for p in snapshot.get("projects") or []:
        kind = housing_kind(p.get("project_type"))
        taluk = (p.get("taluk") or "").strip() or "Unknown"
        ly = str(launch_year_of(p, snapshot) or "unknown")
        all_counts["projects_approved"] += 1
        kind_counts[kind]["projects_approved"] += 1
        all_taluks[taluk]["approved"] += 1
        kind_taluks[kind][taluk]["approved"] += 1
        year_counts[ly]["projects_approved"] += 1
        year_taluks[ly][taluk]["approved"] += 1
        year_kind_counts[ly][kind]["projects_approved"] += 1
        year_kind_taluks[ly][kind][taluk]["approved"] += 1

        f = latest_filing(p)
        if f is None:
            unreported.append(
                {
                    "name": (p.get("name") or "").strip() or f"project {p.get('project_id')}",
                    "kind": kind,
                    "kind_label": kind_label(kind),
                    "type": (p.get("project_type") or "").strip(),
                    "taluk": taluk,
                    "launch_year": int(ly) if ly.isdigit() else None,
                }
            )
            all_counts["unreported"] += 1
            kind_counts[kind]["unreported"] += 1
            all_taluks[taluk]["unreported"] += 1
            kind_taluks[kind][taluk]["unreported"] += 1
            year_counts[ly]["unreported"] += 1
            year_taluks[ly][taluk]["unreported"] += 1
            year_kind_counts[ly][kind]["unreported"] += 1
            year_kind_taluks[ly][kind][taluk]["unreported"] += 1
            continue

        supply = int(f.get("supply") or 0)
        demand = int(f.get("demand") or 0)
        inventory = int(f.get("inventory") or 0)
        row = {
            "id": str(p.get("project_id") or ""),
            "name": (p.get("name") or "").strip(),
            "promoter": (p.get("promoter") or "").strip(),
            "reg": (p.get("reg") or "").strip(),
            "taluk": taluk,
            "type": (p.get("project_type") or "").strip(),
            "kind": kind,
            "kind_label": kind_label(kind),
            "launch_year": int(ly) if ly.isdigit() else None,
            "approved": (p.get("approved_on") or "").strip(),
            "quarter": quarter_label(f.get("fy"), f.get("quarter")),
            "submitted": f.get("submitted_on"),
            "supply": supply,
            "demand": demand,
            "inventory": inventory,
        }
        projects.append(row)
        all_counts["projects_with_qpr"] += 1
        all_counts["supply"] += supply
        all_counts["demand"] += demand
        all_counts["inventory"] += inventory
        all_taluks[taluk]["n"] += 1
        all_taluks[taluk]["supply"] += supply
        all_taluks[taluk]["demand"] += demand
        all_taluks[taluk]["inventory"] += inventory
        kind_counts[kind]["projects_with_qpr"] += 1
        kind_counts[kind]["supply"] += supply
        kind_counts[kind]["demand"] += demand
        kind_counts[kind]["inventory"] += inventory
        kind_taluks[kind][taluk]["n"] += 1
        kind_taluks[kind][taluk]["supply"] += supply
        kind_taluks[kind][taluk]["demand"] += demand
        kind_taluks[kind][taluk]["inventory"] += inventory
        year_counts[ly]["projects_with_qpr"] += 1
        year_counts[ly]["supply"] += supply
        year_counts[ly]["demand"] += demand
        year_counts[ly]["inventory"] += inventory
        year_taluks[ly][taluk]["n"] += 1
        year_taluks[ly][taluk]["supply"] += supply
        year_taluks[ly][taluk]["demand"] += demand
        year_taluks[ly][taluk]["inventory"] += inventory
        year_kind_counts[ly][kind]["projects_with_qpr"] += 1
        year_kind_counts[ly][kind]["supply"] += supply
        year_kind_counts[ly][kind]["demand"] += demand
        year_kind_counts[ly][kind]["inventory"] += inventory
        year_kind_taluks[ly][kind][taluk]["n"] += 1
        year_kind_taluks[ly][kind][taluk]["supply"] += supply
        year_kind_taluks[ly][kind][taluk]["demand"] += demand
        year_kind_taluks[ly][kind][taluk]["inventory"] += inventory

    kind_rank = {k: i for i, k in enumerate(KIND_ORDER)}
    unreported.sort(
        key=lambda r: (
            r.get("launch_year") or 0,
            kind_rank.get(r["kind"], 99),
            r["name"].lower(),
        )
    )
    projects.sort(key=lambda r: (-r["supply"], r["name"]))

    market = _finish_market_block(all_counts, all_taluks)
    kinds = {
        k: _finish_market_block(kind_counts[k], kind_taluks[k], kind=k)
        for k in KIND_ORDER
        if kind_counts[k]["projects_approved"] > 0
    }
    year_keys = sorted((y for y in year_counts if y.isdigit()), key=int)
    years: dict[str, Any] = {}
    for y in year_keys:
        block = _finish_market_block(year_counts[y], year_taluks[y])
        block["year"] = y
        block["label"] = f"{y} launches"
        block["kinds"] = {
            k: _finish_market_block(
                year_kind_counts[y][k], year_kind_taluks[y][k], kind=k
            )
            for k in KIND_ORDER
            if year_kind_counts[y][k]["projects_approved"] > 0
        }
        years[y] = block

    meta = dict(qoq.get("meta") or {})
    meta["default_view"] = default_view
    meta["default_kind"] = default_kind if default_kind in {"all", *kinds} else "all"
    qoq["meta"] = meta
    return {
        "qoq": qoq,
        "market": market,
        "kinds": kinds,
        "years": years,
        "kind_meta": {k: dict(KIND_META[k]) for k in kinds},
        "projects": projects,
        "unreported": unreported,
    }
