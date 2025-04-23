import sqlite3
import os

# Get the path to the database file
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, '..', 'src', 'nova_database.db')

def delete_sources_and_reset():
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Delete the specific entries
        cursor.execute("DELETE FROM Sources WHERE SourceName IN (?, ?)", 
                      ('The Cincinnati Enquirer', 'The Seattle Post Intelligencer'))
        
        # Get the maximum ID after deletion
        cursor.execute("SELECT MAX(SourceID) FROM Sources")
        max_id = cursor.fetchone()[0]

        # Reset the sequence to the current maximum ID
        cursor.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'Sources'", (max_id,))
        
        # Commit the changes
        conn.commit()
        
        print("Specified sources deleted and sequence reset successfully.")
        print(f"Next SourceID will be: {max_id + 1}")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        # Close the connection
        if conn:
            conn.close()

if __name__ == "__main__":
    delete_sources_and_reset()