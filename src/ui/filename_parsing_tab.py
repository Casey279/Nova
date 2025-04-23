# File: filename_parsing_tab.py

import os
import re
import json
import shutil
import sqlite3
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
    QLabel, QSplitter, QMessageBox, QInputDialog, QTableWidget, QListWidgetItem,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView
from database_manager import DatabaseManager
from filename_parser_widget import FilenameParserWidget

class FilenameParsingTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.downloaded_files_dir = os.path.join(os.path.dirname(os.path.dirname(db_path)), "assets", "downloaded_files")
        self.intake_dir = os.path.join(os.path.dirname(os.path.dirname(db_path)), "assets", "intake")

        # Ensure directories exist
        os.makedirs(self.downloaded_files_dir, exist_ok=True)
        os.makedirs(self.intake_dir, exist_ok=True)

        # Pre-defined rules for known sources

        self.setup_database()
        self.initUI()

    def setup_database(self):
        """Ensure the database has the required tables and columns for filename parsing rules."""
        cursor = self.db_manager.conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='FilenameParsingRules'
        """)
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            # Create table only if it doesn't exist
            cursor.execute('''
                CREATE TABLE FilenameParsingRules (
                    id INTEGER PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    format_description TEXT NOT NULL,
                    example TEXT NOT NULL,
                    is_custom BOOLEAN DEFAULT 0
                )
            ''')
            self.db_manager.conn.commit()
        
        print("Database setup completed. Table exists:", table_exists)  # Debug print

    def create_rules_display(self):
        """Create and configure the rules display list."""
        rules_list = QListWidget()
        rules_list.setWordWrap(True)  # Enable text wrapping
        
        # Get rules from database
        cursor = self.db_manager.conn.cursor()
        cursor.execute("SELECT source_name, format_description, example FROM FilenameParsingRules ORDER BY id")
        rules = cursor.fetchall()
        
        for source_name, format_desc, example in rules:
            # Create item for the source name (bold)
            source_item = QListWidgetItem(source_name)
            font = source_item.font()
            font.setBold(True)
            source_item.setFont(font)
            rules_list.addItem(source_item)
            
            # Add format description
            format_item = QListWidgetItem(f"Format: {format_desc}")
            rules_list.addItem(format_item)
            
            # Add example
            example_item = QListWidgetItem(f"Example: {example}")
            rules_list.addItem(example_item)
            
            # Add blank line for padding (except after last rule)
            rules_list.addItem(QListWidgetItem(""))
        
        return rules_list

    def initUI(self):
        layout = QHBoxLayout(self)

        # Left Panel - File List
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # File list
        left_layout.addWidget(QLabel("Files in Downloaded Folder:"))
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        self.file_list.itemSelectionChanged.connect(self.handle_file_selection)
        left_layout.addWidget(self.file_list)

        # Buttons
        button_layout = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        analyze_button = QPushButton("Analyze Filenames")
        refresh_button.clicked.connect(self.refresh_file_list)
        analyze_button.clicked.connect(self.analyze_filenames)
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(analyze_button)
        left_layout.addLayout(button_layout)

        # Middle Panel - Parser
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)  # Match other panels' margins
        middle_layout.setSpacing(10)  # Reset spacing
        title_label = QLabel("Filename Parser:")
        middle_layout.addWidget(title_label)
        self.parser_widget = FilenameParserWidget()
        self.parser_widget.pattern_saved.connect(self.save_parsing_rule)
        middle_layout.addWidget(self.parser_widget, 1)  # Add stretch factor

        # Right Panel - Rules
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Established Rules:"))
        self.rules_list = self.create_rules_display()  # Changed from create_rules_table
        right_layout.addWidget(self.rules_list)

        # Add panels to splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(middle_panel)
        splitter.addWidget(right_panel)
        
        # Set initial sizes - adjust these numbers as needed
        splitter.setSizes([250, 500, 250])
        
        layout.addWidget(splitter)
        self.refresh_file_list()

    def init_parser_widget(self):
        """Initialize the parser widget and connect its signals."""
        self.parser_widget = FilenameParserWidget()
        self.parser_widget.pattern_saved.connect(self.save_parsing_rule)

    def save_parsing_rule(self, pattern_data):
        """Handle saving the parsing rule to the database."""
        print("Attempting to save pattern rule...")
        print(f"Pattern data received: {pattern_data}")
        
        source_name, ok = QInputDialog.getText(
            self, 
            "Save Pattern Rule", 
            "Enter a name for this pattern rule:"
        )
        
        if ok and source_name:
            try:
                format_description = self._generate_format_description(pattern_data)
                example = self._generate_example(pattern_data['segments'])
                
                print(f"Format description: {format_description}")
                print(f"Example: {example}")
                
                cursor = self.db_manager.conn.cursor()
                
                # Begin transaction
                self.db_manager.conn.execute('BEGIN')
                try:
                    cursor.execute('''
                        INSERT INTO FilenameParsingRules 
                        (source_name, pattern, format_description, example, is_custom) 
                        VALUES (?, ?, ?, ?, 1)
                    ''', (
                        source_name,
                        json.dumps(pattern_data),
                        format_description,
                        example
                    ))
                    
                    # Commit the transaction
                    self.db_manager.conn.commit()
                    print(f"Rule saved to database with source_name: {source_name}")
                    
                    # Verify the save
                    cursor.execute("SELECT * FROM FilenameParsingRules WHERE source_name = ?", (source_name,))
                    result = cursor.fetchone()
                    print(f"Verification query result: {result}")
                    
                    self.refresh_rules_table()
                    QMessageBox.information(self, "Success", f"Pattern rule '{source_name}' has been saved.")
                    
                    # Clear the form fields after successful save
                    self.parser_widget.clear_fields()
                    
                except Exception as e:
                    print(f"Error during transaction: {e}")
                    self.db_manager.conn.rollback()
                    raise
                    
            except Exception as e:
                print(f"Error saving rule: {str(e)}")
                QMessageBox.warning(self, "Error", f"Failed to save pattern rule: {str(e)}")


    def _generate_format_description(self, pattern_data):
        """Generate a human-readable format description."""
        assignments = pattern_data['fieldAssignments']
        segments = pattern_data['segments']
        separator = pattern_data.get('separator', '_')
        
        format_parts = []
        for i in range(len(segments)):
            if assignments['publication'] and i in assignments['publication']:
                format_parts.append('Publication')
            elif assignments.get('year') == i:
                format_parts.append('YYYY')
            elif assignments.get('month') == i:
                format_parts.append('MM')
            elif assignments.get('day') == i:
                format_parts.append('DD')
            elif assignments.get('page') == i:
                format_parts.append('Page')
                
        return separator.join(format_parts)

    def _generate_example(self, segments):
        """Generate an example using the original filename."""
        return '_'.join(segment['text'] for segment in segments)

    def refresh_file_list(self):
        """Refresh the file list from the downloaded_files folder."""
        self.file_list.clear()
        print(f"Refreshing files from: {self.downloaded_files_dir}")  # Debug
        files = [
            f for f in os.listdir(self.downloaded_files_dir)
            if os.path.isfile(os.path.join(self.downloaded_files_dir, f)) 
            and f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        print(f"Found files: {files}")  # Debug
        self.file_list.addItems(files)

    def analyze_filenames(self):
        """Analyze all files and identify those matching rules vs those needing parsing."""
        self.refresh_file_list()
        
        recognized_files = []
        unrecognized_files = []
        
        for i in range(self.file_list.count()):
            filename = self.file_list.item(i).text()
            if self.check_filename_against_rules(filename):
                recognized_files.append(filename)
            else:
                unrecognized_files.append(filename)

        if recognized_files:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"{len(recognized_files)} files match existing rules and can be moved to intake.")
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            
            if msg.exec_() == QMessageBox.Ok:
                # Move recognized files
                for filename in recognized_files:
                    src = os.path.join(self.downloaded_files_dir, filename)
                    dst = os.path.join(self.intake_dir, filename)
                    try:
                        shutil.move(src, dst)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to move {filename}: {str(e)}")
                
                # Refresh the file list after moving files
                self.refresh_file_list()
                
                # Show confirmation
                QMessageBox.information(self, "Files Moved", 
                    f"{len(recognized_files)} files have been moved to the intake folder.")

            if unrecognized_files:
                msg = QMessageBox.information(self, "Unrecognized Files",
                    f"{len(unrecognized_files)} files remain that don't match any rules.")

        else:
            QMessageBox.information(self, "No Matches",
                "No files match existing rules.")

    def refresh_rules_table(self):
        """Refresh the rules display with current database contents."""
        if hasattr(self, 'rules_list'):
            self.rules_list.clear()
            
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT source_name, format_description, example FROM FilenameParsingRules ORDER BY id")
            rules = cursor.fetchall()
            
            for source_name, format_desc, example in rules:
                # Create item for the source name (bold)
                source_item = QListWidgetItem(source_name)
                font = source_item.font()
                font.setBold(True)
                source_item.setFont(font)
                self.rules_list.addItem(source_item)
                
                # Add format description
                format_item = QListWidgetItem(f"Format: {format_desc}")
                self.rules_list.addItem(format_item)
                
                # Add example
                example_item = QListWidgetItem(f"Example: {example}")
                self.rules_list.addItem(example_item)
                
                # Add blank line for padding
                self.rules_list.addItem(QListWidgetItem(""))


    def check_filename_against_rules(self, filename):
        """Check if filename matches any existing rule patterns."""
        # Strip file extension for checking
        base_filename = os.path.splitext(filename)[0]
        
        cursor = self.db_manager.conn.cursor()
        cursor.execute("SELECT pattern FROM FilenameParsingRules")
        rules = cursor.fetchall()
        
        for (pattern_json,) in rules:
            try:
                pattern_data = json.loads(pattern_json)
                # Get the field assignments and segments from the pattern
                assignments = pattern_data['fieldAssignments']
                segments = pattern_data['segments']
                separator = pattern_data.get('separator', '_')
                
                # Split the filename being checked
                test_segments = base_filename.split(separator)
                
                # Check if number of segments matches
                if len(test_segments) == len(segments):
                    # Check if the segments match where we expect publication, date, and page
                    matches = True
                    for i, segment in enumerate(test_segments):
                        # Check publication segments
                        if i in assignments.get('publication', []):
                            continue
                        # Check year
                        elif i == assignments.get('year') and segment.isdigit() and len(segment) == 4:
                            continue
                        # Check month
                        elif i == assignments.get('month') and segment.isdigit() and 1 <= int(segment) <= 12:
                            continue
                        # Check day
                        elif i == assignments.get('day') and segment.isdigit() and 1 <= int(segment) <= 31:
                            continue
                        # Check page number
                        elif i == assignments.get('page') and segment.isdigit():
                            continue
                        # If any segment doesn't match expectations, mark as non-match
                        else:
                            matches = False
                            break
                    
                    if matches:
                        return True
                        
            except Exception as e:
                print(f"Error checking pattern: {e}")
                continue
        
        return False

    def move_recognized_files(self, files):
        """Move recognized files to the intake folder."""
        for filename in files:
            src = os.path.join(self.downloaded_files_dir, filename)
            dst = os.path.join(self.intake_dir, filename)
            try:
                shutil.move(src, dst)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to move {filename}: {str(e)}")
        self.refresh_file_list()

    def handle_file_selection(self):
        """Handle file selection and update the parser UI."""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        filename = selected_items[0].text()
        print(f"Selected file: {filename}")  # Debug print
        self.parser_widget.update_filename(filename)

    def update_parser_ui(self, filename):
        """Update the parser UI with the selected filename."""
        # Here we would initialize and update the React component
        # This implementation would depend on how you're handling the React integration
        pass

    def save_custom_rule(self, pattern_data):
        """Save a custom parsing rule to the database."""
        rule_name, ok = QInputDialog.getText(
            self, 
            "Name Custom Rule", 
            "Enter a name for this custom rule:"
        )
        
        if ok and rule_name:
            cursor = self.db_manager.conn.cursor()
            cursor.execute(
                """
                INSERT INTO FilenameParsingRules 
                (Name, Pattern, Fields, Separator) 
                VALUES (?, ?, ?, ?)
                """,
                (rule_name, json.dumps(pattern_data["pattern"]), 
                 json.dumps(pattern_data["fields"]), 
                 pattern_data["separator"])
            )
            self.db_manager.conn.commit()
            self.rules_list.addItem(f"Custom: {rule_name}")