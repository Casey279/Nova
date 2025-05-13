#!/usr/bin/env python3
# File: repository_tab.py

import os
import sys
import datetime
import json
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
                            QPushButton, QLabel, QLineEdit, QComboBox, QGroupBox,
                            QFormLayout, QTextEdit, QTableWidget, QTableWidgetItem,
                            QHeaderView, QFileDialog, QMessageBox, QProgressBar,
                            QDateEdit, QCheckBox, QSpinBox, QScrollArea, QFrame,
                            QDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QPixmap, QImage, QColor

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.components.base_tab import BaseTab
from ui.components.search_panel import SearchPanel
from ui.components.table_panel import TablePanel
from ui.components.detail_panel import DetailPanel

# Import ChroniclingAmerica panel
try:
    from ui.repository_chronicling_america_panel import RepositoryChroniclingAmericaPanel
    CHRONICLING_AMERICA_AVAILABLE = True
except ImportError:
    CHRONICLING_AMERICA_AVAILABLE = False

# Import newspaper repository components
# Set up import paths
newspaper_repo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'newspaper_repository')
if newspaper_repo_path not in sys.path:
    sys.path.append(newspaper_repo_path)

try:
    # Try direct imports
    from repository_database import RepositoryDatabaseManager
    from file_manager import FileManager
    from ocr_processor import OCRProcessor
    from main_db_connector import MainDBConnector
    
    # Import BackgroundProcessingService without bulk_task
    try:
        from background_service import BackgroundProcessingService
    except (ImportError, SyntaxError) as e:
        logging.error(f"Error importing BackgroundProcessingService: {e}")
        
        # Simple mock class
        class BackgroundProcessingService:
            def __init__(self, *args, **kwargs):
                self.running = False
                self.bulk_task_manager = None
                self.task_queue = type('MockQueue', (), {'qsize': lambda self: 0})()
                self.in_progress_tasks = {}
                
            def start(self): self.running = True
            def stop(self): self.running = False
            def pause(self): pass
            def resume(self): pass
    
    # Try to import create_service_control_widget separately
    try:
        # First try separate module
        from create_service_control_widget import create_service_control_widget
    except ImportError:
        try:
            # Then try from background_service
            from background_service import create_service_control_widget
        except ImportError:
            # Create a simple function as fallback
            def create_service_control_widget(*args, **kwargs):
                from PyQt5.QtWidgets import QLabel
                return QLabel("Service control not available")
            
except ImportError as e:
    logging.error(f"Error importing repository modules: {e}")
    
    # Create dummy classes if all imports fail
    class RepositoryDatabaseManager:
        def __init__(self, *args, **kwargs): 
            pass
        
        def create_tables(self): 
            pass
            
        def get_newspaper_count(self): 
            return 0
    
    class FileManager:
        def __init__(self, *args, **kwargs): 
            pass
        
        def create_directory_structure(self): 
            pass
    
    class OCRProcessor:
        def __init__(self, *args, **kwargs): 
            pass
    
    class MainDBConnector:
        def __init__(self, *args, **kwargs): 
            pass
    
    class BackgroundProcessingService:
        def __init__(self, *args, **kwargs):
            self.running = False
            self.bulk_task_manager = None
            self.task_queue = type('MockQueue', (), {'qsize': lambda self: 0})()
            self.in_progress_tasks = {}
            
        def start(self): self.running = True
        def stop(self): self.running = False
        def pause(self): pass
        def resume(self): pass
        
    def create_service_control_widget(*args, **kwargs):
        return None

