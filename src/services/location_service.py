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
            SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                   Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
            FROM Locations
            ORDER BY DisplayName
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
            column = filter_column.lower()
            # Map UI column names to database column names
            column_mapping = {
                "name": "DisplayName",
                "location_name": "LocationName",
                "aliases": "Aliases",
                "description": "Description",
                "coordinates": "Coordinates",
                "address": "Address",
                "city": "City",
                "state": "State",
                "country": "Country"
            }
            db_column = column_mapping.get(column, column)
            
            query = f"""
                SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                       Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
                FROM Locations
                WHERE {db_column} LIKE ?
                ORDER BY DisplayName
            """
            params = (f"%{search_text}%",)
        else:
            query = """
                SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                       Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
                FROM Locations
                WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ? OR 
                      Description LIKE ? OR Address LIKE ? OR City LIKE ? OR
                      State LIKE ? OR Country LIKE ?
                ORDER BY DisplayName
            """
            params = (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", 
                      f"%{search_text}%", f"%{search_text}%", f"%{search_text}%",
                      f"%{search_text}%", f"%{search_text}%")
        
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
            SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                   Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
            FROM Locations
            WHERE LocationID = ?
        """
        results = self.execute_query(query, (location_id,))
        
        if results:
            return {
                'id': results[0][0],  # Keep 'id' for component compatibility
                'display_name': results[0][1],
                'location_name': results[0][2],
                'aliases': results[0][3],
                'description': results[0][4],
                'coordinates': results[0][5],
                'address': results[0][6],
                'city': results[0][7],
                'state': results[0][8],
                'country': results[0][9],
                'image_file': results[0][10],
                'review_status': results[0][11]
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
            INSERT INTO Locations (DisplayName, LocationName, Aliases, Description, 
                                 Coordinates, Address, City, State, Country, 
                                 ImageFile, ReviewStatus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            location_data.get('display_name', ''),
            location_data.get('location_name', ''),
            location_data.get('aliases', ''),
            location_data.get('description', ''),
            location_data.get('coordinates', ''),
            location_data.get('address', ''),
            location_data.get('city', ''),
            location_data.get('state', ''),
            location_data.get('country', ''),
            location_data.get('image_file', ''),
            location_data.get('review_status', 'needs_review')
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
            UPDATE Locations
            SET DisplayName = ?, LocationName = ?, Aliases = ?, Description = ?,
                Coordinates = ?, Address = ?, City = ?, State = ?, Country = ?,
                ImageFile = ?, ReviewStatus = ?
            WHERE LocationID = ?
        """
        params = (
            location_data.get('display_name', ''),
            location_data.get('location_name', ''),
            location_data.get('aliases', ''),
            location_data.get('description', ''),
            location_data.get('coordinates', ''),
            location_data.get('address', ''),
            location_data.get('city', ''),
            location_data.get('state', ''),
            location_data.get('country', ''),
            location_data.get('image_file', ''),
            location_data.get('review_status', 'needs_review'),
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
        query = "DELETE FROM Locations WHERE LocationID = ?"
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
            SELECT s.Title, COUNT(lm.MentionID)
            FROM LocationMentions lm
            JOIN Sources s ON lm.SourceID = s.SourceID
            WHERE lm.LocationID = ?
            GROUP BY s.Title
            ORDER BY COUNT(lm.MentionID) DESC
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
            SELECT COUNT(*) FROM LocationMentions
            WHERE LocationID = ?
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
                'query': "DELETE FROM LocationMentions WHERE LocationID = ?",
                'params': (location_id,)
            },
            {
                'query': "DELETE FROM Locations WHERE LocationID = ?",
                'params': (location_id,)
            }
        ]
        
        self.execute_transaction(queries)
        return True
    
    def get_events_for_location(self, location_id: int) -> List[Tuple]:
        """
        Get events associated with a location.
        
        Args:
            location_id: ID of the location
            
        Returns:
            List of event records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.Title, e.Description, e.SourceID
            FROM Events e
            JOIN LocationMentions lm ON e.EventID = lm.EventID
            WHERE lm.LocationID = ?
            ORDER BY e.EventDate DESC
        """
        return self.execute_query(query, (location_id,))

    def search_by_alias(self, alias: str) -> List[Tuple]:
        """
        Search for locations by alias.
        
        Args:
            alias: Alias to search for
            
        Returns:
            List of location records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT LocationID, DisplayName, LocationName, Aliases, Description, 
                   Coordinates, Address, City, State, Country, ImageFile, ReviewStatus
            FROM Locations
            WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ?
            ORDER BY DisplayName
        """
        params = (f"%{alias}%", f"%{alias}%", f"%{alias}%")
        
        return self.execute_query(query, params)