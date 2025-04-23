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
        try:
            cursor = self.conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS Sources (
                SourceID INTEGER PRIMARY KEY AUTOINCREMENT,
                SourceName TEXT NOT NULL,
                SourceType TEXT,
                Publisher TEXT,
                Location TEXT,
                EstablishedDate TEXT,
                DiscontinuedDate TEXT,
                ImagePath TEXT,
                ReviewStatus TEXT DEFAULT 'needs_review'
            )''')
            self.conn.commit()
            print("Sources Table created successfully.")
        except Error as e:
            print(f"Error creating Sources table: {e}")

    def insert_source(self, source_name, source_type, publisher, location, 
                      established_date, discontinued_date, image_path=None, aliases=None, review_status='needs_review'):
        try:
            cursor = self.conn.cursor()
            # Join aliases into a single semicolon-separated string
            aliases_str = '; '.join(aliases.splitlines()) if aliases else None
            cursor.execute('''
                INSERT INTO Sources (SourceName, SourceType, Publisher, Location, 
                                     EstablishedDate, DiscontinuedDate, ImagePath, Aliases, ReviewStatus)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (source_name, source_type, publisher, location, 
                  established_date, discontinued_date, image_path, aliases_str, review_status))
            self.conn.commit()
            print("Source inserted successfully.")
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting source: {e}")
            return None

    def get_all_sources(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM Sources")
            rows = cursor.fetchall()
            
            sources = []
            for row in rows:
                sources.append({
                    "SourceID": row[0],
                    "SourceName": row[1],
                    "SourceType": row[2],
                    "Aliases": row[3].split('; ') if row[3] else [],  # Convert to list
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
            row = cursor.fetchone()
            if row:
                return {
                    "SourceID": row[0],
                    "SourceName": row[1],
                    "SourceType": row[2],
                    "Aliases": row[3].split('; ') if row[3] else [],  # Convert to list
                    "Publisher": row[4],
                    "Location": row[5],
                    "EstablishedDate": row[6],
                    "DiscontinuedDate": row[7],
                    "ImagePath": row[8],
                    "ReviewStatus": row[9]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching source by name: {e}")
            return None

    def update_source(self, source_id, source_name, source_type, publisher, location, 
                    established_date, discontinued_date, image_path, aliases=None,
                    political_affiliations=None, summary=None):
        try:
            cursor = self.conn.cursor()
            # Join aliases into a single semicolon-separated string
            aliases_str = '; '.join(aliases.splitlines()) if aliases else None
            cursor.execute('''
                UPDATE Sources 
                SET SourceName=?, SourceType=?, Publisher=?, Location=?, 
                    EstablishedDate=?, DiscontinuedDate=?, ImagePath=?, Aliases=?,
                    PoliticalAffiliations=?, Summary=?
                WHERE SourceID=?
            ''', (source_name, source_type, publisher, location, 
                established_date, discontinued_date, image_path, aliases_str,
                political_affiliations, summary, source_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating source: {e}")
            return False

    def update_source_status(self, source_id, status):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE Sources 
                SET ReviewStatus = ?
                WHERE SourceID = ?
            ''', (status, source_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating source status: {e}")
            return False

    def get_events_by_source(self, source_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT EventID, EventDate, EventTitle 
                FROM Events 
                WHERE SourceID = ?
                ORDER BY EventDate DESC
            """, (source_id,))
            events = cursor.fetchall()
            return [{"EventID": row[0], "EventDate": row[1], "EventTitle": row[2]} for row in events]
        except sqlite3.Error as e:
            print(f"Error fetching events for source: {e}")
            return []

    def get_events_by_source_and_date(self, source_id, start_date, end_date):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT EventID, EventDate, EventTitle 
                FROM Events 
                WHERE SourceID = ? 
                AND EventDate BETWEEN ? AND ?
                ORDER BY EventDate DESC
            """, (source_id, start_date, end_date))
            events = cursor.fetchall()
            return [{"EventID": row[0], "EventDate": row[1], "EventTitle": row[2]} for row in events]
        except sqlite3.Error as e:
            print(f"Error fetching events by date range: {e}")
            return []

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
                    "Aliases": row[3].split('; ') if row[3] else [],  # Convert to list
                    "Publisher": row[4],
                    "Location": row[5],
                    "EstablishedDate": row[6],
                    "DiscontinuedDate": row[7],
                    "ImagePath": row[8],
                    "ReviewStatus": row[9],
                    "PoliticalAffiliations": row[10],
                    "Summary": row[11]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching source by ID: {e}")
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

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")
