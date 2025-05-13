#!/usr/bin/env python3
"""
Script to clear Sources and NewspaperPages tables to start fresh.
"""

import os
import sqlite3

# Path to the database
# Try to find the database file in common locations
def find_database():
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_database.db"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nova_database.db"),
        "/mnt/c/AI/Nova/nova_database.db"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found database at: {path}")
            return path

    # If database not found, ask the user
    db_path = input("Database not found in common locations. Please enter the full path to nova_database.db: ")
    if os.path.exists(db_path):
        return db_path
    else:
        print(f"Database not found at {db_path}")
        return None

DB_PATH = find_database()

def clear_tables():
    if DB_PATH is None:
        print("Cannot clear tables: Database not found")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check for NewspaperPages table in different case formats
    newspaper_table_name = None
    for table_name in ['NewspaperPages', 'newspaper_pages', 'NEWSPAPERPAGES']:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone():
            newspaper_table_name = table_name
            break

    if newspaper_table_name:
        # Get count before deleting
        cursor.execute(f"SELECT COUNT(*) FROM {newspaper_table_name}")
        count = cursor.fetchone()[0]
        print(f"Found {count} records in {newspaper_table_name} table")

        # Delete all records
        cursor.execute(f"DELETE FROM {newspaper_table_name}")
        print(f"Deleted all records from {newspaper_table_name} table")
    else:
        print("Newspaper pages table does not exist, will be created during import")
    
    # Clear Sources table
    cursor.execute("SELECT COUNT(*) FROM Sources")
    count = cursor.fetchone()[0]
    print(f"Found {count} records in Sources table")
    
    # Delete only newspaper sources
    cursor.execute("DELETE FROM Sources WHERE SourceType = 'newspaper'")
    print(f"Deleted newspaper records from Sources table")
    
    # Get remaining count
    cursor.execute("SELECT COUNT(*) FROM Sources")
    remaining = cursor.fetchone()[0]
    print(f"Remaining records in Sources table: {remaining}")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print("Tables cleared successfully")

if __name__ == "__main__":
    print("Clearing newspaper tables...")
    clear_tables()
    print("Done!")