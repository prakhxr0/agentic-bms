import sqlite3
conn = sqlite3.connect('outputs/wiring_test/eplusout.sql')
cursor = conn.cursor()
cursor.execute('SELECT ReportDataDictionaryIndex, Name, KeyValue FROM ReportDataDictionary WHERE Name = "Schedule Value" AND KeyValue IN ("Clg-SetP-Sch", "Htg-SetP-Sch")')
for row in cursor.fetchall():
    print('Dict:', row)
    idx = row[0]
    cursor.execute('SELECT TimeIndex, Value FROM ReportData WHERE ReportDataDictionaryIndex = ? ORDER BY TimeIndex', (idx,))
    vals = cursor.fetchall()
    print('  Values (first 20):', vals[:20])
    print('  Min:', min(v[1] for v in vals), 'Max:', max(v[1] for v in vals), 'Count:', len(vals))