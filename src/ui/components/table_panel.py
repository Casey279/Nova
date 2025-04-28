# File: table_panel.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView, QMenu, QAction)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QCursor

class TablePanel(QWidget):
    """
    A reusable table panel component that can be used across different tabs.
    Handles display of tabular data with context menu support.
    """
    
    # Define signals for table interactions
    item_selected = pyqtSignal(int)  # Row ID selected
    item_double_clicked = pyqtSignal(int)  # Row ID double-clicked
    context_menu_requested = pyqtSignal(QPoint, int)  # Position, Row ID
    
    def __init__(self, headers, parent=None):
        """
        Initialize the table panel with the specified headers.
        
        Args:
            headers (list): List of column header strings
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.headers = headers
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI components for the table panel."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        
        # Connect signals
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def on_selection_changed(self):
        """Handle selection changes and emit the selected row ID."""
        selected_items = self.table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            # Get the ID from the hidden first column (assuming ID is stored there)
            row_id = int(self.table.item(row, 0).data(Qt.UserRole))
            self.item_selected.emit(row_id)
    
    def on_item_double_clicked(self, item):
        """Handle double-click events and emit the selected row ID."""
        row = item.row()
        row_id = int(self.table.item(row, 0).data(Qt.UserRole))
        self.item_double_clicked.emit(row_id)
    
    def on_context_menu(self, position):
        """Handle context menu requests."""
        selected_items = self.table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            row_id = int(self.table.item(row, 0).data(Qt.UserRole))
            # Emit signal with the position and ID
            self.context_menu_requested.emit(QCursor.pos(), row_id)
    
    def clear_table(self):
        """Clear all rows from the table."""
        self.table.setRowCount(0)
    
    def populate_table(self, data, id_column=0):
        """
        Populate the table with data.
        
        Args:
            data (list): List of rows, where each row is a list of values
            id_column (int): Index of the column containing the ID
        """
        self.clear_table()
        self.table.setSortingEnabled(False)  # Disable sorting during update
        
        for row_idx, row_data in enumerate(data):
            self.table.insertRow(row_idx)
            
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                
                # Store the ID in the user role of the first column
                if col_idx == 0:
                    item.setData(Qt.UserRole, int(row_data[id_column]))
                
                self.table.setItem(row_idx, col_idx, item)
        
        self.table.setSortingEnabled(True)  # Re-enable sorting

    def get_selected_row_id(self):
        """Get the ID of the currently selected row."""
        selected_items = self.table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            return int(self.table.item(row, 0).data(Qt.UserRole))
        return None