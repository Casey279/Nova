#!/usr/bin/env python3
# File: repository_chronicling_america_panel.py

import os
import sys
import time
import sqlite3
import logging
import traceback
import re
from datetime import datetime, date
from calendar import month_name
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QLineEdit, QListWidget, QListWidgetItem,
                            QMessageBox, QProgressBar, QGroupBox, QComboBox,
                            QDateEdit, QCheckBox, QTextEdit, QGridLayout, QSplitter,
                            QSpinBox, QFormLayout, QTableWidget, QTableWidgetItem,
                            QHeaderView, QAbstractItemView, QTabWidget, QToolButton,
                            QMenu, QAction, QFileDialog, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QSize
from PyQt5.QtGui import QPixmap, QIcon

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import API client
try:
    from api.chronicling_america import ChroniclingAmericaClient, PageMetadata
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False
    # Define placeholder for type hinting
    class PageMetadata:
        pass

# Import from newspaper repository
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'newspaper_repository'))
from repository_database import RepositoryDatabaseManager
from config import get_config

class SearchWorker(QThread):
    """Worker thread for searching ChroniclingAmerica."""
    
    progress_signal = pyqtSignal(int, int)  # current, total (for download phase)
    search_results_signal = pyqtSignal(list, dict)  # results, pagination
    status_signal = pyqtSignal(str)  # Status message
    rate_limit_signal = pyqtSignal(dict)  # Rate limit info
    finished_signal = pyqtSignal(dict)  # results from download/import
    error_signal = pyqtSignal(str)  # error message
    
    def __init__(self, search_params, download_dir, max_pages=1, 
                download_formats=None, repository_manager=None):
        """
        Initialize the search worker.
        
        Args:
            search_params: Dictionary of search parameters
            download_dir: Directory to save downloaded files
            max_pages: Maximum number of result pages to process
            download_formats: List of formats to download
            repository_manager: RepositoryDatabaseManager instance
        """
        super().__init__()
        self.search_params = search_params
        self.download_dir = download_dir
        self.max_pages = max_pages
        self.download_formats = download_formats or ['pdf', 'jp2', 'ocr', 'json']
        self.repository_manager = repository_manager
        self.cancel_flag = False
        self.operation = "search"  # "search" or "download"
        self.client = None
        
    def run(self):
        """Run the search operation."""
        try:
            self.status_signal.emit("Initializing ChroniclingAmerica client...")
            
            # Create API client
            self.client = ChroniclingAmericaClient(
                output_directory=self.download_dir,
                request_delay=1.0  # Conservative rate limit
            )
            
            # Send rate limit info
            self.rate_limit_signal.emit({
                'delay': self.client.request_delay,
                'last_request': 'Never'
            })
            
            if self.operation == "search":
                self._perform_search()
            elif self.operation == "download":
                self._perform_download()
                
        except Exception as e:
            self.error_signal.emit(f"Error in search worker: {str(e)}\n{traceback.format_exc()}")
            
    def _perform_search(self):
        """Perform the search operation."""
        try:
            self.status_signal.emit("Searching for newspaper pages...")
            
            # Extract search parameters
            keywords = self.search_params.get("keywords")
            lccn = self.search_params.get("lccn")
            state = self.search_params.get("state")
            date_start = self.search_params.get("date_start")
            date_end = self.search_params.get("date_end")
            page = self.search_params.get("page", 1)
            
            # Perform the search
            pages, pagination = self.client.search_pages(
                keywords=keywords,
                lccn=lccn,
                state=state,
                date_start=date_start,
                date_end=date_end,
                page=page
            )
            
            # Update rate limit info
            self.rate_limit_signal.emit({
                'delay': self.client.request_delay,
                'last_request': datetime.now().strftime("%H:%M:%S")
            })
            
            # Send the results
            self.search_results_signal.emit(pages, pagination)
            self.status_signal.emit(f"Found {len(pages)} results.")
            
        except Exception as e:
            self.error_signal.emit(f"Search error: {str(e)}")
            
    def _perform_download(self):
        """Perform the download operation."""
        try:
            # Get pages to download
            pages = self.search_params.get("pages", [])
            total_pages = len(pages)
            
            if not pages:
                self.error_signal.emit("No pages to download.")
                return
                
            self.status_signal.emit(f"Downloading {total_pages} pages...")
            
            # Track results
            download_results = []
            downloaded_count = 0
            
            # Process each page
            for i, page in enumerate(pages):
                if self.cancel_flag:
                    self.status_signal.emit("Download cancelled.")
                    break
                    
                # Update progress
                self.progress_signal.emit(i + 1, total_pages)
                self.status_signal.emit(f"Downloading page {i+1}/{total_pages}: {page.title}")
                
                try:
                    # Download the page
                    result = self.client.download_page_content(
                        page_metadata=page,
                        formats=self.download_formats,
                        save_files=True
                    )
                    
                    # Add metadata for reference
                    result['metadata'] = {
                        'lccn': page.lccn,
                        'issue_date': page.issue_date.isoformat() if hasattr(page.issue_date, 'isoformat') else str(page.issue_date),
                        'sequence': page.sequence,
                        'title': page.title
                    }
                    
                    download_results.append(result)
                    downloaded_count += 1
                    
                    # Update rate limit info
                    self.rate_limit_signal.emit({
                        'delay': self.client.request_delay,
                        'last_request': datetime.now().strftime("%H:%M:%S")
                    })
                    
                    # Wait a bit to respect rate limits
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.error_signal.emit(f"Error downloading page {i+1}/{total_pages}: {str(e)}")
                    
            # Import downloaded pages if repository manager is available
            import_count = 0
            if self.repository_manager and download_results:
                self.status_signal.emit(f"Importing {len(download_results)} pages into repository...")
                try:
                    page_ids = self.client.integrate_with_repository(
                        download_results=download_results,
                        repository_manager=self.repository_manager
                    )
                    import_count = len(page_ids)
                except Exception as e:
                    self.error_signal.emit(f"Error importing pages: {str(e)}")
            
            # Send summary
            results_summary = {
                'downloaded': downloaded_count,
                'imported': import_count,
                'download_results': download_results
            }
            
            self.finished_signal.emit(results_summary)
            self.status_signal.emit(f"Downloaded {downloaded_count} pages, imported {import_count} pages.")
            
        except Exception as e:
            self.error_signal.emit(f"Download error: {str(e)}")
            
    def cancel(self):
        """Cancel the current operation."""
        self.cancel_flag = True
        self.status_signal.emit("Cancelling operation...")


