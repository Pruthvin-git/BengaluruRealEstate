"""HTTP access to the Karnataka RERA public portal."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

import requests

from parse import parse_listing, parse_quarter_filings

BASE = "https://rera.karnataka.gov.in"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    )
}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_listing(
    district: str,
    listings_dir: Path,
    timeout: int = 180,
) -> bytes:
    listings_dir.mkdir(parents=True, exist_ok=True)
    s = session()
    print("GET /home", flush=True)
    s.get(f"{BASE}/home", timeout=60)
    print(f"POST /projectViewDetails district={district!r}", flush=True)
    r = s.post(
        f"{BASE}/projectViewDetails",
        data={
            "project": "",
            "firm": "",
            "appNo": "",
            "regNo": "",
            "district": district,
            "subdistrict": "0",
            "btn1": "Search",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{BASE}/viewAllProjects",
            "Origin": BASE,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=timeout,
    )
    r.raise_for_status()
    slug = district.lower().replace(" ", "_")
    path = listings_dir / f"{slug}.html"
    path.write_bytes(r.content)
    print(f"listing {r.status_code} {len(r.content)} bytes -> {path}", flush=True)
    return r.content


def _fetch_details_one(
    project: dict[str, Any],
    details_dir: Path,
    resume: bool,
) -> dict[str, Any]:
    pid = str(project["project_id"])
    html_path = details_dir / f"{pid}.html"
    html = None
    if resume and html_path.exists() and html_path.stat().st_size > 1000:
        html = html_path.read_text(encoding="utf-8", errors="ignore")
    else:
        s = session()
        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                r = s.post(
                    f"{BASE}/projectDetails",
                    data={"action": pid},
                    headers={
                        "Accept": "*/*",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "X-Requested-With": "XMLHttpRequest",
                        "Origin": BASE,
                        "Referer": f"{BASE}/projectViewDetails",
                    },
                    timeout=90,
                )
                r.raise_for_status()
                html_path.write_bytes(r.content)
                html = r.text
                break
            except Exception as e:
                last_err = e
                time.sleep(attempt * 2)
        if html is None:
            return {
                **project,
                "filings": [],
                "note": f"fetch_error: {last_err}",
            }
    filings = parse_quarter_filings(html)
    note = None
    if not filings:
        note = "no_parking_qpr"
    elif all(f.get("supply") is None for f in filings):
        note = "no_parking_table"
    return {**project, "filings": filings, "note": note, "html_len": len(html)}


def fetch_project_filings(
    projects: list[dict[str, Any]],
    details_dir: Path,
    workers: int = 3,
    resume: bool = True,
    progress: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    details_dir.mkdir(parents=True, exist_ok=True)
    done: list[dict[str, Any]] = []
    total = len(projects)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(_fetch_details_one, p, details_dir, resume): p for p in projects
        }
        finished = 0
        for fut in as_completed(futs):
            row = fut.result()
            done.append(row)
            finished += 1
            if progress:
                progress(finished, total, row)
            elif finished % 10 == 0 or finished == total:
                print(
                    f"details {finished}/{total} {row.get('name')} "
                    f"filings={len(row.get('filings') or [])} note={row.get('note')}",
                    flush=True,
                )
    return done


def load_projects_from_listing(
    html: str | bytes,
    year: int,
    district: str,
) -> list[dict[str, Any]]:
    text = html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else html
    return parse_listing(text, year=year, district=district)
