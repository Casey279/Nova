#!/usr/bin/env python3
# Test script for the Chronicling America tab functionality

import os
import sys
import sqlite3
import logging
from datetime import datetime
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QDate

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.chronicling_america_tab import ChroniclingAmericaTab, USING_IMPROVED_CLIENT

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_temp_database():
    """Create a temporary database for testing."""
    temp_dir = os.path.join(os.path.dirname(__file__), "..", "test_output")
    os.makedirs(temp_dir, exist_ok=True)
    
    db_path = os.path.join(temp_dir, "test_db.sqlite")
    
    # Create a basic database structure for testing
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create a simple sources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            title TEXT,
            author TEXT,
            source_type TEXT,
            publication_date TEXT,
            content TEXT,
            url TEXT,
            lccn TEXT,
            page_number INTEGER,
            image_path TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
    return db_path

def test_chronicling_america_tab():
    """Test the Chronicling America tab functionality."""
    # Create a temporary database
    db_path = create_temp_database()
    
    # Create the application
    app = QApplication(sys.argv)
    
    # Create the tab
    tab = ChroniclingAmericaTab(db_path=db_path)
    
    # Print information about the client being used
    if USING_IMPROVED_CLIENT:
        logger.info("Using ImprovedChroniclingAmericaClient for searching")
    else:
        logger.info("Using standard ChroniclingAmericaClient for searching")
    
    # Set search parameters
    # Seattle Post-Intelligencer in April 1891
    tab.newspaper_combo.setCurrentIndex(tab.newspaper_combo.findData("sn83045604"))
    tab.date_start_edit.setDate(QDate(1891, 4, 1))
    tab.date_end_edit.setDate(QDate(1891, 4, 30))
    
    # Disable import to avoid modifying the database
    tab.import_check.setChecked(False)
    
    # Show the tab (but don't process events)
    tab.show()
    
    # Simulate searching
    logger.info("Performing search with the following parameters:")
    logger.info(f"  Newspaper: Seattle Post-Intelligencer (LCCN: sn83045604)")
    logger.info(f"  Date range: 1891-04-01 to 1891-04-30")
    
    # Call the search method directly
    tab.search()
    
    # Process Qt events to allow the search to complete
    # But limit the number of iterations to avoid an infinite loop
    for _ in range(100):
        app.processEvents()
        
        # If search is complete, break the loop
        if not hasattr(tab, 'search_worker') or not tab.search_worker.isRunning():
            break
    
    # Log results
    logger.info(f"Search results: {tab.results_list.count()} items found")
    
    # Clean up
    tab.deleteLater()
    
    return tab.results_list.count() > 0

if __name__ == "__main__":
    logger.info("Testing Chronicling America tab functionality")
    
    success = test_chronicling_america_tab()
    
    if success:
        logger.info("Test PASSED: Found results from the Seattle Post-Intelligencer in April 1891")
        sys.exit(0)
    else:
        logger.error("Test FAILED: No results found")
        sys.exit(1)