# File: chronicling_america_tab_improved.py
# Improved version of the Chronicling America tab with better UI and functionality

import sys
import os
import re
import json
import requests
from datetime import datetime
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QLineEdit, QListWidget, QListWidgetItem,
                            QMessageBox, QProgressBar, QGroupBox, QComboBox,
                            QDateEdit, QCheckBox, QTextEdit, QGridLayout, QSplitter,
                            QSpinBox, QFormLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate

from services import ImportService

try:
    # Try to import the improved client first
    from api.chronicling_america_improved import ImprovedChroniclingAmericaClient as ChroniclingAmericaClient
    API_AVAILABLE = True
    USING_IMPROVED_CLIENT = True
except ImportError:
    # Fall back to the original client if improved version is not available
    try:
        from api.chronicling_america import ChroniclingAmericaClient
        API_AVAILABLE = True
        USING_IMPROVED_CLIENT = False
    except ImportError:
        API_AVAILABLE = False
        USING_IMPROVED_CLIENT = False


class SearchWorker(QThread):
    """Worker thread for searching ChroniclingAmerica."""
    
    progress_signal = pyqtSignal(int, int)  # current, total (for download phase)
    search_results_signal = pyqtSignal(list, dict)  # results, pagination
    finished_signal = pyqtSignal(dict)  # results from download/import
    error_signal = pyqtSignal(str)  # error message
    
    def __init__(self, search_params, download_dir, max_pages=1, 
                download_formats=None, import_service=None):
        """
        Initialize the search worker.
        
        Args:
            search_params: Parameters for the search
            download_dir: Directory to save downloads
            max_pages: Maximum number of search result pages
            download_formats: Formats to download
            import_service: ImportService instance for importing results
        """
        super().__init__()
        self.search_params = search_params
        self.download_dir = download_dir
        self.max_pages = max_pages
        self.download_formats = download_formats or ['pdf', 'ocr']
        self.import_service = import_service
        self.download_results = []
        self.search_only = self.import_service is None
        
    def run(self):
        """Run the search and download process."""
        try:
            if not API_AVAILABLE:
                self.error_signal.emit("ChroniclingAmerica API is not available")
                return
            
            # Create API client
            client = ChroniclingAmericaClient(output_directory=self.download_dir)
            
            if self.search_only:
                # Search only
                pages, pagination = client.search_pages(
                    keywords=self.search_params.get('keywords'),
                    lccn=self.search_params.get('lccn'),
                    state=self.search_params.get('state'),
                    date_start=self.search_params.get('date_start'),
                    date_end=self.search_params.get('date_end'),
                    page=1,  # Start with first page
                    max_pages=self.max_pages  # Use the max_pages parameter
                )
                
                # Send results to UI
                self.search_results_signal.emit(pages, pagination)
                
            else:
                # Search and download
                results = self.import_service.import_from_chronicling_america(
                    search_params=self.search_params,
                    download_dir=self.download_dir,
                    max_pages=self.max_pages,
                    formats=self.download_formats
                )
                
                # Report finished
                self.finished_signal.emit(results)
                
        except Exception as e:
            self.error_signal.emit(str(e))


