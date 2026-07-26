#!/usr/bin/env python3
"""Compare two metrics JSON files and print a table."""

import json
import sys
from pathlib import Path


def load_metrics(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def fmt(val):
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_results.py <baseline.json> <test.json>")
        sys.exit(1)

    base = load_metrics(Path(sys.argv[1]))
    test = load_metrics(Path(sys.argv[2]))

    print(f"\n{'Metric':<35} {'Baseline':>12} {'Test':>12} {'Delta':>10} {'% Change':>10}")
    print("-" * 85)

    keys = [
        ("total_site_energy_kwh", "Total Site Energy (kWh)"),
        ("cooling_electricity_kwh", "Cooling Electricity (kWh)"),
        ("heating_electricity_kwh", "Heating Electricity (kWh)"),
        ("fan_electricity_kwh", "Fan Electricity (kWh)"),
        ("avg_pmv", "Avg PMV"),
        ("min_pmv", "Min PMV"),
        ("max_pmv", "Max PMV"),
        ("avg_ppd", "Avg PPD"),
        ("avg_zone_temp_c", "Avg Zone Temp (°C)"),
    ]

    for key, label in keys:
        b = base.get(key)
        t = test.get(key)
        if b is not None and t is not None and isinstance(b, (int, float)) and isinstance(t, (int, float)):
            delta = t - b
            pct = (delta / b * 100) if b != 0 else float('inf')
            print(f"{label:<35} {fmt(b):>12} {fmt(t):>12} {fmt(delta):>10} {fmt(pct):>10}")
        else:
            print(f"{label:<35} {fmt(b):>12} {fmt(t):>12} {'N/A':>10} {'N/A':>10}")


if __name__ == "__main__":
    main()