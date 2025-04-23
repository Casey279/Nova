import sqlite3
import os

# Get the path to the Nova database
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, '..', 'src', 'nova_database.db')

def clear_all_tables():
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Fetch all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            # Delete all rows from each table
            cursor.execute(f"DELETE FROM {table}")
            print(f"Cleared table: {table}")

            # Reset the primary key sequence if applicable
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")

        # Commit changes
        conn.commit()
        print("\nAll tables have been cleared successfully. The database is now empty.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()

# Run the script
if __name__ == "__main__":
    clear_all_tables()
