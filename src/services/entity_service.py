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
            SELECT id, name, aliases, description, entity_type, start_date, end_date, source 
            FROM entities
            ORDER BY name
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
            query = f"""
                SELECT id, name, aliases, description, entity_type, start_date, end_date, source 
                FROM entities
                WHERE {filter_column.lower()} LIKE ?
                ORDER BY name
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT id, name, aliases, description, entity_type, start_date, end_date, source 
                FROM entities
                WHERE name LIKE ? OR aliases LIKE ? OR description LIKE ? OR 
                      entity_type LIKE ? OR start_date LIKE ? OR end_date LIKE ? OR source LIKE ?
                ORDER BY name
            """
            params = (
                f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", 
                f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", f"%{search_text}%"
            )
        
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
            SELECT id, name, aliases, description, entity_type, start_date, end_date, source 
            FROM entities
            WHERE id = ?
        """
        results = self.execute_query(query, (entity_id,))
        
        if results:
            return {
                'id': results[0][0],
                'name': results[0][1],
                'aliases': results[0][2],
                'description': results[0][3],
                'entity_type': results[0][4],
                'start_date': results[0][5],
                'end_date': results[0][6],
                'source': results[0][7]
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
            INSERT INTO entities (name, aliases, description, entity_type, start_date, end_date, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            entity_data.get('name', ''),
            entity_data.get('aliases', ''),
            entity_data.get('description', ''),
            entity_data.get('entity_type', ''),
            entity_data.get('start_date', ''),
            entity_data.get('end_date', ''),
            entity_data.get('source', '')
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
            UPDATE entities
            SET name = ?, aliases = ?, description = ?, entity_type = ?, 
                start_date = ?, end_date = ?, source = ?
            WHERE id = ?
        """
        params = (
            entity_data.get('name', ''),
            entity_data.get('aliases', ''),
            entity_data.get('description', ''),
            entity_data.get('entity_type', ''),
            entity_data.get('start_date', ''),
            entity_data.get('end_date', ''),
            entity_data.get('source', ''),
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
        query = "DELETE FROM entities WHERE id = ?"
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
            SELECT s.title, COUNT(em.id)
            FROM entity_mentions em
            JOIN sources s ON em.source_id = s.id
            WHERE em.entity_id = ?
            GROUP BY s.title
            ORDER BY COUNT(em.id) DESC
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
            SELECT COUNT(*) FROM entity_mentions
            WHERE entity_id = ?
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
                'query': "DELETE FROM entity_mentions WHERE entity_id = ?",
                'params': (entity_id,)
            },
            {
                'query': "DELETE FROM entities WHERE id = ?",
                'params': (entity_id,)
            }
        ]
        
        self.execute_transaction(queries)
        return True
    
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
            SELECT id, name, aliases, description, entity_type, start_date, end_date, source 
            FROM entities
            WHERE entity_type = ?
            ORDER BY name
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
            SELECT DISTINCT entity_type 
            FROM entities
            ORDER BY entity_type
        """
        results = self.execute_query(query)
        return [result[0] for result in results if result[0]]