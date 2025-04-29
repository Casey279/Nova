# File: event_service.py

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date
from .base_service import BaseService, DatabaseError

class EventService(BaseService):
    """
    Service for handling event-related database operations.
    Events represent historical occurrences linked to characters, locations, and entities.
    """
    
    def get_all_events(self, limit: int = 100, offset: int = 0) -> List[Tuple]:
        """
        Get all events from the database with pagination.
        
        Args:
            limit: Maximum number of events to return
            offset: Number of events to skip
            
        Returns:
            List of event records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
            FROM events e
            LEFT JOIN sources s ON e.SourceID = s.SourceID
            ORDER BY e.EventDate DESC
            LIMIT ? OFFSET ?
        """
        return self.execute_query(query, (limit, offset))
    
    def get_events_count(self) -> int:
        """
        Get the total number of events in the database.
        
        Returns:
            Total number of events
            
        Raises:
            DatabaseError: If query fails
        """
        query = "SELECT COUNT(*) FROM events"
        result = self.execute_query(query)
        return result[0][0] if result else 0
    
    def search_events_by_date(self, start_date: Optional[str] = None, 
                             end_date: Optional[str] = None, 
                             limit: int = 100, 
                             offset: int = 0) -> List[Tuple]:
        """
        Search for events by date range.
        
        Args:
            start_date: Start date (inclusive, format: YYYY-MM-DD)
            end_date: End date (inclusive, format: YYYY-MM-DD)
            limit: Maximum number of events to return
            offset: Number of events to skip
            
        Returns:
            List of matching event records
            
        Raises:
            DatabaseError: If query fails
        """
        if start_date and end_date:
            query = """
                SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
                FROM events e
                LEFT JOIN sources s ON e.SourceID = s.SourceID
                WHERE e.EventDate BETWEEN ? AND ?
                ORDER BY e.EventDate DESC
                LIMIT ? OFFSET ?
            """
            params = (start_date, end_date, limit, offset)
        elif start_date:
            query = """
                SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
                FROM events e
                LEFT JOIN sources s ON e.SourceID = s.SourceID
                WHERE e.EventDate >= ?
                ORDER BY e.EventDate DESC
                LIMIT ? OFFSET ?
            """
            params = (start_date, limit, offset)
        elif end_date:
            query = """
                SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
                FROM events e
                LEFT JOIN sources s ON e.SourceID = s.SourceID
                WHERE e.EventDate <= ?
                ORDER BY e.EventDate DESC
                LIMIT ? OFFSET ?
            """
            params = (end_date, limit, offset)
        else:
            return self.get_all_events(limit, offset)
        
        return self.execute_query(query, params)
    
    def search_events_by_text(self, search_text: str, 
                             limit: int = 100, 
                             offset: int = 0) -> List[Tuple]:
        """
        Search for events by text in title or description.
        
        Args:
            search_text: Text to search for
            limit: Maximum number of events to return
            offset: Number of events to skip
            
        Returns:
            List of matching event records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
            FROM events e
            LEFT JOIN sources s ON e.SourceID = s.SourceID
            WHERE e.EventTitle LIKE ? OR e.EventText LIKE ?
            ORDER BY e.EventDate DESC
            LIMIT ? OFFSET ?
        """
        search_pattern = f"%{search_text}%"
        params = (search_pattern, search_pattern, limit, offset)
        
        return self.execute_query(query, params)
    
    def get_event_by_id(self, event_id: int) -> Optional[Dict[str, Any]]:
        """
        Get an event by ID.
        
        Args:
            event_id: ID of the event
            
        Returns:
            Event data as a dictionary, or None if not found
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, 
                   e.SourceID, s.SourceName as source_title,
                   e.page_number, e.confidence, e.verified
            FROM events e
            LEFT JOIN sources s ON e.SourceID = s.SourceID
            WHERE e.EventID = ?
        """
        results = self.execute_query(query, (event_id,))
        
        if not results:
            return None
        
        event_data = {
            'id': results[0][0],
            'event_date': results[0][1],
            'title': results[0][2],
            'description': results[0][3],
            'source_id': results[0][4],
            'source_title': results[0][5],
            'page_number': results[0][6],
            'confidence': results[0][7],
            'verified': bool(results[0][8])
        }
        
        # Get associated entities
        event_data['characters'] = self.get_event_characters(event_id)
        event_data['locations'] = self.get_event_locations(event_id)
        event_data['entities'] = self.get_event_entities(event_id)
        
        return event_data
    

    def get_events_character(self, character_id: int) -> List[Tuple]:
        """
        Get all events associated with a character.
        
        Args:
            character_id: ID of the character
            
        Returns:
            List of event records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText
            FROM Events e
            JOIN EventCharacters ec ON e.EventID = ec.EventID
            WHERE ec.CharacterID = ?
            ORDER BY e.EventDate
        """
        return self.execute_query(query, (character_id,))
    
    def get_event_locations(self, event_id: int) -> List[Dict[str, Any]]:
        """
        Get locations associated with an event.
        
        Args:
            event_id: ID of the event
            
        Returns:
            List of location data
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT l.id, l.name, lm.context, lm.id as mention_id
            FROM location_mentions lm
            JOIN locations l ON lm.location_id = l.id
            WHERE lm.event_id = ?
            ORDER BY l.name
        """
        results = self.execute_query(query, (event_id,))
        
        locations = []
        for row in results:
            locations.append({
                'id': row[0],
                'name': row[1],
                'context': row[2],
                'mention_id': row[3]
            })
        
        return locations
    
    def get_event_entities(self, event_id: int) -> List[Dict[str, Any]]:
        """
        Get entities associated with an event.
        
        Args:
            event_id: ID of the event
            
        Returns:
            List of entity data
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.name, e.entity_type, em.context, em.id as mention_id
            FROM entity_mentions em
            JOIN entities e ON em.entity_id = e.EventID
            WHERE em.event_id = ?
            ORDER BY e.name
        """
        results = self.execute_query(query, (event_id,))
        
        entities = []
        for row in results:
            entities.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'context': row[3],
                'mention_id': row[4]
            })
        
        return entities
    
    def get_events_by_date(self, event_date: str) -> List[Tuple]:
        """
        Get events for a specific date.
        
        Args:
            event_date: Date string (format: YYYY-MM-DD)
            
        Returns:
            List of event records
            
        Raises:
            DatabaseError: If query fails
        """
        query = """
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
            FROM events e
            LEFT JOIN sources s ON e.SourceID = s.SourceID
            WHERE e.EventDate = ?
            ORDER BY e.EventTitle
        """
        return self.execute_query(query, (event_date,))
    
    def get_events_for_character(self, character_id: int) -> List[Tuple]:
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
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
            FROM events e
            JOIN character_mentions cm ON e.EventID = cm.event_id
            LEFT JOIN sources s ON e.SourceID = s.SourceID
            WHERE cm.character_id = ?
            ORDER BY e.EventDate DESC
        """
        return self.execute_query(query, (character_id,))
    
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
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
            FROM events e
            JOIN location_mentions lm ON e.EventID = lm.event_id
            LEFT JOIN sources s ON e.SourceID = s.SourceID
            WHERE lm.location_id = ?
            ORDER BY e.EventDate DESC
        """
        return self.execute_query(query, (location_id,))
    
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
            SELECT e.EventID, e.EventDate, e.EventTitle, e.EventText, e.SourceID, s.SourceName as source_title 
            FROM events e
            JOIN entity_mentions em ON e.EventID = em.event_id
            LEFT JOIN sources s ON e.SourceID = s.SourceID
            WHERE em.entity_id = ?
            ORDER BY e.EventDate DESC
        """
        return self.execute_query(query, (entity_id,))