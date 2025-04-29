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
            SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                   Publisher, City, State, Country, URL, FileName, ImportDate, ReviewStatus
            FROM Sources
            ORDER BY Title
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
            column = filter_column.lower()
            # Map UI column names to database column names
            column_mapping = {
                "title": "Title",
                "aliases": "Aliases",
                "author": "Author",
                "source_type": "SourceType",
                "publication_date": "PublicationDate",
                "publisher": "Publisher",
                "city": "City",
                "state": "State",
                "country": "Country",
                "url": "URL",
                "file_name": "FileName",
                "content": "Content"
            }
            db_column = column_mapping.get(column, column)
            
            query = f"""
                SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                       Publisher, City, State, Country, URL, FileName, ImportDate, ReviewStatus
                FROM Sources
                WHERE {db_column} LIKE ?
                ORDER BY Title
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                       Publisher, City, State, Country, URL, FileName, ImportDate, ReviewStatus
                FROM Sources
                WHERE Title LIKE ? OR Aliases LIKE ? OR Author LIKE ? OR 
                      SourceType LIKE ? OR PublicationDate LIKE ? OR Content LIKE ?
                ORDER BY Title
            """
            params = (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", 
                     f"%{search_text}%", f"%{search_text}%", f"%{search_text}%")
        
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
            SELECT SourceID, Title, Aliases, Author, SourceType, PublicationDate, 
                   Publisher, City, State, Country, URL, Content, FileName, 
                   ImportDate, ReviewStatus
            FROM Sources
            WHERE SourceID = ?
        """
        results = self.execute_query(query, (source_id,))
        
        if results:
            return {
                'id': results[0][0],  # Keep 'id' for component compatibility
                'title': results[0][1],
                'aliases': results[0][2],
                'author': results[0][3],
                'source_type': results[0][4],
                'publication_date': results[0][5],
                'publisher': results[0][6],
                'city': results[0][7],
                'state': results[0][8],
                'country': results[0][9],
                'url': results[0][10],
                'content': results[0][11],
                'file_name': results[0][12],
                'import_date': results[0][13],
                'review_status': results[0][14]
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
            INSERT INTO Sources (Title, Aliases, Author, SourceType, PublicationDate, 
                               Publisher, City, State, Country, URL, 
                               Content, FileName, ImportDate, ReviewStatus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Format date if provided
        pub_date = source_data.get('publication_date')
        if isinstance(pub_date, datetime):
            pub_date = pub_date.strftime('%Y-%m-%d')
        
        import_date = source_data.get('import_date')
        if not import_date:
            import_date = datetime.now().strftime('%Y-%m-%d')
        elif isinstance(import_date, datetime):
            import_date = import_date.strftime('%Y-%m-%d')
        
        params = (
            source_data.get('title', ''),
            source_data.get('aliases', ''),
            source_data.get('author', ''),
            source_data.get('source_type', 'document'),
            pub_date,
            source_data.get('publisher', ''),
            source_data.get('city', ''),
            source_data.get('state', ''),
            source_data.get('country', ''),
            source_data.get('url', ''),
            source_data.get('content', ''),
            source_data.get('file_name', ''),
            import_date,
            source_data.get('review_status', 'needs_review')
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
            UPDATE Sources
            SET Title = ?, Aliases = ?, Author = ?, SourceType = ?, PublicationDate = ?,
                Publisher = ?, City = ?, State = ?, Country = ?, URL = ?,
                Content = ?, FileName = ?, ImportDate = ?, ReviewStatus = ?
            WHERE SourceID = ?
        """
        
        # Format date if provided
        pub_date = source_data.get('publication_date')
        if isinstance(pub_date, datetime):
            pub_date = pub_date.strftime('%Y-%m-%d')
        
        import_date = source_data.get('import_date')
        if isinstance(import_date, datetime):
            import_date = import_date.strftime('%Y-%m-%d')
        
        params = (
            source_data.get('title', ''),
            source_data.get('aliases', ''),
            source_data.get('author', ''),
            source_data.get('source_type', 'document'),
            pub_date,
            source_data.get('publisher', ''),
            source_data.get('city', ''),
            source_data.get('state', ''),
            source_data.get('country', ''),
            source_data.get('url', ''),
            source_data.get('content', ''),
            source_data.get('file_name', ''),
            import_date,
            source_data.get('review_status', 'needs_review'),
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
        query = "DELETE FROM Sources WHERE SourceID = ?"
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
                SELECT COUNT(*) FROM CharacterMentions
                WHERE SourceID = ?
            """, (source_id,))
            character_count = cursor.fetchone()[0]
            
            # Get location mentions
            cursor.execute("""
                SELECT COUNT(*) FROM LocationMentions
                WHERE SourceID = ?
            """, (source_id,))
            location_count = cursor.fetchone()[0]
            
            # Get entity mentions
            cursor.execute("""
                SELECT COUNT(*) FROM EntityMentions
                WHERE SourceID = ?
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
                'query': "DELETE FROM CharacterMentions WHERE SourceID = ?",
                'params': (source_id,)
            },
            {
                'query': "DELETE FROM LocationMentions WHERE SourceID = ?",
                'params': (source_id,)
            },
            {
                'query': "DELETE FROM EntityMentions WHERE SourceID = ?",
                'params': (source_id,)
            },
            {
                'query': "DELETE FROM Sources WHERE SourceID = ?",
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
            SELECT DISTINCT SourceType 
            FROM Sources
            WHERE SourceType IS NOT NULL AND SourceType != ''
            ORDER BY SourceType
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
        query = "SELECT Content FROM Sources WHERE SourceID = ?"
        results = self.execute_query(query, (source_id,))
        
        if results and results[0][0]:
            return results[0][0]
        
        return None
        
    def search_by_alias(self, alias: str) -> List[Tuple]:
        """
        Search for sources by alias.
        
        Args:
            alias: Alias to search for
            
        Returns:
            List of source records
            
        Raises:
            DatabaseError: If query fails
        """