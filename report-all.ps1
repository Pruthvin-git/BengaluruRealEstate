# Consolidate every launch-year snapshot (2025, 2026, …) into one QoQ report.
# Requires yearly snapshots from: python krera.py scrape --year 2025  (and 2026, …)
param(
    [string]$District = "Bengaluru Urban"
)
Set-Location $PSScriptRoot
python krera.py report --district $District --All --stats qoq --kind all
