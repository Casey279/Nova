import sqlite3

# Define the path to your database
db_path = "C:\\AI\\Nova\\src\\nova_database.db"

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fetch the column headers and contents of the Sources table
cursor.execute("PRAGMA table_info(Sources)")
columns = [description[1] for description in cursor.fetchall()]

cursor.execute("SELECT * FROM Sources")
rows = cursor.fetchall()

# Display column headers and contents
print("Columns:", columns)
for row in rows:
    print(row)

# Close the connection
conn.close()
