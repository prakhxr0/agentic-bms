"""SQLite metrics extraction - canonical function for comparing runs."""

import sqlite3
from pathlib import Path


def extract_metrics(sql_path: Path) -> dict:
    """
    Extract canonical metrics from eplusout.sql for comparison.

    Returns:
        dict with keys:
        - total_electricity_kwh
        - cooling_electricity_kwh
        - heating_electricity_kwh
        - avg_pmv
        - avg_zone_temp_c
        - schedule_values: dict of schedule_name -> list of values
    """
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()

    metrics = {}

    # Total facility electricity (hourly meter -> sum to kWh)
    cursor.execute("""
        SELECT rd.Value
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Electricity:Facility'
    """)
    elec_vals = [row[0] for row in cursor.fetchall()]
    if elec_vals:
        # Values are in Joules per timestep; convert to kWh
        metrics["total_electricity_kwh"] = sum(elec_vals) / 3.6e6
    else:
        metrics["total_electricity_kwh"] = 0.0

    # Cooling electricity
    cursor.execute("""
        SELECT rd.Value
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Cooling:Electricity'
    """)
    cool_vals = [row[0] for row in cursor.fetchall()]
    metrics["cooling_electricity_kwh"] = sum(cool_vals) / 3.6e6 if cool_vals else 0.0

    # Heating electricity
    cursor.execute("""
        SELECT rd.Value
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Heating:Electricity'
    """)
    heat_vals = [row[0] for row in cursor.fetchall()]
    metrics["heating_electricity_kwh"] = sum(heat_vals) / 3.6e6 if heat_vals else 0.0

    # Average PMV (SPACE1-1 PEOPLE 1)
    cursor.execute("""
        SELECT rd.Value
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Zone Thermal Comfort Fanger Model PMV'
          AND rdd.KeyValue LIKE '%PEOPLE%'
    """)
    pmv_vals = [row[0] for row in cursor.fetchall()]
    metrics["avg_pmv"] = sum(pmv_vals) / len(pmv_vals) if pmv_vals else None

    # Average zone temperature
    cursor.execute("""
        SELECT rd.Value
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Zone Air Temperature'
          AND rdd.KeyValue = 'SPACE1-1'
    """)
    temp_vals = [row[0] for row in cursor.fetchall()]
    metrics["avg_zone_temp_c"] = sum(temp_vals) / len(temp_vals) if temp_vals else None

    # Schedule values for setpoint schedules
    schedule_values = {}
    for sched_name in ["CLG-SETP-SCH", "HTG-SETP-SCH"]:
        cursor.execute("""
            SELECT rd.Value
            FROM ReportData rd
            JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
            WHERE rdd.Name = 'Schedule Value'
              AND rdd.KeyValue = ?
            ORDER BY rd.TimeIndex
        """, (sched_name,))
        vals = [row[0] for row in cursor.fetchall()]
        schedule_values[sched_name] = vals

    metrics["schedule_values"] = schedule_values

    conn.close()
    return metrics


def print_metrics(metrics: dict, label: str = ""):
    """Pretty print metrics dict."""
    if label:
        print(f"\n=== {label} ===")
    print(f"  Total Electricity: {metrics.get('total_electricity_kwh', 0):.1f} kWh")
    print(f"  Cooling Electricity: {metrics.get('cooling_electricity_kwh', 0):.1f} kWh")
    print(f"  Heating Electricity: {metrics.get('heating_electricity_kwh', 0):.1f} kWh")
    print(f"  Avg PMV: {metrics.get('avg_pmv', 'N/A')}")
    print(f"  Avg Zone Temp: {metrics.get('avg_zone_temp_c', 'N/A'):.2f} °C")
    for sched, vals in metrics.get("schedule_values", {}).items():
        if vals:
            print(f"  {sched}: min={min(vals):.1f} max={max(vals):.1f} mean={sum(vals)/len(vals):.1f} count={len(vals)}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        m = extract_metrics(Path(sys.argv[1]))
        print_metrics(m, sys.argv[1])