# File: base_tab.py

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QMenu, QAction, 
                             QMessageBox, QSplitter)
from PyQt5.QtCore import Qt

from .table_panel import TablePanel
from .search_panel import SearchPanel
from .detail_panel import DetailPanel

class BaseTab(QWidget):
    """
    Base class for tabs with a three-panel layout (search, table, details).
    Provides common functionality and structure for entity-focused tabs.
    """
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the base tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        
        # These should be defined in subclasses
        self.table_headers = []
        self.detail_fields = []
        self.search_filters = []
        
        # Initialize UI components
        self.setup_ui()
        self.setup_connections()
        self.load_data()
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QHBoxLayout(self)
        
        # Create a splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: Search and Table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create search panel
        self.search_panel = SearchPanel(
            filters=self.search_filters,
            search_placeholder=f"Search {self.__class__.__name__.replace('Tab', '')}..."
        )
        
        # Create table panel
        self.table_panel = TablePanel(headers=self.table_headers)
        
        left_layout.addWidget(self.search_panel)
        left_layout.addWidget(self.table_panel)
        
        # Right panel: Details
        self.detail_panel = DetailPanel(fields=self.detail_fields)
        
        # Add panels to splitter
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(self.detail_panel)
        
        # Set initial sizes (70% for table, 30% for details)
        self.splitter.setSizes([700, 300])
        
        main_layout.addWidget(self.splitter)
        self.setLayout(main_layout)
    
    def setup_connections(self):
        """Set up signal connections."""
        # Search panel connections
        self.search_panel.search_requested.connect(self.on_search)
        self.search_panel.clear_requested.connect(self.on_clear_search)
        
        # Table panel connections
        self.table_panel.item_selected.connect(self.on_item_selected)
        self.table_panel.item_double_clicked.connect(self.on_item_double_clicked)
        self.table_panel.context_menu_requested.connect(self.on_context_menu)
        
        # Detail panel connections
        self.detail_panel.save_requested.connect(self.on_save)
        self.detail_panel.cancel_requested.connect(self.on_cancel)
        self.detail_panel.delete_requested.connect(self.on_delete)
    
    def load_data(self):
        """Load data into the table. To be implemented by subclasses."""
        pass
    
    def on_search(self, search_text, filter_value):
        """
        Handle search requests.
        
        Args:
            search_text (str): Text to search for
            filter_value (str): Filter value to apply
        """
        pass
    
    def on_clear_search(self):
        """Handle clear search requests."""
        self.load_data()
    
    def on_item_selected(self, item_id):
        """
        Handle item selection.
        
        Args:
            item_id (int): ID of the selected item
        """
        pass
    
    def on_item_double_clicked(self, item_id):
        """
        Handle item double-click.
        
        Args:
            item_id (int): ID of the double-clicked item
        """
        pass
    
    def on_context_menu(self, position, item_id):
        """
        Handle context menu requests.
        
        Args:
            position (QPoint): Position for the context menu
            item_id (int): ID of the item at the position
        """
        pass
    
    def on_save(self, field_data):
        """
        Handle save requests.
        
        Args:
            field_data (dict): Field data to save
        """
        pass
    
    def on_cancel(self):
        """Handle cancel requests."""
        pass
    
    def on_delete(self, item_id):
        """
        Handle delete requests.
        
        Args:
            item_id (int): ID of the item to delete
        """
        pass
    
    def show_message(self, title, message, icon=QMessageBox.Information):
        """
        Show a message box.
        
        Args:
            title (str): Message box title
            message (str): Message to display
            icon (QMessageBox.Icon): Icon to display
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        msg_box.exec_()
    
    def confirm_action(self, title, message):
        """
        Show a confirmation dialog.
        
        Args:
            title (str): Dialog title
            message (str): Message to display
            
        Returns:
            bool: True if confirmed, False otherwise
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        return msg_box.exec_() == QMessageBox.Yes