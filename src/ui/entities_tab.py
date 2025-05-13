# File: entities_tab.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services import EntityService, DatabaseError
from ui.components.base_tab import BaseTab

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                            QPushButton, QMessageBox, QListWidget, QListWidgetItem,
                            QMenu, QAction, QLineEdit, QComboBox, QTextEdit, QFormLayout, QScrollArea, QFileDialog)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

class EntitiesTab(BaseTab):
    """
    Tab for managing entity information in the database.
    Inherits from BaseTab to use the standardized three-panel layout.
    """
    view_event_signal = pyqtSignal(int)  # Event ID to view
    edit_event_signal = pyqtSignal(int)  # Event ID to edit
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the entities tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        # Create service before BaseTab initialization
        self.entity_service = EntityService(db_path)
        self.current_entity_id = None
        
        # Initialize BaseTab
        super().__init__(db_path, parent)
        
        # Load initial data
        self.load_data()
    
    def create_left_panel(self):
        """Create the left panel with entity list and controls."""
        # Create a wrapper widget to hold the table panel
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Add search layout
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search term...")
        search_layout.addWidget(self.search_input)
        
        # Add search button
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.on_search)
        search_layout.addWidget(search_button)
        
        # Add reset button
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self.load_data)
        search_layout.addWidget(reset_button)
        
        layout.addLayout(search_layout)
        
        # Create list for entities
        self.entities_list = QListWidget()
        self.entities_list.itemClicked.connect(self.display_entity_details)
        layout.addWidget(self.entities_list)
        
        # Add buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add New Entity")
        add_button.clicked.connect(self.add_new_entity)
        button_layout.addWidget(add_button)
        
        delete_button = QPushButton("Delete Entity")
        delete_button.clicked.connect(self.delete_entity)
        button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
        
        return left_widget
    
    def create_middle_panel(self):
        """Create the middle panel with entity details."""
        # Create detail panel
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
        self.vitals_section = QLabel("No entity selected")
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
        
        # Buttons: Edit Entity
        button_layout = QHBoxLayout()
        
        # Edit Entity button
        self.edit_entity_button = QPushButton("Edit Entity")
        self.edit_entity_button.clicked.connect(self.edit_entity)
        button_layout.addWidget(self.edit_entity_button)
        
        detail_layout.addLayout(button_layout)
        
        return self.detail_panel
    
    def create_image_section(self, entity_dict=None):
        """Create the image section of the profile."""
        image_widget = QWidget()
        layout = QVBoxLayout(image_widget)
        
        # Image Display
        self.image_label = QLabel()
        self.image_label.setFixedSize(200, 200)
        if entity_dict and entity_dict.get('ImagePath'):
            pixmap = QPixmap(entity_dict['ImagePath'])
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
        
        return image_widget    
    
    def create_vitals_section(self, entity_dict=None):
        """Create the vitals section for entity details."""
        vitals_widget = QWidget()
        layout = QFormLayout(vitals_widget)
        layout.setVerticalSpacing(10)
        
        fields = [
            ('Name', 'name'),
            ('Type', 'type'),
            ('Aliases', 'aliases'),
            ('Description', 'description'),
            ('Source', 'source')
        ]
        
        for label, field in fields:
            field_label = QLabel(f"{label}:")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            
            if label == 'Aliases':
                aliases_text = QTextEdit()
                if entity_dict:
                    aliases_text.setPlainText(str(entity_dict.get(field, '')))
                aliases_text.setReadOnly(True)
                aliases_text.setMaximumHeight(40)
                layout.addRow(field_label, aliases_text)
            else:
                field_value = QLabel()
                if entity_dict:
                    value = str(entity_dict.get(field, ''))
                    field_value.setText(value)
                field_value.setWordWrap(True)
                layout.addRow(field_label, field_value)
        
        return vitals_widget    
    
    def update_vitals_section(self, entity_dict):
        """Update the vitals section with the latest entity details."""
        # Clear the vitals section layout before updating
        self.clear_layout(self.vitals_section_layout)
        
        # Create a new vitals section with updated entity data
        self.vitals_section = self.create_vitals_section(entity_dict)
        
        # Add the updated vitals section to the container
        self.vitals_section_layout.addWidget(self.vitals_section)

    def add_additional_fields(self, layout, entity_dict):
        """Add additional entity information fields to the layout."""
        # Fields for the additional information section
        fields = [
            ('type', 'Type'),
            ('description', 'Description'),
            ('source', 'Source')
        ]
        
        for db_field, display_name in fields:
            # Create label
            field_label = QLabel(f"<b>{display_name}:</b>")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            layout.addWidget(field_label)
            
            # Create value label
            value = entity_dict.get(db_field, '')
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

    def add_new_entity(self):
        """Add a new entity."""
        # This would typically open a dialog for entering entity details
        # For now, create a simple entity with default values
        try:
            # Create a new entity with default values
            new_entity = {
                'name': 'New Entity',
                'type': 'Generic',
                'aliases': '',
                'description': '',
                'source': ''
            }
            
            # Add the new entity to the database
            new_id = self.entity_service.create_entity(new_entity)
            
            # Reload the entities list
            self.load_data()
            
            # Find and select the new entity in the list
            for i in range(self.entities_list.count()):
                item = self.entities_list.item(i)
                if item.data(Qt.UserRole) == new_id:
                    self.entities_list.setCurrentItem(item)
                    self.display_entity_details(item)
                    break
                    
            QMessageBox.information(self, "Success", "New entity added successfully. Please edit its details.")
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to add entity: {str(e)}")

    def edit_entity(self):
        """Edit the current entity."""
        if not self.current_entity_id:
            QMessageBox.warning(self, "Warning", "Please select an entity to edit.")
            return
        
        # This would typically open a dialog for editing entity details
        # For now, just show a message
        QMessageBox.information(self, "Edit Entity", 
                            "Entity editing dialog would appear here.\n"
                            "Not implemented in this version.")

    def delete_entity(self):
        """Delete the current entity."""
        if not self.current_entity_id:
            QMessageBox.warning(self, "Warning", "Please select an entity to delete.")
            return
        
        try:
            # Get entity details for confirmation
            entity = self.entity_service.get_entity_by_id(self.current_entity_id)
            
            if not entity:
                return
                
            # Confirm deletion
            reply = QMessageBox.question(
                self, 
                "Confirm Deletion", 
                f"Are you sure you want to delete the entity '{entity['name']}'?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
                
            # Delete the entity
            self.entity_service.delete_entity(self.current_entity_id)
            
            # Clear the details panels
            self.display_name_label.clear()
            self.image_label.clear()
            self.image_label.setText("No Image")
            self.article_list.clear()
            self.article_text_view.clear()
            self.clear_layout(self.lower_layout)
            self.clear_layout(self.vitals_section_layout)
            self.vitals_section = QLabel("No entity selected")
            self.vitals_section_layout.addWidget(self.vitals_section)
            
            # Reload the entities list
            self.load_data()
            
            # Reset current entity ID
            self.current_entity_id = None
            
            QMessageBox.information(self, "Success", "Entity deleted successfully.")
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to delete entity: {str(e)}")

    def change_photo(self):
        """Change the photo for the current entity."""
        if not self.current_entity_id:
            QMessageBox.warning(self, "No Selection", "Please select an entity first.")
            return
        
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            pixmap = QPixmap(file_name)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                try:
                    self.entity_service.update_entity_image(self.current_entity_id, file_name)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to update image: {str(e)}")
            else:
                QMessageBox.warning(self, "Error", "Failed to load the selected image.")

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

    def display_entity_details(self, item):
        """Display the details of the selected entity."""
        if not item:
            return
            
        # Get entity ID from item
        entity_id = item.data(Qt.UserRole)
        self.current_entity_id = entity_id
        
        try:
            entity = self.entity_service.get_entity_by_id(entity_id)
            
            if not entity:
                QMessageBox.warning(self, "Entity Not Found", "Selected entity could not be found.")
                return
                
            # Update display name
            self.display_name_label.setText(entity.get('name', 'Unknown'))
            
            # Update image
            if entity.get('ImagePath'):
                pixmap = QPixmap(entity['ImagePath'])
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.image_label.clear()
                self.image_label.setText("No Image")
                self.image_label.setAlignment(Qt.AlignCenter)
            
            # Update the vitals section
            self.update_vitals_section(entity)
            
            # Clear previous additional content
            self.clear_layout(self.lower_layout)
            
            # Add additional fields to the lower section
            self.add_additional_fields(self.lower_layout, entity)
            
            # Load associated articles
            self.load_associated_articles()
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to display entity details: {str(e)}")                    
    
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
    
    def load_associated_articles(self):
        """Load articles associated with the selected entity."""
        self.article_list.clear()
        if not self.current_entity_id:
            return
        
        try:
            # Get articles associated with this entity
            associated_articles = self.entity_service.get_associated_articles(self.current_entity_id)
            
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

    def display_article_content(self, item):
        """Display the content of the selected article."""
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

    def apply_date_filter(self):
        """Apply date filter to articles."""
        if not self.current_entity_id:
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
            filtered_articles = self.entity_service.get_articles_by_entity_and_date(
                self.current_entity_id, start_date, end_date)
            
            self.article_list.clear()
            for article in filtered_articles:
                # Get the date in YYYY-MM-DD format
                date = article.get('EventDate', 'No Date')
                title = article.get('EventTitle', 'Untitled')
                
                # Format: "YYYY-MM-DD Title"
                item = QListWidgetItem(f"{date} {title}")
                item.setData(Qt.UserRole, article.get('EventID'))
                item.setData(Qt.UserRole + 1, article.get('EventText', ''))
                self.article_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to apply date filter: {str(e)}")

    def clear_date_filter(self):
        """Clear the date filter."""
        self.start_year_edit.clear()
        self.start_month_edit.clear()
        self.start_day_edit.clear()
        self.end_year_edit.clear()
        self.end_month_edit.clear()
        self.end_day_edit.clear()
        
        # Reload all articles without the date filter
        self.load_associated_articles()

    def clear_viewer(self):
        """Clears the article text viewer."""
        self.article_text_view.clear()    
    
    def load_data(self):
        """Load all entities from the database."""
        try:
            entities = self.entity_service.get_all_entities()
            self.entities_list.clear()
            
            for entity in entities:
                display_name = entity.get('name', 'Unnamed Entity')
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, entity.get('id'))
                self.entities_list.addItem(item)
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", str(e))
    
    def on_search(self):
        """Handle search button click."""
        search_text = self.search_input.text()
        
        if not search_text:
            self.load_data()
            return
        
        try:
            results = self.entity_service.search_entities(search_text)
            self.entities_list.clear()
            
            for entity in results:
                display_name = entity.get('name', 'Unnamed Entity')
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, entity.get('id'))
                self.entities_list.addItem(item)
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", str(e))