"""Compare setpoints and zone temps between baseline and AI."""
import sqlite3

def get_data(path, label):
    c = sqlite3.connect(path)
    cur = c.cursor()
    for name in ["Zone Thermostat Heating Setpoint Temperature",
                  "Zone Thermostat Cooling Setpoint Temperature",
                  "Zone Air Temperature"]:
        cur.execute("""
            SELECT KeyValue, AVG(Value), MIN(Value), MAX(Value)
            FROM ReportData rd
            JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
            WHERE rdd.Name = ? AND KeyValue NOT LIKE '%PLENUM%'
            GROUP BY KeyValue
        """, (name,))
        rows = cur.fetchall()
        print(f"\n{label} - {name}:")
        for k, avg, mn, mx in rows:
            print(f"  {k}: avg={avg:.2f} [{mn:.2f}, {mx:.2f}]")
    c.close()

get_data("outputs/summer_baseline/eplusout.sql", "BASELINE (7-day)")
get_data("outputs/ai_1day_test_v3/eplusout.sql", "AI (1-day)")
