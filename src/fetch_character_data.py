import sqlite3

def fetch_character_data(db_path):
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Execute the query to fetch CharacterID, DisplayName, and Aliases from the Characters table
        cursor.execute("SELECT CharacterID, DisplayName, Aliases FROM Characters")

        # Fetch all rows from the result
        rows = cursor.fetchall()

        # Display the fetched data
        print(f"{'CharacterID':<12}{'DisplayName':<25}{'Aliases'}")
        print("="*50)
        for row in rows:
            print(f"{row[0]:<12}{row[1]:<25}{row[2] if row[2] else 'None'}")

        # Close the connection to the database
        conn.close()

    except sqlite3.Error as e:
        print(f"Error accessing the database: {e}")

if __name__ == "__main__":
    db_path = "C:/AI/Nova/src/nova_database.db"  # Update this path if necessary
    fetch_character_data(db_path)
