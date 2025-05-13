#!/usr/bin/env python3
"""
Test script for the improved Chronicling America tab

This provides a standalone test window to verify the improved interface
works correctly. It properly displays newspaper information including title,
LCCN, location, and date range in the dropdown.

How to use:
1. Run this script directly: python src/test_improved_ca_tab.py
2. Select a state from the dropdown
3. Verify that the newspaper dropdown is populated with detailed information
   in the format: "Publication Name (LCCN), Publication City, First Issue Date to Latest Issue Date"
4. Try other features like searching, custom LCCN, etc.
"""

import sys
import os
import logging
import tempfile

# Set up logging to console with more detailed output
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QStatusBar
from PyQt5.QtCore import Qt

# Add the parent directory to sys.path to find modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)  # Use insert instead of append for priority

# Import the improved tab directly from the current directory
try:
    from ui.chronicling_america_tab_improved import ChroniclingAmericaTabImproved
    logging.info("Successfully imported ChroniclingAmericaTabImproved")
except ImportError as e:
    logging.error(f"Failed to import ChroniclingAmericaTabImproved: {e}")
    sys.exit(1)

class TestWindow(QMainWindow):
    """Test window for the improved Chronicling America tab."""

    def __init__(self):
        super().__init__()

        # Set up the window
        self.setWindowTitle("Improved Chronicling America Tab Test")
        self.setGeometry(100, 100, 1200, 800)

        # Create status bar for messages
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Test window initialized. Select a state to see improved newspaper listings.")

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add header label explaining the test
        header_label = QLabel("Test Window for Improved Chronicling America Tab")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 10px;")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        instructions_label = QLabel(
            "1. Select a state from the dropdown\n"
            "2. Verify that newspaper dropdown shows detailed information\n"
            "3. Format should be: Publication Name (LCCN), Publication City, Date Range"
        )
        instructions_label.setStyleSheet("font-size: 12pt; margin-bottom: 20px;")
        instructions_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions_label)

        # Determine path to a test database - use temp directory
        db_path = os.path.join(tempfile.gettempdir(), "test_ca_db.sqlite")
        logging.info(f"Using database path: {db_path}")

        # Create the tab and add it to the layout
        self.ca_tab = ChroniclingAmericaTabImproved(db_path)

        # Connect to status messages
        self.ca_tab.state_combo.currentIndexChanged.connect(self.on_state_changed)
        self.ca_tab.newspaper_combo.currentIndexChanged.connect(self.on_newspaper_changed)

        layout.addWidget(self.ca_tab)

    def on_state_changed(self, index):
        """Handle state selection changes."""
        state = self.ca_tab.state_combo.currentText()
        if state:
            self.statusBar.showMessage(f"Selected state: {state}. Loading newspapers...")

    def on_newspaper_changed(self, index):
        """Handle newspaper selection changes."""
        if index > 0:  # Skip the "Select Title" item
            newspaper = self.ca_tab.newspaper_combo.currentText()
            lccn = self.ca_tab.newspaper_combo.currentData()
            self.statusBar.showMessage(f"Selected newspaper: {newspaper}, LCCN: {lccn}")

def main():
    """Main function to run the test window."""
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    print("Running test window for improved Chronicling America Tab...")
    print("Verify that the newspaper dropdown shows detailed information in this format:")
    print("  Publication Name (LCCN), Publication City, First Issue Date to Latest Issue Date")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()