# File: character_service.py

import sqlite3
from typing import List, Dict, Any, Optional, Tuple

class CharacterService:
    """Service for managing character data in the database."""
    
    def __init__(self, db_path: str):
        """Initialize with database path."""
        self.db_path = db_path
    
    def _get_connection(self) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
        """Get a database connection and cursor."""
        conn = sqlite3.connect(self.db_path)
        # Enable foreign keys support
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        return conn, cursor
    
    def _cursor_to_dict(self, cursor, row) -> Dict:
        """Convert a database row to a dictionary."""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    
    def get_all_characters(self) -> List[Dict[str, Any]]:
        """Get all characters from the database."""
        conn, cursor = self._get_connection()
        try:
            conn.row_factory = self._cursor_to_dict
            cursor = conn.cursor()
            cursor.execute("""
                SELECT CharacterID, DisplayName, FirstName, LastName, Reviewed
                FROM Characters 
                ORDER BY DisplayName
            """)
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise Exception(f"Failed to get characters: {str(e)}")
        finally:
            conn.close()
    
    def get_characters_by_level(self, level: str) -> List[Dict[str, Any]]:
        """Get characters by hierarchy level."""
        level_tables = {
            "Primary": "PrimaryCharacters",
            "Secondary": "SecondaryCharacters",
            "Tertiary": "TertiaryCharacters",
            "Quaternary": "QuaternaryCharacters"
        }
        
        if level not in level_tables:
            raise ValueError(f"Invalid level: {level}")
        
        table = level_tables[level]
        conn, cursor = self._get_connection()
        try:
            conn.row_factory = self._cursor_to_dict
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT c.CharacterID, c.DisplayName, c.FirstName, c.LastName, c.Reviewed
                FROM Characters c
                JOIN {table} h ON c.CharacterID = h.CharacterID
                ORDER BY c.DisplayName
            """)
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise Exception(f"Failed to get {level} characters: {str(e)}")
        finally:
            conn.close()
    
    def get_character_by_id(self, character_id: int) -> Optional[Dict[str, Any]]:
        """Get character by ID."""
        conn, cursor = self._get_connection()
        try:
            conn.row_factory = self._cursor_to_dict
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM Characters WHERE CharacterID = ?
            """, (character_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            raise Exception(f"Failed to get character {character_id}: {str(e)}")
        finally:
            conn.close()
    
    def add_character(self, character_data: Dict[str, Any]) -> int:
        """Add a new character to the database."""
        conn, cursor = self._get_connection()
        try:
            # Construct column names and placeholders dynamically
            columns = []
            placeholders = []
            values = []
            
            for column, value in character_data.items():
                if value is not None:  # Only include non-None values
                    columns.append(column)
                    placeholders.append('?')
                    values.append(value)
            
            query = f"""
                INSERT INTO Characters ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """
            
            cursor.execute(query, values)
            
            # Add to Tertiary level by default
            new_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO TertiaryCharacters (CharacterID)
                VALUES (?)
            """, (new_id,))
            
            conn.commit()
            return new_id
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Failed to add character: {str(e)}")
        finally:
            conn.close()
    
    def update_character(self, character_id: int, character_data: Dict[str, Any]) -> bool:
        """Update an existing character."""
        conn, cursor = self._get_connection()
        try:
            # Construct SET clause dynamically
            set_clause = []
            values = []
            
            for column, value in character_data.items():
                if column != 'CharacterID':  # Skip ID field
                    set_clause.append(f"{column} = ?")
                    values.append(value)
            
            # Add ID to values
            values.append(character_id)
            
            query = f"""
                UPDATE Characters
                SET {', '.join(set_clause)}
                WHERE CharacterID = ?
            """
            
            cursor.execute(query, values)
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Failed to update character {character_id}: {str(e)}")
        finally:
            conn.close()
    
    def delete_character(self, character_id: int) -> bool:
        """Delete a character from the database."""
        conn, cursor = self._get_connection()
        try:
            # Delete character's associations
            cursor.execute("""
                DELETE FROM EventCharacters WHERE CharacterID = ?
            """, (character_id,))
            
            # Delete from hierarchy tables
            hierarchy_tables = [
                "PrimaryCharacters", "SecondaryCharacters", 
                "TertiaryCharacters", "QuaternaryCharacters"
            ]
            
            for table in hierarchy_tables:
                cursor.execute(f"""
                    DELETE FROM {table} WHERE CharacterID = ?
                """, (character_id,))
            
            # Delete the character
            cursor.execute("""
                DELETE FROM Characters WHERE CharacterID = ?
            """, (character_id,))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Failed to delete character {character_id}: {str(e)}")
        finally:
            conn.close()
    
    def mark_character_reviewed(self, character_id: int) -> bool:
        """Mark a character as reviewed."""
        conn, cursor = self._get_connection()
        try:
            cursor.execute("""
                UPDATE Characters
                SET Reviewed = 1
                WHERE CharacterID = ?
            """, (character_id,))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Failed to mark character {character_id} as reviewed: {str(e)}")
        finally:
            conn.close()
    
    def get_character_level(self, character_id: int) -> str:
        """Get the hierarchy level for a specific character."""
        conn, cursor = self._get_connection()
        try:
            levels = {
                "PrimaryCharacters": "Primary",
                "SecondaryCharacters": "Secondary",
                "TertiaryCharacters": "Tertiary",
                "QuaternaryCharacters": "Quaternary"
            }
            
            for table, level in levels.items():
                cursor.execute(f"""
                    SELECT 1 FROM {table} WHERE CharacterID = ?
                """, (character_id,))
                
                if cursor.fetchone():
                    return level
            
            return "Tertiary"  # Default level
        except sqlite3.Error as e:
            raise Exception(f"Failed to get character level for {character_id}: {str(e)}")
        finally:
            conn.close()
    
    def set_character_level(self, character_id: int, level: str) -> bool:
        """Set the hierarchy level for a character."""
        conn, cursor = self._get_connection()
        try:
            levels = {
                "Primary": "PrimaryCharacters",
                "Secondary": "SecondaryCharacters",
                "Tertiary": "TertiaryCharacters",
                "Quaternary": "QuaternaryCharacters"
            }
            
            if level not in levels:
                raise ValueError(f"Invalid level: {level}")
            
            new_table = levels[level]
            
            # Remove from all hierarchy tables
            for table in levels.values():
                cursor.execute(f"""
                    DELETE FROM {table} WHERE CharacterID = ?
                """, (character_id,))
            
            # Add to new hierarchy table
            cursor.execute(f"""
                INSERT INTO {new_table} (CharacterID) VALUES (?)
            """, (character_id,))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Failed to set character {character_id} to {level} level: {str(e)}")
        finally:
            conn.close()
    
    def get_associated_articles(self, character_id: int) -> List[Dict[str, Any]]:
        """Get articles associated with a character."""
        conn, cursor = self._get_connection()
        try:
            conn.row_factory = self._cursor_to_dict
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.EventID, e.EventDate, e.PublicationDate, e.EventTitle, e.EventText
                FROM Events e
                JOIN EventCharacters ec ON e.EventID = ec.EventID
                WHERE ec.CharacterID = ?
                ORDER BY e.EventDate DESC
            """, (character_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise Exception(f"Failed to get associated articles for character {character_id}: {str(e)}")
        finally:
            conn.close()
    
    def get_articles_by_character_and_date(self, character_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get articles for a character filtered by date range."""
        conn, cursor = self._get_connection()
        try:
            conn.row_factory = self._cursor_to_dict
            cursor = conn.cursor()
            
            query = """
                SELECT e.EventID, e.EventDate, e.PublicationDate, e.EventTitle, e.EventText
                FROM Events e
                JOIN EventCharacters ec ON e.EventID = ec.EventID
                WHERE ec.CharacterID = ?
            """
            params = [character_id]
            
            if start_date:
                query += " AND e.EventDate >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND e.EventDate <= ?"
                params.append(end_date)
            
            query += " ORDER BY e.EventDate DESC"
            
            cursor.execute(query, params)
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise Exception(f"Failed to get filtered articles for character {character_id}: {str(e)}")
        finally:
            conn.close()
    
    def update_character_image(self, character_id: int, image_path: str) -> bool:
        """Update a character's image path."""
        conn, cursor = self._get_connection()
        try:
            cursor.execute("""
                UPDATE Characters
                SET ImagePath = ?
                WHERE CharacterID = ?
            """, (image_path, character_id))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Failed to update image for character {character_id}: {str(e)}")
        finally:
            conn.close()
    
    def search_characters(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for characters by name or alias."""
        conn, cursor = self._get_connection()
        try:
            search_pattern = f"%{search_term}%"
            conn.row_factory = self._cursor_to_dict
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT CharacterID, DisplayName, FirstName, LastName, Reviewed
                FROM Characters
                WHERE DisplayName LIKE ? 
                   OR FirstName LIKE ? 
                   OR LastName LIKE ? 
                   OR Aliases LIKE ?
                ORDER BY DisplayName
            """, (search_pattern, search_pattern, search_pattern, search_pattern))
            
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise Exception(f"Failed to search characters: {str(e)}")
        finally:
            conn.close()