#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Repository Configuration UI Component for Nova

This module provides a user interface for configuring newspaper repositories,
including paths, database settings, and import/export preferences.
"""

import os
import sys
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                            QLabel, QLineEdit, QPushButton, QComboBox, 
                            QFileDialog, QMessageBox, QGroupBox, QFormLayout,
                            QTabWidget, QCheckBox, QSpinBox, QTableWidget,
                            QTableWidgetItem, QHeaderView, QToolButton,
                            QApplication, QDialog, QDialogButtonBox, QTextEdit)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPixmap, QColor

# Import Nova components
from src.ui.components.base_tab import BaseTab
from src.repository.config import RepositoryConfig
from src.repository.base_repository import BaseRepository

class CredentialsDialog(QDialog):
    """Dialog for entering and editing API credentials"""
    
    def __init__(self, service_name, parent=None):
        super().__init__(parent)
        self.service_name = service_name
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        self.setWindowTitle(f"{self.service_name} Credentials")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Form for credentials
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.api_key_input = QLineEdit()
        
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)
        form_layout.addRow("API Key:", self.api_key_input)
        
        # Additional notes area
        self.notes_label = QLabel("Notes:")
        self.notes_text = QTextEdit()
        self.notes_text.setMaximumHeight(80)
        
        if self.service_name == "Chronicling America":
            self.notes_text.setPlainText("No API key required for Chronicling America. Leave blank.")
            self.api_key_input.setEnabled(False)
        elif self.service_name == "Newspapers.com":
            self.notes_text.setPlainText("Enter your Newspapers.com account credentials.")
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        # Layout assembly
        layout.addLayout(form_layout)
        layout.addWidget(self.notes_label)
        layout.addWidget(self.notes_text)
        layout.addWidget(self.button_box)
    
    def get_credentials(self):
        """Return the entered credentials as a dictionary"""
        return {
            "username": self.username_input.text(),
            "password": self.password_input.text(),
            "api_key": self.api_key_input.text()
        }
    
    def set_credentials(self, credentials):
        """Set the dialog fields from a credentials dictionary"""
        if not credentials:
            return
            
        self.username_input.setText(credentials.get("username", ""))
        self.password_input.setText(credentials.get("password", ""))
        self.api_key_input.setText(credentials.get("api_key", ""))


class PathSettingsWidget(QWidget):
    """Widget for configuring repository file paths"""
    
    path_changed = pyqtSignal(str, str)  # path_type, new_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI elements"""
        layout = QVBoxLayout(self)
        
        # Base directory
        base_group = QGroupBox("Repository Base Directory")
        base_layout = QHBoxLayout()
        
        self.base_path_input = QLineEdit()
        self.base_browse_btn = QPushButton("Browse...")
        
        base_layout.addWidget(self.base_path_input)
        base_layout.addWidget(self.base_browse_btn)
        
        base_group.setLayout(base_layout)
        layout.addWidget(base_group)
        
        # Subdirectory structure
        paths_group = QGroupBox("Storage Structure")
        paths_layout = QGridLayout()
        
        # Directory paths
        path_types = [
            ("Original Files", "original"),
            ("Processed Files", "processed"),
            ("OCR Results", "ocr_results"),
            ("Article Clips", "article_clips"),
            ("Thumbnails", "thumbnails"),
            ("Temp Files", "temp")
        ]
        
        self.path_inputs = {}
        
        for i, (label_text, path_type) in enumerate(path_types):
            label = QLabel(f"{label_text}:")
            input_field = QLineEdit()
            browse_btn = QToolButton()
            browse_btn.setText("...")
            
            # Store for later reference
            self.path_inputs[path_type] = input_field
            
            # Layout placement
            paths_layout.addWidget(label, i, 0)
            paths_layout.addWidget(input_field, i, 1)
            paths_layout.addWidget(browse_btn, i, 2)
            
            # Connect signal
            browse_btn.clicked.connect(
                lambda checked, pt=path_type: self.browse_path(pt)
            )
            input_field.textChanged.connect(
                lambda text, pt=path_type: self.path_changed.emit(pt, text)
            )
        
        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)
        
        # Connect base path browse
        self.base_browse_btn.clicked.connect(self.browse_base_path)
        self.base_path_input.textChanged.connect(self.update_subdirectories)
    
    def browse_base_path(self):
        """Browse for base repository directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Repository Base Directory", 
            self.base_path_input.text() or os.path.expanduser("~")
        )
        if directory:
            self.base_path_input.setText(directory)
    
    def browse_path(self, path_type):
        """Browse for a specific subdirectory"""
        current_path = self.path_inputs[path_type].text()
        
        # Default to subdirectory of base if not set
        if not current_path and self.base_path_input.text():
            current_path = os.path.join(self.base_path_input.text(), path_type)
        
        directory = QFileDialog.getExistingDirectory(
            self, f"Select {path_type.replace('_', ' ').title()} Directory", 
            current_path or os.path.expanduser("~")
        )
        if directory:
            self.path_inputs[path_type].setText(directory)
    
    def update_subdirectories(self):
        """Update subdirectory paths when base path changes"""
        base_path = self.base_path_input.text()
        if not base_path:
            return
            
        # Only update empty paths or paths that were under the old base
        for path_type, input_field in self.path_inputs.items():
            if not input_field.text() or os.path.commonpath([base_path]) in input_field.text():
                input_field.setText(os.path.join(base_path, path_type))
                self.path_changed.emit(path_type, input_field.text())
    
    def set_paths(self, paths_dict):
        """Set the path values from a dictionary"""
        if not paths_dict:
            return
            
        if "base" in paths_dict:
            self.base_path_input.setText(paths_dict["base"])
            
        for path_type, input_field in self.path_inputs.items():
            if path_type in paths_dict:
                input_field.setText(paths_dict[path_type])
    
    def get_paths(self):
        """Get the current path values as a dictionary"""
        paths = {"base": self.base_path_input.text()}
        
        for path_type, input_field in self.path_inputs.items():
            paths[path_type] = input_field.text()
            
        return paths


class DatabaseSettingsWidget(QWidget):
    """Widget for configuring database settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI elements"""
        layout = QVBoxLayout(self)
        
        # Database type selection
        db_type_group = QGroupBox("Database Type")
        db_type_layout = QHBoxLayout()
        
        self.db_type_combo = QComboBox()
        self.db_type_combo.addItem("SQLite (file-based)", "sqlite")
        self.db_type_combo.addItem("MySQL", "mysql")
        self.db_type_combo.addItem("PostgreSQL", "postgres")
        
        db_type_layout.addWidget(QLabel("Type:"))
        db_type_layout.addWidget(self.db_type_combo)
        db_type_layout.addStretch()
        
        db_type_group.setLayout(db_type_layout)
        layout.addWidget(db_type_group)
        
        # Connection settings stack
        self.db_settings_stack = QTabWidget()
        self.db_settings_stack.setTabPosition(QTabWidget.West)
        
        # SQLite settings
        sqlite_widget = QWidget()
        sqlite_layout = QFormLayout(sqlite_widget)
        
        self.sqlite_path_input = QLineEdit()
        self.sqlite_browse_btn = QPushButton("Browse...")
        
        sqlite_path_layout = QHBoxLayout()
        sqlite_path_layout.addWidget(self.sqlite_path_input)
        sqlite_path_layout.addWidget(self.sqlite_browse_btn)
        
        sqlite_layout.addRow("Database File:", sqlite_path_layout)
        
        # MySQL settings
        mysql_widget = QWidget()
        mysql_layout = QFormLayout(mysql_widget)
        
        self.mysql_host_input = QLineEdit("localhost")
        self.mysql_port_input = QLineEdit("3306")
        self.mysql_user_input = QLineEdit()
        self.mysql_password_input = QLineEdit()
        self.mysql_password_input.setEchoMode(QLineEdit.Password)
        self.mysql_db_input = QLineEdit()
        
        mysql_layout.addRow("Host:", self.mysql_host_input)
        mysql_layout.addRow("Port:", self.mysql_port_input)
        mysql_layout.addRow("Username:", self.mysql_user_input)
        mysql_layout.addRow("Password:", self.mysql_password_input)
        mysql_layout.addRow("Database:", self.mysql_db_input)
        
        # PostgreSQL settings
        postgres_widget = QWidget()
        postgres_layout = QFormLayout(postgres_widget)
        
        self.postgres_host_input = QLineEdit("localhost")
        self.postgres_port_input = QLineEdit("5432")
        self.postgres_user_input = QLineEdit()
        self.postgres_password_input = QLineEdit()
        self.postgres_password_input.setEchoMode(QLineEdit.Password)
        self.postgres_db_input = QLineEdit()
        
        postgres_layout.addRow("Host:", self.postgres_host_input)
        postgres_layout.addRow("Port:", self.postgres_port_input)
        postgres_layout.addRow("Username:", self.postgres_user_input)
        postgres_layout.addRow("Password:", self.postgres_password_input)
        postgres_layout.addRow("Database:", self.postgres_db_input)
        
        # Add tabs to stack
        self.db_settings_stack.addTab(sqlite_widget, "SQLite")
        self.db_settings_stack.addTab(mysql_widget, "MySQL")
        self.db_settings_stack.addTab(postgres_widget, "PostgreSQL")
        
        layout.addWidget(self.db_settings_stack)
        
        # Additional database options
        options_group = QGroupBox("Database Options")
        options_layout = QVBoxLayout()
        
        self.auto_backup_check = QCheckBox("Automatically back up database")
        self.backup_frequency_combo = QComboBox()
        self.backup_frequency_combo.addItem("Daily", "daily")
        self.backup_frequency_combo.addItem("Weekly", "weekly")
        self.backup_frequency_combo.addItem("Monthly", "monthly")
        
        backup_layout = QHBoxLayout()
        backup_layout.addWidget(self.auto_backup_check)
        backup_layout.addWidget(QLabel("Frequency:"))
        backup_layout.addWidget(self.backup_frequency_combo)
        backup_layout.addStretch()
        
        options_layout.addLayout(backup_layout)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Connect signals
        self.db_type_combo.currentIndexChanged.connect(self.on_db_type_changed)
        self.sqlite_browse_btn.clicked.connect(self.browse_sqlite_path)
        
        # Initialize UI state
        self.on_db_type_changed(0)
    
    def on_db_type_changed(self, index):
        """Handle change of database type"""
        self.db_settings_stack.setCurrentIndex(index)
    
    def browse_sqlite_path(self):
        """Browse for SQLite database file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select SQLite Database File", 
            self.sqlite_path_input.text() or os.path.expanduser("~"),
            "SQLite Databases (*.db *.sqlite);;All Files (*.*)"
        )
        if file_path:
            self.sqlite_path_input.setText(file_path)
    
    def set_database_settings(self, settings):
        """Set the database settings from a dictionary"""
        if not settings:
            return
            
        # Set database type
        db_type = settings.get("type", "sqlite")
        index = self.db_type_combo.findData(db_type)
        if index >= 0:
            self.db_type_combo.setCurrentIndex(index)
            
        # Set type-specific settings
        if db_type == "sqlite":
            self.sqlite_path_input.setText(settings.get("path", ""))
        elif db_type == "mysql":
            self.mysql_host_input.setText(settings.get("host", "localhost"))
            self.mysql_port_input.setText(str(settings.get("port", "3306")))
            self.mysql_user_input.setText(settings.get("user", ""))
            self.mysql_password_input.setText(settings.get("password", ""))
            self.mysql_db_input.setText(settings.get("database", ""))
        elif db_type == "postgres":
            self.postgres_host_input.setText(settings.get("host", "localhost"))
            self.postgres_port_input.setText(str(settings.get("port", "5432")))
            self.postgres_user_input.setText(settings.get("user", ""))
            self.postgres_password_input.setText(settings.get("password", ""))
            self.postgres_db_input.setText(settings.get("database", ""))
            
        # Set backup options
        self.auto_backup_check.setChecked(settings.get("auto_backup", False))
        frequency = settings.get("backup_frequency", "daily")
        index = self.backup_frequency_combo.findData(frequency)
        if index >= 0:
            self.backup_frequency_combo.setCurrentIndex(index)
    
    def get_database_settings(self):
        """Get the current database settings as a dictionary"""
        db_type = self.db_type_combo.currentData()
        settings = {"type": db_type}
        
        if db_type == "sqlite":
            settings["path"] = self.sqlite_path_input.text()
        elif db_type == "mysql":
            settings.update({
                "host": self.mysql_host_input.text(),
                "port": int(self.mysql_port_input.text() or 3306),
                "user": self.mysql_user_input.text(),
                "password": self.mysql_password_input.text(),
                "database": self.mysql_db_input.text()
            })
        elif db_type == "postgres":
            settings.update({
                "host": self.postgres_host_input.text(),
                "port": int(self.postgres_port_input.text() or 5432),
                "user": self.postgres_user_input.text(),
                "password": self.postgres_password_input.text(),
                "database": self.postgres_db_input.text()
            })
            
        # Add backup settings
        settings["auto_backup"] = self.auto_backup_check.isChecked()
        settings["backup_frequency"] = self.backup_frequency_combo.currentData()
        
        return settings


