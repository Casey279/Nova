# File: events_tab.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services import EventService, DatabaseError
from utils import date_utils


from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                            QTableWidget, QTableWidgetItem, QHeaderView, 
                            QAbstractItemView, QGroupBox, QLabel, QLineEdit,
                            QPushButton, QDateEdit, QTextEdit, QComboBox,
                            QListWidget, QListWidgetItem, QMessageBox, QMenu, 
                            QAction, QGridLayout)
from PyQt5.QtCore import Qt, QDate, pyqtSignal




class EventsTab(QWidget):
    """
    Tab for browsing and viewing historical events.
    Provides search functionality, event details, and links to editing in Article Processor.
    """
    
    # Signal to notify main UI that an event should be loaded in Article Processor
    edit_event_signal = pyqtSignal(int)  # Event ID
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the events tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        self.event_service = EventService(db_path)
        
        # Current pagination state
        self.current_page = 1
        self.events_per_page = 50
        self.total_events = 0
        self.current_search_mode = None
        self.current_search_params = {}
        
        # Initialize UI
        self.setup_ui()
        
        # Load initial data
        self.load_events()
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Search controls
        search_group = QGroupBox("Search")
        search_layout = QGridLayout()
        
        # Date search
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addYears(-1))
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        
        self.date_search_button = QPushButton("Search by Date")
        self.date_search_button.clicked.connect(self.search_by_date)
        
        # Text search
        self.text_search_field = QLineEdit()
        self.text_search_field.setPlaceholderText("Enter search text...")
        self.text_search_field.returnPressed.connect(self.search_by_text)
        
        self.text_search_button = QPushButton("Search")
        self.text_search_button.clicked.connect(self.search_by_text)
        
        # Reset button
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_search)
        
        # Add widgets to search layout
        search_layout.addWidget(QLabel("Start Date:"), 0, 0)
        search_layout.addWidget(self.start_date_edit, 0, 1)
        search_layout.addWidget(QLabel("End Date:"), 0, 2)
        search_layout.addWidget(self.end_date_edit, 0, 3)
        search_layout.addWidget(self.date_search_button, 0, 4)
        
        search_layout.addWidget(QLabel("Search Text:"), 1, 0)
        search_layout.addWidget(self.text_search_field, 1, 1, 1, 3)
        search_layout.addWidget(self.text_search_button, 1, 4)
        
        search_layout.addWidget(self.reset_button, 2, 4)
        
        search_group.setLayout(search_layout)
        
        # Create splitter for main content
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: Events list
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(4)
        self.events_table.setHorizontalHeaderLabels(["Date", "Title", "Source", "ID"])
        self.events_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.events_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.events_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.events_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.events_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.events_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Connect signals
        self.events_table.itemSelectionChanged.connect(self.on_event_selected)
        self.events_table.customContextMenuRequested.connect(self.show_context_menu)
        self.events_table.itemDoubleClicked.connect(self.on_event_double_clicked)
        
        # Right panel: Event details
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        # Event metadata
        metadata_group = QGroupBox("Event Details")
        metadata_layout = QVBoxLayout()
        
        self.event_title_label = QLabel("Title: ")
        self.event_date_label = QLabel("Date: ")
        self.event_source_label = QLabel("Source: ")
        
        metadata_layout.addWidget(self.event_title_label)
        metadata_layout.addWidget(self.event_date_label)
        metadata_layout.addWidget(self.event_source_label)
        
        # Event description
        self.event_description = QTextEdit()
        self.event_description.setReadOnly(True)
        metadata_layout.addWidget(QLabel("Description:"))
        metadata_layout.addWidget(self.event_description)
        
        metadata_group.setLayout(metadata_layout)
        
        # Associated entities
        entities_group = QGroupBox("Associated Entities")
        entities_layout = QVBoxLayout()
        
        # Characters
        characters_layout = QVBoxLayout()
        characters_layout.addWidget(QLabel("Characters:"))
        self.characters_list = QListWidget()
        characters_layout.addWidget(self.characters_list)
        
        # Locations
        locations_layout = QVBoxLayout()
        locations_layout.addWidget(QLabel("Locations:"))
        self.locations_list = QListWidget()
        locations_layout.addWidget(self.locations_list)
        
        # Other entities
        other_entities_layout = QVBoxLayout()
        other_entities_layout.addWidget(QLabel("Other Entities:"))
        self.entities_list = QListWidget()
        other_entities_layout.addWidget(self.entities_list)
        
        entities_tabs_layout = QHBoxLayout()
        entities_tabs_layout.addLayout(characters_layout)
        entities_tabs_layout.addLayout(locations_layout)
        entities_tabs_layout.addLayout(other_entities_layout)
        
        entities_layout.addLayout(entities_tabs_layout)
        entities_group.setLayout(entities_layout)
        
        # Edit button
        self.edit_button = QPushButton("Edit in Article Processor")
        self.edit_button.clicked.connect(self.edit_current_event)
        self.edit_button.setEnabled(False)
        
        # Add all components to details layout
        details_layout.addWidget(metadata_group)
        details_layout.addWidget(entities_group)
        details_layout.addWidget(self.edit_button)
        
        # Add panels to splitter
        splitter.addWidget(self.events_table)
        splitter.addWidget(details_widget)
        
        # Set initial sizes (50% for each panel)
        splitter.setSizes([500, 500])
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        
        self.prev_page_button = QPushButton("Previous Page")
        self.prev_page_button.clicked.connect(self.previous_page)
        self.prev_page_button.setEnabled(False)
        
        self.page_label = QLabel("Page 1")
        
        self.next_page_button = QPushButton("Next Page")
        self.next_page_button.clicked.connect(self.next_page)
        
        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_page_button)
        
        # Add all components to main layout
        main_layout.addWidget(search_group)
        main_layout.addWidget(splitter, 1)  # 1 = stretch factor
        main_layout.addLayout(pagination_layout)
    
    def load_events(self):
        """Load events based on current pagination and search settings."""
        try:
            offset = (self.current_page - 1) * self.events_per_page
            
            # Determine which type of search/load to perform
            if self.current_search_mode == "date":
                start_date = self.current_search_params.get("start_date")
                end_date = self.current_search_params.get("end_date")
                events = self.event_service.search_events_by_date(
                    start_date, end_date, self.events_per_page, offset
                )
            elif self.current_search_mode == "text":
                search_text = self.current_search_params.get("search_text")
                events = self.event_service.search_events_by_text(
                    search_text, self.events_per_page, offset
                )
            else:
                # Default: load all events
                events = self.event_service.get_all_events(self.events_per_page, offset)
            
            # Update the table
            self.events_table.setRowCount(0)  # Clear table
            
            for row_index, event in enumerate(events):
                self.events_table.insertRow(row_index)
                
                event_id = event[0]
                event_date = event[1]
                event_title = event[2]
                event_description = event[3]
                source_id = event[4]
                source_title = event[5] or "Unknown"
                
                # Format date for display
                formatted_date = event_date
                if event_date:
                    try:
                        date_obj = date_utils.parse_date(event_date)
                        if date_obj:
                            formatted_date = date_utils.format_date(date_obj, "%b %d, %Y")
                    except:
                        pass
                
                # Create table items
                date_item = QTableWidgetItem(formatted_date)
                title_item = QTableWidgetItem(event_title)
                source_item = QTableWidgetItem(source_title)
                id_item = QTableWidgetItem(str(event_id))
                
                # Store event ID as user data for easier retrieval
                date_item.setData(Qt.UserRole, event_id)
                title_item.setData(Qt.UserRole, event_id)
                source_item.setData(Qt.UserRole, event_id)
                id_item.setData(Qt.UserRole, event_id)
                
                # Add items to table
                self.events_table.setItem(row_index, 0, date_item)
                self.events_table.setItem(row_index, 1, title_item)
                self.events_table.setItem(row_index, 2, source_item)
                self.events_table.setItem(row_index, 3, id_item)
            
            # Update pagination controls
            self.update_pagination_controls()
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", f"Error loading events: {str(e)}")

    # Add this method to the EventsTab class to show a specific event

    def view_event(self, event_id):
        """
        View a specific event given its ID.
        Find and select the event in the table, then display its details.
        
        Args:
            event_id: ID of the event to view
        """
        # Search for the event in the current table view
        found = False
        for row in range(self.events_table.rowCount()):
            item = self.events_table.item(row, 3)  # ID column
            if item and int(item.text()) == event_id:
                # Select this row
                self.events_table.selectRow(row)
                found = True
                break
        
        if not found:
            # Event not in current view, need to search for it
            try:
                # Get the event data
                event_data = self.event_service.get_event_by_id(event_id)
                
                if not event_data:
                    self.show_message("Error", f"Event with ID {event_id} not found.", QMessageBox.Warning)
                    return
                
                # Reset search filters
                self.current_search_mode = None
                self.current_search_params = {}
                self.current_page = 1
                
                # Load all events (first page)
                self.load_events()
                
                # Try to find and select the event again
                for row in range(self.events_table.rowCount()):
                    item = self.events_table.item(row, 3)  # ID column
                    if item and int(item.text()) == event_id:
                        self.events_table.selectRow(row)
                        found = True
                        break
                    
                if not found:
                    self.show_message("Note", f"Event with ID {event_id} was found but is not on the current page.", 
                                    QMessageBox.Information)
                    
                    # Directly load event details
                    self.load_event_details(event_id)
                
            except DatabaseError as e:
                self.show_message("Database Error", f"Error finding event: {str(e)}", QMessageBox.Critical)

    def update_pagination_controls(self):
        """Update pagination buttons and label based on current state."""
        try:
            # Get total count based on current search mode
            if self.current_search_mode == "date":
                start_date = self.current_search_params.get("start_date")
                end_date = self.current_search_params.get("end_date")
                # This would require additional methods in the service to get counts for specific searches
                # For simplicity, we'll just use get_events_count() for now
                self.total_events = self.event_service.get_events_count()
            elif self.current_search_mode == "text":
                # Similarly, this would require additional methods
                self.total_events = self.event_service.get_events_count()
            else:
                self.total_events = self.event_service.get_events_count()
            
            total_pages = max(1, (self.total_events + self.events_per_page - 1) // self.events_per_page)
            
            # Update page label
            self.page_label.setText(f"Page {self.current_page} of {total_pages}")
            
            # Enable/disable navigation buttons
            self.prev_page_button.setEnabled(self.current_page > 1)
            self.next_page_button.setEnabled(self.current_page < total_pages)
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", f"Error updating pagination: {str(e)}")
    
    def previous_page(self):
        """Go to the previous page of events."""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_events()
    
    def next_page(self):
        """Go to the next page of events."""
        total_pages = (self.total_events + self.events_per_page - 1) // self.events_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_events()
    
    def search_by_date(self):
        """Search events by date range."""
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
        
        self.current_search_mode = "date"
        self.current_search_params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        self.current_page = 1  # Reset to first page
        self.load_events()
    
    def search_by_text(self):
        """Search events by text in title or description."""
        search_text = self.text_search_field.text().strip()
        
        if not search_text:
            return
        
        self.current_search_mode = "text"
        self.current_search_params = {
            "search_text": search_text
        }
        
        self.current_page = 1  # Reset to first page
        self.load_events()
    
    def reset_search(self):
        """Reset search filters and show all events."""
        self.text_search_field.clear()
        
        # Reset date filters to default
        self.start_date_edit.setDate(QDate.currentDate().addYears(-1))
        self.end_date_edit.setDate(QDate.currentDate())
        
        # Clear search mode and params
        self.current_search_mode = None
        self.current_search_params = {}
        
        self.current_page = 1  # Reset to first page
        self.load_events()
    
    def on_event_selected(self):
        """Handle event selection in the table."""
        selected_items = self.events_table.selectedItems()
        
        if not selected_items:
            self.clear_event_details()
            return
        
        # Get event ID from selected row
        event_id = selected_items[0].data(Qt.UserRole)
        
        if event_id:
            self.load_event_details(event_id)
    
    def load_event_details(self, event_id):
        """
        Load and display details for the selected event.
        
        Args:
            event_id: ID of the event to display
        """
        try:
            event_data = self.event_service.get_event_by_id(event_id)
            
            if not event_data:
                self.clear_event_details()
                return
            
            # Update metadata labels
            self.event_title_label.setText(f"Title: {event_data['title']}")
            
            # Format date for display
            event_date = event_data['event_date']
            formatted_date = event_date
            if event_date:
                try:
                    date_obj = date_utils.parse_date(event_date)
                    if date_obj:
                        formatted_date = date_utils.format_date(date_obj, "%B %d, %Y")
                except:
                    pass
            
            self.event_date_label.setText(f"Date: {formatted_date}")
            self.event_source_label.setText(f"Source: {event_data['source_title']}")
            
            # Update description
            self.event_description.setPlainText(event_data['description'])
            
            # Update associated entities lists
            self.update_associated_entities(event_data)
            
            # Enable edit button
            self.edit_button.setEnabled(True)
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", f"Error loading event details: {str(e)}")
    
    def update_associated_entities(self, event_data):
        """
        Update lists of associated entities.
        
        Args:
            event_data: Event data dictionary
        """
        # Clear lists
        self.characters_list.clear()
        self.locations_list.clear()
        self.entities_list.clear()
        
        # Add characters
        for character in event_data.get('characters', []):
            item = QListWidgetItem(character['name'])
            item.setData(Qt.UserRole, character['id'])
            self.characters_list.addItem(item)
        
        # Add locations
        for location in event_data.get('locations', []):
            item = QListWidgetItem(location['name'])
            item.setData(Qt.UserRole, location['id'])
            self.locations_list.addItem(item)
        
        # Add other entities
        for entity in event_data.get('entities', []):
            item = QListWidgetItem(f"{entity['name']} ({entity['type']})")
            item.setData(Qt.UserRole, entity['id'])
            self.entities_list.addItem(item)
    
    def clear_event_details(self):
        """Clear all event details."""
        self.event_title_label.setText("Title: ")
        self.event_date_label.setText("Date: ")
        self.event_source_label.setText("Source: ")
        self.event_description.clear()
        
        self.characters_list.clear()
        self.locations_list.clear()
        self.entities_list.clear()
        
        self.edit_button.setEnabled(False)
    
    def edit_current_event(self):
        """Send signal to load the current event in Article Processor for editing."""
        selected_items = self.events_table.selectedItems()
        
        if not selected_items:
            return
        
        event_id = selected_items[0].data(Qt.UserRole)
        
        if event_id:
            self.edit_event_signal.emit(event_id)
    
    def on_event_double_clicked(self, item):
        """Handle double-click on an event (same as edit button)."""
        self.edit_current_event()
    
    def show_context_menu(self, position):
        """
        Show context menu for events table.
        
        Args:
            position: Mouse position
        """
        selected_items = self.events_table.selectedItems()
        
        if not selected_items:
            return
        
        event_id = selected_items[0].data(Qt.UserRole)
        
        if not event_id:
            return
        
        # Create context menu
        context_menu = QMenu(self)
        
        edit_action = QAction("Edit in Article Processor", self)
        edit_action.triggered.connect(self.edit_current_event)
        
        view_source_action = QAction("View Source Document", self)
        view_source_action.triggered.connect(lambda: self.view_source_document(event_id))
        
        context_menu.addAction(edit_action)
        context_menu.addAction(view_source_action)
        
        # Show menu
        context_menu.exec_(self.events_table.mapToGlobal(position))
    
    def view_source_document(self, event_id):
        """
        Open the source document for an event.
        
        Args:
            event_id: ID of the event
        """
        try:
            event_data = self.event_service.get_event_by_id(event_id)
            
            if not event_data or not event_data.get('source_id'):
                QMessageBox.information(self, "View Source", "No source document available for this event.")
                return
            
            # This would typically open a document viewer or source content dialog
            # For now, just show a message with source info
            QMessageBox.information(
                self, 
                "View Source Document", 
                f"Source: {event_data['source_title']}\n\n"
                f"This feature will open the source document viewer.\n"
                f"Source ID: {event_data['source_id']}"
            )
            
        except DatabaseError as e:
            QMessageBox.critical(self, "Database Error", f"Error retrieving source document: {str(e)}")