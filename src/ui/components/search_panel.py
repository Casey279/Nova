# File: search_panel.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QComboBox)
from PyQt5.QtCore import pyqtSignal

class SearchPanel(QWidget):
    """
    A reusable search panel component that can be used across different tabs.
    Provides search functionality with optional filters.
    """
    
    # Define signals
    search_requested = pyqtSignal(str, str)  # Search text, filter value
    clear_requested = pyqtSignal()
    
    def __init__(self, filters=None, search_placeholder="Search...", parent=None):
        """
        Initialize the search panel.
        
        Args:
            filters (list, optional): List of filter options
            search_placeholder (str): Placeholder text for search field
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.filters = filters
        self.search_placeholder = search_placeholder
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components for the search panel."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Search field and buttons
        search_layout = QHBoxLayout()
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText(self.search_placeholder)
        self.search_field.returnPressed.connect(self.on_search)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.on_search)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.on_clear)
        
        search_layout.addWidget(self.search_field)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.clear_button)
        
        layout.addLayout(search_layout)
        
        # Add filter if specified
        if self.filters:
            filter_layout = QHBoxLayout()
            
            filter_label = QLabel("Filter by:")
            self.filter_combo = QComboBox()
            self.filter_combo.addItems(self.filters)
            
            filter_layout.addWidget(filter_label)
            filter_layout.addWidget(self.filter_combo)
            filter_layout.addStretch()
            
            layout.addLayout(filter_layout)
        
        self.setLayout(layout)
    
    def on_search(self):
        """Handle search button click or Enter key press."""
        search_text = self.search_field.text()
        filter_value = self.filter_combo.currentText() if hasattr(self, 'filter_combo') else ""
        self.search_requested.emit(search_text, filter_value)
    
    def on_clear(self):
        """Handle clear button click."""
        self.search_field.clear()
        if hasattr(self, 'filter_combo'):
            self.filter_combo.setCurrentIndex(0)
        self.clear_requested.emit()
    
    def get_search_text(self):
        """Get the current search text."""
        return self.search_field.text()
    
    def get_filter_value(self):
        """Get the current filter value if available."""
        if hasattr(self, 'filter_combo'):
            return self.filter_combo.currentText()
        return ""
    
    def set_search_text(self, text):
        """Set the search text."""
        self.search_field.setText(text)
    
    def set_filter_value(self, value):
        """Set the filter value if available."""
        if hasattr(self, 'filter_combo') and value in self.filters:
            index = self.filters.index(value)
            self.filter_combo.setCurrentIndex(index)