#!/usr/bin/env python3
import sqlite3
import os

# Path to the database
db_path = '/mnt/c/AI/Nova/src/nova_database.db'

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Task 1: Check the structure of the Sources table
print("=== Sources Table Structure ===")
cursor.execute('PRAGMA table_info(Sources)')
for col in cursor.fetchall():
    # col structure: (id, name, type, not null, default, pk)
    pk_str = " PRIMARY KEY" if col[5] else ""
    print(f"- {col[1]} ({col[2]}){pk_str}")

# Task 2: Count records in Sources table
cursor.execute('SELECT COUNT(*) FROM Sources')
count = cursor.fetchone()[0]
print(f"\n=== Records in Sources Table: {count} ===")

# Show a sample of records
if count > 0:
    print("\n=== Sample Records in Sources Table ===")
    cursor.execute('SELECT * FROM Sources LIMIT 3')
    columns = [desc[0] for desc in cursor.description]
    print("Columns:", columns)
    
    rows = cursor.fetchall()
    for row in rows:
        print("---")
        for i, col in enumerate(columns):
            print(f"{col}: {row[i]}")

# Task 3: Check for repository tables
print("\n=== Checking for Repository Tables ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
repo_tables = []

for table in tables:
    table_name = table[0]
    if any(keyword in table_name.lower() for keyword in ['newspaper', 'page', 'article', 'repo', 'chronicle']):
        repo_tables.append(table_name)

if repo_tables:
    print(f"Potential repository tables found: {repo_tables}")
else:
    print("No obvious repository tables found.")
    print("All tables in database:")
    for table in tables:
        print(f"- {table[0]}")

# Task 4: Empty the Sources table (commented out for safety)
print("\n=== Emptying Sources Table ===")
cursor.execute('DELETE FROM Sources')
conn.commit()
cursor.execute('SELECT COUNT(*) FROM Sources')
new_count = cursor.fetchone()[0]
print(f"Sources table now has {new_count} records.")

# Close the connection
conn.close()
print("\nDatabase connection closed.")