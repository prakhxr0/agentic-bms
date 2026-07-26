import sqlite3

def compare(sql_a, sql_b, label_a, label_b):
    conn_a = sqlite3.connect(sql_a)
    conn_b = sqlite3.connect(sql_b)
    cur_a = conn_a.cursor()
    cur_b = conn_b.cursor()
    
    for name in ["Zone Air Temperature", "Zone Thermal Comfort Fanger Model PMV"]:
        cur_a.execute("""
            SELECT rdd.KeyValue, AVG(rd.Value), MIN(rd.Value), MAX(rd.Value)
            FROM ReportData rd
            JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
            WHERE rdd.Name = ? AND rdd.KeyValue NOT LIKE 'PLENUM%'
            GROUP BY rdd.KeyValue
            ORDER BY rdd.KeyValue
        """, (name,))
        cur_b.execute("""
            SELECT rdd.KeyValue, AVG(rd.Value), MIN(rd.Value), MAX(rd.Value)
            FROM ReportData rd
            JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
            WHERE rdd.Name = ? AND rdd.KeyValue NOT LIKE 'PLENUM%'
            GROUP BY rdd.KeyValue
            ORDER BY rdd.KeyValue
        """, (name,))
        rows_a = cur_a.fetchall()
        rows_b = cur_b.fetchall()
        print(f"\n{name}:")
        for (ka, avga, mina, maxa), (kb, avgb, minb, maxb) in zip(rows_a, rows_b):
            same = abs(avga - avgb) < 0.001
            print(f"  {ka}: {label_a}={avga:.3f} {label_b}={avgb:.3f} same={same}")
    
    conn_a.close()
    conn_b.close()

compare(r"outputs\summer_baseline_1d\eplusout.sql",
        r"outputs\phase6_ai_1d\eplusout.sql",
        "BASELINE", "AI")
