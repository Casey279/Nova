# File: detail_panel.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QTextEdit, QPushButton, QLabel,
                             QScrollArea, QFrame)
from PyQt5.QtCore import pyqtSignal, Qt

class DetailPanel(QWidget):
    """
    A reusable detail panel component that can be used across different tabs.
    Provides a form for viewing and editing details of a selected item.
    """
    
    # Define signals
    save_requested = pyqtSignal(dict)  # Field data
    cancel_requested = pyqtSignal()
    delete_requested = pyqtSignal(int)  # Item ID
    
    def __init__(self, fields, parent=None):
        """
        Initialize the detail panel.
        
        Args:
            fields (list): List of field definitions. Each field is a dict with:
                           - 'name': Internal field name
                           - 'label': Display label
                           - 'type': Field type ('text', 'textarea', etc.)
                           - 'readonly': Whether the field is read-only
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.fields = fields
        self.field_widgets = {}  # To store references to field widgets
        self.current_id = None
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components for the detail panel."""
        main_layout = QVBoxLayout(self)
        
        # Create a scroll area for the form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Create a widget to contain the form
        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        
        # Create fields based on the field definitions
        for field in self.fields:
            if field['type'] == 'text':
                widget = QLineEdit()
                if field.get('readonly', False):
                    widget.setReadOnly(True)
            elif field['type'] == 'textarea':
                widget = QTextEdit()
                if field.get('readonly', False):
                    widget.setReadOnly(True)
            else:
                # Default to text field
                widget = QLineEdit()
            
            self.field_widgets[field['name']] = widget
            form_layout.addRow(QLabel(field['label']), widget)
        
        scroll_area.setWidget(form_container)
        main_layout.addWidget(scroll_area)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.on_save)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.on_cancel)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.on_delete)
        self.delete_button.setEnabled(False)  # Disabled by default
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.delete_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def on_save(self):
        """Handle save button click."""
        field_data = {}
        for field in self.fields:
            name = field['name']
            widget = self.field_widgets[name]
            
            if field['type'] == 'text':
                value = widget.text()
            elif field['type'] == 'textarea':
                value = widget.toPlainText()
            else:
                value = widget.text()
            
            field_data[name] = value
        
        if self.current_id is not None:
            field_data['id'] = self.current_id
        
        self.save_requested.emit(field_data)
    
    def on_cancel(self):
        """Handle cancel button click."""
        self.clear_fields()
        self.cancel_requested.emit()
    
    def on_delete(self):
        """Handle delete button click."""
        if self.current_id is not None:
            self.delete_requested.emit(self.current_id)
    
    def set_data(self, data):
        """
        Set the data for the form fields.
        
        Args:
            data (dict): Dictionary of field values
        """
        self.current_id = data.get('id')
        
        for field in self.fields:
            name = field['name']
            if name in data:
                widget = self.field_widgets[name]
                value = data[name]
                
                if field['type'] == 'text':
                    widget.setText(str(value))
                elif field['type'] == 'textarea':
                    widget.setPlainText(str(value))
        
        # Enable or disable delete button based on whether we have an ID
        self.delete_button.setEnabled(self.current_id is not None)
    
    def clear_fields(self):
        """Clear all form fields."""
        for field in self.fields:
            widget = self.field_widgets[field['name']]
            
            if field['type'] == 'text':
                widget.clear()
            elif field['type'] == 'textarea':
                widget.clear()
        
        self.current_id = None
        self.delete_button.setEnabled(False)
    
    def get_field_value(self, field_name):
        """Get the value of a specific field."""
        if field_name in self.field_widgets:
            widget = self.field_widgets[field_name]
            
            for field in self.fields:
                if field['name'] == field_name:
                    if field['type'] == 'text':
                        return widget.text()
                    elif field['type'] == 'textarea':
                        return widget.toPlainText()
        
        return None