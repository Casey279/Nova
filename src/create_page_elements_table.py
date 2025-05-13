#!/usr/bin/env python3
"""
Script to create the PageElements table for storing structural decomposition of newspaper pages.
This table will store information about the individual elements of each newspaper page
(columns, paragraphs, headlines, images, etc.) to support advanced OCR processing.
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

def create_page_elements_table():
    """
    Create the PageElements table for storing structural decomposition of newspaper pages.
    """
    db_path = find_database()
    if db_path is None:
        logger.error("Cannot create table: Database not found")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Begin a transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='PageElements'")
        if cursor.fetchone():
            logger.info("PageElements table already exists")
        else:
            # Create the PageElements table
            cursor.execute("""
                CREATE TABLE PageElements (
                    ElementID INTEGER PRIMARY KEY AUTOINCREMENT,
                    PageID INTEGER NOT NULL,                -- Foreign key to NewspaperPages table
                    ElementType TEXT NOT NULL,              -- Type of element: column, paragraph, headline, image, etc.
                    ElementIdentifier TEXT NOT NULL,        -- Logical identifier (e.g., 'A1' for column A, paragraph 1)
                    SequenceOrder INTEGER NOT NULL,         -- Order within the parent element for reassembly
                    ParentElementID INTEGER,                -- Foreign key to parent element (NULL for top-level elements)
                    ContinuedFromID INTEGER,                -- Element this continues from (for article continuations)
                    ContinuedToID INTEGER,                  -- Element this continues to (for article continuations)
                    X1 INTEGER NOT NULL,                    -- Left coordinate of bounding box
                    Y1 INTEGER NOT NULL,                    -- Top coordinate of bounding box
                    X2 INTEGER NOT NULL,                    -- Right coordinate of bounding box
                    Y2 INTEGER NOT NULL,                    -- Bottom coordinate of bounding box
                    OCRText TEXT,                           -- OCR text for this element
                    OCRConfidence REAL,                     -- Confidence score of OCR (0-100%)
                    ProcessingStatus TEXT DEFAULT 'pending', -- Status: pending, ocr_complete, verified, etc.
                    ArticleID INTEGER,                      -- ID for grouping elements belonging to the same article
                    Notes TEXT,                             -- Any notes about this element
                    CreatedDate TEXT DEFAULT CURRENT_TIMESTAMP,
                    LastModified TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (PageID) REFERENCES NewspaperPages(PageID) ON DELETE CASCADE,
                    FOREIGN KEY (ParentElementID) REFERENCES PageElements(ElementID) ON DELETE SET NULL,
                    FOREIGN KEY (ContinuedFromID) REFERENCES PageElements(ElementID) ON DELETE SET NULL,
                    FOREIGN KEY (ContinuedToID) REFERENCES PageElements(ElementID) ON DELETE SET NULL
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX idx_page_elements_pageid ON PageElements(PageID)")
            cursor.execute("CREATE INDEX idx_page_elements_parent ON PageElements(ParentElementID)")
            cursor.execute("CREATE INDEX idx_page_elements_article ON PageElements(ArticleID)")
            cursor.execute("CREATE INDEX idx_page_elements_continued_from ON PageElements(ContinuedFromID)")
            cursor.execute("CREATE INDEX idx_page_elements_continued_to ON PageElements(ContinuedToID)")
            
            logger.info("PageElements table created successfully")
        
        # Create an Articles table for grouping page elements into articles
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Articles'")
        if cursor.fetchone():
            logger.info("Articles table already exists")
        else:
            cursor.execute("""
                CREATE TABLE Articles (
                    ArticleID INTEGER PRIMARY KEY AUTOINCREMENT,
                    SourceID INTEGER,                       -- Source ID (newspaper)
                    ArticleTitle TEXT,                      -- Title of the article
                    ArticleDate TEXT,                       -- Publication date
                    Authors TEXT,                           -- Authors of the article
                    Category TEXT,                          -- Category/type of article (news, editorial, etc.)
                    FullText TEXT,                          -- Assembled full text of the article
                    Keywords TEXT,                          -- Keywords/tags for the article
                    ProcessingStatus TEXT DEFAULT 'pending', -- Status: pending, assembled, verified, etc.
                    Notes TEXT,                             -- Any notes about this article
                    CreatedDate TEXT DEFAULT CURRENT_TIMESTAMP,
                    LastModified TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (SourceID) REFERENCES Sources(SourceID) ON DELETE SET NULL
                )
            """)
            
            cursor.execute("CREATE INDEX idx_articles_sourceid ON Articles(SourceID)")
            cursor.execute("CREATE INDEX idx_articles_date ON Articles(ArticleDate)")
            
            logger.info("Articles table created successfully")
        
        # Commit the transaction
        conn.commit()
        logger.info("All tables created or verified successfully")
        
        # Print schema for verification
        cursor.execute("PRAGMA table_info(PageElements)")
        columns_info = cursor.fetchall()
        logger.info("PageElements table schema:")
        for col in columns_info:
            logger.info(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL allowed'}")
        
        cursor.execute("PRAGMA table_info(Articles)")
        columns_info = cursor.fetchall()
        logger.info("Articles table schema:")
        for col in columns_info:
            logger.info(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL allowed'}")
        
        return True
            
    except sqlite3.Error as e:
        # Roll back the transaction on error
        if conn:
            conn.rollback()
        logger.error(f"Error creating tables: {str(e)}")
        return False
    
    finally:
        # Close the connection
        if conn:
            conn.close()

def create_element_type_mapping():
    """
    Create a table for mapping element types to their properties.
    This helps standardize the types of elements that can be identified.
    """
    db_path = find_database()
    if db_path is None:
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Begin a transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ElementTypes'")
        if cursor.fetchone():
            logger.info("ElementTypes table already exists")
        else:
            # Create the ElementTypes table
            cursor.execute("""
                CREATE TABLE ElementTypes (
                    TypeID INTEGER PRIMARY KEY AUTOINCREMENT,
                    TypeName TEXT NOT NULL UNIQUE,          -- Unique name of the element type
                    Description TEXT,                       -- Description of this type
                    ParentTypes TEXT,                       -- Comma-separated list of types that can be parents
                    ChildTypes TEXT,                        -- Comma-separated list of types that can be children
                    CanHaveText BOOLEAN DEFAULT 1,          -- Whether this element can contain text
                    DisplayColor TEXT,                      -- Color for UI display (hex code)
                    SortOrder INTEGER                       -- For ordering in UI displays
                )
            """)
            
            # Insert default element types
            element_types = [
                ("COLUMN", "Newspaper column", "", "HEADLINE,SUBHEADLINE,PARAGRAPH,IMAGE,CAPTION,BYLINE", 1, "#88CCFF", 1),
                ("HEADLINE", "Article headline", "COLUMN", "SUBHEADLINE,DATELINE,BYLINE", 1, "#FF8888", 2),
                ("SUBHEADLINE", "Article subheadline", "COLUMN,HEADLINE", "DATELINE,BYLINE", 1, "#FFAAAA", 3),
                ("PARAGRAPH", "Text paragraph", "COLUMN,ARTICLE", "", 1, "#AAFFAA", 4),
                ("IMAGE", "Pictorial image", "COLUMN,ARTICLE", "CAPTION", 0, "#FFFFAA", 5),
                ("CAPTION", "Image caption", "COLUMN,ARTICLE,IMAGE", "", 1, "#FFDDAA", 6),
                ("BYLINE", "Author attribution", "COLUMN,ARTICLE,HEADLINE", "", 1, "#DDAAFF", 7),
                ("DATELINE", "Date and location line", "COLUMN,ARTICLE,HEADLINE", "", 1, "#AADDFF", 8),
                ("ADVERTISEMENT", "Advertisement", "COLUMN", "HEADLINE,PARAGRAPH,IMAGE", 1, "#DDDDDD", 9),
                ("TABLE", "Tabular data", "COLUMN,ARTICLE", "", 1, "#FFCCDD", 10)
            ]
            
            cursor.executemany("""
                INSERT INTO ElementTypes (TypeName, Description, ParentTypes, ChildTypes, CanHaveText, DisplayColor, SortOrder)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, element_types)
            
            logger.info(f"ElementTypes table created with {len(element_types)} default types")
            
        # Commit the transaction
        conn.commit()
        return True
            
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Error creating ElementTypes table: {str(e)}")
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Creating tables for newspaper structural decomposition...")
    
    page_elements_success = create_page_elements_table()
    element_types_success = create_element_type_mapping()
    
    if page_elements_success and element_types_success:
        logger.info("All tables for structural decomposition created successfully")
        logger.info("Ready to begin OCR structural decomposition process")
    else:
        logger.error("Failed to create one or more tables")