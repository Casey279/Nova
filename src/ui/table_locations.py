# File: table_locations.py

import sqlite3
from sqlite3 import Error

class LocationsTable:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.create_connection()
        

    def create_connection(self):
        """Create a database connection to SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"Connected to database at {self.db_path}")
        except Error as e:
            print(f"Error connecting to database: {e}")

    def insert_location(self, display_name, location_name=None, aliases=None, description=None, 
                        coordinates=None, address=None, city=None, state=None, country=None,
                        image_file=None, review_status='needs_review'):
        """Insert a new location into the Locations table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO Locations 
                (DisplayName, LocationName, Aliases, Description, Coordinates, 
                 Address, City, State, Country, ImageFile, ReviewStatus) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (display_name, location_name or display_name, aliases, description, 
                  coordinates, address, city, state, country, image_file, review_status))
            self.conn.commit()
            print("Location inserted successfully.")
            cursor.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting location: {e}")
            return None

    def update_location(self, location_id, display_name=None, location_name=None, aliases=None, 
                       description=None, coordinates=None, address=None, city=None, 
                       state=None, country=None, image_file=None, review_status=None):
        """Update a location in the Locations table."""
        try:
            cursor = self.conn.cursor()
            
            # Get current values to use if not provided
            cursor.execute('''
                SELECT DisplayName, LocationName, Aliases, Description, Coordinates, 
                       Address, City, State, Country, ImageFile, ReviewStatus
                FROM Locations WHERE LocationID = ?
            ''', (location_id,))
            current = cursor.fetchone()
            
            if not current:
                print(f"Location with ID {location_id} not found.")
                return False
                
            # Use provided values or current values if not provided
            display_name = display_name if display_name is not None else current[0]
            location_name = location_name if location_name is not None else current[1]
            aliases = aliases if aliases is not None else current[2]
            description = description if description is not None else current[3]
            coordinates = coordinates if coordinates is not None else current[4]
            address = address if address is not None else current[5]
            city = city if city is not None else current[6]
            state = state if state is not None else current[7]
            country = country if country is not None else current[8]
            image_file = image_file if image_file is not None else current[9]
            review_status = review_status if review_status is not None else current[10]
            
            cursor.execute('''
                UPDATE Locations 
                SET DisplayName = ?, LocationName = ?, Aliases = ?, Description = ?, 
                    Coordinates = ?, Address = ?, City = ?, State = ?, Country = ?, 
                    ImageFile = ?, ReviewStatus = ?
                WHERE LocationID = ?
            ''', (display_name, location_name, aliases, description, coordinates,
                  address, city, state, country, image_file, review_status, location_id))
            self.conn.commit()
            print("Location updated successfully.")
            return True
        except Error as e:
            print(f"Error updating location: {e}")
            return False

    def delete_location(self, location_id):
        """Delete a location from the Locations table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM Locations WHERE LocationID = ?", (location_id,))
            self.conn.commit()
            print("Location deleted successfully.")
            return True
        except Error as e:
            print(f"Error deleting location: {e}")
            return False

    def get_location(self, location_id):
        """Get a location by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                       Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
                FROM Locations 
                WHERE LocationID = ?
            ''', (location_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error getting location: {e}")
            return None

    def get_all_locations(self):
        """Get all locations."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                       Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
                FROM Locations
                ORDER BY DisplayName
            ''')
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting locations: {e}")
            return []

    def search_locations(self, search_term):
        """Search for locations by name, alias, or description."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                       Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
                FROM Locations
                WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ? OR 
                      Description LIKE ? OR Address LIKE ? OR City LIKE ?
                ORDER BY DisplayName
            ''', (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", 
                  f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
            return cursor.fetchall()
        except Error as e:
            print(f"Error searching locations: {e}")
            return []

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")