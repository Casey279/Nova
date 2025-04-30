# File: table_panel.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QPushButton, QLabel, QLineEdit, QComboBox, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal

class TablePanel(QWidget):
    """A reusable panel for displaying tabular data with optional filtering."""
    
    # Define signals
    item_selected = pyqtSignal(object)
    
    def __init__(self, headers=None, data=None, item_double_clicked=None, parent=None):
        super().__init__(parent)
        self.headers = headers or []
        self.data = data or []
        self.item_double_clicked_callback = item_double_clicked
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Search bar (optional)
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.filter_items)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table/list widget
        self.table = QListWidget()
        if self.item_double_clicked_callback:
            self.table.itemDoubleClicked.connect(self.item_double_clicked_callback)
        self.table.itemClicked.connect(self.on_item_selected)
        layout.addWidget(self.table)
        
        # Populate with initial data
        self.populate_table(self.data)
    
    def populate_table(self, data):
        """Populate the table with data."""
        self.table.clear()
        for item in data:
            self.add_item(item)
    
    def add_item(self, item_data):
        """Add a single item to the table."""
        # This is a simplified version assuming a list or string representation
        # In a real implementation, you'd handle different column types
        if isinstance(item_data, (list, tuple)):
            # If it's a list or tuple, use the first element as display text
            from PyQt5.QtWidgets import QListWidgetItem
            list_item = QListWidgetItem(str(item_data[0]))
            # Store the whole item data as user data
            list_item.setData(Qt.UserRole, item_data)
            self.table.addItem(list_item)
        elif hasattr(item_data, '__dict__'):
            # If it's an object, use __str__ for display and store the object
            from PyQt5.QtWidgets import QListWidgetItem
            list_item = QListWidgetItem(str(item_data))
            list_item.setData(Qt.UserRole, item_data)
            self.table.addItem(list_item)
        else:
            # For simple strings or other types
            self.table.addItem(str(item_data))
    
    def clear(self):
        """Clear all items from the table."""
        self.table.clear()
    
    def get_selected_item(self):
        """Get the currently selected item."""
        items = self.table.selectedItems()
        if items:
            return items[0]
        return None
    
    def on_item_selected(self, item):
        """Handle item selection and emit signal."""
        self.item_selected.emit(item)
    
    def filter_items(self, text):
        """Filter items based on search text."""
        for i in range(self.table.count()):
            item = self.table.item(i)
            # Show/hide based on whether the search text is in the item text
            item.setHidden(text.lower() not in item.text().lower())