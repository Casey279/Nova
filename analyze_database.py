#!/usr/bin/env python3
import sqlite3
import os
from datetime import datetime

# Path to the database
db_path = '/mnt/c/AI/Nova/src/nova_database.db'

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if NewspaperPages table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='NewspaperPages'")
newspaper_pages_exists = cursor.fetchone() is not None

print(f"NewspaperPages table exists: {newspaper_pages_exists}")

# 1. Check Sources table
cursor.execute("SELECT COUNT(*) FROM Sources")
source_count = cursor.fetchone()[0]
print(f"\nSources table has {source_count} records")

if source_count > 0:
    cursor.execute("SELECT * FROM Sources")
    columns = [desc[0] for desc in cursor.description]
    sources = cursor.fetchall()
    
    print("\nSources table records:")
    for source in sources:
        print("\n" + "-" * 50)
        for i, col in enumerate(columns):
            print(f"{col}: {source[i]}")

# 2. Check NewspaperPages table (if it exists)
if newspaper_pages_exists:
    cursor.execute("SELECT COUNT(*) FROM NewspaperPages")
    pages_count = cursor.fetchone()[0]
    print(f"\nNewspaperPages table has {pages_count} records")
    
    if pages_count > 0:
        # Get summary by issue date and sequence
        cursor.execute("""
            SELECT IssueDate, COUNT(*) as page_count, 
                   MIN(Sequence) as min_seq, MAX(Sequence) as max_seq,
                   GROUP_CONCAT(Sequence ORDER BY Sequence) as sequences
            FROM NewspaperPages
            GROUP BY IssueDate
            ORDER BY IssueDate
        """)
        
        date_summary = cursor.fetchall()
        print("\nPages by issue date:")
        for date_info in date_summary:
            issue_date, count, min_seq, max_seq, sequences = date_info
            print(f"Date: {issue_date} - {count} pages (Sequences {min_seq}-{max_seq})")
            # Show sequences for dates with gaps
            if count < (max_seq - min_seq + 1):
                print(f"  Sequences: {sequences}")
        
        # Get a sample of the most recent pages
        cursor.execute("""
            SELECT np.PageID, np.SourceID, np.LCCN, np.IssueDate, np.Sequence, 
                   np.PageTitle, np.ImagePath, np.ImportDate
            FROM NewspaperPages np
            ORDER BY np.ImportDate DESC, np.IssueDate, np.Sequence
            LIMIT 5
        """)
        
        columns = [desc[0] for desc in cursor.description]
        recent_pages = cursor.fetchall()
        
        print("\nMost recent pages:")
        for page in recent_pages:
            print("\n" + "-" * 50)
            for i, col in enumerate(columns):
                print(f"{col}: {page[i]}")
                
        # Get counts by LCCN
        cursor.execute("""
            SELECT LCCN, COUNT(*) as page_count
            FROM NewspaperPages
            GROUP BY LCCN
            ORDER BY page_count DESC
        """)
        
        lccn_counts = cursor.fetchall()
        print("\nPages by LCCN:")
        for lccn, count in lccn_counts:
            print(f"LCCN: {lccn} - {count} pages")
            
        # Try to identify sequence gaps for specific LCCN and date range
        lccn = "sn83045604"  # Seattle Post-Intelligencer
        date_start = "1892-04-15"
        date_end = "1892-04-20"
        
        cursor.execute("""
            SELECT IssueDate, Sequence
            FROM NewspaperPages
            WHERE LCCN = ? AND IssueDate BETWEEN ? AND ?
            ORDER BY IssueDate, Sequence
        """, (lccn, date_start, date_end))
        
        existing_pages = cursor.fetchall()
        print(f"\nExisting pages for LCCN {lccn} from {date_start} to {date_end}:")
        
        current_date = None
        date_sequences = []
        all_dates = {}
        
        for date, seq in existing_pages:
            if current_date != date:
                if current_date is not None:
                    all_dates[current_date] = date_sequences
                    print(f"  {current_date}: {len(date_sequences)} pages - Sequences: {', '.join(map(str, date_sequences))}")
                current_date = date
                date_sequences = []
            
            date_sequences.append(seq)
        
        # Don't forget the last date
        if current_date is not None:
            all_dates[current_date] = date_sequences
            print(f"  {current_date}: {len(date_sequences)} pages - Sequences: {', '.join(map(str, date_sequences))}")
            
        # Analyze possible reasons for skipping
        print("\nPossible reasons for skipping:")
        
        # Check if there are missing dates in the range
        date_format = "%Y-%m-%d"
        start = datetime.strptime(date_start, date_format)
        end = datetime.strptime(date_end, date_format)
        days = (end - start).days + 1
        
        print(f"Date range covers {days} days")
        print(f"Found data for {len(all_dates)} dates")
        
        if len(all_dates) < days:
            print("Missing dates could be one reason for skipping")
        
        # Check if there are missing sequences in each date
        for date, sequences in all_dates.items():
            expected_seqs = list(range(1, max(sequences) + 1))
            missing_seqs = [seq for seq in expected_seqs if seq not in sequences]
            if missing_seqs:
                print(f"Date {date} has missing sequences: {', '.join(map(str, missing_seqs))}")

# Close the connection
conn.close()
print("\nAnalysis complete.")