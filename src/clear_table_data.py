import sqlite3
import os

# Get the path to the database file
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, '..', 'src', 'nova_database.db')

def clear_table(table_name):
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Delete all rows from the specified table
        cursor.execute(f"DELETE FROM {table_name}")

        # Reset the primary key (assuming it's named 'ID' or ends with 'ID')
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")

        # Commit the changes
        conn.commit()

        print(f"Table '{table_name}' has been cleared and its primary key reset.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        # Close the connection
        if conn:
            conn.close()

# Uncomment only the table you want to clear
if __name__ == "__main__":
    # clear_table("Sources")
    # clear_table("Events")
    # clear_table("EventCharacters")
    # clear_table("EventLocations")
    # clear_table("EventEntities")
    # clear_table("EventMetadata")
    # clear_table("NewspaperPages")
    pass