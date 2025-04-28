# File: entities_tab.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services import EntityService, DatabaseError
from ui.components import BaseTab

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QAbstractItemView, QGroupBox, 
                            QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, QMenu, 
                            QAction, QMessageBox, QListWidget, QListWidgetItem, QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal


class EntitiesTab(BaseTab):
    """
    Tab for managing entity information in the database.
    Entities can be events, organizations, or other notable items.
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
        # Define tab-specific properties
        self.table_headers = ["ID", "Name", "Type", "Start Date", "End Date", "Aliases", "Description"]
        
        self.detail_fields = [
            {'name': 'name', 'label': 'Name:', 'type': 'text'},
            {'name': 'entity_type', 'label': 'Type:', 'type': 'text'},
            {'name': 'start_date', 'label': 'Start Date:', 'type': 'text'},
            {'name': 'end_date', 'label': 'End Date:', 'type': 'text'},
            {'name': 'aliases', 'label': 'Aliases:', 'type': 'text'},
            {'name': 'description', 'label': 'Description:', 'type': 'textarea'},
            {'name': 'source', 'label': 'Source:', 'type': 'text'}
        ]
        
        self.search_filters = ["All", "Name", "Type", "Aliases", "Description", "Start Date", "End Date", "Source"]
        
        # Create entity service
        self.entity_service = EntityService(db_path)
        
        # Initialize the base tab
        super().__init__(db_path, parent)
        
        # Add filter by type button to the search panel if available
        self.setup_type_filter()

    def load_entity_events(self, entity_id):
        """
        Load events associated with a entity.
        
        Args:
            entity_id: ID of the entity
        """
        try:
            # Clear current events
            self.events_list.clear()
            self.view_event_button.setEnabled(False)
            
            # Get events for the entity
            events = self.entity_service.get_entity_events(entity_id)
            
            # Add events to the list
            for event in events:
                event_id = event[0]
                event_date = event[1] or "Unknown date"
                event_title = event[2] or "Untitled event"
                
                # Format date for display if available
                if event_date:
                    from ..utils import date_utils
                    try:
                        date_obj = date_utils.parse_date(event_date)
                        if date_obj:
                            event_date = date_utils.format_date(date_obj, "%b %d, %Y")
                    except:
                        pass
                
                # Create list item
                item_text = f"{event_date}: {event_title}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, event_id)
                
                self.events_list.addItem(item)
                
        except DatabaseError as e:
            self.show_message("Database Error", f"Error loading entity events: {str(e)}", QMessageBox.Critical)

    def on_events_list_selection_changed(self):
        """Handle selection changes in the events list."""
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
        selected_items = self.events_list.selectedItems()
        if selected_items:
            event_id = selected_items[0].data(Qt.UserRole)
            if event_id:
                self.view_event_signal.emit(event_id)        
    
    def setup_type_filter(self):
        """Set up the entity type filter dropdown if applicable."""
        # This is a placeholder for custom filtering by entity type
        # In a real implementation, this would add a dropdown to filter by entity type
        pass
    
    def load_data(self):
        """Load all entities from the database."""
        try:
            data = self.entity_service.get_all_entities()
            self.table_panel.populate_table(data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error loading entities: {str(e)}", QMessageBox.Critical)
    
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
            data = self.entity_service.search_entities(search_text, filter_value)
            self.table_panel.populate_table(data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error searching entities: {str(e)}", QMessageBox.Critical)
    
    def on_item_selected(self, item_id):
        """
        Handle entity selection.
        
        Args:
            item_id (int): ID of the selected entity
        """
        try:
            entity_data = self.entity_service.get_entity_by_id(item_id)
            if entity_data:
                self.detail_panel.set_data(entity_data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error loading entity details: {str(e)}", QMessageBox.Critical)
    
    def on_save(self, field_data):
        """
        Handle saving entity details.
        
        Args:
            field_data (dict): Field data to save
        """
        try:
            if 'id' in field_data and field_data['id'] is not None:
                # Update existing record
                self.entity_service.update_entity(field_data['id'], field_data)
                message = f"Entity '{field_data['name']}' updated successfully."
            else:
                # Insert new record
                self.entity_service.create_entity(field_data)
                message = f"Entity '{field_data['name']}' added successfully."
            
            self.load_data()
            self.show_message("Success", message)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error saving entity: {str(e)}", QMessageBox.Critical)
    
    def on_delete(self, item_id):
        """
        Handle deleting an entity.
        
        Args:
            item_id (int): ID of the entity to delete
        """
        try:
            # Get entity data for confirmation message
            entity_data = self.entity_service.get_entity_by_id(item_id)
            
            if not entity_data:
                return
            
            entity_name = entity_data['name']
            
            # Confirm deletion
            if not self.confirm_action("Confirm Deletion", 
                                       f"Are you sure you want to delete '{entity_name}'?"):
                return
            
            # Check for references in other tables
            ref_count = self.entity_service.count_entity_references(item_id)
            
            if ref_count > 0:
                if not self.confirm_action("References Exist", 
                                          f"This entity is referenced in {ref_count} records. "
                                          f"Deleting will remove all references as well. Continue?"):
                    return
                
                # Delete entity with all references
                self.entity_service.delete_entity_with_references(item_id)
            else:
                # Delete just the entity
                self.entity_service.delete_entity(item_id)
            
            self.load_data()
            self.detail_panel.clear_fields()
            self.show_message("Success", f"Entity '{entity_name}' deleted successfully.")
        
        except DatabaseError as e:
            self.show_message("Database Error", f"Error deleting entity: {str(e)}", QMessageBox.Critical)
    
    def on_context_menu(self, position, item_id):
        """
        Show context menu for entity.
        
        Args:
            position (QPoint): Position for the context menu
            item_id (int): ID of the entity
        """
        menu = QMenu()
        
        # Get entity info
        entity_data = self.entity_service.get_entity_by_id(item_id)
        
        if not entity_data:
            return
        
        entity_name = entity_data['name']
        entity_type = entity_data.get('entity_type', '')
        
        # Create menu actions
        edit_action = QAction(f"Edit '{entity_name}'", self)
        edit_action.triggered.connect(lambda: self.on_item_selected(item_id))
        
        delete_action = QAction(f"Delete '{entity_name}'", self)
        delete_action.triggered.connect(lambda: self.on_delete(item_id))
        
        show_refs_action = QAction(f"Show references to '{entity_name}'", self)
        show_refs_action.triggered.connect(lambda: self.show_references(item_id, entity_name))
        
        change_type_action = QAction(f"Change entity type", self)
        change_type_action.triggered.connect(lambda: self.change_entity_type(item_id, entity_name, entity_type))
        
        # Add actions to menu
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(show_refs_action)
        menu.addAction(change_type_action)
        
        # Show the menu
        menu.exec_(position)
    
    def show_references(self, entity_id, entity_name):
        """
        Show references to an entity.
        
        Args:
            entity_id (int): ID of the entity
            entity_name (str): Name of the entity for display
        """
        try:
            refs = self.entity_service.get_entity_references(entity_id)
            
            if not refs:
                self.show_message("References", f"No references found for '{entity_name}'.")
                return
            
            # Format references for display
            ref_text = f"References to '{entity_name}':\n\n"
            for source, count in refs:
                ref_text += f"• {source}: {count} mentions\n"
            
            # Show in a message box
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Entity References")
            msg_box.setText(ref_text)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec_()
            
        except DatabaseError as e:
            self.show_message("Database Error", f"Error retrieving entity references: {str(e)}", QMessageBox.Critical)
    
    def change_entity_type(self, entity_id, entity_name, current_type):
        """
        Change the type of an entity.
        
        Args:
            entity_id (int): ID of the entity
            entity_name (str): Name of the entity
            current_type (str): Current type of the entity
        """
        try:
            # Get available entity types
            entity_types = self.entity_service.get_entity_types()
            
            # Show input dialog for new type
            new_type, ok = QInputDialog.getItem(
                self,
                "Change Entity Type",
                f"Select new type for '{entity_name}':",
                entity_types,
                entity_types.index(current_type) if current_type in entity_types else 0,
                True
            )
            
            if ok and new_type:
                # Update entity type
                entity_data = self.entity_service.get_entity_by_id(entity_id)
                entity_data['entity_type'] = new_type
                
                self.entity_service.update_entity(entity_id, entity_data)
                self.load_data()
                
                # If the current entity is selected, refresh the detail view
                if self.detail_panel.current_id == entity_id:
                    self.on_item_selected(entity_id)
                
                self.show_message("Success", f"Entity type changed to '{new_type}'.")
            
        except DatabaseError as e:
            self.show_message("Database Error", f"Error changing entity type: {str(e)}", QMessageBox.Critical)
    
    def filter_by_type(self, entity_type):
        """
        Filter entities by type.
        
        Args:
            entity_type (str): Type to filter by
        """
        try:
            if not entity_type or entity_type.lower() == "all":
                self.load_data()
                return
            
            data = self.entity_service.get_entities_by_type(entity_type)
            self.table_panel.populate_table(data)
            
        except DatabaseError as e:
            self.show_message("Database Error", f"Error filtering entities: {str(e)}", QMessageBox.Critical)