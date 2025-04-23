import sqlite3

def get_character_data(db_path, character_name="John Considine"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute("SELECT * FROM Characters WHERE DisplayName = ? LIMIT 1", (character_name,))
        columns = [description[0] for description in cursor.description]
        
        # Get the data
        row = cursor.fetchone()
        
        if row:
            char_data = dict(zip(columns, row))
            return char_data
        else:
            return None
            
    except sqlite3.Error as e:
        print(f"Error accessing database at {db_path}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def compare_character_data():
    c_path = "C:\\AI\\Nova\\src\\nova_database.db"
    d_path = "D:\\AI\\Nova1\\src\\nova_database.db"
    
    print("\nChecking C drive database:")
    print("-" * 50)
    c_data = get_character_data(c_path)
    if c_data:
        for key, value in c_data.items():
            print(f"{key}: {value}")
    
    print("\nChecking D drive database:")
    print("-" * 50)
    d_data = get_character_data(d_path)
    if d_data:
        for key, value in d_data.items():
            print(f"{key}: {value}")

if __name__ == "__main__":
    compare_character_data()