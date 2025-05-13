"""
Test script to verify that the ChroniclingAmericaTab UI correctly integrates
with the ImprovedChroniclingAmericaClient's earliest issue date detection.

This test script creates a minimal PyQt application to load the ChroniclingAmericaTab
and test the earliest issue date integration.
"""

import os
import sys
import json
import logging
from datetime import datetime, date, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Qt components
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt

# Import our UI components
from src.ui.chronicling_america_tab import ChroniclingAmericaTab, USING_IMPROVED_CLIENT

class TestWindow(QMainWindow):
    """Test window to host the ChroniclingAmericaTab."""
    
    def __init__(self):
        super().__init__()
        
        # Create a dummy database path
        self.db_path = "test_db.sqlite"
        
        # Create the tab
        self.ca_tab = ChroniclingAmericaTab(self.db_path)
        
        # Set up the window
        self.setCentralWidget(self.ca_tab)
        self.setWindowTitle("ChroniclingAmericaTab Test")
        self.resize(1200, 800)
        
    def test_earliest_date_integration(self):
        """Test the earliest date integration."""
        # Call the verification function on the tab
        results = self.ca_tab.verify_earliest_date_integration()
        
        # Log the results
        logger.info("Earliest date integration test results:")
        logger.info(f"Using improved client: {results['using_improved_client']}")
        logger.info(f"Earliest date available: {results['earliest_date_available']}")
        
        if results['newspaper_title']:
            logger.info(f"Newspaper title: {results['newspaper_title']}")
        
        if results['earliest_date']:
            logger.info(f"Earliest date: {results['earliest_date']}")
        
        for message in results['messages']:
            logger.info(f"Message: {message}")
        
        logger.info(f"Success: {results['success']}")
        
        return results
        
    def test_search_with_early_date(self):
        """
        Test searching for pages with a date range that starts before the first issue.
        
        This test manually sets up a search with the Seattle Post-Intelligencer LCCN
        and a date range starting from January 1, 1888 (before the first issue on May 11, 1888).
        It then initiates a search and lets the UI handle the results.
        """
        # Set up the search parameters
        lccn = "sn83045604"  # Seattle Post-Intelligencer
        
        # Use the custom LCCN option
        self.ca_tab.custom_lccn_check.setChecked(True)
        self.ca_tab.lccn_edit.setText(lccn)
        
        # Set date range from January 1, 1888 to June 1, 1888
        start_date = QDate(1888, 1, 1)
        end_date = QDate(1888, 6, 1)
        
        self.ca_tab.date_start_edit.setDate(start_date)
        self.ca_tab.date_end_edit.setDate(end_date)
        
        # Log the test setup
        logger.info(f"Setting up search for LCCN {lccn} from {start_date.toString('yyyy-MM-dd')} to {end_date.toString('yyyy-MM-dd')}")
        logger.info("Expecting search to be adjusted to start from May 11, 1888 (first issue)")
        
        # Initiate the search
        self.ca_tab.search()
        
        # Note: The search is asynchronous, so results won't be immediately available
        # In a real test, we would need to connect to signals or use QTest to wait for results
        logger.info("Search initiated. Check the UI for results.")
        logger.info("Look for the text 'Search adjusted to start from the first issue' in the status bar.")
        
        return True

def main():
    """Main function to run tests."""
    app = QApplication(sys.argv)
    
    # Create the test window
    window = TestWindow()
    
    # Test the earliest date integration
    results = window.test_earliest_date_integration()
    
    if results['success']:
        # If the integration test passes, try a search test
        window.test_search_with_early_date()
        
        # Show the window to see the UI
        window.show()
        
        # Start the Qt event loop
        sys.exit(app.exec_())
    else:
        logger.error("Earliest date integration test failed, not continuing with search test.")
        sys.exit(1)

if __name__ == "__main__":
    main()