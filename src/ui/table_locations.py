# File: table_locations.py

import sqlite3

class TableLocations:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = self.create_connection()

    def create_connection(self):
        """Create a database connection to the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            print(f"Connected to the database at {self.db_path}")
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return None

    def create_locations_table(self):
        """Create the Locations table with all necessary fields."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Locations (
                    LocationID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DisplayName TEXT UNIQUE,
                    LocationName TEXT,
                    Aliases TEXT,
                    Address TEXT,
                    City TEXT,
                    LocationType TEXT,
                    YearBuilt TEXT,
                    Description TEXT,
                    Owners TEXT,
                    Managers TEXT,
                    Employees TEXT,
                    Summary TEXT,
                    ImagePath TEXT
                )
            """)
            self.conn.commit()
            print("Locations table created successfully.")
        except sqlite3.Error as e:
            print(f"Error creating Locations table: {e}")

    def insert_location(self, display_name, location_name, aliases, address, city, location_type, year_built, description, owners, managers, employees, summary, image_path):
        """Insert a new location into the Locations table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO Locations (DisplayName, LocationName, Aliases, Address, City, LocationType, YearBuilt, Description, Owners, Managers, Employees, Summary, ImagePath)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (display_name, location_name, aliases, address, city, location_type, year_built, description, owners, managers, employees, summary, image_path))
            self.conn.commit()
            print("Location inserted successfully.")
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting location: {e}")
            return None

    def get_all_locations(self):
        """Fetch all locations from the Locations table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM Locations")
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching locations: {e}")
            return []

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")
