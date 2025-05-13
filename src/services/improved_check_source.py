"""
Function to check if a source already exists in the database, with improved URL support.
This function is designed to be included in the ImportService class.
"""

from typing import Optional, Dict, Any

def check_if_source_exists(self, source_name: str, lccn: str = None, sequence: int = None, 
                         issue_date: str = None, external_url: str = None) -> Optional[Dict[str, Any]]:
    """
    Check if a source with the given name and/or URL already exists in the database.
    
    Args:
        source_name: Name of the source to check
        lccn: LCCN identifier (optional)
        sequence: Page sequence number (optional)
        issue_date: Issue date (optional)
        external_url: External URL for the source (optional) - most reliable identifier

    Returns:
        Source data as a dictionary if found, None otherwise
    """
    try:
        # Connect to the database
        conn, cursor = self.connect()
        
        # First try to find by external URL if provided
        if external_url:
            cursor.execute("""
                SELECT SourceID, SourceName, Aliases, ExternalURL
                FROM Sources
                WHERE ExternalURL = ?
            """, (external_url,))
            result = cursor.fetchone()
            
            if result:
                conn.close()
                return {
                    'id': result[0],
                    'name': result[1],
                    'aliases': result[2],
                    'external_url': result[3]
                }
        
        # If URL not found, try by exact source name
        cursor.execute("""
            SELECT SourceID, SourceName, Aliases, ExternalURL
            FROM Sources
            WHERE SourceName = ?
        """, (source_name,))
        result = cursor.fetchone()

        if result:
            conn.close()
            return {
                'id': result[0],
                'name': result[1],
                'aliases': result[2],
                'external_url': result[3] if len(result) > 3 else None
            }

        # If source_name includes sequence number, also try without it (for backward compatibility)
        # Format "Title - Date - Seq N" -> try "Title - Date"
        if " - Seq " in source_name and lccn:
            # Extract title and date part
            base_name = source_name.split(" - Seq ")[0]
            
            # If we have a sequence number and we're checking against old records without URLs,
            # we need to be extremely cautious to avoid false duplicates
            cursor.execute("""
                SELECT SourceID, SourceName, Aliases, ExternalURL 
                FROM Sources 
                WHERE SourceName = ? AND Aliases LIKE ?
            """, (base_name, f"%{lccn}%"))
            
            results = cursor.fetchall()
            
            # For old records without sequence numbers, we need to 
            # check if this exact sequence has already been imported
            if len(results) > 0:
                # Legacy records don't have URLs, so let's check if we've already processed this sequence
                # by counting the number of sources with URLs for this date/lccn
                if sequence is not None:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM Sources 
                        WHERE SourceName LIKE ? AND Aliases LIKE ? AND ExternalURL IS NOT NULL
                    """, (f"{base_name}%", f"%{lccn}%"))
                    
                    url_count = cursor.fetchone()[0]
                    
                    # If we don't have any records with URLs yet, treat it as a new record
                    if url_count == 0:
                        conn.close()
                        return None
                
                # Return the first result as a match
                conn.close()
                return {
                    'id': results[0][0],
                    'name': results[0][1],
                    'aliases': results[0][2],
                    'external_url': results[0][3] if len(results[0]) > 3 else None
                }
        
        conn.close()
        return None
    except Exception as e:
        print(f"Error checking if source exists: {str(e)}")
        return None