class BulkDownloadWorker(QThread):
    """Worker thread for bulk downloading newspaper pages by timeframe."""
    
    progress_signal = pyqtSignal(int, int)  # current, total
    search_progress_signal = pyqtSignal(int, int)  # current page, total pages
    status_signal = pyqtSignal(str)  # Status message
    file_status_signal = pyqtSignal(str, str)  # file name, status
    rate_limit_signal = pyqtSignal(dict)  # Rate limit info
    finished_signal = pyqtSignal(dict)  # results from download/import
    error_signal = pyqtSignal(str)  # error message
    
    def __init__(self, download_params, download_dir, repository_manager=None):
        """
        Initialize the bulk download worker.
        
        Args:
            download_params: Dictionary of download parameters
            download_dir: Directory to save downloaded files
            repository_manager: RepositoryDatabaseManager instance
        """
        super().__init__()
        self.download_params = download_params
        self.download_dir = download_dir
        self.repository_manager = repository_manager
        self.cancel_flag = False
        self.client = None
        
    def run(self):
        """Run the bulk download operation."""
        try:
            self.status_signal.emit("Initializing ChroniclingAmerica client...")
            
            # Create API client
            self.client = ChroniclingAmericaClient(
                output_directory=self.download_dir,
                request_delay=1.0  # Conservative rate limit
            )
            
            # Send rate limit info
            self.rate_limit_signal.emit({
                'delay': self.client.request_delay,
                'last_request': 'Never'
            })
            
            # Start the bulk download process
            self._perform_bulk_download()
                
        except Exception as e:
            self.error_signal.emit(f"Error in bulk download worker: {str(e)}\n{traceback.format_exc()}")
            
    def _perform_bulk_download(self):
        """Perform the bulk download operation."""
        try:
            # Extract parameters
            year = self.download_params.get("year")
            month = self.download_params.get("month")
            lccn = self.download_params.get("lccn")
            state = self.download_params.get("state")
            formats = self.download_params.get("formats", ['pdf', 'jp2', 'ocr', 'json'])
            
            # Prepare date range
            if month:
                month_num = list(month_name).index(month) if isinstance(month, str) else month
                date_start = f"{year}-{month_num:02d}-01"
                
                # Calculate end date based on month
                if month_num in [4, 6, 9, 11]:
                    date_end = f"{year}-{month_num:02d}-30"
                elif month_num == 2:
                    # Check for leap year
                    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                        date_end = f"{year}-{month_num:02d}-29"
                    else:
                        date_end = f"{year}-{month_num:02d}-28"
                else:
                    date_end = f"{year}-{month_num:02d}-31"
            else:
                # Full year
                date_start = f"{year}-01-01"
                date_end = f"{year}-12-31"
                
            self.status_signal.emit(f"Searching for newspaper pages from {date_start} to {date_end}...")
            
            # Initial search to determine total pages
            search_params = {
                "date_start": date_start,
                "date_end": date_end,
                "page": 1
            }

            # Only add LCCN if specified (allows searching by date range only)
            if lccn:
                search_params["lccn"] = lccn

            # Only add state if specified (allows searching without state filter)
            if state:
                search_params["state"] = state
            
            pages, pagination = self.client.search_pages(**search_params)
            total_search_pages = pagination.get('total_pages', 1)
            total_items = pagination.get('total_items', 0)
            
            if total_items == 0:
                self.error_signal.emit(f"No newspaper pages found for the selected timeframe {date_start} to {date_end}.")
                return
            
            self.status_signal.emit(f"Found {total_items} newspaper pages across {total_search_pages} result pages.")
            
            # Fetch all pages
            all_pages = pages.copy()
            
            for page_num in range(2, min(total_search_pages + 1, 101)):  # Limit to 100 pages to prevent excessive requests
                if self.cancel_flag:
                    self.status_signal.emit("Search cancelled.")
                    break
                    
                self.search_progress_signal.emit(page_num, total_search_pages)
                self.status_signal.emit(f"Fetching result page {page_num}/{total_search_pages}...")
                
                # Update search page number
                search_params["page"] = page_num
                
                # Search for the next page
                try:
                    next_pages, _ = self.client.search_pages(**search_params)
                    all_pages.extend(next_pages)
                    
                    # Wait a bit to respect rate limits
                    time.sleep(1.0)
                except Exception as e:
                    self.error_signal.emit(f"Error fetching result page {page_num}: {str(e)}")
                    # Continue with the pages we have
            
            total_download_pages = len(all_pages)
            self.status_signal.emit(f"Preparing to download {total_download_pages} newspaper pages...")
            
            # Download the pages
            download_results = []
            downloaded_count = 0
            
            for i, page in enumerate(all_pages):
                if self.cancel_flag:
                    self.status_signal.emit("Download cancelled.")
                    break
                    
                # Update progress
                self.progress_signal.emit(i + 1, total_download_pages)
                
                try:
                    page_title = page.title if hasattr(page, 'title') else f"Page {page.sequence}"
                    page_date = page.issue_date.strftime("%Y-%m-%d") if hasattr(page.issue_date, 'strftime') else str(page.issue_date)
                    self.status_signal.emit(f"Downloading page {i+1}/{total_download_pages}: {page_title} ({page_date})")
                    self.file_status_signal.emit(f"{page_title} ({page_date})", "Downloading...")
                    
                    # Download the page
                    result = self.client.download_page_content(
                        page_metadata=page,
                        formats=formats,
                        save_files=True
                    )
                    
                    # Add metadata for reference
                    result['metadata'] = {
                        'lccn': page.lccn,
                        'issue_date': page.issue_date.isoformat() if hasattr(page.issue_date, 'isoformat') else str(page.issue_date),
                        'sequence': page.sequence,
                        'title': page.title if hasattr(page, 'title') else f"Page {page.sequence}"
                    }
                    
                    download_results.append(result)
                    downloaded_count += 1
                    
                    # Update status
                    self.file_status_signal.emit(f"{page_title} ({page_date})", "Downloaded")
                    
                    # Update rate limit info
                    self.rate_limit_signal.emit({
                        'delay': self.client.request_delay,
                        'last_request': datetime.now().strftime("%H:%M:%S")
                    })
                    
                    # Wait a bit to respect rate limits
                    time.sleep(0.5)
                    
                except Exception as e:
                    error_msg = str(e)
                    self.error_signal.emit(f"Error downloading page {i+1}/{total_download_pages}: {error_msg}")
                    self.file_status_signal.emit(f"{page.title} ({page_date})", f"Error: {error_msg[:30]}...")
            
            # Import downloaded pages if repository manager is available
            import_count = 0
            if self.repository_manager and download_results:
                self.status_signal.emit(f"Importing {len(download_results)} pages into repository...")
                try:
                    page_ids = self.client.integrate_with_repository(
                        download_results=download_results,
                        repository_manager=self.repository_manager
                    )
                    import_count = len(page_ids)
                except Exception as e:
                    self.error_signal.emit(f"Error importing pages: {str(e)}")
            
            # Send summary
            results_summary = {
                'total_found': total_items,
                'downloaded': downloaded_count,
                'imported': import_count,
                'timeframe': f"{date_start} to {date_end}",
                'download_results': download_results
            }
            
            self.finished_signal.emit(results_summary)
            self.status_signal.emit(f"Downloaded {downloaded_count} pages, imported {import_count} pages.")
            
        except Exception as e:
            self.error_signal.emit(f"Bulk download error: {str(e)}")
            
    def cancel(self):
        """Cancel the current operation."""
        self.cancel_flag = True
        self.status_signal.emit("Cancelling operation...")


