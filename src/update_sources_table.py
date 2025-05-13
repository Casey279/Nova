#!/usr/bin/env python3
"""
Script to update the Sources table with additional fields for comprehensive citation support.
This script will add new fields while preserving existing data.
"""

import os
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the database
def find_database():
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_database.db"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nova_database.db"),
        "/mnt/c/AI/Nova/nova_database.db"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"Found database at: {path}")
            return path
    
    # If database not found, ask the user
    db_path = input("Database not found in common locations. Please enter the full path to nova_database.db: ")
    if os.path.exists(db_path):
        return db_path
    else:
        logger.error(f"Database not found at {db_path}")
        return None

def update_sources_table():
    """
    Update the Sources table with additional fields for comprehensive citation support.
    """
    db_path = find_database()
    if db_path is None:
        logger.error("Cannot update table: Database not found")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Begin a transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Get list of existing columns in Sources table
        cursor.execute("PRAGMA table_info(Sources)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Existing columns: {existing_columns}")
        
        # Fields to add - we'll check if they exist first
        new_fields = [
            # Authorship Information
            {"name": "Author", "type": "TEXT"},
            {"name": "Editor", "type": "TEXT"},
            {"name": "Translator", "type": "TEXT"},
            
            # Publication Details
            {"name": "PublicationDate", "type": "TEXT"},
            {"name": "Edition", "type": "TEXT"},
            {"name": "Volume", "type": "TEXT"},
            {"name": "Issue", "type": "TEXT"},
            
            # Location Information (breaking down Location field)
            {"name": "City", "type": "TEXT"},
            {"name": "State", "type": "TEXT"},
            {"name": "Country", "type": "TEXT"},
            
            # Access Information
            {"name": "URL", "type": "TEXT"},
            {"name": "DOI", "type": "TEXT"},
            {"name": "ISBN", "type": "TEXT"},
            {"name": "ISSN", "type": "TEXT"},
            {"name": "FileName", "type": "TEXT"},
            
            # Metadata
            {"name": "ImportDate", "type": "TEXT"},
            {"name": "Content", "type": "TEXT"},
            
            # Newspaper-Specific
            {"name": "LCCN", "type": "TEXT"},
            {"name": "PublicationFrequency", "type": "TEXT"},
            {"name": "Circulation", "type": "TEXT"},
            {"name": "PoliticalAffiliation", "type": "TEXT"},
            {"name": "SourceCode", "type": "TEXT"},
            {"name": "Summary", "type": "TEXT"}
        ]
        
        # Add each field if it doesn't exist
        for field in new_fields:
            if field["name"] not in existing_columns:
                logger.info(f"Adding field {field['name']} ({field['type']})")
                cursor.execute(f"ALTER TABLE Sources ADD COLUMN {field['name']} {field['type']}")
            else:
                logger.info(f"Field {field['name']} already exists")
        
        # Commit the transaction
        conn.commit()
        logger.info("Sources table updated successfully")
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(Sources)")
        updated_columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Updated table now has {len(updated_columns)} columns: {updated_columns}")
        
        # Handle fields that are stored in incorrect places
        # For example, if LCCN is currently stored in Aliases, we might want to migrate it
        
        # Check if we have any LCCNs stored in Aliases field for newspapers
        cursor.execute("SELECT SourceID, Aliases FROM Sources WHERE SourceType = 'newspaper' AND Aliases IS NOT NULL")
        newspaper_sources = cursor.fetchall()
        
        update_count = 0
        for source in newspaper_sources:
            source_id = source[0]
            aliases = source[1]
            
            # Check if this looks like an LCCN in the Aliases field
            if aliases and len(aliases) <= 15 and not aliases.startswith("[") and not "," in aliases:
                # It's probably just an LCCN, migrate it
                logger.info(f"Migrating LCCN {aliases} from Aliases field for SourceID {source_id}")
                cursor.execute("UPDATE Sources SET LCCN = ?, Aliases = NULL WHERE SourceID = ?", 
                               (aliases, source_id))
                update_count += 1
        
        if update_count > 0:
            logger.info(f"Migrated {update_count} LCCNs from Aliases field to LCCN field")
            conn.commit()
        
        return True
            
    except sqlite3.Error as e:
        # Roll back the transaction on error
        if conn:
            conn.rollback()
        logger.error(f"Error updating Sources table: {str(e)}")
        return False
    
    finally:
        # Close the connection
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Updating Sources table with additional fields...")
    success = update_sources_table()
    if success:
        logger.info("Sources table successfully updated with all recommended fields")
    else:
        logger.error("Failed to update Sources table")