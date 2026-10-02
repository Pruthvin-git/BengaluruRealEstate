#!/usr/bin/env python3
"""User-driven K-RERA parking QoQ: scrape when you choose, chart overall or taluk."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from portal import fetch_listing, fetch_project_filings, load_projects_from_listing
from report import DEFAULT_CANVAS, generate_reports
from store import (
    DETAILS,
    KIND_ORDER,
    LISTINGS,
    build_report_data,
    import_legacy_rows,
    latest_snapshot,
    list_latest_snapshots,
    load_snapshot,
    merge_year_snapshots,
    save_snapshot,
    _format_unreported,
)

DEFAULT_DISTRICT = "Bengaluru Urban"
DEFAULT_YEAR = 2026


def _ask(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def _yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def cmd_scrape(district: str, year: int, workers: int, resume: bool) -> Path | None:
    html = fetch_listing(district, LISTINGS)
    projects = load_projects_from_listing(html, year=year, district=district)
    print(f"{len(projects)} approved projects in {year} · {district}", flush=True)
    if not projects:
        print(f"No projects matched for {year} · {district} - skipping.", flush=True)
        return None

    def progress(done: int, total: int, row: dict) -> None:
        if done % 5 == 0 or done == total:
            n = len(row.get("filings") or [])
            print(
                f"details {done}/{total} {row.get('name')} filings={n} note={row.get('note')}",
                flush=True,
            )

    filled = fetch_project_filings(
        projects,
        DETAILS,
        workers=workers,
        resume=resume,
        progress=progress,
    )
    path = save_snapshot(
        filled,
        district=district,
        approved_year=year,
        capture="all_filings",
    )
    with_p = sum(1 for p in filled if any(f.get("supply") is not None for f in p.get("filings") or []))
    print(f"snapshot {path} · {with_p}/{len(filled)} projects have parking QPRs", flush=True)
    return path


def _default_canvas(name: str) -> Path | None:
    if DEFAULT_CANVAS.is_dir():
        return DEFAULT_CANVAS / name
    return None


def _emit_report(
    data: dict,
    canvas_path: Path | None,
    print_unreported: bool = False,
    latest_by_year: bool = False,
) -> None:
    paths = generate_reports(data, canvas_path=canvas_path)
    for label, p in paths.items():
        print(f"{label}: {p}", flush=True)
    m = data["market"]
    print(
        f"market supply={m['supply']} demand={m['demand']} inventory={m['inventory']} "
        f"qpr={m['projects_with_qpr']}/{m['projects_approved']} unreported={m['unreported']}",
        flush=True,
    )
    years = data.get("years") or {}
    if years and latest_by_year:
        print(
            "Latest supply / demand / inventory by launch year "
            "(latest QPR per project):",
            flush=True,
        )
    for y, block in years.items():
        print(
            f"{y} launches: approved={block['projects_approved']} "
            f"qpr={block['projects_with_qpr']} unreported={block['unreported']} "
            f"supply={block['supply']} demand={block['demand']} inventory={block['inventory']}",
            flush=True,
        )
    for key in KIND_ORDER:
        block = (data.get("kinds") or {}).get(key)
        if not block:
            continue
        print(
            f"{block['label']}: approved={block['projects_approved']} "
            f"qpr={block['projects_with_qpr']} unreported={block['unreported']} "
            f"supply={block['supply']} demand={block['demand']} inventory={block['inventory']}",
            flush=True,
        )
    qoq = data["qoq"]
    if qoq["meta"].get("qoq"):
        print(f"QoQ quarters: {', '.join(qoq['quarters'])}", flush=True)
        by_year = qoq.get("by_year") or {}
        for y in by_year:
            s = by_year[y]["overall"]
            parts = []
            for i, q in enumerate(qoq["quarters"]):
                parts.append(
                    f"{q} S={s['supply'][i]} D={s['demand'][i]} I={s['inventory'][i]}"
                )
            print(f"  {y}: " + " | ".join(parts), flush=True)
    if print_unreported:
        cmd_unreported_print(data["unreported"])


def cmd_report(
    district: str,
    year: int,
    snapshot: Path | None,
    canvas: Path | None,
    stats: str = "market",
    kind: str = "all",
    print_unreported: bool = False,
    all_years: bool = False,
) -> None:
    skipped = False
    if not all_years:
        path = snapshot or latest_snapshot(district, year)
        if path is None or not path.exists():
            print(f"No snapshot for {district} {year} - skipping.", flush=True)
            skipped = True
        else:
            print(f"using {path}", flush=True)
            snap = load_snapshot(path)
            data = build_report_data(snap, default_view=stats, default_kind=kind)
            canvas_path = canvas or _default_canvas(
                f"krera-parking-qoq-{year}.canvas.tsx"
            )
            _emit_report(data, canvas_path, print_unreported=print_unreported)

    found = list_latest_snapshots(district)
    if not found:
        print(f"No yearly snapshots for {district} to club.", flush=True)
        return
    print(
        f"clubbing years {', '.join(str(y) for y, _ in found)}",
        flush=True,
    )
    for y, path in found:
        print(f"  {y}: {path}", flush=True)
    snap = merge_year_snapshots(district)
    canvas_path = canvas if all_years else None
    if canvas_path is None:
        canvas_path = _default_canvas("krera-parking-qoq-all.canvas.tsx")
    data = build_report_data(snap, default_view=stats, default_kind=kind)
    _emit_report(
        data,
        canvas_path,
        print_unreported=print_unreported if (all_years or skipped) else False,
        latest_by_year=True,
    )


def cmd_unreported_print(rows: list) -> None:
    if not rows:
        print("\nUnreported quarterly parking (0):", flush=True)
        return
    if isinstance(rows[0], str):
        print(f"\nUnreported quarterly parking ({len(rows)}):", flush=True)
        for name in rows:
            print(name, flush=True)
        return
    print(f"\nUnreported quarterly parking ({len(rows)}):\n", flush=True)
    print(_format_unreported(rows).rstrip(), flush=True)


def cmd_unreported(
    district: str,
    year: int,
    snapshot: Path | None,
    all_years: bool = False,
) -> None:
    if all_years:
        snap = merge_year_snapshots(district)
        if not snap.get("projects"):
            raise SystemExit(
                f"No yearly snapshots for {district}. Run scrape for 2025 and 2026."
            )
        data = build_report_data(snap)
    else:
        path = snapshot or latest_snapshot(district, year)
        if path is None or not path.exists():
            print(f"No snapshot for {district} {year} - skipping.", flush=True)
            found = list_latest_snapshots(district)
            if not found:
                print(f"No yearly snapshots for {district}.", flush=True)
                return
            snap = merge_year_snapshots(district)
            data = build_report_data(snap)
        else:
            data = build_report_data(load_snapshot(path))
    cmd_unreported_print(data["unreported"])


def cmd_import(json_path: Path, district: str, year: int, scraped_at: str) -> Path:
    rows = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(rows, dict) and "projects" in rows:
        rows = rows["projects"]
    path = import_legacy_rows(
        rows,
        district=district,
        approved_year=year,
        scraped_at=scraped_at,
    )
    print(f"imported {len(rows)} rows -> {path}", flush=True)
    return path


def interactive() -> None:
    print("K-RERA parking QoQ (user-driven — you choose when to scrape)\n")
    district = _ask("District", DEFAULT_DISTRICT)
    year_raw = _ask("Approved year (or all)", str(DEFAULT_YEAR))
    all_years = year_raw.strip().lower() in {"all", "--all"}
    year = DEFAULT_YEAR if all_years else int(year_raw)
    print("1) Scrape portal now")
    print("2) Build market / project / QoQ charts from last snapshot")
    print("3) Scrape then build charts")
    print("4) Import a parking JSON from an earlier scrape")
    choice = _ask("Choice", "3")
    if choice == "4":
        src = Path(_ask("JSON path", ""))
        if not src.exists():
            raise SystemExit(f"not found: {src}")
        when = _ask("Scraped-at timestamp (ISO or date)", "2026-09-21")
        cmd_import(src, district, year, when)
        cmd_report(district, year, None, None, print_unreported=True, all_years=all_years)
        return
    if choice in {"1", "3"}:
        if all_years:
            found = list_latest_snapshots(district)
            years = [y for y, _ in found] or [2025, 2026]
            print(f"scrape years: {', '.join(str(y) for y in years)}", flush=True)
            workers = int(_ask("Parallel downloads", "3"))
            resume = _yes("Reuse project HTML already in data/details")
            for y in years:
                cmd_scrape(district, y, workers, resume)
        else:
            workers = int(_ask("Parallel downloads", "3"))
            resume = _yes("Reuse project HTML already in data/details")
            cmd_scrape(district, year, workers, resume)
    if choice in {"2", "3"}:
        stats = _ask("Default chart (market / projects / qoq)", "qoq" if all_years else "market")
        kind = _ask("Default type (all / apartments / plots)", "all")
        cmd_report(
            district, year, None, None, stats=stats, kind=kind,
            print_unreported=True, all_years=all_years,
        )
    if choice == "1":
        if _yes("Build charts now"):
            stats = _ask("Default chart (market / projects / qoq)", "qoq" if all_years else "market")
            kind = _ask("Default type (all / apartments / plots)", "all")
            cmd_report(
                district, year, None, None, stats=stats, kind=kind,
                print_unreported=True, all_years=all_years,
            )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Scrape K-RERA Quarterly Updates parking (supply / demand / inventory) "
            "when you decide a new quarter is in, then chart market, projects, or QoQ."
        )
    )
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--district", default=DEFAULT_DISTRICT)
    shared.add_argument("--year", type=int, default=DEFAULT_YEAR)
    sub = p.add_subparsers(dest="cmd")

    sc = sub.add_parser(
        "scrape",
        parents=[shared],
        help="Download listing + every project's quarterly filings, then build charts",
    )
    sc.add_argument("--workers", type=int, default=3)
    sc.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-download project HTML even if cached",
    )

    rp = sub.add_parser(
        "report",
        parents=[shared],
        help="Build market / project / QoQ charts from the latest snapshot",
    )
    rp.add_argument("--snapshot", type=Path)
    rp.add_argument("--canvas", type=Path, help="Cursor .canvas.tsx path")
    rp.add_argument(
        "--stats",
        choices=["market", "projects", "qoq"],
        default="market",
        help="Default canvas view: overall market, per-project, or QoQ",
    )
    rp.add_argument(
        "--kind",
        choices=["all", "apartments", "plots", "other"],
        default="all",
        help="Default type filter: apartments, plots/villas, or all",
    )
    rp.add_argument(
        "--all",
        "--All",
        dest="all_years",
        action="store_true",
        help="Consolidate every launch-year snapshot for the district (QoQ breakup)",
    )
    rp.add_argument(
        "--list-unreported",
        action="store_true",
        help="Print names of projects with no parking QPR",
    )

    ur = sub.add_parser(
        "unreported",
        parents=[shared],
        help="List projects with no quarterly parking filing",
    )
    ur.add_argument("--snapshot", type=Path)
    ur.add_argument(
        "--all",
        "--All",
        dest="all_years",
        action="store_true",
        help="List unreported names across every launch-year snapshot",
    )

    im = sub.add_parser(
        "import-json",
        parents=[shared],
        help="Import a previous parking JSON as a snapshot",
    )
    im.add_argument("json_path", type=Path)
    im.add_argument("--scraped-at", default="2026-09-21")

    sub.add_parser("run", parents=[shared], help="Scrape then report")
    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        interactive()
        return
    args = build_parser().parse_args(argv)
    district = args.district
    year = args.year
    if args.cmd == "scrape":
        cmd_scrape(district, year, args.workers, resume=not args.no_resume)
        cmd_report(district, year, None, None, print_unreported=True)
    elif args.cmd == "report":
        cmd_report(
            district,
            year,
            args.snapshot,
            args.canvas,
            stats=args.stats,
            kind=args.kind,
            print_unreported=args.list_unreported,
            all_years=args.all_years,
        )
    elif args.cmd == "unreported":
        cmd_unreported(district, year, args.snapshot, all_years=args.all_years)
    elif args.cmd == "import-json":
        cmd_import(args.json_path, district, year, args.scraped_at)
        cmd_report(district, year, None, None, print_unreported=True)
    elif args.cmd == "run":
        cmd_scrape(district, year, 3, resume=True)
        cmd_report(district, year, None, None, print_unreported=True)
    else:
        interactive()


if __name__ == "__main__":
    main()
