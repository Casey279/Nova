# File: characters_tab.py

import os
import sqlite3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
                             QLabel, QLineEdit, QTextEdit, QFormLayout, QScrollArea, QDialogButtonBox,
                             QListWidgetItem, QFileDialog, QMessageBox, QFrame, QComboBox,
                             QDialog)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from ui.components.base_tab import BaseTab
from ui.components.table_panel import TablePanel
from ui.components.detail_panel import DetailPanel
from ui.components.search_panel import SearchPanel
from services.character_service import CharacterService

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
        self.service = CharacterService(db_path)
        self.current_character_id = None
        super().__init__(db_path, parent)
        
        # Additional setup after UI initialization
        self.load_characters()
        QTimer.singleShot(0, self.setup_additional_connections)
    
    def setup_additional_connections(self):
        """Set up additional connections after UI initialization."""
        # Connect table selection to detail display
        if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'table'):
            self.table_panel.table.itemClicked.connect(self.display_character_details)
        
        # Make sure edit buttons are wired up
        if hasattr(self, 'detail_panel'):
            if hasattr(self.detail_panel, 'edit_button'):
                self.detail_panel.edit_button.clicked.connect(self.edit_character)
            if hasattr(self.detail_panel, 'mark_reviewed_button'):
                self.detail_panel.mark_reviewed_button.clicked.connect(self.mark_character_reviewed)
    
    def create_left_panel(self):
        """Create the left panel with character list and controls."""
        # Create a wrapper widget to hold the table panel
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # View dropdown for filtering characters
        view_layout = QHBoxLayout()
        view_layout.addWidget(QLabel("View:"))
        self.view_dropdown = QComboBox()
        self.view_dropdown.addItems(["All Characters", "Primary Characters", "Secondary Characters", "Tertiary Characters", "Quaternary Characters"])
        self.view_dropdown.currentTextChanged.connect(self.load_characters)
        view_layout.addWidget(self.view_dropdown)
        layout.addLayout(view_layout)
        
        # Create table panel for character list
        self.table_panel = TablePanel(
            headers=["Character Name"],
            data=[],
            item_double_clicked=self.display_character_details
        )
        layout.addWidget(self.table_panel)
        
        # Add buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add New Character")
        add_button.clicked.connect(self.add_new_character)
        button_layout.addWidget(add_button)
        
        delete_button = QPushButton("Delete Character")
        delete_button.clicked.connect(self.delete_character)
        button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
        
        return left_widget
    
    def create_middle_panel(self):
        """Create the middle panel with character details."""
        # Create detail panel for character information
        self.detail_panel = QWidget()
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(5, 5, 5, 5)
        
        # Display Name at the top
        self.display_name_label = QLabel()
        self.display_name_label.setAlignment(Qt.AlignCenter)
        self.display_name_label.setFont(QFont("Arial", 16, QFont.Bold))
        detail_layout.addWidget(self.display_name_label)
        
        # Upper Section: Image and Vitals
        upper_section = QFrame()
        upper_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        upper_section.setLineWidth(2)
        upper_layout = QHBoxLayout(upper_section)
        
        # Create image section
        self.image_section = self.create_image_section()
        upper_layout.addWidget(self.image_section)
        
        # Create and store vitals section (initialize as empty container)
        self.vitals_section_container = QWidget()
        self.vitals_section_layout = QVBoxLayout(self.vitals_section_container)
        
        # Add an empty placeholder for vitals initially
        self.vitals_section = QLabel("No character selected")  # Placeholder text
        self.vitals_section_layout.addWidget(self.vitals_section)
        
        upper_layout.addWidget(self.vitals_section_container)
        
        detail_layout.addWidget(upper_section)
        
        # Lower Section: Additional Information
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.lower_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        detail_layout.addWidget(self.scroll_area)
        
        # Buttons: Edit Character and Mark Reviewed
        button_layout = QHBoxLayout()
        
        # Edit Character button
        self.edit_character_button = QPushButton("Edit Character")
        self.edit_character_button.clicked.connect(self.edit_character)
        button_layout.addWidget(self.edit_character_button)
        
        # Mark Reviewed button
        self.mark_reviewed_button = QPushButton("Mark Reviewed")
        self.mark_reviewed_button.clicked.connect(self.mark_character_reviewed)
        button_layout.addWidget(self.mark_reviewed_button)
        
        detail_layout.addLayout(button_layout)
        
        return self.detail_panel
    
    def create_right_panel(self):
        """Create the right panel with associated articles."""
        # Create a wrapper widget for the right panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # Label for the article list
        right_layout.addWidget(QLabel("Associated Articles:"))
        
        # Associated articles list
        self.article_list = QListWidget()
        self.article_list.itemClicked.connect(self.display_article_content)
        right_layout.addWidget(self.article_list)
        
        # Date filtering section
        filter_label = QLabel("Filter Articles by Date:")
        right_layout.addWidget(filter_label)
        
        # Date filtering inputs
        date_filter_layout = QVBoxLayout()
        
        # Start Date Section
        start_date_layout = QHBoxLayout()
        start_date_layout.addWidget(QLabel("Start Date:"))
        
        self.start_year_edit = QLineEdit()
        self.start_year_edit.setPlaceholderText("YYYY")
        self.start_year_edit.setFixedWidth(60)
        self.start_month_edit = QLineEdit()
        self.start_month_edit.setPlaceholderText("MM")
        self.start_month_edit.setFixedWidth(40)
        self.start_day_edit = QLineEdit()
        self.start_day_edit.setPlaceholderText("DD")
        self.start_day_edit.setFixedWidth(40)
        
        start_date_layout.addWidget(self.start_year_edit)
        start_date_layout.addWidget(self.start_month_edit)
        start_date_layout.addWidget(self.start_day_edit)
        date_filter_layout.addLayout(start_date_layout)
        
        # End Date Section
        end_date_layout = QHBoxLayout()
        end_date_layout.addWidget(QLabel("End Date:"))
        
        self.end_year_edit = QLineEdit()
        self.end_year_edit.setPlaceholderText("YYYY")
        self.end_year_edit.setFixedWidth(60)
        self.end_month_edit = QLineEdit()
        self.end_month_edit.setPlaceholderText("MM")
        self.end_month_edit.setFixedWidth(40)
        self.end_day_edit = QLineEdit()
        self.end_day_edit.setPlaceholderText("DD")
        self.end_day_edit.setFixedWidth(40)
        
        end_date_layout.addWidget(self.end_year_edit)
        end_date_layout.addWidget(self.end_month_edit)
        end_date_layout.addWidget(self.end_day_edit)
        date_filter_layout.addLayout(end_date_layout)
        
        # Filter buttons
        filter_buttons_layout = QHBoxLayout()
        apply_filter_button = QPushButton("Apply Date Filter")
        apply_filter_button.clicked.connect(self.apply_date_filter)
        filter_buttons_layout.addWidget(apply_filter_button)
        
        self.clear_date_filter_button = QPushButton("Clear Filter")
        self.clear_date_filter_button.clicked.connect(self.clear_date_filter)
        filter_buttons_layout.addWidget(self.clear_date_filter_button)
        
        date_filter_layout.addLayout(filter_buttons_layout)
        right_layout.addLayout(date_filter_layout)
        
        # Article text viewer
        self.article_text_view = QTextEdit()
        self.article_text_view.setReadOnly(True)
        right_layout.addWidget(self.article_text_view)
        
        # Clear Viewer Button
        self.clear_viewer_button = QPushButton("Clear Viewer")
        self.clear_viewer_button.clicked.connect(self.clear_viewer)
        right_layout.addWidget(self.clear_viewer_button)
        
        return right_widget
    
    def create_image_section(self, character_dict=None):
        """Create the image section of the profile."""
        image_widget = QWidget()
        layout = QVBoxLayout(image_widget)
        
        # Image Display
        self.image_label = QLabel()
        self.image_label.setFixedSize(200, 200)
        if character_dict and character_dict.get('ImagePath'):
            pixmap = QPixmap(character_dict['ImagePath'])
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.image_label.setText("No Image")
            self.image_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.image_label)
        
        # Change Photo Button
        change_photo_button = QPushButton("Change Photo")
        change_photo_button.clicked.connect(self.change_photo)
        layout.addWidget(change_photo_button)
        
        # Current Level Display
        self.current_level_label = QLabel("Current Level: Tertiary")  # Default value
        self.current_level_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(self.current_level_label)
        
        # Dropdown for Changing Level
        self.level_dropdown = QComboBox()
        self.level_dropdown.addItems(["Change Level", "Primary", "Secondary", "Tertiary", "Quaternary"])
        self.level_dropdown.setCurrentIndex(0)  # Default to "Change Level"
        self.level_dropdown.currentTextChanged.connect(self.change_character_level)
        layout.addWidget(self.level_dropdown)
        
        return image_widget
    
    def create_vitals_section(self, character_dict=None):
        """Create the vitals section for character details."""
        vitals_widget = QWidget()
        layout = QFormLayout(vitals_widget)
        layout.setVerticalSpacing(10)
        
        fields = [
            ('Name', lambda d: f"{d.get('FirstName', '')} {d.get('MiddleName', '') if d.get('MiddleName') else ''} {d.get('LastName', '')}".strip()),
            ('Aliases', 'Aliases'),
            ('Gender', 'Gender'),
            ('BirthDate', 'BirthDate'),
            ('DeathDate', 'DeathDate'),
            ('Height', 'Height'),
            ('Weight', 'Weight'),
            ('Eyes', 'Eyes'),
            ('Hair', 'Hair'),
            ('Occupation', 'Occupation')
        ]
        
        for label, field in fields:
            field_label = QLabel(f"{label}:")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            
            if label == 'Aliases':
                aliases_text = QTextEdit()
                if character_dict:
                    aliases_text.setPlainText(str(character_dict.get(field, '')))
                aliases_text.setReadOnly(True)
                aliases_text.setMaximumHeight(40)
                layout.addRow(field_label, aliases_text)
            else:
                field_value = QLabel()
                if character_dict:
                    if callable(field):
                        value = field(character_dict)
                    else:
                        value = str(character_dict.get(field, ''))
                    field_value.setText(value)
                field_value.setWordWrap(True)
                layout.addRow(field_label, field_value)
        
        return vitals_widget
    
    def load_characters(self, view=None):
        """Load characters into the left panel, filtering based on the selected view."""
        view = view or self.view_dropdown.currentText()
        
        try:
            # Get characters from service
            if view == "All Characters":
                characters = self.service.get_all_characters()
            else:
                level_map = {
                    "Primary Characters": "Primary",
                    "Secondary Characters": "Secondary",
                    "Tertiary Characters": "Tertiary",
                    "Quaternary Characters": "Quaternary"
                }
                level = level_map.get(view)
                characters = self.service.get_characters_by_level(level)
            
            # Clear and populate the table
            if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'table'):
                self.table_panel.clear()
                
                for character in characters:
                    item = QListWidgetItem(character['DisplayName'])
                    item.setData(Qt.UserRole, character['CharacterID'])
                    
                    # Highlight unreviewed characters in red
                    if character.get('Reviewed', 0) == 0:
                        item.setForeground(Qt.red)
                    
                    self.table_panel.table.addItem(item)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load characters: {str(e)}")
    
    def display_character_details(self, item):
        """Display the details of the selected character in the center panel."""
        if not item:
            return
        
        previous_character_id = self.current_character_id
        self.current_character_id = item.data(Qt.UserRole)
        
        try:
            character = self.service.get_character_by_id(self.current_character_id)
            
            if not character:
                QMessageBox.warning(self, "Character Not Found", "Selected character could not be found.")
                return
            
            # Clear previous content if changing character
            if previous_character_id != self.current_character_id:
                self.clear_layout(self.lower_layout)
                self.article_text_view.clear()
            
            # Update display name
            self.display_name_label.setText(character.get('DisplayName', 'Unknown'))
            
            # Update image
            if character.get('ImagePath'):
                pixmap = QPixmap(character['ImagePath'])
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.image_label.clear()
                self.image_label.setText("No Image")
                self.image_label.setAlignment(Qt.AlignCenter)
            
            # Update the current level label
            current_level = self.service.get_character_level(self.current_character_id)
            self.current_level_label.setText(f"Current Level: {current_level}")
            
            # Reset the dropdown to "Change Level"
            self.level_dropdown.setCurrentIndex(0)
            
            # Update the vitals section
            self.update_vitals_section(character)
            
            # Add additional fields
            self.add_additional_fields(self.lower_layout, character)
            
            # Load associated articles
            self.load_associated_articles()
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to display character details: {str(e)}")
    
    def update_vitals_section(self, character_dict):
        """Update the vitals section with the latest character details."""
        # Clear the vitals section layout before updating
        self.clear_layout(self.vitals_section_layout)
        
        # Create a new vitals section with updated character data
        self.vitals_section = self.create_vitals_section(character_dict)
        
        # Add the updated vitals section to the container
        self.vitals_section_layout.addWidget(self.vitals_section)
    
    def add_additional_fields(self, layout, character_dict):
        """Add additional character information fields to the layout."""
        # Define fields to display
        fields = [
            ('Affiliations', 'Affiliations'), 
            ('BackgroundSummary', 'Background'), 
            ('PersonalityTraits', 'Personality Traits'), 
            ('Family', 'Family'), 
            ('FindAGrave', 'Find A Grave')
        ]
        
        for field in fields:
            field_name = field[1] if isinstance(field, tuple) else field
            db_field = field[0] if isinstance(field, tuple) else field
            
            # Create label
            field_label = QLabel(f"<b>{field_name}:</b>")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            layout.addWidget(field_label)
            
            # Create value label
            value = character_dict.get(db_field, '')
            if value:
                value_label = QLabel(value)
                value_label.setWordWrap(True)
                value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                layout.addWidget(value_label)
            else:
                value_label = QLabel("Not specified")
                value_label.setStyleSheet("color: gray;")
                layout.addWidget(value_label)
            
            layout.addSpacing(10)
    
    # In CharactersTab class, update the load_associated_articles method to display the date correctly

    def load_associated_articles(self):
        """Load articles associated with the selected character."""
        self.article_list.clear()
        if not self.current_character_id:
            return
        
        try:
            associated_articles = self.service.get_associated_articles(self.current_character_id)
            
            for article in associated_articles:
                # Get the publication date as the primary display date
                display_date = article.get('PublicationDate', 'No Date')
                title = article.get('EventTitle', 'Untitled')
                
                # Format: "YYYY-MM-DD Title"
                item = QListWidgetItem(f"{display_date} {title}")
                item.setData(Qt.UserRole, article.get('EventID'))
                item.setData(Qt.UserRole + 1, article.get('EventText', ''))
                self.article_list.addItem(item)
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load associated articles: {str(e)}")

    def apply_date_filter(self):
        """Apply the date range filter to the associated articles list."""
        if not self.current_character_id:
            return
        
        start_date = None
        if self.start_year_edit.text():
            start_date = f"{self.start_year_edit.text()}"
            if self.start_month_edit.text():
                start_date += f"-{self.start_month_edit.text().zfill(2)}"
                if self.start_day_edit.text():
                    start_date += f"-{self.start_day_edit.text().zfill(2)}"
        
        end_date = None
        if self.end_year_edit.text():
            end_date = f"{self.end_year_edit.text()}"
            if self.end_month_edit.text():
                end_date += f"-{self.end_month_edit.text().zfill(2)}"
                if self.end_day_edit.text():
                    end_date += f"-{self.end_day_edit.text().zfill(2)}"
        
        try:
            filtered_articles = self.service.get_articles_by_character_and_date(
                self.current_character_id, start_date, end_date)
            
            self.article_list.clear()
            for article in filtered_articles:
                # Get the date in YYYY-MM-DD format
                date = article.get('EventDate', 'No Date')
                # Format only if the date exists
                if date and date != 'No Date':
                    # Ensure the date is properly formatted even if it's partial
                    date_parts = date.split('-')
                    if len(date_parts) >= 1:
                        formatted_date = date_parts[0]  # At least year
                        if len(date_parts) >= 2:
                            formatted_date += f"-{date_parts[1].zfill(2)}"  # Add month with zero padding
                            if len(date_parts) >= 3:
                                formatted_date += f"-{date_parts[2].zfill(2)}"  # Add day with zero padding
                        date = formatted_date
                
                title = article.get('EventTitle', 'Untitled')
                # Format: "YYYY-MM-DD Title"
                item = QListWidgetItem(f"{date} {title}")
                item.setData(Qt.UserRole, article.get('EventID'))
                item.setData(Qt.UserRole + 1, article.get('EventText', ''))
                self.article_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to apply date filter: {str(e)}")

    def clear_date_filter(self):
        """Clears the date range filter and resets the article list."""
        self.start_year_edit.clear()
        self.start_month_edit.clear()
        self.start_day_edit.clear()
        self.end_year_edit.clear()
        self.end_month_edit.clear()
        self.end_day_edit.clear()

    def display_article_content(self, item):
        """Display the content of the selected article in the text viewer."""
        if not item:
            return
        
        try:
            # Get the stored event text directly from the item
            event_text = item.data(Qt.UserRole + 1)
            if event_text:
                self.article_text_view.setText(event_text)
            else:
                self.article_text_view.setText("No content available for this article.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to display article content: {str(e)}")
    
        
        # Reload all articles without the date filter
        self.load_associated_articles()
    
    def clear_viewer(self):
        """Clears the event text viewer content."""
        self.article_text_view.clear()
    
    def change_photo(self):
        """Change the character's photo."""
        if not self.current_character_id:
            QMessageBox.warning(self, "No Character Selected", "Please select a character first.")
            return
        
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            pixmap = QPixmap(file_name)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                try:
                    self.service.update_character_image(self.current_character_id, file_name)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to update image: {str(e)}")
            else:
                QMessageBox.warning(self, "Error", "Failed to load the selected image.")
    
    def add_new_character(self):
        """Add a new character to the database."""
        dialog = CharacterDialog(self)
        if dialog.exec_():
            character_data = dialog.get_character_data()
            try:
                # Use service to add the character
                new_id = self.service.add_character(character_data)
                if new_id:
                    self.load_characters()
                    QMessageBox.information(self, "Success", "New character added successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add character: {str(e)}")
    
    def edit_character(self):
        """Edit the selected character."""
        if not self.current_character_id:
            QMessageBox.warning(self, "No Character Selected", "Please select a character to edit.")
            return
        
        try:
            # Get current character data
            character = self.service.get_character_by_id(self.current_character_id)
            if not character:
                QMessageBox.warning(self, "Character Not Found", "Selected character could not be found.")
                return
            
            dialog = CharacterDialog(self, character)
            if dialog.exec_():
                updated_data = dialog.get_character_data()
                self.service.update_character(self.current_character_id, updated_data)
                
                # Reload characters list and refresh display
                self.load_characters()
                
                # If there's still a selected item, refresh its details
                current_item = self.table_panel.table.currentItem()
                if current_item:
                    self.display_character_details(current_item)
                
                QMessageBox.information(self, "Success", "Character updated successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to edit character: {str(e)}")
    
    def delete_character(self):
        """Delete the selected character."""
        if not self.current_character_id:
            QMessageBox.warning(self, "No Character Selected", "Please select a character to delete.")
            return
        
        reply = QMessageBox.question(self, 'Delete Character', 'Are you sure you want to delete this character?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.service.delete_character(self.current_character_id)
                self.load_characters()
                self.article_text_view.clear()
                self.article_list.clear()
                self.clear_layout(self.lower_layout)
                self.display_name_label.clear()
                self.image_label.clear()
                self.image_label.setText("No Image")
                self.current_character_id = None
                QMessageBox.information(self, "Success", "Character deleted successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete character: {str(e)}")
    
    def mark_character_reviewed(self):
        """Mark the selected character as reviewed."""
        if not self.current_character_id:
            QMessageBox.warning(self, "No Character Selected", "Please select a character to mark as reviewed.")
            return
        
        try:
            self.service.mark_character_reviewed(self.current_character_id)
            self.load_characters()
            QMessageBox.information(self, "Success", "Character has been marked as reviewed.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to mark character as reviewed: {str(e)}")
    
    def change_character_level(self, new_level):
        """Change the hierarchy level of the selected character."""
        if new_level == "Change Level" or not self.current_character_id:
            return
        
        try:
            self.service.set_character_level(self.current_character_id, new_level)
            
            # Update the left panel list to remove the character from the current view
            self.load_characters()
            
            # Update the center panel to reflect the new level
            self.current_level_label.setText(f"Current Level: {new_level}")
            self.level_dropdown.setCurrentIndex(0)  # Reset dropdown to "Change Level"
            
            QMessageBox.information(self, "Success", f"Character moved to {new_level} level.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to change character level: {str(e)}")
    
    def clear_layout(self, layout):
        """Clear all widgets from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())