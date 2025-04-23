import sqlite3
import os

# Get the path to the database file
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "nova_database.db")

def get_table_info(table_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table info
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"\nTable: {table_name}")
    print("Columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Get the first row of data (if any)
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print("\nSample data (first row):")
        for col, value in zip([c[1] for c in columns], row):
            print(f"  {col}: {value}")
    else:
        print("\nNo data in this table.")
    
    conn.close()

# Uncomment the table you want to inspect
if __name__ == "__main__":
    # Permanent Tables
    # get_table_info("Events")
    # get_table_info("Locations")
    # get_table_info("Entities")
    # get_table_info("EventCharacters")
    # get_table_info("EventLocations")
    # get_table_info("EventEntities")
    # get_table_info("PrimaryCharacters")
    # get_table_info("SecondaryCharacters")
    # get_table_info("TertiaryCharacters")
    # get_table_info("QuaternaryCharacters")
    # get_table_info("TabEvents")
    # get_table_info("Sources")
    get_table_info("Characters")
    # get_table_info("EventMetadata")
    
    # Transient Tables
    # get_table_info("TransientEvents")
    # get_table_info("TransientCharacters")
    # get_table_info("TransientLocations")
    # get_table_info("TransientEntities")
    # get_table_info("TransientSources")
    # get_table_info("TransientEventCharacters")
    # get_table_info("TransientEventLocations")
    # get_table_info("TransientEventEntities")
    # get_table_info("TransientEventMetadata")
    pass