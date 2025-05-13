#!/usr/bin/env python3
"""
Script to fix newspaper data in the database.
This script:
1. Creates the NewspaperPages table if it doesn't exist
2. Extracts information from existing Sources records
3. Creates a single Source record for the newspaper
4. Creates appropriate NewspaperPages records linked to the Source
"""

import os
import sqlite3
import re
from datetime import datetime

# Path to the database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_database.db")

def create_newspaper_pages_table(cursor):
    """Create the NewspaperPages table if it doesn't exist."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS NewspaperPages (
        PageID INTEGER PRIMARY KEY AUTOINCREMENT,
        SourceID INTEGER,
        LCCN TEXT NOT NULL,
        IssueDate TEXT NOT NULL,
        Sequence INTEGER NOT NULL,
        PageTitle TEXT,
        PageNumber TEXT,
        ImagePath TEXT,
        OCRPath TEXT,
        PDFPath TEXT,
        JSONPath TEXT,
        ExternalURL TEXT,
        ImportDate TEXT,
        ProcessedFlag INTEGER DEFAULT 0,
        FOREIGN KEY (SourceID) REFERENCES Sources(SourceID),
        UNIQUE(LCCN, IssueDate, Sequence)
    )
    """)
    print("NewspaperPages table created or already exists")

def extract_info_from_source_name(source_name):
    """Extract date and possibly sequence from source name."""
    # Example format: "The Seattle post-intelligencer. [volume] - 1892-04-15"
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', source_name)
    
    issue_date = None
    if date_match:
        issue_date = date_match.group(1)
    
    # Extract sequence if present (format might be "- Seq X" at the end)
    sequence = 1  # Default sequence
    seq_match = re.search(r'Seq (\d+)', source_name)
    if seq_match:
        sequence = int(seq_match.group(1))
    
    return {
        'issue_date': issue_date,
        'sequence': sequence
    }

def create_consolidated_newspaper_data():
    """
    Fix newspaper data by:
    1. Creating a single source record for each LCCN
    2. Creating page records for each page
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the NewspaperPages table if it doesn't exist
    create_newspaper_pages_table(cursor)
    
    # Find all newspaper sources with LCCN sn83045604
    cursor.execute("""
    SELECT SourceID, SourceName, Aliases 
    FROM Sources 
    WHERE Aliases LIKE ? AND SourceType = 'newspaper'
    ORDER BY SourceID
    """, ('sn83045604',))
    
    existing_sources = cursor.fetchall()
    
    if not existing_sources:
        print("No newspaper sources found with LCCN sn83045604")
        conn.close()
        return
    
    print(f"Found {len(existing_sources)} existing source records with LCCN sn83045604")
    
    # Get the first source as a template
    first_source = existing_sources[0]
    source_id = first_source[0]
    base_name = "The Seattle post-intelligencer"
    lccn = "sn83045604"
    
    # Use this source as the canonical source for all pages
    print(f"Using SourceID {source_id} as the canonical source for all pages")
    
    # Update the source name to remove the date and make it the canonical source
    cursor.execute("""
    UPDATE Sources 
    SET SourceName = ?, Aliases = ? 
    WHERE SourceID = ?
    """, (base_name, lccn, source_id))
    
    # Create newspaper page entries for each existing source
    pages_inserted = 0
    dates_processed = set()
    
    for old_source in existing_sources:
        old_id = old_source[0]
        old_name = old_source[1]
        
        # Skip the source we're keeping
        if old_id == source_id:
            continue
        
        # Extract info from source name
        info = extract_info_from_source_name(old_name)
        issue_date = info.get('issue_date')
        sequence = info.get('sequence')
        
        # Skip if we can't extract a date
        if not issue_date:
            print(f"Skipping source {old_id}: {old_name} - Could not extract date")
            continue
        
        # Create an identifier for this date+sequence
        page_key = f"{issue_date}_{sequence}"
        
        # Skip duplicates
        if page_key in dates_processed:
            print(f"Skipping duplicate {page_key}")
            continue
        
        # Insert into NewspaperPages
        try:
            cursor.execute("""
            INSERT INTO NewspaperPages (
                SourceID, LCCN, IssueDate, Sequence, PageTitle, ImportDate
            ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                source_id, 
                lccn, 
                issue_date, 
                sequence, 
                old_name,
                datetime.now().strftime('%Y-%m-%d')
            ))
            
            dates_processed.add(page_key)
            pages_inserted += 1
            
            # Delete the old source
            cursor.execute("DELETE FROM Sources WHERE SourceID = ?", (old_id,))
            
        except sqlite3.IntegrityError as e:
            print(f"Error inserting page for {old_name}: {e}")
    
    # Commit changes
    conn.commit()
    
    # Final report
    print(f"\nMigration complete:")
    print(f"- Kept SourceID {source_id} as the canonical source for newspaper '{base_name}'")
    print(f"- Created {pages_inserted} newspaper page records")
    print(f"- Removed {len(existing_sources) - 1} redundant source records")
    
    # Verify the results
    cursor.execute("SELECT COUNT(*) FROM Sources WHERE Aliases = ?", (lccn,))
    source_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM NewspaperPages WHERE LCCN = ?", (lccn,))
    page_count = cursor.fetchone()[0]
    
    print(f"\nVerification:")
    print(f"- Sources table now has {source_count} record(s) for LCCN {lccn}")
    print(f"- NewspaperPages table now has {page_count} records for LCCN {lccn}")
    
    conn.close()

if __name__ == "__main__":
    print("Starting newspaper data migration...")
    create_consolidated_newspaper_data()
    print("Done!")