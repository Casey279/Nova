#!/usr/bin/env python3
# File: main_db_connector.py

import os
import sys
import json
import sqlite3
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MainDBConnector')

class MainDBConnector:
    """
    Facilitates data transfer between the newspaper repository and the main Nova database.
    
    Handles:
    - Converting repository article segments to main database events
    - Creating new events in the main database
    - Establishing links between repository articles and main database events
    - Updating status flags when articles are promoted
    - Detecting potential duplicates before import
    - Supporting both individual and batch imports
    - Syncing changes between the systems
    """
    
    def __init__(self, repo_db_manager, main_db_connection):
        """
        Initialize the main database connector.
        
        Args:
            repo_db_manager: Repository database manager instance
            main_db_connection: Connection to the main Nova database or path to database file
        """
        self.repo_db = repo_db_manager
        
        # Set up connection to main database
        if isinstance(main_db_connection, str):
            # It's a path to the database
            self.main_db_path = main_db_connection
            try:
                self.main_db_conn = sqlite3.connect(main_db_connection)
                self.main_db_conn.row_factory = sqlite3.Row
                self.main_db_cursor = self.main_db_conn.cursor()
            except sqlite3.Error as e:
                logger.error(f"Error connecting to main database: {e}")
                raise
        else:
            # It's an existing connection or service
            self.main_db_conn = main_db_connection
            self.main_db_path = None
            
            # Try to get a cursor - this will fail if main_db_connection isn't a valid connection
            # or if it doesn't have the expected interface
            try:
                if hasattr(main_db_connection, 'cursor'):
                    # It's a sqlite3 connection
                    self.main_db_cursor = main_db_connection.cursor()
                elif hasattr(main_db_connection, 'conn'):
                    # It's a DatabaseManager or similar object
                    self.main_db_conn = main_db_connection.conn
                    self.main_db_cursor = main_db_connection.cursor
                else:
                    raise ValueError("Cannot determine how to get a cursor from the provided connection")
            except Exception as e:
                logger.error(f"Error setting up main database cursor: {e}")
                raise
                
        # Validate the connections
        self._validate_connections()
        
        # Cache for event types and sources
        self.event_types_cache = {}
        self.sources_cache = {}
    
    def _validate_connections(self):
        """Validate that both database connections are working and have expected schema."""
        # Check repository database
        if not hasattr(self.repo_db, 'conn') or not self.repo_db.conn:
            raise ValueError("Repository database connection is not available")
        
        # Test repository database by querying for a table
        try:
            cursor = self.repo_db.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='newspaper_pages'")
            if not cursor.fetchone():
                raise ValueError("Repository database does not have expected schema")
        except Exception as e:
            raise ValueError(f"Repository database validation failed: {e}")
        
        # Test main database
        try:
            self.main_db_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Events'")
            if not self.main_db_cursor.fetchone():
                raise ValueError("Main database does not have Events table")
            
            self.main_db_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Sources'")
            if not self.main_db_cursor.fetchone():
                raise ValueError("Main database does not have Sources table")
        except Exception as e:
            raise ValueError(f"Main database validation failed: {e}")
            
    def import_segment_as_event(self, segment_id: int, title: str, date: str, 
                               text_content: str, source_id: str) -> Optional[int]:
        """
        Import a repository article segment as an event in the main database.
        
        Args:
            segment_id: ID of the segment in the repository
            title: Title for the new event
            date: Date for the event (YYYY-MM-DD)
            text_content: Text content of the article
            source_id: ID of the source in the main database
            
        Returns:
            ID of the created event or None if import failed
        """
        try:
            # Check if segment exists
            segment = self.repo_db.get_segment_by_id(segment_id)
            if not segment:
                logger.error(f"Segment ID {segment_id} not found in repository")
                return None
                
            # Check if segment is already imported
            if segment.get('processing_status') == 'imported':
                logger.info(f"Segment {segment_id} already imported as event {segment.get('linked_event_id')}")
                return segment.get('linked_event_id')
            
            # Get page info for additional metadata
            page_info = self.repo_db.get_page_by_id(segment['page_id'])
            
            # Check if source exists in main database
            main_source_id = self._ensure_source_exists(source_id, page_info)
            
            # Create event in main database
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Prepare the event data
            event_data = {
                'EventTitle': title,
                'EventDate': date,
                'EventText': text_content,
                'SourceID': main_source_id,
                'page_number': page_info['page_number'] if page_info else None,
                'created_date': current_date,
                'modified_date': current_date,
                'status': 'active',
                'confidence': 0.8,  # Default confidence
                'verified': 0       # Not verified by default
            }
            
            # Handle optional image
            if segment.get('image_path') and os.path.exists(segment['image_path']):
                # Copy image to main database assets folder
                dest_path = self._copy_image_to_main_db(
                    segment['image_path'],
                    page_info['newspaper_name'] if page_info else 'Unknown',
                    date
                )
                if dest_path:
                    event_data['image_path'] = dest_path
            
            # Insert the event
            event_id = self._create_event(event_data)
            
            if not event_id:
                logger.error(f"Failed to create event for segment {segment_id}")
                return None
                
            # Extract and add entities, characters, and locations if available
            self._extract_and_add_entities(event_id, text_content)
            
            # Update repository segment status
            self.repo_db.update_segment_status(segment_id, 'imported', event_id)
            
            logger.info(f"Successfully imported segment {segment_id} as event {event_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"Error importing segment {segment_id}: {e}")
            return None
    
    def find_potential_duplicates(self, text_content: str, title: str = None, 
                                date: str = None) -> List[int]:
        """
        Find potential duplicate events in the main database.
        
        Args:
            text_content: Text content to check for duplicates
            title: Optional title to check 
            date: Optional date to narrow search
            
        Returns:
            List of event IDs that could be duplicates
        """
        try:
            # Create a list to store potential duplicate event IDs
            duplicates = []
            
            # First, check by exact title match if title is provided
            if title:
                query = "SELECT EventID FROM Events WHERE EventTitle = ?"
                self.main_db_cursor.execute(query, (title,))
                rows = self.main_db_cursor.fetchall()
                for row in rows:
                    duplicates.append(row[0])
            
            # If we have date, use it to narrow search
            date_clause = ""
            params = []
            
            if date:
                date_clause = "WHERE EventDate = ?"
                params = [date]
                
            # Check for text similarity
            # We'll use a simple approach: look for events containing significant segments 
            # of the article text
            
            # Split text into words and take chunks for searching
            words = text_content.split()
            if len(words) >= 10:
                # Take first 10 words as a search phrase
                start_phrase = " ".join(words[:10])
                
                # Take 10 words from the middle
                mid_index = len(words) // 2
                mid_phrase = " ".join(words[mid_index:mid_index+10])
                
                # Search for events containing these phrases
                for phrase in [start_phrase, mid_phrase]:
                    query = f"SELECT EventID FROM Events {date_clause} WHERE EventText LIKE ?"
                    search_params = params + [f"%{phrase}%"]
                    
                    self.main_db_cursor.execute(query, search_params)
                    rows = self.main_db_cursor.fetchall()
                    
                    for row in rows:
                        event_id = row[0]
                        if event_id not in duplicates:
                            duplicates.append(event_id)
            
            # Check for events with very similar titles
            if title and len(title) > 10:
                # Use first part of title as a search term
                title_start = title[:len(title)//2]
                
                query = f"SELECT EventID FROM Events {date_clause} WHERE EventTitle LIKE ?"
                search_params = params + [f"%{title_start}%"]
                
                self.main_db_cursor.execute(query, search_params)
                rows = self.main_db_cursor.fetchall()
                
                for row in rows:
                    event_id = row[0]
                    if event_id not in duplicates:
                        duplicates.append(event_id)
            
            return duplicates
            
        except Exception as e:
            logger.error(f"Error finding potential duplicates: {e}")
            return []
    
    def batch_import_segments(self, segment_ids: List[int]) -> Dict[str, Any]:
        """
        Import multiple segments to the main database in a batch.
        
        Args:
            segment_ids: List of segment IDs to import
            
        Returns:
            Dictionary with counts of successful and failed imports
        """
        results = {
            'success_count': 0,
            'failure_count': 0,
            'duplicate_count': 0,
            'failures': [],
            'duplicates': []
        }
        
        for segment_id in segment_ids:
            try:
                # Get segment details
                segment = self.repo_db.get_segment_by_id(segment_id)
                if not segment:
                    results['failure_count'] += 1
                    results['failures'].append({
                        'segment_id': segment_id,
                        'reason': 'Segment not found'
                    })
                    continue
                
                # Get page info
                page_info = self.repo_db.get_page_by_id(segment['page_id'])
                
                # Check for duplicates
                duplicate_events = self.find_potential_duplicates(
                    segment['text_content'],
                    segment.get('headline'),
                    page_info['publication_date'] if page_info else None
                )
                
                if duplicate_events:
                    # Mark as duplicate of the first matching event
                    self.repo_db.update_segment_status(segment_id, 'duplicate', duplicate_events[0])
                    
                    results['duplicate_count'] += 1
                    results['duplicates'].append({
                        'segment_id': segment_id,
                        'duplicate_of': duplicate_events[0]
                    })
                    continue
                
                # Import the segment
                event_id = self.import_segment_as_event(
                    segment_id,
                    segment.get('headline', f"Article from {page_info['newspaper_name']}"),
                    page_info['publication_date'] if page_info else datetime.now().strftime('%Y-%m-%d'),
                    segment['text_content'],
                    page_info.get('source_id', '1')  # Default to ID 1 if not found
                )
                
                if event_id:
                    results['success_count'] += 1
                else:
                    results['failure_count'] += 1
                    results['failures'].append({
                        'segment_id': segment_id,
                        'reason': 'Import failed'
                    })
                    
            except Exception as e:
                logger.error(f"Error in batch import for segment {segment_id}: {e}")
                results['failure_count'] += 1
                results['failures'].append({
                    'segment_id': segment_id,
                    'reason': str(e)
                })
        
        return results
    
    def sync_from_main_to_repo(self, event_id: int) -> bool:
        """
        Sync changes from a main database event back to the repository.
        
        Args:
            event_id: ID of the event in the main database
            
        Returns:
            True if sync was successful, False otherwise
        """
        try:
            # Find segment linked to this event
            segments = self.repo_db.get_segments_by_event_id(event_id)
            if not segments:
                logger.warning(f"No segments found in repository linked to event {event_id}")
                return False
                
            # Get event data from main database
            query = """
                SELECT EventTitle, EventText, EventDate, modified_date 
                FROM Events WHERE EventID = ?
            """
            self.main_db_cursor.execute(query, (event_id,))
            row = self.main_db_cursor.fetchone()
            
            if not row:
                logger.error(f"Event {event_id} not found in main database")
                return False
                
            # Get values from row (handle both tuple and sqlite.Row)
            if hasattr(row, 'keys'):
                event_title = row['EventTitle']
                event_text = row['EventText']
                event_date = row['EventDate']
                modified_date = row['modified_date']
            else:
                event_title, event_text, event_date, modified_date = row
                
            # Update each linked segment in repository
            for segment in segments:
                # Only update if main database version is newer
                if (not modified_date or not segment.get('modified_date') or 
                    modified_date > segment['modified_date']):
                    
                    # Update headline and text content
                    self.repo_db.update_segment_content(
                        segment['id'],
                        event_title,
                        event_text
                    )
                    
                    logger.info(f"Synced segment {segment['id']} from event {event_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error syncing from main database to repository for event {event_id}: {e}")
            return False
    
    def sync_all_events(self) -> Dict[str, int]:
        """
        Sync all events between main database and repository.
        
        Returns:
            Dictionary with counts of synced, failed, and unchanged items
        """
        results = {
            'synced_to_main': 0,
            'synced_to_repo': 0,
            'unchanged': 0,
            'failed': 0
        }
        
        try:
            # Get all segments that are linked to main database events
            segments = self.repo_db.get_segments_by_status('imported')
            
            for segment in segments:
                try:
                    event_id = segment.get('linked_event_id')
                    if not event_id:
                        continue
                        
                    # Get event data from main database
                    query = "SELECT modified_date FROM Events WHERE EventID = ?"
                    self.main_db_cursor.execute(query, (event_id,))
                    row = self.main_db_cursor.fetchone()
                    
                    if not row:
                        logger.warning(f"Event {event_id} not found in main database")
                        continue
                        
                    # Get modified date
                    main_modified = row[0] if isinstance(row, tuple) else row['modified_date']
                    repo_modified = segment.get('modified_date')
                    
                    # Compare modification dates
                    if main_modified and repo_modified:
                        if main_modified > repo_modified:
                            # Main is newer, sync to repo
                            if self.sync_from_main_to_repo(event_id):
                                results['synced_to_repo'] += 1
                            else:
                                results['failed'] += 1
                        elif repo_modified > main_modified:
                            # Repo is newer, sync to main
                            if self._update_main_from_segment(segment['id'], event_id):
                                results['synced_to_main'] += 1
                            else:
                                results['failed'] += 1
                        else:
                            # Same modification date, no sync needed
                            results['unchanged'] += 1
                    else:
                        # Missing dates, do full sync in both directions to be safe
                        self.sync_from_main_to_repo(event_id)
                        self._update_main_from_segment(segment['id'], event_id)
                        results['synced_to_repo'] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing segment {segment['id']}: {e}")
                    results['failed'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error in sync_all_events: {e}")
            return results
    
    def mark_segment_as_duplicate(self, segment_id: int, event_id: int) -> bool:
        """
        Mark a segment as a duplicate of an existing event.
        
        Args:
            segment_id: ID of the segment in the repository
            event_id: ID of the existing event in the main database
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            # Verify event exists in main database
            query = "SELECT EventID FROM Events WHERE EventID = ?"
            self.main_db_cursor.execute(query, (event_id,))
            if not self.main_db_cursor.fetchone():
                logger.error(f"Event {event_id} not found in main database")
                return False
                
            # Update segment status
            return self.repo_db.update_segment_status(segment_id, 'duplicate', event_id)
            
        except Exception as e:
            logger.error(f"Error marking segment {segment_id} as duplicate: {e}")
            return False
    
    def get_segments_for_event(self, event_id: int) -> List[Dict[str, Any]]:
        """
        Get all repository segments linked to a main database event.
        
        Args:
            event_id: ID of the event in the main database
            
        Returns:
            List of segment dictionaries
        """
        try:
            return self.repo_db.get_segments_by_event_id(event_id)
        except Exception as e:
            logger.error(f"Error getting segments for event {event_id}: {e}")
            return []
    
    def get_event_details(self, event_id: int) -> Dict[str, Any]:
        """
        Get detailed information about an event from the main database.
        
        Args:
            event_id: ID of the event
            
        Returns:
            Dictionary with event details or empty dict if not found
        """
        try:
            query = """
                SELECT e.EventID, e.EventTitle, e.EventText, e.EventDate, 
                       e.SourceID, s.SourceName, e.page_number, e.confidence, 
                       e.verified, e.created_date, e.modified_date, e.status
                FROM Events e
                LEFT JOIN Sources s ON e.SourceID = s.SourceID
                WHERE e.EventID = ?
            """
            self.main_db_cursor.execute(query, (event_id,))
            row = self.main_db_cursor.fetchone()
            
            if not row:
                return {}
                
            # Handle both tuple and sqlite.Row
            if hasattr(row, 'keys'):
                event = dict(row)
            else:
                event = {
                    'EventID': row[0],
                    'EventTitle': row[1], 
                    'EventText': row[2],
                    'EventDate': row[3],
                    'SourceID': row[4],
                    'SourceName': row[5],
                    'page_number': row[6],
                    'confidence': row[7],
                    'verified': row[8],
                    'created_date': row[9],
                    'modified_date': row[10],
                    'status': row[11]
                }
                
            # Get linked segments from repository
            event['linked_segments'] = self.get_segments_for_event(event_id)
            
            return event
            
        except Exception as e:
            logger.error(f"Error getting event details for {event_id}: {e}")
            return {}
    
    def _ensure_source_exists(self, source_id: str, page_info: Dict[str, Any]) -> int:
        """
        Ensure source exists in main database, creating it if necessary.
        
        Args:
            source_id: Source ID from repository
            page_info: Dictionary with page information
            
        Returns:
            ID of the source in the main database
        """
        try:
            # Check if source is already cached
            if source_id in self.sources_cache:
                return self.sources_cache[source_id]
                
            # Try to find existing source by name
            source_name = page_info.get('newspaper_name', 'Unknown')
            query = "SELECT SourceID FROM Sources WHERE SourceName = ?"
            self.main_db_cursor.execute(query, (source_name,))
            row = self.main_db_cursor.fetchone()
            
            if row:
                source_id_in_main = row[0]
                self.sources_cache[source_id] = source_id_in_main
                return source_id_in_main
                
            # Create new source
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            query = """
                INSERT INTO Sources (SourceName, SourceType, Publisher, 
                                   EstablishedDate, ReviewStatus)
                VALUES (?, ?, ?, ?, ?)
            """
            
            # Use newspaper type for all sources from this repository
            self.main_db_cursor.execute(query, (
                source_name,
                "Newspaper",
                page_info.get('publisher', ''),
                page_info.get('established_date', ''),
                "imported"
            ))
            
            self.main_db_conn.commit()
            new_source_id = self.main_db_cursor.lastrowid
            
            self.sources_cache[source_id] = new_source_id
            return new_source_id
            
        except Exception as e:
            logger.error(f"Error ensuring source exists: {e}")
            # Default to source ID 1 if there's an error
            return 1
    
    def _create_event(self, event_data: Dict[str, Any]) -> Optional[int]:
        """
        Create a new event in the main database.
        
        Args:
            event_data: Dictionary with event data
            
        Returns:
            ID of the created event or None if creation failed
        """
        try:
            # Prepare query based on available fields
            fields = []
            values = []
            placeholders = []
            
            for key, value in event_data.items():
                if value is not None:
                    fields.append(key)
                    values.append(value)
                    placeholders.append('?')
            
            query = f"""
                INSERT INTO Events ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            """
            
            self.main_db_cursor.execute(query, values)
            self.main_db_conn.commit()
            
            return self.main_db_cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return None
    
    def _copy_image_to_main_db(self, image_path: str, source_name: str, date_str: str) -> Optional[str]:
        """
        Copy an image file to the main database's file structure.
        
        Args:
            image_path: Path to the source image
            source_name: Name of the source
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Path to the copied file or None if copy failed
        """
        try:
            if not os.path.exists(image_path):
                logger.warning(f"Image file not found: {image_path}")
                return None
                
            # If we don't know the main database path, we can't determine where to copy
            if not self.main_db_path:
                logger.warning("Cannot copy image: main database path unknown")
                return None
                
            # Get main database directory
            main_db_dir = os.path.dirname(self.main_db_path)
            
            # Determine assets directory (typical Nova structure)
            assets_dir = os.path.join(main_db_dir, '..', 'assets', 'EnteredEvents')
            if not os.path.exists(assets_dir):
                # Try another common location
                assets_dir = os.path.join(main_db_dir, 'assets', 'EnteredEvents')
                if not os.path.exists(assets_dir):
                    # Create the directory
                    os.makedirs(assets_dir, exist_ok=True)
            
            # Clean up source name for filename
            safe_source = source_name.replace(' ', '_').replace('/', '-')[:20]
            
            # Generate a Nova-style filename: DATE_TITLE_TYPE_SOURCE_PAGE_CODE.jpg
            # Default format for imported newspaper articles
            basename = os.path.basename(image_path)
            ext = os.path.splitext(basename)[1] or '.jpg'
            
            new_filename = f"{date_str}_Article_N_{safe_source}_1_XX{ext}"
            
            # Full destination path
            dest_path = os.path.join(assets_dir, new_filename)
            
            # Copy the file
            shutil.copy2(image_path, dest_path)
            logger.info(f"Copied image to {dest_path}")
            
            return dest_path
            
        except Exception as e:
            logger.error(f"Error copying image to main database: {e}")
            return None
    
    def _extract_and_add_entities(self, event_id: int, text_content: str) -> None:
        """
        Extract entities from text and add them to the event.
        
        Args:
            event_id: ID of the event
            text_content: Text content to analyze
        """
        try:
            # This is a simplified implementation - in a real system, you'd use
            # an NLP library or service to extract entities
            
            # Simple keyword extraction based on capitalized words
            words = text_content.split()
            potential_entities = set()
            
            for i, word in enumerate(words):
                # Look for capitalized words not at the start of sentences
                if (len(word) > 1 and word[0].isupper() and word[1:].islower() and 
                    (i > 0 and words[i-1][-1] not in '.!?')):
                    potential_entities.add(word.strip(',.;:()[]{}"\'-'))
            
            # Add extracted entities (up to 10)
            for entity in list(potential_entities)[:10]:
                self._add_entity_to_event(event_id, entity, 'unknown')
                
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
    
    def _add_entity_to_event(self, event_id: int, entity_name: str, entity_type: str) -> None:
        """
        Add an entity to an event in the main database.
        
        Args:
            event_id: ID of the event
            entity_name: Name of the entity
            entity_type: Type of entity
        """
        try:
            # Check if entity exists
            query = "SELECT EventID FROM Entities WHERE name = ?"
            self.main_db_cursor.execute(query, (entity_name,))
            row = self.main_db_cursor.fetchone()
            
            entity_id = None
            if row:
                entity_id = row[0]
            else:
                # Create new entity
                query = "INSERT INTO Entities (name, entity_type) VALUES (?, ?)"
                self.main_db_cursor.execute(query, (entity_name, entity_type))
                self.main_db_conn.commit()
                entity_id = self.main_db_cursor.lastrowid
            
            if entity_id:
                # Link entity to event
                query = "INSERT INTO entity_mentions (event_id, entity_id) VALUES (?, ?)"
                self.main_db_cursor.execute(query, (event_id, entity_id))
                self.main_db_conn.commit()
                
        except Exception as e:
            logger.error(f"Error adding entity to event: {e}")
    
    def _update_main_from_segment(self, segment_id: int, event_id: int) -> bool:
        """
        Update a main database event from repository segment data.
        
        Args:
            segment_id: ID of the segment in repository
            event_id: ID of the event in main database
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Get segment data
            segment = self.repo_db.get_segment_by_id(segment_id)
            if not segment:
                logger.error(f"Segment {segment_id} not found")
                return False
                
            # Update event in main database
            query = """
                UPDATE Events 
                SET EventTitle = ?, EventText = ?, modified_date = ?
                WHERE EventID = ?
            """
            
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.main_db_cursor.execute(query, (
                segment.get('headline', ''),
                segment.get('text_content', ''),
                current_date,
                event_id
            ))
            
            self.main_db_conn.commit()
            logger.info(f"Updated event {event_id} from segment {segment_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating main database from segment: {e}")
            return False