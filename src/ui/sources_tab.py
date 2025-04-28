# File: sources_tab.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services import SourceService, DatabaseError
from ui.components import BaseTab

from PyQt5.QtWidgets import (QMenu, QAction, QMessageBox, QTextEdit, QDialog, 
                            QVBoxLayout, QDialogButtonBox, QFileDialog)
from PyQt5.QtCore import Qt


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
        # Define tab-specific properties
        self.table_headers = ["ID", "Title", "Author", "Type", "Publication Date", "URL"]
        
        self.detail_fields = [
            {'name': 'title', 'label': 'Title:', 'type': 'text'},
            {'name': 'author', 'label': 'Author:', 'type': 'text'},
            {'name': 'source_type', 'label': 'Type:', 'type': 'text'},
            {'name': 'publication_date', 'label': 'Publication Date:', 'type': 'text'},
            {'name': 'url', 'label': 'URL:', 'type': 'text'}
        ]
        
        self.search_filters = ["All", "Title", "Author", "Type", "Publication Date", "URL", "Content"]
        
        # Create source service
        self.source_service = SourceService(db_path)
        
        # Initialize the base tab
        super().__init__(db_path, parent)
    
    def load_data(self):
        """Load all sources from the database."""
        try:
            data = self.source_service.get_all_sources()
            self.table_panel.populate_table(data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error loading sources: {str(e)}", QMessageBox.Critical)
    
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
            data = self.source_service.search_sources(search_text, filter_value)
            self.table_panel.populate_table(data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error searching sources: {str(e)}", QMessageBox.Critical)
    
    def on_item_selected(self, item_id):
        """
        Handle source selection.
        
        Args:
            item_id (int): ID of the selected source
        """
        try:
            source_data = self.source_service.get_source_by_id(item_id)
            if source_data:
                # Remove content field from data before setting in detail panel
                # (Content is displayed separately via a "View Content" action)
                if 'content' in source_data:
                    source_data.pop('content')
                
                self.detail_panel.set_data(source_data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error loading source details: {str(e)}", QMessageBox.Critical)
    
    def on_save(self, field_data):
        """
        Handle saving source details.
        
        Args:
            field_data (dict): Field data to save
        """
        try:
            # Get content if the source already exists
            content = None
            if 'id' in field_data and field_data['id'] is not None:
                existing_data = self.source_service.get_source_by_id(field_data['id'])
                if existing_data and 'content' in existing_data:
                    content = existing_data['content']
            
            # Add content to field_data
            if content:
                field_data['content'] = content
            
            if 'id' in field_data and field_data['id'] is not None:
                # Update existing record
                self.source_service.update_source(field_data['id'], field_data)
                message = f"Source '{field_data['title']}' updated successfully."
            else:
                # Insert new record
                field_data['content'] = field_data.get('content', '')
                self.source_service.create_source(field_data)
                message = f"Source '{field_data['title']}' added successfully."
            
            self.load_data()
            self.show_message("Success", message)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error saving source: {str(e)}", QMessageBox.Critical)
    
    def on_delete(self, item_id):
        """
        Handle deleting a source.
        
        Args:
            item_id (int): ID of the source to delete
        """
        try:
            # Get source data for confirmation message
            source_data = self.source_service.get_source_by_id(item_id)
            
            if not source_data:
                return
            
            source_title = source_data['title']
            
            # Confirm deletion
            if not self.confirm_action("Confirm Deletion", 
                                       f"Are you sure you want to delete '{source_title}'?"):
                return
            
            # Check for references to this source
            refs = self.source_service.get_source_references(item_id)
            total_refs = sum(refs.values()) if refs else 0
            
            if total_refs > 0:
                if not self.confirm_action("References Exist", 
                                          f"This source is referenced in {total_refs} records. "
                                          f"Deleting will remove all references as well. Continue?"):
                    return
                
                # Delete source with all references
                self.source_service.delete_source_with_references(item_id)
            else:
                # Delete just the source
                self.source_service.delete_source(item_id)
            
            self.load_data()
            self.detail_panel.clear_fields()
            self.show_message("Success", f"Source '{source_title}' deleted successfully.")
        
        except DatabaseError as e:
            self.show_message("Database Error", f"Error deleting source: {str(e)}", QMessageBox.Critical)
    
    def on_context_menu(self, position, item_id):
        """
        Show context menu for source.
        
        Args:
            position (QPoint): Position for the context menu
            item_id (int): ID of the source
        """
        menu = QMenu()
        
        # Get source info
        source_data = self.source_service.get_source_by_id(item_id)
        
        if not source_data:
            return
        
        source_title = source_data['title']
        
        # Create menu actions
        edit_action = QAction(f"Edit '{source_title}'", self)
        edit_action.triggered.connect(lambda: self.on_item_selected(item_id))
        
        view_content_action = QAction(f"View Content", self)
        view_content_action.triggered.connect(lambda: self.view_source_content(item_id, source_title))
        
        export_action = QAction(f"Export Content", self)
        export_action.triggered.connect(lambda: self.export_source_content(item_id, source_title))
        
        delete_action = QAction(f"Delete '{source_title}'", self)
        delete_action.triggered.connect(lambda: self.on_delete(item_id))
        
        show_refs_action = QAction(f"Show entity references", self)
        show_refs_action.triggered.connect(lambda: self.show_entity_references(item_id, source_title))
        
        # Add actions to menu
        menu.addAction(edit_action)
        menu.addAction(view_content_action)
        menu.addAction(export_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(show_refs_action)
        
        # Show the menu
        menu.exec_(position)
    
    def view_source_content(self, source_id, source_title):
        """
        View the content of a source.
        
        Args:
            source_id (int): ID of the source
            source_title (str): Title of the source
        """
        try:
            content = self.source_service.get_source_content(source_id)
            
            if not content:
                self.show_message("Content", "No content available for this source.", QMessageBox.Information)
                return
            
            # Create a dialog to display the content
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Content: {source_title}")
            dialog.resize(800, 600)
            
            layout = QVBoxLayout(dialog)
            
            text_edit = QTextEdit()
            text_edit.setPlainText(content)
            text_edit.setReadOnly(True)
            
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            
            layout.addWidget(text_edit)
            layout.addWidget(buttons)
            
            dialog.setLayout(layout)
            dialog.exec_()
            
        except DatabaseError as e:
            self.show_message("Database Error", f"Error retrieving source content: {str(e)}", QMessageBox.Critical)
    
    def export_source_content(self, source_id, source_title):
        """
        Export the content of a source to a file.
        
        Args:
            source_id (int): ID of the source
            source_title (str): Title of the source
        """
        try:
            content = self.source_service.get_source_content(source_id)
            
            if not content:
                self.show_message("Export", "No content available to export.", QMessageBox.Information)
                return
            
            # Get file path for export
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Source Content",
                f"{source_title}.txt",
                "Text Files (*.txt);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Write content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.show_message("Export", f"Content exported successfully to {file_path}", QMessageBox.Information)
            
        except Exception as e:
            self.show_message("Export Error", f"Error exporting content: {str(e)}", QMessageBox.Critical)
    
    def show_entity_references(self, source_id, source_title):
        """
        Show entities referenced in a source.
        
        Args:
            source_id (int): ID of the source
            source_title (str): Title of the source
        """
        try:
            refs = self.source_service.get_source_references(source_id)
            
            if not refs:
                self.show_message("References", f"No entity references found in '{source_title}'.", QMessageBox.Information)
                return
            
            # Format references for display
            ref_text = f"Entities referenced in '{source_title}':\n\n"
            
            if refs.get('characters', 0) > 0:
                ref_text += f"• Characters: {refs['characters']} mentions\n"
            
            if refs.get('locations', 0) > 0:
                ref_text += f"• Locations: {refs['locations']} mentions\n"
            
            if refs.get('entities', 0) > 0:
                ref_text += f"• Other entities: {refs['entities']} mentions\n"
            
            # Show in a message box
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Entity References")
            msg_box.setText(ref_text)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec_()
            
        except DatabaseError as e:
            self.show_message("Database Error", f"Error retrieving entity references: {str(e)}", QMessageBox.Critical)