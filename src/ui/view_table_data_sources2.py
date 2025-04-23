import sqlite3

conn = sqlite3.connect("C:\\AI\\Nova\\src\\nova_database.db")
cursor = conn.cursor()
cursor.execute("SELECT SourceID, SourceName, Aliases FROM Sources")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
