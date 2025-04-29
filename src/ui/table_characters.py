# File: table_characters.py

import sqlite3
from sqlite3 import Error

class CharactersTable:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.create_connection()
        self.create_table()

    def create_connection(self):
        """Create a database connection to SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"Connected to database at {self.db_path}")
        except Error as e:
            print(f"Error connecting to database: {e}")

    def create_table(self):
        """Create the Characters table if it doesn't exist."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS Characters (
                CharacterID INTEGER PRIMARY KEY AUTOINCREMENT,
                DisplayName TEXT NOT NULL UNIQUE,
                FirstName TEXT,
                MiddleName TEXT,
                LastName TEXT,
                Title TEXT,
                Suffix TEXT,
                Aliases TEXT,
                Description TEXT,
                ImageFile TEXT,
                Reviewed INTEGER DEFAULT 0
            )
            ''')
            self.conn.commit()
            print("Characters table created or verified successfully.")
        except Error as e:
            print(f"Error creating Characters table: {e}")

    def insert_character(self, display_name, first_name=None, middle_name=None, last_name=None, 
                        title=None, suffix=None, aliases=None, description=None, 
                        image_file=None, reviewed=0):
        """Insert a new character into the Characters table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO Characters 
                (DisplayName, FirstName, MiddleName, LastName, Title, Suffix, 
                 Aliases, Description, ImageFile, Reviewed) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (display_name, first_name, middle_name, last_name, title, suffix, 
                 aliases, description, image_file, reviewed))
            self.conn.commit()
            print("Character inserted successfully.")
            cursor.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting character: {e}")
            return None

    def update_character(self, character_id, display_name=None, first_name=None, middle_name=None, 
                        last_name=None, title=None, suffix=None, aliases=None, 
                        description=None, image_file=None, reviewed=None):
        """Update a character in the Characters table."""
        try:
            cursor = self.conn.cursor()
            
            # Get current values to use if not provided
            cursor.execute('''
                SELECT DisplayName, FirstName, MiddleName, LastName, Title, Suffix, 
                       Aliases, Description, ImageFile, Reviewed
                FROM Characters WHERE CharacterID = ?
            ''', (character_id,))
            current = cursor.fetchone()
            
            if not current:
                print(f"Character with ID {character_id} not found.")
                return False
                
            # Use provided values or current values if not provided
            display_name = display_name if display_name is not None else current[0]
            first_name = first_name if first_name is not None else current[1]
            middle_name = middle_name if middle_name is not None else current[2]
            last_name = last_name if last_name is not None else current[3]
            title = title if title is not None else current[4]
            suffix = suffix if suffix is not None else current[5]
            aliases = aliases if aliases is not None else current[6]
            description = description if description is not None else current[7]
            image_file = image_file if image_file is not None else current[8]
            reviewed = reviewed if reviewed is not None else current[9]
            
            cursor.execute('''
                UPDATE Characters 
                SET DisplayName = ?, FirstName = ?, MiddleName = ?, LastName = ?, 
                    Title = ?, Suffix = ?, Aliases = ?, Description = ?, 
                    ImageFile = ?, Reviewed = ?
                WHERE CharacterID = ?
            ''', (display_name, first_name, middle_name, last_name, title, suffix, 
                 aliases, description, image_file, reviewed, character_id))
            self.conn.commit()
            print("Character updated successfully.")
            return True
        except Error as e:
            print(f"Error updating character: {e}")
            return False

    def delete_character(self, character_id):
        """Delete a character from the Characters table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM Characters WHERE CharacterID = ?", (character_id,))
            self.conn.commit()
            print("Character deleted successfully.")
            return True
        except Error as e:
            print(f"Error deleting character: {e}")
            return False

    def get_character(self, character_id):
        """Get a character by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName, 
                       Title, Suffix, Aliases, Description, ImageFile, Reviewed
                FROM Characters 
                WHERE CharacterID = ?
            ''', (character_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error getting character: {e}")
            return None

    def get_all_characters(self):
        """Get all characters."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName, 
                       Title, Suffix, Aliases, Description, ImageFile, Reviewed
                FROM Characters
                ORDER BY DisplayName
            ''')
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting characters: {e}")
            return []

    def search_characters(self, search_term):
        """Search for characters by name or description."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName, 
                       Title, Suffix, Aliases, Description, ImageFile, Reviewed
                FROM Characters
                WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR 
                      Aliases LIKE ? OR Description LIKE ?
                ORDER BY DisplayName
            ''', (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", 
                  f"%{search_term}%", f"%{search_term}%"))
            return cursor.fetchall()
        except Error as e:
            print(f"Error searching characters: {e}")
            return []

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")