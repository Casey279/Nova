#!/usr/bin/env python3
import sqlite3

# Path to the database
db_path = '/mnt/c/AI/Nova/src/nova_database.db'

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create NewspaperPages table
print("Creating NewspaperPages table...")
cursor.execute('''
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
''')

# Create an index for faster lookups
cursor.execute('''
CREATE INDEX IF NOT EXISTS idx_newspaper_lccn_date_seq ON NewspaperPages (LCCN, IssueDate, Sequence)
''')

# Commit the changes
conn.commit()
print("NewspaperPages table created successfully.")

# Close the connection
conn.close()
print("Database connection closed.")