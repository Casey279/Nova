# File: article_processor.py

import sys
import os
import sqlite3
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database_manager import DatabaseManager

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QSplitter, QSplitterHandle, QMessageBox, QDialog,
                            QTextEdit, QDialogButtonBox)
from PyQt5.QtGui import QPainter
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal

# Import component panels
from components.document_panel import DocumentPanel
from components.text_panel import TextPanel
from components.entity_panel import EntityPanel


class CustomSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setStyleSheet("background-color: lightgray")  # Change the color if desired

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw custom icon or text here - you can customize this as needed
        painter.drawText(self.rect(), Qt.AlignCenter, "<>")  # Drawing "<>" in the middle of the handle


class CustomSplitter(QSplitter):
    def createHandle(self):
        return CustomSplitterHandle(self.orientation(), self)  # Use our custom handle


class ArticleProcessor(QWidget):
    """
    ArticleProcessor coordinates document viewing, OCR processing, and metadata management.
    
    This class has been refactored to use specialized components:
    - DocumentPanel: Handles image display and region selection
    - TextPanel: Manages OCR and text editing
    - EntityPanel: Manages metadata and entity tagging
    
    ArticleProcessor serves as a container and coordinator for these components.
    """
    
    name_added = pyqtSignal()

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.image_path = None
        self.current_event_id = None
        self.changes_made = False
        self.project_folder = None
        
        # Create all UI components
        self.initUI()
        
        # Use a single timer for both setup operations
        QTimer.singleShot(0, self.post_init_setup)

    def set_project_folder(self, folder_path):
        """Set the current project folder path"""
        self.project_folder = folder_path
        self.document_panel.set_project_folder(folder_path)

    def post_init_setup(self):
        """Handle all post-initialization setup"""
        self.setup_event_filters()
        self.set_initial_sizes()

    def initUI(self):
        """Initialize the user interface"""
        layout = QHBoxLayout(self)
        self.splitter = CustomSplitter(Qt.Horizontal)

        # Define splitter positions
        self.left_split = 0.25
        self.center_split = 0.50
        self.right_split = 0.25

        # Create component panels
        self.document_panel = DocumentPanel()
        self.text_panel = TextPanel()
        self.entity_panel = EntityPanel(self.db_manager)

        # Add panels to splitter
        self.splitter.addWidget(self.document_panel)
        self.splitter.addWidget(self.text_panel)
        self.splitter.addWidget(self.entity_panel)

        # Connect signals between components
        self.connect_signals()

        # Add the splitter to the main layout
        layout.addWidget(self.splitter)

    def connect_signals(self):
        """Connect signals between component panels"""
        # Document panel signals
        self.document_panel.image_loaded.connect(self.on_image_loaded)
        self.document_panel.region_selected.connect(self.text_panel.run_region_ocr)
        
        # Text panel signals
        self.text_panel.text_changed.connect(self.on_text_changed)
        self.text_panel.names_detected.connect(self.entity_panel.add_detected_names)
        
        # Entity panel signals
        self.entity_panel.save_requested.connect(self.save_data)
        self.entity_panel.metadata_changed.connect(self.on_metadata_changed)

    def set_initial_sizes(self):
        """Set initial sizes for the splitter panels"""
        window_width = self.width()
        # Set initial positions with right splitter at max position (0.80)
        self.left_split = 0.25  # Left panel at 25%
        self.center_split = 0.55  # Center panel fills to 80% (0.25 + 0.55 = 0.80)
        self.right_split = 0.20  # Right panel takes remaining 20%
        
        self.splitter.setSizes([
            int(window_width * self.left_split),
            int(window_width * self.center_split),
            int(window_width * self.right_split)
        ])

    def setup_event_filters(self):
        """Install event filters on the splitter handles"""
        self.splitter.handle(1).installEventFilter(self)
        self.splitter.handle(2).installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle splitter movement constraints"""
        if event.type() == QEvent.MouseMove:
            total_width = self.width()
            
            if obj == self.splitter.handle(1):  # Left splitter
                # Don't let left splitter move past 20% or 30% of window width
                min_pos = 0.20
                max_pos = 0.30
                current_pos = obj.mapToGlobal(event.pos()).x() / total_width
                
                if current_pos < min_pos:
                    self.left_split = min_pos
                elif current_pos > max_pos:
                    self.left_split = max_pos
                    
            elif obj == self.splitter.handle(2):  # Right splitter
                # Don't let right splitter move past 70% or 80% of window width
                min_pos = 0.70
                max_pos = 0.80
                current_pos = obj.mapToGlobal(event.pos()).x() / total_width
                
                if current_pos < min_pos:
                    self.center_split = min_pos - self.left_split
                elif current_pos > max_pos:
                    self.center_split = max_pos - self.left_split
                    
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        # Update splitter sizes when window is resized
        self.set_initial_sizes()

    #
    # Event handlers and signal slots
    #
    
    def on_image_loaded(self, image_path):
        """Handle image loaded signal from document panel"""
        self.image_path = image_path
        self.text_panel.set_image_path(image_path)
        
        # Parse filename to extract metadata if possible
        if image_path:
            filename = os.path.basename(image_path)
            self.try_extract_metadata_from_filename(filename)
            
        self.changes_made = True

    def on_text_changed(self, text):
        """Handle text changed signal from text panel"""
        self.changes_made = True
    
    def on_metadata_changed(self, metadata):
        """Handle metadata changed signal from entity panel"""
        self.changes_made = True

    def try_extract_metadata_from_filename(self, filename):
        """Try to extract metadata from the filename pattern"""
        try:
            # Call a separate helper method to parse based on your filename rules
            metadata = self.parse_filename(filename)
            if metadata:
                # Update entity panel with extracted data
                self.entity_panel.event_date_input.setText(metadata.get('event_date', ''))
                self.entity_panel.event_title_input.setText(metadata.get('event_title', ''))
                self.entity_panel.source_type_input.setText(metadata.get('source_type', ''))
                self.entity_panel.source_name_input.setText(metadata.get('source_name', ''))
                self.entity_panel.publication_date_input.setText(metadata.get('event_date', ''))
                
                # Add page number to metadata
                self.entity_panel.metadata['page_number'] = metadata.get('page_number', '')
        except Exception as e:
            print(f"Error extracting metadata from filename: {str(e)}")
    
    def parse_filename(self, filename):
        """Parse filename according to the project's naming convention"""
        try:
            parts = filename.split('_')
            if len(parts) < 5:
                return None
            
            date = parts[0]
            event_title = parts[1]
            source_type_code = parts[2]
            source_name = parts[3]
            page_number = parts[4]
            
            source_code = parts[5].split('.')[0] if len(parts) > 5 else 'XX'
            
            source_type_mapping = {
                'N': 'N - Newspaper',
                'B': 'B - Book',
                'J': 'J - Journal',
                'M': 'M - Magazine',
                'W': 'W - Wikipedia',
                'D': 'D - Diary/Personal Journal',
                'L': 'L - Letter/Correspondence',
                'G': 'G - Government Document',
                'C': 'C - Court Record',
                'R': 'R - Religious Record',
                'S': 'S - Ship Record/Manifest',
                'P': 'P - Photograph',
                'A': 'A - Academic Paper',
                'T': 'T - Trade Publication',
                'I': 'I - Interview Transcript',
                'O': 'O - Other'
            }
            
            source_type_full = source_type_mapping.get(source_type_code, source_type_code)
            
            actual_source_name = source_name
            if source_code != 'XX':
                cursor = self.db_manager.conn.cursor()
                cursor.execute("SELECT SourceName FROM Sources WHERE SourceCode = ?", (source_code,))
                result = cursor.fetchone()
                if result:
                    actual_source_name = result[0]
            
            return {
                'event_date': date,
                'event_title': event_title,
                'source_type': source_type_full,
                'source_name': actual_source_name,
                'page_number': page_number,
                'source_code': source_code
            }
        except Exception as e:
            print(f"Error parsing filename: {str(e)}")
            return None

    def save_data(self, event_data):
        """Save event data to database"""
        # Collect data from all panels
        complete_data = event_data.copy()
        complete_data['text_content'] = self.text_panel.get_text()
        complete_data['image_path'] = self.image_path
        
        try:
            # Determine if this is a new event or update
            if self.current_event_id:
                # Update existing event
                success = self.update_event(self.current_event_id, complete_data)
                if success:
                    QMessageBox.information(self, "Success", f"Event {self.current_event_id} updated successfully.")
            else:
                # Create new event
                event_id = self.create_event(complete_data)
                if event_id:
                    self.current_event_id = event_id
                    self.entity_panel.current_event_id = event_id
                    self.entity_panel.event_id_label.setText(f"Event ID: {event_id}")
                    QMessageBox.information(self, "Success", f"Event created with ID: {event_id}")
            
            # Reset changes flag
            self.changes_made = False
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save event: {str(e)}")

    def create_event(self, data):
        """Create a new event with the given data"""
        try:
            # Create event record
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                INSERT INTO Events (
                    EventDate, PublicationDate, EventTitle, EventText,
                    SourceType, SourceName, FilePath, Status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('event_date', ''),
                data.get('publication_date', ''),
                data.get('event_title', ''),
                data.get('text_content', ''),
                data.get('source_type', ''),
                data.get('source_name', ''),
                self.image_path,
                'active'
            ))
            
            # Get the new event ID
            event_id = cursor.lastrowid
            
            # Create associated entities
            self.save_associated_entities(event_id, data)
            
            # Save metadata
            self.save_metadata(event_id, data.get('metadata', {}))
            
            # Commit the transaction
            self.db_manager.conn.commit()
            
            return event_id
            
        except sqlite3.Error as e:
            self.db_manager.conn.rollback()
            raise Exception(f"Database error: {str(e)}")

    def update_event(self, event_id, data):
        """Update an existing event with the given data"""
        try:
            # Update event record
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                UPDATE Events SET
                    EventDate = ?,
                    PublicationDate = ?,
                    EventTitle = ?,
                    EventText = ?,
                    SourceType = ?,
                    SourceName = ?,
                    FilePath = ?,
                    LastModified = CURRENT_TIMESTAMP
                WHERE EventID = ?
            """, (
                data.get('event_date', ''),
                data.get('publication_date', ''),
                data.get('event_title', ''),
                data.get('text_content', ''),
                data.get('source_type', ''),
                data.get('source_name', ''),
                self.image_path,
                event_id
            ))
            
            # Delete existing associations
            cursor.execute("DELETE FROM EventCharacters WHERE EventID = ?", (event_id,))
            cursor.execute("DELETE FROM EventLocations WHERE EventID = ?", (event_id,))
            cursor.execute("DELETE FROM EventEntities WHERE EventID = ?", (event_id,))
            cursor.execute("DELETE FROM EventMetadata WHERE EventID = ?", (event_id,))
            
            # Create new associations
            self.save_associated_entities(event_id, data)
            
            # Save metadata
            self.save_metadata(event_id, data.get('metadata', {}))
            
            # Commit the transaction
            self.db_manager.conn.commit()
            
            return True
            
        except sqlite3.Error as e:
            self.db_manager.conn.rollback()
            raise Exception(f"Database error: {str(e)}")

    def save_associated_entities(self, event_id, data):
        """Save associated entities for an event"""
        cursor = self.db_manager.conn.cursor()
        
        # Save characters
        for char_name in data.get('characters', []):
            char_id = self.entity_panel.get_or_create_character(char_name)
            if char_id:
                cursor.execute("""
                    INSERT INTO EventCharacters (EventID, CharacterID)
                    VALUES (?, ?)
                """, (event_id, char_id))
        
        # Save locations
        for loc_name in data.get('locations', []):
            loc_id = self.entity_panel.get_or_create_location(loc_name)
            if loc_id:
                cursor.execute("""
                    INSERT INTO EventLocations (EventID, LocationID)
                    VALUES (?, ?)
                """, (event_id, loc_id))
        
        # Save entities
        for ent_name in data.get('entities', []):
            ent_id = self.entity_panel.get_or_create_entity(ent_name)
            if ent_id:
                cursor.execute("""
                    INSERT INTO EventEntities (EventID, EntityID)
                    VALUES (?, ?)
                """, (event_id, ent_id))

    def save_metadata(self, event_id, metadata):
        """Save metadata for an event"""
        if not metadata:
            return
            
        cursor = self.db_manager.conn.cursor()
        for key, value in metadata.items():
            cursor.execute("""
                INSERT INTO EventMetadata (EventID, MetadataKey, MetadataValue)
                VALUES (?, ?, ?)
            """, (event_id, key, value))

    def load_event(self, event_id):
        """Load an event from the database"""
        if self.changes_made:
            reply = QMessageBox.question(
                self, "Unsaved Changes", 
                "You have unsaved changes. Do you want to save them before loading?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                # Get current data
                event_data = self.entity_panel.get_event_data()
                # Add text content
                event_data['text_content'] = self.text_panel.get_text()
                # Save data
                self.save_data(event_data)
            elif reply == QMessageBox.Cancel:
                return False
        
        # Load event data into entity panel
        event_id, text, image_path = self.entity_panel.load_event_content(event_id)
        
        if event_id:
            # Update current event ID
            self.current_event_id = event_id
            
            # Load image
            if image_path:
                self.image_path = image_path
                self.document_panel.display_image(image_path)
            
            # Load text
            if text:
                self.text_panel.set_text(text)
            
            # Reset changes flag
            self.changes_made = False
            
            return True
        
        return False

    def load_previous_event(self):
        """Load the previous event"""
        event_id, text, image_path = self.entity_panel.load_previous_event()
        if event_id:
            self.current_event_id = event_id
            
            if image_path:
                self.image_path = image_path
                self.document_panel.display_image(image_path)
            
            if text:
                self.text_panel.set_text(text)
            
            self.changes_made = False

    def load_next_event(self):
        """Load the next event"""
        event_id, text, image_path = self.entity_panel.load_next_event()
        if event_id:
            self.current_event_id = event_id
            
            if image_path:
                self.image_path = image_path
                self.document_panel.display_image(image_path)
            
            if text:
                self.text_panel.set_text(text)
            
            self.changes_made = False

    def recall_last_entry(self):
        """Recall the last entered event"""
        event_id, text, image_path = self.entity_panel.recall_last_entry()
        if event_id:
            self.current_event_id = event_id
            
            if image_path:
                self.image_path = image_path
                self.document_panel.display_image(image_path)
            
            if text:
                self.text_panel.set_text(text)
            
            self.changes_made = False

    def closeEvent(self, event):
        """Handle window close event"""
        if self.changes_made:
            reply = QMessageBox.question(
                self, "Unsaved Changes", 
                "You have unsaved changes. Do you want to save them before exiting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                # Get current data
                event_data = self.entity_panel.get_event_data()
                # Add text content
                event_data['text_content'] = self.text_panel.get_text()
                # Save data
                self.save_data(event_data)
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()