# File: characters_tab.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.character_service import CharacterService, DatabaseError
from ui.components import BaseTab

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QAbstractItemView, QGroupBox, 
                            QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, QMenu, 
                            QAction, QMessageBox, QListWidget, QListWidgetItem, QInputDialog,
                            QDialog, QDialogButtonBox, QFormLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

class CharacterDialog(QDialog):
    def __init__(self, parent=None, character_data=None):
        super().__init__(parent)
        self.character_data = character_data
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Character Details")
        layout = QVBoxLayout(self)

        # Character details form
        form_layout = QFormLayout()

        self.fields = {}
        field_names = ['Prefix', 'FirstName', 'MiddleName', 'LastName', 'Suffix',
                      'DisplayName', 'Aliases', 'Gender', 'BirthDate', 'DeathDate',
                      'Height', 'Weight', 'Hair', 'Eyes', 'Occupation', 'Family',
                      'Affiliations', 'FindAGrave', 'ClifftonStrengths',
                      'Enneagram', 'MyersBriggs']

        for field in field_names:
            self.fields[field] = QLineEdit()
            if self.character_data and field in self.character_data:
                value = self.character_data[field]
                # Only set text if value is not None and not empty
                if value and str(value).strip():
                    self.fields[field].setText(str(value))
            form_layout.addRow(field, self.fields[field])

        # TextEdit fields
        text_fields = ['BackgroundSummary', 'PersonalityTraits']
        for field in text_fields:
            self.fields[field] = QTextEdit()
            if self.character_data and field in self.character_data:
                value = self.character_data[field]
                # Only set text if value is not None and not empty
                if value and str(value).strip():
                    self.fields[field].setPlainText(str(value))
            form_layout.addRow(field, self.fields[field])

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def get_character_data(self):
        """Get the character data from the form fields."""
        data = {}
        for field, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                value = widget.text().strip()
            else:  # QTextEdit
                value = widget.toPlainText().strip()
            data[field] = value if value else None
          
        # Preserve the ImagePath from the original data if it exists
        if self.character_data and 'ImagePath' in self.character_data:
            data['ImagePath'] = self.character_data['ImagePath']
        else:
            data['ImagePath'] = None
        return data

