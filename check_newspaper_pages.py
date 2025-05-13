import sqlite3
import os

def check_database():
    db_path = '/mnt/c/AI/Nova/nova_database.db'  # Updated path
    
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if NewspaperPages table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='NewspaperPages'")
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        print("NewspaperPages table does not exist!")
        return
    
    # Count records in the table
    cursor.execute("SELECT COUNT(*) FROM NewspaperPages")
    count = cursor.fetchone()[0]
    print(f"Total records in NewspaperPages table: {count}")
    
    # Get sample records if there are any
    if count > 0:
        cursor.execute("SELECT PageID, SourceID, LCCN, IssueDate, Sequence FROM NewspaperPages LIMIT 5")
        records = cursor.fetchall()
        print("\nSample records:")
        for record in records:
            print(f"PageID: {record[0]}, SourceID: {record[1]}, LCCN: {record[2]}, IssueDate: {record[3]}, Sequence: {record[4]}")
    
    # Count records in Sources table
    cursor.execute("SELECT COUNT(*) FROM Sources")
    count = cursor.fetchone()[0]
    print(f"\nTotal records in Sources table: {count}")
    
    # Get sample records if there are any
    if count > 0:
        cursor.execute("SELECT SourceID, SourceName, Aliases FROM Sources LIMIT 5")
        records = cursor.fetchall()
        print("\nSample sources:")
        for record in records:
            print(f"SourceID: {record[0]}, SourceName: {record[1]}, Aliases: {record[2]}")
    
    conn.close()

if __name__ == "__main__":
    check_database()