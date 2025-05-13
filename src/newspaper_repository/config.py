#!/usr/bin/env python3
# File: config.py

"""
Configuration management module for the newspaper repository system.

This module handles:
1. Default configuration settings for all components
2. Loading custom settings from configuration files
3. Validation of configuration values
4. UI for configuration management
5. Documentation for all configuration options
"""

import os
import json
import logging
import platform
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union
from dataclasses import dataclass, field, asdict
import re
import shutil
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('repository_config')

# Define configuration options with their documentation and validation rules
@dataclass
class RepositoryConfig:
    """Configuration settings for the newspaper repository system."""
    
    # Repository paths
    repository_path: str = str(Path.home() / "newspaper_repository")
    """Base directory for all repository files and database."""
    
    database_path: str = ""  # Will be set to repository_path/repository.db by default
    """Path to the SQLite database file. If empty, defaults to {repository_path}/repository.db."""
    
    # Main Nova database settings
    main_db_path: str = ""
    """Path to the main Nova database. Required for integration with the main system."""
    
    # OCR settings
    tesseract_path: str = ""
    """Path to Tesseract OCR executable. If empty, system will search in PATH."""
    
    ocr_languages: str = "eng"
    """Languages to use for OCR, separated by '+' (e.g., 'eng+fra'). Default is English."""
    
    ocr_psm: int = 3
    """
    Page Segmentation Mode for Tesseract:
    0 - Orientation and script detection only
    1 - Automatic page segmentation with OSD
    2 - Automatic page segmentation, no OSD or OCR
    3 - Fully automatic page segmentation, no OSD (default)
    4 - Assume a single column of text of variable sizes
    5 - Assume a single uniform block of vertically aligned text
    6 - Assume a single uniform block of text
    7 - Treat the image as a single text line
    8 - Treat the image as a single word
    9 - Treat the image as a single word in a circle
    10 - Treat the image as a single character
    11 - Sparse text - Find as much text as possible in no particular order
    12 - Sparse text with OSD
    13 - Raw line - Treat the image as a single text line
    """
    
    ocr_oem: int = 3
    """
    OCR Engine Mode for Tesseract:
    0 - Legacy engine only
    1 - Neural nets LSTM engine only
    2 - Legacy + LSTM engines
    3 - Default based on what is available (recommended)
    """
    
    # Article extraction settings
    min_segment_height: int = 100
    """Minimum height in pixels for an article segment to be considered valid."""
    
    min_segment_width: int = 100
    """Minimum width in pixels for an article segment to be considered valid."""
    
    min_segment_text_length: int = 30
    """Minimum text length in characters for an article segment to be considered valid."""
    
    headline_max_lines: int = 3
    """Maximum number of lines to consider as the headline of an article."""
    
    # File storage settings
    image_format: str = "jpg"
    """Format to save image files (jpg, png, tiff)."""
    
    image_quality: int = 90
    """Quality for JPEG images (0-100)."""
    
    compress_text_files: bool = False
    """Whether to compress large text files with gzip."""
    
    # Processing settings
    max_concurrent_tasks: int = 2
    """Maximum number of concurrent processing tasks."""
    
    max_retries: int = 3
    """Maximum number of retry attempts for failed tasks."""
    
    retry_delay_seconds: int = 300
    """Delay in seconds before retrying a failed task."""
    
    task_timeout_minutes: int = 30
    """Maximum time in minutes a task can run before being considered stuck."""
    
    auto_process_imports: bool = True
    """Whether to automatically add imported pages to the processing queue."""
    
    # Search engine settings
    search_index_path: str = ""  # Will be set to repository_path/search_index.db by default
    """Path to the search index database. If empty, defaults to {repository_path}/search_index.db."""
    
    fuzzy_search_enabled: bool = True
    """Whether to enable fuzzy matching for search queries."""
    
    fuzzy_threshold: int = 70
    """Minimum similarity score (0-100) for fuzzy matching. Higher values mean stricter matching."""
    
    default_search_limit: int = 100
    """Default maximum number of search results to return."""
    
    # API settings
    api_request_delay: float = 0.5
    """Delay in seconds between API requests to avoid rate limiting."""
    
    chronicling_america_download_dir: str = ""  # Will be set to repository_path/downloads/chroniclingamerica by default
    """Directory for ChroniclingAmerica downloads. If empty, defaults to {repository_path}/downloads/chroniclingamerica."""
    
    # Integration settings
    sync_interval_minutes: int = 0
    """Interval for auto-syncing with main database (0 = disabled)."""
    
    require_confirmation_for_import: bool = True
    """Whether to require user confirmation before importing to main database."""
    
    # Appearance settings
    ui_theme: str = "default"
    """UI theme to use (default, light, dark)."""
    
    def __post_init__(self):
        """Set derived values and perform basic validation."""
        # Set default database path if not specified
        if not self.database_path:
            self.database_path = os.path.join(self.repository_path, "repository.db")
            
        # Set default search index path if not specified
        if not self.search_index_path:
            self.search_index_path = os.path.join(self.repository_path, "search_index.db")
            
        # Set default ChroniclingAmerica download directory if not specified
        if not self.chronicling_america_download_dir:
            self.chronicling_america_download_dir = os.path.join(self.repository_path, "downloads", "chroniclingamerica")
        
        # Normalize paths
        self.repository_path = os.path.abspath(os.path.expanduser(self.repository_path))
        self.database_path = os.path.abspath(os.path.expanduser(self.database_path))
        self.search_index_path = os.path.abspath(os.path.expanduser(self.search_index_path))
        self.chronicling_america_download_dir = os.path.abspath(os.path.expanduser(self.chronicling_america_download_dir))
        
        if self.main_db_path:
            self.main_db_path = os.path.abspath(os.path.expanduser(self.main_db_path))
        if self.tesseract_path:
            self.tesseract_path = os.path.abspath(os.path.expanduser(self.tesseract_path))
    
    def validate(self) -> List[str]:
        """
        Validate the configuration settings.
        
        Returns:
            List of validation error messages, or empty list if valid
        """
        errors = []
        
        # Validate paths
        if not os.access(os.path.dirname(self.repository_path), os.W_OK):
            errors.append(f"Repository path directory is not writable: {os.path.dirname(self.repository_path)}")
            
        if not os.access(os.path.dirname(self.database_path), os.W_OK):
            errors.append(f"Database path directory is not writable: {os.path.dirname(self.database_path)}")
            
        if not os.access(os.path.dirname(self.search_index_path), os.W_OK):
            errors.append(f"Search index path directory is not writable: {os.path.dirname(self.search_index_path)}")
            
        if not os.access(os.path.dirname(self.chronicling_america_download_dir), os.W_OK):
            errors.append(f"Download directory is not writable: {os.path.dirname(self.chronicling_america_download_dir)}")
            
        if self.main_db_path and not os.path.exists(self.main_db_path):
            errors.append(f"Main database path does not exist: {self.main_db_path}")
            
        # Validate Tesseract
        if self.tesseract_path:
            if not os.path.exists(self.tesseract_path):
                errors.append(f"Tesseract executable not found at: {self.tesseract_path}")
        else:
            # Check if tesseract is in PATH
            tesseract_in_path = shutil.which("tesseract") is not None
            if not tesseract_in_path:
                errors.append("Tesseract not found in PATH. Please install Tesseract or set tesseract_path.")
        
        # Validate OCR settings
        if not re.match(r'^[a-z]{3}(\+[a-z]{3})*$', self.ocr_languages):
            errors.append(f"Invalid OCR languages format: {self.ocr_languages}. Use format like 'eng' or 'eng+fra'.")
            
        if not 0 <= self.ocr_psm <= 13:
            errors.append(f"Invalid PSM value: {self.ocr_psm}. Must be between 0 and 13.")
            
        if not 0 <= self.ocr_oem <= 3:
            errors.append(f"Invalid OEM value: {self.ocr_oem}. Must be between 0 and 3.")
        
        # Validate article extraction settings
        if self.min_segment_height <= 0:
            errors.append(f"Invalid min_segment_height: {self.min_segment_height}. Must be positive.")
            
        if self.min_segment_width <= 0:
            errors.append(f"Invalid min_segment_width: {self.min_segment_width}. Must be positive.")
            
        if self.min_segment_text_length <= 0:
            errors.append(f"Invalid min_segment_text_length: {self.min_segment_text_length}. Must be positive.")
            
        if self.headline_max_lines <= 0:
            errors.append(f"Invalid headline_max_lines: {self.headline_max_lines}. Must be positive.")
        
        # Validate file storage settings
        if self.image_format not in ["jpg", "png", "tiff"]:
            errors.append(f"Invalid image_format: {self.image_format}. Must be jpg, png, or tiff.")
            
        if not 0 <= self.image_quality <= 100:
            errors.append(f"Invalid image_quality: {self.image_quality}. Must be between 0 and 100.")
        
        # Validate processing settings
        if self.max_concurrent_tasks <= 0:
            errors.append(f"Invalid max_concurrent_tasks: {self.max_concurrent_tasks}. Must be positive.")
            
        if self.max_retries < 0:
            errors.append(f"Invalid max_retries: {self.max_retries}. Must be non-negative.")
            
        if self.retry_delay_seconds < 0:
            errors.append(f"Invalid retry_delay_seconds: {self.retry_delay_seconds}. Must be non-negative.")
            
        if self.task_timeout_minutes <= 0:
            errors.append(f"Invalid task_timeout_minutes: {self.task_timeout_minutes}. Must be positive.")
        
        # Validate search settings
        if not 0 <= self.fuzzy_threshold <= 100:
            errors.append(f"Invalid fuzzy_threshold: {self.fuzzy_threshold}. Must be between 0 and 100.")
            
        if self.default_search_limit <= 0:
            errors.append(f"Invalid default_search_limit: {self.default_search_limit}. Must be positive.")
        
        # Validate API settings
        if self.api_request_delay < 0:
            errors.append(f"Invalid api_request_delay: {self.api_request_delay}. Must be non-negative.")
        
        # Validate integration settings
        if self.sync_interval_minutes < 0:
            errors.append(f"Invalid sync_interval_minutes: {self.sync_interval_minutes}. Must be non-negative.")
        
        # Validate appearance settings
        if self.ui_theme not in ["default", "light", "dark"]:
            errors.append(f"Invalid ui_theme: {self.ui_theme}. Must be default, light, or dark.")
            
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'RepositoryConfig':
        """Create configuration from dictionary."""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__annotations__})


