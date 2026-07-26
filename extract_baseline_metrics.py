#!/usr/bin/env python
"""Extract metrics from simulation outputs (SQL + ESO) — works on any output folder."""

import json
import sqlite3
import re
import os
import argparse
from collections import defaultdict

JOULES_PER_KWH = 3.6e6

def find_environment_period_index(conn):
    """Find the Weather Run Period (actual simulation) EnvironmentPeriodIndex."""
    cur = conn.cursor()
    cur.execute("""
        SELECT EnvironmentPeriodIndex, EnvironmentName, EnvironmentType
        FROM EnvironmentPeriods
    """)
    rows = cur.fetchall()
    # EnvironmentType: 1=DesignDay, 2=DesignRunPeriod, 3=WeatherRunPeriod
    for idx, name, env_type in rows:
        if env_type == 3:  # WeatherRunPeriod is the actual run from the weather file
            print(f"Found Weather Run Period: Index={idx}, Name={name}")
            return idx
    # Fallback: return the last environment (common case)
    if rows:
        print("Warning: No EnvironmentType=3 found, using last environment")
        return rows[-1][0]
    return None

def query_meter_data(conn, meter_names, env_idx):
    """Query hourly meter values for specific meters within a given environment."""
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in meter_names)
    query = f"""
        SELECT rd.Value, rdd.Name
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        JOIN Time t ON rd.TimeIndex = t.TimeIndex
        WHERE rdd.Name IN ({placeholders})
          AND t.EnvironmentPeriodIndex = ?
        ORDER BY t.TimeIndex
    """
    cur.execute(query, meter_names + [env_idx])
    # Shape: {meter_name: [values]}
    data = defaultdict(list)
    for value, name in cur.fetchall():
        data[name].append(value)
    return dict(data)

def extract_energy_metrics(sql_path, log_path):
    """Extract total kWh and peak kW from Electricity:Facility."""
    print(f"\nExtracting energy metrics from SQLite: {sql_path}")
    if not os.path.exists(sql_path):
        print(f"Error: SQL file not found: {sql_path}")
        return None, None, None, None, None
    conn = sqlite3.connect(sql_path)
    env_idx = find_environment_period_index(conn)
    if env_idx is None:
        print("Error: Could not find any environment period")
        conn.close()
        return None, None, None, None

    meter_names = ["Electricity:Facility", "Electricity:Building",
                   "Heating:Electricity", "Cooling:Electricity"]
    meter_data = query_meter_data(conn, meter_names, env_idx)
    conn.close()

    # For non-cumulative hourly meters, sum of hours = total energy
    total_kwh = None
    peak_kw = None
    building_kwh = None
    cooling_kwh = None
    heating_kwh = None

    if "Electricity:Facility" in meter_data:
        fac_vals = meter_data["Electricity:Facility"]
        # All values are in Joules (since that's EnergyPlus's default for meters)
        total_joules = sum(fac_vals)
        total_kwh = total_joules / JOULES_PER_KWH
        # Peak demand = max hourly energy consumption (Watts) = max(Joules per hour) / 3600 seconds
        peak_joules = max(fac_vals) if fac_vals else 0
        peak_kw = peak_joules / 3600
        print(f"  Total Electricity: {total_kwh:.1f} kWh")
        print(f"  Peak Demand: {peak_kw:.1f} kW")

    if "Electricity:Building" in meter_data:
        building_kwh = sum(meter_data["Electricity:Building"]) / JOULES_PER_KWH
        print(f"  Building Electricity: {building_kwh:.1f} kWh")

    if "Cooling:Electricity" in meter_data:
        cooling_kwh = sum(meter_data["Cooling:Electricity"]) / JOULES_PER_KWH
        print(f"  Cooling Electricity: {cooling_kwh:.1f} kWh")

    if "Heating:Electricity" in meter_data:
        heating_kwh = sum(meter_data["Heating:Electricity"]) / JOULES_PER_KWH
        print(f"  Heating Electricity: {heating_kwh:.1f} kWh")

    return total_kwh, peak_kw, building_kwh, cooling_kwh, heating_kwh

