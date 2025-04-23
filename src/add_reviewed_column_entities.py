import sqlite3

# Path to your database
db_path = "C:/AI/Nova/nova_database.db"

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if the 'Reviewed' column exists, and if not, add it
try:
    cursor.execute("ALTER TABLE Entities ADD COLUMN Reviewed INTEGER DEFAULT 0")
    print("Column 'Reviewed' added successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'Reviewed' already exists.")
    else:
        print("An error occurred:", e)

# Close the connection
conn.commit()
conn.close()