class ConfigManager:
    """
    Manages configuration settings for the newspaper repository system.
    Handles loading, saving, and validating configuration.
    """
    
    def __init__(self):
        """Initialize the configuration manager with default settings."""
        self.config = RepositoryConfig()
        self.config_file = self._get_default_config_path()
        
        # Try to load config from default location
        if os.path.exists(self.config_file):
            try:
                self.load_config(self.config_file)
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")
                # Continue with default settings
    
    def _get_default_config_path(self) -> str:
        """Get the default path for the configuration file."""
        # Platform-specific config location
        if platform.system() == "Windows":
            config_dir = os.path.join(os.environ.get("APPDATA", ""), "NovaHistoricalDB")
        else:  # macOS, Linux, etc.
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "novahistoricaldb")
            
        # Create config directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        return os.path.join(config_dir, "newspaper_repository.json")
    
    def load_config(self, config_file: str) -> bool:
        """
        Load configuration from a JSON file.
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
                
            self.config = RepositoryConfig.from_dict(config_dict)
            self.config_file = config_file
            logger.info(f"Loaded configuration from {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def save_config(self, config_file: Optional[str] = None) -> bool:
        """
        Save configuration to a JSON file.
        
        Args:
            config_file: Path to save the configuration file, or None to use current path
            
        Returns:
            True if successful, False otherwise
        """
        if config_file:
            self.config_file = config_file
            
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config.to_dict(), f, indent=4)
                
            logger.info(f"Saved configuration to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def validate_config(self) -> List[str]:
        """
        Validate the current configuration.
        
        Returns:
            List of validation error messages, or empty list if valid
        """
        return self.config.validate()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = RepositoryConfig()
    
    def get_tesseract_cmd(self) -> str:
        """
        Get the Tesseract command path.
        
        Returns:
            Path to tesseract executable
        """
        if self.config.tesseract_path:
            return self.config.tesseract_path
            
        # Try to find tesseract in PATH
        tesseract_cmd = shutil.which("tesseract")
        if tesseract_cmd:
            return tesseract_cmd
            
        # Platform-specific default locations
        if platform.system() == "Windows":
            return r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        elif platform.system() == "Darwin":  # macOS
            return "/usr/local/bin/tesseract"
        else:  # Linux
            return "/usr/bin/tesseract"
    
    def get_tesseract_config(self) -> str:
        """
        Get the Tesseract configuration string.
        
        Returns:
            Configuration string for pytesseract
        """
        return f"--psm {self.config.ocr_psm} --oem {self.config.ocr_oem} -l {self.config.ocr_languages}"
    
    def get_repository_dirs(self) -> Dict[str, str]:
        """
        Get paths to all repository directories.
        
        Returns:
            Dictionary with paths to all repository directories
        """
        base_path = self.config.repository_path
        return {
            "base": base_path,
            "original_pages": os.path.join(base_path, "original_pages"),
            "ocr_text": os.path.join(base_path, "ocr_text"),
            "hocr_output": os.path.join(base_path, "hocr_output"),
            "article_segments": os.path.join(base_path, "article_segments"),
            "enhanced_segments": os.path.join(base_path, "enhanced_segments")
        }


try:
    from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                                QLabel, QLineEdit, QSpinBox, QComboBox, QCheckBox, 
                                QPushButton, QTabWidget, QWidget, QFileDialog, 
                                QMessageBox, QGroupBox, QSizePolicy)
    from PyQt5.QtCore import Qt, pyqtSignal
    from PyQt5.QtGui import QIntValidator

    class ConfigDialog(QDialog):
        """Dialog for editing configuration settings through a graphical interface."""
        
        config_updated = pyqtSignal()
        
        def __init__(self, config_manager: ConfigManager, parent=None):
            """
            Initialize the configuration dialog.
            
            Args:
                config_manager: The configuration manager
                parent: Parent widget
            """
            super().__init__(parent)
            self.config_manager = config_manager
            self.config = config_manager.config
            self.setWindowTitle("Newspaper Repository Configuration")
            self.setMinimumWidth(600)
            self.setup_ui()
        
        def setup_ui(self):
            """Set up the dialog user interface."""
            main_layout = QVBoxLayout(self)
            
            # Create tab widget
            tabs = QTabWidget()
            
            # Create tabs for different categories of settings
            paths_tab = self.create_paths_tab()
            ocr_tab = self.create_ocr_tab()
            article_tab = self.create_article_tab()
            storage_tab = self.create_storage_tab()
            processing_tab = self.create_processing_tab()
            search_tab = self.create_search_tab()
            api_tab = self.create_api_tab()
            
            # Add tabs to widget
            tabs.addTab(paths_tab, "Paths")
            tabs.addTab(ocr_tab, "OCR Settings")
            tabs.addTab(article_tab, "Article Extraction")
            tabs.addTab(storage_tab, "File Storage")
            tabs.addTab(processing_tab, "Processing & Integration")
            tabs.addTab(search_tab, "Search Engine")
            tabs.addTab(api_tab, "API Settings")
            
            main_layout.addWidget(tabs)
            
            # Add buttons at the bottom
            button_layout = QHBoxLayout()
            
            self.save_button = QPushButton("Save")
            self.save_button.clicked.connect(self.save_config)
            
            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.clicked.connect(self.reject)
            
            self.reset_button = QPushButton("Reset to Defaults")
            self.reset_button.clicked.connect(self.reset_to_defaults)
            
            button_layout.addWidget(self.reset_button)
            button_layout.addStretch()
            button_layout.addWidget(self.cancel_button)
            button_layout.addWidget(self.save_button)
            
            main_layout.addLayout(button_layout)
            
            # Load current settings
            self.load_settings()
        
        def create_paths_tab(self) -> QWidget:
            """Create the paths configuration tab."""
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            form = QFormLayout()
            
            # Repository path
            self.repository_path = QLineEdit()
            browse_repo_button = QPushButton("Browse...")
            browse_repo_button.clicked.connect(self.browse_repository_path)
            
            repo_layout = QHBoxLayout()
            repo_layout.addWidget(self.repository_path)
            repo_layout.addWidget(browse_repo_button)
            
            form.addRow("Repository Path:", repo_layout)
            form.addRow("", QLabel("Base directory for all repository files and database."))
            
            # Database path
            self.database_path = QLineEdit()
            browse_db_button = QPushButton("Browse...")
            browse_db_button.clicked.connect(self.browse_database_path)
            
            db_layout = QHBoxLayout()
            db_layout.addWidget(self.database_path)
            db_layout.addWidget(browse_db_button)
            
            form.addRow("Database Path:", db_layout)
            form.addRow("", QLabel("Path to the SQLite database file. If empty, defaults to {repository_path}/repository.db."))
            
            # Main Nova database path
            self.main_db_path = QLineEdit()
            browse_main_db_button = QPushButton("Browse...")
            browse_main_db_button.clicked.connect(self.browse_main_db_path)
            
            main_db_layout = QHBoxLayout()
            main_db_layout.addWidget(self.main_db_path)
            main_db_layout.addWidget(browse_main_db_button)
            
            form.addRow("Main DB Path:", main_db_layout)
            form.addRow("", QLabel("Path to the main Nova database. Required for integration with the main system."))
            
            # Tesseract path
            self.tesseract_path = QLineEdit()
            browse_tesseract_button = QPushButton("Browse...")
            browse_tesseract_button.clicked.connect(self.browse_tesseract_path)
            
            tesseract_layout = QHBoxLayout()
            tesseract_layout.addWidget(self.tesseract_path)
            tesseract_layout.addWidget(browse_tesseract_button)
            
            form.addRow("Tesseract Path:", tesseract_layout)
            form.addRow("", QLabel("Path to Tesseract OCR executable. If empty, system will search in PATH."))
            
            layout.addLayout(form)
            layout.addStretch()
            return tab
        
        def create_ocr_tab(self) -> QWidget:
            """Create the OCR settings tab."""
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            form = QFormLayout()
            
            # OCR languages
            self.ocr_languages = QLineEdit()
            form.addRow("OCR Languages:", self.ocr_languages)
            form.addRow("", QLabel("Languages to use for OCR, separated by '+' (e.g., 'eng+fra'). Default is English."))
            
            # PSM mode
            self.ocr_psm = QComboBox()
            psm_options = [
                "0 - Orientation and script detection only",
                "1 - Automatic page segmentation with OSD",
                "2 - Automatic page segmentation, no OSD or OCR",
                "3 - Fully automatic page segmentation, no OSD (default)",
                "4 - Assume a single column of text of variable sizes",
                "5 - Assume a single uniform block of vertically aligned text",
                "6 - Assume a single uniform block of text",
                "7 - Treat the image as a single text line",
                "8 - Treat the image as a single word",
                "9 - Treat the image as a single word in a circle",
                "10 - Treat the image as a single character",
                "11 - Sparse text - Find as much text as possible in no particular order",
                "12 - Sparse text with OSD",
                "13 - Raw line - Treat the image as a single text line"
            ]
            self.ocr_psm.addItems(psm_options)
            form.addRow("Page Segmentation Mode:", self.ocr_psm)
            
            # OEM mode
            self.ocr_oem = QComboBox()
            oem_options = [
                "0 - Legacy engine only",
                "1 - Neural nets LSTM engine only",
                "2 - Legacy + LSTM engines",
                "3 - Default based on what is available (recommended)"
            ]
            self.ocr_oem.addItems(oem_options)
            form.addRow("OCR Engine Mode:", self.ocr_oem)
            
            layout.addLayout(form)
            
            # Add information about testing OCR settings
            info_group = QGroupBox("OCR Settings Help")
            info_layout = QVBoxLayout(info_group)
            
            info_text = QLabel(
                "OCR settings affect text recognition quality and speed. Tips:\n\n"
                "- For newspaper pages, PSM 3 (auto) or 6 (single block) often work best\n"
                "- Multiple languages slow down OCR but may improve accuracy for mixed text\n"
                "- OEM 3 (default) is recommended as it automatically selects the best available engine\n\n"
                "If you're unsure, leave the default settings."
            )
            info_text.setWordWrap(True)
            info_layout.addWidget(info_text)
            
            layout.addWidget(info_group)
            layout.addStretch()
            return tab
        
        def create_article_tab(self) -> QWidget:
            """Create the article extraction settings tab."""
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            form = QFormLayout()
            
            # Min segment height
            self.min_segment_height = QSpinBox()
            self.min_segment_height.setRange(10, 1000)
            form.addRow("Min Segment Height (px):", self.min_segment_height)
            
            # Min segment width
            self.min_segment_width = QSpinBox()
            self.min_segment_width.setRange(10, 1000)
            form.addRow("Min Segment Width (px):", self.min_segment_width)
            
            # Min segment text length
            self.min_segment_text_length = QSpinBox()
            self.min_segment_text_length.setRange(1, 1000)
            form.addRow("Min Segment Text Length:", self.min_segment_text_length)
            
            # Headline max lines
            self.headline_max_lines = QSpinBox()
            self.headline_max_lines.setRange(1, 10)
            form.addRow("Max Headline Lines:", self.headline_max_lines)
            
            layout.addLayout(form)
            
            # Add information about article extraction settings
            info_group = QGroupBox("Article Extraction Help")
            info_layout = QVBoxLayout(info_group)
            
            info_text = QLabel(
                "These settings affect how articles are identified and extracted from newspaper pages:\n\n"
                "- Minimum dimensions filter out small fragments that aren't full articles\n"
                "- Minimum text length prevents extracting image captions or short fragments\n"
                "- Max headline lines determines how many initial lines to treat as the article headline\n\n"
                "Adjust these settings based on the newspapers you're processing."
            )
            info_text.setWordWrap(True)
            info_layout.addWidget(info_text)
            
            layout.addWidget(info_group)
            layout.addStretch()
            return tab
        
        def create_storage_tab(self) -> QWidget:
            """Create the file storage settings tab."""
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            form = QFormLayout()
            
            # Image format
            self.image_format = QComboBox()
            self.image_format.addItems(["jpg", "png", "tiff"])
            form.addRow("Image Format:", self.image_format)
            
            # Image quality
            self.image_quality = QSpinBox()
            self.image_quality.setRange(1, 100)
            form.addRow("JPEG Image Quality:", self.image_quality)
            
            # Compress text files
            self.compress_text_files = QCheckBox("Compress large text files with gzip")
            form.addRow("", self.compress_text_files)
            
            layout.addLayout(form)
            
            # Add information about storage settings
            info_group = QGroupBox("Storage Settings Help")
            info_layout = QVBoxLayout(info_group)
            
            info_text = QLabel(
                "File storage settings affect disk usage and access speed:\n\n"
                "- JPG is smaller but lossy; PNG is lossless but larger; TIFF preserves the most quality\n"
                "- Higher JPEG quality (1-100) means better image quality but larger files\n"
                "- Text compression saves disk space but adds processing overhead when reading files\n\n"
                "For most newspaper pages, JPG at quality 90 provides a good balance."
            )
            info_text.setWordWrap(True)
            info_layout.addWidget(info_text)
            
            layout.addWidget(info_group)
            layout.addStretch()
            return tab
        
        def create_processing_tab(self) -> QWidget:
            """Create the processing and integration settings tab."""
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            # Processing settings group
            processing_group = QGroupBox("Processing Settings")
            processing_layout = QFormLayout(processing_group)
            
            # Max concurrent tasks
            self.max_concurrent_tasks = QSpinBox()
            self.max_concurrent_tasks.setRange(1, 16)
            processing_layout.addRow("Max Concurrent Tasks:", self.max_concurrent_tasks)
            
            # Auto process imports
            self.auto_process_imports = QCheckBox("Automatically process new imports")
            processing_layout.addRow("", self.auto_process_imports)
            
            # Max retries
            self.max_retries = QSpinBox()
            self.max_retries.setRange(0, 10)
            processing_layout.addRow("Max Retry Attempts:", self.max_retries)
            
            # Retry delay
            self.retry_delay_seconds = QSpinBox()
            self.retry_delay_seconds.setRange(0, 3600)
            self.retry_delay_seconds.setSuffix(" seconds")
            processing_layout.addRow("Retry Delay:", self.retry_delay_seconds)
            
            # Task timeout
            self.task_timeout_minutes = QSpinBox()
            self.task_timeout_minutes.setRange(1, 240)
            self.task_timeout_minutes.setSuffix(" minutes")
            processing_layout.addRow("Task Timeout:", self.task_timeout_minutes)
            
            layout.addWidget(processing_group)
            
            # Integration settings group
            integration_group = QGroupBox("Integration Settings")
            integration_layout = QFormLayout(integration_group)
            
            # Sync interval
            self.sync_interval_minutes = QSpinBox()
            self.sync_interval_minutes.setRange(0, 1440)  # 0 to 24 hours
            self.sync_interval_minutes.setSpecialValueText("Disabled")
            integration_layout.addRow("Auto-sync Interval (minutes):", self.sync_interval_minutes)
            
            # Require confirmation
            self.require_confirmation_for_import = QCheckBox("Require confirmation before import to main database")
            integration_layout.addRow("", self.require_confirmation_for_import)
            
            layout.addWidget(integration_group)
            
            # UI settings group
            ui_group = QGroupBox("UI Settings")
            ui_layout = QFormLayout(ui_group)
            
            # UI theme
            self.ui_theme = QComboBox()
            self.ui_theme.addItems(["default", "light", "dark"])
            ui_layout.addRow("UI Theme:", self.ui_theme)
            
            layout.addWidget(ui_group)
            layout.addStretch()
            return tab
        
        def browse_repository_path(self):
            """Browse for repository path directory."""
            directory = QFileDialog.getExistingDirectory(
                self, "Select Repository Directory", 
                self.repository_path.text() or os.path.expanduser("~")
            )
            if directory:
                self.repository_path.setText(directory)
        
        def browse_database_path(self):
            """Browse for database file path."""
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Select Database File",
                self.database_path.text() or os.path.join(self.repository_path.text(), "repository.db"),
                "SQLite Database (*.db);;All Files (*)"
            )
            if file_path:
                self.database_path.setText(file_path)
        
        def browse_main_db_path(self):
            """Browse for main database file path."""
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Main Nova Database",
                self.main_db_path.text() or os.path.expanduser("~"),
                "SQLite Database (*.db);;All Files (*)"
            )
            if file_path:
                self.main_db_path.setText(file_path)
        
        def browse_tesseract_path(self):
            """Browse for Tesseract executable path."""
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Tesseract Executable",
                self.tesseract_path.text() or "",
                "Executable Files (*.exe);;All Files (*)"
            )
            if file_path:
                self.tesseract_path.setText(file_path)
                
        def create_search_tab(self) -> QWidget:
            """Create the search engine settings tab."""
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            # Main settings group
            search_group = QGroupBox("Search Engine Settings")
            search_layout = QFormLayout(search_group)
            
            # Search index path
            self.search_index_path = QLineEdit()
            browse_index_button = QPushButton("Browse...")
            browse_index_button.clicked.connect(self.browse_search_index_path)
            
            index_layout = QHBoxLayout()
            index_layout.addWidget(self.search_index_path)
            index_layout.addWidget(browse_index_button)
            
            search_layout.addRow("Search Index Path:", index_layout)
            search_layout.addRow("", QLabel("Path to the search index database. If empty, defaults to {repository_path}/search_index.db."))
            
            # Fuzzy search enabled
            self.fuzzy_search_enabled = QCheckBox("Enable fuzzy matching for search queries")
            search_layout.addRow("", self.fuzzy_search_enabled)
            
            # Fuzzy threshold
            self.fuzzy_threshold = QSpinBox()
            self.fuzzy_threshold.setRange(0, 100)
            self.fuzzy_threshold.setSuffix("%")
            search_layout.addRow("Fuzzy Match Threshold:", self.fuzzy_threshold)
            
            # Default search limit
            self.default_search_limit = QSpinBox()
            self.default_search_limit.setRange(1, 1000)
            self.default_search_limit.setSingleStep(10)
            search_layout.addRow("Default Search Limit:", self.default_search_limit)
            
            layout.addWidget(search_group)
            
            # Add information about search settings
            info_group = QGroupBox("Search Settings Help")
            info_layout = QVBoxLayout(info_group)
            
            info_text = QLabel(
                "Search engine settings affect search performance and quality:\n\n"
                "- Fuzzy matching enables finding similar terms (e.g., 'newspaper' when searching for 'newpaper')\n"
                "- Higher fuzzy threshold (0-100%) means stricter matching, requiring closer similarity\n"
                "- Default search limit controls maximum results returned (higher values may slow down searches)\n\n"
                "For most use cases, enabling fuzzy search with a threshold of 70% provides a good balance."
            )
            info_text.setWordWrap(True)
            info_layout.addWidget(info_text)
            
            layout.addWidget(info_group)
            layout.addStretch()
            return tab
            
        def browse_search_index_path(self):
            """Browse for search index file path."""
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Select Search Index File",
                self.search_index_path.text() or os.path.join(self.repository_path.text(), "search_index.db"),
                "SQLite Database (*.db);;All Files (*)"
            )
            if file_path:
                self.search_index_path.setText(file_path)
                
        def create_api_tab(self) -> QWidget:
            """Create the API settings tab."""
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            # General API settings group
            general_group = QGroupBox("General API Settings")
            general_layout = QFormLayout(general_group)
            
            # API request delay
            self.api_request_delay = QDoubleSpinBox()
            self.api_request_delay.setRange(0.0, 10.0)
            self.api_request_delay.setDecimals(1)
            self.api_request_delay.setSingleStep(0.1)
            self.api_request_delay.setSuffix(" seconds")
            general_layout.addRow("Request Delay:", self.api_request_delay)
            general_layout.addRow("", QLabel("Delay between API requests to avoid rate limiting."))
            
            layout.addWidget(general_group)
            
            # ChroniclingAmerica settings group
            ca_group = QGroupBox("ChroniclingAmerica API Settings")
            ca_layout = QFormLayout(ca_group)
            
            # ChroniclingAmerica download directory
            self.chronicling_america_download_dir = QLineEdit()
            browse_ca_button = QPushButton("Browse...")
            browse_ca_button.clicked.connect(self.browse_ca_download_dir)
            
            ca_dir_layout = QHBoxLayout()
            ca_dir_layout.addWidget(self.chronicling_america_download_dir)
            ca_dir_layout.addWidget(browse_ca_button)
            
            ca_layout.addRow("Download Directory:", ca_dir_layout)
            ca_layout.addRow("", QLabel("Directory for ChroniclingAmerica downloads. If empty, defaults to {repository_path}/downloads/chroniclingamerica."))
            
            layout.addWidget(ca_group)
            
            # Add information about API settings
            info_group = QGroupBox("API Settings Help")
            info_layout = QVBoxLayout(info_group)
            
            info_text = QLabel(
                "API settings affect interactions with external services:\n\n"
                "- Request delay prevents hitting rate limits by spacing out consecutive requests\n"
                "- Setting a dedicated download directory helps organize content by source\n\n"
                "The Library of Congress ChroniclingAmerica API does not require authentication, but it's still "
                "good practice to use reasonable delays between requests."
            )
            info_text.setWordWrap(True)
            info_layout.addWidget(info_text)
            
            layout.addWidget(info_group)
            layout.addStretch()
            return tab
            
        def browse_ca_download_dir(self):
            """Browse for ChroniclingAmerica download directory."""
            directory = QFileDialog.getExistingDirectory(
                self, "Select ChroniclingAmerica Download Directory", 
                self.chronicling_america_download_dir.text() or os.path.join(self.repository_path.text(), "downloads", "chroniclingamerica")
            )
            if directory:
                self.chronicling_america_download_dir.setText(directory)
        
        def load_settings(self):
            """Load current settings into UI controls."""
            # Paths tab
            self.repository_path.setText(self.config.repository_path)
            self.database_path.setText(self.config.database_path)
            self.main_db_path.setText(self.config.main_db_path)
            self.tesseract_path.setText(self.config.tesseract_path)
            
            # OCR tab
            self.ocr_languages.setText(self.config.ocr_languages)
            self.ocr_psm.setCurrentIndex(self.config.ocr_psm)
            self.ocr_oem.setCurrentIndex(self.config.ocr_oem)
            
            # Article tab
            self.min_segment_height.setValue(self.config.min_segment_height)
            self.min_segment_width.setValue(self.config.min_segment_width)
            self.min_segment_text_length.setValue(self.config.min_segment_text_length)
            self.headline_max_lines.setValue(self.config.headline_max_lines)
            
            # Storage tab
            self.image_format.setCurrentText(self.config.image_format)
            self.image_quality.setValue(self.config.image_quality)
            self.compress_text_files.setChecked(self.config.compress_text_files)
            
            # Processing tab
            self.max_concurrent_tasks.setValue(self.config.max_concurrent_tasks)
            self.auto_process_imports.setChecked(self.config.auto_process_imports)
            self.max_retries.setValue(self.config.max_retries)
            self.retry_delay_seconds.setValue(self.config.retry_delay_seconds)
            self.task_timeout_minutes.setValue(self.config.task_timeout_minutes)
            self.sync_interval_minutes.setValue(self.config.sync_interval_minutes)
            self.require_confirmation_for_import.setChecked(self.config.require_confirmation_for_import)
            self.ui_theme.setCurrentText(self.config.ui_theme)
            
            # Search tab
            self.search_index_path.setText(self.config.search_index_path)
            self.fuzzy_search_enabled.setChecked(self.config.fuzzy_search_enabled)
            self.fuzzy_threshold.setValue(self.config.fuzzy_threshold)
            self.default_search_limit.setValue(self.config.default_search_limit)
            
            # API tab
            self.api_request_delay.setValue(self.config.api_request_delay)
            self.chronicling_america_download_dir.setText(self.config.chronicling_america_download_dir)
        
        def save_config(self):
            """Save settings from UI controls to configuration."""
            # Update config from UI values
            
            # Paths tab
            self.config.repository_path = self.repository_path.text()
            self.config.database_path = self.database_path.text()
            self.config.main_db_path = self.main_db_path.text()
            self.config.tesseract_path = self.tesseract_path.text()
            
            # OCR tab
            self.config.ocr_languages = self.ocr_languages.text()
            self.config.ocr_psm = self.ocr_psm.currentIndex()
            self.config.ocr_oem = self.ocr_oem.currentIndex()
            
            # Article tab
            self.config.min_segment_height = self.min_segment_height.value()
            self.config.min_segment_width = self.min_segment_width.value()
            self.config.min_segment_text_length = self.min_segment_text_length.value()
            self.config.headline_max_lines = self.headline_max_lines.value()
            
            # Storage tab
            self.config.image_format = self.image_format.currentText()
            self.config.image_quality = self.image_quality.value()
            self.config.compress_text_files = self.compress_text_files.isChecked()
            
            # Processing tab
            self.config.max_concurrent_tasks = self.max_concurrent_tasks.value()
            self.config.auto_process_imports = self.auto_process_imports.isChecked()
            self.config.max_retries = self.max_retries.value()
            self.config.retry_delay_seconds = self.retry_delay_seconds.value()
            self.config.task_timeout_minutes = self.task_timeout_minutes.value()
            self.config.sync_interval_minutes = self.sync_interval_minutes.value()
            self.config.require_confirmation_for_import = self.require_confirmation_for_import.isChecked()
            self.config.ui_theme = self.ui_theme.currentText()
            
            # Search tab
            self.config.search_index_path = self.search_index_path.text()
            self.config.fuzzy_search_enabled = self.fuzzy_search_enabled.isChecked()
            self.config.fuzzy_threshold = self.fuzzy_threshold.value()
            self.config.default_search_limit = self.default_search_limit.value()
            
            # API tab
            self.config.api_request_delay = self.api_request_delay.value()
            self.config.chronicling_america_download_dir = self.chronicling_america_download_dir.text()
            
            # Validate configuration
            errors = self.config.validate()
            if errors:
                # Show validation errors
                QMessageBox.warning(
                    self,
                    "Configuration Errors",
                    "The following configuration errors were found:\n\n" + "\n".join(errors)
                )
                return
            
            # Save configuration
            self.config_manager.config = self.config
            if self.config_manager.save_config():
                self.config_updated.emit()
                self.accept()
            else:
                QMessageBox.critical(
                    self,
                    "Save Error",
                    "Failed to save configuration file."
                )
        
        def reset_to_defaults(self):
            """Reset configuration to default values."""
            if QMessageBox.question(
                self,
                "Reset Configuration",
                "Are you sure you want to reset all settings to default values?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self.config_manager.reset_to_defaults()
                self.config = self.config_manager.config
                self.load_settings()

except ImportError:
    # PyQt5 not available, UI components will not be available
    logger.warning("PyQt5 not available. Configuration UI will not be available.")
    ConfigDialog = None


# Create a global instance for easy access throughout the application
config_manager = ConfigManager()

def get_config() -> RepositoryConfig:
    """
    Get the current configuration.
    
    Returns:
        Current configuration settings
    """
    return config_manager.config

def show_config_dialog(parent=None) -> bool:
    """
    Show the configuration dialog.
    
    Args:
        parent: Parent widget
        
    Returns:
        True if configuration was updated, False otherwise
    """
    if ConfigDialog is None:
        logger.error("Configuration UI is not available (PyQt5 not installed)")
        return False
        
    dialog = ConfigDialog(config_manager, parent)
    result = dialog.exec_()
    return result == QDialog.Accepted


if __name__ == "__main__":
    # When run directly, show the configuration dialog
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    show_config_dialog()
    sys.exit(0)