# File: document_service.py

import os
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from .base_service import BaseService, DatabaseError

class DocumentService(BaseService):
    """
    Service for handling document processing operations.
    Provides methods for parsing and processing documents.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the document service.
        
        Args:
            db_path: Path to the database
        """
        super().__init__(db_path)
    
    def parse_document_name(self, filename: str) -> Dict[str, Any]:
        """
        Parse document filename to extract metadata.
        
        Args:
            filename: Name of the document file
            
        Returns:
            Dictionary containing extracted metadata
        """
        # Strip extension
        basename = os.path.splitext(filename)[0]
        
        # Default metadata
        metadata = {
            'date': None,
            'title': basename,
            'source': '',
            'author': '',
            'type': 'document'
        }
        
        # Try to extract date using various patterns
        date_patterns = [
            # YYYY-MM-DD
            r'(\d{4})[_\-](\d{1,2})[_\-](\d{1,2})',
            # MM-DD-YYYY
            r'(\d{1,2})[_\-](\d{1,2})[_\-](\d{4})',
            # YYYY.MM.DD
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
            # Just year (YYYY)
            r'\b(\d{4})\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, basename)
            if match:
                if len(match.groups()) == 3:
                    try:
                        if pattern == date_patterns[0]:  # YYYY-MM-DD
                            year, month, day = match.groups()
                        elif pattern == date_patterns[1]:  # MM-DD-YYYY
                            month, day, year = match.groups()
                        else:  # YYYY.MM.DD
                            year, month, day = match.groups()
                        
                        date_str = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                        metadata['date'] = date_str
                        
                        # Remove date from title
                        title = re.sub(pattern, '', basename).strip('_- ')
                        if title:
                            metadata['title'] = title
                        
                        break
                    except (ValueError, IndexError):
                        continue
                elif len(match.groups()) == 1:
                    # Just year
                    year = match.group(1)
                    metadata['date'] = f"{year}-01-01"
                    
                    # Remove year from title
                    title = re.sub(r'\b' + year + r'\b', '', basename).strip('_- ')
                    if title:
                        metadata['title'] = title
                    
                    break
        
        # Try to extract source if it's in brackets or parentheses
        source_patterns = [
            r'\[([^\]]+)\]',  # [Source]
            r'\(([^\)]+)\)',  # (Source)
        ]
        
        for pattern in source_patterns:
            match = re.search(pattern, basename)
            if match:
                metadata['source'] = match.group(1)
                
                # Remove source from title
                title = re.sub(pattern, '', metadata['title']).strip('_- ')
                if title:
                    metadata['title'] = title
                break
        
        return metadata
    
    def add_document(self, metadata: Dict[str, Any], content: str) -> int:
        """
        Add a document to the database.
        
        Args:
            metadata: Document metadata
            content: Document content
            
        Returns:
            ID of the added document
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # Format date if provided
            date_str = metadata.get('date')
            if date_str:
                try:
                    # Ensure date is in YYYY-MM-DD format
                    if isinstance(date_str, str):
                        if '-' in date_str:
                            datetime.strptime(date_str, '%Y-%m-%d')
                        else:
                            date_str = None
                except ValueError:
                    date_str = None
            
            query = """
                INSERT INTO sources (title, author, source_type, publication_date, content)
                VALUES (?, ?, ?, ?, ?)
            """
            
            params = (
                metadata.get('title', ''),
                metadata.get('author', ''),
                metadata.get('type', 'document'),
                date_str,
                content
            )
            
            self.execute_update(query, params)
            return self.get_last_insert_id()
            
        except Exception as e:
            raise DatabaseError(f"Failed to add document: {str(e)}")
    
    def extract_entities(self, content: str, document_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract entities from document content.
        
        Args:
            content: Document content
            document_id: ID of the document
            
        Returns:
            Dictionary with extracted entities
            
        Raises:
            DatabaseError: If database operation fails
        """
        # This is a placeholder for more sophisticated entity extraction
        # In a real implementation, this would use NLP or pattern matching
        
        entities = {
            'characters': [],
            'locations': [],
            'events': []
        }
        
        # Extract potential character names (capitalized words)
        name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        potential_names = re.findall(name_pattern, content)
        
        # Filter common words and duplicates
        common_words = {'The', 'A', 'An', 'This', 'That', 'These', 'Those', 'I', 'You', 'He', 'She', 'It', 'We', 'They'}
        unique_names = set()
        
        for name in potential_names:
            if name not in common_words and len(name) > 1 and name not in unique_names:
                unique_names.add(name)
                entities['characters'].append({
                    'name': name,
                    'confidence': 0.7,  # Placeholder confidence score
                    'mentions': []  # To be populated with positions
                })
        
        # Find mentions of each character
        for character in entities['characters']:
            name = character['name']
            for match in re.finditer(r'\b' + re.escape(name) + r'\b', content):
                start, end = match.span()
                context_start = max(0, start - 50)
                context_end = min(len(content), end + 50)
                
                character['mentions'].append({
                    'start': start,
                    'end': end,
                    'context': content[context_start:context_end]
                })
        
        return entities
    
    def store_entity_mentions(self, document_id: int, entities: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Store entity mentions in the database.
        
        Args:
            document_id: ID of the document
            entities: Dictionary with extracted entities
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            conn, cursor = self.connect()
            
            # Process characters
            for character in entities.get('characters', []):
                name = character['name']
                
                # Check if character exists
                cursor.execute("SELECT id FROM characters WHERE name = ?", (name,))
                result = cursor.fetchone()
                
                if result:
                    character_id = result[0]
                else:
                    # Create new character
                    cursor.execute(
                        "INSERT INTO characters (name, description, source) VALUES (?, ?, ?)",
                        (name, '', f"Auto-extracted from document ID: {document_id}")
                    )
                    character_id = cursor.lastrowid
                
                # Store mentions
                for mention in character.get('mentions', []):
                    cursor.execute(
                        """
                        INSERT INTO character_mentions 
                        (character_id, source_id, context, start_pos, end_pos)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            character_id,
                            document_id,
                            mention.get('context', ''),
                            mention.get('start', 0),
                            mention.get('end', 0)
                        )
                    )
            
            # Similar logic could be implemented for locations and events
            
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to store entity mentions: {str(e)}")
    
    def process_document(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Process a document: parse metadata, add to database, extract entities.
        
        Args:
            filename: Name of the document file
            content: Document content
            
        Returns:
            Dictionary with processing results
            
        Raises:
            DatabaseError: If processing fails
        """
        try:
            # Parse document name
            metadata = self.parse_document_name(filename)
            
            # Add document to database
            document_id = self.add_document(metadata, content)
            
            # Extract entities
            entities = self.extract_entities(content, document_id)
            
            # Store entity mentions
            self.store_entity_mentions(document_id, entities)
            
            return {
                'document_id': document_id,
                'metadata': metadata,
                'entities': {
                    'characters': len(entities.get('characters', [])),
                    'locations': len(entities.get('locations', [])),
                    'events': len(entities.get('events', []))
                }
            }
        except Exception as e:
            raise DatabaseError(f"Document processing failed: {str(e)}")