import sqlite3

def check_location_occupations():
    conn = sqlite3.connect("C:\\AI\\Nova\\src\\nova_database.db")
    cursor = conn.cursor()
    
    print("Checking LocationOccupations table:")
    print("-" * 50)
    
    cursor.execute("SELECT * FROM LocationOccupations")
    rows = cursor.fetchall()
    
    if rows:
        cursor.execute("PRAGMA table_info(LocationOccupations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        for row in rows:
            print("\nOccupation Record:")
            for col, val in zip(columns, row):
                print(f"{col}: {val}")
    else:
        print("No records found in LocationOccupations table")
    
    conn.close()

if __name__ == "__main__":
    check_location_occupations()