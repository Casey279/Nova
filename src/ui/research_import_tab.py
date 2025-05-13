# File: research_import_tab.py

import sys
import os
# Ensure the src directory is in the path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
print(f"Research import tab - Python path: {sys.path}")
from services import ImportService, SourceService, DatabaseError
from utils import file_utils, date_utils

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QFileDialog, QListWidget, QListWidgetItem,
                            QMessageBox, QProgressBar, QGroupBox, QComboBox,
                            QCheckBox, QLineEdit, QTextEdit, QGridLayout, QSplitter,
                            QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Import subtabs
try:
    from .chronicling_america_tab import ChroniclingAmericaTab
    CHRONICLING_AMERICA_AVAILABLE = True
except ImportError:
    CHRONICLING_AMERICA_AVAILABLE = False



class ImportWorker(QThread):
    """Worker thread for handling file imports."""
    
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(dict)  # results
    error_signal = pyqtSignal(str)  # error message
    
    def __init__(self, import_service, file_paths):
        """
        Initialize the import worker.
        
        Args:
            import_service: ImportService instance
            file_paths: List of file paths to import
        """
        super().__init__()
        self.import_service = import_service
        self.file_paths = file_paths
    
    def run(self):
        """Run the import process."""
        try:
            results = {'successful': [], 'failed': []}
            total = len(self.file_paths)
            
            for i, file_path in enumerate(self.file_paths):
                try:
                    result = self.import_service.import_file(file_path)
                    results['successful'].append(result)
                except Exception as e:
                    results['failed'].append({
                        'file_path': file_path,
                        'error': str(e)
                    })
                
                # Report progress
                self.progress_signal.emit(i + 1, total)
            
            # Report finished
            self.finished_signal.emit(results)
            
        except Exception as e:
            self.error_signal.emit(str(e))

