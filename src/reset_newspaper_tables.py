#!/usr/bin/env python3
"""
Script to completely reset the Sources and NewspaperPages tables,
including resetting the primary key sequences to start from 1.
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

def reset_tables():
    """
    Reset the Sources, NewspaperPages, and table_sources tables.

    This function:
    1. Deletes all newspaper-related records from Sources and NewspaperPages
    2. Deletes all records from table_sources
    3. Resets the primary key sequences so new records start from ID 1
    4. Backs up the existing records (number only) for verification
    """
    db_path = find_database()
    if db_path is None:
        logger.error("Cannot reset tables: Database not found")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Begin a transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Back up record counts for verification
        cursor.execute("SELECT COUNT(*) FROM Sources WHERE SourceType = 'newspaper'")
        sources_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM NewspaperPages")
        pages_count = cursor.fetchone()[0]
        
        logger.info(f"Before reset: Found {sources_count} newspaper sources and {pages_count} newspaper pages")
        
        # Delete all records from NewspaperPages
        cursor.execute("DELETE FROM NewspaperPages")
        logger.info(f"Deleted all {pages_count} records from NewspaperPages table")
        
        # Delete all newspaper records from Sources
        cursor.execute("DELETE FROM Sources WHERE SourceType = 'newspaper'")
        logger.info(f"Deleted all {sources_count} newspaper records from Sources table")

        # Check if table_sources exists and reset it too
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='table_sources'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM table_sources")
            table_sources_count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM table_sources")
            logger.info(f"Deleted all {table_sources_count} records from table_sources")
        else:
            logger.info("table_sources not found, skipping")

        # Reset the autoincrement counters by using SQLite's VACUUM and recreating the tables
        # First, get the table creation SQL
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='Sources'")
        sources_sql = cursor.fetchone()[0]

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='NewspaperPages'")
        pages_sql = cursor.fetchone()[0]

        # Get table_sources SQL if it exists
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='table_sources'")
        table_sources_sql_result = cursor.fetchone()
        table_sources_sql = table_sources_sql_result[0] if table_sources_sql_result else None

        # Drop the tables
        cursor.execute("DROP TABLE IF EXISTS NewspaperPages")
        cursor.execute("DROP TABLE IF EXISTS Sources")
        if table_sources_sql:
            cursor.execute("DROP TABLE IF EXISTS table_sources")

        # Recreate the tables using the original SQL (this resets the autoincrement)
        cursor.execute(sources_sql)
        cursor.execute(pages_sql)
        if table_sources_sql:
            cursor.execute(table_sources_sql)
        
        # Commit the transaction
        conn.commit()
        
        # Verify that tables are empty and primary keys are reset
        cursor.execute("SELECT COUNT(*) FROM Sources")
        new_sources_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM NewspaperPages")
        new_pages_count = cursor.fetchone()[0]

        # Check table_sources count if it exists
        table_sources_count = 0
        if table_sources_sql:
            cursor.execute("SELECT COUNT(*) FROM table_sources")
            table_sources_count = cursor.fetchone()[0]
            logger.info(f"After reset: {new_sources_count} sources, {new_pages_count} pages, {table_sources_count} table_sources entries")
        else:
            logger.info(f"After reset: {new_sources_count} sources and {new_pages_count} pages")

        # Check if tables are properly reset
        tables_empty = (new_sources_count == 0 and new_pages_count == 0)
        if table_sources_sql:
            tables_empty = tables_empty and (table_sources_count == 0)

        if tables_empty:
            logger.info("Tables successfully reset with primary keys starting from 1")
            return True
        else:
            logger.warning("Tables reset but may not be empty. Check database manually.")
            return False
            
    except sqlite3.Error as e:
        # Roll back the transaction on error
        if conn:
            conn.rollback()
        logger.error(f"Error resetting tables: {str(e)}")
        return False
    
    finally:
        # Close the connection
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Resetting newspaper tables...")
    success = reset_tables()
    if success:
        logger.info("Tables reset successfully. Primary keys will start from 1.")
        logger.info("You can now re-import your newspaper pages.")
    else:
        logger.error("Failed to reset tables.")