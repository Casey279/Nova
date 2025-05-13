# File: repository_database.py

import os
import sqlite3
import json
from datetime import datetime
from sqlite3 import Error

class RepositoryDatabaseManager:
    """
    Manages the newspaper repository database operations.
    Handles creating tables, adding entries, updating statuses, and querying content.
    """
    
    def __init__(self, db_path):
        """
        Initialize the repository database manager.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.create_connection()
        self.create_tables()
    
    def create_connection(self):
        """Create a database connection to the SQLite database."""
        try:
            # Create directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
            self.cursor = self.conn.cursor()
            print(f"Connected to newspaper repository database at {self.db_path}")
        except Error as e:
            print(f"Error connecting to database: {e}")
    
    def create_tables(self):
        """Create necessary tables if they don't exist."""
        try:
            # Create newspaper_pages table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS newspaper_pages (
                    page_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    publication_date TEXT NOT NULL,
                    page_number INTEGER,
                    filename TEXT NOT NULL,
                    image_path TEXT,
                    ocr_status INTEGER DEFAULT 0,
                    processed_date TEXT,
                    origin TEXT NOT NULL,
                    metadata TEXT,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create article_segments table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS article_segments (
                    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id INTEGER NOT NULL,
                    headline TEXT,
                    article_text TEXT NOT NULL,
                    position_data TEXT,
                    image_clip_path TEXT,
                    imported_to_main BOOLEAN DEFAULT 0,
                    main_db_event_id INTEGER,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    modified_date TEXT,
                    FOREIGN KEY (page_id) REFERENCES newspaper_pages (page_id) ON DELETE CASCADE
                )
            """)
            
            # Create article_keywords table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS article_keywords (
                    keyword_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    segment_id INTEGER NOT NULL,
                    keyword TEXT NOT NULL,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (segment_id) REFERENCES article_segments (segment_id) ON DELETE CASCADE
                )
            """)
            
            # Create processing_queue table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    parameters TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER DEFAULT 1,
                    retries INTEGER DEFAULT 0,
                    last_error TEXT,
                    added_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT
                )
            """)
            
            # Create indexes for better performance
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_source ON newspaper_pages (source_name)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_date ON newspaper_pages (publication_date)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_segments_page ON article_segments (page_id)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_keywords_segment ON article_keywords (segment_id)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue (status)")
            
            self.conn.commit()
            print("Repository database tables created successfully")
        except Error as e:
            print(f"Error creating tables: {e}")
    
    #
    # Newspaper Pages Operations
    #
    
    def add_newspaper_page(self, source_name, publication_date, page_number, filename, 
                           image_path=None, origin="other", metadata=None):
        """
        Add a new newspaper page to the repository.
        
        Args:
            source_name (str): Name of the newspaper source
            publication_date (str): Publication date in YYYY-MM-DD format
            page_number (int): Page number
            filename (str): Filename of the page image
            image_path (str, optional): Path to the stored image
            origin (str, optional): Source of the page (chroniclingamerica, newspapers.com, other)
            metadata (dict, optional): Additional metadata for the page
            
        Returns:
            int: ID of the newly created page, or None if failed
        """
        try:
            # Convert metadata dict to JSON string if provided
            metadata_json = json.dumps(metadata) if metadata else None
            
            self.cursor.execute("""
                INSERT INTO newspaper_pages 
                (source_name, publication_date, page_number, filename, image_path, origin, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (source_name, publication_date, page_number, filename, image_path, origin, metadata_json))
            
            self.conn.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"Error adding newspaper page: {e}")
            return None
    
    def update_page_ocr_status(self, page_id, ocr_status, processed_date=None):
        """
        Update the OCR status of a newspaper page.
        
        Args:
            page_id (int): ID of the newspaper page
            ocr_status (int): OCR status code (0=pending, 1=completed, 2=error)
            processed_date (str, optional): Date when processing occurred
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            processed_date = processed_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.cursor.execute("""
                UPDATE newspaper_pages
                SET ocr_status = ?, processed_date = ?
                WHERE page_id = ?
            """, (ocr_status, processed_date, page_id))
            
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"Error updating page OCR status: {e}")
            return False

    def get_all_pages(self, limit=100, offset=0):
        """
        Get all newspaper pages with pagination.

        Args:
            limit (int): Maximum number of pages to return
            offset (int): Number of pages to skip

        Returns:
            List of page records
        """
        try:
            self.cursor.execute("""
                SELECT * FROM newspaper_pages
                ORDER BY publication_date DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            return [self._row_to_page(row) for row in self.cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error getting all pages: {e}")
            return []
        
    def _row_to_page(self, row):
        """Convert a database row to a page object."""
        from collections import namedtuple
        Page = namedtuple('Page', [
            'id', 'newspaper_name', 'publication_date', 'page_number',
            'source_id', 'source_url', 'image_path', 'ocr_text_path',
            'hocr_path', 'ocr_status', 'created_date', 'modified_date'
        ])

        return Page(
            id=row['page_id'],
            newspaper_name=row['newspaper_name'],
            publication_date=row['publication_date'],
            page_number=row['page_number'],
            source_id=row['source_id'],
            source_url=row.get('source_url', ''),
            image_path=row.get('image_path', ''),
            ocr_text_path=row.get('ocr_text_path', ''),
            hocr_path=row.get('hocr_path', ''),
            ocr_status=row['ocr_status'],
            created_date=row.get('created_date', ''),
            modified_date=row.get('modified_date', '')
        )        

    def get_newspaper_page(self, page_id):
        """
        Get newspaper page details by ID.
        
        Args:
            page_id (int): ID of the newspaper page
            
        Returns:
            dict: Page details or None if not found
        """
        try:
            self.cursor.execute("""
                SELECT page_id, source_name, publication_date, page_number, 
                       filename, image_path, ocr_status, processed_date, 
                       origin, metadata, created_date
                FROM newspaper_pages
                WHERE page_id = ?
            """, (page_id,))
            
            row = self.cursor.fetchone()
            if row:
                page = {
                    "page_id": row[0],
                    "source_name": row[1],
                    "publication_date": row[2],
                    "page_number": row[3],
                    "filename": row[4],
                    "image_path": row[5],
                    "ocr_status": row[6],
                    "processed_date": row[7],
                    "origin": row[8],
                    "metadata": json.loads(row[9]) if row[9] else None,
                    "created_date": row[10]
                }
                return page
            return None
        except Error as e:
            print(f"Error getting newspaper page: {e}")
            return None
    
    def search_newspaper_pages(self, source_name=None, publication_date=None, 
                               origin=None, ocr_status=None, limit=100, offset=0):
        """
        Search for newspaper pages with filters.
        
        Args:
            source_name (str, optional): Filter by source name
            publication_date (str, optional): Filter by publication date
            origin (str, optional): Filter by origin
            ocr_status (int, optional): Filter by OCR status
            limit (int, optional): Maximum number of results
            offset (int, optional): Pagination offset
            
        Returns:
            list: List of matching page dictionaries
        """
        try:
            query = """
                SELECT page_id, source_name, publication_date, page_number, 
                       filename, image_path, ocr_status, processed_date, 
                       origin, metadata, created_date
                FROM newspaper_pages
                WHERE 1=1
            """
            params = []
            
            if source_name:
                query += " AND source_name = ?"
                params.append(source_name)
            
            if publication_date:
                query += " AND publication_date = ?"
                params.append(publication_date)
            
            if origin:
                query += " AND origin = ?"
                params.append(origin)
            
            if ocr_status is not None:
                query += " AND ocr_status = ?"
                params.append(ocr_status)
            
            query += " ORDER BY publication_date DESC, page_number ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            self.cursor.execute(query, params)
            
            results = []
            for row in self.cursor.fetchall():
                page = {
                    "page_id": row[0],
                    "source_name": row[1],
                    "publication_date": row[2],
                    "page_number": row[3],
                    "filename": row[4],
                    "image_path": row[5],
                    "ocr_status": row[6],
                    "processed_date": row[7],
                    "origin": row[8],
                    "metadata": json.loads(row[9]) if row[9] else None,
                    "created_date": row[10]
                }
                results.append(page)
            
            return results
        except Error as e:
            print(f"Error searching newspaper pages: {e}")
            return []
    
    #
    # Article Segments Operations
    #
    
    def add_article_segment(self, page_id, article_text, headline=None, 
                            position_data=None, image_clip_path=None):
        """
        Add a new article segment to the repository.
        
        Args:
            page_id (int): ID of the parent newspaper page
            article_text (str): OCR text of the article
            headline (str, optional): Article headline
            position_data (dict, optional): JSON data with coordinates on original page
            image_clip_path (str, optional): Path to the article image clip
            
        Returns:
            int: ID of the newly created segment, or None if failed
        """
        try:
            # Convert position data dict to JSON string if provided
            position_json = json.dumps(position_data) if position_data else None
            
            self.cursor.execute("""
                INSERT INTO article_segments 
                (page_id, headline, article_text, position_data, image_clip_path)
                VALUES (?, ?, ?, ?, ?)
            """, (page_id, headline, article_text, position_json, image_clip_path))
            
            self.conn.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"Error adding article segment: {e}")
            return None
    
    def update_segment_import_status(self, segment_id, imported_to_main, main_db_event_id=None):
        """
        Update the import status of an article segment.
        
        Args:
            segment_id (int): ID of the article segment
            imported_to_main (bool): Whether imported to main database
            main_db_event_id (int, optional): ID in the main database if imported
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            modified_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.cursor.execute("""
                UPDATE article_segments
                SET imported_to_main = ?, main_db_event_id = ?, modified_date = ?
                WHERE segment_id = ?
            """, (1 if imported_to_main else 0, main_db_event_id, modified_date, segment_id))
            
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"Error updating segment import status: {e}")
            return False
    
    def get_article_segment(self, segment_id):
        """
        Get article segment details by ID.
        
        Args:
            segment_id (int): ID of the article segment
            
        Returns:
            dict: Segment details or None if not found
        """
        try:
            self.cursor.execute("""
                SELECT s.segment_id, s.page_id, s.headline, s.article_text, 
                       s.position_data, s.image_clip_path, s.imported_to_main, 
                       s.main_db_event_id, s.created_date, s.modified_date,
                       p.source_name, p.publication_date, p.page_number
                FROM article_segments s
                JOIN newspaper_pages p ON s.page_id = p.page_id
                WHERE s.segment_id = ?
            """, (segment_id,))
            
            row = self.cursor.fetchone()
            if row:
                segment = {
                    "segment_id": row[0],
                    "page_id": row[1],
                    "headline": row[2],
                    "article_text": row[3],
                    "position_data": json.loads(row[4]) if row[4] else None,
                    "image_clip_path": row[5],
                    "imported_to_main": bool(row[6]),
                    "main_db_event_id": row[7],
                    "created_date": row[8],
                    "modified_date": row[9],
                    "source_name": row[10],
                    "publication_date": row[11],
                    "page_number": row[12]
                }
                
                # Get keywords for this segment
                self.cursor.execute("""
                    SELECT keyword FROM article_keywords
                    WHERE segment_id = ?
                """, (segment_id,))
                
                segment["keywords"] = [row[0] for row in self.cursor.fetchall()]
                
                return segment
            return None
        except Error as e:
            print(f"Error getting article segment: {e}")
            return None
    
    def get_page_segments(self, page_id):
        """
        Get all article segments for a specific newspaper page.
        
        Args:
            page_id (int): ID of the newspaper page
            
        Returns:
            list: List of segment dictionaries
        """
        try:
            self.cursor.execute("""
                SELECT segment_id, headline, article_text, position_data,
                       image_clip_path, imported_to_main, main_db_event_id
                FROM article_segments
                WHERE page_id = ?
                ORDER BY segment_id
            """, (page_id,))
            
            results = []
            for row in self.cursor.fetchall():
                segment = {
                    "segment_id": row[0],
                    "headline": row[1],
                    "article_text": row[2],
                    "position_data": json.loads(row[3]) if row[3] else None,
                    "image_clip_path": row[4],
                    "imported_to_main": bool(row[5]),
                    "main_db_event_id": row[6]
                }
                
                # Get keywords for this segment
                self.cursor.execute("""
                    SELECT keyword FROM article_keywords
                    WHERE segment_id = ?
                """, (segment.get("segment_id"),))
                
                segment["keywords"] = [row[0] for row in self.cursor.fetchall()]
                
                results.append(segment)
            
            return results
        except Error as e:
            print(f"Error getting page segments: {e}")
            return []
    
    def search_article_text(self, query, limit=50, offset=0):
        """
        Search for article segments containing specific text.
        
        Args:
            query (str): Search query text
            limit (int, optional): Maximum number of results
            offset (int, optional): Pagination offset
            
        Returns:
            list: List of matching segment dictionaries
        """
        try:
            search_query = f"%{query}%"
            
            self.cursor.execute("""
                SELECT s.segment_id, s.page_id, s.headline, s.article_text,
                       p.source_name, p.publication_date, p.page_number
                FROM article_segments s
                JOIN newspaper_pages p ON s.page_id = p.page_id
                WHERE s.article_text LIKE ? OR s.headline LIKE ?
                ORDER BY p.publication_date DESC
                LIMIT ? OFFSET ?
            """, (search_query, search_query, limit, offset))
            
            results = []
            for row in self.cursor.fetchall():
                segment = {
                    "segment_id": row[0],
                    "page_id": row[1],
                    "headline": row[2],
                    "article_text": row[3],
                    "source_name": row[4],
                    "publication_date": row[5],
                    "page_number": row[6]
                }
                results.append(segment)
            
            return results
        except Error as e:
            print(f"Error searching article text: {e}")
            return []
    
    #
    # Article Keywords Operations
    #
    
    def add_article_keyword(self, segment_id, keyword):
        """
        Add a keyword to an article segment.
        
        Args:
            segment_id (int): ID of the article segment
            keyword (str): Keyword to add
            
        Returns:
            int: ID of the newly created keyword, or None if failed
        """
        try:
            # First check if this keyword already exists for this segment
            self.cursor.execute("""
                SELECT COUNT(*) FROM article_keywords
                WHERE segment_id = ? AND keyword = ?
            """, (segment_id, keyword))
            
            if self.cursor.fetchone()[0] > 0:
                # Keyword already exists for this segment
                return None
            
            self.cursor.execute("""
                INSERT INTO article_keywords (segment_id, keyword)
                VALUES (?, ?)
            """, (segment_id, keyword))
            
            self.conn.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"Error adding article keyword: {e}")
            return None
    
    def remove_article_keyword(self, segment_id, keyword):
        """
        Remove a keyword from an article segment.
        
        Args:
            segment_id (int): ID of the article segment
            keyword (str): Keyword to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.cursor.execute("""
                DELETE FROM article_keywords
                WHERE segment_id = ? AND keyword = ?
            """, (segment_id, keyword))
            
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"Error removing article keyword: {e}")
            return False
    
    def get_keywords_for_segment(self, segment_id):
        """
        Get all keywords for a specific article segment.
        
        Args:
            segment_id (int): ID of the article segment
            
        Returns:
            list: List of keywords
        """
        try:
            self.cursor.execute("""
                SELECT keyword FROM article_keywords
                WHERE segment_id = ?
                ORDER BY keyword
            """, (segment_id,))
            
            return [row[0] for row in self.cursor.fetchall()]
        except Error as e:
            print(f"Error getting keywords for segment: {e}")
            return []
    
    def search_by_keyword(self, keyword, limit=50, offset=0):
        """
        Find all article segments tagged with a specific keyword.
        
        Args:
            keyword (str): Keyword to search for
            limit (int, optional): Maximum number of results
            offset (int, optional): Pagination offset
            
        Returns:
            list: List of matching segment dictionaries
        """
        try:
            self.cursor.execute("""
                SELECT s.segment_id, s.page_id, s.headline, s.article_text,
                       p.source_name, p.publication_date, p.page_number
                FROM article_segments s
                JOIN newspaper_pages p ON s.page_id = p.page_id
                JOIN article_keywords k ON s.segment_id = k.segment_id
                WHERE k.keyword = ?
                ORDER BY p.publication_date DESC
                LIMIT ? OFFSET ?
            """, (keyword, limit, offset))
            
            results = []
            for row in self.cursor.fetchall():
                segment = {
                    "segment_id": row[0],
                    "page_id": row[1],
                    "headline": row[2],
                    "article_text": row[3],
                    "source_name": row[4],
                    "publication_date": row[5],
                    "page_number": row[6]
                }
                results.append(segment)
            
            return results
        except Error as e:
            print(f"Error searching by keyword: {e}")
            return []
    
    #
    # ChroniclingAmerica Specific Operations
    #
    
    def add_chronicling_america_page(self, lccn, publication_name, publication_date, 
                                  page_number, image_path=None, ocr_path=None, 
                                  json_metadata=None, download_status="complete", 
                                  download_date=None):
        """
        Add a newspaper page from Chronicling America to the repository.
        
        Args:
            lccn (str): Library of Congress Control Number
            publication_name (str): Name of the newspaper
            publication_date (str): Publication date in YYYY-MM-DD format
            page_number (int): Page sequence number
            image_path (str, optional): Path to the stored image
            ocr_path (str, optional): Path to the OCR text file
            json_metadata (dict, optional): Additional metadata from ChroniclingAmerica
            download_status (str, optional): Status of the download process
            download_date (str, optional): Date when the page was downloaded
            
        Returns:
            int: ID of the newly created page, or None if failed
        """
        try:
            # Generate a filename from the metadata
            filename = f"{lccn}_{publication_date.replace('-', '')}_{page_number}"
            
            # Set download date if not provided
            if not download_date:
                download_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            # Create metadata object
            metadata = {
                "lccn": lccn,
                "download_status": download_status,
                "download_date": download_date
            }
            
            # Add json_metadata if provided
            if json_metadata:
                metadata.update(json_metadata)
                
            # Add the page using the core method
            return self.add_newspaper_page(
                source_name=publication_name,
                publication_date=publication_date,
                page_number=page_number,
                filename=filename,
                image_path=image_path,
                origin="chroniclingamerica",
                metadata=metadata
            )
        except Error as e:
            print(f"Error adding ChroniclingAmerica page: {e}")
            return None
            
    def update_chronicling_america_download_status(self, page_id, status, error_message=None):
        """
        Update the download status for a ChroniclingAmerica page.
        
        Args:
            page_id (int): ID of the newspaper page
            status (str): New status ('pending', 'downloading', 'complete', 'error')
            error_message (str, optional): Error message if status is 'error'
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First get the current metadata
            self.cursor.execute("""
                SELECT metadata FROM newspaper_pages
                WHERE page_id = ?
            """, (page_id,))
            
            row = self.cursor.fetchone()
            if not row or not row[0]:
                return False
                
            metadata = json.loads(row[0])
            
            # Update the download status
            metadata["download_status"] = status
            if error_message:
                metadata["error_message"] = error_message
            metadata["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Save the updated metadata
            self.cursor.execute("""
                UPDATE newspaper_pages
                SET metadata = ?
                WHERE page_id = ?
            """, (json.dumps(metadata), page_id))
            
            self.conn.commit()
            return True
        except Error as e:
            print(f"Error updating ChroniclingAmerica download status: {e}")
            return False
            
    def get_chronicling_america_pages(self, lccn=None, publication_name=None, 
                                   date_start=None, date_end=None, 
                                   download_status=None, location=None,
                                   limit=50, offset=0):
        """
        Get newspaper pages from ChroniclingAmerica with optional filters.
        
        Args:
            lccn (str, optional): Filter by Library of Congress Control Number
            publication_name (str, optional): Filter by newspaper name
            date_start (str, optional): Filter by start date (YYYY-MM-DD)
            date_end (str, optional): Filter by end date (YYYY-MM-DD)
            download_status (str, optional): Filter by download status
            location (str, optional): Filter by publication location (state or city)
            limit (int, optional): Maximum number of results
            offset (int, optional): Pagination offset
            
        Returns:
            list: List of matching page dictionaries
        """
        try:
            query = """
                SELECT page_id, source_name, publication_date, page_number, 
                       filename, image_path, ocr_status, processed_date, 
                       origin, metadata, created_date
                FROM newspaper_pages
                WHERE origin = 'chroniclingamerica'
            """
            params = []
            
            if publication_name:
                query += " AND source_name = ?"
                params.append(publication_name)
                
            if date_start:
                query += " AND publication_date >= ?"
                params.append(date_start)
                
            if date_end:
                query += " AND publication_date <= ?"
                params.append(date_end)
                
            # For LCCN, download_status, and location we need to search in the JSON metadata
            # Using JSON functions (supported in SQLite 3.9.0+)
            if lccn:
                query += " AND JSON_EXTRACT(metadata, '$.lccn') = ?"
                params.append(lccn)
            
            if download_status:
                query += " AND JSON_EXTRACT(metadata, '$.download_status') = ?"
                params.append(download_status)
                
            if location:
                # Search in place_of_publication field
                query += " AND (JSON_EXTRACT(metadata, '$.place_of_publication') LIKE ? OR "
                query += "JSON_EXTRACT(metadata, '$.state') = ?)"
                params.append(f"%{location}%")
                params.append(location)
            
            query += " ORDER BY publication_date DESC, page_number ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            self.cursor.execute(query, params)
            
            results = []
            for row in self.cursor.fetchall():
                page = {
                    "page_id": row[0],
                    "source_name": row[1],
                    "publication_date": row[2],
                    "page_number": row[3],
                    "filename": row[4],
                    "image_path": row[5],
                    "ocr_status": row[6],
                    "processed_date": row[7],
                    "origin": row[8],
                    "metadata": json.loads(row[9]) if row[9] else None,
                    "created_date": row[10]
                }
                results.append(page)
            
            return results
        except Error as e:
            print(f"Error getting ChroniclingAmerica pages: {e}")
            return []
    
    def update_batch_download_status(self, lccn=None, publication_date=None, status="complete"):
        """
        Update the download status for multiple ChroniclingAmerica pages at once.
        Useful for tracking batch operations.
        
        Args:
            lccn (str, optional): Filter by Library of Congress Control Number
            publication_date (str, optional): Filter by publication date
            status (str): New status to set for matching pages
            
        Returns:
            int: Number of rows updated
        """
        try:
            # Get all matching pages
            if not lccn and not publication_date:
                print("Error: Must provide at least one filter (lccn or publication_date)")
                return 0
                
            query = """
                SELECT page_id, metadata FROM newspaper_pages
                WHERE origin = 'chroniclingamerica'
            """
            params = []
            
            if lccn:
                query += " AND JSON_EXTRACT(metadata, '$.lccn') = ?"
                params.append(lccn)
                
            if publication_date:
                query += " AND publication_date = ?"
                params.append(publication_date)
                
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            count = 0
            
            # Update each page's metadata
            for row in rows:
                page_id = row[0]
                metadata = json.loads(row[1]) if row[1] else {}
                
                # Update status
                metadata["download_status"] = status
                metadata["last_updated"] = update_time
                
                # Save back to database
                self.cursor.execute("""
                    UPDATE newspaper_pages
                    SET metadata = ?
                    WHERE page_id = ?
                """, (json.dumps(metadata), page_id))
                
                count += 1
                
            self.conn.commit()
            return count
        except Error as e:
            print(f"Error updating batch download status: {e}")
            return 0
            
    def get_chronicling_america_stats(self):
        """
        Get statistics about ChroniclingAmerica content in the repository.
        
        Returns:
            dict: Dictionary with various statistics
        """
        try:
            stats = {
                "total_pages": 0,
                "total_newspapers": 0,
                "total_states": 0,
                "by_status": {
                    "complete": 0,
                    "pending": 0,
                    "error": 0
                },
                "by_year": {}
            }
            
            # Get total pages
            self.cursor.execute("""
                SELECT COUNT(*) FROM newspaper_pages
                WHERE origin = 'chroniclingamerica'
            """)
            stats["total_pages"] = self.cursor.fetchone()[0]
            
            # Get total newspapers (unique source_name)
            self.cursor.execute("""
                SELECT COUNT(DISTINCT source_name) FROM newspaper_pages
                WHERE origin = 'chroniclingamerica'
            """)
            stats["total_newspapers"] = self.cursor.fetchone()[0]
            
            # Count by download status (requires iterating through records due to JSON)
            self.cursor.execute("""
                SELECT metadata FROM newspaper_pages
                WHERE origin = 'chroniclingamerica'
            """)
            
            # Process each row
            for row in self.cursor.fetchall():
                if row[0]:
                    metadata = json.loads(row[0])
                    status = metadata.get("download_status", "complete")
                    
                    # Update status counts
                    if status in stats["by_status"]:
                        stats["by_status"][status] += 1
                    else:
                        stats["by_status"][status] = 1
                    
                    # Track unique states
                    state = metadata.get("state")
                    if state:
                        if "states" not in stats:
                            stats["states"] = set()
                        stats["states"].add(state)
            
            # Convert states set to count
            if "states" in stats:
                stats["total_states"] = len(stats["states"])
                stats["states"] = list(stats["states"])
            else:
                stats["total_states"] = 0
                stats["states"] = []
                
            # Count by year
            self.cursor.execute("""
                SELECT SUBSTR(publication_date, 1, 4), COUNT(*)
                FROM newspaper_pages
                WHERE origin = 'chroniclingamerica'
                GROUP BY SUBSTR(publication_date, 1, 4)
                ORDER BY SUBSTR(publication_date, 1, 4)
            """)
            
            for row in self.cursor.fetchall():
                stats["by_year"][row[0]] = row[1]
                
            return stats
        except Error as e:
            print(f"Error getting ChroniclingAmerica stats: {e}")
            return {
                "total_pages": 0,
                "total_newspapers": 0,
                "total_states": 0,
                "by_status": {},
                "by_year": {}
            }
    
    #
    # Processing Queue Operations
    #
    
    def add_to_queue(self, file_path, priority=1):
        """
        Add a file to the processing queue.
        
        Args:
            file_path (str): Path to the file to process
            priority (int, optional): Processing priority (higher = more important)
            
        Returns:
            int: ID of the queue entry, or None if failed
        """
        try:
            added_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.cursor.execute("""
                INSERT INTO processing_queue (file_path, status, priority, added_date)
                VALUES (?, 'pending', ?, ?)
            """, (file_path, priority, added_date))
            
            self.conn.commit()
            return self.cursor.lastrowid
        except Error as e:
            print(f"Error adding to queue: {e}")
            return None
    
    def update_queue_status(self, queue_id, status, error_message=None):
        """
        Update the status of a queue entry.
        
        Args:
            queue_id (int): ID of the queue entry
            status (str): New status ('pending', 'processing', 'completed', 'error')
            error_message (str, optional): Error message if status is 'error'
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            processed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if status == 'error' and error_message:
                # For error status, update error message and increment retry count
                self.cursor.execute("""
                    UPDATE processing_queue
                    SET status = ?, processed_date = ?, error_message = ?,
                        retry_count = retry_count + 1, last_retry_date = ?
                    WHERE queue_id = ?
                """, (status, processed_date, error_message, processed_date, queue_id))
            else:
                # For other statuses, just update status and processed date
                self.cursor.execute("""
                    UPDATE processing_queue
                    SET status = ?, processed_date = ?
                    WHERE queue_id = ?
                """, (status, processed_date, queue_id))
            
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            print(f"Error updating queue status: {e}")
            return False
    
    def get_next_pending_item(self):
        """
        Get the next pending item from the processing queue.
        
        Returns:
            dict: Queue item details or None if no pending items
        """
        try:
            self.cursor.execute("""
                SELECT queue_id, file_path, priority, added_date, retry_count
                FROM processing_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, retry_count ASC, added_date ASC
                LIMIT 1
            """)
            
            row = self.cursor.fetchone()
            if row:
                item = {
                    "queue_id": row[0],
                    "file_path": row[1],
                    "priority": row[2],
                    "added_date": row[3],
                    "retry_count": row[4]
                }
                
                # Mark as processing
                self.update_queue_status(item["queue_id"], "processing")
                
                return item
            return None
        except Error as e:
            print(f"Error getting next pending item: {e}")
            return None
    
    def get_queue_stats(self):
        """
        Get statistics about the processing queue.
        
        Returns:
            dict: Queue statistics
        """
        try:
            self.cursor.execute("""
                SELECT status, COUNT(*) 
                FROM processing_queue
                GROUP BY status
            """)
            
            stats = {"pending": 0, "processing": 0, "completed": 0, "error": 0}
            
            for row in self.cursor.fetchall():
                stats[row[0]] = row[1]
            
            return stats
        except Error as e:
            print(f"Error getting queue stats: {e}")
            return {"pending": 0, "processing": 0, "completed": 0, "error": 0}
    
    #
    # Processing Queue Methods for Background Service
    #
    
    def add_to_processing_queue(self, page_id, operation, parameters=None, priority=1):
        """
        Add a task to the processing queue.
        
        Args:
            page_id (str): ID of the newspaper page to process
            operation (str): Operation to perform (e.g., 'ocr', 'segment', 'extract_articles')
            parameters (str, optional): JSON-encoded parameters string
            priority (int, optional): Priority of the task (lower numbers = higher priority)
            
        Returns:
            str: Task ID in the format {page_id}_{operation}, or None if failed
        """
        try:
            task_id = f"{page_id}_{operation}"
            
            # Check if already in queue
            self.cursor.execute("""
                SELECT queue_id FROM processing_queue
                WHERE page_id = ? AND operation = ? AND status = 'pending'
            """, (page_id, operation))
            
            if self.cursor.fetchone():
                print(f"Task {task_id} already in queue")
                return task_id
            
            # Add to queue
            self.cursor.execute("""
                INSERT INTO processing_queue 
                (page_id, operation, parameters, status, priority, added_date)
                VALUES (?, ?, ?, 'pending', ?, datetime('now'))
            """, (page_id, operation, parameters, priority))
            
            self.conn.commit()
            print(f"Added task {task_id} to processing queue")
            return task_id
            
        except Error as e:
            print(f"Error adding to processing queue: {e}")
            return None
    
    def get_pending_processing_queue_items(self, limit=100):
        """
        Get pending items from the processing queue.
        
        Args:
            limit (int): Maximum number of items to return
            
        Returns:
            list: List of pending queue items
        """
        try:
            self.cursor.execute("""
                SELECT queue_id, page_id, operation, parameters, priority, retries, last_error, added_date
                FROM processing_queue
                WHERE status = 'pending'
                ORDER BY priority, added_date
                LIMIT ?
            """, (limit,))
            
            items = []
            for row in self.cursor.fetchall():
                items.append({
                    "queue_id": row[0],
                    "page_id": row[1],
                    "operation": row[2],
                    "parameters": row[3],
                    "priority": row[4],
                    "retries": row[5],
                    "last_error": row[6],
                    "added_date": row[7]
                })
            
            return items
            
        except Error as e:
            print(f"Error getting pending queue items: {e}")
            return []
    
    def get_processing_queue_item(self, item_id):
        """
        Get a specific item from the processing queue.
        
        Args:
            item_id (str): Task ID in the format {page_id}_{operation}
            
        Returns:
            dict: Queue item, or None if not found
        """
        try:
            # Parse the item ID to get page_id and operation
            if '_' in item_id:
                page_id, operation = item_id.split('_', 1)
                
                self.cursor.execute("""
                    SELECT queue_id, page_id, operation, parameters, status, priority,
                           retries, last_error, added_date, started_at, completed_at, result
                    FROM processing_queue
                    WHERE page_id = ? AND operation = ?
                """, (page_id, operation))
                
                row = self.cursor.fetchone()
                if row:
                    return {
                        "queue_id": row[0],
                        "page_id": row[1],
                        "operation": row[2],
                        "parameters": row[3],
                        "status": row[4],
                        "priority": row[5],
                        "retries": row[6],
                        "last_error": row[7],
                        "added_date": row[8],
                        "started_at": row[9],
                        "completed_at": row[10],
                        "result": row[11]
                    }
            
            return None
            
        except Error as e:
            print(f"Error getting queue item {item_id}: {e}")
            return None
    
    def update_processing_queue_item(self, item_id, **kwargs):
        """
        Update a processing queue item.
        
        Args:
            item_id (str): Task ID in the format {page_id}_{operation}
            **kwargs: Keyword arguments to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parse the item ID to get page_id and operation
            if '_' in item_id:
                page_id, operation = item_id.split('_', 1)
                
                # Build the update query
                set_clause = []
                params = []
                
                for key, value in kwargs.items():
                    set_clause.append(f"{key} = ?")
                    params.append(value)
                
                params.extend([page_id, operation])
                
                # Execute the update
                self.cursor.execute(f"""
                    UPDATE processing_queue
                    SET {', '.join(set_clause)}
                    WHERE page_id = ? AND operation = ?
                """, params)
                
                self.conn.commit()
                return self.cursor.rowcount > 0
            
            return False
            
        except Error as e:
            print(f"Error updating queue item {item_id}: {e}")
            return False
    
    def remove_from_processing_queue(self, item_id):
        """
        Remove an item from the processing queue.
        
        Args:
            item_id (str): Task ID in the format {page_id}_{operation}
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parse the item ID to get page_id and operation
            if '_' in item_id:
                page_id, operation = item_id.split('_', 1)
                
                self.cursor.execute("""
                    DELETE FROM processing_queue
                    WHERE page_id = ? AND operation = ?
                """, (page_id, operation))
                
                self.conn.commit()
                return self.cursor.rowcount > 0
            
            return False
            
        except Error as e:
            print(f"Error removing queue item {item_id}: {e}")
            return False
    
    def add_to_queue(self, file_path, priority=1):
        """
        Add a file to the processing queue.
        
        This is a legacy method kept for backward compatibility.
        New code should use add_to_processing_queue instead.
        
        Args:
            file_path (str): Path to the file to process
            priority (int): Priority of the task (lower numbers = higher priority)
            
        Returns:
            int: Queue ID if successful, None otherwise
        """
        # Extract page ID from file path for backward compatibility
        try:
            # Create a placeholder page ID from the file path
            page_id = f"file_{os.path.basename(file_path)}"
            
            # Add to new queue format
            task_id = self.add_to_processing_queue(
                page_id=page_id,
                operation="ocr",
                parameters=json.dumps({"file_path": file_path}),
                priority=priority
            )
            
            return task_id
        except Exception as e:
            print(f"Error adding file to queue: {e}")
            return None
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Closed database connection")