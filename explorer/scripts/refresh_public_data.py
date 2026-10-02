#!/usr/bin/env python3
"""Download the public quarterly CSV and K-RERA complaint/order indexes.

Reads only public portal pages. Re-run when you want fresher complaint counts.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DATA = PUBLIC / "data"
LIB = ROOT / "lib"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    )
}
BASE = "https://rera.karnataka.gov.in"
ROW_RE = re.compile(
    r"<tr>\s*<td>\s*</td>\s*<td>(.*?)</td>\s*<td>\s*(\d+)\s*</td>\s*"
    r"<td>\s*<a[^>]*href=\"([^\"]+)\"",
    re.I | re.S,
)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def clean(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def abs_href(href: str) -> str:
    href = html.unescape(href).strip()
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return BASE + href
    return f"{BASE}/{href}"


def complaint_index(body: str) -> list[dict]:
    rows = []
    seen = set()
    for name, count, href in ROW_RE.findall(body):
        item = {
            "name": clean(name),
            "count": int(count),
            "href": abs_href(href),
        }
        key = (item["name"].upper(), item["href"])
        if not item["name"] or key in seen:
            continue
        seen.add(key)
        rows.append(item)
    return rows


def orders_from(body: str) -> list[dict]:
    soup = BeautifulSoup(body, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    parsed = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 12:
            continue
        texts = [clean(td.get_text(" ", strip=True)) for td in cells]
        link = cells[-1].find("a")
        href = abs_href(link.get("href", "")) if link and link.get("href") else ""
        relief = texts[9]
        if len(relief) > 280:
            relief = relief[:277] + "..."
        parsed.append(
            {
                "complaintNo": texts[1],
                "complaintDate": texts[2],
                "orderDate": texts[3],
                "petitioner": texts[4],
                "respondent": texts[5],
                "project": texts[6],
                "promoter": texts[7],
                "district": texts[8],
                "relief": relief,
                "judgementBy": texts[10] if len(texts) > 10 else "",
                "bench": texts[11] if len(texts) > 11 else "",
                "orderHref": href,
            }
        )
    return parsed


def download(s: requests.Session, url: str, dest: Path) -> None:
    print(f"GET {url}", flush=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = s.get(url, timeout=180)
        r.raise_for_status()
        dest.write_bytes(r.content)
        size = len(r.content)
    except requests.exceptions.SSLError:
        print("  python SSL failed, retrying with curl", flush=True)
        subprocess.run(["curl.exe", "-fsSL", "--retry", "3", "-o", str(dest), url], check=True)
        size = dest.stat().st_size
    print(f"  {dest.name} {size} bytes", flush=True)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    LIB.mkdir(parents=True, exist_ok=True)
    s = session()
    download(
        s,
        "https://raw.githubusercontent.com/t0r0id/rera-quarterly-explorer/main/public/projects.csv",
        PUBLIC / "projects.csv",
    )
    download(
        s,
        "https://raw.githubusercontent.com/t0r0id/rera-quarterly-explorer/main/lib/project-metrics.ts",
        LIB / "project-metrics.ts",
    )
    download(
        s,
        "https://raw.githubusercontent.com/t0r0id/rera-quarterly-explorer/main/tests/project-metrics.test.mjs",
        ROOT / "tests" / "project-metrics.test.mjs",
    )

    print("GET project complaints", flush=True)
    project_html = s.get(f"{BASE}/projectComplaintReport", timeout=120).text
    projects = complaint_index(project_html)
    print(f"  projects with complaints: {len(projects)}", flush=True)

    print("GET promoter complaints", flush=True)
    promoter_html = s.get(f"{BASE}/promoterComplaintReport", timeout=120).text
    promoters = complaint_index(promoter_html)
    print(f"  promoters with complaints: {len(promoters)}", flush=True)

    print("GET authority orders", flush=True)
    order_html = s.get(f"{BASE}/viewAllProjectOrders", timeout=180).text
    order_rows = orders_from(order_html)
    print(f"  orders: {len(order_rows)}", flush=True)
    if order_rows:
        print("  sample", json.dumps(order_rows[0], ensure_ascii=False)[:400], flush=True)

    (DATA / "project-complaints.json").write_text(
        json.dumps({"source": f"{BASE}/projectComplaintReport", "items": projects}, ensure_ascii=False),
        encoding="utf-8",
    )
    (DATA / "promoter-complaints.json").write_text(
        json.dumps({"source": f"{BASE}/promoterComplaintReport", "items": promoters}, ensure_ascii=False),
        encoding="utf-8",
    )
    (DATA / "orders.json").write_text(
        json.dumps({"source": f"{BASE}/viewAllProjectOrders", "items": order_rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    print("wrote indexes", flush=True)


if __name__ == "__main__":
    main()