class ResearchImportTab(QWidget):
    """
    Tab for importing research materials into the database.
    Allows selection and import of various file types.
    """
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the research import tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        
        # Create services
        self.import_service = ImportService(db_path)
        self.source_service = SourceService(db_path)
        
        # Initialize UI
        self.setup_ui()
        
        # Set default values
        self.last_directory = ""
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Create tab widget for subtabs
        self.tab_widget = QTabWidget()
        
        # Create the file import tab (original functionality)
        self.file_import_tab = QWidget()
        self.setup_file_import_tab()
        self.tab_widget.addTab(self.file_import_tab, "File Import")
        
        # Add ChroniclingAmerica tab if available
        if CHRONICLING_AMERICA_AVAILABLE:
            self.chronicling_america_tab = ChroniclingAmericaTab(self.db_path)
            self.tab_widget.addTab(self.chronicling_america_tab, "Chronicling America")
        
        # Add the tab widget to the main layout
        main_layout.addWidget(self.tab_widget)
        
        # Status label at the bottom of the main tab
        self.main_status_label = QLabel("")
        main_layout.addWidget(self.main_status_label)
    
    def setup_file_import_tab(self):
        """Set up the file import tab components."""
        file_import_layout = QVBoxLayout(self.file_import_tab)
        
        # Create a splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Top section: File selection
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout()
        
        button_layout = QHBoxLayout()
        
        self.select_files_button = QPushButton("Select Files")
        self.select_files_button.clicked.connect(self.select_files)
        
        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_folder)
        
        self.clear_button = QPushButton("Clear List")
        self.clear_button.clicked.connect(self.clear_file_list)
        
        button_layout.addWidget(self.select_files_button)
        button_layout.addWidget(self.select_folder_button)
        button_layout.addWidget(self.clear_button)
        
        file_layout.addLayout(button_layout)
        
        # File list
        self.file_list = QListWidget()
        file_layout.addWidget(self.file_list)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItems([
            "All Files (*.*)",
            "Text Files (*.txt)",
            "PDF Files (*.pdf)",
            "Word Documents (*.doc;*.docx)",
            "Spreadsheets (*.csv;*.xls;*.xlsx)"
        ])
        
        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.file_type_combo)
        filter_layout.addStretch()
        
        file_layout.addLayout(filter_layout)
        
        file_group.setLayout(file_layout)
        top_layout.addWidget(file_group)
        
        # Middle section: Import options
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        
        options_group = QGroupBox("Import Options")
        options_layout = QGridLayout()
        
        # Date format
        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems([
            "Auto-detect",
            "YYYY-MM-DD",
            "MM-DD-YYYY",
            "DD-MM-YYYY",
            "YYYY/MM/DD",
            "MM/DD/YYYY",
            "DD/MM/YYYY"
        ])
        
        # Source type
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems([
            "Auto-detect",
            "Document",
            "Article",
            "Book",
            "Letter",
            "Report",
            "Newspaper",
            "Interview",
            "Transcript"
        ])
        
        # Options
        self.auto_extract_check = QCheckBox("Auto-extract metadata from filename")
        self.auto_extract_check.setChecked(True)
        
        self.process_content_check = QCheckBox("Process content for entities")
        self.process_content_check.setChecked(True)
        
        # Add to layout
        options_layout.addWidget(QLabel("Date Format:"), 0, 0)
        options_layout.addWidget(self.date_format_combo, 0, 1)
        
        options_layout.addWidget(QLabel("Source Type:"), 1, 0)
        options_layout.addWidget(self.source_type_combo, 1, 1)
        
        options_layout.addWidget(self.auto_extract_check, 2, 0, 1, 2)
        options_layout.addWidget(self.process_content_check, 3, 0, 1, 2)
        
        options_group.setLayout(options_layout)
        middle_layout.addWidget(options_group)
        
        # Meta data preview
        metadata_group = QGroupBox("Metadata Preview")
        metadata_layout = QVBoxLayout()
        
        self.metadata_preview = QTextEdit()
        self.metadata_preview.setReadOnly(True)
        metadata_layout.addWidget(self.metadata_preview)
        
        metadata_group.setLayout(metadata_layout)
        middle_layout.addWidget(metadata_group)
        
        # Bottom section: Import controls
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar)
        
        # Import button
        import_layout = QHBoxLayout()
        
        self.import_button = QPushButton("Import Files")
        self.import_button.clicked.connect(self.import_files)
        self.import_button.setEnabled(False)
        
        import_layout.addStretch()
        import_layout.addWidget(self.import_button)
        
        bottom_layout.addLayout(import_layout)
        
        # Status label
        self.status_label = QLabel("")
        bottom_layout.addWidget(self.status_label)
        
        # Add widgets to splitter
        splitter.addWidget(top_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(bottom_widget)
        
        # Set initial sizes (50% for top, 30% for middle, 20% for bottom)
        splitter.setSizes([500, 300, 200])
        
        # Add splitter to main layout
        file_import_layout.addWidget(splitter)
        
        # Connect signals
        self.file_list.itemSelectionChanged.connect(self.update_metadata_preview)
    
    def select_files(self):
        """Open file dialog to select files for import."""
        filter_text = self.file_type_combo.currentText()
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Import",
            self.last_directory,
            filter_text
        )
        
        if file_paths:
            self.last_directory = os.path.dirname(file_paths[0])
            self.add_files_to_list(file_paths)
    
    def select_folder(self):
        """Open folder dialog to select a folder for import."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Import",
            self.last_directory
        )
        
        if folder_path:
            self.last_directory = folder_path
            
            # Get filter extensions
            filter_text = self.file_type_combo.currentText()
            
            if filter_text == "All Files (*.*)":
                # Import all supported file types
                extensions = ['.txt', '.pdf', '.doc', '.docx', '.csv', '.xls', '.xlsx']
            else:
                # Extract extensions from filter text
                extensions = []
                start_idx = filter_text.find('(')
                end_idx = filter_text.find(')')
                
                if start_idx != -1 and end_idx != -1:
                    extensions_str = filter_text[start_idx+1:end_idx]
                    extensions = [ext.strip() for ext in extensions_str.split(';')]
                    extensions = [ext[1:] if ext.startswith('*.') else ext for ext in extensions]
            
            # Get all files in directory with matching extensions
            file_paths = []
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in extensions:
                        file_paths.append(os.path.join(root, file))
            
            self.add_files_to_list(file_paths)
    
    def add_files_to_list(self, file_paths):
        """
        Add files to the list widget.
        
        Args:
            file_paths: List of file paths to add
        """
        for file_path in file_paths:
            # Check if file is already in the list
            items = self.file_list.findItems(file_path, Qt.MatchExactly)
            if not items:
                item = QListWidgetItem(file_path)
                self.file_list.addItem(item)
        
        # Enable import button if files are added
        self.import_button.setEnabled(self.file_list.count() > 0)
    
    def clear_file_list(self):
        """Clear the file list."""
        self.file_list.clear()
        self.import_button.setEnabled(False)
        self.metadata_preview.clear()

    def set_project_info(self, project_folder):
        """
        Update the tab with the selected project folder information.
        
        Args:
            project_folder (str): Path to the selected project folder
        """
        # Store the project folder path
        self.project_folder = project_folder
        self.last_directory = project_folder
        
        # Update main UI to show current project
        project_name = os.path.basename(project_folder)
        self.main_status_label.setText(f"Current Project: {project_name}")
        
        # Update status in the file import tab
        self.status_label.setText(f"Current Project: {project_name}")
        
        # Create downloads directory for the project
        downloads_dir = os.path.join(project_folder, "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Update chronicling america tab if available
        if CHRONICLING_AMERICA_AVAILABLE and hasattr(self, 'chronicling_america_tab'):
            chronicling_america_dir = os.path.join(downloads_dir, "chroniclingamerica")
            os.makedirs(chronicling_america_dir, exist_ok=True)
            self.chronicling_america_tab.download_directory = chronicling_america_dir
        
        # Clear existing files in the file import tab
        self.clear_file_list()
        
        # Optionally, list files from the project folder
        try:
            # Get filter extensions based on current selection
            filter_text = self.file_type_combo.currentText()
            
            if filter_text == "All Files (*.*)":
                # Import all supported file types
                extensions = ['.txt', '.pdf', '.doc', '.docx', '.csv', '.xls', '.xlsx']
            else:
                # Extract extensions from filter text
                extensions = []
                start_idx = filter_text.find('(')
                end_idx = filter_text.find(')')
                
                if start_idx != -1 and end_idx != -1:
                    extensions_str = filter_text[start_idx+1:end_idx]
                    extensions = [ext.strip() for ext in extensions_str.split(';')]
                    extensions = [ext[1:] if ext.startswith('*.') else ext for ext in extensions]
            
            # Get all files in directory with matching extensions
            file_paths = []
            for root, _, files in os.walk(project_folder):
                for file in files:
                    file_ext = os.path.splitext(file)[1].lower()
                    if any(file_ext == ext.lower() for ext in extensions):
                        file_paths.append(os.path.join(root, file))
            
            # Add files to list
            self.add_files_to_list(file_paths)
            
        except Exception as e:
            self.status_label.setText(f"Error loading project files: {str(e)}")

    def update_metadata_preview(self):
        """Update metadata preview based on selected file."""
        selected_items = self.file_list.selectedItems()
        
        if not selected_items:
            self.metadata_preview.clear()
            return
        
        file_path = selected_items[0].text()
        file_name = os.path.basename(file_path)
        
        try:
            # Parse metadata from filename
            metadata = self.import_service.parse_file_name(file_name)
            
            # Format for display
            preview_text = f"File: {file_name}\n\n"
            preview_text += f"Title: {metadata.get('title', '')}\n"
            preview_text += f"Author: {metadata.get('author', '')}\n"
            preview_text += f"Type: {metadata.get('source_type', '')}\n"
            
            date_str = metadata.get('publication_date', '')
            if date_str:
                formatted_date = date_utils.format_date(date_utils.parse_date(date_str), '%B %d, %Y')
                preview_text += f"Date: {formatted_date}\n"
            else:
                preview_text += "Date: Not detected\n"
            
            preview_text += f"URL: {metadata.get('url', '')}\n"
            
            # Add file info
            file_size = file_utils.get_file_size(file_path)
            formatted_size = file_utils.format_file_size(file_size)
            preview_text += f"\nFile Size: {formatted_size}\n"
            
            mime_type = file_utils.get_mime_type(file_path)
            preview_text += f"MIME Type: {mime_type}\n"
            
            self.metadata_preview.setPlainText(preview_text)
            
        except Exception as e:
            self.metadata_preview.setPlainText(f"Error parsing metadata: {str(e)}")
    
    def import_files(self):
        """Import selected files into the database."""
        # Get file paths from list
        file_paths = []
        for i in range(self.file_list.count()):
            file_paths.append(self.file_list.item(i).text())
        
        if not file_paths:
            return
        
        # Clear progress
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting import...")
        
        # Create and start import worker
        self.import_worker = ImportWorker(self.import_service, file_paths)
        
        # Connect signals
        self.import_worker.progress_signal.connect(self.update_import_progress)
        self.import_worker.finished_signal.connect(self.import_completed)
        self.import_worker.error_signal.connect(self.import_error)
        
        # Disable UI during import
        self.set_ui_enabled(False)
        
        # Start import
        self.import_worker.start()
    
    def update_import_progress(self, current, total):
        """
        Update progress bar.
        
        Args:
            current: Current progress
            total: Total items
        """
        percent = (current / total) * 100
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(f"Importing file {current} of {total}...")
    
    def import_completed(self, results):
        """
        Handle import completion.
        
        Args:
            results: Import results
        """
        successful = results.get('successful', [])
        failed = results.get('failed', [])
        
        total = len(successful) + len(failed)
        
        # Update UI
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Import completed: {len(successful)} successful, {len(failed)} failed.")
        
        # Show result message
        message = f"Import completed.\n\n"
        message += f"Successfully imported: {len(successful)} files.\n"
        message += f"Failed imports: {len(failed)} files.\n\n"
        
        if failed:
            message += "Failed files:\n"
            for failure in failed[:5]:  # Show first 5 failures
                file_name = os.path.basename(failure['file_path'])
                message += f"• {file_name}: {failure['error']}\n"
            
            if len(failed) > 5:
                message += f"...and {len(failed) - 5} more.\n"
        
        QMessageBox.information(self, "Import Results", message)
        
        # Clear file list if all successful
        if not failed:
            self.clear_file_list()
        else:
            # Remove successful files from list
            successful_paths = [result['file_name'] for result in successful]
            
            for i in range(self.file_list.count() - 1, -1, -1):
                item = self.file_list.item(i)
                file_name = os.path.basename(item.text())
                
                if file_name in successful_paths:
                    self.file_list.takeItem(i)
        
        # Re-enable UI
        self.set_ui_enabled(True)
    
    def import_error(self, error_message):
        """
        Handle import error.
        
        Args:
            error_message: Error message
        """
        self.status_label.setText(f"Import failed: {error_message}")
        
        QMessageBox.critical(self, "Import Error", f"Import failed: {error_message}")
        
        # Re-enable UI
        self.set_ui_enabled(True)
    
    def set_ui_enabled(self, enabled):
        """
        Enable or disable UI elements during import.
        
        Args:
            enabled: Whether UI should be enabled
        """
        self.select_files_button.setEnabled(enabled)
        self.select_folder_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.import_button.setEnabled(enabled and self.file_list.count() > 0)
        self.file_type_combo.setEnabled(enabled)
        self.date_format_combo.setEnabled(enabled)
        self.source_type_combo.setEnabled(enabled)
        self.auto_extract_check.setEnabled(enabled)
        self.process_content_check.setEnabled(enabled)