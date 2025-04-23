# File: view_parsing_rules.py

import sqlite3
import json
import os

def view_parsing_rules():
    # Point directly to the database in the src folder
    db_path = os.path.join(os.path.dirname(__file__), "nova_database.db")
    print(f"Looking for database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all rules from FilenameParsingRules table
        cursor.execute("SELECT * FROM FilenameParsingRules")
        rules = cursor.fetchall()
        
        # Get column names for FilenameParsingRules table
        cursor.execute("PRAGMA table_info(FilenameParsingRules)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print("\nContents of FilenameParsingRules table:")
        print("-" * 100)
        
        # Print column headers
        for col in columns:
            print(f"{col:<20}", end="")
        print("\n" + "-" * 100)
        
        # Print data rows
        for rule in rules:
            for value in rule:
                if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                    try:
                        # Format JSON fields more readably
                        parsed = json.loads(value)
                        value = json.dumps(parsed, indent=2)
                    except json.JSONDecodeError:
                        pass
                print(f"{str(value)[:19]:<20}", end="")
            print()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    view_parsing_rules()