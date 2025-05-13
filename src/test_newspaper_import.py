#!/usr/bin/env python3
"""
Simple test script to verify that our newspaper import code is working correctly.
Uses a direct database connection to check the database after a small test import.
"""

import os
import sqlite3

# Path to the database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_database.db")

def check_db_status():
    """Check the current state of the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check Sources table
    cursor.execute("SELECT COUNT(*) FROM Sources")
    source_count = cursor.fetchone()[0]
    print(f"Sources table has {source_count} total records")
    
    # Check for sources with LCCN sn83045604
    cursor.execute("SELECT COUNT(*) FROM Sources WHERE Aliases = ? OR Aliases LIKE ?", 
                  ('sn83045604', '%sn83045604%'))
    pi_sources = cursor.fetchone()[0]
    print(f"Sources table has {pi_sources} record(s) with LCCN sn83045604")
    
    # Check if NewspaperPages table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='NewspaperPages'")
    np_exists = cursor.fetchone() is not None
    
    if np_exists:
        # Check NewspaperPages table
        cursor.execute("SELECT COUNT(*) FROM NewspaperPages")
        page_count = cursor.fetchone()[0]
        print(f"NewspaperPages table has {page_count} total records")
        
        # Check for pages with LCCN sn83045604
        cursor.execute("SELECT COUNT(*) FROM NewspaperPages WHERE LCCN = ?", ('sn83045604',))
        pi_pages = cursor.fetchone()[0]
        print(f"NewspaperPages table has {pi_pages} record(s) with LCCN sn83045604")
        
        # Get some example pages
        if pi_pages > 0:
            cursor.execute("""
                SELECT np.PageID, np.IssueDate, np.Sequence, s.SourceName
                FROM NewspaperPages np
                JOIN Sources s ON np.SourceID = s.SourceID
                WHERE np.LCCN = ?
                ORDER BY np.IssueDate, np.Sequence
                LIMIT 5
            """, ('sn83045604',))
            
            pages = cursor.fetchall()
            print("\nExample newspaper pages:")
            for page in pages:
                print(f"- PageID: {page[0]}, IssueDate: {page[1]}, Sequence: {page[2]}, SourceName: {page[3]}")
    else:
        print("NewspaperPages table does not exist")
    
    conn.close()

if __name__ == "__main__":
    print("Checking database status...")
    check_db_status()
    print("\nNow run the import through the UI to see results.\n")
    print("Step 1: In the 'Chronicling America' tab, select 'Washington' state")
    print("Step 2: Select 'The Seattle post-intelligencer. [volume]'")
    print("Step 3: Set date range from 1892-04-15 to 1892-04-17")
    print("Step 4: Click Search")
    print("Step 5: Click 'Download All Results'")
    print("Step 6: After import completes, run this script again to verify results")
    print("\nExpected result: ONE entry in Sources table, MULTIPLE entries in NewspaperPages table")