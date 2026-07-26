import sqlite3
conn = sqlite3.connect('outputs/wiring_test/eplusout.sql')
cursor = conn.cursor()
cursor.execute('SELECT DISTINCT Name, KeyValue FROM ReportDataDictionary WHERE Name = "Schedule Value"')
for row in cursor.fetchall():
    print(row)