def extract_pmv_metrics(eso_path):
    """Extract PMV comfort metrics from ESO (zone thermal comfort variables)."""
    print(f"\nExtracting PMV metrics from ESO: {eso_path}")
    if not os.path.exists(eso_path):
        print(f"Error: ESO file not found: {eso_path}")
        return {}
    metadata = {}
    data = defaultdict(list)

    with open(eso_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Program Version"):
                continue
            # Metadata lines start with digits and a comma
            if re.match(r"^\d+,\d+,", line):
                parts = line.split(",", 4)
                if len(parts) >= 4:
                    idx = parts[0].strip()
                    name = parts[3].strip().split("!")[0].strip()
                    key = parts[2].strip() if len(parts) >= 4 else ""
                    metadata[idx] = {"key": key, "name": name}
            else:
                parts = line.split(",", 1)
                if len(parts) == 2:
                    idx = parts[0].strip()
                    if idx in metadata:
                        try:
                            val = float(parts[1].strip())
                            data[idx].append(val)
                        except ValueError:
                            pass

    # Find PMV variables: 'Zone Thermal Comfort Fanger Model PMV' and 'PPD'
    pmv_indices = []
    ppd_indices = []
    for idx, info in metadata.items():
        name = info["name"]
        if "Zone Thermal Comfort Fanger Model PMV" in name:
            pmv_indices.append(idx)
        if "Zone Thermal Comfort Fanger Model PPD" in name:
            ppd_indices.append(idx)

    if not pmv_indices:
        print("Warning: No PMV variables found in ESO")
        return {}

    print(f"Found {len(pmv_indices)} PMV variable(s), {len(ppd_indices)} PPD variable(s)")

    zone_metrics = {}
    for idx in pmv_indices:
        info = metadata[idx]
        key = info["key"]
        zone_name = key  # e.g., "SPACE1-1 PEOPLE 1"
        if not zone_name:
            continue
        # Extract zone: key format "SPACE1-1 PEOPLE 1" -> "SPACE1-1"
        zone_match = re.match(r"([A-Z]+\d+-\d+)", zone_name)
        if not zone_match:
            continue
        zone = zone_match.group(1)
        values = data.get(idx, [])
        if not values:
            continue
        avg = sum(values) / len(values)
        min_v = min(values)
        max_v = max(values)
        # Comfort: PMV in [-0.5, 0.5]
        comfortable = sum(1 for v in values if -0.5 <= v <= 0.5)
        total = len(values)
        comfort_pct = (comfortable / total * 100) if total > 0 else 0
        zone_metrics[zone] = {
            "avg_pmv": avg,
            "min_pmv": min_v,
            "max_pmv": max_v,
            "comfort_pct": comfort_pct,
            "total_timesteps": total,
            "comfortable_timesteps": comfortable,
        }

    # Overall metrics across all zones
    if zone_metrics:
        all_avgs = [z["avg_pmv"] for z in zone_metrics.values()]
        overall_avg = sum(all_avgs) / len(all_avgs)
        total_timesteps = sum(z["total_timesteps"] for z in zone_metrics.values())
        total_comfortable = sum(z["comfortable_timesteps"] for z in zone_metrics.values())
        overall_comfort_pct = (total_comfortable / total_timesteps * 100) if total_timesteps > 0 else 0
        zone_metrics["overall"] = {
            "avg_pmv": overall_avg,
            "comfort_pct": overall_comfort_pct,
        }
    return zone_metrics

def main():
    parser = argparse.ArgumentParser(description="Extract metrics from simulation outputs")
    parser.add_argument("--output-dir", type=str, default="outputs/baseline",
                        help="Directory containing eplusout.sql, .eso, .err")
    parser.add_argument("--output-json", type=str, default=None,
                        help="Path for output JSON (default: <output-dir>_metrics.json)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base_dir, args.output_dir) if not os.path.isabs(args.output_dir) else args.output_dir

    sql_path = os.path.join(out_dir, "eplusout.sql")
    eso_path = os.path.join(out_dir, "eplusout.eso")
    log_path = os.path.join(out_dir, "eplusout.err")

    json_path = args.output_json
    if json_path is None:
        json_path = os.path.join(base_dir, os.path.basename(out_dir) + "_metrics.json")

    print("=" * 50)
    print(f"Extracting Metrics from: {out_dir}")
    print("=" * 50)

    # Energy (SQL)
    total_kwh, peak_kw, building_kwh, cooling_kwh, heating_kwh = extract_energy_metrics(sql_path, log_path)

    # PMV (ESO)
    zone_metrics = extract_pmv_metrics(eso_path)

    # Total hours from log
    total_hours = 0
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            content = f.read()
        step_lines = [l for l in content.split("\n") if l.startswith("Step ")]
        total_hours = len(step_lines)
        if total_hours > 0:
            print(f"Simulation timesteps: {total_hours}")
    if total_hours == 0:
        total_hours = 8760
        print(f"Simulation timesteps: {total_hours} (fallback)")

    # Compose JSON
    metrics = {
        "total_kwh": round(total_kwh, 1) if total_kwh is not None else None,
        "peak_kw": round(peak_kw, 1) if peak_kw is not None else None,
        "pmv_comfort_pct": round(zone_metrics.get("overall", {}).get("comfort_pct", 0), 1),
        "avg_pmv": round(zone_metrics.get("overall", {}).get("avg_pmv", 0), 3),
        "total_hours": total_hours,
        "zones": {}
    }
    # Add per-zone PMV metrics
    for zone, zm in zone_metrics.items():
        if zone == "overall":
            continue
        metrics["zones"][zone] = {
            "avg_pmv": round(zm["avg_pmv"], 3),
            "min_pmv": round(zm["min_pmv"], 3),
            "max_pmv": round(zm["max_pmv"], 3),
            "comfort_pct": round(zm["comfort_pct"], 1),
            "total_timesteps": zm["total_timesteps"],
            "comfortable_timesteps": zm["comfortable_timesteps"],
        }

    with open(json_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved to: {json_path}")

if __name__ == "__main__":
    main()