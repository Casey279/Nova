# File: sources_tab.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services import SourceService, DatabaseError
from ui.components.base_tab import BaseTab

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox,
                            QPushButton, QMessageBox, QListWidget, QListWidgetItem,
                            QMenu, QAction, QLineEdit, QTextEdit, QFormLayout, QScrollArea,
                            QDialog, QDialogButtonBox, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class SourcesTab(BaseTab):
    """
    Tab for managing source information in the database.
    Sources include documents, articles, books, and other reference materials.
    Inherits from BaseTab to use the standardized three-panel layout.
    """
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the sources tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        # Create service before BaseTab initialization
        self.source_service = SourceService(db_path)
        self.current_source_id = None
        
        # Initialize BaseTab
        super().__init__(db_path, parent)
        
        # Load initial data
        self.load_data()
    
    def create_left_panel(self):
        """Create the left panel with source list and controls."""
        # Create a wrapper widget
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Add search layout
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search term...")
        search_layout.addWidget(self.search_input)
        
        # Add filter dropdown
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Title", "Author", "Type", "Publication Date", "URL", "Content"])
        search_layout.addWidget(self.filter_combo)
        
        # Add search button
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.on_search)
        search_layout.addWidget(search_button)
        
        # Add reset button
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self.load_data)
        search_layout.addWidget(reset_button)
        
        layout.addLayout(search_layout)
        
        # Create list for sources
        self.sources_list = QListWidget()
        self.sources_list.itemClicked.connect(self.display_source_details)
        layout.addWidget(self.sources_list)
        
        # Add buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add New Source")
        add_button.clicked.connect(self.add_new_source)
        button_layout.addWidget(add_button)
        
        delete_button = QPushButton("Delete Source")
        delete_button.clicked.connect(self.delete_source)
        button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
        
        return left_widget
    
    def create_middle_panel(self):
        """Create the middle panel with source details."""
        # Create detail panel
        self.detail_panel = QWidget()
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(5, 5, 5, 5)
        
        # Display Title at the top
        self.display_title_label = QLabel()
        self.display_title_label.setAlignment(Qt.AlignCenter)
        self.display_title_label.setFont(QFont("Arial", 16, QFont.Bold))
        detail_layout.addWidget(self.display_title_label)
        
        # Source Details Section
        details_section = QFrame()
        details_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        details_section.setLineWidth(2)
        details_layout = QVBoxLayout(details_section)
        
        # Create and store details form container
        self.details_container = QWidget()
        self.details_layout = QFormLayout(self.details_container)
        
        # Add an empty placeholder initially
        self.details_section = QLabel("No source selected")
        self.details_layout.addRow(self.details_section)
        
        details_layout.addWidget(self.details_container)
        detail_layout.addWidget(details_section)
        
        # Content preview section
        self.content_title = QLabel("Content Preview:")
        self.content_title.setFont(QFont("Arial", 12, QFont.Bold))
        detail_layout.addWidget(self.content_title)
        
        self.content_preview = QTextEdit()
        self.content_preview.setReadOnly(True)
        self.content_preview.setMaximumHeight(150)
        detail_layout.addWidget(self.content_preview)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # View Full Content button
        self.view_content_button = QPushButton("View Full Content")
        self.view_content_button.clicked.connect(self.view_source_content)
        self.view_content_button.setEnabled(False)
        button_layout.addWidget(self.view_content_button)
        
        # Export Content button
        self.export_content_button = QPushButton("Export Content")
        self.export_content_button.clicked.connect(self.export_source_content)
        self.export_content_button.setEnabled(False)
        button_layout.addWidget(self.export_content_button)
        
        detail_layout.addLayout(button_layout)
        
        # Edit button
        self.edit_source_button = QPushButton("Edit Source")
        self.edit_source_button.clicked.connect(self.edit_source)
        detail_layout.addWidget(self.edit_source_button)
        
        return self.detail_panel
    
    def create_right_panel(self):
        """Create the right panel with entity references."""
        # Create a wrapper widget
        right_widget = QWidget()
        layout = QVBoxLayout(right_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title label
        title_label = QLabel("Entity References:")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title_label)
        
        # Create tabs or sections for different entity types
        self.references_container = QWidget()
        self.references_layout = QVBoxLayout(self.references_container)
        
        # Characters section
        self.chars_label = QLabel("Characters:")
        self.chars_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.references_layout.addWidget(self.chars_label)
        
        self.chars_list = QListWidget()
        self.references_layout.addWidget(self.chars_list)
        
        # Locations section
        self.locs_label = QLabel("Locations:")
        self.locs_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.references_layout.addWidget(self.locs_label)
        
        self.locs_list = QListWidget()
        self.references_layout.addWidget(self.locs_list)
        
        # Other entities section
        self.ents_label = QLabel("Other Entities:")
        self.ents_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.references_layout.addWidget(self.ents_label)
        
        self.ents_list = QListWidget()
        self.references_layout.addWidget(self.ents_list)
        
        layout.addWidget(self.references_container)
        
        # Add a button to refresh references
        refresh_button = QPushButton("Refresh References")
        refresh_button.clicked.connect(lambda: self.load_entity_references(self.current_source_id))
        layout.addWidget(refresh_button)
        
        return right_widget
    
    def create_source_details(self, source_dict=None):
        """Create the details form for source information."""
        details_widget = QWidget()
        layout = QFormLayout(details_widget)
        layout.setVerticalSpacing(10)
        
        # Define fields to display
        fields = [
            ('Title', 'title'),
            ('Author', 'author'),
            ('Type', 'source_type'),
            ('Publication Date', 'publication_date'),
            ('URL', 'url')
        ]
        
        for label, field in fields:
            field_label = QLabel(f"{label}:")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            
            field_value = QLabel()
            if source_dict and field in source_dict:
                value = str(source_dict.get(field, ''))
                field_value.setText(value)
            field_value.setWordWrap(True)
            
            layout.addRow(field_label, field_value)
        
        return details_widget
    
    def update_details_section(self, source_dict):
        """Update the details section with the latest source info."""
        # Clear the details layout
        self.clear_layout(self.details_layout)
        
        # Create a new details section with updated data
        self.details_section = self.create_source_details(source_dict)
        
        # Add the updated section to the container
        self.details_layout.addWidget(self.details_section)
    
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
    
    def load_data(self):
        """Load all sources from the database."""
        try:
            sources = self.source_service.get_all_sources()
            self.sources_list.clear()

            for source in sources:
                # Sources are returned as tuples, not dictionaries
                # The fields are: SourceID, SourceName, Aliases, SourceType, Abbreviation,
                # Publisher, Location, EstablishedDate, DiscontinuedDate, ImagePath,
                # SourceCode, ReviewStatus, PoliticalAffiliations, Summary
                source_id = source[0]  # SourceID
                display_title = source[1] or 'Untitled Source'  # SourceName

                item = QListWidgetItem(display_title)
                item.setData(Qt.UserRole, source_id)
                self.sources_list.addItem(item)
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", str(e))
    
    def on_search(self):
        """Handle search button click."""
        search_text = self.search_input.text()
        filter_option = self.filter_combo.currentText()

        if not search_text:
            self.load_data()
            return

        try:
            results = self.source_service.search_sources(search_text, filter_option)
            self.sources_list.clear()

            for source in results:
                # Sources from search are also returned as tuples
                source_id = source[0]  # First column is ID
                # Title column depends on the schema, but is typically the second column
                display_title = source[1] if len(source) > 1 else 'Untitled Source'

                item = QListWidgetItem(display_title)
                item.setData(Qt.UserRole, source_id)
                self.sources_list.addItem(item)
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", str(e))
    
    def display_source_details(self, item):
        """Display the details of the selected source."""
        if not item:
            return
            
        # Get source ID from item
        source_id = item.data(Qt.UserRole)
        self.current_source_id = source_id
        
        try:
            source = self.source_service.get_source_by_id(source_id)
            
            if not source:
                QMessageBox.warning(self, "Source Not Found", "Selected source could not be found.")
                return
                
            # Update display title
            self.display_title_label.setText(source.get('title', 'Unknown'))
            
            # Update the details section
            self.update_details_section(source)
            
            # Update content preview
            content = source.get('content', '')
            if content:
                # Show first 1000 characters of content
                preview = content[:1000]
                if len(content) > 1000:
                    preview += "..."
                self.content_preview.setText(preview)
                self.view_content_button.setEnabled(True)
                self.export_content_button.setEnabled(True)
            else:
                self.content_preview.setText("No content available")
                self.view_content_button.setEnabled(False)
                self.export_content_button.setEnabled(False)
            
            # Load entity references
            self.load_entity_references(source_id)
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to display source details: {str(e)}")
    
    def load_entity_references(self, source_id):
        """Load entity references for the selected source."""
        if not source_id:
            return
        
        try:
            # Clear current lists
            self.chars_list.clear()
            self.locs_list.clear()
            self.ents_list.clear()
            
            # Get references
            refs = self.source_service.get_source_entity_references(source_id)
            
            # Populate character references
            if 'characters' in refs and refs['characters']:
                for char in refs['characters']:
                    item = QListWidgetItem(char['name'])
                    item.setData(Qt.UserRole, char['id'])
                    self.chars_list.addItem(item)
            
            # Populate location references
            if 'locations' in refs and refs['locations']:
                for loc in refs['locations']:
                    item = QListWidgetItem(loc['name'])
                    item.setData(Qt.UserRole, loc['id'])
                    self.locs_list.addItem(item)
            
            # Populate other entity references
            if 'entities' in refs and refs['entities']:
                for ent in refs['entities']:
                    item = QListWidgetItem(ent['name'])
                    item.setData(Qt.UserRole, ent['id'])
                    self.ents_list.addItem(item)
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to load entity references: {str(e)}")
    
    def add_new_source(self):
        """Add a new source."""
        # This would typically open a dialog for entering source details
        # For now, create a simple source with default values
        try:
            # Create a new source with default values
            new_source = {
                'title': 'New Source',
                'author': '',
                'source_type': 'Document',
                'publication_date': '',
                'url': '',
                'content': ''
            }
            
            # Add the new source to the database
            new_id = self.source_service.create_source(new_source)
            
            # Reload the sources list
            self.load_data()
            
            # Find and select the new source in the list
            for i in range(self.sources_list.count()):
                item = self.sources_list.item(i)
                if item.data(Qt.UserRole) == new_id:
                    self.sources_list.setCurrentItem(item)
                    self.display_source_details(item)
                    break
                    
            QMessageBox.information(self, "Success", "New source added successfully. Please edit its details.")
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to add source: {str(e)}")
    
    def edit_source(self):
        """Edit the current source."""
        if not self.current_source_id:
            QMessageBox.warning(self, "Warning", "Please select a source to edit.")
            return
        
        # This would typically open a dialog for editing source details
        # For now, just show a message
        QMessageBox.information(self, "Edit Source", 
                              "Source editing dialog would appear here.\n"
                              "Not implemented in this version.")
    
    def delete_source(self):
        """Delete the current source."""
        if not self.current_source_id:
            QMessageBox.warning(self, "Warning", "Please select a source to delete.")
            return
        
        try:
            # Get source details for confirmation
            source = self.source_service.get_source_by_id(self.current_source_id)
            
            if not source:
                return
                
            # Confirm deletion
            reply = QMessageBox.question(
                self, 
                "Confirm Deletion", 
                f"Are you sure you want to delete the source '{source['title']}'?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
                
            # Check for references
            refs = self.source_service.get_source_references(self.current_source_id)
            total_refs = sum(refs.values()) if refs else 0
            
            if total_refs > 0:
                # Confirm deletion with references
                reply = QMessageBox.question(
                    self, 
                    "References Exist", 
                    f"This source is referenced in {total_refs} records. "
                    f"Deleting will remove all references as well. Continue?",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                
                if reply != QMessageBox.Yes:
                    return
                
                # Delete source with all references
                self.source_service.delete_source_with_references(self.current_source_id)
            else:
                # Delete just the source
                self.source_service.delete_source(self.current_source_id)
            
            # Clear the details panels
            self.display_title_label.clear()
            self.content_preview.clear()
            self.chars_list.clear()
            self.locs_list.clear()
            self.ents_list.clear()
            self.clear_layout(self.details_layout)
            
            # Add a placeholder to the details section
            self.details_section = QLabel("No source selected")
            self.details_layout.addWidget(self.details_section)
            
            # Reload the sources list
            self.load_data()
            
            # Reset current source ID
            self.current_source_id = None
            
            QMessageBox.information(self, "Success", "Source deleted successfully.")
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to delete source: {str(e)}")
    
    def view_source_content(self):
        """View the full content of the current source."""
        if not self.current_source_id:
            return
        
        try:
            source = self.source_service.get_source_by_id(self.current_source_id)
            
            if not source or not source.get('content'):
                QMessageBox.information(self, "Content", "No content available for this source.")
                return
            
            # Create a dialog to display the content
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Content: {source.get('title', 'Unknown')}")
            dialog.resize(800, 600)
            
            layout = QVBoxLayout(dialog)
            
            text_edit = QTextEdit()
            text_edit.setPlainText(source['content'])
            text_edit.setReadOnly(True)
            
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            
            layout.addWidget(text_edit)
            layout.addWidget(buttons)
            
            dialog.setLayout(layout)
            dialog.exec_()
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Error", f"Failed to retrieve source content: {str(e)}")
    
    def export_source_content(self):
        """Export the content of the current source to a file."""
        if not self.current_source_id:
            return
        
        try:
            source = self.source_service.get_source_by_id(self.current_source_id)
            
            if not source or not source.get('content'):
                QMessageBox.information(self, "Export", "No content available to export.")
                return
            
            # Get file path for export
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Source Content",
                f"{source.get('title', 'Unknown')}.txt",
                "Text Files (*.txt);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Write content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(source['content'])
            
            QMessageBox.information(self, "Export", f"Content exported successfully to {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting content: {str(e)}")