class ArticlePreviewWidget(QWidget):
    """Widget for displaying a preview of a newspaper article segment."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Image preview
        self.image_label = QLabel("No image selected")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(200)
        layout.addWidget(self.image_label)
        
        # Metadata display
        metadata_layout = QFormLayout()
        self.article_title = QLabel("N/A")
        self.article_date = QLabel("N/A")
        self.article_source = QLabel("N/A")
        
        metadata_layout.addRow("Title:", self.article_title)
        metadata_layout.addRow("Date:", self.article_date)
        metadata_layout.addRow("Source:", self.article_source)
        
        layout.addLayout(metadata_layout)
        
        # Text content
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        layout.addWidget(self.text_display)
        
        # Set layout
        self.setLayout(layout)
        
    def set_article(self, article_data):
        """Display article data in the preview widget."""
        if not article_data:
            return
            
        # Update metadata
        self.article_title.setText(article_data.get("title", "Untitled"))
        self.article_date.setText(article_data.get("date", "Unknown date"))
        self.article_source.setText(article_data.get("source", "Unknown source"))
        
        # Update text content
        self.text_display.setText(article_data.get("text", "No text available"))
        
        # Load image if available
        image_path = article_data.get("image_path", "")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.width(), 
                200, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            ))
        else:
            self.image_label.setText("No image available")


class RepositoryTab(BaseTab):
    """Tab for the newspaper repository browser and management."""
    
    def __init__(self, repository_db_path, main_db_path, repository_path):
        """
        Initialize the repository tab.

        Args:
            repository_db_path: Path to the repository database
            main_db_path: Path to the main Nova database
            repository_path: Path to the repository file storage
        """
        # Pass repository_db_path as db_path to BaseTab
        super().__init__(db_path=repository_db_path, parent=None)

        # Create main layout for repository tab - this is needed because BaseTab's
        # init_ui method creates a layout but doesn't store it as an instance attribute
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.repository_db_path = repository_db_path
        self.main_db_path = main_db_path
        self.repository_path = repository_path

        # Initialize repository database
        self.repo_db_manager = RepositoryDatabaseManager(repository_db_path)
        self.repo_db_manager.create_tables()

        # Ensure repository directories exist
        os.makedirs(repository_path, exist_ok=True)

        # Initialize file manager
        self.file_manager = FileManager(repository_path)
        self.file_manager.create_directory_structure()

        # Initialize background processing service
        try:
            self.background_service = BackgroundProcessingService(
                db_path=repository_db_path,
                base_directory=repository_path,
                max_retries=3,
                retry_delay=60,
                max_concurrent_tasks=2
            )
            # Skip bulk task manager to avoid circular import issues
            self.background_service.bulk_task_manager = None
        except Exception as e:
            import logging
            logging.error(f"Error initializing background service: {e}")
            # Create a minimal implementation to avoid errors
            self.background_service = BackgroundProcessingService(
                db_path=repository_db_path,
                base_directory=repository_path
            )

        # Set up UI components specific to repository tab
        self.setup_repository_components()
        
    def closeEvent(self, event):
        """Handle tab close event to properly shut down the background service."""
        # Stop the background service if it's running
        if hasattr(self, 'background_service') and self.background_service:
            try:
                if hasattr(self.background_service, 'running') and self.background_service.running:
                    # Confirm with user if there are pending tasks
                    queue_size = self.background_service.task_queue.qsize() if hasattr(self.background_service, 'task_queue') else 0
                    in_progress = len(self.background_service.in_progress_tasks) if hasattr(self.background_service, 'in_progress_tasks') else 0
                    
                    if queue_size > 0 or in_progress > 0:
                        msg_box = QMessageBox()
                        msg_box.setWindowTitle("Background Service Running")
                        msg_box.setText(f"The background service is still running with "
                                      f"{queue_size} tasks in queue and {in_progress} tasks in progress.")
                        msg_box.setInformativeText("Do you want to stop the service?")
                        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msg_box.setDefaultButton(QMessageBox.Yes)
                        
                        if msg_box.exec_() != QMessageBox.Yes:
                            event.ignore()
                            return
                    
                    # Stop the service
                    if hasattr(self.background_service, 'stop'):
                        self.background_service.stop()
            except Exception as e:
                import logging
                logging.error(f"Error stopping background service: {e}")
            
        # Call the parent class closeEvent
        super().closeEvent(event)
    
    def init_ui(self):
        """Override the parent class init_ui to use our own layout."""
        # We're not calling super().init_ui() because we're using our own layout
        # that was created in __init__ as self.main_layout
        pass

    def setup_repository_components(self):
        """Initialize repository UI components."""
        # Initialize additional components
        self.ocr_processor = OCRProcessor()
        self.main_db_connector = MainDBConnector(self.repo_db_manager, self.main_db_path)
        
        # Create service control widget if function is available
        try:
            if callable(create_service_control_widget):
                # Check the number of parameters expected by the function
                import inspect
                sig = inspect.signature(create_service_control_widget)

                # Call with appropriate number of arguments
                if len(sig.parameters) == 1:
                    self.service_control = create_service_control_widget(self.background_service)
                elif len(sig.parameters) == 2:
                    # Assume second parameter is parent widget
                    self.service_control = create_service_control_widget(self.background_service, self)
                else:
                    # Default to a simple widget
                    self.service_control = QWidget()
                    logging.warning("create_service_control_widget has unexpected signature")
            else:
                self.service_control = QWidget()
        except Exception as e:
            logging.error(f"Error creating service control widget: {e}")
            self.service_control = QWidget()
            
        # Create tabs for different repository views
        self.repository_tabs = QTabWidget()
        
        # Browser tab
        self.browser_tab = QWidget()
        self.setup_browser_tab(self.browser_tab)
        self.repository_tabs.addTab(self.browser_tab, "Browse")
        
        # Import tab
        self.import_tab = QWidget()
        self.setup_import_tab(self.import_tab)
        self.repository_tabs.addTab(self.import_tab, "Import")
        
        # Chronicling America tab
        if CHRONICLING_AMERICA_AVAILABLE:
            self.ca_tab = RepositoryChroniclingAmericaPanel(
                self.repo_db_manager,
                self
            )
            self.repository_tabs.addTab(self.ca_tab, "Chronicling America")
        
        # Add repository tabs to main layout
        self.main_layout.addWidget(self.repository_tabs)
        
        # Add service control panel
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.StyledPanel)
        control_layout = QVBoxLayout(control_frame)
        control_layout.addWidget(QLabel("Background Service Control"))
        control_layout.addWidget(self.service_control)
        
        self.main_layout.addWidget(control_frame)
        
    def setup_browser_tab(self, tab):
        """Set up the repository browser tab."""
        layout = QVBoxLayout(tab)
        
        # Main split view
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: Search/filter
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Search box
        search_group = QGroupBox("Search")
        search_layout = QFormLayout()
        
        self.search_input = QLineEdit()
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_repository)
        
        search_row = QHBoxLayout()
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_button)
        
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addYears(-1))
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        
        search_layout.addRow("Keywords:", search_row)
        search_layout.addRow("Date From:", self.date_start)
        search_layout.addRow("Date To:", self.date_end)
        
        self.publication_combo = QComboBox()
        self.publication_combo.addItem("All Publications", 0)
        search_layout.addRow("Publication:", self.publication_combo)
        
        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group)
        
        # Filters
        filter_group = QGroupBox("Filters")
        filter_layout = QVBoxLayout()
        
        self.filter_has_ocr = QCheckBox("Has OCR Text")
        self.filter_has_images = QCheckBox("Has Images")
        
        filter_layout.addWidget(self.filter_has_ocr)
        filter_layout.addWidget(self.filter_has_images)
        
        filter_group.setLayout(filter_layout)
        left_layout.addWidget(filter_group)
        
        # Add to splitter
        splitter.addWidget(left_panel)
        
        # Middle panel: Results
        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Date", "Publication", "Title", "ID"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        middle_layout.addWidget(QLabel("Search Results:"))
        middle_layout.addWidget(self.results_table)
        
        # Add to splitter
        splitter.addWidget(middle_panel)
        
        # Right panel: Preview
        self.preview_widget = ArticlePreviewWidget()
        splitter.addWidget(self.preview_widget)
        
        # Set initial sizes
        splitter.setSizes([200, 400, 300])
        
        # Add to layout
        layout.addWidget(splitter)
        
    def setup_import_tab(self, tab):
        """Set up the import tab."""
        layout = QVBoxLayout(tab)
        
        # Source selection
        source_group = QGroupBox("Import Source")
        source_layout = QFormLayout()
        
        self.source_combo = QComboBox()
        self.source_combo.addItem("Local Files", "local")
        self.source_combo.addItem("Chronicling America", "ca")
        self.source_combo.addItem("Newspapers.com", "newspapers")
        
        source_layout.addRow("Source:", self.source_combo)
        
        # Source directory
        self.source_path = QLineEdit()
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_source_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.source_path)
        path_layout.addWidget(self.browse_button)
        
        source_layout.addRow("Source Path:", path_layout)
        
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)
        
        # Import options
        options_group = QGroupBox("Import Options")
        options_layout = QVBoxLayout()
        
        self.recursive_check = QCheckBox("Import Recursively")
        self.ocr_check = QCheckBox("Perform OCR")
        self.ocr_check.setChecked(True)
        
        options_layout.addWidget(self.recursive_check)
        options_layout.addWidget(self.ocr_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Progress area
        progress_group = QGroupBox("Import Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Ready to import")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.import_button = QPushButton("Start Import")
        self.import_button.clicked.connect(self.start_import)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_import)
        self.cancel_button.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def browse_source_path(self):
        """Browse for source directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", ""
        )
        if directory:
            self.source_path.setText(directory)
    
    def search_repository(self):
        """Search the repository."""
        # This would be implemented to query the repository database
        QMessageBox.information(
            self, "Search", 
            "This search functionality would be implemented to query the repository database."
        )
    
    def start_import(self):
        """Start the import process."""
        # This would be implemented to start the import process
        QMessageBox.information(
            self, "Import", 
            "This import functionality would be implemented to start the import process."
        )
    
    def cancel_import(self):
        """Cancel the import process."""
        # This would be implemented to cancel the import process
        QMessageBox.information(
            self, "Cancel Import", 
            "This would cancel the import process."
        )


# For testing
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create a test environment
    repo_db_path = "test_repository.db"
    main_db_path = "test_nova.db"
    repo_path = "test_repository"
    
    widget = RepositoryTab(repo_db_path, main_db_path, repo_path)
    widget.show()
    
    sys.exit(app.exec_())