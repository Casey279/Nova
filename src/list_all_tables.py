import sqlite3
import os

# Get the path to the database file
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, '..', 'src', 'nova_database.db')

def list_tables():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query to get all table names
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
        """)
        
        tables = cursor.fetchall()
        print("\nTables in database:")
        print("-" * 20)
        for table in tables:
            print(table[0])
            
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_tables()