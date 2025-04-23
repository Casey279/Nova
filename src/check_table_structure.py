# File: check_table_structure.py

import sqlite3
import os

def check_table_structure():
    db_path = os.path.join(os.path.dirname(__file__), "nova_database.db")
    print(f"Checking database at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='FilenameParsingRules'")
    result = cursor.fetchone()
    
    if result:
        print("\nTable Structure:")
        print("-" * 80)
        print(result[0])
    else:
        print("Table not found!")
    
    conn.close()

if __name__ == "__main__":
    check_table_structure()