class RepositoryChroniclingAmericaPanel(QWidget):
    """Panel for searching and downloading from ChroniclingAmerica."""
    
    # Signals to update repository tab
    repository_updated_signal = pyqtSignal()
    
    def __init__(self, repository_manager, parent=None):
        """
        Initialize the panel.
        
        Args:
            repository_manager: Instance of RepositoryDatabaseManager
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Set up logging for this class
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.repository_manager = repository_manager
        
        # Initialize variables
        self.current_page = 1
        self.total_pages = 1
        self.current_results = []
        self.search_params = {}
        
        # Workers
        self.search_worker = None
        self.bulk_download_worker = None
        
        # Download directory
        try:
            config = get_config()
            # Handle different types of config objects
            if hasattr(config, 'get'):
                self.download_directory = config.get('download_directory', os.path.join(os.path.expanduser("~"), "Downloads", "ChroniclingAmerica"))
            elif isinstance(config, dict):
                self.download_directory = config.get('download_directory', os.path.join(os.path.expanduser("~"), "Downloads", "ChroniclingAmerica"))
            else:
                # Default fallback
                self.download_directory = os.path.join(os.path.expanduser("~"), "Downloads", "ChroniclingAmerica")
        except Exception as e:
            # Default fallback in case of any error
            self.logger.error(f"Error getting config: {e}")
            self.download_directory = os.path.join(os.path.expanduser("~"), "Downloads", "ChroniclingAmerica")
        
        # Setup UI
        self.setup_ui()
        
        # Disable API-dependent features if API is not available
        if not API_AVAILABLE:
            self.show_api_unavailable()
    
    def setup_ui(self):
        """Set up the UI components."""
        main_layout = QVBoxLayout(self)
        
        # Create a splitter for resizable sections
        splitter = QSplitter(Qt.Vertical)
        
        # Top section: Search and filters
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # Title and description
        title_label = QLabel("Chronicling America Newspaper Search")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        description_label = QLabel("Search and download historical newspapers from the Library of Congress")
        description_label.setWordWrap(True)
        
        top_layout.addWidget(title_label)
        top_layout.addWidget(description_label)
        top_layout.addSpacing(10)
        
        # Create tabs for different search modes
        search_tabs = QTabWidget()
        
        # Simple search tab
        search_tab = QWidget()
        search_tab_layout = QVBoxLayout(search_tab)
        
        # Search form
        search_form_layout = QFormLayout()
        
        # Keywords
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("Enter search terms...")
        search_form_layout.addRow("Keywords:", self.keywords_edit)
        
        # LCCN (Library of Congress Control Number)
        self.lccn_edit = QLineEdit()
        self.lccn_edit.setPlaceholderText("e.g., sn83030214")
        search_form_layout.addRow("LCCN:", self.lccn_edit)
        
        # Show/hide advanced options
        self.advanced_toggle = QPushButton("Show Advanced Options")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.clicked.connect(self.toggle_advanced_search)
        
        search_tab_layout.addLayout(search_form_layout)
        search_tab_layout.addWidget(self.advanced_toggle)
        
        # Advanced search options
        self.advanced_search_group = QGroupBox("Advanced Search Options")
        self.advanced_search_group.setVisible(False)
        advanced_layout = QFormLayout(self.advanced_search_group)
        
        # State
        self.state_combo = QComboBox()
        self.state_combo.addItems([
            "",  # Empty for "All states"
            "Alabama", "Alaska", "Arizona", "Arkansas", "California", 
            "Colorado", "Connecticut", "Delaware", "Florida", "Georgia", 
            "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", 
            "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", 
            "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", 
            "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", 
            "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", 
            "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", 
            "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", 
            "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
        ])
        advanced_layout.addRow("State:", self.state_combo)
        
        # Date range
        date_layout = QHBoxLayout()
        
        self.date_start_edit = QDateEdit()
        self.date_start_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_start_edit.setCalendarPopup(True)
        self.date_start_edit.setDate(QDate(1800, 1, 1))
        
        self.date_end_edit = QDateEdit()
        self.date_end_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_end_edit.setCalendarPopup(True)
        self.date_end_edit.setDate(QDate.currentDate())
        
        date_layout.addWidget(self.date_start_edit)
        date_layout.addWidget(QLabel(" to "))
        date_layout.addWidget(self.date_end_edit)
        
        advanced_layout.addRow("Date Range:", date_layout)
        
        # Results per page
        self.results_per_page_spin = QSpinBox()
        self.results_per_page_spin.setRange(10, 100)
        self.results_per_page_spin.setSingleStep(10)
        self.results_per_page_spin.setValue(20)
        advanced_layout.addRow("Results per page:", self.results_per_page_spin)
        
        # Download options
        download_layout = QHBoxLayout()
        
        self.download_pdf_check = QCheckBox("PDF")
        self.download_pdf_check.setChecked(True)
        
        self.download_jp2_check = QCheckBox("JP2")
        self.download_jp2_check.setChecked(True)
        
        self.download_ocr_check = QCheckBox("OCR Text")
        self.download_ocr_check.setChecked(True)
        
        self.download_json_check = QCheckBox("JSON Metadata")
        self.download_json_check.setChecked(True)
        
        download_layout.addWidget(self.download_pdf_check)
        download_layout.addWidget(self.download_jp2_check)
        download_layout.addWidget(self.download_ocr_check)
        download_layout.addWidget(self.download_json_check)
        download_layout.addStretch()
        
        advanced_layout.addRow("Download formats:", download_layout)
        
        search_tab_layout.addWidget(self.advanced_search_group)
        
        # Search button
        search_button_layout = QHBoxLayout()
        
        self.search_button = QPushButton("Search")
        self.search_button.setIcon(QIcon.fromTheme("search"))
        self.search_button.clicked.connect(self.search)
        self.search_button.setMinimumWidth(150)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_search_form)
        
        search_button_layout.addStretch()
        search_button_layout.addWidget(self.clear_button)
        search_button_layout.addWidget(self.search_button)
        
        search_tab_layout.addLayout(search_button_layout)
        
        # Add search tab to tabs
        search_tabs.addTab(search_tab, "Search")
        
        # Bulk download tab
        bulk_tab = QWidget()
        bulk_tab_layout = QVBoxLayout(bulk_tab)
        
        # Title and description
        bulk_title = QLabel("Bulk Download by Timeframe")
        bulk_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        bulk_description = QLabel("Download all newspaper pages from a specific timeframe and newspaper")
        bulk_description.setWordWrap(True)
        
        bulk_tab_layout.addWidget(bulk_title)
        bulk_tab_layout.addWidget(bulk_description)
        bulk_tab_layout.addSpacing(10)
        
        # Bulk download form
        bulk_form_layout = QFormLayout()
        
        # Year selection
        self.bulk_year_combo = QComboBox()
        # Add years from 1789 to current year
        current_year = datetime.now().year
        years = [str(year) for year in range(1789, current_year + 1)]
        years.reverse()  # Most recent first
        self.bulk_year_combo.addItems(years)
        bulk_form_layout.addRow("Year:", self.bulk_year_combo)
        
        # Month selection
        self.bulk_month_combo = QComboBox()
        self.bulk_month_combo.addItem("All Year")  # Option for entire year
        self.bulk_month_combo.addItems(list(month_name)[1:])  # January to December
        bulk_form_layout.addRow("Month:", self.bulk_month_combo)
        
        # Newspaper selection
        self.bulk_newspaper_combo = QComboBox()
        self.bulk_newspaper_combo.addItem("All Newspapers")
        self.bulk_newspaper_combo.addItem("New York Tribune (sn83030214)")
        self.bulk_newspaper_combo.addItem("Chicago Daily Tribune (sn83045487)")
        self.bulk_newspaper_combo.addItem("The Washington Times (sn87062268)")
        self.bulk_newspaper_combo.addItem("The San Francisco Call (sn85066387)")
        self.bulk_newspaper_combo.addItem("The Evening World (sn83030273)")
        self.bulk_newspaper_combo.addItem("Other (specify LCCN)")
        bulk_form_layout.addRow("Newspaper:", self.bulk_newspaper_combo)
        
        # LCCN input for custom newspaper
        self.bulk_lccn_edit = QLineEdit()
        self.bulk_lccn_edit.setPlaceholderText("Enter LCCN (e.g., sn83030214)")
        self.bulk_lccn_edit.setEnabled(False)
        bulk_form_layout.addRow("Custom LCCN:", self.bulk_lccn_edit)
        
        # Connect newspaper selection to LCCN field
        self.bulk_newspaper_combo.currentIndexChanged.connect(self.on_bulk_newspaper_changed)
        
        # State selection
        self.bulk_state_combo = QComboBox()
        self.bulk_state_combo.addItems([
            "All States",  # Option for all states
            "Alabama", "Alaska", "Arizona", "Arkansas", "California", 
            "Colorado", "Connecticut", "Delaware", "Florida", "Georgia", 
            "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", 
            "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", 
            "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", 
            "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", 
            "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", 
            "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", 
            "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", 
            "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
        ])
        bulk_form_layout.addRow("State:", self.bulk_state_combo)
        
        # Download options
        bulk_download_layout = QHBoxLayout()
        
        self.bulk_download_pdf_check = QCheckBox("PDF")
        self.bulk_download_pdf_check.setChecked(True)
        
        self.bulk_download_jp2_check = QCheckBox("JP2")
        self.bulk_download_jp2_check.setChecked(True)
        
        self.bulk_download_ocr_check = QCheckBox("OCR Text")
        self.bulk_download_ocr_check.setChecked(True)
        
        self.bulk_download_json_check = QCheckBox("JSON Metadata")
        self.bulk_download_json_check.setChecked(True)
        
        bulk_download_layout.addWidget(self.bulk_download_pdf_check)
        bulk_download_layout.addWidget(self.bulk_download_jp2_check)
        bulk_download_layout.addWidget(self.bulk_download_ocr_check)
        bulk_download_layout.addWidget(self.bulk_download_json_check)
        bulk_download_layout.addStretch()
        
        bulk_form_layout.addRow("Download formats:", bulk_download_layout)
        
        # Import options
        self.bulk_import_check = QCheckBox("Import into repository")
        self.bulk_import_check.setChecked(True)
        bulk_form_layout.addRow("Repository:", self.bulk_import_check)
        
        bulk_tab_layout.addLayout(bulk_form_layout)
        
        # Download directory
        download_dir_layout = QHBoxLayout()
        
        self.bulk_download_dir_edit = QLineEdit(self.download_directory)
        self.bulk_download_dir_edit.setReadOnly(True)
        
        self.bulk_download_dir_button = QPushButton("Browse...")
        self.bulk_download_dir_button.clicked.connect(self.browse_download_directory)
        
        download_dir_layout.addWidget(self.bulk_download_dir_edit, 1)
        download_dir_layout.addWidget(self.bulk_download_dir_button)
        
        bulk_form_layout.addRow("Download to:", download_dir_layout)
        
        # Start bulk download button
        bulk_button_layout = QHBoxLayout()
        
        self.bulk_download_button = QPushButton("Start Bulk Download")
        self.bulk_download_button.setIcon(QIcon.fromTheme("download"))
        self.bulk_download_button.clicked.connect(self.start_bulk_download)
        self.bulk_download_button.setMinimumWidth(200)
        
        bulk_button_layout.addStretch()
        bulk_button_layout.addWidget(self.bulk_download_button)
        
        bulk_tab_layout.addLayout(bulk_button_layout)
        
        # Add bulk download tab to tabs
        search_tabs.addTab(bulk_tab, "Bulk Download")
        
        top_layout.addWidget(search_tabs)
        
        # Status and rate limit info
        status_group = QGroupBox("Status")
        status_layout = QFormLayout(status_group)
        
        self.rate_limit_label = QLabel("Rate limit: 0.5s between requests")
        self.last_request_label = QLabel("Last request: Never")
        self.api_status_label = QLabel("Ready")
        
        status_layout.addRow("API Status:", self.api_status_label)
        status_layout.addRow("Rate limit:", self.rate_limit_label)
        status_layout.addRow("Last request:", self.last_request_label)
        
        top_layout.addWidget(status_group)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_current_operation)
        self.cancel_button.setEnabled(False)
        top_layout.addWidget(self.cancel_button)
        
        # Add the top widget to the splitter
        splitter.addWidget(top_widget)
        
        # Bottom section: Results and downloads
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        # Results section
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout(results_group)
        
        # Search results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels(["Title", "Date", "Page", "LCCN", "Actions", "Preview"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # Title column
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Actions column
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Preview column
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setAlternatingRowColors(True)  # Improve readability
        self.results_table.itemSelectionChanged.connect(self.on_result_selection_changed)
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("« Previous Page")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)
        
        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setAlignment(Qt.AlignCenter)
        
        self.next_button = QPushButton("Next Page »")
        self.next_button.clicked.connect(self.next_page)
        self.next_button.setEnabled(False)
        
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_button)
        
        # Download controls
        download_controls_layout = QHBoxLayout()
        
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self.select_all_results)
        
        self.download_selected_button = QPushButton("Download Selected")
        self.download_selected_button.clicked.connect(self.download_selected)
        self.download_selected_button.setEnabled(False)
        
        self.download_all_button = QPushButton("Download All Results")
        self.download_all_button.clicked.connect(self.download_all)
        self.download_all_button.setEnabled(False)
        
        download_controls_layout.addWidget(self.select_all_button)
        download_controls_layout.addStretch()
        download_controls_layout.addWidget(self.download_selected_button)
        download_controls_layout.addWidget(self.download_all_button)
        
        results_layout.addWidget(self.results_table)
        results_layout.addLayout(pagination_layout)
        results_layout.addLayout(download_controls_layout)
        
        # Bulk download progress section
        bulk_progress_group = QGroupBox("Bulk Download Progress")
        bulk_progress_layout = QVBoxLayout(bulk_progress_group)
        
        # Main progress bar with label
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("Overall Progress:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%v/%m files (%p%)")
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar, 1)
        
        # Search progress bar (for fetching pages during bulk download)
        search_progress_layout = QHBoxLayout()
        self.search_progress_label = QLabel("Searching:")
        self.search_progress_bar = QProgressBar()
        self.search_progress_bar.setFormat("Page %v/%m (%p%)")
        search_progress_layout.addWidget(self.search_progress_label)
        search_progress_layout.addWidget(self.search_progress_bar, 1)
        
        # File status list
        file_status_layout = QVBoxLayout()
        file_status_label = QLabel("File Status:")
        self.file_status_list = QListWidget()
        file_status_layout.addWidget(file_status_label)
        file_status_layout.addWidget(self.file_status_list)
        
        # Status text
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        
        bulk_progress_layout.addLayout(progress_layout)
        bulk_progress_layout.addLayout(search_progress_layout)
        bulk_progress_layout.addLayout(file_status_layout)
        bulk_progress_layout.addWidget(self.status_text)
        
        # Initialize progress bars
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.search_progress_bar.setValue(0)
        self.search_progress_bar.setMaximum(100)
        
        # Add results and progress groups to bottom layout
        bottom_layout.addWidget(results_group)
        bottom_layout.addWidget(bulk_progress_group)
        
        # Add bottom widget to splitter
        splitter.addWidget(bottom_widget)
        
        # Set stretch factors
        splitter.setStretchFactor(0, 1)  # Top section
        splitter.setStretchFactor(1, 2)  # Bottom section
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
    
    def toggle_advanced_search(self, checked):
        """Toggle visibility of advanced search options."""
        self.advanced_search_group.setVisible(checked)
        self.advanced_toggle.setText("Hide Advanced Options" if checked else "Show Advanced Options")
        
    def on_bulk_newspaper_changed(self, index):
        """Handle change in bulk newspaper selection."""
        # Enable LCCN field only if "Other" is selected
        self.bulk_lccn_edit.setEnabled(index == self.bulk_newspaper_combo.count() - 1)

        # If a specific newspaper is selected, extract the LCCN
        if index > 0 and index < self.bulk_newspaper_combo.count() - 1:
            # Extract LCCN from the combo box text
            text = self.bulk_newspaper_combo.currentText()
            lccn_match = re.search(r'\((sn\d+)\)', text)
            if lccn_match:
                self.bulk_lccn_edit.setText(lccn_match.group(1))
            else:
                self.bulk_lccn_edit.clear()
        elif index == 0:  # "All Newspapers"
            # Clear the LCCN field when "All Newspapers" is selected
            self.bulk_lccn_edit.clear()
    
    def browse_download_directory(self):
        """Open a dialog to select the download directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            self.download_directory,
            QFileDialog.ShowDirsOnly
        )
        
        if dir_path:
            self.download_directory = dir_path
            self.bulk_download_dir_edit.setText(dir_path)
    
    def clear_search_form(self):
        """Clear all search form fields."""
        self.keywords_edit.clear()
        self.lccn_edit.clear()
        self.state_combo.setCurrentIndex(0)
        self.date_start_edit.setDate(QDate(1800, 1, 1))
        self.date_end_edit.setDate(QDate.currentDate())
        self.results_per_page_spin.setValue(20)
        
    def search(self):
        """Perform a search based on current form values."""
        if not API_AVAILABLE:
            QMessageBox.critical(
                self,
                "API Not Available",
                "The ChroniclingAmerica API client is not available. Please check that the API module is installed correctly."
            )
            return
            
        # Collect search parameters
        keywords = self.keywords_edit.text().strip()
        lccn = self.lccn_edit.text().strip()
        
        # If both empty and advanced search not shown, suggest using a search parameter
        # But we'll still allow date-only searches
        if not keywords and not lccn and not self.advanced_search_group.isVisible():
            # Show warning but don't prevent the search if user confirms
            response = QMessageBox.information(
                self,
                "Search Parameter Recommended",
                "You haven't specified any search terms. This may return a large number of results.\n\n"
                "Click OK to continue with date-based search or Cancel to modify your search.",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            # If user clicks Cancel, abort the search
            if response == QMessageBox.Cancel:
                return
            
        # Prepare search parameters
        self.search_params = {
            "keywords": keywords if keywords else None,
            "lccn": lccn if lccn else None,
            "page": 1,  # Start at page 1
        }
        
        # Add advanced parameters if visible
        if self.advanced_search_group.isVisible():
            # State
            state = self.state_combo.currentText()
            self.search_params["state"] = state if state else None
            
            # Date range
            date_start = self.date_start_edit.date().toString("yyyy-MM-dd")
            date_end = self.date_end_edit.date().toString("yyyy-MM-dd")
            
            self.search_params["date_start"] = date_start
            self.search_params["date_end"] = date_end
            
            # Results per page
            self.search_params["items_per_page"] = self.results_per_page_spin.value()
            
        # Update current page
        self.current_page = 1
            
        # Start the search
        self._start_search_worker()
        
    def _start_search_worker(self):
        """Start the search worker thread."""
        # Clear previous results
        self.results_table.setRowCount(0)
        self.current_results = []
        
        # Update UI
        self.api_status_label.setText("Searching...")
        self.cancel_button.setEnabled(True)
        self.search_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.download_selected_button.setEnabled(False)
        self.download_all_button.setEnabled(False)
        
        # Create and start worker
        self.search_worker = SearchWorker(
            search_params=self.search_params,
            download_dir=self.download_directory,
            max_pages=1,  # Just one page at a time
            repository_manager=self.repository_manager
        )
        
        # Connect signals
        self.search_worker.search_results_signal.connect(self.search_results_received)
        self.search_worker.status_signal.connect(self.update_status)
        self.search_worker.error_signal.connect(self.search_error)
        self.search_worker.rate_limit_signal.connect(self.update_rate_limit)
        self.search_worker.finished.connect(self._on_search_worker_finished)
        
        # Start the worker
        self.search_worker.start()
        
    def _on_search_worker_finished(self):
        """Handle completion of the search worker thread."""
        # Update UI
        self.api_status_label.setText("Ready")
        self.cancel_button.setEnabled(False)
        self.search_button.setEnabled(True)
        
        # Clean up
        self.search_worker = None
        
    def search_results_received(self, pages, pagination):
        """
        Handle search results.
        
        Args:
            pages: List of PageMetadata objects
            pagination: Dict with pagination info
        """
        # Update pagination info
        self.total_pages = pagination.get('total_pages', 1)
        
        # Update current results
        self.current_results = pages
        
        # Update UI
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < self.total_pages)
        
        # Clear table
        self.results_table.setRowCount(0)
        
        # Populate results table
        if pages:
            self.results_table.setRowCount(len(pages))
            
            for i, page in enumerate(pages):
                # Title
                title_item = QTableWidgetItem(page.title)
                self.results_table.setItem(i, 0, title_item)
                
                # Date
                date_text = page.issue_date.strftime("%Y-%m-%d") if hasattr(page.issue_date, 'strftime') else str(page.issue_date)
                date_item = QTableWidgetItem(date_text)
                self.results_table.setItem(i, 1, date_item)
                
                # Page/Sequence
                page_num = page.page_number if page.page_number else page.sequence
                page_item = QTableWidgetItem(str(page_num))
                self.results_table.setItem(i, 2, page_item)
                
                # LCCN
                lccn_item = QTableWidgetItem(page.lccn)
                self.results_table.setItem(i, 3, lccn_item)
                
                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(2)
                
                download_button = QPushButton("Download")
                download_button.setProperty("row", i)
                download_button.clicked.connect(lambda checked, row=i: self.download_row(row))
                
                actions_layout.addWidget(download_button)
                self.results_table.setCellWidget(i, 4, actions_widget)
                
                # Preview button
                preview_widget = QWidget()
                preview_layout = QHBoxLayout(preview_widget)
                preview_layout.setContentsMargins(2, 2, 2, 2)
                
                preview_button = QPushButton("Preview")
                preview_button.setProperty("row", i)
                preview_button.clicked.connect(lambda checked, row=i: self.preview_page(row))
                
                preview_layout.addWidget(preview_button)
                self.results_table.setCellWidget(i, 5, preview_widget)
            
            # Enable download buttons
            self.download_all_button.setEnabled(True)
        else:
            # No results
            self.download_all_button.setEnabled(False)
            
            # Add a "No results" row
            self.results_table.setRowCount(1)
            no_results_item = QTableWidgetItem("No results found")
            no_results_item.setTextAlignment(Qt.AlignCenter)
            
            # Span all columns
            self.results_table.setSpan(0, 0, 1, self.results_table.columnCount())
            self.results_table.setItem(0, 0, no_results_item)
    
    def search_error(self, error_message):
        """
        Handle search error.
        
        Args:
            error_message: Error message
        """
        # Update UI
        self.api_status_label.setText("Error")
        self.status_text.append(f"Error: {error_message}")
        
        # Show a message box
        QMessageBox.critical(
            self,
            "Search Error",
            f"An error occurred during the search:\n{error_message}"
        )
    
    def on_result_selection_changed(self):
        """Handle change in result selection."""
        # Enable download button if any rows are selected
        has_selection = len(self.results_table.selectedItems()) > 0
        self.download_selected_button.setEnabled(has_selection)
    
    def previous_page(self):
        """Go to the previous page of results."""
        if self.current_page > 1:
            self.current_page -= 1
            self.search_params["page"] = self.current_page
            self._start_search_worker()
    
    def next_page(self):
        """Go to the next page of results."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.search_params["page"] = self.current_page
            self._start_search_worker()
    
    def download_row(self, row):
        """
        Download a specific row.
        
        Args:
            row: Row index
        """
        if 0 <= row < len(self.current_results):
            # Get the page
            page = self.current_results[row]
            
            # Download the page
            self.download_pages([page])
    
    def download_selected(self):
        """Download selected results."""
        # Get selected rows
        rows = set(item.row() for item in self.results_table.selectedItems())
        
        # Get pages
        pages = [self.current_results[row] for row in rows if 0 <= row < len(self.current_results)]
        
        # Download pages
        if pages:
            self.download_pages(pages)
    
    def download_all(self):
        """Download all current results."""
        if self.current_results:
            self.download_pages(self.current_results)
    
    def select_all_results(self):
        """Select all rows in the results table."""
        self.results_table.selectAll()
    
    def download_pages(self, pages):
        """
        Download and import newspaper pages.
        
        Args:
            pages: List of PageMetadata objects
        """
        try:
            if not pages:
                return
                
            # Check network connectivity first
            try:
                import socket
                # Try to connect to chroniclingamerica.loc.gov
                socket.create_connection(("chroniclingamerica.loc.gov", 80), timeout=5)
            except (socket.timeout, socket.error) as e:
                QMessageBox.critical(
                    self,
                    "Network Error",
                    f"Cannot connect to ChroniclingAmerica servers. Please check your internet connection and try again.\n\nError: {str(e)}"
                )
                return
            
            # Get download formats
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
                    "No Formats Selected",
                    "Please select at least one download format."
                )
                return
            
            # Configure worker
            self.search_worker = SearchWorker(
                search_params={"pages": pages},
                download_dir=self.download_directory,
                download_formats=formats,
                repository_manager=self.repository_manager
            )
            self.search_worker.operation = "download"
            
            # Connect signals
            self.search_worker.progress_signal.connect(self.update_download_progress)
            self.search_worker.status_signal.connect(self.update_status)
            self.search_worker.rate_limit_signal.connect(self.update_rate_limit)
            self.search_worker.error_signal.connect(self.search_error)
            self.search_worker.finished.connect(self._on_search_worker_finished)
            
            # Update UI
            self.api_status_label.setText("Downloading...")
            self.cancel_button.setEnabled(True)
            self.search_button.setEnabled(False)
            self.download_selected_button.setEnabled(False)
            self.download_all_button.setEnabled(False)
            
            # Set up progress bar
            self.progress_bar.setMaximum(len(pages))
            self.progress_bar.setValue(0)
            
            # Show confirmation with estimate
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Download Started")
            
            # Estimate download size
            est_size_per_page = 10  # Rough estimate in MB per page
            est_total_size = est_size_per_page * len(pages)
            
            msg.setText(f"Downloading {len(pages)} pages...")
            msg.setInformativeText(
                f"Estimated total size: ~{est_total_size} MB\n"
                f"Download directory: {self.download_directory}\n\n"
                f"The download will continue in the background. You can continue using the application."
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            
            # Start the worker
            self.search_worker.start()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Download Error",
                f"An error occurred starting the download:\n{str(e)}"
            )
    
    def preview_page(self, row):
        """
        Preview a newspaper page.
        
        Args:
            row: Row index
        """
        try:
            if 0 <= row < len(self.current_results):
                page = self.current_results[row]
                
                # Create a preview window
                preview_dialog = QDialog(self)
                preview_dialog.setWindowTitle(f"Preview: {page.title}")
                preview_dialog.resize(800, 900)
                
                # Dialog layout
                preview_layout = QVBoxLayout(preview_dialog)
                
                # Load image preview in a separate thread to not block UI
                class PreviewWorker(QThread):
                    image_ready = pyqtSignal(QPixmap)
                    error = pyqtSignal(str)
                    
                    def __init__(self, page_metadata):
                        super().__init__()
                        self.page = page_metadata
                        
                    def run(self):
                        try:
                            if not self.page.jp2_url:
                                self.error.emit("No preview URL available")
                                return
                                
                            # Request the image
                            import requests
                            response = requests.get(self.page.jp2_url, stream=True)
                            response.raise_for_status()
                            
                            # Create a temporary file
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                                for chunk in response.iter_content(chunk_size=8192):
                                    tmp.write(chunk)
                                tmp_filename = tmp.name
                            
                            # Load the image
                            pixmap = QPixmap(tmp_filename)
                            
                            # Remove temp file
                            os.unlink(tmp_filename)
                            
                            if pixmap.isNull():
                                self.error.emit("Failed to load preview image")
                            else:
                                self.image_ready.emit(pixmap)
                                
                        except Exception as e:
                            self.error.emit(f"Error loading preview: {str(e)}")
                
                # Create a label for the image
                info_label = QLabel(f"Title: {page.title}\nDate: {page.issue_date}\nLCCN: {page.lccn}")
                preview_layout.addWidget(info_label)
                
                # Add a loading message
                loading_label = QLabel("Loading preview...")
                preview_layout.addWidget(loading_label)
                
                # Create a scroll area for the image
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                preview_layout.addWidget(scroll_area)
                
                # Add close button
                close_button = QPushButton("Close")
                close_button.clicked.connect(preview_dialog.accept)
                preview_layout.addWidget(close_button)
                
                # Start the worker
                preview_worker = PreviewWorker(page)
                
                def on_image_ready(pixmap):
                    loading_label.setVisible(False)
                    image_label = QLabel()
                    image_label.setPixmap(pixmap)
                    image_label.setScaledContents(True)
                    image_label.setMinimumSize(1, 1)
                    scroll_area.setWidget(image_label)
                
                def on_preview_error(error_msg):
                    loading_label.setText(f"Error: {error_msg}")
                
                preview_worker.image_ready.connect(on_image_ready)
                preview_worker.error.connect(on_preview_error)
                preview_worker.start()
                
                # Show the dialog
                preview_dialog.exec_()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Preview Error",
                f"An error occurred loading the preview:\n{str(e)}"
            )
    
    def start_bulk_download(self):
        """Start bulk download for the selected timeframe."""
        try:
            if not API_AVAILABLE:
                QMessageBox.critical(
                    self,
                    "API Not Available",
                    "The ChroniclingAmerica API client is not available. Please check that the API module is installed correctly."
                )
                return
                
            # Check network connectivity
            try:
                import socket
                socket.create_connection(("chroniclingamerica.loc.gov", 80), timeout=5)
            except (socket.timeout, socket.error) as e:
                QMessageBox.critical(
                    self,
                    "Network Error",
                    f"Cannot connect to ChroniclingAmerica servers. Please check your internet connection and try again.\n\nError: {str(e)}"
                )
                return
            
            # Get parameters
            year = int(self.bulk_year_combo.currentText())
            
            # Month (optional)
            month = None
            if self.bulk_month_combo.currentIndex() > 0:  # Not "All Year"
                month = self.bulk_month_combo.currentText()
            
            # LCCN (optional)
            lccn = None
            newspaper_index = self.bulk_newspaper_combo.currentIndex()

            if newspaper_index > 0:  # Not "All Newspapers"
                if newspaper_index == self.bulk_newspaper_combo.count() - 1:  # "Other"
                    lccn = self.bulk_lccn_edit.text().strip()
                    # Only validate LCCN if one is provided
                    if lccn and not re.match(r'^sn\d{5,}$', lccn):
                        QMessageBox.warning(
                            self,
                            "Invalid LCCN Format",
                            "The LCCN should be in the format 'sn' followed by digits (e.g., sn83045604)."
                        )
                        return
                else:
                    # Extract LCCN from combo box text
                    text = self.bulk_newspaper_combo.currentText()
                    lccn_match = re.search(r'\((sn\d+)\)', text)
                    if lccn_match:
                        lccn = lccn_match.group(1)
            # For "All Newspapers" (index 0), lccn will remain None

            # State (optional)
            state = None
            if self.bulk_state_combo.currentIndex() > 0:  # Not "All States"
                state = self.bulk_state_combo.currentText()
            
            # Get download formats
            formats = []
            if self.bulk_download_pdf_check.isChecked():
                formats.append('pdf')
            if self.bulk_download_jp2_check.isChecked():
                formats.append('jp2')
            if self.bulk_download_ocr_check.isChecked():
                formats.append('ocr')
            if self.bulk_download_json_check.isChecked():
                formats.append('json')
                
            if not formats:
                QMessageBox.warning(
                    self,
                    "No Formats Selected",
                    "Please select at least one download format."
                )
                return
            
            # Configure download parameters
            download_params = {
                "year": year,
                "month": month,
                "lccn": lccn,  # Will be None for "All Newspapers"
                "state": state,  # Will be None for "All States"
                "formats": formats
            }
            
            # Configure repository manager
            repo_manager = None
            if self.bulk_import_check.isChecked():
                repo_manager = self.repository_manager
            
            # Clear the file status list
            self.file_status_list.clear()
            
            # Clear and initialize progress bars
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(100)
            self.search_progress_bar.setValue(0)
            self.search_progress_bar.setMaximum(100)
            
            # Create and configure worker
            self.bulk_download_worker = BulkDownloadWorker(
                download_params=download_params,
                download_dir=self.download_directory,
                repository_manager=repo_manager
            )
            
            # Connect signals
            self.bulk_download_worker.progress_signal.connect(self.update_download_progress)
            self.bulk_download_worker.search_progress_signal.connect(self.update_search_progress)
            self.bulk_download_worker.status_signal.connect(self.update_status)
            self.bulk_download_worker.file_status_signal.connect(self.update_file_status)
            self.bulk_download_worker.rate_limit_signal.connect(self.update_rate_limit)
            self.bulk_download_worker.error_signal.connect(self.bulk_download_error)
            self.bulk_download_worker.finished_signal.connect(self.bulk_download_finished)
            
            # Update UI
            self.api_status_label.setText("Bulk downloading...")
            self.cancel_button.setEnabled(True)
            self.bulk_download_button.setEnabled(False)
            
            # Show confirmation with estimate
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Bulk Download Started")
            
            timeframe = f"{month} {year}" if month else f"Year {year}"
            msg.setText(f"Starting bulk download for {timeframe}")
            
            # Include additional filters in the message
            filter_info = "Filters:"
            if lccn:
                newspaper_name = self.bulk_newspaper_combo.currentText().split(" (")[0]
                if newspaper_name == "Other":
                    filter_info += f"\n- LCCN: {lccn}"
                else:
                    filter_info += f"\n- Newspaper: {newspaper_name} ({lccn})"
            else:
                filter_info += "\n- All newspapers"
                
            if state and state != "All States":
                filter_info += f"\n- State: {state}"
                
            format_info = "Selected formats: " + ", ".join(formats)
            
            msg.setInformativeText(
                f"{filter_info}\n\n{format_info}\n\n"
                f"Download directory: {self.download_directory}\n\n"
                f"The download will continue in the background. You can monitor progress below."
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            
            # Start the worker
            self.bulk_download_worker.start()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Bulk Download Error",
                f"An error occurred starting the bulk download:\n{str(e)}"
            )
    
    def update_download_progress(self, current, total):
        """
        Update the download progress.
        
        Args:
            current: Current progress value
            total: Total progress value
        """
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
    def update_search_progress(self, current, total):
        """
        Update the search progress during bulk download.
        
        Args:
            current: Current page
            total: Total pages
        """
        self.search_progress_bar.setMaximum(total)
        self.search_progress_bar.setValue(current)
    
    def update_status(self, message):
        """
        Update the status text.
        
        Args:
            message: Status message
        """
        self.status_text.append(message)
        # Automatically scroll to bottom
        self.status_text.verticalScrollBar().setValue(self.status_text.verticalScrollBar().maximum())
    
    def update_file_status(self, filename, status):
        """
        Update the status of a specific file.
        
        Args:
            filename: File name
            status: Status message
        """
        # Check if item already exists
        found = False
        for i in range(self.file_status_list.count()):
            item = self.file_status_list.item(i)
            if item.text().startswith(filename):
                item.setText(f"{filename}: {status}")
                found = True
                break
                
        if not found:
            item = QListWidgetItem(f"{filename}: {status}")
            self.file_status_list.addItem(item)
            
        # Scroll to show the newest item
        self.file_status_list.scrollToBottom()
    
    def update_rate_limit(self, rate_limit_info):
        """
        Update rate limit information.
        
        Args:
            rate_limit_info: Dictionary with rate limit info
        """
        delay = rate_limit_info.get('delay', 0)
        last_request = rate_limit_info.get('last_request', 'Never')
        
        self.rate_limit_label.setText(f"Rate limit: {delay}s between requests")
        self.last_request_label.setText(f"Last request: {last_request}")
    
    def _cancel_current_operation(self):
        """Cancel the current operation."""
        # Cancel search worker
        if self.search_worker:
            self.status_text.append("Cancelling search operation...")
            self.search_worker.cancel()
        
        # Cancel bulk download worker
        if self.bulk_download_worker:
            self.status_text.append("Cancelling bulk download operation...")
            self.bulk_download_worker.cancel()
    
    def bulk_download_error(self, error_message):
        """
        Handle bulk download error.
        
        Args:
            error_message: Error message
        """
        # Update UI
        self.status_text.append(f"Error: {error_message}")
        
        # Show a message box only for serious errors
        if "No newspaper pages found" not in error_message:
            QMessageBox.critical(
                self,
                "Bulk Download Error",
                f"An error occurred during the bulk download:\n{error_message}"
            )
    
    def bulk_download_finished(self, results):
        """
        Handle bulk download completion.
        
        Args:
            results: Dictionary with download results
        """
        # Update UI
        self.api_status_label.setText("Ready")
        self.cancel_button.setEnabled(False)
        self.bulk_download_button.setEnabled(True)
        
        # Show completion message
        total_found = results.get('total_found', 0)
        downloaded = results.get('downloaded', 0)
        imported = results.get('imported', 0)
        timeframe = results.get('timeframe', '')
        
        completion_message = (
            f"Bulk download completed for {timeframe}\n\n"
            f"Total pages found: {total_found}\n"
            f"Pages downloaded: {downloaded}\n"
            f"Pages imported to repository: {imported}\n\n"
            f"Download directory: {self.download_directory}"
        )
        
        self.status_text.append("\n" + completion_message)
        
        # Emit signal to update repository tab if pages were imported
        if imported > 0:
            self.repository_updated_signal.emit()
            
        # Show a message box
        QMessageBox.information(
            self,
            "Bulk Download Complete",
            completion_message
        )
        
        # Clean up
        self.bulk_download_worker = None
    
    def show_api_unavailable(self):
        """Show a message that the API is unavailable."""
        # Disable controls
        self.search_button.setEnabled(False)
        self.bulk_download_button.setEnabled(False)
        
        # Show message
        self.api_status_label.setText("API Unavailable")
        self.status_text.append("The ChroniclingAmerica API client is not available. Please check that the API module is installed correctly.")
        
        # Add a message to the search form
        message_label = QLabel(
            "The ChroniclingAmerica API client is not available.\n"
            "Please check that the API module is installed correctly."
        )
        message_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Add to layout - find the search form layout
        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            if isinstance(item.widget(), QSplitter):
                splitter = item.widget()
                for j in range(splitter.count()):
                    if j == 0:  # Top widget
                        top_widget = splitter.widget(j)
                        top_layout = top_widget.layout()
                        if top_layout:
                            top_layout.insertWidget(2, message_label)  # Insert after description
                            break