class CharactersTab(BaseTab):
    """
    Tab for managing character information in the database.
    Inherits from BaseTab to use the standardized three-panel layout.
    """
    view_event_signal = pyqtSignal(int)  # Event ID to view
    edit_event_signal = pyqtSignal(int)  # Event ID to edit    
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the characters tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        # Define tab-specific properties
        self.table_headers = ["ID", "Name", "First Name", "Last Name", "Aliases", "Reviewed"]
        
        self.detail_fields = [
            {'name': 'display_name', 'label': 'Display Name:', 'type': 'text'},
            {'name': 'first_name', 'label': 'First Name:', 'type': 'text'},
            {'name': 'middle_name', 'label': 'Middle Name:', 'type': 'text'},
            {'name': 'last_name', 'label': 'Last Name:', 'type': 'text'},
            {'name': 'prefix', 'label': 'Title/Prefix:', 'type': 'text'},
            {'name': 'suffix', 'label': 'Suffix:', 'type': 'text'},
            {'name': 'aliases', 'label': 'Aliases:', 'type': 'text'},
            {'name': 'gender', 'label': 'Gender:', 'type': 'text'},
            {'name': 'birth_date', 'label': 'Birth Date:', 'type': 'text'},
            {'name': 'death_date', 'label': 'Death Date:', 'type': 'text'},
            {'name': 'background_summary', 'label': 'Background:', 'type': 'textarea'}
        ]
        
        self.search_filters = ["All", "Name", "Aliases", "First Name", "Last Name"]
        
        # Create character service
        self.character_service = CharacterService(db_path)
        
        # Initialize the base tab
        super().__init__(db_path, parent)
        
        # Add additional UI components to the right panel AFTER BaseTab initialization
        self.events_list = None  # Initialize to None
        self.setup_right_panel()

    def setup_right_panel(self):
        """Add events list and buttons to the right panel."""
        if not hasattr(self, 'right_panel') or self.right_panel is None:
            # Right panel hasn't been created by BaseTab yet
            return
            
        events_group = QGroupBox("Associated Events")
        events_layout = QVBoxLayout(events_group)
        
        # Events list
        self.events_list = QListWidget()
        self.events_list.itemSelectionChanged.connect(self.on_events_list_selection_changed)
        self.events_list.itemDoubleClicked.connect(self.on_event_double_clicked)
        events_layout.addWidget(self.events_list)
        
        # View event button
        self.view_event_button = QPushButton("View Event")
        self.view_event_button.clicked.connect(self.view_selected_event)
        self.view_event_button.setEnabled(False)
        events_layout.addWidget(self.view_event_button)
        
        # Add events group to the right panel
        self.right_panel.layout().addWidget(events_group)

    def load_character_events(self, character_id):
        """
        Load events associated with a character.
        
        Args:
            character_id: ID of the character
        """
        if not self.events_list:
            return
            
        try:
            # Clear current events
            self.events_list.clear()
            self.view_event_button.setEnabled(False)
            
            # Get events for the character
            events = self.character_service.get_character_events(character_id)
            
            # Add events to the list
            for event in events:
                event_id = event[0]
                event_date = event[1] or "Unknown date"
                event_title = event[2] or "Untitled event"
                
                # Create list item
                item_text = f"{event_date}: {event_title}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, event_id)
                
                self.events_list.addItem(item)
                
        except Exception as e:
            self.show_message("Database Error", f"Error loading character events: {str(e)}", QMessageBox.Critical)

    def on_events_list_selection_changed(self):
        """Handle selection changes in the events list."""
        if not self.events_list:
            return
        selected_items = self.events_list.selectedItems()
        self.view_event_button.setEnabled(len(selected_items) > 0)

    def on_event_double_clicked(self, item):
        """
        Handle double-click on an event item.
        
        Args:
            item: The clicked item
        """
        event_id = item.data(Qt.UserRole)
        if event_id:
            self.edit_event_signal.emit(event_id)

    def view_selected_event(self):
        """View the selected event in the Events tab."""
        if not self.events_list:
            return
        selected_items = self.events_list.selectedItems()
        if selected_items:
            event_id = selected_items[0].data(Qt.UserRole)
            if event_id:
                self.view_event_signal.emit(event_id)        
    
    def load_data(self):
        """Load all characters from the database."""
        try:
            data = self.character_service.get_all_characters()
            self.table_panel.populate_table(data)
        except Exception as e:
            self.show_message("Database Error", f"Error loading characters: {str(e)}", QMessageBox.Critical)
    
    def on_search(self, search_text, filter_value):
        """
        Handle search requests.
        
        Args:
            search_text (str): Text to search for
            filter_value (str): Column to search in
        """
        if not search_text:
            self.load_data()
            return
        
        try:
            data = self.character_service.search_characters(search_text, filter_value)
            self.table_panel.populate_table(data)
        except Exception as e:
            self.show_message("Database Error", f"Error searching characters: {str(e)}", QMessageBox.Critical)
    
    def on_item_selected(self, item_id):
        """
        Handle character selection.
        
        Args:
            item_id (int): ID of the selected character
        """
        try:
            character_data = self.character_service.get_character_by_id(item_id)
            if character_data:
                self.detail_panel.set_data(character_data)
                self.load_character_events(item_id)
        except Exception as e:
            self.show_message("Database Error", f"Error loading character details: {str(e)}", QMessageBox.Critical)
    
    def on_save(self, field_data):
        """
        Handle saving character details.
        
        Args:
            field_data (dict): Field data to save
        """
        try:
            if 'id' in field_data and field_data['id'] is not None:
                # Update existing record
                self.character_service.update_character(field_data['id'], field_data)
                message = f"Character '{field_data['display_name']}' updated successfully."
            else:
                # Insert new record
                self.character_service.create_character(field_data)
                message = f"Character '{field_data['display_name']}' added successfully."
            
            self.load_data()
            self.show_message("Success", message)
        except Exception as e:
            self.show_message("Database Error", f"Error saving character: {str(e)}", QMessageBox.Critical)
    
    def on_delete(self, item_id):
        """
        Handle deleting a character.
        
        Args:
            item_id (int): ID of the character to delete
        """
        try:
            # Get character data for confirmation message
            character_data = self.character_service.get_character_by_id(item_id)
            
            if not character_data:
                return
            
            character_name = character_data['display_name']
            
            # Confirm deletion
            if not self.confirm_action("Confirm Deletion", 
                                       f"Are you sure you want to delete '{character_name}'?"):
                return
            
            # Check for references in other tables
            ref_count = self.character_service.count_character_references(item_id)
            
            if ref_count > 0:
                if not self.confirm_action("References Exist", 
                                          f"This character is referenced in {ref_count} records. "
                                          f"Deleting will remove all references as well. Continue?"):
                    return
                
                # Delete character with all references
                self.character_service.delete_character_with_references(item_id)
            else:
                # Delete just the character
                self.character_service.delete_character(item_id)
            
            self.load_data()
            self.detail_panel.clear_fields()
            self.show_message("Success", f"Character '{character_name}' deleted successfully.")
        
        except Exception as e:
            self.show_message("Database Error", f"Error deleting character: {str(e)}", QMessageBox.Critical)
    
    def on_context_menu(self, position, item_id):
        """
        Show context menu for character.
        
        Args:
            position (QPoint): Position for the context menu
            item_id (int): ID of the character
        """
        menu = QMenu()
        
        # Get character info
        character_data = self.character_service.get_character_by_id(item_id)
        
        if not character_data:
            return
        
        character_name = character_data['display_name']
        
        # Create menu actions
        edit_action = QAction(f"Edit '{character_name}'", self)
        edit_action.triggered.connect(lambda: self.on_item_selected(item_id))
        
        delete_action = QAction(f"Delete '{character_name}'", self)
        delete_action.triggered.connect(lambda: self.on_delete(item_id))
        
        show_refs_action = QAction(f"Show references to '{character_name}'", self)
        show_refs_action.triggered.connect(lambda: self.show_references(item_id, character_name))
        
        # Add actions to menu
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(show_refs_action)
        
        # Show the menu
        menu.exec_(position)
    
    def show_references(self, character_id, character_name):
        """
        Show references to a character.
        
        Args:
            character_id (int): ID of the character
            character_name (str): Name of the character for display
        """
        try:
            refs = self.character_service.get_character_references(character_id)
            
            if not refs:
                self.show_message("References", f"No references found for '{character_name}'.")
                return
            
            # Format references for display
            ref_text = f"References to '{character_name}':\n\n"
            for source, count in refs:
                ref_text += f"• {source}: {count} mentions\n"
            
            # Show in a message box
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Character References")
            msg_box.setText(ref_text)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec_()
            
        except Exception as e:
            self.show_message("Database Error", f"Error retrieving character references: {str(e)}", QMessageBox.Critical)