class APICredentialsWidget(QWidget):
    """Widget for managing API credentials for different services"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.credentials = {}
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI elements"""
        layout = QVBoxLayout(self)
        
        # Services table
        self.services_table = QTableWidget(0, 3)  # rows will be added dynamically
        self.services_table.setHorizontalHeaderLabels(["Service", "Status", "Actions"])
        self.services_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.services_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.services_table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.services_table)
        
        # Add predefined services
        self.add_service("Chronicling America")
        self.add_service("Newspapers.com")
        self.add_service("Library of Congress")
        
        # Add custom service button
        self.add_service_btn = QPushButton("Add Custom Service")
        layout.addWidget(self.add_service_btn)
        
        # Connect signals
        self.add_service_btn.clicked.connect(self.add_custom_service)
    
    def add_service(self, service_name):
        """Add a service to the table"""
        row = self.services_table.rowCount()
        self.services_table.insertRow(row)
        
        # Service name
        name_item = QTableWidgetItem(service_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.services_table.setItem(row, 0, name_item)
        
        # Status
        has_credentials = service_name in self.credentials
        status_text = "Configured" if has_credentials else "Not Configured"
        status_item = QTableWidgetItem(status_text)
        status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
        status_color = QColor("#4CAF50") if has_credentials else QColor("#F44336")
        status_item.setForeground(status_color)
        self.services_table.setItem(row, 1, status_item)
        
        # Actions cell with buttons
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 2, 2, 2)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.edit_credentials(service_name))
        
        delete_btn = QPushButton("Remove")
        delete_btn.clicked.connect(lambda: self.remove_service(service_name))
        
        actions_layout.addWidget(edit_btn)
        actions_layout.addWidget(delete_btn)
        
        self.services_table.setCellWidget(row, 2, actions_widget)
    
    def add_custom_service(self):
        """Add a custom service"""
        service_name, ok = QFileDialog.getSaveFileName(
            self, "Enter Service Name",
            "", "Text (*.txt)"
        )
        
        if ok and service_name:
            self.add_service(service_name)
    
    def edit_credentials(self, service_name):
        """Edit credentials for a service"""
        dialog = CredentialsDialog(service_name, self)
        
        # Pre-fill with existing credentials if any
        if service_name in self.credentials:
            dialog.set_credentials(self.credentials[service_name])
        
        if dialog.exec_() == QDialog.Accepted:
            self.credentials[service_name] = dialog.get_credentials()
            
            # Update status in the table
            for row in range(self.services_table.rowCount()):
                if self.services_table.item(row, 0).text() == service_name:
                    status_item = QTableWidgetItem("Configured")
                    status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                    status_item.setForeground(QColor("#4CAF50"))
                    self.services_table.setItem(row, 1, status_item)
                    break
    
    def remove_service(self, service_name):
        """Remove a service from the table"""
        for row in range(self.services_table.rowCount()):
            if self.services_table.item(row, 0).text() == service_name:
                self.services_table.removeRow(row)
                
                # Also remove credentials if any
                if service_name in self.credentials:
                    del self.credentials[service_name]
                    
                break
    
    def set_credentials(self, credentials_dict):
        """Set all credentials from a dictionary"""
        self.credentials = credentials_dict or {}
        
        # Update status cells
        for row in range(self.services_table.rowCount()):
            service_name = self.services_table.item(row, 0).text()
            has_credentials = service_name in self.credentials
            
            status_text = "Configured" if has_credentials else "Not Configured"
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            status_color = QColor("#4CAF50") if has_credentials else QColor("#F44336")
            status_item.setForeground(status_color)
            
            self.services_table.setItem(row, 1, status_item)
    
    def get_credentials(self):
        """Get all credentials as a dictionary"""
        return self.credentials


