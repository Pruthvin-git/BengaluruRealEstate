# KRERA — parking supply / demand / inventory

User-driven scrape of [Karnataka RERA](https://rera.karnataka.gov.in/projectViewDetails) **Quarterly Updates**. Run it when a new QPR window is in; the script does not guess quarter dates.

For each approved project it reads:

| Portal field | Chart series |
|---|---|
| Total No of Parkings | **Supply** |
| Total No Of Parkings Booked | **Demand** |
| Total No of Parkings Available | **Inventory** |

Charts (pick on the canvas or with `--stats`):

| View | What |
|---|---|
| **Overall market** | Totals plus Apartments vs Plots / villas vs Other |
| **Projects** | Same three series per project, filterable by type |
| **QoQ** | Overall or Taluk, also filterable by type |
| **Unreported QPR** | Names grouped by type |

```powershell
python krera.py report --stats market --kind all
python krera.py report --stats market --kind apartments
python krera.py report --stats market --kind plots
python krera.py report --stats projects
python krera.py report --stats qoq
python krera.py unreported

# Missing year is skipped; then every available launch-year snapshot is clubbed
python krera.py report --district "Bengaluru Urban" --year 2023 --stats market
python krera.py report --district "Bengaluru Urban" --All --stats qoq --kind all
.\report-all.ps1
```

## Setup

```powershell
cd KRERA
pip install -r requirements.txt
```

## When a new quarter is out

```powershell
python krera.py
```

That asks for district, approved year, and whether to scrape now or only rebuild charts.

Same thing without prompts:

```powershell
# Pull every quarterly filing, then build HTML + canvas charts
# (slow; ~3–8 min for Bengaluru Urban).
python krera.py scrape --district "Bengaluru Urban" --year 2026

# Rebuild charts from an existing snapshot (no portal hit)
python krera.py report --district "Bengaluru Urban" --year 2026 --stats market
```

`scrape` keeps project HTML under `data/details/` and **reuses it** next time (`--no-resume` to force a fresh download). One scrape captures **all** QPR panels on each project page, so Q4 and Q1 both land in the same snapshot. The next run, after promoters file Q2, adds that quarter to the same chart.

## Outputs

| File | What |
|---|---|
| `data/snapshots/{District}_{year}_latest.json` | Full project + filing snapshot |
| `data/reports/{District}_{year}.json` | Market, projects, QoQ series, unreported names |
| `data/reports/{District}_{year}.html` | Browser: Overall market / Projects / QoQ / Unreported |
| `data/reports/{District}_{year}_unreported.txt` | Names grouped by Apartments / Plots / villas |
| Cursor canvas `krera-parking-qoq-all.canvas.tsx` | Consolidated all launch years + QoQ breakup |

`--All` (or `--all`) merges every `{District}_{year}_latest.json` for that district. A `--year` with no snapshot is skipped, then the same clubbed report is written. After you scrape 2024 or 2027, those years join the QoQ charts automatically.

```powershell
python krera.py report --district "Bengaluru Urban" --All --stats qoq --kind all
```

## Import the Sep 2026 scrape

If you already have a parking JSON from the earlier one-off pull:

```powershell
python krera.py import-json path\to\bu_2026_parking.json --district "Bengaluru Urban" --year 2026 --scraped-at 2026-09-21
```

That import is **latest filing only**. True QoQ needs `scrape`, which stores every quarter panel.

## Notes

- Default filter: district **Bengaluru Urban**, registration **approved in 2026**.
- Plotted Development is charted as **Plots / villas**; Residential/Group Housing and Mixed Development as **Apartments**. Plotted layouts almost never have a parking table; they stay in the snapshot and under Unreported QPR.
- Be polite to the portal: default 3 parallel downloads.
# BengaluruRealEstate
