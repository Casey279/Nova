# File: table_sources.py

import sqlite3
from sqlite3 import Error

class SourcesTable:
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
        """Create the Sources table if it doesn't exist."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS Sources (
                SourceID INTEGER PRIMARY KEY AUTOINCREMENT,
                Title TEXT NOT NULL,
                Aliases TEXT,
                Author TEXT,
                SourceType TEXT,
                PublicationDate TEXT,
                Publisher TEXT,
                City TEXT,
                State TEXT,
                Country TEXT,
                URL TEXT,
                Content TEXT,
                FileName TEXT,
                ImportDate TEXT,
                ReviewStatus TEXT DEFAULT 'needs_review'
            )
            ''')
            self.conn.commit()
            print("Sources table created or verified successfully.")
        except Error as e:
            print(f"Error creating Sources table: {e}")

    def insert_source(self, title, aliases=None, author=None, source_type=None, publication_date=None,
                     publisher=None, city=None, state=None, country=None, url=None,
                     content=None, file_name=None, import_date=None, review_status='needs_review'):
        """Insert a new source into the Sources table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO Sources 
                (Title, Aliases, Author, SourceType, PublicationDate, Publisher, 
                 City, State, Country, URL, Content, FileName, ImportDate, ReviewStatus) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, aliases, author, source_type, publication_date, 
                  publisher, city, state, country, url, 
                  content, file_name, import_date, review_status))
            self.conn.commit()
            print("Source inserted successfully.")
            cursor.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting source: {e}")
            return None

    def update_source(self, source_id, title=None, aliases=None, author=None, source_type=None, 
                     publication_date=None, publisher=None, city=None, state=None, country=None, 
                     url=None, content=None, file_name=None, import_date=None, review_status=None):
        """Update a source in the Sources table."""
        try:
            cursor = self.conn.cursor()
            
            # Get current values to use if not provided
            cursor.execute('''
                SELECT Title, Aliases, Author, SourceType, PublicationDate, Publisher, 
                       City, State, Country, URL, Content, FileName, ImportDate, ReviewStatus
                FROM Sources WHERE SourceID = ?
            ''', (source_id,))
            current = cursor.fetchone()
            
            if not current:
                print(f"Source with ID {source_id} not found.")
                return False
                
            # Use provided values or current values if not provided
            title = title if title is not None else current[0]
            aliases = aliases if aliases is not None else current[1]
            author = author if author is not None else current[2]
            source_type = source_type if source_type is not None else current[3]
            publication_date = publication_date if publication_date is not None else current[4]
            publisher = publisher if publisher is not None else current[5]
            city = city if city is not None else current[6]
            state = state if state is not None else current[7]
            country = country if country is not None else current[8]
            url = url if url is not None else current[9]
            content = content if content is not None else current[10]
            file_name = file_name if file_name is not None else current[11]
            import_date = import_date if import_date is not None else current[12]
            review_status = review_status if review_status is not None else current[13]
            
            cursor.execute('''
                UPDATE Sources 
                SET Title = ?, Aliases = ?, Author = ?, SourceType = ?, PublicationDate = ?, 
                    Publisher = ?, City = ?, State = ?, Country = ?, URL = ?, 
                    Content = ?, FileName = ?, ImportDate = ?, ReviewStatus = ?
                WHERE SourceID = ?
            ''', (title, aliases, author, source_type, publication_date, 
                  publisher, city, state, country, url, 
                  content, file_name, import_date, review_status, source_id))
            self.conn.commit()
            print("Source updated successfully.")
            return True
        except Error as e:
            print(f"Error updating source: {e}")
            return False

    def delete_source(self, source_id):
        """Delete a source from the Sources table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM Sources WHERE SourceID = ?", (source_id,))
            self.conn.commit()
            print("Source deleted successfully.")
            return True
        except Error as e:
            print(f"Error deleting source: {e}")
            return False

    def get_source(self, source_id):
        """Get a source by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                       Publisher, City, State, Country, URL, Content, FileName, 
                       ImportDate, ReviewStatus
                FROM Sources 
                WHERE SourceID = ?
            ''', (source_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error getting source: {e}")
            return None

    def get_all_sources(self):
        """Get all sources."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                       Publisher, City, State, Country, URL, FileName, ImportDate, ReviewStatus
                FROM Sources
                ORDER BY Title
            ''')
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting sources: {e}")
            return []

    def search_sources(self, search_term):
        """Search for sources by title, alias, author, or content."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                       Publisher, City, State, Country, URL, FileName, ImportDate, ReviewStatus
                FROM Sources
                WHERE Title LIKE ? OR Aliases LIKE ? OR Author LIKE ? OR 
                      Content LIKE ? OR SourceType LIKE ?
                ORDER BY Title
            ''', (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", 
                  f"%{search_term}%", f"%{search_term}%"))
            return cursor.fetchall()
        except Error as e:
            print(f"Error searching sources: {e}")
            return []
            
    def get_sources_by_type(self, source_type):
        """Get sources by type."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                       Publisher, City, State, Country, URL, FileName, ImportDate, ReviewStatus
                FROM Sources
                WHERE SourceType = ?
                ORDER BY Title
            ''', (source_type,))
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting sources by type: {e}")
            return []

    def get_source_types(self):
        """Get all unique source types."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT DISTINCT SourceType
                FROM Sources
                WHERE SourceType IS NOT NULL AND SourceType != ''
                ORDER BY SourceType
            ''')
            return [row[0] for row in cursor.fetchall()]
        except Error as e:
            print(f"Error getting source types: {e}")
            return []

    def get_source_content(self, source_id):
        """Get the content of a source."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT Content FROM Sources WHERE SourceID = ?", (source_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Error as e:
            print(f"Error getting source content: {e}")
            return None

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")