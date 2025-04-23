import sqlite3

def inspect_table(db_path, table_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table structure
        cursor.execute(f"PRAGMA table_info({table_name})")
        structure = cursor.fetchall()

        print(f"\nStructure of table '{table_name}':")
        for column in structure:
            print(f"Column: {column[1]}, Type: {column[2]}, Nullable: {'Yes' if column[3] == 0 else 'No'}, Default: {column[4]}")

        # Get sample content (first 5 rows)
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        content = cursor.fetchall()

        print(f"\nSample content of table '{table_name}' (first 5 rows):")
        for row in content:
            print(row)

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()

# Old Database Tables (D:\Nova1\data\nova.db)
# Uncomment the table you want to inspect:
# inspect_table("D:\\Nova1\\data\\nova.db", "Locations")
# inspect_table("D:\\Nova1\\data\\nova.db", "SourceEvents")
# inspect_table("D:\\Nova1\\data\\nova.db", "Entities")
# inspect_table("D:\\Nova1\\data\\nova.db", "CharacterLocationRelations")
# inspect_table("D:\\Nova1\\data\\nova.db", "MediaSources")
# inspect_table("D:\\Nova1\\data\\nova.db", "PrimaryCharacters")
# inspect_table("D:\\Nova1\\data\\nova.db", "SecondaryCharacters")
# inspect_table("D:\\Nova1\\data\\nova.db", "TertiaryCharacters")
# inspect_table("D:\\Nova1\\data\\nova.db", "FamilyRelationships")
# inspect_table("D:\\Nova1\\data\\nova.db", "RelationshipTypes")
# inspect_table("D:\\Nova1\\data\\nova.db", "EntityLocationLinks")
# inspect_table("D:\\Nova1\\data\\nova.db", "LocationEvents")
# inspect_table("D:\\Nova1\\data\\nova.db", "EntityEvents")
# inspect_table("D:\\Nova1\\data\\nova.db", "Sources")
# inspect_table("D:\\Nova1\\data\\nova.db", "CharacterEntitiesRelations")
# inspect_table("D:\\Nova1\\data\\nova.db", "Events")
# inspect_table("D:\\Nova1\\data\\nova.db", "Characters")
# inspect_table("D:\\Nova1\\data\\nova.db", "CharacterEvents")
# inspect_table("D:\\Nova1\\data\\nova.db", "TabEvents")

# New Database Tables (C:\AI\Nova\src\nova_database.db)
# Uncomment the table you want to inspect:
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "Events")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "Locations")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "Entities")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "EventCharacters")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "EventLocations")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "EventEntities")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "Characters")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "PrimaryCharacters")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "SecondaryCharacters")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "TertiaryCharacters")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "QuaternaryCharacters")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "TabEvents")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "Sources")
# inspect_table("C:\\AI\\Nova\\src\\nova_database.db", "EventMetadata")