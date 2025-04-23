# File: transient_manager.py

import sqlite3
import os
from database_manager import DatabaseManager

class TransientManager:
    def __init__(self, db_path):
        print("Initializing TransientManager...")  # Debug print
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        print("About to setup transient tables...")  # Debug print
        self.setup_transient_tables()
        print("Transient tables setup complete")  # Debug print

    def setup_transient_tables(self):
        """Create minimal set of transient tables"""
        print("Starting setup_transient_tables...")  # Debug print
        try:
            # Create TransientEvents table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS TransientEvents (
                    EventID INTEGER PRIMARY KEY,
                    EventDate TEXT,
                    PublicationDate TEXT,
                    EventTitle TEXT,
                    EventText TEXT,
                    SourceType TEXT,
                    SourceName TEXT,
                    Filename TEXT,
                    FilePath TEXT,
                    SourceID INTEGER,
                    QualityScore INTEGER,
                    FOREIGN KEY (SourceID) REFERENCES Sources(SourceID)
                )
            """)
            print("Created TransientEvents table")

            # Create TransientEventMetadata table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS TransientEventMetadata (
                    EventID INTEGER,
                    MetadataKey TEXT,
                    MetadataValue TEXT,
                    PRIMARY KEY (EventID, MetadataKey)
                )
            """)
            print("Created TransientEventMetadata table")

            self.conn.commit()
            print("All transient tables created and committed")

        except sqlite3.Error as e:
            print(f"Error creating transient tables: {str(e)}")
            raise

    def transfer_to_permanent(self, event_id=None):
        """
        Transfer data from transient to permanent tables.
        In the simplified system, only events and metadata are in transient tables.
        If event_id is provided, transfer only that event and related data.
        If event_id is None, transfer all transient events.
        """
        try:
            # Start a transaction
            self.cursor.execute("BEGIN TRANSACTION")

            # Build WHERE clause based on event_id
            where_clause = f"WHERE EventID = {event_id}" if event_id else ""

            # Transfer Events
            self.cursor.execute(f"""
                INSERT OR REPLACE INTO Events 
                SELECT * FROM TransientEvents 
                {where_clause}
            """)

            # Transfer metadata
            if event_id:
                self.cursor.execute("""
                    INSERT OR REPLACE INTO EventMetadata 
                    SELECT * FROM TransientEventMetadata 
                    WHERE EventID = ?
                """, (event_id,))
            else:
                self.cursor.execute("""
                    INSERT OR REPLACE INTO EventMetadata 
                    SELECT * FROM TransientEventMetadata
                """)

            # Commit the transaction
            self.conn.commit()

        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Error transferring data to permanent tables: {str(e)}")
            raise

    def get_event_by_id(self, event_id):
        """Get event by ID from transient tables."""
        if not event_id:
            return None
            
        try:
            self.cursor.execute("""
                SELECT EventID, EventDate, PublicationDate, EventTitle, EventText, 
                    SourceType, SourceName, Filename, FilePath, SourceID, QualityScore
                FROM TransientEvents
                WHERE EventID = ?
            """, (event_id,))
                
            row = self.cursor.fetchone()
            if not row:
                return None
                
            # Convert to dictionary with explicit field mapping
            event_data = {
                "event_id": row[0],
                "event_date": row[1],
                "publication_date": row[2],
                "title": row[3],
                "text_content": row[4],
                "source_type": row[5],
                "source_name": row[6],
                "filename": row[7],
                "filepath": row[8],
                "source_id": row[9],
                "quality_score": row[10]
            }
                
            # Get associated metadata
            self.cursor.execute("""
                SELECT MetadataKey, MetadataValue 
                FROM TransientEventMetadata 
                WHERE EventID = ?
            """, (event_id,))
                
            metadata = {row[0]: row[1] for row in self.cursor.fetchall()}
            event_data['metadata'] = metadata
                
            return event_data
                
        except sqlite3.Error as e:
            print(f"Error fetching event by ID: {e}")
            return None
        
    def add_event_metadata(self, event_id, metadata_dict):
        """Add or update metadata for a transient event."""
        try:
            self.cursor.execute("BEGIN TRANSACTION")
            
            for key, value in metadata_dict.items():
                self.cursor.execute("""
                    INSERT OR REPLACE INTO TransientEventMetadata (EventID, MetadataKey, MetadataValue)
                    VALUES (?, ?, ?)
                """, (event_id, key, value))
                
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Error adding event metadata: {e}")
            return False        
        
    def clear_transient_event(self, event_id):
        """Clear a specific event and its metadata from transient tables after successful transfer."""
        try:
            self.cursor.execute("BEGIN TRANSACTION")
            
            # Delete from TransientEventMetadata
            self.cursor.execute("DELETE FROM TransientEventMetadata WHERE EventID = ?", (event_id,))
            
            # Delete from TransientEvents
            self.cursor.execute("DELETE FROM TransientEvents WHERE EventID = ?", (event_id,))
            
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Error clearing transient event: {e}")
            return False        

    def clear_transient_tables(self):
        """Clear all data from transient tables"""
        try:
            tables = [
                'TransientEvents',
                'TransientEventMetadata'
            ]
                
            for table in tables:
                self.cursor.execute(f"DELETE FROM {table}")
                
            self.conn.commit()

        except sqlite3.Error as e:
            print(f"Error clearing transient tables: {str(e)}")
            raise

    def transfer_to_permanent(self, event_id=None):
        """
        Transfer event data from transient to permanent tables.
        Events and metadata are the only transient data in the simplified system.
        
        Args:
            event_id: Optional; if provided, transfer only that event, otherwise transfer all
        """
        try:
            # Start a transaction
            self.cursor.execute("BEGIN TRANSACTION")

            # If event_id provided, transfer just that event, otherwise transfer all
            if event_id:
                # Transfer single event
                self.cursor.execute("""
                    INSERT INTO Events (
                        EventDate, PublicationDate, EventTitle, EventText,
                        SourceType, SourceName, Filename, FilePath, SourceID, QualityScore
                    )
                    SELECT 
                        EventDate, PublicationDate, EventTitle, EventText,
                        SourceType, SourceName, Filename, FilePath, SourceID, QualityScore
                    FROM TransientEvents
                    WHERE EventID = ?
                """, (event_id,))
                
                # Get the new event ID from permanent table
                new_event_id = self.cursor.lastrowid
                
                # Transfer associated metadata
                self.cursor.execute("""
                    INSERT INTO EventMetadata (EventID, MetadataKey, MetadataValue)
                    SELECT ?, MetadataKey, MetadataValue
                    FROM TransientEventMetadata
                    WHERE EventID = ?
                """, (new_event_id, event_id))

                # Clear the transferred event from transient tables
                self.clear_transient_event(event_id)
                
            else:
                # Transfer all events
                self.cursor.execute("""
                    INSERT INTO Events (
                        EventDate, PublicationDate, EventTitle, EventText,
                        SourceType, SourceName, Filename, FilePath, SourceID, QualityScore
                    )
                    SELECT 
                        EventDate, PublicationDate, EventTitle, EventText,
                        SourceType, SourceName, Filename, FilePath, SourceID, QualityScore
                    FROM TransientEvents
                """)
                
                # Transfer all metadata
                self.cursor.execute("""
                    INSERT INTO EventMetadata (EventID, MetadataKey, MetadataValue)
                    SELECT EventID, MetadataKey, MetadataValue
                    FROM TransientEventMetadata
                """)
                
                # Clear all transient tables
                self.clear_transient_tables()

            # Commit the transaction
            self.conn.commit()
            return True

        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Error transferring data to permanent tables: {str(e)}")
            return False

    def handle_character_classification(self):
        """Handle the transfer of character classifications to appropriate tables"""
        try:
            # Get all characters with classifications
            self.cursor.execute("""
                SELECT CharacterID, Classification 
                FROM TransientCharacters 
                WHERE Classification IS NOT NULL
            """)
            
            characters = self.cursor.fetchall()
            
            for char_id, classification in characters:
                # Remove from all classification tables first
                tables = ['PrimaryCharacters', 'SecondaryCharacters', 
                         'TertiaryCharacters', 'QuaternaryCharacters']
                
                for table in tables:
                    self.cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE CharacterID = ?
                    """, (char_id,))
                
                # Add to appropriate classification table
                table_name = f"{classification}Characters"
                self.cursor.execute(f"""
                    INSERT OR REPLACE INTO {table_name} (CharacterID)
                    VALUES (?)
                """, (char_id,))

        except sqlite3.Error as e:
            print(f"Error handling character classification: {str(e)}")
            raise

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()