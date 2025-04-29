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
            SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName, 
                   Title, Suffix, Aliases, Description, ImageFile, Reviewed
            FROM Characters
            ORDER BY DisplayName
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
            column = filter_column.lower()
            # Map UI column names to database column names
            column_mapping = {
                "name": "DisplayName",
                "aliases": "Aliases",
                "description": "Description"
                # Add more mappings as needed
            }
            db_column = column_mapping.get(column, column)
            
            query = f"""
                SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName, 
                       Title, Suffix, Aliases, Description, ImageFile, Reviewed
                FROM Characters
                WHERE {db_column} LIKE ?
                ORDER BY DisplayName
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName, 
                       Title, Suffix, Aliases, Description, ImageFile, Reviewed
                FROM Characters
                WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR 
                      MiddleName LIKE ? OR Aliases LIKE ? OR Description LIKE ?
                ORDER BY DisplayName
            """
            params = (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", 
                     f"%{search_text}%", f"%{search_text}%", f"%{search_text}%")
        
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
            SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName,
                   Title, Suffix, Aliases, Description, ImageFile, Reviewed
            FROM Characters
            WHERE CharacterID = ?
        """
        results = self.execute_query(query, (character_id,))
        
        if results:
            return {
                'id': results[0][0],  # Keep 'id' for component compatibility
                'display_name': results[0][1],
                'first_name': results[0][2],
                'middle_name': results[0][3],
                'last_name': results[0][4],
                'title': results[0][5],
                'suffix': results[0][6],
                'aliases': results[0][7],
                'description': results[0][8],
                'image_file': results[0][9],
                'reviewed': results[0][10]
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
            INSERT INTO Characters (DisplayName, FirstName, MiddleName, LastName,
                                  Title, Suffix, Aliases, Description, ImageFile, Reviewed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            character_data.get('display_name', ''),
            character_data.get('first_name', ''),
            character_data.get('middle_name', ''),
            character_data.get('last_name', ''),
            character_data.get('title', ''),
            character_data.get('suffix', ''),
            character_data.get('aliases', ''),
            character_data.get('description', ''),
            character_data.get('image_file', ''),
            character_data.get('reviewed', 0)
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
            UPDATE Characters
            SET DisplayName = ?, FirstName = ?, MiddleName = ?, LastName = ?,
                Title = ?, Suffix = ?, Aliases = ?, Description = ?, ImageFile = ?, Reviewed = ?
            WHERE CharacterID = ?
        """
        params = (
            character_data.get('display_name', ''),
            character_data.get('first_name', ''),
            character_data.get('middle_name', ''),
            character_data.get('last_name', ''),
            character_data.get('title', ''),
            character_data.get('suffix', ''),
            character_data.get('aliases', ''),
            character_data.get('description', ''),
            character_data.get('image_file', ''),
            character_data.get('reviewed', 0),
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
        query = "DELETE FROM Characters WHERE CharacterID = ?"
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
            SELECT s.Title, COUNT(cm.MentionID)
            FROM CharacterMentions cm
            JOIN Sources s ON cm.SourceID = s.SourceID
            WHERE cm.CharacterID = ?
            GROUP BY s.Title
            ORDER BY COUNT(cm.MentionID) DESC
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
            SELECT COUNT(*) FROM CharacterMentions
            WHERE CharacterID = ?
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
                'query': "DELETE FROM CharacterMentions WHERE CharacterID = ?",
                'params': (character_id,)
            },
            {
                'query': "DELETE FROM Characters WHERE CharacterID = ?",
                'params': (character_id,)
            }
        ]
        
        self.execute_transaction(queries)
        return True
    
    def get_character_events(self, character_id: int) -> List[Tuple]:
        """
        Get events associated with a character.
        
        Args:
            character_id: ID of the character
            
        Returns:
            List of event records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.Title, e.Description, e.SourceID
            FROM Events e
            JOIN CharacterMentions cm ON e.EventID = cm.EventID
            WHERE cm.CharacterID = ?
            ORDER BY e.EventDate DESC
        """
        return self.execute_query(query, (character_id,))

    def search_by_alias(self, alias: str) -> List[Tuple]:
        """
        Search for characters by alias.
        
        Args:
            alias: Alias to search for
            
        Returns:
            List of character records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT CharacterID, DisplayName, FirstName, MiddleName, LastName,
                   Title, Suffix, Aliases, Description, ImageFile, Reviewed
            FROM Characters
            WHERE DisplayName LIKE ? OR Aliases LIKE ?
            ORDER BY DisplayName
        """
        params = (f"%{alias}%", f"%{alias}%")
        
        return self.execute_query(query, params)