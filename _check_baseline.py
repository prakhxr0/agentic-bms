import sqlite3

c = sqlite3.connect("outputs/summer_baseline_1d/eplusout.sql")
cur = c.cursor()
cur.execute("SELECT COUNT(*) FROM ReportData")
print("ReportData rows:", cur.fetchone()[0])

cur.execute("""
    SELECT rdd.Name, rdd.KeyValue, AVG(rd.Value), MIN(rd.Value), MAX(rd.Value)
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    WHERE rdd.Name LIKE '%PMV%' AND rdd.KeyValue NOT LIKE '%PLENUM%'
    GROUP BY rdd.Name, rdd.KeyValue
""")
print("\nPMV by zone:")
for name, key, avg, mn, mx in cur.fetchall():
    print(f"  {key}: avg={avg:.4f} [{mn:.4f}, {mx:.4f}]")

# Energy
cur.execute("""
    SELECT rdd.Name, SUM(rd.Value)
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    WHERE rdd.Name = 'Electricity:Facility'
    GROUP BY rdd.Name
""")
total_j = cur.fetchone()
if total_j:
    print(f"\nTotal Energy: {total_j[1]/3.6e6:.1f} kWh")

c.close()
