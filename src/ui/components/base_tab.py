# File: base_tab.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                            QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, 
                            QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit, 
                            QComboBox, QMenu, QAction, QMessageBox, QListWidget, 
                            QListWidgetItem, QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter

from PyQt5.QtWidgets import QSplitterHandle

class CustomSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setStyleSheet("background-color: lightgray")  # Customize handle appearance

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw custom text/icon in the middle of the handle (e.g., "<>")
        painter.drawText(self.rect(), Qt.AlignCenter, "<>")  # Drawing "<>" in the middle of the handle

class CustomSplitter(QSplitter):
    def createHandle(self):
        return CustomSplitterHandle(self.orientation(), self)  # Use our custom handle

class BaseTab(QWidget):
    """Base class for tabs with a three-panel layout."""
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the base tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        
        # Initialize UI components
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface with a three-panel layout."""
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a splitter for the three panels
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Create the left panel (search and list)
        self.left_panel = self.create_left_panel()
        self.splitter.addWidget(self.left_panel)
        
        # Create the middle panel (details form)
        self.middle_panel = self.create_middle_panel()
        self.splitter.addWidget(self.middle_panel)
        
        # Create the right panel (associated items)
        self.right_panel = self.create_right_panel()
        self.splitter.addWidget(self.right_panel)
        
        # Set initial sizes (25%, 50%, 25%)
        self.splitter.setSizes([int(self.width() * 0.25), int(self.width() * 0.5), int(self.width() * 0.25)])
        
        # Add the splitter to the main layout
        main_layout.addWidget(self.splitter)
    
    def create_left_panel(self):
        """
        Create the left panel (search and list).
        Override in subclasses.
        
        Returns:
            QWidget: The left panel widget
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Placeholder label
        layout.addWidget(QLabel("Left Panel - Override in subclass"))
        
        return panel
    
    def create_middle_panel(self):
        """
        Create the middle panel (details form).
        Override in subclasses.
        
        Returns:
            QWidget: The middle panel widget
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Placeholder label
        layout.addWidget(QLabel("Middle Panel - Override in subclass"))
        
        return panel
    
    def create_right_panel(self):
        """
        Create the right panel (associated items).
        Override in subclasses.
        
        Returns:
            QWidget: The right panel widget
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Placeholder label
        layout.addWidget(QLabel("Right Panel - Override in subclass"))
        
        return panel