class RepositoryConfig(BaseTab):
    """Main repository configuration UI component"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_config = None
        self.settings = QSettings("NovaProject", "RepositoryConfig")
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        """Set up the UI elements"""
        main_layout = QVBoxLayout(self)
        
        # Repository selection/creation
        repo_group = QGroupBox("Repository")
        repo_layout = QHBoxLayout()
        
        self.repo_combo = QComboBox()
        self.repo_combo.setMinimumWidth(300)
        
        self.new_repo_btn = QPushButton("New")
        self.rename_repo_btn = QPushButton("Rename")
        self.delete_repo_btn = QPushButton("Delete")
        
        repo_layout.addWidget(QLabel("Repository:"))
        repo_layout.addWidget(self.repo_combo)
        repo_layout.addWidget(self.new_repo_btn)
        repo_layout.addWidget(self.rename_repo_btn)
        repo_layout.addWidget(self.delete_repo_btn)
        
        repo_group.setLayout(repo_layout)
        main_layout.addWidget(repo_group)
        
        # Configuration tabs
        self.config_tabs = QTabWidget()
        
        # General tab
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        
        self.repo_name_input = QLineEdit()
        self.repo_desc_input = QTextEdit()
        self.repo_desc_input.setMaximumHeight(80)
        
        general_layout.addRow("Name:", self.repo_name_input)
        general_layout.addRow("Description:", self.repo_desc_input)
        
        # Paths tab
        self.paths_widget = PathSettingsWidget()
        
        # Database tab
        self.db_widget = DatabaseSettingsWidget()
        
        # API Credentials tab
        self.api_widget = APICredentialsWidget()
        
        # Advanced tab
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        
        ocr_group = QGroupBox("OCR Settings")
        ocr_layout = QFormLayout()
        
        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItem("Tesseract", "tesseract")
        self.ocr_engine_combo.addItem("Google Cloud Vision", "google")
        self.ocr_engine_combo.addItem("Azure Computer Vision", "azure")
        
        self.ocr_language_combo = QComboBox()
        self.ocr_language_combo.addItem("English", "eng")
        self.ocr_language_combo.addItem("Spanish", "spa")
        self.ocr_language_combo.addItem("French", "fra")
        self.ocr_language_combo.addItem("German", "deu")
        self.ocr_language_combo.addItem("Multiple Languages", "multi")
        
        ocr_layout.addRow("OCR Engine:", self.ocr_engine_combo)
        ocr_layout.addRow("Language:", self.ocr_language_combo)
        
        ocr_group.setLayout(ocr_layout)
        advanced_layout.addWidget(ocr_group)
        
        # Performance group
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout()
        
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 32)
        self.threads_spin.setValue(4)
        
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(0, 10000)
        self.cache_size_spin.setValue(500)
        self.cache_size_spin.setSuffix(" MB")
        
        perf_layout.addRow("Processing Threads:", self.threads_spin)
        perf_layout.addRow("Cache Size:", self.cache_size_spin)
        
        perf_group.setLayout(perf_layout)
        advanced_layout.addWidget(perf_group)
        
        # Add all tabs
        self.config_tabs.addTab(general_tab, "General")
        self.config_tabs.addTab(self.paths_widget, "Paths")
        self.config_tabs.addTab(self.db_widget, "Database")
        self.config_tabs.addTab(self.api_widget, "API Credentials")
        self.config_tabs.addTab(advanced_tab, "Advanced")
        
        main_layout.addWidget(self.config_tabs)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.import_btn = QPushButton("Import Config")
        self.export_btn = QPushButton("Export Config")
        self.save_btn = QPushButton("Save Configuration")
        
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(button_layout)
        
        # Connect signals
        self.connect_signals()
        
        # Initialize
        self.refresh_repositories()
        
    def connect_signals(self):
        """Connect UI signals to slots"""
        # Repository selection
        self.repo_combo.currentIndexChanged.connect(self.on_repository_changed)
        self.new_repo_btn.clicked.connect(self.create_new_repository)
        self.rename_repo_btn.clicked.connect(self.rename_repository)
        self.delete_repo_btn.clicked.connect(self.delete_repository)
        
        # Action buttons
        self.import_btn.clicked.connect(self.import_config)
        self.export_btn.clicked.connect(self.export_config)
        self.save_btn.clicked.connect(self.save_config)
    
    def refresh_repositories(self):
        """Refresh the list of available repositories"""
        self.repo_combo.clear()
        
        # This would use actual repository discovery logic
        # For now, we'll add some example repositories
        self.repo_combo.addItem("Default Repository", "default")
        self.repo_combo.addItem("Washington Newspapers", "washington")
        self.repo_combo.addItem("New York Times Archive", "nyt")
        self.repo_combo.addItem("User Repository 1", "user1")
        
        # Select previously selected repository if possible
        previous = self.settings.value("last_repository")
        if previous:
            index = self.repo_combo.findData(previous)
            if index >= 0:
                self.repo_combo.setCurrentIndex(index)
    
    def on_repository_changed(self, index):
        """Handle change of selected repository"""
        if index < 0:
            return
            
        repo_id = self.repo_combo.itemData(index)
        if not repo_id:
            return
            
        # This would load the actual repository instance
        self.settings.setValue("last_repository", repo_id)
        
        # Load config data from API into UI
        # For now, we'll use some example data
        self.load_repository_config(repo_id)
    
    def load_repository_config(self, repo_id):
        """Load repository configuration data into the UI"""
        # This would normally fetch from the repository service
        # For now, just simulate with sample data
        if repo_id == "default":
            config = {
                "name": "Default Repository",
                "description": "The default repository for newspaper archives",
                "paths": {
                    "base": "/mnt/c/AI/Nova/test_repository",
                    "original": "/mnt/c/AI/Nova/test_repository/original",
                    "processed": "/mnt/c/AI/Nova/test_repository/processed",
                    "ocr_results": "/mnt/c/AI/Nova/test_repository/ocr_results",
                    "article_clips": "/mnt/c/AI/Nova/test_repository/article_clips",
                    "thumbnails": "/mnt/c/AI/Nova/test_repository/thumbnails",
                    "temp": "/mnt/c/AI/Nova/test_repository/temp"
                },
                "database": {
                    "type": "sqlite",
                    "path": "/mnt/c/AI/Nova/test_repository/repository.db",
                    "auto_backup": True,
                    "backup_frequency": "daily"
                },
                "credentials": {
                    "Chronicling America": {
                        "username": "",
                        "password": "",
                        "api_key": ""
                    }
                },
                "advanced": {
                    "ocr_engine": "tesseract",
                    "ocr_language": "eng",
                    "threads": 4,
                    "cache_size": 500
                }
            }
        else:
            # Empty config for other repositories
            config = {
                "name": self.repo_combo.currentText(),
                "description": "",
                "paths": {},
                "database": {},
                "credentials": {},
                "advanced": {
                    "ocr_engine": "tesseract",
                    "ocr_language": "eng",
                    "threads": 4,
                    "cache_size": 500
                }
            }
        
        # Update UI with config data
        self.repo_name_input.setText(config.get("name", ""))
        self.repo_desc_input.setText(config.get("description", ""))
        
        self.paths_widget.set_paths(config.get("paths", {}))
        self.db_widget.set_database_settings(config.get("database", {}))
        self.api_widget.set_credentials(config.get("credentials", {}))
        
        # Set advanced options
        advanced = config.get("advanced", {})
        
        # OCR engine
        ocr_engine = advanced.get("ocr_engine", "tesseract")
        index = self.ocr_engine_combo.findData(ocr_engine)
        if index >= 0:
            self.ocr_engine_combo.setCurrentIndex(index)
            
        # OCR language
        ocr_language = advanced.get("ocr_language", "eng")
        index = self.ocr_language_combo.findData(ocr_language)
        if index >= 0:
            self.ocr_language_combo.setCurrentIndex(index)
            
        # Performance settings
        self.threads_spin.setValue(advanced.get("threads", 4))
        self.cache_size_spin.setValue(advanced.get("cache_size", 500))
        
        # Store config
        self.repo_config = config
    
    def get_current_config(self):
        """Get the current configuration as a dictionary"""
        config = {
            "name": self.repo_name_input.text(),
            "description": self.repo_desc_input.toPlainText(),
            "paths": self.paths_widget.get_paths(),
            "database": self.db_widget.get_database_settings(),
            "credentials": self.api_widget.get_credentials(),
            "advanced": {
                "ocr_engine": self.ocr_engine_combo.currentData(),
                "ocr_language": self.ocr_language_combo.currentData(),
                "threads": self.threads_spin.value(),
                "cache_size": self.cache_size_spin.value()
            }
        }
        
        return config
    
    def create_new_repository(self):
        """Create a new repository configuration"""
        name, ok = QInputDialog.getText(
            self, "Create New Repository", 
            "Enter repository name:"
        )
        
        if ok and name:
            # Generate a simple ID
            repo_id = name.lower().replace(" ", "_")
            
            # Check if it already exists
            for i in range(self.repo_combo.count()):
                if self.repo_combo.itemData(i) == repo_id:
                    QMessageBox.warning(
                        self, "Duplicate Repository",
                        f"A repository with ID '{repo_id}' already exists."
                    )
                    return
            
            # Add to combo and select it
            self.repo_combo.addItem(name, repo_id)
            self.repo_combo.setCurrentIndex(self.repo_combo.count() - 1)
            
            # Clear form for new configuration
            self.repo_name_input.setText(name)
            self.repo_desc_input.clear()
            self.paths_widget.set_paths({})
            self.db_widget.set_database_settings({})
            self.api_widget.set_credentials({})
            
            QMessageBox.information(
                self, "Repository Created",
                f"Repository '{name}' has been created. Configure it and click Save."
            )
    
    def rename_repository(self):
        """Rename the current repository"""
        current_index = self.repo_combo.currentIndex()
        if current_index < 0:
            return
            
        current_name = self.repo_combo.currentText()
        current_id = self.repo_combo.itemData(current_index)
        
        new_name, ok = QInputDialog.getText(
            self, "Rename Repository", 
            "Enter new repository name:",
            text=current_name
        )
        
        if ok and new_name and new_name != current_name:
            # Update combo
            self.repo_combo.setItemText(current_index, new_name)
            
            # Update name in form
            self.repo_name_input.setText(new_name)
            
            QMessageBox.information(
                self, "Repository Renamed",
                f"Repository renamed to '{new_name}'. Click Save to apply changes."
            )
    
    def delete_repository(self):
        """Delete the current repository"""
        current_index = self.repo_combo.currentIndex()
        if current_index < 0:
            return
            
        repo_name = self.repo_combo.currentText()
        
        confirm = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete the repository '{repo_name}'?\n\n"
            "This will only remove the configuration, not the actual data files.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.repo_combo.removeItem(current_index)
            
            QMessageBox.information(
                self, "Repository Deleted",
                f"Repository '{repo_name}' has been deleted."
            )
    
    def import_config(self):
        """Import repository configuration from a JSON file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Configuration", 
            "", "JSON Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
                
            # Basic validation
            required_keys = ["name", "paths", "database"]
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required key: {key}")
            
            # Update UI with imported config
            self.repo_name_input.setText(config.get("name", ""))
            self.repo_desc_input.setText(config.get("description", ""))
            
            self.paths_widget.set_paths(config.get("paths", {}))
            self.db_widget.set_database_settings(config.get("database", {}))
            self.api_widget.set_credentials(config.get("credentials", {}))
            
            # Advanced settings
            advanced = config.get("advanced", {})
            
            ocr_engine = advanced.get("ocr_engine", "tesseract")
            index = self.ocr_engine_combo.findData(ocr_engine)
            if index >= 0:
                self.ocr_engine_combo.setCurrentIndex(index)
                
            ocr_language = advanced.get("ocr_language", "eng")
            index = self.ocr_language_combo.findData(ocr_language)
            if index >= 0:
                self.ocr_language_combo.setCurrentIndex(index)
                
            self.threads_spin.setValue(advanced.get("threads", 4))
            self.cache_size_spin.setValue(advanced.get("cache_size", 500))
            
            QMessageBox.information(
                self, "Configuration Imported",
                f"Configuration imported from {file_path}.\n"
                "Click Save to apply the imported configuration."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, "Import Error",
                f"Failed to import configuration: {str(e)}"
            )
    
    def export_config(self):
        """Export repository configuration to a JSON file"""
        config = self.get_current_config()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Configuration", 
            f"{config['name'].replace(' ', '_')}_config.json",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=2)
                
            QMessageBox.information(
                self, "Configuration Exported",
                f"Configuration exported to {file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, "Export Error",
                f"Failed to export configuration: {str(e)}"
            )
    
    def save_config(self):
        """Save the current configuration"""
        config = self.get_current_config()
        repo_id = self.repo_combo.currentData()
        
        if not repo_id:
            QMessageBox.warning(
                self, "No Repository Selected",
                "No repository selected. Please select or create a repository."
            )
            return
            
        # This would normally save to the repository service
        # For now, just show a success message
        
        # Check for required fields
        if not config["name"]:
            QMessageBox.warning(
                self, "Missing Information",
                "Repository name is required."
            )
            return
            
        # For SQLite, check database path
        if config["database"].get("type") == "sqlite" and not config["database"].get("path"):
            QMessageBox.warning(
                self, "Missing Information",
                "SQLite database path is required."
            )
            return
            
        # For path-based config, check base directory
        if not config["paths"].get("base"):
            QMessageBox.warning(
                self, "Missing Information",
                "Repository base directory is required."
            )
            return
        
        QMessageBox.information(
            self, "Configuration Saved",
            f"Repository configuration for '{config['name']}' has been saved."
        )
        
        # Store config
        self.repo_config = config
    
    def load_settings(self):
        """Load application settings"""
        # Select previously selected repository if possible
        previous = self.settings.value("last_repository")
        if previous:
            index = self.repo_combo.findData(previous)
            if index >= 0:
                self.repo_combo.setCurrentIndex(index)
    
    def save_settings(self):
        """Save application settings"""
        # Save selected repository
        current_index = self.repo_combo.currentIndex()
        if current_index >= 0:
            repo_id = self.repo_combo.itemData(current_index)
            self.settings.setValue("last_repository", repo_id)
    
    def closeEvent(self, event):
        """Handle close event"""
        self.save_settings()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RepositoryConfig()
    window.show()
    sys.exit(app.exec_())