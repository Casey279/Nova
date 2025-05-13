import sqlite3
import os

# Get the path to the database file
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, '..', 'src', 'nova_database.db')

def view_table_contents(table_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Get all rows
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        print(f"\nContents of {table_name}:")
        print("-" * 50)
        print("Columns:", ", ".join(columns))
        print("-" * 50)
        
        if not rows:
            print("Table is empty")
        else:
            for row in rows:
                print(row)
                
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Uncomment to view specific table contents
    # view_table_contents("Events")
    # view_table_contents("Locations")
    # view_table_contents("Entities")
    # view_table_contents("Characters")
    # view_table_contents("Sources")
    # view_table_contents("EventCharacters")
    # view_table_contents("EventLocations")
    # view_table_contents("EventEntities")
    # view_table_contents("EventMetadata")
    # view_table_contents("NewspaperPages")

    # Transient Tables
    # view_table_contents("TransientEvents")
    # view_table_contents("TransientCharacters")
    # view_table_contents("TransientLocations")
    # view_table_contents("TransientEntities")
    # view_table_contents("TransientSources")
    # view_table_contents("TransientEventCharacters")
    # view_table_contents("TransientEventLocations")
    # view_table_contents("TransientEventEntities")
    # view_table_contents("TransientEventMetadata")
    pass