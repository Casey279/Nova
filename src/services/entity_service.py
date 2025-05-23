# File: entity_service.py

from typing import List, Dict, Any, Tuple, Optional
from .base_service import BaseService, DatabaseError

class EntityService(BaseService):
    """
    Service for handling entity-related database operations.
    Entities can be events, organizations, or other notable items.
    """
    
    def get_all_entities(self) -> List[Tuple]:
        """
        Get all entities from the database.
        
        Returns:
            List of entity records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT EntityID, DisplayName, Name, Aliases, Type, Description, 
                   EstablishedDate, Affiliation, Summary, ImagePath, KnownMembers
            FROM Entities
            ORDER BY DisplayName
        """
        return self.execute_query(query)
    
    def search_entities(self, search_text: str, filter_column: Optional[str] = None) -> List[Tuple]:
        """
        Search for entities matching the criteria.
        
        Args:
            search_text: Text to search for
            filter_column: Column to search in (None for all columns)
            
        Returns:
            List of matching entity records
            
        Raises:
            DatabaseError: If query fails
        """
        if filter_column and filter_column.lower() != "all":
            column = filter_column.lower()
            # Map UI column names to database column names
            column_mapping = {
                "name": "DisplayName",
                "display_name": "DisplayName",
                "aliases": "Aliases",
                "description": "Description",
                "type": "Type",
                "established_date": "EstablishedDate",
                "affiliation": "Affiliation",
                "summary": "Summary",
                "known_members": "KnownMembers"
            }
            db_column = column_mapping.get(column, column)
            
            query = f"""
                SELECT EntityID, DisplayName, Name, Aliases, Type, Description, 
                       EstablishedDate, Affiliation, Summary, ImagePath, KnownMembers
                FROM Entities
                WHERE {db_column} LIKE ?
                ORDER BY DisplayName
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT EntityID, DisplayName, Name, Aliases, Type, Description, 
                       EstablishedDate, Affiliation, Summary, ImagePath, KnownMembers
                FROM Entities
                WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ? OR 
                      Description LIKE ? OR Type LIKE ? OR 
                      EstablishedDate LIKE ? OR Affiliation LIKE ? OR Summary LIKE ? OR
                      KnownMembers LIKE ?
                ORDER BY DisplayName
            """
            params = (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", 
                     f"%{search_text}%", f"%{search_text}%", f"%{search_text}%",
                     f"%{search_text}%", f"%{search_text}%", f"%{search_text}%")
        
        return self.execute_query(query, params)
    
    def get_entity_by_id(self, entity_id: int) -> Optional[Dict[str, Any]]:
        """
        Get an entity by ID.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            Entity data as a dictionary, or None if not found
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT EntityID, DisplayName, Name, Aliases, Type, Description, 
                   EstablishedDate, Affiliation, Summary, ImagePath, KnownMembers
            FROM Entities
            WHERE EntityID = ?
        """
        results = self.execute_query(query, (entity_id,))
        
        if results:
            return {
                'id': results[0][0],  # Keep 'id' for component compatibility
                'display_name': results[0][1],
                'name': results[0][2],
                'aliases': results[0][3],
                'type': results[0][4],
                'description': results[0][5],
                'established_date': results[0][6],
                'affiliation': results[0][7],
                'summary': results[0][8],
                'image_path': results[0][9],
                'known_members': results[0][10]
            }
        
        return None
    
    def create_entity(self, entity_data: Dict[str, Any]) -> int:
        """
        Create a new entity.
        
        Args:
            entity_data: Dictionary with entity data
            
        Returns:
            ID of the created entity
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            INSERT INTO Entities (DisplayName, Name, Aliases, Type, Description, 
                                EstablishedDate, Affiliation, Summary, ImagePath, KnownMembers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            entity_data.get('display_name', ''),
            entity_data.get('name', ''),
            entity_data.get('aliases', ''),
            entity_data.get('type', ''),
            entity_data.get('description', ''),
            entity_data.get('established_date', ''),
            entity_data.get('affiliation', ''),
            entity_data.get('summary', ''),
            entity_data.get('image_path', ''),
            entity_data.get('known_members', '')
        )
        
        self.execute_update(query, params)
        return self.get_last_insert_id()
    
    def update_entity(self, entity_id: int, entity_data: Dict[str, Any]) -> bool:
        """
        Update an existing entity.
        
        Args:
            entity_id: ID of the entity to update
            entity_data: Dictionary with updated entity data
            
        Returns:
            True if successful, False if entity not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            UPDATE Entities
            SET DisplayName = ?, Name = ?, Aliases = ?, Type = ?, Description = ?, 
                EstablishedDate = ?, Affiliation = ?, Summary = ?, ImagePath = ?, KnownMembers = ?
            WHERE EntityID = ?
        """
        params = (
            entity_data.get('display_name', ''),
            entity_data.get('name', ''),
            entity_data.get('aliases', ''),
            entity_data.get('type', ''),
            entity_data.get('description', ''),
            entity_data.get('established_date', ''),
            entity_data.get('affiliation', ''),
            entity_data.get('summary', ''),
            entity_data.get('image_path', ''),
            entity_data.get('known_members', ''),
            entity_id
        )
        
        rows_affected = self.execute_update(query, params)
        return rows_affected > 0
    
    def delete_entity(self, entity_id: int) -> bool:
        """
        Delete an entity.
        
        Args:
            entity_id: ID of the entity to delete
            
        Returns:
            True if successful, False if entity not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = "DELETE FROM Entities WHERE EntityID = ?"
        rows_affected = self.execute_update(query, (entity_id,))
        return rows_affected > 0
    
    def get_entity_references(self, entity_id: int) -> List[Tuple]:
        """
        Get references to an entity in other tables.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            List of references
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT s.SourceName, COUNT(em.MentionID)
            FROM EntityMentions em
            JOIN Sources s ON em.SourceID = s.SourceID
            WHERE em.EntityID = ?
            GROUP BY s.SourceName
            ORDER BY COUNT(em.MentionID) DESC
        """
        return self.execute_query(query, (entity_id,))
    
    def count_entity_references(self, entity_id: int) -> int:
        """
        Count references to an entity.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            Number of references
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT COUNT(*) FROM EntityMentions
            WHERE EntityID = ?
        """
        result = self.execute_query(query, (entity_id,))
        return result[0][0] if result else 0
    
    def delete_entity_with_references(self, entity_id: int) -> bool:
        """
        Delete an entity and all its references.
        
        Args:
            entity_id: ID of the entity to delete
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If transaction fails
        """
        # Create a transaction to delete the entity and its references
        queries = [
            {
                'query': "DELETE FROM EntityMentions WHERE EntityID = ?",
                'params': (entity_id,)
            },
            {
                'query': "DELETE FROM Entities WHERE EntityID = ?",
                'params': (entity_id,)
            }
        ]
        
        self.execute_transaction(queries)
        return True
    
    def get_events_for_entity(self, entity_id: int) -> List[Tuple]:
        """
        Get events associated with an entity.
        
        Args:
            entity_id: ID of the entity
            
        Returns:
            List of event records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID
            FROM Events e
            JOIN EventEntities ee ON e.EventID = ee.EventID
            WHERE ee.EntityID = ?
            ORDER BY e.EventDate DESC
        """
        return self.execute_query(query, (entity_id,))
    
    def get_entities_by_type(self, entity_type: str) -> List[Tuple]:
        """
        Get entities filtered by type.
        
        Args:
            entity_type: Type of entities to retrieve
            
        Returns:
            List of entity records of the specified type
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT EntityID, DisplayName, Name, Aliases, Type, Description, 
                   EstablishedDate, Affiliation, Summary, ImagePath, KnownMembers
            FROM Entities
            WHERE Type = ?
            ORDER BY DisplayName
        """
        return self.execute_query(query, (entity_type,))
    
    def get_entity_types(self) -> List[str]:
        """
        Get all unique entity types in the database.
        
        Returns:
            List of entity types
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT DISTINCT Type 
            FROM Entities
            WHERE Type IS NOT NULL AND Type != ''
            ORDER BY Type
        """
        results = self.execute_query(query)
        return [result[0] for result in results if result[0]]

    def search_by_alias(self, alias: str) -> List[Tuple]:
        """
        Search for entities by alias.
        
        Args:
            alias: Alias to search for
            
        Returns:
            List of entity records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT EntityID, DisplayName, Name, Aliases, Type, Description, 
                   EstablishedDate, Affiliation, Summary, ImagePath, KnownMembers
            FROM Entities
            WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ?
            ORDER BY DisplayName
        """
        params = (f"%{alias}%", f"%{alias}%", f"%{alias}%")
        
        return self.execute_query(query, params)