import sqlite3

# Replace with your actual database path
db_path = "C:/AI/Nova/src/nova_database.db"

def check_table_schema(table_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        if columns:
            print(f"{table_name} table schema:")
            for column in columns:
                print(f"Column: {column[1]}, Type: {column[2]}")
        else:
            print(f"No information found for the '{table_name}' table. It might not exist.")

    except sqlite3.Error as e:
        print(f"An error occurred while checking schema for table '{table_name}': {e}")

    finally:
        if conn:
            conn.close()

# Uncomment the lines below to check the schema of any table
check_table_schema("Sources")
# check_table_schema("Events")
# check_table_schema("Characters")
# check_table_schema("Locations")
# check_table_schema("Entities")
