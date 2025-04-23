# File: events_tab.py

import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton, QTextEdit, QSplitter, QMessageBox)
from PyQt5.QtCore import Qt
from database_manager import DatabaseManager

class EventsTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_manager = DatabaseManager(db_path)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Create splitter for dividing the left, center, and right panels
        splitter = QSplitter(Qt.Horizontal)

        # Left Panel: Event List
        left_panel = self.create_event_list_section()
        splitter.addWidget(left_panel)

        # Center Panel: Event Details (Non-editable)
        center_panel = self.create_event_details_section()
        splitter.addWidget(center_panel)

        # Right Panel: Associated Names (Characters, Locations, Entities)
        right_panel = self.create_associated_names_section()
        splitter.addWidget(right_panel)

        # Set initial sizes (33%, 33%, 33%)
        splitter.setSizes([int(self.width() * 0.33), int(self.width() * 0.33), int(self.width() * 0.33)])

        # Add the splitter to the main layout
        layout.addWidget(splitter)
        self.setLayout(layout)

    def create_event_list_section(self):
        # Left Panel: List of Events
        left_panel = QWidget()
        left_layout = QVBoxLayout()

        # List widget for showing event titles
        self.event_list = QListWidget()
        left_layout.addWidget(QLabel("Event List"))
        left_layout.addWidget(self.event_list)

        # Refresh Events List Button
        refresh_button = QPushButton("Refresh Events List")
        refresh_button.clicked.connect(self.load_event_list)
        left_layout.addWidget(refresh_button)

        left_panel.setLayout(left_layout)
        return left_panel

    def create_event_details_section(self):
        # Center Panel: Display Event Text
        center_panel = QWidget()
        center_layout = QVBoxLayout()

        self.event_details_text = QTextEdit()
        self.event_details_text.setReadOnly(True)  # Ensure the text is not editable
        center_layout.addWidget(QLabel("Event Details"))
        center_layout.addWidget(self.event_details_text)

        center_panel.setLayout(center_layout)
        return center_panel

    def create_associated_names_section(self):
        # Right Panel: Associated Names (Characters, Locations, Entities)
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        right_layout.addWidget(QLabel("Associated Names (Characters, Locations, Entities)"))

        # Associated Characters
        right_layout.addWidget(QLabel("Characters"))
        self.character_list = QListWidget()
        self.character_list.itemClicked.connect(self.view_character)
        right_layout.addWidget(self.character_list)

        # Associated Locations
        right_layout.addWidget(QLabel("Locations"))
        self.location_list = QListWidget()
        self.location_list.itemClicked.connect(self.view_location)
        right_layout.addWidget(self.location_list)

        # Associated Entities
        right_layout.addWidget(QLabel("Entities"))
        self.entity_list = QListWidget()
        self.entity_list.itemClicked.connect(self.view_entity)
        right_layout.addWidget(self.entity_list)

        right_panel.setLayout(right_layout)
        return right_panel

    def load_event_list(self):
        # Fetch all events from the database and populate the event list
        events = self.db_manager.get_all_events()
        self.event_list.clear()
        for event in events:
            self.event_list.addItem(f"{event['EventDate']} - {event['EventTitle']}")

    def load_event_details(self, item):
        # Fetch details of the clicked event from the database
        event_title = item.text().split(" - ")[1]  # Extract the title from the list item
        event = self.db_manager.get_event_by_title(event_title)

        if event:
            self.event_details_text.setText(event['EventText'])
            self.load_associated_names(event['EventID'])

    def load_associated_names(self, event_id):
        # Load associated characters, locations, and entities based on the EventID
        self.character_list.clear()
        self.location_list.clear()
        self.entity_list.clear()

        characters = self.db_manager.get_characters_by_event(event_id)
        for character in characters:
            self.character_list.addItem(character['DisplayName'])

        locations = self.db_manager.get_locations_by_event(event_id)
        for location in locations:
            self.location_list.addItem(location['LocationName'])

        entities = self.db_manager.get_entities_by_event(event_id)
        for entity in entities:
            self.entity_list.addItem(entity['Name'])

    def view_character(self, item):
        # View the selected character in the Characters Tab
        QMessageBox.information(self, "Character Selected", f"View Character: {item.text()}")

    def view_location(self, item):
        # View the selected location in the Locations Tab
        QMessageBox.information(self, "Location Selected", f"View Location: {item.text()}")

    def view_entity(self, item):
        # View the selected entity in the Entities Tab
        QMessageBox.information(self, "Entity Selected", f"View Entity: {item.text()}")
