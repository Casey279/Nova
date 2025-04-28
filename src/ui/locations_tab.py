# File: locations_tab.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services import LocationService, DatabaseError
from ui.components import BaseTab

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QAbstractItemView, QGroupBox, 
                            QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, QMenu, 
                            QAction, QMessageBox, QListWidget, QListWidgetItem, QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal


class LocationsTab(BaseTab):
    """
    Tab for managing location information in the database.
    Inherits from BaseTab to use the standardized three-panel layout.
    """
    view_event_signal = pyqtSignal(int)  # Event ID to view
    edit_event_signal = pyqtSignal(int)  # Event ID to edit    
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the locations tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        # Define tab-specific properties
        self.table_headers = ["ID", "Name", "Aliases", "Description", "Coordinates", "Source"]
        
        self.detail_fields = [
            {'name': 'name', 'label': 'Name:', 'type': 'text'},
            {'name': 'aliases', 'label': 'Aliases:', 'type': 'text'},
            {'name': 'coordinates', 'label': 'Coordinates:', 'type': 'text'},
            {'name': 'description', 'label': 'Description:', 'type': 'textarea'},
            {'name': 'source', 'label': 'Source:', 'type': 'text'}
        ]
        
        self.search_filters = ["All", "Name", "Aliases", "Coordinates", "Description", "Source"]
        
        # Create location service
        self.location_service = LocationService(db_path)
        
        # Initialize the base tab
        super().__init__(db_path, parent)

    def load_location_events(self, location_id):
        """
        Load events associated with a location.
        
        Args:
            location_id: ID of the location
        """
        try:
            # Clear current events
            self.events_list.clear()
            self.view_event_button.setEnabled(False)
            
            # Get events for the location
            events = self.location_service.get_events_for_location(location_id)
            
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
            self.show_message("Database Error", f"Error loading location events: {str(e)}", QMessageBox.Critical)

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
    
    def load_data(self):
        """Load all locations from the database."""
        try:
            data = self.location_service.get_all_locations()
            self.table_panel.populate_table(data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error loading locations: {str(e)}", QMessageBox.Critical)
    
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
            data = self.location_service.search_locations(search_text, filter_value)
            self.table_panel.populate_table(data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error searching locations: {str(e)}", QMessageBox.Critical)
    
    def on_item_selected(self, item_id):
        """
        Handle location selection.
        
        Args:
            item_id (int): ID of the selected location
        """
        try:
            location_data = self.location_service.get_location_by_id(item_id)
            if location_data:
                self.detail_panel.set_data(location_data)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error loading location details: {str(e)}", QMessageBox.Critical)
    
    def on_save(self, field_data):
        """
        Handle saving location details.
        
        Args:
            field_data (dict): Field data to save
        """
        try:
            if 'id' in field_data and field_data['id'] is not None:
                # Update existing record
                self.location_service.update_location(field_data['id'], field_data)
                message = f"Location '{field_data['name']}' updated successfully."
            else:
                # Insert new record
                self.location_service.create_location(field_data)
                message = f"Location '{field_data['name']}' added successfully."
            
            self.load_data()
            self.show_message("Success", message)
        except DatabaseError as e:
            self.show_message("Database Error", f"Error saving location: {str(e)}", QMessageBox.Critical)
    
    def on_delete(self, item_id):
        """
        Handle deleting a location.
        
        Args:
            item_id (int): ID of the location to delete
        """
        try:
            # Get location data for confirmation message
            location_data = self.location_service.get_location_by_id(item_id)
            
            if not location_data:
                return
            
            location_name = location_data['name']
            
            # Confirm deletion
            if not self.confirm_action("Confirm Deletion", 
                                       f"Are you sure you want to delete '{location_name}'?"):
                return
            
            # Check for references in other tables
            ref_count = self.location_service.count_location_references(item_id)
            
            if ref_count > 0:
                if not self.confirm_action("References Exist", 
                                          f"This location is referenced in {ref_count} records. "
                                          f"Deleting will remove all references as well. Continue?"):
                    return
                
                # Delete location with all references
                self.location_service.delete_location_with_references(item_id)
            else:
                # Delete just the location
                self.location_service.delete_location(item_id)
            
            self.load_data()
            self.detail_panel.clear_fields()
            self.show_message("Success", f"Location '{location_name}' deleted successfully.")
        
        except DatabaseError as e:
            self.show_message("Database Error", f"Error deleting location: {str(e)}", QMessageBox.Critical)
    
    def on_context_menu(self, position, item_id):
        """
        Show context menu for location.
        
        Args:
            position (QPoint): Position for the context menu
            item_id (int): ID of the location
        """
        menu = QMenu()
        
        # Get location info
        location_data = self.location_service.get_location_by_id(item_id)
        
        if not location_data:
            return
        
        location_name = location_data['name']
        
        # Create menu actions
        edit_action = QAction(f"Edit '{location_name}'", self)
        edit_action.triggered.connect(lambda: self.on_item_selected(item_id))
        
        delete_action = QAction(f"Delete '{location_name}'", self)
        delete_action.triggered.connect(lambda: self.on_delete(item_id))
        
        show_refs_action = QAction(f"Show references to '{location_name}'", self)
        show_refs_action.triggered.connect(lambda: self.show_references(item_id, location_name))
        
        map_action = QAction(f"Show on map", self)
        map_action.triggered.connect(lambda: self.show_on_map(item_id, location_name))
        
        # Add actions to menu
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(show_refs_action)
        
        # Only add map action if coordinates are available
        if location_data.get('coordinates'):
            menu.addAction(map_action)
        
        # Show the menu
        menu.exec_(position)
    
    def show_references(self, location_id, location_name):
        """
        Show references to a location.
        
        Args:
            location_id (int): ID of the location
            location_name (str): Name of the location for display
        """
        try:
            refs = self.location_service.get_location_references(location_id)
            
            if not refs:
                self.show_message("References", f"No references found for '{location_name}'.")
                return
            
            # Format references for display
            ref_text = f"References to '{location_name}':\n\n"
            for source, count in refs:
                ref_text += f"• {source}: {count} mentions\n"
            
            # Show in a message box
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Location References")
            msg_box.setText(ref_text)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec_()
            
        except DatabaseError as e:
            self.show_message("Database Error", f"Error retrieving location references: {str(e)}", QMessageBox.Critical)
    
    def show_on_map(self, location_id, location_name):
        """
        Show location on map.
        
        Args:
            location_id (int): ID of the location
            location_name (str): Name of the location
        """
        try:
            location_data = self.location_service.get_location_by_id(location_id)
            
            if not location_data or not location_data.get('coordinates'):
                self.show_message("Map Error", "No coordinates available for this location.", QMessageBox.Warning)
                return
            
            # This is a placeholder for map integration
            # In a real implementation, this would open a map view with the coordinates
            coordinates = location_data['coordinates']
            
            self.show_message("Map View", 
                             f"Map view for '{location_name}' at coordinates: {coordinates}\n\n"
                             f"Map integration not implemented yet.", 
                             QMessageBox.Information)
            
        except DatabaseError as e:
            self.show_message("Database Error", f"Error retrieving location coordinates: {str(e)}", QMessageBox.Critical)