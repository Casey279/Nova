# File: character_service.py

from typing import List, Dict, Any, Tuple, Optional
from .base_service import BaseService, DatabaseError

class CharacterService(BaseService):
    """
    Service for handling character-related database operations.
    """
    
    def get_all_characters(self) -> List[Tuple]:
        """
        Get all characters from the database.
        
        Returns:
            List of character records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT id, name, aliases, description, source 
            FROM characters
            ORDER BY name
        """
        return self.execute_query(query)
    
    def search_characters(self, search_text: str, filter_column: Optional[str] = None) -> List[Tuple]:
        """
        Search for characters matching the criteria.
        
        Args:
            search_text: Text to search for
            filter_column: Column to search in (None for all columns)
            
        Returns:
            List of matching character records
            
        Raises:
            DatabaseError: If query fails
        """
        if filter_column and filter_column.lower() != "all":
            query = f"""
                SELECT id, name, aliases, description, source 
                FROM characters
                WHERE {filter_column.lower()} LIKE ?
                ORDER BY name
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT id, name, aliases, description, source 
                FROM characters
                WHERE name LIKE ? OR aliases LIKE ? OR description LIKE ? OR source LIKE ?
                ORDER BY name
            """
            params = (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", f"%{search_text}%")
        
        return self.execute_query(query, params)
    
    def get_character_by_id(self, character_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a character by ID.
        
        Args:
            character_id: ID of the character
            
        Returns:
            Character data as a dictionary, or None if not found
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT id, name, aliases, description, source 
            FROM characters
            WHERE id = ?
        """
        results = self.execute_query(query, (character_id,))
        
        if results:
            return {
                'id': results[0][0],
                'name': results[0][1],
                'aliases': results[0][2],
                'description': results[0][3],
                'source': results[0][4]
            }
        
        return None
    
    def create_character(self, character_data: Dict[str, Any]) -> int:
        """
        Create a new character.
        
        Args:
            character_data: Dictionary with character data
            
        Returns:
            ID of the created character
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            INSERT INTO characters (name, aliases, description, source)
            VALUES (?, ?, ?, ?)
        """
        params = (
            character_data.get('name', ''),
            character_data.get('aliases', ''),
            character_data.get('description', ''),
            character_data.get('source', '')
        )
        
        self.execute_update(query, params)
        return self.get_last_insert_id()
    
    def update_character(self, character_id: int, character_data: Dict[str, Any]) -> bool:
        """
        Update an existing character.
        
        Args:
            character_id: ID of the character to update
            character_data: Dictionary with updated character data
            
        Returns:
            True if successful, False if character not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            UPDATE characters
            SET name = ?, aliases = ?, description = ?, source = ?
            WHERE id = ?
        """
        params = (
            character_data.get('name', ''),
            character_data.get('aliases', ''),
            character_data.get('description', ''),
            character_data.get('source', ''),
            character_id
        )
        
        rows_affected = self.execute_update(query, params)
        return rows_affected > 0
    
    def delete_character(self, character_id: int) -> bool:
        """
        Delete a character.
        
        Args:
            character_id: ID of the character to delete
            
        Returns:
            True if successful, False if character not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = "DELETE FROM characters WHERE id = ?"
        rows_affected = self.execute_update(query, (character_id,))
        return rows_affected > 0
    
    def get_character_references(self, character_id: int) -> List[Tuple]:
        """
        Get references to a character in other tables.
        
        Args:
            character_id: ID of the character
            
        Returns:
            List of references
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT s.title, COUNT(cm.id)
            FROM character_mentions cm
            JOIN sources s ON cm.source_id = s.id
            WHERE cm.character_id = ?
            GROUP BY s.title
            ORDER BY COUNT(cm.id) DESC
        """
        return self.execute_query(query, (character_id,))
    
    def count_character_references(self, character_id: int) -> int:
        """
        Count references to a character.
        
        Args:
            character_id: ID of the character
            
        Returns:
            Number of references
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT COUNT(*) FROM character_mentions
            WHERE character_id = ?
        """
        result = self.execute_query(query, (character_id,))
        return result[0][0] if result else 0
    
    def delete_character_with_references(self, character_id: int) -> bool:
        """
        Delete a character and all its references.
        
        Args:
            character_id: ID of the character to delete
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If transaction fails
        """
        # Create a transaction to delete the character and its references
        queries = [
            {
                'query': "DELETE FROM character_mentions WHERE character_id = ?",
                'params': (character_id,)
            },
            {
                'query': "DELETE FROM characters WHERE id = ?",
                'params': (character_id,)
            }
        ]
        
        self.execute_transaction(queries)
        return True