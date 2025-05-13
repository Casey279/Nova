#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Repository Import UI Component for Nova

This module provides a user interface for importing content into the newspaper repository,
supporting various import sources and formats.
"""

import os
import sys
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                            QTreeView, QListView, QLabel, 
                            QLineEdit, QPushButton, QComboBox, QDateEdit,
                            QFileDialog, QMessageBox, QTabWidget, QGroupBox,
                            QFormLayout, QRadioButton, QButtonGroup, QProgressBar,
                            QCheckBox, QSpinBox, QTextEdit, QToolButton)
from PyQt5.QtCore import Qt, QSize, QDate, QThread, pyqtSignal, pyqtSlot, QSettings
from PyQt5.QtGui import QIcon, QPixmap, QStandardItemModel, QStandardItem

# Import Nova components
from src.ui.components.base_tab import BaseTab
from src.repository.config import RepositoryConfig
from src.repository.base_repository import BaseRepository
from src.repository.publication_repository import PublicationRepository

class ImportTask(QThread):
    """Thread for handling import operations"""
    progress_signal = pyqtSignal(int, str)
    completed_signal = pyqtSignal(bool, str)
    
    def __init__(self, import_type, source_path, target_repo, options=None):
        super().__init__()
        self.import_type = import_type
        self.source_path = source_path
        self.target_repo = target_repo
        self.options = options or {}
        self.running = False
        
    def run(self):
        """Run the import task"""
        self.running = True
        try:
            # Simulate or implement actual import logic
            if self.import_type == "file":
                self._import_files()
            elif self.import_type == "chronicling_america":
                self._import_chronicling_america()
            elif self.import_type == "newspapers_com":
                self._import_newspapers_com()
            else:
                raise ValueError(f"Unknown import type: {self.import_type}")
                
            self.completed_signal.emit(True, "Import completed successfully")
        except Exception as e:
            self.completed_signal.emit(False, f"Import failed: {str(e)}")
        finally:
            self.running = False
            
    def _import_files(self):
        """Import from local files"""
        # Implementation for file-based import
        total_files = len([f for f in os.listdir(self.source_path) 
                          if os.path.isfile(os.path.join(self.source_path, f))])
        for i, filename in enumerate(os.listdir(self.source_path)):
            if not self.running:
                break
                
            file_path = os.path.join(self.source_path, filename)
            if os.path.isfile(file_path):
                # Process file - this would call repository methods
                progress = int((i + 1) / total_files * 100)
                self.progress_signal.emit(progress, f"Importing {filename}")
                
    def _import_chronicling_america(self):
        """Import from Chronicling America"""
        # Implementation for Chronicling America API import
        # This would use the downloader and API classes
        steps = 10  # Example
        for i in range(steps):
            if not self.running:
                break
                
            # Simulate API interaction and processing
            progress = int((i + 1) / steps * 100)
            self.progress_signal.emit(progress, f"Processing batch {i+1}/{steps}")
            
    def _import_newspapers_com(self):
        """Import from Newspapers.com"""
        # Implementation for Newspapers.com import
        # Similar logic to other import methods
        steps = 5  # Example
        for i in range(steps):
            if not self.running:
                break
                
            # Simulate import steps
            progress = int((i + 1) / steps * 100)
            self.progress_signal.emit(progress, f"Importing batch {i+1}/{steps}")
    
    def stop(self):
        """Stop the import process"""
        self.running = False


class RepositoryImport(BaseTab):
    """UI for importing content into the newspaper repository"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.import_task = None
        self.current_repo = None
        self.settings = QSettings("NovaProject", "RepositoryImport")
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        """Set up the UI elements"""
        main_layout = QVBoxLayout(self)
        
        # Repository selection
        repo_group = QGroupBox("Target Repository")
        repo_layout = QFormLayout()
        
        self.repo_combo = QComboBox()
        self.repo_combo.setMinimumWidth(300)
        self.refresh_repo_btn = QToolButton()
        self.refresh_repo_btn.setText("↻")
        self.refresh_repo_btn.setToolTip("Refresh repository list")
        
        repo_selector = QHBoxLayout()
        repo_selector.addWidget(self.repo_combo)
        repo_selector.addWidget(self.refresh_repo_btn)
        
        repo_layout.addRow("Repository:", repo_selector)
        repo_group.setLayout(repo_layout)
        main_layout.addWidget(repo_group)
        
        # Import source configuration
        source_group = QGroupBox("Import Source")
        source_layout = QVBoxLayout()
        
        # Source type selection
        type_layout = QHBoxLayout()
        self.source_type_group = QButtonGroup(self)
        
        self.file_radio = QRadioButton("Local Files")
        self.ca_radio = QRadioButton("Chronicling America")
        self.newspapers_radio = QRadioButton("Newspapers.com")
        
        self.source_type_group.addButton(self.file_radio, 0)
        self.source_type_group.addButton(self.ca_radio, 1)
        self.source_type_group.addButton(self.newspapers_radio, 2)
        
        type_layout.addWidget(self.file_radio)
        type_layout.addWidget(self.ca_radio)
        type_layout.addWidget(self.newspapers_radio)
        type_layout.addStretch()
        
        source_layout.addLayout(type_layout)
        
        # Stack of source-specific input forms
        self.source_config_stack = QTabWidget()
        self.source_config_stack.setTabPosition(QTabWidget.South)
        self.source_config_stack.setDocumentMode(True)
        
        # Local Files tab
        file_widget = QWidget()
        file_layout = QFormLayout(file_widget)
        
        self.src_path_input = QLineEdit()
        self.src_path_input.setMinimumWidth(350)
        self.browse_btn = QPushButton("Browse...")
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.src_path_input)
        path_layout.addWidget(self.browse_btn)
        
        self.recursive_check = QCheckBox("Import recursively")
        
        file_layout.addRow("Source Directory:", path_layout)
        file_layout.addRow("", self.recursive_check)
        
        # Chronicling America tab
        ca_widget = QWidget()
        ca_layout = QFormLayout(ca_widget)
        
        self.ca_publication = QLineEdit()
        self.ca_start_date = QDateEdit()
        self.ca_start_date.setDisplayFormat("yyyy-MM-dd")
        self.ca_start_date.setDate(QDate.currentDate().addYears(-1))
        self.ca_end_date = QDateEdit()
        self.ca_end_date.setDisplayFormat("yyyy-MM-dd")
        self.ca_end_date.setDate(QDate.currentDate())
        
        self.ca_state_combo = QComboBox()
        # Add states that are available in CA
        states = ["All", "Alabama", "Alaska", "Arizona", "California", "Colorado", 
                 "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho",
                 "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
                 "Maryland", "Michigan", "Minnesota", "Mississippi", "Missouri", 
                 "Montana", "Nebraska", "Nevada", "New Jersey", "New Mexico",
                 "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma",
                 "Oregon", "Pennsylvania", "South Carolina", "South Dakota", 
                 "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
                 "West Virginia", "Wisconsin"]
        self.ca_state_combo.addItems(states)
        
        ca_layout.addRow("Publication:", self.ca_publication)
        ca_layout.addRow("State:", self.ca_state_combo)
        ca_layout.addRow("Start Date:", self.ca_start_date)
        ca_layout.addRow("End Date:", self.ca_end_date)
        
        # Newspapers.com tab
        np_widget = QWidget()
        np_layout = QFormLayout(np_widget)
        
        self.np_query = QLineEdit()
        self.np_location = QLineEdit()
        self.np_start_year = QSpinBox()
        self.np_start_year.setRange(1700, datetime.now().year)
        self.np_start_year.setValue(1880)
        
        self.np_end_year = QSpinBox()
        self.np_end_year.setRange(1700, datetime.now().year)
        self.np_end_year.setValue(1920)
        
        self.np_credentials = QPushButton("Set Credentials...")
        
        np_layout.addRow("Search Query:", self.np_query)
        np_layout.addRow("Location:", self.np_location)
        np_layout.addRow("Start Year:", self.np_start_year)
        np_layout.addRow("End Year:", self.np_end_year)
        np_layout.addRow("", self.np_credentials)
        
        # Add tabs to stack
        self.source_config_stack.addTab(file_widget, "Local Files")
        self.source_config_stack.addTab(ca_widget, "Chronicling America")
        self.source_config_stack.addTab(np_widget, "Newspapers.com")
        
        source_layout.addWidget(self.source_config_stack)
        source_group.setLayout(source_layout)
        main_layout.addWidget(source_group)
        
        # Import options
        options_group = QGroupBox("Import Options")
        options_layout = QVBoxLayout()
        
        # Basic options
        self.extract_text_check = QCheckBox("Extract text using OCR if needed")
        self.extract_text_check.setChecked(True)
        
        self.generate_thumbnails_check = QCheckBox("Generate thumbnails")
        self.generate_thumbnails_check.setChecked(True)
        
        self.auto_categorize_check = QCheckBox("Auto-categorize content")
        
        options_layout.addWidget(self.extract_text_check)
        options_layout.addWidget(self.generate_thumbnails_check)
        options_layout.addWidget(self.auto_categorize_check)
        
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)
        
        # Progress area
        progress_group = QGroupBox("Import Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_status = QLabel("Ready to import")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_status)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.clear_btn = QPushButton("Clear")
        self.import_btn = QPushButton("Start Import")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # Connect signals
        self.connect_signals()
        
        # Initialize state
        self.file_radio.setChecked(True)
        self.update_source_ui()
        
    def connect_signals(self):
        """Connect UI signals to slots"""
        # Repository selection
        self.refresh_repo_btn.clicked.connect(self.refresh_repositories)
        self.repo_combo.currentIndexChanged.connect(self.on_repository_changed)
        
        # Source type selection
        self.source_type_group.buttonClicked.connect(self.update_source_ui)
        
        # Local files source
        self.browse_btn.clicked.connect(self.browse_source_path)
        
        # Action buttons
        self.clear_btn.clicked.connect(self.clear_form)
        self.import_btn.clicked.connect(self.start_import)
        self.cancel_btn.clicked.connect(self.cancel_import)
        
        # Credentials
        self.np_credentials.clicked.connect(self.set_newspapers_credentials)
        
    def update_source_ui(self):
        """Update the source configuration UI based on selected source type"""
        if self.file_radio.isChecked():
            self.source_config_stack.setCurrentIndex(0)
        elif self.ca_radio.isChecked():
            self.source_config_stack.setCurrentIndex(1)
        elif self.newspapers_radio.isChecked():
            self.source_config_stack.setCurrentIndex(2)
    
    def browse_source_path(self):
        """Open file dialog to select source directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", 
            self.src_path_input.text() or os.path.expanduser("~")
        )
        if directory:
            self.src_path_input.setText(directory)
    
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
        if index >= 0:
            repo_id = self.repo_combo.itemData(index)
            # This would load the actual repository instance
            self.current_repo = repo_id
            self.settings.setValue("last_repository", repo_id)
    
    def set_newspapers_credentials(self):
        """Open dialog to set newspapers.com credentials"""
        # This would open a dialog to input username/password
        # For now, just show a message
        QMessageBox.information(
            self, "Credentials Required",
            "To import from Newspapers.com, you need to provide login credentials. "
            "This feature will be implemented in a future update."
        )
    
    def clear_form(self):
        """Clear all form inputs"""
        self.src_path_input.clear()
        self.ca_publication.clear()
        self.ca_state_combo.setCurrentIndex(0)
        self.np_query.clear()
        self.np_location.clear()
        
        # Reset checkboxes
        self.extract_text_check.setChecked(True)
        self.generate_thumbnails_check.setChecked(True)
        self.auto_categorize_check.setChecked(False)
        
        # Reset progress
        self.progress_bar.setValue(0)
        self.progress_status.setText("Ready to import")
    
    def start_import(self):
        """Start the import process"""
        # Validate inputs
        if not self.current_repo:
            QMessageBox.warning(self, "No Repository Selected", 
                               "Please select a target repository.")
            return
        
        import_type = ""
        source_path = ""
        options = {
            "extract_text": self.extract_text_check.isChecked(),
            "generate_thumbnails": self.generate_thumbnails_check.isChecked(),
            "auto_categorize": self.auto_categorize_check.isChecked()
        }
        
        # Get source-specific options
        if self.file_radio.isChecked():
            import_type = "file"
            source_path = self.src_path_input.text()
            options["recursive"] = self.recursive_check.isChecked()
            
            if not source_path or not os.path.isdir(source_path):
                QMessageBox.warning(self, "Invalid Source", 
                                   "Please select a valid source directory.")
                return
                
        elif self.ca_radio.isChecked():
            import_type = "chronicling_america"
            source_path = "api"  # Not an actual path
            options["publication"] = self.ca_publication.text()
            options["state"] = self.ca_state_combo.currentText()
            options["start_date"] = self.ca_start_date.date().toString("yyyy-MM-dd")
            options["end_date"] = self.ca_end_date.date().toString("yyyy-MM-dd")
            
        elif self.newspapers_radio.isChecked():
            import_type = "newspapers_com"
            source_path = "api"  # Not an actual path
            options["query"] = self.np_query.text()
            options["location"] = self.np_location.text()
            options["start_year"] = self.np_start_year.value()
            options["end_year"] = self.np_end_year.value()
            
            if not options["query"]:
                QMessageBox.warning(self, "Invalid Search", 
                                   "Please enter a search query.")
                return
        
        # Create and start import task
        self.import_task = ImportTask(
            import_type, source_path, self.current_repo, options
        )
        self.import_task.progress_signal.connect(self.update_progress)
        self.import_task.completed_signal.connect(self.import_completed)
        
        # Update UI
        self.import_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_status.setText("Starting import...")
        
        # Start the task
        self.import_task.start()
    
    def cancel_import(self):
        """Cancel the current import operation"""
        if self.import_task and self.import_task.isRunning():
            self.import_task.stop()
            self.progress_status.setText("Import cancelled")
            
        self.import_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
    
    def update_progress(self, value, message):
        """Update the progress bar and status message"""
        self.progress_bar.setValue(value)
        self.progress_status.setText(message)
    
    def import_completed(self, success, message):
        """Handle import completion"""
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Import Complete", message)
        else:
            QMessageBox.warning(self, "Import Failed", message)
        
        self.import_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_status.setText(message)
    
    def load_settings(self):
        """Load saved settings"""
        self.refresh_repositories()
        
        # Load last used source type
        source_type = self.settings.value("source_type", 0, int)
        if source_type == 0:
            self.file_radio.setChecked(True)
        elif source_type == 1:
            self.ca_radio.setChecked(True)
        elif source_type == 2:
            self.newspapers_radio.setChecked(True)
        
        self.update_source_ui()
        
        # Load other settings
        self.src_path_input.setText(self.settings.value("source_path", ""))
        self.recursive_check.setChecked(self.settings.value("recursive", False, bool))
        
        self.extract_text_check.setChecked(
            self.settings.value("extract_text", True, bool))
        self.generate_thumbnails_check.setChecked(
            self.settings.value("generate_thumbnails", True, bool))
        self.auto_categorize_check.setChecked(
            self.settings.value("auto_categorize", False, bool))
    
    def save_settings(self):
        """Save current settings"""
        # Source type
        if self.file_radio.isChecked():
            self.settings.setValue("source_type", 0)
        elif self.ca_radio.isChecked():
            self.settings.setValue("source_type", 1)
        elif self.newspapers_radio.isChecked():
            self.settings.setValue("source_type", 2)
        
        # Other settings
        self.settings.setValue("source_path", self.src_path_input.text())
        self.settings.setValue("recursive", self.recursive_check.isChecked())
        
        self.settings.setValue("extract_text", self.extract_text_check.isChecked())
        self.settings.setValue("generate_thumbnails", 
                              self.generate_thumbnails_check.isChecked())
        self.settings.setValue("auto_categorize", self.auto_categorize_check.isChecked())
    
    def closeEvent(self, event):
        """Handle close event"""
        self.save_settings()
        
        # Make sure to stop any running import task
        if self.import_task and self.import_task.isRunning():
            self.import_task.stop()
            self.import_task.wait()
        
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RepositoryImport()
    window.show()
    sys.exit(app.exec_())