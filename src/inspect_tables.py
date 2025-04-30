# File: inspect_tables.py

import sqlite3

def inspect_table(db_path, table_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table structure
        cursor.execute(f"PRAGMA table_info({table_name})")
        structure = cursor.fetchall()

        print(f"Structure of table '{table_name}':")
        for column in structure:
            print(f"Column: {column[1]}, Type: {column[2]}, Nullable: {'Yes' if column[3] == 0 else 'No'}, Default: {column[4]}")

        # Get sample content (first 5 rows)
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        content = cursor.fetchall()

        print(f"Sample content of table '{table_name}' (first {len(content)} rows):")
        for row in content:
            print(row)

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()


# Database path
db_path = "C:\\AI\\Nova\\src\\nova_database.db"

# Uncomment the table you want to inspect:
inspect_table(db_path, "Events")
# inspect_table(db_path, "Locations")
# inspect_table(db_path, "Entities")
# inspect_table(db_path, "EventCharacters")
# inspect_table(db_path, "EventLocations")
# inspect_table(db_path, "EventEntities")
# inspect_table(db_path, "Characters")
# inspect_table(db_path, "PrimaryCharacters")
# inspect_table(db_path, "SecondaryCharacters")
# inspect_table(db_path, "TertiaryCharacters")
# inspect_table(db_path, "QuaternaryCharacters")
# inspect_table(db_path, "TabEvents")
# inspect_table(db_path, "Sources")
# inspect_table(db_path, "EventMetadata")