class ChroniclingAmericaTabImproved(QWidget):
    """
    Improved tab for searching and importing content from the ChroniclingAmerica API.
    """
    
    def __init__(self, db_path, parent=None):
        """
        Initialize the ChroniclingAmerica search tab.
        
        Args:
            db_path (str): Path to the database
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        self.db_path = db_path
        
        # Create services
        self.import_service = ImportService(db_path)
        
        # Initialize UI
        self.setup_ui()
        
        # Set default values
        self.download_directory = os.path.join(os.path.dirname(db_path), "downloads", "chroniclingamerica")
        os.makedirs(self.download_directory, exist_ok=True)
        
        # Disable tab if API is not available
        self.setEnabled(API_AVAILABLE)
        if not API_AVAILABLE:
            self.status_label.setText("ChroniclingAmerica API is not available. Make sure the api module is installed correctly.")
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Create a splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Top section: Search parameters
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        search_group = QGroupBox("Search Parameters")
        search_layout = QFormLayout()
        
        # State selection - moved to the top
        self.state_combo = QComboBox()
        self.state_combo.addItem("All", "")  # All states option at the top
        
        # Add state abbreviations in alphabetical order
        state_abbrevs = [
            ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"), 
            ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"), 
            ("DC", "District of Columbia"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"), 
            ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"), 
            ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"), 
            ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"), 
            ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), 
            ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), 
            ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), 
            ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"), ("PR", "Puerto Rico"), 
            ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"), 
            ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"), 
            ("VI", "Virgin Islands"), ("VA", "Virginia"), ("WA", "Washington"), 
            ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming")
        ]
        
        # Add states to the combo box
        for abbrev, name in sorted(state_abbrevs, key=lambda x: x[1]):  # Sort by state name
            self.state_combo.addItem(name, abbrev)
        
        # Enable keyboard navigation
        self.state_combo.setEditable(True)
        self.state_combo.setInsertPolicy(QComboBox.NoInsert)  # Don't allow inserting new items
        
        # Connect state selection change event
        self.state_combo.currentIndexChanged.connect(self.on_state_changed)
        
        search_layout.addRow("Select State:", self.state_combo)
        
        # Newspaper selection - updated to be dynamically populated based on state
        self.newspaper_combo = QComboBox()
        self.newspaper_combo.addItem("Select Title", "")  # Changed from "All Newspapers" to "Select Title"
        search_layout.addRow("Newspaper:", self.newspaper_combo)
        
        # Custom LCCN checkbox and field
        custom_lccn_layout = QHBoxLayout()
        
        # Checkbox for enabling custom LCCN input
        self.custom_lccn_check = QCheckBox()
        self.custom_lccn_check.setChecked(False)
        self.custom_lccn_check.stateChanged.connect(self.on_custom_lccn_toggled)
        
        # Custom LCCN input field
        self.lccn_edit = QLineEdit()
        self.lccn_edit.setEnabled(False)
        self.lccn_edit.setPlaceholderText("Enter LCCN (e.g., sn83045604)")
        
        # Search button for LCCN
        self.lccn_search_button = QPushButton("Search")
        self.lccn_search_button.setEnabled(False)
        self.lccn_search_button.clicked.connect(self.on_lccn_search)
        
        custom_lccn_layout.addWidget(self.lccn_edit)
        custom_lccn_layout.addWidget(self.lccn_search_button)
        
        search_layout.addRow("Custom LCCN:", self.custom_lccn_check)
        search_layout.addRow("", custom_lccn_layout)
        
        # Date range - kept as is but moved below LCCN
        date_layout = QHBoxLayout()
        
        self.date_start_edit = QDateEdit()
        self.date_start_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_start_edit.setCalendarPopup(True)
        self.date_start_edit.setDate(QDate(1800, 1, 1))
        
        self.date_end_edit = QDateEdit()
        self.date_end_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_end_edit.setCalendarPopup(True)
        self.date_end_edit.setDate(QDate.currentDate())
        
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.date_start_edit)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.date_end_edit)
        
        search_layout.addRow("Date Range:", date_layout)
        
        # Keywords - moved to the bottom
        self.keywords_edit = QLineEdit()
        search_layout.addRow("Keywords:", self.keywords_edit)
        
        # Search button
        search_button_layout = QHBoxLayout()
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search)
        search_button_layout.addStretch()
        search_button_layout.addWidget(self.search_button)
        
        search_layout.addRow("", search_button_layout)
        
        search_group.setLayout(search_layout)
        top_layout.addWidget(search_group)
        
        # Store the newspaper data by state
        self.newspapers_by_state = {}
        
        # Middle section: Search results
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout()
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.itemSelectionChanged.connect(self.update_result_preview)
        results_layout.addWidget(self.results_list)
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        
        self.page_label = QLabel("Page 1 of 1")
        self.prev_button = QPushButton("Previous Page")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)
        
        self.next_button = QPushButton("Next Page")
        self.next_button.clicked.connect(self.next_page)
        self.next_button.setEnabled(False)
        
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)
        
        results_layout.addLayout(pagination_layout)
        
        results_group.setLayout(results_layout)
        middle_layout.addWidget(results_group)
        
        # Result preview
        preview_group = QGroupBox("Result Preview")
        preview_layout = QVBoxLayout()
        
        self.result_preview = QTextEdit()
        self.result_preview.setReadOnly(True)
        preview_layout.addWidget(self.result_preview)
        
        preview_group.setLayout(preview_layout)
        middle_layout.addWidget(preview_group)
        
        # Bottom section: Download and import controls
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        download_group = QGroupBox("Download and Import")
        download_layout = QGridLayout()
        
        # Download options
        self.download_pdf_check = QCheckBox("PDF")
        self.download_pdf_check.setChecked(False)
        
        self.download_jp2_check = QCheckBox("JP2 (high-res image)")
        self.download_jp2_check.setChecked(True)
        
        self.download_ocr_check = QCheckBox("OCR Text")
        self.download_ocr_check.setChecked(False)
        
        self.download_json_check = QCheckBox("JSON Metadata")
        self.download_json_check.setChecked(False)
        
        download_layout.addWidget(QLabel("Download Formats:"), 0, 0)
        download_layout.addWidget(self.download_pdf_check, 0, 1)
        download_layout.addWidget(self.download_jp2_check, 0, 2)
        download_layout.addWidget(self.download_ocr_check, 1, 1)
        download_layout.addWidget(self.download_json_check, 1, 2)
        
        # Max pages to download
        max_pages_layout = QHBoxLayout()
        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(1, 100)
        self.max_pages_spin.setValue(1)
        max_pages_layout.addWidget(QLabel("Max Results Pages:"))
        max_pages_layout.addWidget(self.max_pages_spin)
        max_pages_layout.addStretch()
        
        download_layout.addLayout(max_pages_layout, 2, 0, 1, 3)
        
        # Import options
        self.import_check = QCheckBox("Import to Database")
        self.import_check.setChecked(True)
        download_layout.addWidget(self.import_check, 3, 0, 1, 3)
        
        # Download button
        download_button_layout = QHBoxLayout()
        self.download_selected_button = QPushButton("Download Selected")
        self.download_selected_button.clicked.connect(lambda: self.download(selected_only=True))
        self.download_selected_button.setEnabled(False)
        
        self.download_all_button = QPushButton("Download All Results")
        self.download_all_button.clicked.connect(lambda: self.download(selected_only=False))
        self.download_all_button.setEnabled(False)
        
        download_button_layout.addWidget(self.download_selected_button)
        download_button_layout.addWidget(self.download_all_button)
        
        download_layout.addLayout(download_button_layout, 4, 0, 1, 3)
        
        download_group.setLayout(download_layout)
        bottom_layout.addWidget(download_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        bottom_layout.addWidget(self.status_label)
        
        # Add widgets to splitter
        splitter.addWidget(top_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(bottom_widget)
        
        # Set initial sizes (30% for top, 40% for middle, 30% for bottom)
        splitter.setSizes([300, 400, 300])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Store current page number and search parameters
        self.current_page = 1
        self.search_results = []
        self.pagination_info = {}
        self.current_search_params = {}
    
    def search(self):
        """Search for newspaper content."""
        # Get search parameters
        keywords = self.keywords_edit.text().strip()
        date_start = self.date_start_edit.date().toString("yyyy-MM-dd")
        date_end = self.date_end_edit.date().toString("yyyy-MM-dd")
        
        # Get state and LCCN based on UI mode
        state = None
        lccn = None
        
        # Check if we're in custom LCCN mode
        if self.custom_lccn_check.isChecked():
            # Use the custom LCCN
            lccn = self.lccn_edit.text().strip()
            # No state filter in this mode
        else:
            # Get state from dropdown
            state_name = self.state_combo.currentText()
            if state_name and state_name != "All":
                state = state_name
            
            # Get LCCN from newspaper dropdown
            selected_lccn = self.newspaper_combo.currentData()
            if selected_lccn:
                lccn = selected_lccn
        
        # Validate search parameters - at minimum we need a date range
        if not date_start or not date_end:
            QMessageBox.warning(
                self,
                "Date Range Required",
                "Please provide a date range for your search. Optional filters include keywords, LCCN, or state."
            )
            return
        
        # Show what we're searching for
        search_info = f"Searching for newspapers from {date_start} to {date_end}"
        if lccn:
            newspaper_title = ""
            for i in range(self.newspaper_combo.count()):
                if self.newspaper_combo.itemData(i) == lccn:
                    newspaper_title = self.newspaper_combo.itemText(i).split(" (")[0]
                    break
            
            if newspaper_title:
                search_info += f" from {newspaper_title}"
            else:
                search_info += f" with LCCN {lccn}"
        elif state:
            search_info += f" from {state}"
            
        if keywords:
            search_info += f" containing '{keywords}'"
            
        self.status_label.setText(search_info)
        
        # Store search parameters
        self.current_search_params = {
            'keywords': keywords,
            'state': state,
            'date_start': date_start,
            'date_end': date_end,
            'lccn': lccn
        }
        
        # Reset current page
        self.current_page = 1
        
        # Create worker for search
        self.search_worker = SearchWorker(
            search_params=self.current_search_params,
            download_dir=self.download_directory,
            max_pages=5,  # Use 5 pages by default for searching to get more results
            # Don't pass import_service to indicate search-only mode
            import_service=None
        )
        
        # Connect signals
        self.search_worker.search_results_signal.connect(self.search_results_received)
        self.search_worker.error_signal.connect(self.search_error)
        
        # Update UI
        self.status_label.setText("Searching...")
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.set_ui_enabled(False)
        
        # Clear previous results
        self.results_list.clear()
        self.result_preview.clear()
        
        # Start search
        self.search_worker.start()
    
    def search_results_received(self, pages, pagination):
        """
        Handle search results.
        
        Args:
            pages: List of PageMetadata objects
            pagination: Pagination information
        """
        # Store results
        self.search_results = pages
        self.pagination_info = pagination
        
        # Update UI
        self.results_list.clear()
        
        if not pages:
            self.status_label.setText("No results found.")
            self.set_ui_enabled(True)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            return
        
        # Add results to list
        for page in pages:
            item_text = f"{page.title} - {page.issue_date} (Page {page.sequence})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, page)
            self.results_list.addItem(item)
        
        # Update pagination controls
        total_pages = pagination.get('total_pages', 1)
        self.page_label.setText(f"Page {self.current_page} of {total_pages}")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < total_pages)
        
        # Update status
        total_items = pagination.get('total_items', 0)
        self.status_label.setText(f"Found {total_items} results. Displaying page {self.current_page} of {total_pages}.")
        
        # Enable download buttons
        self.download_selected_button.setEnabled(True)
        self.download_all_button.setEnabled(True)
        
        # Reset progress bar
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # Re-enable UI
        self.set_ui_enabled(True)
    
    def search_error(self, error_message):
        """
        Handle search error.
        
        Args:
            error_message: Error message
        """
        self.status_label.setText(f"Search failed: {error_message}")
        
        QMessageBox.critical(self, "Search Error", f"Search failed: {error_message}")
        
        # Reset progress bar
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # Re-enable UI
        self.set_ui_enabled(True)
    
    def previous_page(self):
        """Go to the previous page of search results."""
        if self.current_page > 1:
            self.current_page -= 1
            self.current_search_params['page'] = self.current_page
            self.search()
    
    def next_page(self):
        """Go to the next page of search results."""
        total_pages = self.pagination_info.get('total_pages', 1)
        if self.current_page < total_pages:
            self.current_page += 1
            self.current_search_params['page'] = self.current_page
            self.search()
    
    def update_result_preview(self):
        """Update the preview based on selected result."""
        selected_items = self.results_list.selectedItems()
        
        if not selected_items:
            self.result_preview.clear()
            self.download_selected_button.setEnabled(False)
            return
        
        # Get the selected page metadata
        page = selected_items[0].data(Qt.UserRole)
        
        # Format for display
        preview_text = f"Title: {page.title}\n"
        preview_text += f"Date: {page.issue_date.strftime('%B %d, %Y')}\n"
        preview_text += f"Page Number: {page.sequence}\n"
        preview_text += f"LCCN: {page.lccn}\n\n"
        
        preview_text += "Available Formats:\n"
        if page.pdf_url:
            preview_text += "• PDF\n"
        if page.jp2_url:
            preview_text += "• JP2 (high-res image)\n"
        if page.ocr_url:
            preview_text += "• OCR Text\n"
        
        preview_text += f"\nView Online: {page.url}\n"
        
        self.result_preview.setPlainText(preview_text)
        self.download_selected_button.setEnabled(True)
    
    def download(self, selected_only=False):
        """
        Download and optionally import newspaper content.
        
        Args:
            selected_only: Whether to download only selected items
        """
        # Get formats to download
        formats = []
        if self.download_pdf_check.isChecked():
            formats.append('pdf')
        if self.download_jp2_check.isChecked():
            formats.append('jp2')
        if self.download_ocr_check.isChecked():
            formats.append('ocr')
        if self.download_json_check.isChecked():
            formats.append('json')
        
        if not formats:
            QMessageBox.warning(
                self,
                "Download Format Required",
                "Please select at least one format to download."
            )
            return
        
        # Get pages to download
        if selected_only:
            selected_items = self.results_list.selectedItems()
            if not selected_items:
                return
                
            # Get selected page metadata
            pages = [item.data(Qt.UserRole) for item in selected_items]
            
            # Create download params
            search_params = {
                'keywords': None,
                'state': None,
                'date_start': None,
                'date_end': None,
                'lccn': None,
                'specific_pages': pages
            }
            
        else:
            # Use current search parameters for downloading all results
            search_params = self.current_search_params
        
        # Get max pages
        max_pages = self.max_pages_spin.value()
        
        # Determine if we should import
        import_to_db = self.import_check.isChecked()
        
        # Create worker for download/import
        self.download_worker = SearchWorker(
            search_params=search_params,
            download_dir=self.download_directory,
            max_pages=max_pages,
            download_formats=formats,
            import_service=self.import_service if import_to_db else None
        )
        
        # Connect signals
        self.download_worker.progress_signal.connect(self.update_download_progress)
        self.download_worker.finished_signal.connect(self.download_completed)
        self.download_worker.error_signal.connect(self.download_error)
        
        # Update UI
        if selected_only:
            self.status_label.setText(f"Downloading {len(pages)} selected items...")
        else:
            total_items = self.pagination_info.get('total_items', 0)
            page_items = min(20, total_items)  # Typically 20 items per page
            self.status_label.setText(f"Downloading up to {page_items * max_pages} items...")
        
        self.progress_bar.setValue(0)
        self.set_ui_enabled(False)
        
        # Start download
        self.download_worker.start()
    
    def update_download_progress(self, current, total):
        """
        Update progress bar for download.
        
        Args:
            current: Current progress
            total: Total items
        """
        percent = (current / total) * 100
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(f"Downloading item {current} of {total}...")
    
    def download_completed(self, results):
        """
        Handle download completion.
        
        Args:
            results: Download/import results
        """
        successful = results.get('successful', [])
        failed = results.get('failed', [])
        total_downloaded = results.get('total_downloaded', 0)
        total_imported = results.get('total_imported', 0)
        
        # Update UI
        self.progress_bar.setValue(100)
        
        if self.import_check.isChecked():
            self.status_label.setText(
                f"Download and import completed: {len(successful)} imported, {len(failed)} failed."
            )
        else:
            self.status_label.setText(
                f"Download completed: {total_downloaded} downloaded."
            )
        
        # Show result message
        message = f"Operation completed.\n\n"
        
        if self.import_check.isChecked():
            message += f"Downloaded: {total_downloaded} items.\n"
            message += f"Successfully imported: {total_imported} items.\n"
            message += f"Failed imports: {len(failed)} items.\n\n"
            
            if failed:
                message += "Failed items:\n"
                for failure in failed[:5]:  # Show first 5 failures
                    message += f"• {failure.get('lccn', 'Unknown')}: {failure['error']}\n"
                
                if len(failed) > 5:
                    message += f"...and {len(failed) - 5} more.\n"
        else:
            message += f"Successfully downloaded: {total_downloaded} items.\n"
            message += f"Download directory: {self.download_directory}\n"
        
        QMessageBox.information(self, "Download Results", message)
        
        # Re-enable UI
        self.set_ui_enabled(True)
    
    def download_error(self, error_message):
        """
        Handle download error.
        
        Args:
            error_message: Error message
        """
        self.status_label.setText(f"Download failed: {error_message}")
        
        QMessageBox.critical(self, "Download Error", f"Download failed: {error_message}")
        
        # Re-enable UI
        self.set_ui_enabled(True)
    
    def on_state_changed(self, index):
        """
        Handle state selection change.
        
        When a state is selected, dynamically populate the newspaper dropdown
        with newspapers from that state.
        
        Args:
            index: Selected index in the state combo box
        """
        # Get the selected state abbreviation
        state_abbrev = self.state_combo.currentData()
        state_name = self.state_combo.currentText()
        
        if not state_name or state_name == "All":
            # Clear the newspaper combo box except for "Select Title"
            self.newspaper_combo.clear()
            self.newspaper_combo.addItem("Select Title", "")
            return
        
        self.status_label.setText(f"Loading newspapers for {state_name}...")
        self.set_ui_enabled(False)
        
        # Start a worker thread to fetch newspapers for this state
        # If we've already fetched them, use the cached data
        if state_abbrev in self.newspapers_by_state:
            # Use cached data
            self.update_newspaper_combo(self.newspapers_by_state[state_abbrev])
        else:
            # Fetch newspapers for this state
            self.fetch_newspapers_for_state(state_abbrev, state_name)
    
    def fetch_newspapers_for_state(self, state_abbrev, state_name):
        """
        Fetch newspapers for a specific state.

        Args:
            state_abbrev: Two-letter state abbreviation
            state_name: Full state name
        """
        try:
            # URL for the newspaper list
            url = f"https://chroniclingamerica.loc.gov/newspapers/"
            params = {'state': state_name}

            # Show status
            self.status_label.setText(f"Fetching newspapers for {state_name}...")
            self.progress_bar.setRange(0, 0)  # Set to indeterminate

            # Make the request to get the HTML page - no need for JSON format
            response = requests.get(url, params=params)
            html = response.text

            # Extract information using regex patterns specific to the Chronicling America table structure

            # LCCN - these appear in the href of the title links
            lccn_pattern = r'href="/lccn/([^/]+?)/"'

            # Title - the actual newspaper name in the title column
            title_pattern = r'<td\s+class="title"[^>]*>\s*<a\s+href="[^"]+"[^>]*>(.*?)</a>'

            # Place of publication (city, state)
            place_pattern = r'<td\s+class="place"[^>]*>(.*?)</td>'

            # Earliest issue date
            earliest_pattern = r'<td\s+class="date[^"]*earliest[^"]*">(.*?)</td>'

            # Latest issue date
            latest_pattern = r'<td\s+class="date[^"]*latest[^"]*">(.*?)</td>'

            # Find all matching elements - compile patterns for better performance
            lccn_regex = re.compile(lccn_pattern)
            title_regex = re.compile(title_pattern)
            place_regex = re.compile(place_pattern)
            earliest_regex = re.compile(earliest_pattern)
            latest_regex = re.compile(latest_pattern)

            lccns = lccn_regex.findall(html)
            titles = title_regex.findall(html)
            places = place_regex.findall(html)
            earliest_dates = earliest_regex.findall(html)
            latest_dates = latest_regex.findall(html)

            # Log what we found for debugging
            print(f"Found: {len(lccns)} LCCNs, {len(titles)} titles, {len(places)} places, {len(earliest_dates)} earliest dates, {len(latest_dates)} latest dates")

            # Deal with potential mismatches in number of items
            min_length = min(len(lccns), len(titles), len(places), len(earliest_dates), len(latest_dates))
            if min_length == 0:
                # If no items found with all information, try an alternative approach
                # Look for the table rows directly
                print("No complete items found, trying alternative extraction...")

                # Directly scrape the HTML manually
                # First, let's save the HTML to a file for debugging if needed
                with open("state_newspapers.html", "w", encoding="utf-8") as f:
                    f.write(html)

                # Get all table rows that might contain newspaper data
                # This is a more manual but reliable extraction method
                row_pattern = r'<tr[^>]*>(.*?)</tr>'
                row_regex = re.compile(row_pattern, re.DOTALL)
                row_matches = row_regex.findall(html)

                rows = []

                # Process each row manually
                for row_html in row_matches:
                    # Check if this row has an LCCN link
                    lccn_match = re.search(r'href="/lccn/([^/]+?)/"', row_html)
                    if not lccn_match:
                        continue

                    lccn = lccn_match.group(1)

                    # Extract title
                    title_match = re.search(r'<td[^>]*class="title"[^>]*>.*?<a[^>]*>(.*?)</a>', row_html, re.DOTALL)
                    title = title_match.group(1).strip() if title_match else ""

                    # Extract place
                    place_match = re.search(r'<td[^>]*class="place"[^>]*>(.*?)</td>', row_html, re.DOTALL)
                    place = place_match.group(1).strip() if place_match else ""

                    # Extract earliest date
                    earliest_match = re.search(r'<td[^>]*class="date[^"]*earliest[^"]*">(.*?)</td>', row_html, re.DOTALL)
                    earliest = earliest_match.group(1).strip() if earliest_match else ""

                    # Extract latest date
                    latest_match = re.search(r'<td[^>]*class="date[^"]*latest[^"]*">(.*?)</td>', row_html, re.DOTALL)
                    latest = latest_match.group(1).strip() if latest_match else ""

                    # If we have all the essential data, add this row
                    if lccn and title:
                        rows.append((lccn, title, place, earliest, latest))

                if rows:
                    print(f"Found {len(rows)} complete rows through alternative extraction")

                    # Reset our lists
                    lccns = []
                    titles = []
                    places = []
                    earliest_dates = []
                    latest_dates = []

                    # Fill our lists from the row data
                    for row in rows:
                        lccns.append(row[0])
                        titles.append(row[1])
                        places.append(row[2])
                        earliest_dates.append(row[3])
                        latest_dates.append(row[4])

                    # Update min_length
                    min_length = len(rows)

            # Remove duplicates - we'll process only unique LCCNs
            unique_newspapers = {}

            for i in range(min_length):
                lccn = lccns[i].strip()

                # Skip if we've already seen this LCCN
                if lccn in unique_newspapers:
                    continue

                # Get other fields
                title = titles[i].strip()
                place = places[i].strip()
                earliest = earliest_dates[i].strip()
                latest = latest_dates[i].strip()

                # Store this newspaper with all available details
                unique_newspapers[lccn] = {
                    'lccn': lccn,
                    'title': title,
                    'place': place,
                    'earliest_date': earliest,
                    'latest_date': latest
                }

            # Create list of newspaper objects with proper formatting for display and sorting
            newspapers = []

            for lccn, data in unique_newspapers.items():
                # Extract title for sorting (ignoring leading "The ")
                title = data['title']
                sort_title = title
                if title.lower().startswith("the "):
                    sort_title = title[4:]

                # Format place to simplify if needed
                place = data['place']

                # If place contains a comma, extract just the city
                city = place
                if ',' in place:
                    parts = place.split(',')
                    city = parts[0].strip()

                # Format date range
                date_range = ""
                if data['earliest_date'] or data['latest_date']:
                    earliest = data['earliest_date']
                    latest = data['latest_date']
                    date_range = f"{earliest} to {latest}"

                # Create display text in the exact format requested
                # Format: Publication Name (LCCN), Publication City, First Issue Date to Latest Issue Date
                display_text = f"{title} ({lccn})"
                if city:
                    display_text += f", {city}"
                if date_range:
                    display_text += f", {date_range}"

                # Add newspaper to the list
                newspapers.append({
                    'lccn': lccn,
                    'title': title,
                    'sort_title': sort_title,
                    'place': place,
                    'city': city,
                    'date_range': date_range,
                    'earliest_date': data['earliest_date'],
                    'latest_date': data['latest_date'],
                    'display_text': display_text
                })

            # Store the newspapers for this state
            self.newspapers_by_state[state_abbrev] = newspapers

            # Update the UI
            self.update_newspaper_combo(newspapers)

        except Exception as e:
            # In case of error, update the UI with a message
            import traceback
            print(f"Error fetching newspapers: {str(e)}")
            traceback.print_exc()
            self.status_label.setText(f"Error loading newspapers: {str(e)}")
            self.set_ui_enabled(True)
            self.progress_bar.setRange(0, 100)  # Reset progress bar
    
    def update_newspaper_combo(self, newspapers):
        """
        Update the newspaper combo box with a list of newspapers.

        Args:
            newspapers: List of newspaper objects
        """
        # Clear the current items
        self.newspaper_combo.clear()

        # Add "Select Title" option at the top
        self.newspaper_combo.addItem("Select Title", "")

        # Sort newspapers alphabetically by sort_title (ignoring "The " prefix)
        try:
            sorted_newspapers = sorted(newspapers, key=lambda x: x.get('sort_title', '').lower())

            # Add newspapers to the combo box with the properly formatted display text
            for newspaper in sorted_newspapers:
                lccn = newspaper.get('lccn', '')

                # Get the display text in the exact format requested:
                # Publication Name (LCCN), Publication City, First Issue Date to Latest Issue Date
                title = newspaper.get('title', '')
                city = newspaper.get('city', '')
                date_range = newspaper.get('date_range', '')

                # Build the display text exactly as requested
                display_text = f"{title} ({lccn})"
                if city:
                    display_text += f", {city}"
                if date_range:
                    display_text += f", {date_range}"

                # Add the item to the combo box with the LCCN as data
                self.newspaper_combo.addItem(display_text, lccn)

            # Log what we added
            if newspapers:
                print(f"Added {len(newspapers)} newspapers to dropdown. First item: {sorted_newspapers[0].get('display_text', '')}")

        except Exception as e:
            import traceback
            print(f"Error sorting/displaying newspapers: {str(e)}")
            traceback.print_exc()

            # Fallback - just add them unsorted if there's an error
            for newspaper in newspapers:
                lccn = newspaper.get('lccn', '')
                title = newspaper.get('title', f"Newspaper ({lccn})")
                self.newspaper_combo.addItem(title, lccn)

        # Re-enable the UI
        self.set_ui_enabled(True)
        self.progress_bar.setRange(0, 100)  # Reset progress bar
        self.status_label.setText(f"Found {len(newspapers)} newspapers for {self.state_combo.currentText()}")
    
    def on_custom_lccn_toggled(self, state):
        """
        Handle custom LCCN checkbox toggle.
        
        Args:
            state: Checkbox state (Qt.Checked or Qt.Unchecked)
        """
        # Enable or disable the LCCN edit field and search button
        is_checked = state == Qt.Checked
        self.lccn_edit.setEnabled(is_checked)
        self.lccn_search_button.setEnabled(is_checked)
        
        # Disable state and newspaper selections if custom LCCN is enabled
        self.state_combo.setEnabled(not is_checked)
        self.newspaper_combo.setEnabled(not is_checked)
        
        # Clear the LCCN field if unchecked
        if not is_checked:
            self.lccn_edit.clear()
    
    def on_lccn_search(self):
        """
        Handle custom LCCN search button click.
        
        Searches for a newspaper with the specified LCCN and updates
        the state and newspaper selections if found.
        """
        lccn = self.lccn_edit.text().strip()
        
        if not lccn:
            self.status_label.setText("Please enter an LCCN")
            return
        
        self.status_label.setText(f"Searching for LCCN: {lccn}...")
        
        # Fetch newspaper details by LCCN
        try:
            url = f"https://chroniclingamerica.loc.gov/lccn/{lccn}.json"
            response = requests.get(url)
            
            if response.status_code == 200:
                # Parse the response
                try:
                    data = response.json()
                    
                    # Extract newspaper details
                    title = data.get('name', f"Newspaper ({lccn})")
                    place = data.get('place', [{}])[0].get('name', '')
                    
                    # Try to determine the state from place
                    state_name = None
                    state_abbrev = None
                    
                    # Extract state abbreviation from place if possible
                    if place:
                        # Extract state from place (usually "City, State")
                        parts = place.split(',')
                        if len(parts) > 1:
                            state_part = parts[1].strip()
                            
                            # Try to match with a state in our combo box
                            for i in range(self.state_combo.count()):
                                if state_part in self.state_combo.itemText(i):
                                    state_name = self.state_combo.itemText(i)
                                    state_abbrev = self.state_combo.itemData(i)
                                    break
                    
                    # Update UI to show the newspaper details
                    self.status_label.setText(f"Found: {title} from {place}")
                    
                    # If we found a state, select it
                    if state_name:
                        # Temporarily disconnect the state change signal to avoid triggering newspaper reload
                        self.state_combo.currentIndexChanged.disconnect(self.on_state_changed)
                        
                        # Set the state
                        index = self.state_combo.findText(state_name)
                        if index >= 0:
                            self.state_combo.setCurrentIndex(index)
                        
                        # Reconnect the signal
                        self.state_combo.currentIndexChanged.connect(self.on_state_changed)
                        
                        # Load newspapers for this state if not already loaded
                        if state_abbrev not in self.newspapers_by_state:
                            self.fetch_newspapers_for_state(state_abbrev, state_name)
                        else:
                            self.update_newspaper_combo(self.newspapers_by_state[state_abbrev])
                    
                    # Try to find this LCCN in the newspaper combo box
                    index = self.newspaper_combo.findData(lccn)
                    if index >= 0:
                        self.newspaper_combo.setCurrentIndex(index)
                    else:
                        # Add this newspaper to the combo box
                        self.newspaper_combo.addItem(f"{title} ({lccn})", lccn)
                        self.newspaper_combo.setCurrentIndex(self.newspaper_combo.count() - 1)
                    
                    return
                    
                except json.JSONDecodeError:
                    self.status_label.setText(f"Error parsing response for LCCN: {lccn}")
            else:
                self.status_label.setText(f"Error: LCCN {lccn} not found")
        
        except Exception as e:
            self.status_label.setText(f"Error searching for LCCN: {str(e)}")
            
        # Re-enable custom LCCN mode even if search failed
        self.custom_lccn_check.setChecked(True)
    
    def set_ui_enabled(self, enabled):
        """
        Enable or disable UI elements during operations.
        
        Args:
            enabled: Whether UI should be enabled
        """
        # Only enable state and newspaper selectors if custom LCCN is unchecked
        custom_lccn_enabled = self.custom_lccn_check.isChecked()
        self.state_combo.setEnabled(enabled and not custom_lccn_enabled)
        self.newspaper_combo.setEnabled(enabled and not custom_lccn_enabled)
        
        # Custom LCCN controls
        self.custom_lccn_check.setEnabled(enabled)
        self.lccn_edit.setEnabled(enabled and custom_lccn_enabled)
        self.lccn_search_button.setEnabled(enabled and custom_lccn_enabled)
        
        # Date range controls
        self.date_start_edit.setEnabled(enabled)
        self.date_end_edit.setEnabled(enabled)
        
        # Keywords field
        self.keywords_edit.setEnabled(enabled)
        
        # Search button
        self.search_button.setEnabled(enabled)
        
        # Results area
        self.results_list.setEnabled(enabled)
        self.prev_button.setEnabled(enabled and self.current_page > 1)
        self.next_button.setEnabled(enabled and self.current_page < self.pagination_info.get('total_pages', 1))
        
        # Download options
        self.download_pdf_check.setEnabled(enabled)
        self.download_jp2_check.setEnabled(enabled)
        self.download_ocr_check.setEnabled(enabled)
        self.download_json_check.setEnabled(enabled)
        self.max_pages_spin.setEnabled(enabled)
        self.import_check.setEnabled(enabled)
        
        # Download buttons
        has_results = enabled and self.results_list.count() > 0
        has_selection = enabled and len(self.results_list.selectedItems()) > 0
        
        self.download_selected_button.setEnabled(enabled and has_selection)
        self.download_all_button.setEnabled(enabled and has_results)