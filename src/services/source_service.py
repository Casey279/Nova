# File: source_service.py

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from .base_service import BaseService, DatabaseError

class SourceService(BaseService):
    """
    Service for handling source-related database operations.
    Sources include documents, articles, books, and other reference materials.
    """
    
    def get_all_sources(self) -> List[Tuple]:
        """
        Get all sources from the database.
        
        Returns:
            List of source records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT id, title, author, source_type, publication_date, url 
            FROM sources
            ORDER BY title
        """
        return self.execute_query(query)
    
    def search_sources(self, search_text: str, filter_column: Optional[str] = None) -> List[Tuple]:
        """
        Search for sources matching the criteria.
        
        Args:
            search_text: Text to search for
            filter_column: Column to search in (None for all columns)
            
        Returns:
            List of matching source records
            
        Raises:
            DatabaseError: If query fails
        """
        if filter_column and filter_column.lower() != "all":
            query = f"""
                SELECT id, title, author, source_type, publication_date, url 
                FROM sources
                WHERE {filter_column.lower()} LIKE ?
                ORDER BY title
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT id, title, author, source_type, publication_date, url 
                FROM sources
                WHERE title LIKE ? OR author LIKE ? OR source_type LIKE ? OR 
                      publication_date LIKE ? OR url LIKE ? OR content LIKE ?
                ORDER BY title
            """
            params = (
                f"%{search_text}%", f"%{search_text}%", f"%{search_text}%",
                f"%{search_text}%", f"%{search_text}%", f"%{search_text}%"
            )
        
        return self.execute_query(query, params)
    
    def get_source_by_id(self, source_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a source by ID.
        
        Args:
            source_id: ID of the source
            
        Returns:
            Source data as a dictionary, or None if not found
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT id, title, author, source_type, publication_date, url, content 
            FROM sources
            WHERE id = ?
        """
        results = self.execute_query(query, (source_id,))
        
        if results:
            return {
                'id': results[0][0],
                'title': results[0][1],
                'author': results[0][2],
                'source_type': results[0][3],
                'publication_date': results[0][4],
                'url': results[0][5],
                'content': results[0][6]
            }
        
        return None
    
    def create_source(self, source_data: Dict[str, Any]) -> int:
        """
        Create a new source.
        
        Args:
            source_data: Dictionary with source data
            
        Returns:
            ID of the created source
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            INSERT INTO sources (title, author, source_type, publication_date, url, content)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        
        # Format date if provided
        pub_date = source_data.get('publication_date')
        if isinstance(pub_date, datetime):
            pub_date = pub_date.strftime('%Y-%m-%d')
        
        params = (
            source_data.get('title', ''),
            source_data.get('author', ''),
            source_data.get('source_type', 'document'),
            pub_date,
            source_data.get('url', ''),
            source_data.get('content', '')
        )
        
        self.execute_update(query, params)
        return self.get_last_insert_id()
    
    def update_source(self, source_id: int, source_data: Dict[str, Any]) -> bool:
        """
        Update an existing source.
        
        Args:
            source_id: ID of the source to update
            source_data: Dictionary with updated source data
            
        Returns:
            True if successful, False if source not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            UPDATE sources
            SET title = ?, author = ?, source_type = ?, publication_date = ?, url = ?, content = ?
            WHERE id = ?
        """
        
        # Format date if provided
        pub_date = source_data.get('publication_date')
        if isinstance(pub_date, datetime):
            pub_date = pub_date.strftime('%Y-%m-%d')
        
        params = (
            source_data.get('title', ''),
            source_data.get('author', ''),
            source_data.get('source_type', 'document'),
            pub_date,
            source_data.get('url', ''),
            source_data.get('content', ''),
            source_id
        )
        
        rows_affected = self.execute_update(query, params)
        return rows_affected > 0
    
    def delete_source(self, source_id: int) -> bool:
        """
        Delete a source.
        
        Args:
            source_id: ID of the source to delete
            
        Returns:
            True if successful, False if source not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = "DELETE FROM sources WHERE id = ?"
        rows_affected = self.execute_update(query, (source_id,))
        return rows_affected > 0
    
    def get_source_references(self, source_id: int) -> Dict[str, int]:
        """
        Get counts of entity references in a source.
        
        Args:
            source_id: ID of the source
            
        Returns:
            Dictionary with counts of different reference types
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            conn, cursor = self.connect()
            
            # Get character mentions
            cursor.execute("""
                SELECT COUNT(*) FROM character_mentions
                WHERE source_id = ?
            """, (source_id,))
            character_count = cursor.fetchone()[0]
            
            # Get location mentions
            cursor.execute("""
                SELECT COUNT(*) FROM location_mentions
                WHERE source_id = ?
            """, (source_id,))
            location_count = cursor.fetchone()[0]
            
            # Get entity mentions
            cursor.execute("""
                SELECT COUNT(*) FROM entity_mentions
                WHERE source_id = ?
            """, (source_id,))
            entity_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'characters': character_count,
                'locations': location_count,
                'entities': entity_count
            }
        
        except Exception as e:
            raise DatabaseError(f"Failed to get source references: {str(e)}")
    
    def delete_source_with_references(self, source_id: int) -> bool:
        """
        Delete a source and all its references.
        
        Args:
            source_id: ID of the source to delete
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If transaction fails
        """
        queries = [
            {
                'query': "DELETE FROM character_mentions WHERE source_id = ?",
                'params': (source_id,)
            },
            {
                'query': "DELETE FROM location_mentions WHERE source_id = ?",
                'params': (source_id,)
            },
            {
                'query': "DELETE FROM entity_mentions WHERE source_id = ?",
                'params': (source_id,)
            },
            {
                'query': "DELETE FROM sources WHERE id = ?",
                'params': (source_id,)
            }
        ]
        
        self.execute_transaction(queries)
        return True
    
    def get_source_types(self) -> List[str]:
        """
        Get all unique source types in the database.
        
        Returns:
            List of source types
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT DISTINCT source_type 
            FROM sources
            ORDER BY source_type
        """
        results = self.execute_query(query)
        return [result[0] for result in results if result[0]]
    
    def get_source_content(self, source_id: int) -> Optional[str]:
        """
        Get the content of a source.
        
        Args:
            source_id: ID of the source
            
        Returns:
            Source content or None if not found
            
        Raises:
            DatabaseError: If query fails
        """
        query = "SELECT content FROM sources WHERE id = ?"
        results = self.execute_query(query, (source_id,))
        
        if results and results[0][0]:
            return results[0][0]
        
        return None