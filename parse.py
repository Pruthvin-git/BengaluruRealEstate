"""Parse K-RERA listing HTML and quarterly parking tables."""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
QUARTER_HEAD_RE = re.compile(
    r"Quarter\s+(Q[1-4])\s*\(\s*([^)<]+?)\s*\)",
    re.I,
)
SUBMITTED_RE = re.compile(r"Submitted on\s*([0-9]{2}-[0-9]{2}-[0-9]{4})", re.I)
PARKING_TABLE_RE = re.compile(
    r"Total No of Parkings\s*</th>\s*"
    r"<th[^>]*>\s*Total No Of Parkings Booked\s*</th>\s*"
    r"<th[^>]*>\s*Total No of Parkings Available\s*</th>\s*"
    r"</tr>\s*</thead>\s*<tbody>\s*<tr>\s*"
    r"<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>",
    re.I | re.S,
)
QUARTER_TAB_RE = re.compile(r'<div id="quarter"[^>]*>(.*)$', re.I | re.S)
APPROVED_YEAR_RE = re.compile(r"/(\d{4})\s*$")


def to_int(text: str | None) -> int | None:
    if text is None:
        return None
    cleaned = re.sub(r"<[^>]+>", " ", text).replace(",", "").strip()
    if not cleaned or cleaned in {"-", "NA", "N/A", "nil", "Nil"}:
        return None
    m = NUM_RE.search(cleaned)
    if not m:
        return None
    try:
        return int(float(m.group(0)))
    except ValueError:
        return None


def approved_year(approved_on: str) -> int | None:
    m = APPROVED_YEAR_RE.search((approved_on or "").strip())
    if not m:
        m = re.search(r"\b(20\d{2})\b", approved_on or "")
    return int(m.group(1)) if m else None


def quarter_sort_key(fy: str | None, quarter: str | None) -> tuple[int, int]:
    """Indian FY '2026-27' Q1 sorts after '2025-26' Q4."""
    start = 0
    if fy:
        try:
            start = int(str(fy).split("-")[0])
        except ValueError:
            start = 0
    qn = 0
    if quarter:
        m = re.search(r"(\d)", str(quarter))
        if m:
            qn = int(m.group(1))
    return (start, qn)


def quarter_label(fy: str | None, quarter: str | None) -> str:
    q = (quarter or "").upper().strip()
    f = (fy or "").strip()
    if q and f:
        return f"{q} {f}"
    return q or f or "Unknown"


def parse_listing(html: str, year: int | None = None, district: str | None = None) -> list[dict[str, Any]]:
    start = html.find('id="approvedTable"')
    if start < 0:
        raise ValueError("approvedTable not found — listing search may have failed")
    table_start = html.rfind("<table", 0, start)
    table_end = html.find("</table>", start)
    if table_start < 0 or table_end < 0:
        raise ValueError("approvedTable bounds not found")
    soup = BeautifulSoup(html[table_start : table_end + len("</table>")], "lxml")
    projects: list[dict[str, Any]] = []
    for row in soup.select("tbody tr"):
        tds = row.find_all("td", recursive=False)
        if len(tds) < 11:
            continue
        link = tds[3].find("a", id=True)
        if not link:
            continue
        pid = (link.get("id") or "").strip()
        if not pid.isdigit():
            continue
        approved = tds[10].get_text(" ", strip=True)
        if year is not None and approved_year(approved) != year:
            continue
        dist = tds[7].get_text(" ", strip=True)
        if district and dist.lower() != district.lower():
            continue
        projects.append(
            {
                "project_id": pid,
                "ack": tds[1].get_text(" ", strip=True),
                "reg": tds[2].get_text(" ", strip=True),
                "promoter": tds[4].get_text(" ", strip=True),
                "name": tds[5].get_text(" ", strip=True),
                "status": tds[6].get_text(" ", strip=True),
                "district": dist,
                "taluk": tds[8].get_text(" ", strip=True),
                "project_type": tds[9].get_text(" ", strip=True),
                "approved_on": approved,
            }
        )
    return projects


def _sum_parking(scope: str) -> tuple[int | None, int | None, int | None, int]:
    supply = demand = inventory = 0
    tables = 0
    any_value = False
    for m in PARKING_TABLE_RE.finditer(scope):
        s, d, i = to_int(m.group(1)), to_int(m.group(2)), to_int(m.group(3))
        if s is None and d is None and i is None:
            continue
        tables += 1
        any_value = True
        supply += s or 0
        demand += d or 0
        inventory += i or 0
    if not any_value:
        return None, None, None, 0
    return supply, demand, inventory, tables


def parse_quarter_filings(html: str) -> list[dict[str, Any]]:
    """Every Quarterly Updates panel: supply / demand / inventory."""
    tab = QUARTER_TAB_RE.search(html)
    if not tab:
        return []
    quarter_html = tab.group(1)
    parts = re.split(r'(?=<div class="panel panel-primary">)', quarter_html)
    filings: list[dict[str, Any]] = []
    for part in parts:
        if "panel panel-primary" not in part:
            continue
        head = QUARTER_HEAD_RE.search(part)
        submitted = SUBMITTED_RE.search(part)
        s, d, i, tables = _sum_parking(part)
        filings.append(
            {
                "quarter": head.group(1).upper() if head else None,
                "fy": head.group(2).strip() if head else None,
                "submitted_on": submitted.group(1) if submitted else None,
                "supply": s,
                "demand": d,
                "inventory": i,
                "parking_tables": tables,
            }
        )
    if filings:
        return filings
    s, d, i, tables = _sum_parking(quarter_html)
    if s is None and d is None and i is None:
        return []
    head = QUARTER_HEAD_RE.search(quarter_html)
    submitted = SUBMITTED_RE.search(quarter_html)
    return [
        {
            "quarter": head.group(1).upper() if head else None,
            "fy": head.group(2).strip() if head else None,
            "submitted_on": submitted.group(1) if submitted else None,
            "supply": s,
            "demand": d,
            "inventory": i,
            "parking_tables": tables,
        }
    ]
