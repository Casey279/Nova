# File: table_entities.py

import sqlite3
from sqlite3 import Error

class EntitiesTable:
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

    def insert_entity(self, display_name, name=None, aliases=None, description=None, 
                     entity_type=None, start_date=None, end_date=None, associated_persons=None,
                     image_file=None, review_status='needs_review'):
        """Insert a new entity into the Entities table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO Entities 
                (DisplayName, Name, Aliases, Description, EntityType, 
                 StartDate, EndDate, AssociatedPersons, ImageFile, ReviewStatus) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (display_name, name or display_name, aliases, description, entity_type,
                  start_date, end_date, associated_persons, image_file, review_status))
            self.conn.commit()
            print("Entity inserted successfully.")
            cursor.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting entity: {e}")
            return None

    def update_entity(self, entity_id, display_name=None, name=None, aliases=None, 
                     description=None, entity_type=None, start_date=None, end_date=None, 
                     associated_persons=None, image_file=None, review_status=None):
        """Update an entity in the Entities table."""
        try:
            cursor = self.conn.cursor()
            
            # Get current values to use if not provided
            cursor.execute('''
                SELECT DisplayName, Name, Aliases, Description, EntityType, 
                       StartDate, EndDate, AssociatedPersons, ImageFile, ReviewStatus
                FROM Entities WHERE EntityID = ?
            ''', (entity_id,))
            current = cursor.fetchone()
            
            if not current:
                print(f"Entity with ID {entity_id} not found.")
                return False
                
            # Use provided values or current values if not provided
            display_name = display_name if display_name is not None else current[0]
            name = name if name is not None else current[1]
            aliases = aliases if aliases is not None else current[2]
            description = description if description is not None else current[3]
            entity_type = entity_type if entity_type is not None else current[4]
            start_date = start_date if start_date is not None else current[5]
            end_date = end_date if end_date is not None else current[6]
            associated_persons = associated_persons if associated_persons is not None else current[7]
            image_file = image_file if image_file is not None else current[8]
            review_status = review_status if review_status is not None else current[9]
            
            cursor.execute('''
                UPDATE Entities 
                SET DisplayName = ?, Name = ?, Aliases = ?, Description = ?, 
                    EntityType = ?, StartDate = ?, EndDate = ?, AssociatedPersons = ?, 
                    ImageFile = ?, ReviewStatus = ?
                WHERE EntityID = ?
            ''', (display_name, name, aliases, description, entity_type,
                  start_date, end_date, associated_persons, image_file, review_status, entity_id))
            self.conn.commit()
            print("Entity updated successfully.")
            return True
        except Error as e:
            print(f"Error updating entity: {e}")
            return False

    def delete_entity(self, entity_id):
        """Delete an entity from the Entities table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM Entities WHERE EntityID = ?", (entity_id,))
            self.conn.commit()
            print("Entity deleted successfully.")
            return True
        except Error as e:
            print(f"Error deleting entity: {e}")
            return False

    def get_entity(self, entity_id):
        """Get an entity by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT EntityID, DisplayName, Name, Aliases, Description, 
                       EntityType, StartDate, EndDate, AssociatedPersons, ImageFile, ReviewStatus
                FROM Entities 
                WHERE EntityID = ?
            ''', (entity_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error getting entity: {e}")
            return None

    def get_all_entities(self):
        """Get all entities."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT EntityID, DisplayName, Name, Aliases, Description, 
                       EntityType, StartDate, EndDate, AssociatedPersons, ImageFile, ReviewStatus
                FROM Entities
                ORDER BY DisplayName
            ''')
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting entities: {e}")
            return []

    def search_entities(self, search_term):
        """Search for entities by name, alias, or description."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT EntityID, DisplayName, Name, Aliases, Description, 
                       EntityType, StartDate, EndDate, AssociatedPersons, ImageFile, ReviewStatus
                FROM Entities
                WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ? OR 
                      Description LIKE ? OR EntityType LIKE ?
                ORDER BY DisplayName
            ''', (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", 
                  f"%{search_term}%", f"%{search_term}%"))
            return cursor.fetchall()
        except Error as e:
            print(f"Error searching entities: {e}")
            return []
            
    def get_entities_by_type(self, entity_type):
        """Get entities by type."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT EntityID, DisplayName, Name, Aliases, Description, 
                       EntityType, StartDate, EndDate, AssociatedPersons, ImageFile, ReviewStatus
                FROM Entities
                WHERE EntityType = ?
                ORDER BY DisplayName
            ''', (entity_type,))
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting entities by type: {e}")
            return []

    def get_entity_types(self):
        """Get all unique entity types."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT DISTINCT EntityType
                FROM Entities
                WHERE EntityType IS NOT NULL AND EntityType != ''
                ORDER BY EntityType
            ''')
            return [row[0] for row in cursor.fetchall()]
        except Error as e:
            print(f"Error getting entity types: {e}")
            return []

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")