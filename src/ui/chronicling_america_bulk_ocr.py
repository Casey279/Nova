"""
Bulk OCR Processing for ChroniclingAmerica Downloads

This module provides a UI for setting up and running bulk OCR processing on files
downloaded from ChroniclingAmerica. It integrates with the newspaper repository
system to process batches of downloaded images.
"""

import os
import sys
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QProgressBar, QGroupBox, 
                             QComboBox, QCheckBox, QFileDialog, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox,
                             QSpinBox, QDialog, QDialogButtonBox, QFormLayout,
                             QApplication, QTabWidget, QTextEdit, QSplitter)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer, QSize

# Import repository modules
from newspaper_repository.background_service import BackgroundServiceManager
from newspaper_repository.bulk_task import BulkOperationType
from newspaper_repository.ocr_processor import OCRProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BulkOCRDialog(QDialog):
    """Dialog for setting up bulk OCR processing of downloaded files."""
    
    def __init__(self, parent=None, repository_path: Optional[str] = None):
        """
        Initialize the bulk OCR dialog.
        
        Args:
            parent: Parent widget
            repository_path: Path to the newspaper repository
        """
        super().__init__(parent)
        
        self.setWindowTitle("Bulk OCR Processing")
        self.setMinimumSize(700, 500)
        
        # Store repository path
        self.repository_path = repository_path
        if not self.repository_path:
            # Try to get from settings
            settings = QSettings("Nova", "NewspaperRepository")
            self.repository_path = settings.value("repository_path")
        
        # Initialize UI
        self.setup_ui()
        
        # Set default values
        self.setup_default_values()
        
        # Initialize background service if repository path is valid
        self.background_service = None
        self.init_background_service()
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Source directory selection
        source_group = QGroupBox("Source Files")
        source_layout = QFormLayout()
        
        self.source_dir_edit = QLineEdit()
        self.source_dir_edit.setReadOnly(True)
        self.source_dir_button = QPushButton("Browse...")
        self.source_dir_button.clicked.connect(self.browse_source_dir)
        
        source_dir_layout = QHBoxLayout()
        source_dir_layout.addWidget(self.source_dir_edit)
        source_dir_layout.addWidget(self.source_dir_button)
        
        source_layout.addRow("Source Directory:", source_dir_layout)
        
        # File pattern and recurse option
        self.file_pattern_edit = QLineEdit("*.jp2;*.jpg;*.jpeg;*.png;*.tif;*.tiff")
        source_layout.addRow("File Pattern:", self.file_pattern_edit)
        
        self.recurse_check = QCheckBox("Include subdirectories")
        self.recurse_check.setChecked(True)
        source_layout.addRow("", self.recurse_check)
        
        source_group.setLayout(source_layout)
        main_layout.addWidget(source_group)
        
        # Processing options
        options_group = QGroupBox("Processing Options")
        options_layout = QFormLayout()
        
        # OCR engine selection
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Tesseract", "tesseract")
        # Add other OCR engines if available
        
        options_layout.addRow("OCR Engine:", self.engine_combo)
        
        # Language selection
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "eng")
        self.language_combo.addItem("English + Old English", "eng+enm")
        self.language_combo.addItem("Multiple Languages", "eng+deu+fra+spa+ita")
        
        options_layout.addRow("Language:", self.language_combo)
        
        # OCR mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Fast", "fast")
        self.mode_combo.addItem("Balanced", "balanced")
        self.mode_combo.addItem("Accurate", "accurate")
        
        options_layout.addRow("OCR Mode:", self.mode_combo)
        
        # Preprocessing options
        self.preprocess_check = QCheckBox("Apply image preprocessing")
        self.preprocess_check.setChecked(True)
        options_layout.addRow("", self.preprocess_check)
        
        # Generate HOCR
        self.hocr_check = QCheckBox("Generate HOCR (with position data)")
        self.hocr_check.setChecked(True)
        options_layout.addRow("", self.hocr_check)
        
        # Segment articles
        self.segment_check = QCheckBox("Segment articles")
        self.segment_check.setChecked(True)
        options_layout.addRow("", self.segment_check)
        
        # Concurrent tasks
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 8)
        self.concurrent_spin.setValue(2)
        options_layout.addRow("Concurrent Tasks:", self.concurrent_spin)
        
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)
        
        # File list group
        files_group = QGroupBox("Files to Process")
        files_layout = QVBoxLayout()
        
        # Table for files
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(4)
        self.files_table.setHorizontalHeaderLabels(["Filename", "Size", "Date", "Status"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        
        # Buttons for file list
        files_button_layout = QHBoxLayout()
        self.scan_button = QPushButton("Scan Directory")
        self.scan_button.clicked.connect(self.scan_directory)
        self.clear_button = QPushButton("Clear List")
        self.clear_button.clicked.connect(self.clear_file_list)
        
        files_button_layout.addWidget(self.scan_button)
        files_button_layout.addWidget(self.clear_button)
        
        files_layout.addWidget(self.files_table)
        files_layout.addLayout(files_button_layout)
        
        files_group.setLayout(files_layout)
        main_layout.addWidget(files_group)
        
        # Results field
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(100)
        main_layout.addWidget(self.results_text)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        button_layout.addWidget(self.status_label, 1)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.start_processing)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)
        
        main_layout.addLayout(button_layout)
    
    def setup_default_values(self):
        """Set up default values for the UI."""
        # Try to set default source directory from repository path
        if self.repository_path:
            # Look for ChroniclingAmerica download directory
            ca_dir = os.path.join(self.repository_path, "original", "chroniclingamerica")
            if os.path.exists(ca_dir):
                self.source_dir_edit.setText(ca_dir)
            else:
                # Use downloads directory
                downloads_dir = os.path.join(self.repository_path, "downloads")
                if os.path.exists(downloads_dir):
                    self.source_dir_edit.setText(downloads_dir)
                else:
                    # Use repository directory
                    self.source_dir_edit.setText(self.repository_path)
        
        # Set default OCR options
        self.engine_combo.setCurrentIndex(0)  # Tesseract
        self.language_combo.setCurrentIndex(0)  # English
        self.mode_combo.setCurrentIndex(1)     # Balanced
    
    def init_background_service(self):
        """Initialize the background processing service."""
        if not self.repository_path:
            self.status_label.setText("Repository path not set")
            return
            
        try:
            # Get database path
            db_path = os.path.join(self.repository_path, "repository.db")
            if not os.path.exists(db_path):
                self.status_label.setText("Repository database not found")
                return
                
            # Initialize service
            self.background_service = BackgroundServiceManager.get_instance(
                db_path=db_path,
                base_directory=self.repository_path,
                max_concurrent_tasks=self.concurrent_spin.value()
            )
            
            self.status_label.setText("Service initialized")
            
            # Start service if not running
            if not self.background_service.running:
                self.background_service.start()
                
            # Register progress callback
            self.background_service.register_progress_callback(self.handle_progress)
            
        except Exception as e:
            self.status_label.setText(f"Error initializing service: {str(e)}")
            logger.error(f"Error initializing background service: {e}")
    
    def browse_source_dir(self):
        """Browse for source directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", self.source_dir_edit.text()
        )
        
        if directory:
            self.source_dir_edit.setText(directory)
    
    def scan_directory(self):
        """Scan the source directory for files to process."""
        source_dir = self.source_dir_edit.text()
        if not source_dir or not os.path.exists(source_dir):
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid source directory.")
            return
            
        # Get file patterns
        patterns = [p.strip() for p in self.file_pattern_edit.text().split(';')]
        if not patterns:
            patterns = ["*.jp2", "*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff"]
            
        # Update UI
        self.status_label.setText("Scanning directory...")
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Create background thread for scanning
        scan_thread = ScanDirectoryThread(
            source_dir=source_dir,
            patterns=patterns,
            recurse=self.recurse_check.isChecked()
        )
        
        scan_thread.files_found.connect(self.update_file_list)
        scan_thread.scan_complete.connect(self.scan_complete)
        scan_thread.scan_error.connect(self.scan_error)
        
        scan_thread.start()
    
    def update_file_list(self, files):
        """Update the file list with found files."""
        self.files_table.setRowCount(len(files))
        
        for i, file_info in enumerate(files):
            filename_item = QTableWidgetItem(os.path.basename(file_info["path"]))
            filename_item.setData(Qt.UserRole, file_info["path"])
            self.files_table.setItem(i, 0, filename_item)
            
            size_item = QTableWidgetItem(self.format_size(file_info["size"]))
            self.files_table.setItem(i, 1, size_item)
            
            date_item = QTableWidgetItem(file_info["date"])
            self.files_table.setItem(i, 2, date_item)
            
            status_item = QTableWidgetItem("Pending")
            self.files_table.setItem(i, 3, status_item)
    
    def scan_complete(self, file_count):
        """Handle scan completion."""
        self.status_label.setText(f"Found {file_count} files")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
    
    def scan_error(self, error_message):
        """Handle scan error."""
        self.status_label.setText(f"Error scanning directory: {error_message}")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        QMessageBox.warning(self, "Scan Error", error_message)
    
    def clear_file_list(self):
        """Clear the file list."""
        self.files_table.setRowCount(0)
        self.status_label.setText("File list cleared")
    
    def start_processing(self):
        """Start the bulk OCR processing."""
        # Check if source directory is valid
        source_dir = self.source_dir_edit.text()
        if not source_dir or not os.path.exists(source_dir):
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid source directory.")
            return
            
        # Check if files are selected
        if self.files_table.rowCount() == 0:
            QMessageBox.warning(self, "No Files", "No files to process. Please scan a directory first.")
            return
            
        # Check if background service is initialized
        if not self.background_service:
            QMessageBox.warning(self, "Service Not Available", 
                              "The background processing service is not available.")
            return
            
        # Gather processing options
        options = {
            "engine": self.engine_combo.currentData(),
            "language": self.language_combo.currentData(),
            "mode": self.mode_combo.currentData(),
            "preprocess": self.preprocess_check.isChecked(),
            "hocr": self.hocr_check.isChecked(),
            "segment": self.segment_check.isChecked(),
            "concurrent_tasks": self.concurrent_spin.value()
        }
        
        # Get file list
        files = []
        for row in range(self.files_table.rowCount()):
            file_path = self.files_table.item(row, 0).data(Qt.UserRole)
            files.append(file_path)
        
        # Create description for bulk task
        description = f"Bulk OCR Processing - {len(files)} files"
        
        # Create bulk task
        try:
            # Update background service concurrency if changed
            if self.background_service.max_concurrent_tasks != options["concurrent_tasks"]:
                # We can't actually change this directly, so we'll note it in results
                self.add_result(f"Note: Concurrent tasks setting will apply to new tasks only")
            
            # Create a new bulk task
            bulk_id = self.background_service.create_bulk_task(
                operation_type=BulkOperationType.OCR.value,
                description=description,
                parameters=options
            )
            
            if not bulk_id:
                raise ValueError("Failed to create bulk task")
                
            self.add_result(f"Created bulk task: {bulk_id}")
            self.add_result(f"Processing {len(files)} files with options:")
            self.add_result(f"  Engine: {options['engine']}")
            self.add_result(f"  Language: {options['language']}")
            self.add_result(f"  Mode: {options['mode']}")
            self.add_result(f"  Preprocessing: {'Yes' if options['preprocess'] else 'No'}")
            self.add_result(f"  HOCR Generation: {'Yes' if options['hocr'] else 'No'}")
            self.add_result(f"  Article Segmentation: {'Yes' if options['segment'] else 'No'}")
            
            # Update UI
            self.status_label.setText(f"Adding files to bulk task {bulk_id}...")
            self.progress_bar.setRange(0, len(files))
            self.progress_bar.setValue(0)
            
            # Add files to bulk task
            for i, file_path in enumerate(files):
                # Create page ID from file path
                page_id = os.path.basename(file_path)
                
                # Add task to bulk operation
                task_params = {
                    "file_path": file_path,
                    "engine": options["engine"],
                    "language": options["language"],
                    "mode": options["mode"],
                    "preprocess": options["preprocess"],
                    "hocr": options["hocr"],
                    "segment_articles": options["segment"]
                }
                
                # Add OCR task
                self.background_service.add_task_to_bulk(
                    bulk_id=bulk_id,
                    page_id=page_id,
                    operation="ocr",
                    parameters=task_params
                )
                
                # Add segmentation task if enabled
                if options["segment"]:
                    segment_params = {
                        "file_path": file_path,
                        "depends_on": f"{page_id}_ocr"  # Dependent on OCR task
                    }
                    
                    self.background_service.add_task_to_bulk(
                        bulk_id=bulk_id,
                        page_id=page_id,
                        operation="segment",
                        parameters=segment_params
                    )
                
                # Update progress
                self.progress_bar.setValue(i + 1)
                
                # Update status in table
                self.files_table.item(i, 3).setText("Added to queue")
            
            # Update UI
            self.add_result(f"Added {len(files)} files to processing queue")
            self.status_label.setText(f"Processing started with bulk ID: {bulk_id}")
            
            # Return task ID for monitoring
            self.accept()
            
        except Exception as e:
            error_message = str(e)
            self.add_result(f"Error starting processing: {error_message}")
            self.status_label.setText(f"Error: {error_message}")
            
            QMessageBox.critical(self, "Processing Error", 
                               f"Error starting bulk processing: {error_message}")
    
    def handle_progress(self, update):
        """Handle progress updates from the background service."""
        update_type = update["type"]
        data = update["data"]
        
        if update_type == "bulk_task_progress":
            bulk_id = data.get("bulk_id")
            task_id = data.get("task_id")
            progress = data.get("progress", 0)
            
            # Update progress bar if it's our bulk task
            # This would require storing the bulk ID after creation
            pass
    
    def add_result(self, message):
        """Add a message to the results text field."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.results_text.append(f"[{timestamp}] {message}")
    
    def format_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class ScanDirectoryThread(QThread):
    """Thread for scanning directories for files to process."""
    
    files_found = pyqtSignal(list)
    scan_complete = pyqtSignal(int)
    scan_error = pyqtSignal(str)
    
    def __init__(self, source_dir, patterns, recurse=True):
        """
        Initialize the scan thread.
        
        Args:
            source_dir: Directory to scan
            patterns: List of file patterns to match
            recurse: Whether to scan subdirectories
        """
        super().__init__()
        
        self.source_dir = source_dir
        self.patterns = patterns
        self.recurse = recurse
    
    def run(self):
        """Run the scan operation."""
        try:
            files = []
            
            # Walk the directory
            if self.recurse:
                # Recursive scan
                for root, _, filenames in os.walk(self.source_dir):
                    for filename in filenames:
                        # Check if file matches any pattern
                        if any(self.match_pattern(filename, pattern) for pattern in self.patterns):
                            file_path = os.path.join(root, filename)
                            files.append(self.get_file_info(file_path))
            else:
                # Non-recursive scan
                for filename in os.listdir(self.source_dir):
                    file_path = os.path.join(self.source_dir, filename)
                    if os.path.isfile(file_path) and any(self.match_pattern(filename, pattern) for pattern in self.patterns):
                        files.append(self.get_file_info(file_path))
            
            # Emit results
            self.files_found.emit(files)
            self.scan_complete.emit(len(files))
            
        except Exception as e:
            self.scan_error.emit(str(e))
    
    def match_pattern(self, filename, pattern):
        """Match filename against a glob pattern."""
        import fnmatch
        return fnmatch.fnmatch(filename.lower(), pattern.lower())
    
    def get_file_info(self, file_path):
        """Get file information."""
        stat = os.stat(file_path)
        
        return {
            "path": file_path,
            "size": stat.st_size,
            "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        }


class BulkProcessingMonitor(QWidget):
    """Widget for monitoring bulk processing tasks."""
    
    def __init__(self, parent=None, repository_path=None):
        """
        Initialize the bulk processing monitor.
        
        Args:
            parent: Parent widget
            repository_path: Path to the newspaper repository
        """
        super().__init__(parent)
        
        # Store repository path
        self.repository_path = repository_path
        
        # Initialize UI
        self.setup_ui()
        
        # Initialize background service
        self.background_service = None
        self.init_background_service()
        
        # Initialize update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_tasks)
        self.update_timer.start(5000)  # Update every 5 seconds
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Task list
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(7)
        self.tasks_table.setHorizontalHeaderLabels([
            "ID", "Description", "Status", "Progress", 
            "Tasks", "Updated", "Actions"
        ])
        self.tasks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tasks_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        main_layout.addWidget(self.tasks_table)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_tasks)
        
        self.new_task_button = QPushButton("New Bulk OCR Task")
        self.new_task_button.clicked.connect(self.new_bulk_task)
        
        self.status_label = QLabel("Ready")
        
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.new_task_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.status_label)
        
        main_layout.addLayout(controls_layout)
    
    def init_background_service(self):
        """Initialize the background processing service."""
        if not self.repository_path:
            self.status_label.setText("Repository path not set")
            return
            
        try:
            # Get database path
            db_path = os.path.join(self.repository_path, "repository.db")
            if not os.path.exists(db_path):
                self.status_label.setText("Repository database not found")
                return
                
            # Initialize service
            self.background_service = BackgroundServiceManager.get_instance(
                db_path=db_path,
                base_directory=self.repository_path
            )
            
            self.status_label.setText("Service initialized")
            
            # Start service if not running
            if not self.background_service.running:
                self.background_service.start()
                
            # Register progress callback
            self.background_service.register_progress_callback(self.handle_progress)
            
            # Refresh tasks
            self.refresh_tasks()
            
        except Exception as e:
            self.status_label.setText(f"Error initializing service: {str(e)}")
            logger.error(f"Error initializing background service: {e}")
    
    def refresh_tasks(self):
        """Refresh the list of bulk tasks."""
        if not self.background_service:
            return
            
        try:
            # Get all bulk tasks
            bulk_tasks = self.background_service.get_all_bulk_tasks()
            
            # Update table
            self.tasks_table.setRowCount(len(bulk_tasks))
            
            for row, task in enumerate(bulk_tasks):
                # ID column
                id_item = QTableWidgetItem(task["bulk_id"])
                self.tasks_table.setItem(row, 0, id_item)
                
                # Description column
                desc_item = QTableWidgetItem(task["description"])
                self.tasks_table.setItem(row, 1, desc_item)
                
                # Status column
                status_item = QTableWidgetItem(task["status"])
                self.tasks_table.setItem(row, 2, status_item)
                
                # Progress column - use a progress bar
                progress_widget = QWidget()
                progress_layout = QHBoxLayout(progress_widget)
                progress_layout.setContentsMargins(2, 2, 2, 2)
                
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 100)
                progress_bar.setValue(int(task["progress"] * 100))
                progress_layout.addWidget(progress_bar)
                
                self.tasks_table.setCellWidget(row, 3, progress_widget)
                
                # Tasks column
                tasks_text = f"{task['completed_tasks']}/{task['total_tasks']} ({task['failed_tasks']} failed)"
                tasks_item = QTableWidgetItem(tasks_text)
                self.tasks_table.setItem(row, 4, tasks_item)
                
                # Updated column
                updated = "N/A"
                if task.get("last_update"):
                    try:
                        update_time = datetime.fromisoformat(task["last_update"])
                        updated = update_time.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        updated = "Error parsing time"
                
                updated_item = QTableWidgetItem(updated)
                self.tasks_table.setItem(row, 5, updated_item)
                
                # Actions column - add buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                # Different buttons depending on status
                if task["status"] == "paused":
                    resume_btn = QPushButton("Resume")
                    resume_btn.clicked.connect(lambda checked=False, id=task["bulk_id"]: self.resume_task(id))
                    actions_layout.addWidget(resume_btn)
                elif task["status"] in ["pending", "in_progress"]:
                    pause_btn = QPushButton("Pause")
                    pause_btn.clicked.connect(lambda checked=False, id=task["bulk_id"]: self.pause_task(id))
                    actions_layout.addWidget(pause_btn)
                
                # Cancel button for active tasks
                if task["status"] in ["pending", "in_progress", "paused"]:
                    cancel_btn = QPushButton("Cancel")
                    cancel_btn.clicked.connect(lambda checked=False, id=task["bulk_id"]: self.cancel_task(id))
                    actions_layout.addWidget(cancel_btn)
                
                # Retry button for failed or partially completed tasks
                if task["status"] in ["failed", "partially_completed"]:
                    retry_btn = QPushButton("Retry Failed")
                    retry_btn.clicked.connect(lambda checked=False, id=task["bulk_id"]: self.retry_task(id))
                    actions_layout.addWidget(retry_btn)
                
                self.tasks_table.setCellWidget(row, 6, actions_widget)
            
            self.status_label.setText(f"Found {len(bulk_tasks)} bulk tasks")
            
        except Exception as e:
            self.status_label.setText(f"Error refreshing tasks: {str(e)}")
            logger.error(f"Error refreshing bulk tasks: {e}")
    
    def handle_progress(self, update):
        """Handle progress updates from the background service."""
        # Could refresh the task list here for real-time updates
        pass
    
    def new_bulk_task(self):
        """Create a new bulk OCR task."""
        dialog = BulkOCRDialog(self, self.repository_path)
        if dialog.exec_() == QDialog.Accepted:
            # Refresh tasks after creating a new one
            self.refresh_tasks()
    
    def pause_task(self, bulk_id):
        """Pause a bulk task."""
        if not self.background_service:
            return
            
        try:
            self.background_service.pause_bulk_task(bulk_id)
            self.status_label.setText(f"Paused task {bulk_id}")
            self.refresh_tasks()
        except Exception as e:
            self.status_label.setText(f"Error pausing task: {str(e)}")
    
    def resume_task(self, bulk_id):
        """Resume a paused bulk task."""
        if not self.background_service:
            return
            
        try:
            self.background_service.resume_bulk_task(bulk_id)
            self.status_label.setText(f"Resumed task {bulk_id}")
            self.refresh_tasks()
        except Exception as e:
            self.status_label.setText(f"Error resuming task: {str(e)}")
    
    def cancel_task(self, bulk_id):
        """Cancel a bulk task."""
        if not self.background_service:
            return
            
        # Confirm cancellation
        reply = QMessageBox.question(
            self, "Confirm Cancellation",
            f"Are you sure you want to cancel task {bulk_id}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.background_service.cancel_bulk_task(bulk_id)
                self.status_label.setText(f"Cancelled task {bulk_id}")
                self.refresh_tasks()
            except Exception as e:
                self.status_label.setText(f"Error cancelling task: {str(e)}")
    
    def retry_task(self, bulk_id):
        """Retry failed tasks in a bulk operation."""
        if not self.background_service:
            return
            
        try:
            count = self.background_service.retry_failed_bulk_tasks(bulk_id)
            self.status_label.setText(f"Retrying {count} failed tasks for {bulk_id}")
            self.refresh_tasks()
        except Exception as e:
            self.status_label.setText(f"Error retrying tasks: {str(e)}")


class ChroniclingAmericaBulkOCRTab(QWidget):
    """Tab for bulk OCR processing of ChroniclingAmerica downloads."""
    
    def __init__(self, parent=None, db_path=None):
        """
        Initialize the bulk OCR tab.
        
        Args:
            parent: Parent widget
            db_path: Path to the database
        """
        super().__init__(parent)
        
        # Get repository path from database path
        self.repository_path = None
        if db_path:
            self.repository_path = os.path.dirname(db_path)
        
        # Initialize UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Create splitter for flexible layout
        splitter = QSplitter(Qt.Vertical)
        
        # Bulk processing tabs
        tabs = QTabWidget()
        
        # Add monitoring tab
        monitor_tab = BulkProcessingMonitor(tabs, self.repository_path)
        tabs.addTab(monitor_tab, "Task Monitor")
        
        # Add to splitter
        splitter.addWidget(tabs)
        
        # Add detail panel
        details_group = QGroupBox("Processing Details")
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        splitter.addWidget(details_group)
        
        # Set initial size
        splitter.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)])
        
        main_layout.addWidget(splitter)
    
    def add_detail(self, message):
        """Add a message to the details panel."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.details_text.append(f"[{timestamp}] {message}")


# For testing the dialog directly
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Test repository path
    repo_path = "/mnt/c/AI/Nova/test_repository"
    
    # Create and show dialog
    dialog = BulkOCRDialog(repository_path=repo_path)
    dialog.show()
    
    sys.exit(app.exec_())