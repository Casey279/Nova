# File: database_manager.py

import sqlite3
from sqlite3 import Error

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.create_connection()
        self.create_tables()
        

    def create_connection(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            print(f"Connected to database at {self.db_path}")
        except Error as e:
            print(f"Error connecting to database: {e}")

    def create_tables(self):
        """Create necessary tables if they don't exist."""
        try:
            cursor = self.conn.cursor()

            # Create Sources Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Sources (
                    SourceID INTEGER PRIMARY KEY AUTOINCREMENT,
                    SourceName TEXT NOT NULL,
                    SourceType TEXT,
                    Aliases TEXT,
                    Publisher TEXT,
                    Location TEXT,
                    EstablishedDate TEXT,
                    DiscontinuedDate TEXT,
                    ImagePath TEXT,
                    ReviewStatus TEXT DEFAULT 'needs_review'
                )
            """)

            # Create Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Events (
                    EventID INTEGER PRIMARY KEY AUTOINCREMENT,
                    EventDate TEXT,
                    PublicationDate TEXT,
                    EventTitle TEXT,
                    EventText TEXT,
                    SourceType TEXT,
                    SourceName TEXT,
                    PageNumber TEXT,  
                    Filename TEXT,
                    FilePath TEXT,
                    SourceID INTEGER,
                    QualityScore INTEGER,
                    Status TEXT DEFAULT 'active',
                    FOREIGN KEY (SourceID) REFERENCES Sources(SourceID)
                )
            """)

            # Create Characters Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Characters (
                    CharacterID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DisplayName TEXT UNIQUE,
                    Salutation TEXT,
                    FirstName TEXT,
                    MiddleName TEXT,
                    LastName TEXT,
                    Suffix TEXT,
                    Aliases TEXT,
                    Gender TEXT,
                    BirthDate TEXT,
                    DeathDate TEXT,
                    Height TEXT,
                    Weight TEXT,
                    Eyes TEXT,
                    Hair TEXT,
                    Occupation TEXT,
                    Affiliations TEXT,
                    Associations TEXT,
                    PersonalityTraits TEXT,
                    BackgroundSummary TEXT,
                    Family TEXT,
                    FindAGrave TEXT,
                    MyersBriggs TEXT,
                    Enneagram TEXT,
                    ClifftonStrengths TEXT,
                    ImagePath TEXT,
                    Reviewed INTEGER
                )
            """)

            # Create Locations Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Locations (
                    LocationID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DisplayName TEXT UNIQUE,
                    LocationName TEXT,
                    Aliases TEXT,
                    Address TEXT,
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

            # Create Entities Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Entities (
                    EntityID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DisplayName TEXT UNIQUE,
                    Name TEXT,
                    Aliases TEXT,
                    Type TEXT,
                    Description TEXT,
                    EstablishedDate TEXT,
                    Affiliation TEXT,
                    Summary TEXT,
                    ImagePath TEXT,
                    KnownMembers TEXT DEFAULT ''
                )
            """)

            # Create Junction Tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS EventCharacters (
                    EventID INTEGER,
                    CharacterID INTEGER,
                    FOREIGN KEY (EventID) REFERENCES Events(EventID),
                    FOREIGN KEY (CharacterID) REFERENCES Characters(CharacterID),
                    PRIMARY KEY (EventID, CharacterID)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS EventLocations (
                    EventID INTEGER,
                    LocationID INTEGER,
                    FOREIGN KEY (EventID) REFERENCES Events(EventID),
                    FOREIGN KEY (LocationID) REFERENCES Locations(LocationID),
                    PRIMARY KEY (EventID, LocationID)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS EventEntities (
                    EventID INTEGER,
                    EntityID INTEGER,
                    FOREIGN KEY (EventID) REFERENCES Events(EventID),
                    FOREIGN KEY (EntityID) REFERENCES Entities(EntityID),
                    PRIMARY KEY (EventID, EntityID)
                )
            """)

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS EventMetadata (
                    MetadataID INTEGER PRIMARY KEY AUTOINCREMENT,
                    EventID INTEGER,
                    Key TEXT,
                    Value TEXT,
                    FOREIGN KEY (EventID) REFERENCES Events(EventID)
                )
            ''')

            # Add the LocationOccupations junction table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS LocationOccupations (
                    LocationID INTEGER,
                    CharacterID INTEGER,
                    RoleType TEXT,
                    StartDate TEXT,
                    EndDate TEXT,
                    Notes TEXT,
                    FOREIGN KEY (LocationID) REFERENCES Locations(LocationID),
                    FOREIGN KEY (CharacterID) REFERENCES Characters(CharacterID)
                )
            """)            

            self.conn.commit()
            print("Tables created or verified successfully.")
        except Error as e:
            print(f"Error creating tables: {e}")

    def add_status_column_to_events(self):
        """Add Status column to Events table if it doesn't exist"""
        try:
            # Check if Status column exists
            self.cursor.execute("PRAGMA table_info(Events)")
            columns = [column[1] for column in self.cursor.fetchall()]
            
            if 'Status' not in columns:
                self.cursor.execute("""
                    ALTER TABLE Events 
                    ADD COLUMN Status TEXT DEFAULT 'active'
                """)
                self.conn.commit()
                print("Status column added to Events table")
            else:
                print("Status column already exists in Events table")
        except sqlite3.Error as e:
            print(f"Error adding Status column: {e}")            
            

    def insert_event_metadata(self, event_id, key, value):
        try:
            self.cursor.execute("""
                INSERT INTO EventMetadata (EventID, Key, Value)
                VALUES (?, ?, ?)
            """, (event_id, key, value))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error inserting event metadata: {e}")

    def insert_event(self, event_date, publication_date, event_title, event_text, source_type, source_name, filename, filepath, source_id=None, quality_score=None):
        try:
            self.cursor.execute("""
                INSERT INTO Events (EventDate, PublicationDate, EventTitle, EventText, SourceType, SourceName, Filename, FilePath, SourceID, QualityScore)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_date, publication_date, event_title, event_text, source_type, source_name, filename, filepath, source_id, quality_score))
            self.conn.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"Error inserting event: {e}")
            return None

    def check_source_exists(self, source_name):
        """Check if source exists by name or alias"""
        try:
            cursor = self.conn.cursor()
            # Check main source name
            cursor.execute("SELECT SourceID FROM Sources WHERE SourceName = ?", (source_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
                
            # Check aliases
            cursor.execute("SELECT SourceID FROM Sources WHERE Aliases LIKE ?", (f"%{source_name}%",))
            result = cursor.fetchone()
            if result:
                return result[0]
                
            return None
        except sqlite3.Error as e:
            print(f"Error checking source: {e}")
            return None

    def add_preliminary_source(self, source_name):
        """Add a new source with preliminary information"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO Sources (SourceName, SourceType, ReviewStatus)
                VALUES (?, 'N', 'needs_review')
            ''', (source_name,))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error adding preliminary source: {e}")
            return None
        
    def update_characters_table_structure(self):
        """Update Characters table to include new name-related fields."""
        try:
            # Check for new columns
            self.cursor.execute("PRAGMA table_info(Characters)")
            existing_columns = [column[1] for column in self.cursor.fetchall()]
            
            # Add new columns if they don't exist
            new_columns = {
                'Prefix': 'TEXT',
                'MiddleName': 'TEXT',
                'Suffix': 'TEXT'
            }
            
            for column_name, column_type in new_columns.items():
                if column_name not in existing_columns:
                    self.cursor.execute(f"ALTER TABLE Characters ADD COLUMN {column_name} {column_type}")
                    print(f"Added {column_name} column to Characters table")
            
            self.conn.commit()
            print("Characters table structure updated successfully")
        except sqlite3.Error as e:
            print(f"Error updating Characters table structure: {e}")        

    def get_or_create_source(self, source_name, source_type='N'):
        """Get source ID or create new source if it doesn't exist."""
        try:
            # Check if source exists
            self.cursor.execute("SELECT SourceID FROM Sources WHERE SourceName = ?", (source_name,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, create new source
            self.cursor.execute("""
                INSERT INTO Sources (SourceName, SourceType, ReviewStatus)
                VALUES (?, ?, 'needs_review')
            """, (source_name, source_type))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error in get_or_create_source: {e}")
            return None

    def add_character_to_tertiary(self, character_id):
        """Add new character to tertiary table by default."""
        try:
            self.cursor.execute("""
                INSERT OR IGNORE INTO TertiaryCharacters (CharacterID)
                VALUES (?)
            """, (character_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error adding character to tertiary: {e}")

    def get_or_create_character(self, character_name):
        """Get character ID or create new character if doesn't exist."""
        try:
            # Check if character exists
            self.cursor.execute("SELECT CharacterID FROM Characters WHERE DisplayName = ?", (character_name,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, create new character
            self.cursor.execute("""
                INSERT INTO Characters (DisplayName, Reviewed)
                VALUES (?, 0)
            """, (character_name,))
            new_id = self.cursor.lastrowid
            
            # Add to tertiary table by default
            self.add_character_to_tertiary(new_id)
            
            self.conn.commit()
            return new_id
        except sqlite3.Error as e:
            print(f"Error in get_or_create_character: {e}")
            return None

    def get_or_create_location(self, location_name):
        """Get location ID or create new location if doesn't exist."""
        try:
            # Check if location exists
            self.cursor.execute("SELECT LocationID FROM Locations WHERE DisplayName = ?", (location_name,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, create new location
            self.cursor.execute("""
                INSERT INTO Locations (DisplayName, LocationName)
                VALUES (?, ?)
            """, (location_name, location_name))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error in get_or_create_location: {e}")
            return None

    def get_or_create_entity(self, entity_name):
        """Get entity ID or create new entity if doesn't exist."""
        try:
            # Check if entity exists
            self.cursor.execute("SELECT EntityID FROM Entities WHERE DisplayName = ?", (entity_name,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, create new entity
            self.cursor.execute("""
                INSERT INTO Entities (DisplayName, Name)
                VALUES (?, ?)
            """, (entity_name, entity_name))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error in get_or_create_entity: {e}")
            return None

    def get_source_by_id(self, source_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM Sources WHERE SourceID = ?", (source_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "SourceID": row[0],
                    "SourceName": row[1],
                    "SourceType": row[2],
                    "Abbreviation": row[3],
                    "Publisher": row[4],
                    "Location": row[5],
                    "EstablishedDate": row[6],
                    "DiscontinuedDate": row[7],
                    "ImagePath": row[8],
                    "SourceCode": row[9],
                    "Aliases": row[10],
                    "ReviewStatus": row[11],
                    "PoliticalAffiliations": row[12],
                    "Summary": row[13]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching source by ID: {e}")
            return None

    def get_events_by_source(self, source_id):
        """Fetch events associated with a specific source by SourceID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT EventID, EventDate, EventTitle 
                FROM Events 
                WHERE SourceID = ?
                ORDER BY EventDate DESC
            """, (source_id,))
            events = cursor.fetchall()
            # Map each event row to a dictionary
            return [{"EventID": row[0], "EventDate": row[1], "EventTitle": row[2]} for row in events]
        except sqlite3.Error as e:
            print(f"Error fetching events for source: {e}")
            return []


    def insert_or_get_source(self, source_name, source_type='N', publisher=None, location=None):
        try:
            # First try to find existing source
            self.cursor.execute("SELECT SourceID FROM Sources WHERE SourceName = ?", (source_name,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, insert new source
            # For unknown sources (XX code), set ReviewStatus to 'preliminary'
            review_status = 'preliminary' if source_type == 'XX' else 'needs_review'
            
            self.cursor.execute("""
                INSERT INTO Sources (SourceName, SourceType, Publisher, Location, ReviewStatus)
                VALUES (?, ?, ?, ?, ?)
            """, (source_name, source_type, publisher, location, review_status))
            self.conn.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"Error inserting or getting source: {e}")
            return None        

    def update_source(self, source_id, source_name, source_type, publisher, location, 
                    established_date, discontinued_date, image_path, aliases,
                    political_affiliations, summary, source_code):  # Added source_code
        """Update an existing source in the Sources table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE Sources 
                SET SourceName = ?, 
                    SourceType = ?,
                    Publisher = ?,
                    Location = ?,
                    EstablishedDate = ?,
                    DiscontinuedDate = ?,
                    ImagePath = ?,
                    Aliases = ?,
                    PoliticalAffiliations = ?,
                    Summary = ?,
                    SourceCode = ?
                WHERE SourceID = ?
            ''', (source_name, source_type, publisher, location, 
                established_date, discontinued_date, image_path, aliases,
                political_affiliations, summary, source_code, source_id))
            self.conn.commit()
            print("Source updated successfully.")
        except sqlite3.Error as e:
            print(f"Error updating source: {e}")

    def update_source_status(self, source_id, status):
        """Update the review status of a source."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE Sources 
                SET ReviewStatus = ?
                WHERE SourceID = ?
            """, (status, source_id))
            self.conn.commit()
            print(f"Source {source_id} status updated to {status}")
            return True
        except sqlite3.Error as e:
            print(f"Error updating source status: {e}")
            return False

    def get_all_events(self):
        """Fetch all events from the Events table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT EventID, EventDate, PublicationDate, EventTitle, QualityScore 
                FROM Events
                ORDER BY PublicationDate DESC
            """)
            return cursor.fetchall()
        except Error as e:
            print(f"Error fetching events: {e}")
            return []

    def insert_character(self, display_name, first_name=None, last_name=None, aliases=None, gender=None,
                         birth_date=None, death_date=None, height=None, weight=None, eyes=None, hair=None,
                         occupation=None, affiliations=None, associations=None, personality_traits=None,
                         background_summary=None, family=None, find_a_grave=None):
        """Insert a new character into the Characters table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO Characters (DisplayName, FirstName, LastName, Aliases, Gender, BirthDate,
                                                  DeathDate, Height, Weight, Eyes, Hair, Occupation, Affiliations, 
                                                  Associations, PersonalityTraits, BackgroundSummary, Family, FindAGrave)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (display_name, first_name, last_name, aliases, gender, birth_date, death_date, height, weight, eyes, hair,
                  occupation, affiliations, associations, personality_traits, background_summary, family, find_a_grave))
            self.conn.commit()
            cursor.execute("SELECT CharacterID FROM Characters WHERE DisplayName = ?", (display_name,))
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting character: {e}")
            return None

    def insert_location(self, location_name, aliases=None, address=None, location_type=None, 
                        year_built=None, owners=None, managers=None, employees=None, summary=None):
        cursor = self.conn.cursor()
        
        # Check if location already exists by name or alias
        cursor.execute("SELECT LocationID FROM Locations WHERE location_name = ? OR ? IN (aliases)", 
                    (location_name, location_name))
        result = cursor.fetchone()

        if result:
            # If location already exists, return its ID
            return result[0]

        # Insert new location with review status if it doesn't exist
        cursor.execute("""
            INSERT INTO Locations (location_name, aliases, address, location_type, year_built, owners, managers, employees, summary, review_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (location_name, aliases or '', address or '', location_type or '', year_built or '', 
            owners or '', managers or '', employees or '', summary or '', 'Needs Review'))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def insert_or_get_location(self, location_name):
        """Insert a basic location record or get existing ID."""
        try:
            # Check if location exists
            self.cursor.execute("SELECT LocationID FROM Locations WHERE DisplayName = ? OR LocationName = ?", 
                            (location_name, location_name))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, insert new location with minimal info
            self.cursor.execute("""
                INSERT INTO Locations (DisplayName, LocationName, ReviewStatus)
                VALUES (?, ?, 'needs_review')
            """, (location_name, location_name))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting location: {e}")
            return None    

    def insert_entity(self, entity_name):
        """Insert a basic entity record or get existing ID."""
        try:
            # First check if entity exists
            self.cursor.execute("SELECT EntityID FROM Entities WHERE DisplayName = ? OR Name = ?", 
                            (entity_name, entity_name))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, insert new entity with minimal info
            self.cursor.execute("""
                INSERT INTO Entities (DisplayName, Name, ReviewStatus)
                VALUES (?, ?, 'needs_review')
            """, (entity_name, entity_name))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting entity: {e}")
            return None
        
    def insert_or_get_entity(self, entity_name):
        """Insert a basic entity record or get existing ID."""
        try:
            # Check if entity exists
            self.cursor.execute("SELECT EntityID FROM Entities WHERE DisplayName = ? OR Name = ?", 
                            (entity_name, entity_name))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            
            # If not found, insert new entity with minimal info
            self.cursor.execute("""
                INSERT INTO Entities (DisplayName, Name, ReviewStatus)
                VALUES (?, ?, 'needs_review')
            """, (entity_name, entity_name))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting entity: {e}")
            return None        

    def clear_event_associations(self, event_id):
        """Clear all associations for an event."""
        try:
            self.cursor.execute("DELETE FROM EventCharacters WHERE EventID = ?", (event_id,))
            self.cursor.execute("DELETE FROM EventLocations WHERE EventID = ?", (event_id,))
            self.cursor.execute("DELETE FROM EventEntities WHERE EventID = ?", (event_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error clearing event associations: {e}")

    def insert_source(self, source_name, source_type, publisher, location, 
                    established_date, discontinued_date, image_path, aliases, 
                    review_status, source_code, political_affiliations, summary):
        """Insert a new source into the Sources table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO Sources (
                    SourceName, SourceType, Publisher, Location, 
                    EstablishedDate, DiscontinuedDate, ImagePath, SourceCode, 
                    Aliases, ReviewStatus, PoliticalAffiliations, Summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (source_name, source_type, publisher, location, 
                established_date, discontinued_date, image_path, source_code, 
                aliases, review_status, political_affiliations, summary))
            self.conn.commit()
            print("Source inserted successfully.")
        except sqlite3.Error as e:
            print(f"Error inserting source: {e}")


    def get_all_sources(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT SourceID, SourceName, SourceType, Aliases, Publisher, Location, 
                    EstablishedDate, DiscontinuedDate, ImagePath, ReviewStatus 
                FROM Sources
            """)
            rows = cursor.fetchall()
            
            sources = []
            for row in rows:
                sources.append({
                    "SourceID": row[0],
                    "SourceName": row[1],
                    "SourceType": row[2],
                    "Aliases": row[3],
                    "Publisher": row[4],
                    "Location": row[5],
                    "EstablishedDate": row[6],
                    "DiscontinuedDate": row[7],
                    "ImagePath": row[8],
                    "ReviewStatus": row[9]
                })
            return sources
        except sqlite3.Error as e:
            print(f"Error fetching sources: {e}")
            return []

    def get_source_by_name(self, source_name):
        """Fetch a source from the Sources table by SourceName."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM Sources WHERE SourceName = ?", (source_name,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Error fetching source by name: {e}")
            return None

    def insert_or_get_character(self, character_name):
        try:
            # Check for character by DisplayName first
            self.cursor.execute("SELECT CharacterID, Reviewed FROM Characters WHERE DisplayName = ?", (character_name,))
            result = self.cursor.fetchone()

            # If not found, check by Aliases
            if not result:
                self.cursor.execute("SELECT CharacterID, Reviewed FROM Characters WHERE Aliases LIKE ?", ('%' + character_name + '%',))
                result = self.cursor.fetchone()

            # If found, return the existing CharacterID
            if result:
                return result[0]  # Existing entry, no review status change

            # If still not found, insert a new character with Reviewed set to 0
            self.cursor.execute("INSERT INTO Characters (DisplayName, Reviewed) VALUES (?, 0)", (character_name,))
            self.conn.commit()
            return self.cursor.lastrowid  # New entry, flagged for review

        except sqlite3.Error as e:
            print(f"Error inserting or getting character: {e}")
            return None



    def get_character_id_by_name(self, character_name):
        """Get character ID by name, checking both DisplayName and Aliases."""
        try:
            # First check DisplayName
            self.cursor.execute("SELECT CharacterID FROM Characters WHERE DisplayName = ?", (character_name,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
                
            # Then check Aliases if no exact match found
            self.cursor.execute("SELECT CharacterID FROM Characters WHERE Aliases LIKE ?", 
                            (f"%{character_name}%",))
            result = self.cursor.fetchone()
            if result:
                return result[0]
                
            return None
        except sqlite3.Error as e:
            print(f"Error getting character ID: {e}")
            return None

    def update_character_associations(self, location_id, owners, managers, employees):
        """Update character associations in the database"""
        try:
            # Get location name for associations
            location_data = self.db_manager.get_location_by_id(location_id)
            location_name = location_data['DisplayName']
            
            # Helper function to process association updates
            def update_associations(characters_str, role):
                if characters_str:
                    character_list = [name.strip() for name in characters_str.split(';')]
                    for character_name in character_list:
                        character_id = self.db_manager.get_character_id_by_name(character_name)
                        if character_id:
                            print(f"Adding {role} association: {character_name} (ID: {character_id}) -> Location {location_id}")
                            self.db_manager.add_location_occupation(
                                location_id=location_id,
                                character_id=character_id,
                                role_type=role
                            )
                            association = f"'{location_name}': ({role})"
                            self.db_manager.update_character_associations(character_id, association)
                        else:
                            print(f"Warning: Character not found: {character_name}")
            
            # Update associations for each role
            update_associations(owners, "Owner")
            update_associations(managers, "Manager")
            update_associations(employees, "Employee")
                
        except Exception as e:
            print(f"Error updating character associations: {str(e)}")

    def get_entity_id_by_name(self, entity_name):
        """Get entity ID by name, checking both DisplayName and Name fields."""
        try:
            self.cursor.execute("""
                SELECT EntityID FROM Entities 
                WHERE DisplayName = ? OR Name = ? OR Aliases LIKE ?
            """, (entity_name, entity_name, f"%{entity_name}%"))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Error getting entity ID: {e}")
            return None            

    def get_article_content_by_title(self, title):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT EventText FROM Events WHERE EventTitle = ?", (title,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"Error fetching article content: {e}")
            return None

    def link_event_character(self, event_id, character_id):
        """Link an event with a character."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO EventCharacters (EventID, CharacterID) VALUES (?, ?)", (event_id, character_id))
            self.conn.commit()
        except Error as e:
            print(f"Error linking event and character: {e}")

    def link_event_location(self, event_id, location_id):
        """Link an event with a location."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO EventLocations (EventID, LocationID) VALUES (?, ?)", (event_id, location_id))
            self.conn.commit()
        except Error as e:
            print(f"Error linking event and location: {e}")

    def link_event_entity(self, event_id, entity_id):
        """Link an event with an entity."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO EventEntities (EventID, EntityID) VALUES (?, ?)", (event_id, entity_id))
            self.conn.commit()
        except Error as e:
            print(f"Error linking event and entity: {e}")

    def update_event_file_info(self, event_id, file_name, file_path):
        try:
            self.cursor.execute("""
                UPDATE Events 
                SET Filename = ?, FilePath = ? 
                WHERE EventID = ?
            """, (file_name, file_path, event_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating event file info: {e}")

    def update_event(self, event_id, event_date, publication_date, title, text_content, source_type, source_name, quality_score=None):
        """Update an existing event in the database."""
        try:
            self.cursor.execute("""
                UPDATE Events 
                SET EventDate = ?, PublicationDate = ?, EventTitle = ?, EventText = ?, 
                    SourceType = ?, SourceName = ?, QualityScore = ?
                WHERE EventID = ?
            """, (event_date, publication_date, title, text_content, source_type, source_name, quality_score, event_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating event: {e}")


    def get_articles_by_character(self, character_id):
        """Fetch articles associated with a specific character."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                FROM Events e
                JOIN EventCharacters ec ON e.EventID = ec.EventID
                WHERE ec.CharacterID = ? AND e.Status = 'active'
                ORDER BY e.PublicationDate DESC
            """, (character_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching articles by character: {e}")
            return []


    def get_event_associations(self, event_id):
        """Fetch the associations of an event from junction tables."""
        try:
            cursor = self.conn.cursor()

            # Fetch associated characters
            cursor.execute("""
                SELECT Characters.DisplayName
                FROM Characters
                JOIN EventCharacters ON Characters.CharacterID = EventCharacters.CharacterID
                WHERE EventCharacters.EventID = ?
            """, (event_id,))
            characters = [row[0] for row in cursor.fetchall()]

            # Fetch associated locations
            cursor.execute("""
                SELECT Locations.LocationName
                FROM Locations
                JOIN EventLocations ON Locations.LocationID = EventLocations.LocationID
                WHERE EventLocations.EventID = ?
            """, (event_id,))
            locations = [row[0] for row in cursor.fetchall()]

            # Fetch associated entities
            cursor.execute("""
                SELECT Entities.Name
                FROM Entities
                JOIN EventEntities ON Entities.EntityID = EventEntities.EntityID
                WHERE EventEntities.EventID = ?
            """, (event_id,))
            entities = [row[0] for row in cursor.fetchall()]

            return {"characters": characters, "locations": locations, "entities": entities}

        except Error as e:
            print(f"Error fetching event associations: {e}")
            return {"characters": [], "locations": [], "entities": []}
        
    def get_event_by_id(self, event_id):
        """Retrieve event details by EventID."""
        self.cursor.execute("""
            SELECT EventDate, PublicationDate, EventTitle, EventText, SourceType, SourceName, QualityScore
            FROM Events 
            WHERE EventID = ?
        """, (event_id,))
        return self.cursor.fetchone()

    def remove_event_associations(self, event_id):
        """Remove all associations (Characters, Locations, Entities) for a given event."""
        self.cursor.execute("DELETE FROM EventCharacters WHERE EventID = ?", (event_id,))
        self.cursor.execute("DELETE FROM EventLocations WHERE EventID = ?", (event_id,))
        self.cursor.execute("DELETE FROM EventEntities WHERE EventID = ?", (event_id,))


    def get_table_data(self, table_name):
        """Fetch all data from the specified table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            column_names = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(column_names, row)) for row in rows]
        except Error as e:
            print(f"Error fetching data from {table_name}: {e}")
            return []
        
    def get_source_by_abbreviation(self, abbreviation):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM Sources WHERE Abbreviation = ?", (abbreviation,))
            row = cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))
            return None
        except sqlite3.Error as e:
            print(f"Error fetching source by abbreviation: {e}")
            return None        

    def get_source_type_full(self, source_code):
        cursor = self.conn.cursor()
        cursor.execute("SELECT SourceType FROM Sources WHERE SourceCode = ?", (source_code,))
        result = cursor.fetchone()
        return result[0] if result else source_code
    
    def get_source_by_code(self, source_code):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Sources WHERE SourceCode = ?", (source_code,))
        return cursor.fetchone()

    def delete_row(self, table_name, row_id):
        """Delete a row from the specified table by its primary key."""
        try:
            cursor = self.conn.cursor()
            primary_key_column = self.get_primary_key_column(table_name)
            cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key_column} = ?", (row_id,))
            self.conn.commit()
        except Error as e:
            print(f"Error deleting row from {table_name}: {e}")

    def get_primary_key_column(self, table_name):
        """Get the primary key column name for the specified table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            for row in cursor.fetchall():
                if row[5] == 1:  # The 5th element is the primary key flag
                    return row[1]  # The 1st element is the column name
            return None
        except Error as e:
            print(f"Error fetching primary key for {table_name}: {e}")
            return None

    def update_location(self, location_id, display_name, location_name, aliases, address, 
                    location_type, year_built, owners, managers, employees, summary, image_path):
        """Update an existing location."""
        try:
            self.cursor.execute("""
                UPDATE Locations SET 
                    DisplayName = ?,
                    LocationName = ?,
                    Aliases = ?,
                    Address = ?,
                    LocationType = ?,
                    YearBuilt = ?,
                    Owners = ?,
                    Managers = ?,
                    Employees = ?,
                    Summary = ?,
                    ImagePath = ?
                WHERE LocationID = ?
            """, (display_name, location_name, aliases, address, location_type, year_built,
                owners, managers, employees, summary, image_path, location_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating location: {e}")
            return False

    def update_locations_table_structure(self):
        """Update the Locations table structure while preserving existing data."""
        try:
            # Check if table exists
            self.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='Locations'
            """)
            table_exists = self.cursor.fetchone() is not None

            if not table_exists:
                # If table doesn't exist, create it with all columns
                self.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Locations (
                        LocationID INTEGER PRIMARY KEY AUTOINCREMENT,
                        DisplayName TEXT UNIQUE,
                        LocationName TEXT,
                        Aliases TEXT,
                        Address TEXT,
                        LocationType TEXT,
                        YearBuilt TEXT,
                        Description TEXT,
                        Owners TEXT,
                        Managers TEXT,
                        Employees TEXT,
                        Summary TEXT,
                        ImagePath TEXT,
                        ReviewStatus TEXT DEFAULT 'reviewed'
                    )
                """)
                print("Locations table created successfully")
            else:
                # Check for missing columns and add them if necessary
                self.cursor.execute("PRAGMA table_info(Locations)")
                existing_columns = [column[1] for column in self.cursor.fetchall()]
                
                # Define all expected columns with their types
                expected_columns = {
                    'LocationID': 'INTEGER PRIMARY KEY AUTOINCREMENT',
                    'DisplayName': 'TEXT UNIQUE',
                    'LocationName': 'TEXT',
                    'Aliases': 'TEXT',
                    'Address': 'TEXT',
                    'LocationType': 'TEXT',
                    'YearBuilt': 'TEXT',
                    'Description': 'TEXT',
                    'Owners': 'TEXT',
                    'Managers': 'TEXT',
                    'Employees': 'TEXT',
                    'Summary': 'TEXT',
                    'ImagePath': 'TEXT',
                    'ReviewStatus': 'TEXT DEFAULT "reviewed"'
                }
                
                # Add any missing columns
                for col_name, col_type in expected_columns.items():
                    if col_name not in existing_columns and col_name != 'LocationID':
                        try:
                            self.cursor.execute(f"ALTER TABLE Locations ADD COLUMN {col_name} {col_type}")
                            print(f"Added column {col_name} to Locations table")
                        except sqlite3.Error as e:
                            print(f"Error adding column {col_name}: {e}")

            self.conn.commit()
            print("Locations table structure updated successfully")
            
        except sqlite3.Error as e:
            print(f"Error updating Locations table structure: {e}")

    def update_location_status(self, location_id, status):
        """Update the review status of a location."""
        try:
            self.cursor.execute("""
                UPDATE Locations 
                SET ReviewStatus = ?
                WHERE LocationID = ?
            """, (status, location_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating location status: {e}")
            return False

    def get_all_locations(self):
        """Fetch all locations from the Locations table."""
        try:
            self.cursor.execute("SELECT * FROM Locations ORDER BY DisplayName")
            columns = [description[0] for description in self.cursor.description]
            locations = []
            for row in self.cursor.fetchall():
                locations.append(dict(zip(columns, row)))
            return locations
        except sqlite3.Error as e:
            print(f"Error fetching locations: {e}")
            return []

    def get_location_by_id(self, location_id):
        """Fetch a location by its ID."""
        try:
            self.cursor.execute("SELECT * FROM Locations WHERE LocationID = ?", (location_id,))
            row = self.cursor.fetchone()
            if row:
                columns = [description[0] for description in self.cursor.description]
                return dict(zip(columns, row))
            return None
        except sqlite3.Error as e:
            print(f"Error fetching location: {e}")
            return None


    def insert_location(self, display_name, location_name, aliases, address, location_type, 
                    year_built, owners, managers, employees, summary, image_path=None):
        """Insert a new location."""
        try:
            self.cursor.execute("""
                INSERT INTO Locations (
                    DisplayName, LocationName, Aliases, Address, 
                    LocationType, YearBuilt, Owners, Managers, 
                    Employees, Summary, ImagePath, ReviewStatus
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reviewed')
            """, (display_name, location_name, aliases, address, location_type, 
                year_built, owners, managers, employees, summary, image_path))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting location: {e}")
            return None

    def delete_location(self, location_id):
        """Delete a location and its associations."""
        try:
            # Delete from EventLocations junction table first
            self.cursor.execute("DELETE FROM EventLocations WHERE LocationID = ?", (location_id,))
            # Delete the location
            self.cursor.execute("DELETE FROM Locations WHERE LocationID = ?", (location_id,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting location: {e}")
            return False

    def update_location_image(self, location_id, image_path):
        """Update the image path for a location."""
        try:
            self.cursor.execute("""
                UPDATE Locations 
                SET ImagePath = ? 
                WHERE LocationID = ?
            """, (image_path, location_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating location image: {e}")
            return False

    def get_articles_by_location(self, location_id):
        """Fetch articles associated with a specific location."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                FROM Events e
                JOIN EventLocations ec ON e.EventID = ec.EventID
                WHERE ec.LocationID = ? AND e.Status = 'active'
                ORDER BY e.PublicationDate DESC
            """, (location_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching articles by location: {e}")
            return []

    def get_articles_by_location_and_date(self, location_id, start_date, end_date):
        """Fetch articles associated with a location within a date range."""
        try:
            self.cursor.execute("""
                SELECT e.EventDate, e.EventTitle, e.EventID
                FROM Events e
                JOIN EventLocations el ON e.EventID = el.EventID
                WHERE el.LocationID = ? 
                AND e.EventDate BETWEEN ? AND ?
                ORDER BY e.EventDate DESC
            """, (location_id, start_date, end_date))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching articles by location and date: {e}")
            return []

    # Add these methods to database_manager.py

    def add_location_occupation(self, location_id, character_id, role_type, 
                            start_date=None, end_date=None, notes=None):
        """Add or update a location occupation record with optional dates."""
        try:
            self.cursor.execute("""
                INSERT INTO LocationOccupations 
                (LocationID, CharacterID, RoleType, StartDate, EndDate, Notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (location_id, character_id, role_type, start_date, end_date, notes))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error adding location occupation: {e}")
            return False

    def update_location_occupation_dates(self, location_id, character_id, role_type, start_date, end_date):
        """Update dates for a location occupation."""
        try:
            self.cursor.execute("""
                UPDATE LocationOccupations 
                SET StartDate = ?, EndDate = ?
                WHERE LocationID = ? AND CharacterID = ? AND RoleType = ?
            """, (start_date, end_date, location_id, character_id, role_type))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating occupation dates: {e}")
            return False

    def get_location_id_by_name(self, location_name):
        """Get location ID by display name."""
        try:
            self.cursor.execute("SELECT LocationID FROM Locations WHERE DisplayName = ?", 
                            (location_name,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Error getting location ID: {e}")
            return None        

    def get_character_occupations(self, character_id):
        """Get all location occupations for a character with dates."""
        try:
            self.cursor.execute("""
                SELECT l.DisplayName as location_name, lo.RoleType, 
                    lo.StartDate, lo.EndDate
                FROM LocationOccupations lo
                JOIN Locations l ON lo.LocationID = l.LocationID
                WHERE lo.CharacterID = ?
                ORDER BY lo.StartDate
            """, (character_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching character occupations: {e}")
            return []

    def get_location_occupants(self, location_id):
        """Get all characters associated with a location with dates."""
        try:
            self.cursor.execute("""
                SELECT c.DisplayName as character_name, lo.RoleType,
                    lo.StartDate, lo.EndDate
                FROM LocationOccupations lo
                JOIN Characters c ON lo.CharacterID = c.CharacterID
                WHERE lo.LocationID = ?
                ORDER BY lo.RoleType, lo.StartDate
            """, (location_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching location occupants: {e}")
            return []

    def get_all_entities(self):
        """Fetch all entities from the Entities table."""
        try:
            self.cursor.execute("SELECT * FROM Entities ORDER BY DisplayName")
            columns = [description[0] for description in self.cursor.description]
            entities = []
            for row in self.cursor.fetchall():
                entities.append(dict(zip(columns, row)))
            return entities
        except sqlite3.Error as e:
            print(f"Error fetching entities: {e}")
            return []

    def get_entity_by_id(self, entity_id):
        """Fetch a single entity by ID."""
        try:
            self.cursor.execute("SELECT * FROM Entities WHERE EntityID = ?", (entity_id,))
            row = self.cursor.fetchone()
            if row:
                columns = [description[0] for description in self.cursor.description]
                return dict(zip(columns, row))
            return None
        except sqlite3.Error as e:
            print(f"Error fetching entity: {e}")
            return None

    def insert_entity(self, display_name, name, aliases, type_, description, 
                    established_date, affiliation, summary, image_path=None):
        """Insert a new entity."""
        try:
            self.cursor.execute("""
                INSERT INTO Entities (
                    DisplayName, Name, Aliases, Type, Description,
                    EstablishedDate, Affiliation, Summary, ImagePath
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (display_name, name, aliases, type_, description,
                established_date, affiliation, summary, image_path))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting entity: {e}")
            return None

    def update_known_members(self, entity_id):
        """Update KnownMembers field based on Character Affiliations."""
        try:
            # Get entity name
            self.cursor.execute("SELECT DisplayName FROM Entities WHERE EntityID = ?", (entity_id,))
            entity_name = self.cursor.fetchone()[0]
            
            # Find all characters with this entity in their Affiliations
            self.cursor.execute("""
                SELECT DisplayName FROM Characters 
                WHERE Affiliations LIKE ?
            """, (f"%{entity_name}%",))
            
            members = [row[0] for row in self.cursor.fetchall()]
            
            # Update the KnownMembers field
            self.cursor.execute("""
                UPDATE Entities 
                SET KnownMembers = ? 
                WHERE EntityID = ?
            """, ('; '.join(members), entity_id))
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating known members: {e}")
            return False

    def update_entity(self, entity_id, entity_data):
        """Update an existing entity."""
        try:
            self.cursor.execute("""
                UPDATE Entities SET
                    DisplayName = ?, Name = ?, Aliases = ?, Type = ?, Description = ?,
                    EstablishedDate = ?, Affiliation = ?, Summary = ?, ImagePath = ?
                WHERE EntityID = ?
            """, (entity_data['DisplayName'], entity_data['Name'], entity_data['Aliases'],
                entity_data['Type'], entity_data['Description'], entity_data['EstablishedDate'],
                entity_data['Affiliation'], entity_data['Summary'],
                entity_data.get('ImagePath'), entity_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating entity: {e}")
            return False
        
    def update_entity_status(self, entity_id, status):
        """Update the review status of an entity."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE Entities 
                SET ReviewStatus = ?
                WHERE EntityID = ?
            """, (status, entity_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating entity status: {e}")
            return False        
        
    def update_character_affiliations(self, character_id, affiliations):
        """Update character's affiliations and update related entities' KnownMembers."""
        try:
            # Update character's affiliations
            self.cursor.execute("""
                UPDATE Characters 
                SET Affiliations = ? 
                WHERE CharacterID = ?
            """, (affiliations, character_id))
            
            # Get all entities to check for updates
            self.cursor.execute("SELECT EntityID FROM Entities")
            entity_ids = [row[0] for row in self.cursor.fetchall()]
            
            # Update KnownMembers for each entity
            for entity_id in entity_ids:
                self.update_known_members(entity_id)
                
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating character affiliations: {e}")
            return False        

    def delete_entity(self, entity_id):
        """Delete an entity and its associations."""
        try:
            # First delete from junction table
            self.cursor.execute("DELETE FROM EventEntities WHERE EntityID = ?", (entity_id,))
            # Then delete the entity
            self.cursor.execute("DELETE FROM Entities WHERE EntityID = ?", (entity_id,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting entity: {e}")
            return False

    def update_entity_image(self, entity_id, image_path):
        """Update the image path for an entity."""
        try:
            self.cursor.execute("""
                UPDATE Entities 
                SET ImagePath = ? 
                WHERE EntityID = ?
            """, (image_path, entity_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating entity image: {e}")
            return False

    def get_articles_by_entity(self, entity_id):
        """Fetch articles associated with a specific entity."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                FROM Events e
                JOIN EventEntities ec ON e.EventID = ec.EventID
                WHERE ec.EntityID = ? AND e.Status = 'active'
                ORDER BY e.PublicationDate DESC
            """, (entity_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching articles by character: {e}")
            return []

    def get_articles_by_entity_and_date(self, entity_id, start_date, end_date):
        """Get articles associated with an entity within a date range."""
        try:
            self.cursor.execute("""
                SELECT e.EventDate, e.EventTitle, e.EventID
                FROM Events e
                JOIN EventEntities ee ON e.EventID = ee.EventID
                WHERE ee.EntityID = ? 
                AND e.EventDate BETWEEN ? AND ?
                ORDER BY e.EventDate DESC
            """, (entity_id, start_date, end_date))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching articles by entity and date: {e}")
            return []

    def get_event_content(self, event_id):
        """Get the content of a specific event."""
        try:
            self.cursor.execute("""
                SELECT EventTitle, EventDate, EventText
                FROM Events
                WHERE EventID = ?
            """, (event_id,))
            result = self.cursor.fetchone()
            if result:
                return f"Title: {result[0]}\nDate: {result[1]}\n\n{result[2]}"
            return None
        except sqlite3.Error as e:
            print(f"Error fetching event content: {e}")
            return None

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

            
