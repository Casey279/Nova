import sqlite3

def display_table_schema(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print(f"\nTable: {table_name}")
    print("-" * 50)
    for col in columns:
        print(f"Column: {col[1]}, Type: {col[2]}, NotNull: {col[3]}, DefaultVal: {col[4]}, PK: {col[5]}")

def main():
    try:
        # Connect to your database
        conn = sqlite3.connect('nova_database.db')  # Replace with your actual database name if different
        cursor = conn.cursor()

        # List of tables to check
        tables = ['table_events', 'table_characters', 'table_locations', 'table_entities', 'table_sources']

        # Display schema for each table
        for table in tables:
            display_table_schema(cursor, table)

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
