# File: location_service.py

from typing import List, Dict, Any, Tuple, Optional
from .base_service import BaseService, DatabaseError

class LocationService(BaseService):
    """
    Service for handling location-related database operations.
    """
    
    def get_all_locations(self) -> List[Tuple]:
        """
        Get all locations from the database.
        
        Returns:
            List of location records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT id, name, aliases, description, coordinates, source 
            FROM locations
            ORDER BY name
        """
        return self.execute_query(query)
    
    def search_locations(self, search_text: str, filter_column: Optional[str] = None) -> List[Tuple]:
        """
        Search for locations matching the criteria.
        
        Args:
            search_text: Text to search for
            filter_column: Column to search in (None for all columns)
            
        Returns:
            List of matching location records
            
        Raises:
            DatabaseError: If query fails
        """
        if filter_column and filter_column.lower() != "all":
            query = f"""
                SELECT id, name, aliases, description, coordinates, source 
                FROM locations
                WHERE {filter_column.lower()} LIKE ?
                ORDER BY name
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT id, name, aliases, description, coordinates, source 
                FROM locations
                WHERE name LIKE ? OR aliases LIKE ? OR description LIKE ? OR coordinates LIKE ? OR source LIKE ?
                ORDER BY name
            """
            params = (
                f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", 
                f"%{search_text}%", f"%{search_text}%"
            )
        
        return self.execute_query(query, params)
    
    def get_location_by_id(self, location_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a location by ID.
        
        Args:
            location_id: ID of the location
            
        Returns:
            Location data as a dictionary, or None if not found
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT id, name, aliases, description, coordinates, source 
            FROM locations
            WHERE id = ?
        """
        results = self.execute_query(query, (location_id,))
        
        if results:
            return {
                'id': results[0][0],
                'name': results[0][1],
                'aliases': results[0][2],
                'description': results[0][3],
                'coordinates': results[0][4],
                'source': results[0][5]
            }
        
        return None
    
    def create_location(self, location_data: Dict[str, Any]) -> int:
        """
        Create a new location.
        
        Args:
            location_data: Dictionary with location data
            
        Returns:
            ID of the created location
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            INSERT INTO locations (name, aliases, description, coordinates, source)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            location_data.get('name', ''),
            location_data.get('aliases', ''),
            location_data.get('description', ''),
            location_data.get('coordinates', ''),
            location_data.get('source', '')
        )
        
        self.execute_update(query, params)
        return self.get_last_insert_id()
    
    def update_location(self, location_id: int, location_data: Dict[str, Any]) -> bool:
        """
        Update an existing location.
        
        Args:
            location_id: ID of the location to update
            location_data: Dictionary with updated location data
            
        Returns:
            True if successful, False if location not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = """
            UPDATE locations
            SET name = ?, aliases = ?, description = ?, coordinates = ?, source = ?
            WHERE id = ?
        """
        params = (
            location_data.get('name', ''),
            location_data.get('aliases', ''),
            location_data.get('description', ''),
            location_data.get('coordinates', ''),
            location_data.get('source', ''),
            location_id
        )
        
        rows_affected = self.execute_update(query, params)
        return rows_affected > 0
    
    def delete_location(self, location_id: int) -> bool:
        """
        Delete a location.
        
        Args:
            location_id: ID of the location to delete
            
        Returns:
            True if successful, False if location not found
            
        Raises:
            DatabaseError: If operation fails
        """
        query = "DELETE FROM locations WHERE id = ?"
        rows_affected = self.execute_update(query, (location_id,))
        return rows_affected > 0
    
    def get_location_references(self, location_id: int) -> List[Tuple]:
        """
        Get references to a location in other tables.
        
        Args:
            location_id: ID of the location
            
        Returns:
            List of references
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT s.title, COUNT(lm.id)
            FROM location_mentions lm
            JOIN sources s ON lm.source_id = s.id
            WHERE lm.location_id = ?
            GROUP BY s.title
            ORDER BY COUNT(lm.id) DESC
        """
        return self.execute_query(query, (location_id,))
    
    def count_location_references(self, location_id: int) -> int:
        """
        Count references to a location.
        
        Args:
            location_id: ID of the location
            
        Returns:
            Number of references
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT COUNT(*) FROM location_mentions
            WHERE location_id = ?
        """
        result = self.execute_query(query, (location_id,))
        return result[0][0] if result else 0
    
    def delete_location_with_references(self, location_id: int) -> bool:
        """
        Delete a location and all its references.
        
        Args:
            location_id: ID of the location to delete
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If transaction fails
        """
        # Create a transaction to delete the location and its references
        queries = [
            {
                'query': "DELETE FROM location_mentions WHERE location_id = ?",
                'params': (location_id,)
            },
            {
                'query': "DELETE FROM locations WHERE id = ?",
                'params': (location_id,)
            }
        ]
        
        self.execute_transaction(queries)
        return True