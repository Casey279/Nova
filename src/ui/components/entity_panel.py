import os
import sys
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QLineEdit, QFormLayout, QGroupBox, 
                            QGridLayout, QDialog, QDialogButtonBox, 
                            QMessageBox, QTextEdit, QListWidget, QListWidgetItem,
                            QCompleter)
from PyQt5.QtCore import Qt, pyqtSignal, QStringListModel
from PyQt5.QtGui import QColor, QBrush

# Import from parent directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database_manager import DatabaseManager


class EntityPanel(QWidget):
    """
    Panel for managing event metadata and entity tagging.
    
    Responsibilities:
    - Event metadata management
    - Associated entities tagging (characters, locations, organizations)
    - Database operations for saving
    """
    
    # Signals
    save_requested = pyqtSignal(dict)  # Emits when save is requested with all data
    metadata_changed = pyqtSignal(dict)  # Emits when metadata changes
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_event_id = None
        self.associated_characters = []
        self.associated_locations = []
        self.associated_entities = []
        self.metadata = {}
        self.changes_made = False
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins
        
        # Navigation
        nav_layout = QHBoxLayout()
        
        recall_button = QPushButton("Recall Last Entered")
        recall_button.clicked.connect(self.recall_last_entry)
        layout.addWidget(recall_button)
        
        prev_button = QPushButton("< Previous")
        prev_button.clicked.connect(self.load_previous_event)
        next_button = QPushButton("Next >")
        next_button.clicked.connect(self.load_next_event)
        
        nav_layout.addWidget(prev_button)
        nav_layout.addWidget(next_button)
        layout.addLayout(nav_layout)
        
        # Metadata button
        metadata_button = QPushButton("Add Additional Metadata")
        metadata_button.clicked.connect(self.open_metadata_dialog)
        layout.addWidget(metadata_button)
        
        # Event ID display
        event_id_layout = QHBoxLayout()
        self.event_id_label = QLabel("Event ID: -")
        self.event_id_label.setStyleSheet(
            "font-weight: bold; color: black; padding: 1px 0px; margin: 0px 0px;"
        )
        event_id_layout.addWidget(self.event_id_label)
        event_id_layout.addStretch()
        layout.addLayout(event_id_layout)
        
        # Event metadata
        form_layout = QFormLayout()
        form_layout.setSpacing(3)  # Reduce vertical spacing
        self.event_date_input = QLineEdit()
        self.publication_date_input = QLineEdit()
        self.event_title_input = QLineEdit()
        self.source_type_input = QLineEdit()
        self.source_name_input = QLineEdit()
        
        form_layout.addRow("Event Date:", self.event_date_input)
        form_layout.addRow("Publication Date:", self.publication_date_input)
        form_layout.addRow("Event Title:", self.event_title_input)
        form_layout.addRow("Source Type:", self.source_type_input)
        form_layout.addRow("Source Name:", self.source_name_input)
        layout.addLayout(form_layout)
        
        # Associated entities sections
        self.characters_widget = self.create_names_section("Characters")
        self.locations_widget = self.create_names_section("Locations")
        self.entities_widget = self.create_names_section("Entities")
        
        layout.addWidget(self.characters_widget)
        layout.addWidget(self.locations_widget)
        layout.addWidget(self.entities_widget)
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.prepare_save)
        layout.addWidget(self.save_button)
    
    def create_names_section(self, title):
        """Create a section for adding/managing entity names"""
        section = QGroupBox(title)
        layout = QVBoxLayout(section)
        
        # Input row
        input_layout = QHBoxLayout()
        name_input = QLineEdit()
        name_input.setPlaceholderText(f"Enter {title.lower()} found in Article")
        name_input.setFixedWidth(250)
        
        # Connect textChanged signal to update suggestions
        name_input.textChanged.connect(
            lambda text_input, title=title, input_widget=name_input:   
            self.update_name_suggestions(text_input, title.lower(), input_widget)
        )
        
        add_button = QPushButton("Add")
        input_layout.addWidget(name_input)
        input_layout.addWidget(add_button)
        layout.addLayout(input_layout)
        
        # Tags container with a grid layout
        tags_container = QWidget()
        tags_layout = QGridLayout(tags_container)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setHorizontalSpacing(10)
        tags_layout.setVerticalSpacing(5)
        layout.addWidget(tags_container)
        
        # Store tags layout reference
        setattr(self, f"{title.lower()}_tags_layout", tags_layout)
        
        # Connect add functionality
        add_button.clicked.connect(lambda: self.add_name_tag(name_input, title.lower()))
        name_input.returnPressed.connect(lambda: self.add_name_tag(name_input, title.lower()))
        
        return section
    
    def update_name_suggestions(self, text_input, category, input_widget):
        """Update the completer with matching names from database."""
        # Create simple completer if it doesn't exist
        if not hasattr(input_widget, 'simple_completer'):
            input_widget.simple_completer = QCompleter([])
            input_widget.simple_completer.setCaseSensitivity(Qt.CaseInsensitive)
            input_widget.simple_completer.setFilterMode(Qt.MatchContains)
            input_widget.setCompleter(input_widget.simple_completer)
        
        try:
            # Only query if we have text
            if text_input and text_input.strip():
                matches = []
                
                # Query appropriate table based on category
                if category == 'characters':
                    self.db_manager.cursor.execute("""
                        SELECT DisplayName FROM Characters 
                        WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR Aliases LIKE ?
                    """, (f"%{text_input}%", f"%{text_input}%", f"%{text_input}%", f"%{text_input}%"))
                    
                elif category == 'locations':
                    self.db_manager.cursor.execute("""
                        SELECT DisplayName FROM Locations 
                        WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ?
                    """, (f"%{text_input}%", f"%{text_input}%", f"%{text_input}%"))
                    
                elif category == 'entities':
                    self.db_manager.cursor.execute("""
                        SELECT DisplayName FROM Entities 
                        WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ?
                    """, (f"%{text_input}%", f"%{text_input}%", f"%{text_input}%"))
                
                # Get all matches
                for row in self.db_manager.cursor.fetchall():
                    if row[0]:
                        matches.append(row[0])
                
                # Update the completer's model with the matches
                model = QStringListModel(matches)
                input_widget.simple_completer.setModel(model)
                
                # Force completion on first character
                if len(text_input) == 1:
                    input_widget.simple_completer.complete()
        
        except Exception as e:
            print(f"Error in update_name_suggestions: {str(e)}")
    
    def add_name_tag(self, input_widget, category):
        """Add a name tag to the appropriate section"""
        # Retrieve the name from the input widget
        name = input_widget.text().strip()
        if name:
            # Create a tag container for the tag's visual appearance
            tag_container = QWidget()
            tag_layout = QHBoxLayout(tag_container)
            tag_layout.setContentsMargins(0, 0, 0, 0)
            tag_layout.setSpacing(5)
            
            # Create the tag button with DisplayName
            tag_button = QPushButton(name)
            tag_button.setStyleSheet("border-radius: 10px; padding: 5px; background-color: lightgray;")
            tag_button.setFlat(True)
            
            # Create remove button
            remove_button = QPushButton("X")
            remove_button.setStyleSheet("background: none; color: red; font-weight: bold;")
            remove_button.setFixedSize(15, 15)
            remove_button.clicked.connect(lambda: self.remove_name_tag(tag_container, category, name))
            
            # Add tag button and remove button to the tag layout
            tag_layout.addWidget(tag_button)
            tag_layout.addWidget(remove_button)
            
            # Add tag container to the grid layout for the category
            tags_layout = getattr(self, f"{category}_tags_layout")
            current_count = tags_layout.count()
            row = current_count // 3  # Calculate the row based on current count and max columns (3)
            col = current_count % 3  # Calculate the column based on current count and max columns (3)
            tags_layout.addWidget(tag_container, row, col)
            
            # Add name to associated list
            associated_list = getattr(self, f"associated_{category}")
            if name not in associated_list:
                associated_list.append(name)
            
            # Mark changes
            self.changes_made = True
            
            # Clear input field
            input_widget.clear()
    
    def remove_name_tag(self, tag_container, category, name):
        """Remove a name tag from the UI and associated lists"""
        # Remove from UI
        tags_layout = getattr(self, f"{category}_tags_layout")
        tags_layout.removeWidget(tag_container)
        tag_container.deleteLater()
        
        # Remove from associated list
        associated_list = getattr(self, f"associated_{category}")
        if name in associated_list:
            associated_list.remove(name)
        
        # Reorganize remaining tags
        self.reorganize_grid_layout(tags_layout)
        
        # Mark changes
        self.changes_made = True
    
    def reorganize_grid_layout(self, grid_layout):
        """Reorganize widgets in a grid layout after removing items"""
        widgets = []
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widgets.append(widget)
        
        # Clear the layout
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        
        # Re-add widgets to the layout in a 3-wide grid
        for index, widget in enumerate(widgets):
            row = index // 3
            col = index % 3
            grid_layout.addWidget(widget, row, col)
    
    def get_or_create_character(self, character_name):
        """Get character ID from database or create new character if needed."""
        try:
            # First check if character exists
            character_id = self.db_manager.get_character_id_by_name(character_name)
            if character_id:
                return character_id
            
            # If not found, create in permanent table with reviewed=0
            print(f"Creating new character '{character_name}' in permanent table")
            
            # Parse name into first/last if possible
            name_parts = character_name.split()
            if len(name_parts) > 1:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
            else:
                first_name = character_name
                last_name = ""
                
            # Insert new character
            character_id = self.db_manager.insert_character(
                display_name=character_name,
                first_name=first_name,
                last_name=last_name,
                reviewed=0  # Mark as needing review
            )
            print(f"Created character '{character_name}' with ID {character_id}")
            return character_id
                
        except Exception as e:
            print(f"Error in get_or_create_character: {str(e)}")
            return None
    
    def get_or_create_location(self, location_name):
        """Get location ID from database or create new location if needed."""
        try:
            # First check if location exists
            location_id = self.db_manager.get_location_id_by_name(location_name)
            if location_id:
                return location_id
            
            # If not found, create in permanent table with review status
            print(f"Creating new location '{location_name}' in permanent table")
            location_id = self.db_manager.insert_location(
                location_name=location_name,
                review_status='needs_review'
            )
            print(f"Created location '{location_name}' with ID {location_id}")
            return location_id
                
        except Exception as e:
            print(f"Error in get_or_create_location: {str(e)}")
            return None
    
    def get_or_create_entity(self, entity_name):
        """Get entity ID from database or create new entity if needed."""
        try:
            # First check if entity exists
            entity_id = self.db_manager.get_entity_id_by_name(entity_name)
            if entity_id:
                return entity_id
            
            # If not found, create in permanent table with review status
            print(f"Creating new entity '{entity_name}' in permanent table")
            entity_id = self.db_manager.insert_entity(
                entity_name=entity_name,
                review_status='needs_review'
            )
            print(f"Created entity '{entity_name}' with ID {entity_id}")
            return entity_id
                
        except Exception as e:
            print(f"Error in get_or_create_entity: {str(e)}")
            return None
    
    def get_or_create_source(self, source_name, source_type='N'):
        """Get source ID from database or create new source if needed."""
        try:
            # First check if source exists
            source_id = self.db_manager.check_source_exists(source_name)
            if source_id:
                return source_id
            
            # If not found, create
            print(f"Creating new source '{source_name}' in database")
            source_id = self.db_manager.add_preliminary_source(source_name)
            print(f"Created source '{source_name}' with ID {source_id}")
            return source_id
                
        except Exception as e:
            print(f"Error in get_or_create_source: {str(e)}")
            return None
    
    def prepare_save(self):
        """Prepare to save the current event data"""
        # Validate required fields
        if not self.event_title_input.text():
            QMessageBox.warning(self, "Missing Data", "Event title is required")
            return
            
        if not self.event_date_input.text():
            QMessageBox.warning(self, "Missing Data", "Event date is required")
            return
        
        # Check if source exists or needs to be created
        source_name = self.source_name_input.text()
        if source_name:
            source_id = self.get_or_create_source(source_name)
            if not source_id:
                QMessageBox.warning(self, "Source Error", f"Could not create source: {source_name}")
                return
        
        # Collect event data
        event_data = {
            'event_id': self.current_event_id,
            'event_date': self.event_date_input.text(),
            'publication_date': self.publication_date_input.text(),
            'event_title': self.event_title_input.text(),
            'source_type': self.source_type_input.text(),
            'source_name': self.source_name_input.text(),
            'characters': self.associated_characters,
            'locations': self.associated_locations,
            'entities': self.associated_entities,
            'metadata': self.metadata
        }
        
        # Show confirmation dialog
        save_info = self.prepare_save_dialog(not self.current_event_id)
        if save_info.exec_() == QDialog.Accepted:
            # Emit save signal with data
            self.save_requested.emit(event_data)
        
    def prepare_save_dialog(self, is_new_event):
        """Create a dialog to confirm save operation"""
        save_info = QDialog(self)
        save_info.setWindowTitle("Confirm Save")
        layout = QVBoxLayout(save_info)
        
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        
        # Display event ID and save type
        save_details = [f"Event ID: {'(New Event)' if is_new_event else self.current_event_id}"]
        save_details.append("\nThe following information will be saved:\n")
        
        # Add main event details
        save_details.extend([
            "\nEvent Details:",
            f"- Event Date: {self.event_date_input.text()}",
            f"- Publication Date: {self.publication_date_input.text()}",
            f"- Title: {self.event_title_input.text()}",
            f"- Source Type: {self.source_type_input.text()}",
            f"- Source Name: {self.source_name_input.text()}\n"
        ])
        
        # Add associated items
        if self.associated_characters:
            save_details.append("\nCharacters:")
            for char in self.associated_characters:
                save_details.append(f"- {char}")
        
        if self.associated_locations:
            save_details.append("\nLocations:")
            for loc in self.associated_locations:
                save_details.append(f"- {loc}")
        
        if self.associated_entities:
            save_details.append("\nEntities:")
            for ent in self.associated_entities:
                save_details.append(f"- {ent}")
        
        # Add metadata
        if self.metadata:
            save_details.append("\nAdditional Metadata:")
            for key, value in self.metadata.items():
                save_details.append(f"- {key}: {value}")
        
        info_text.setText("\n".join(save_details))
        info_text.setMinimumSize(400, 300)
        layout.addWidget(info_text)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(save_info.accept)
        button_box.rejected.connect(save_info.reject)
        layout.addWidget(button_box)
        
        return save_info
    
    def set_event_data(self, event_id, text_content, image_path, event_data=None):
        """Set event data from main controller"""
        # Clear current data
        self.clear_all_fields()
        
        self.current_event_id = event_id
        self.event_id_label.setText(f"Event ID: {event_id or '-'}")
        
        if event_data:
            # Set basic fields
            self.event_date_input.setText(event_data.get('event_date', ''))
            self.publication_date_input.setText(event_data.get('publication_date', ''))
            self.event_title_input.setText(event_data.get('event_title', ''))
            self.source_type_input.setText(event_data.get('source_type', ''))
            self.source_name_input.setText(event_data.get('source_name', ''))
            
            # Set associated items
            self.associated_characters = event_data.get('characters', [])
            self.associated_locations = event_data.get('locations', [])
            self.associated_entities = event_data.get('entities', [])
            
            # Update UI for associated items
            self.update_tags_ui()
            
            # Set metadata
            self.metadata = event_data.get('metadata', {})
        
        # Reset changes flag
        self.changes_made = False
    
    def update_tags_ui(self):
        """Update the UI to display all associated tags"""
        # Clear existing tags
        for category in ['characters', 'locations', 'entities']:
            tags_layout = getattr(self, f"{category}_tags_layout")
            while tags_layout.count():
                item = tags_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Add characters
        for name in self.associated_characters:
            self.add_name_tag(QLineEdit(name), 'characters')
        
        # Add locations
        for name in self.associated_locations:
            self.add_name_tag(QLineEdit(name), 'locations')
        
        # Add entities
        for name in self.associated_entities:
            self.add_name_tag(QLineEdit(name), 'entities')
        
        # Reset changes flag after update (not a real change)
        self.changes_made = False
    
    def get_event_data(self):
        """Get current event data"""
        return {
            'event_id': self.current_event_id,
            'event_date': self.event_date_input.text(),
            'publication_date': self.publication_date_input.text(),
            'event_title': self.event_title_input.text(),
            'source_type': self.source_type_input.text(),
            'source_name': self.source_name_input.text(),
            'characters': self.associated_characters,
            'locations': self.associated_locations,
            'entities': self.associated_entities,
            'metadata': self.metadata
        }
    
    def clear_all_fields(self):
        """Clear all input fields"""
        # Clear text fields
        self.event_date_input.clear()
        self.publication_date_input.clear()
        self.event_title_input.clear()
        self.source_type_input.clear()
        self.source_name_input.clear()
        
        # Clear associated items
        for category in ['characters', 'locations', 'entities']:
            tags_layout = getattr(self, f"{category}_tags_layout")
            while tags_layout.count():
                item = tags_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            
            # Clear associated lists
            getattr(self, f'associated_{category}').clear()
        
        # Clear metadata
        self.metadata.clear()
        
        # Reset current event ID
        self.current_event_id = None
        self.event_id_label.setText("Event ID: -")
        
        # Reset changes flag
        self.changes_made = False
    
    def open_metadata_dialog(self):
        """Open dialog to add additional metadata"""
        metadata_dialog = QDialog()
        metadata_dialog.setWindowTitle("Add Additional Metadata")
        layout = QFormLayout()
        
        # Create a dictionary to store the input fields
        input_fields = {}
        
        # Event Date (read-only)
        event_date = QLineEdit(self.event_date_input.text())
        event_date.setReadOnly(True)
        layout.addRow("Event Date:", event_date)
        
        # Add other fields
        fields = [
            ('publication_date', "Publication Date (if different than Event Date):"),
            ('journal_title', "Journal/Book Title:"),
            ('volume', "Volume/Edition:"),
            ('issue_number', "Issue Number:"),
            ('page_number', "Page Number:"),
            ('column_number', "Column Number:"),
            ('authors', "Author(s):"),
            ('doi_url', "DOI or URL:"),
            ('archive_location', "Archive Location:")
        ]
        
        for field, label in fields:
            input_fields[field] = QLineEdit(self.metadata.get(field, ''))
            layout.addRow(label, input_fields[field])
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(metadata_dialog.accept)
        button_box.rejected.connect(metadata_dialog.reject)
        layout.addWidget(button_box)
        
        metadata_dialog.setLayout(layout)
        
        if metadata_dialog.exec_() == QDialog.Accepted:
            for field, input_widget in input_fields.items():
                if input_widget.text():
                    self.metadata[field] = input_widget.text()
            
            # Emit metadata changed signal
            self.metadata_changed.emit(self.metadata)
            self.changes_made = True
            QMessageBox.information(self, "Metadata Ready", "Metadata has been prepared for saving.")
    
    def load_event_content(self, event_id):
        """Load event content from database"""
        try:
            # Set event to editing status
            self.db_manager.cursor.execute("""
                UPDATE Events 
                SET Status = 'editing' 
                WHERE EventID = ? AND Status = 'active'
            """, (event_id,))
            self.db_manager.conn.commit()
            
            # Load event data
            self.db_manager.cursor.execute("""
                SELECT EventDate, PublicationDate, EventTitle, EventText, 
                    SourceType, SourceName, FilePath, QualityScore
                FROM Events 
                WHERE EventID = ?
            """, (event_id,))
            event_data = self.db_manager.cursor.fetchone()
            
            if event_data:
                self.current_event_id = event_id
                self.event_id_label.setText(f"Event ID: {event_id}")
                
                # Load basic event details
                self.event_date_input.setText(event_data[0] or '')
                self.publication_date_input.setText(event_data[1] or '')
                self.event_title_input.setText(event_data[2] or '')
                self.source_type_input.setText(event_data[4] or '')
                self.source_name_input.setText(event_data[5] or '')
                
                # Load associated tags
                self.load_associated_tags(event_id)
                
                # Reset change tracking
                self.changes_made = False
                
                return event_data[3], event_data[6]  # Return text and image path
                
        except sqlite3.Error as e:
            print(f"Error loading event: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load event: {e}")
            return None, None
    
    def load_associated_tags(self, event_id):
        """Load associated tags for the event"""
        try:
            # Clear existing associations
            self.associated_characters.clear()
            self.associated_locations.clear()
            self.associated_entities.clear()
            
            # Load characters
            self.db_manager.cursor.execute("""
                SELECT c.DisplayName
                FROM EventCharacters ec
                JOIN Characters c ON ec.CharacterID = c.CharacterID
                WHERE ec.EventID = ?
            """, (event_id,))
            
            for row in self.db_manager.cursor.fetchall():
                self.associated_characters.append(row[0])
            
            # Load locations
            self.db_manager.cursor.execute("""
                SELECT l.DisplayName
                FROM EventLocations el
                JOIN Locations l ON el.LocationID = l.LocationID
                WHERE el.EventID = ?
            """, (event_id,))
            
            for row in self.db_manager.cursor.fetchall():
                self.associated_locations.append(row[0])
            
            # Load entities
            self.db_manager.cursor.execute("""
                SELECT e.DisplayName
                FROM EventEntities ee
                JOIN Entities e ON ee.EntityID = e.EntityID
                WHERE ee.EventID = ?
            """, (event_id,))
            
            for row in self.db_manager.cursor.fetchall():
                self.associated_entities.append(row[0])
            
            # Load metadata
            self.db_manager.cursor.execute("""
                SELECT MetadataKey, MetadataValue 
                FROM EventMetadata
                WHERE EventID = ?
            """, (event_id,))
            
            self.metadata = {}
            for key, value in self.db_manager.cursor.fetchall():
                self.metadata[key] = value
            
            # Update UI
            self.update_tags_ui()
            
        except sqlite3.Error as e:
            print(f"Error loading associated tags: {e}")
    
    def recall_last_entry(self):
        """Load the most recently entered event"""
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT EventID FROM Events ORDER BY EventID DESC LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                text, image_path = self.load_event_content(result[0])
                return result[0], text, image_path
            else:
                QMessageBox.information(self, "No Entries", "No entries are available to recall.")
                return None, None, None
                
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Database Error", f"Failed to recall last entry: {str(e)}")
            return None, None, None
    
    def load_previous_event(self):
        """Load the previous event in the database"""
        if not self.current_event_id:
            QMessageBox.information(self, "No Event", "No event is currently loaded.")
            return None, None, None
        
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT EventID FROM Events 
                WHERE EventID < ? 
                ORDER BY EventID DESC LIMIT 1
            """, (self.current_event_id,))
            result = cursor.fetchone()
            
            if result:
                text, image_path = self.load_event_content(result[0])
                return result[0], text, image_path
            else:
                QMessageBox.information(self, "No More Events", "This is the first event in the database.")
                return None, None, None
                
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Database Error", f"Failed to load previous event: {str(e)}")
            return None, None, None
    
    def load_next_event(self):
        """Load the next event in the database"""
        if not self.current_event_id:
            QMessageBox.information(self, "No Event", "No event is currently loaded.")
            return None, None, None
        
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT EventID FROM Events 
                WHERE EventID > ? 
                ORDER BY EventID ASC LIMIT 1
            """, (self.current_event_id,))
            result = cursor.fetchone()
            
            if result:
                text, image_path = self.load_event_content(result[0])
                return result[0], text, image_path
            else:
                QMessageBox.information(self, "No More Events", "This is the last event in the database.")
                return None, None, None
                
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Database Error", f"Failed to load next event: {str(e)}")
            return None, None, None
    
    def add_detected_names(self, names):
        """Add detected names from OCR processing"""
        for name in names:
            # Try to determine category based on database lookup
            category = self.guess_name_category(name)
            if category:
                # Add to the appropriate category
                self.add_name_tag(QLineEdit(name), category)
    
    def guess_name_category(self, name):
        """Guess the category of a name based on database lookup"""
        try:
            # Check if it's a character
            self.db_manager.cursor.execute("""
                SELECT COUNT(*) FROM Characters 
                WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR Aliases LIKE ?
            """, (f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%"))
            if self.db_manager.cursor.fetchone()[0] > 0:
                return 'characters'
            
            # Check if it's a location
            self.db_manager.cursor.execute("""
                SELECT COUNT(*) FROM Locations 
                WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ?
            """, (f"%{name}%", f"%{name}%", f"%{name}%"))
            if self.db_manager.cursor.fetchone()[0] > 0:
                return 'locations'
            
            # Check if it's an entity
            self.db_manager.cursor.execute("""
                SELECT COUNT(*) FROM Entities 
                WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ?
            """, (f"%{name}%", f"%{name}%", f"%{name}%"))
            if self.db_manager.cursor.fetchone()[0] > 0:
                return 'entities'
            
            # Default to characters if no match found
            return 'characters'
            
        except Exception as e:
            print(f"Error in guess_name_category: {str(e)}")
            return 'characters'  # Default to characters on error