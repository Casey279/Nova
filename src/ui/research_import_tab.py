# File: research_import_tab.py

import os
import re
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QFrame, QSplitter, QMessageBox, QDialog,
    QTextEdit, QProgressBar
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap

# Add parent directory to Python path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_manager import DatabaseManager

class DateDetector:
    """Handles detection and standardization of dates in filenames"""
    
    @staticmethod
    def detect_date(filename):
        """
        Detect date in filename using multiple pattern matching strategies.
        Returns standardized date string (YYYY-MM-DD) or None if no date found.
        """
        # Remove file extension
        base_name = os.path.splitext(filename)[0]
        
        # List of date patterns to try, in order of reliability
        patterns = [
            # YYYY-MM-DD or YYYY_MM_DD
            (r'(\d{4})[-_](\d{2})[-_](\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
            
            # YYYYMMDD
            (r'(\d{4})(\d{2})(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
            
            # YYYY-MMM-DD or YYYY_MMM_DD
            (r'(\d{4})[-_](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-_](\d{2})',
             lambda m: f"{m.group(1)}-{DateDetector._month_to_num(m.group(2))}-{m.group(3).zfill(2)}"),
            
            # MM-DD-YYYY or MM_DD_YYYY
            (r'(\d{2})[-_](\d{2})[-_](\d{4})', lambda m: f"{m.group(3)}-{m.group(1)}-{m.group(2)}"),
            
            # More patterns can be added here
        ]
        
        # Try each pattern in sequence
        for pattern, formatter in patterns:
            match = re.search(pattern, base_name)
            if match:
                try:
                    date_str = formatter(match)
                    # Validate the date
                    datetime.strptime(date_str, "%Y-%m-%d")
                    return date_str
                except ValueError:
                    continue
                
        return None
    
    @staticmethod
    def _month_to_num(month):
        """Convert month abbreviation to number string"""
        months = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        return months.get(month, '01')

class SourceDetector:
    """Handles detection of source names in filenames"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    def detect_source(self, filename):
        """
        Detect source name in filename.
        Returns (source_name, page_number) or (None, None) if not found.
        """
        # Remove file extension
        base_name = os.path.splitext(filename)[0]
        
        # Try to match known patterns
        patterns = [
            # Newspapers.com pattern: The_Post_Intelligencer_1891_04_03_8
            (r'^((?:The_)?[A-Za-z_]+)_\d{4}[-_]\d{2}[-_]\d{2}[-_](\d+)', 
             lambda m: (m.group(1).replace('_', ' '), m.group(2))),
            
            # GenealogyBank pattern: Daily_intelligencer_1891-04-03_9
            (r'^([A-Za-z_]+)_\d{4}-\d{2}-\d{2}_(\d+)',
             lambda m: (m.group(1).replace('_', ' '), m.group(2))),
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, base_name)
            if match:
                return formatter(match)
        
        return None, None

class FileProcessor:
    """Handles file operations and metadata extraction"""
    
    def __init__(self, intake_folder, preprocessed_folder, db_manager):
        self.intake_folder = intake_folder
        self.preprocessed_folder = preprocessed_folder
        self.db_manager = db_manager
        self.date_detector = DateDetector()
        self.source_detector = SourceDetector(db_manager)
        
    def copy_to_intake(self, source_paths):
        """
        Copy files to intake folder.
        Returns list of (success, source_path, dest_path, error_msg) tuples.
        """
        results = []
        for src_path in source_paths:
            try:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.intake_folder, filename)
                
                # Handle duplicates by adding suffix if needed
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest_path):
                        new_filename = f"{base}_{counter}{ext}"
                        dest_path = os.path.join(self.intake_folder, new_filename)
                        counter += 1
                
                shutil.copy2(src_path, dest_path)
                results.append((True, src_path, dest_path, None))
            except Exception as e:
                results.append((False, src_path, None, str(e)))
        
        return results
    
    def process_file(self, filepath):
        """
        Process a single file to extract metadata and standardize filename.
        Returns (success, metadata, new_filename) or (False, None, error_msg).
        """
        try:
            filename = os.path.basename(filepath)
            
            # Extract date
            date_str = self.date_detector.detect_date(filename)
            if not date_str:
                return False, None, "No valid date found"
            
            # Extract source and page
            source_name, page_num = self.source_detector.detect_source(filename)
            if not page_num:
                page_num = "0"
            
            # Build metadata
            metadata = {
                'date': date_str,
                'source': source_name or "Unknown",
                'page': page_num,
                'original_filename': filename
            }
            
            # Create standardized filename
            new_filename = f"{date_str}_{metadata['source']}_{metadata['page']}{os.path.splitext(filename)[1]}"
            
            return True, metadata, new_filename
            
        except Exception as e:
            return False, None, str(e)
    
    def move_to_preprocessed(self, filepath, new_filename):
        """
        Move file to preprocessed folder with new filename.
        Returns (success, new_path, error_msg).
        """
        try:
            new_path = os.path.join(self.preprocessed_folder, new_filename)
            
            # Handle duplicates
            if os.path.exists(new_path):
                base, ext = os.path.splitext(new_filename)
                counter = 1
                while os.path.exists(new_path):
                    test_filename = f"{base}_{counter}{ext}"
                    new_path = os.path.join(self.preprocessed_folder, test_filename)
                    counter += 1
            
            shutil.move(filepath, new_path)
            return True, new_path, None
            
        except Exception as e:
            return False, None, str(e)

class ResearchImportTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
        # Initialize paths
        self.current_project_folder = None
        self.intake_folder = None
        self.preprocessed_folder = None
        
        # Initialize file processor
        self.file_processor = None
        
        # Initialize UI
        self.initUI()
        
    def initUI(self):
        """Initialize the user interface"""
        layout = QHBoxLayout(self)
        
        # Create splitter for three panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Original files
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Middle panel - Controls
        middle_panel = self.create_middle_panel()
        splitter.addWidget(middle_panel)
        
        # Right panel - Processed files
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set initial sizes
        splitter.setSizes([300, 300, 300])
        
        layout.addWidget(splitter)
        
    def create_left_panel(self):
        """Create the left panel containing original files"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("Original Files")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # File list
        self.original_list = QListWidget()
        self.original_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.original_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_files_btn = QPushButton("Select Files")
        select_files_btn.clicked.connect(self.select_files)
        button_layout.addWidget(select_files_btn)
        
        select_folder_btn = QPushButton("Select Folder")
        select_folder_btn.clicked.connect(self.select_folder)
        button_layout.addWidget(select_folder_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(clear_btn)
        
        layout.addLayout(button_layout)
        
        return panel
        
    def create_middle_panel(self):
        """Create the middle panel containing controls"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("Processing Controls")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # Process buttons
        process_btn = QPushButton("Process Selected Files")
        process_btn.clicked.connect(self.process_files)
        layout.addWidget(process_btn)
        
        ai_btn = QPushButton("AI Assistance")
        ai_btn.clicked.connect(self.show_ai_dialog)
        layout.addWidget(ai_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        return panel
        
    def create_right_panel(self):
        """Create the right panel containing processed files"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("Processed Files")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # Processed files list
        self.processed_list = QListWidget()
        layout.addWidget(self.processed_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_processed_files)
        button_layout.addWidget(refresh_btn)
        
        revert_btn = QPushButton("Move Back")
        revert_btn.clicked.connect(self.move_back_to_intake)
        button_layout.addWidget(revert_btn)
        
        layout.addLayout(button_layout)
        
        return panel
    
    def set_project_info(self, project_folder):
        """Set up project paths and initialize file processor"""
        if not project_folder:
            return
            
        self.current_project_folder = project_folder
        self.intake_folder = os.path.join(project_folder, "Assets", "Intake-For_Preprocessing")
        self.preprocessed_folder = os.path.join(project_folder, "Assets", "preprocessed")
        
        # Ensure folders exist
        os.makedirs(self.intake_folder, exist_ok=True)
        os.makedirs(self.preprocessed_folder, exist_ok=True)
        
        # Initialize file processor
        self.file_processor = FileProcessor(
            self.intake_folder,
            self.preprocessed_folder,
            self.db_manager
        )
        
        # Refresh lists
        self.refresh_lists()
        
    def refresh_lists(self):
        """Refresh both file lists"""
        self.refresh_original_files()
        self.refresh_processed_files()
        
    def refresh_original_files(self):
        """Refresh the list of files in the intake folder"""
        self.original_list.clear()
        
        if not self.intake_folder or not os.path.exists(self.intake_folder):
            return
            
        for filename in os.listdir(self.intake_folder):
            if os.path.isfile(os.path.join(self.intake_folder, filename)):
                self.original_list.addItem(filename)
                
    def refresh_processed_files(self):
        """Refresh the list of files in the preprocessed folder"""
        self.processed_list.clear()
        
        if not self.preprocessed_folder or not os.path.exists(self.preprocessed_folder):
            return
            
        for filename in os.listdir(self.preprocessed_folder):
            filepath = os.path.join(self.preprocessed_folder, filename)
            if os.path.isfile(filepath):
                item = QListWidgetItem(filename)
                # Add tooltip showing full path
                item.setToolTip(filepath)
                self.processed_list.addItem(item)
                
    def select_files(self):
        """Open file dialog to select files to import"""
        if not self.intake_folder:
            QMessageBox.warning(self, "No Project", "Please open a project before importing files.")
            return
            
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Import",
            "",
            "Image Files (*.jpg *.jpeg *.png *.tif *.tiff);;PDF Files (*.pdf);;All Files (*.*)"
        )
        
        if files:
            self.import_files(files)
            
    def select_folder(self):
        """Open folder dialog to select folder to import"""
        if not self.intake_folder:
            QMessageBox.warning(self, "No Project", "Please open a project before importing files.")
            return
            
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Import",
            ""
        )
        
        if folder:
            files = []
            for root, _, filenames in os.walk(folder):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.pdf']:
                        files.append(os.path.join(root, filename))
            
            if files:
                self.import_files(files)
            else:
                QMessageBox.information(self, "No Files", "No supported files found in selected folder.")
                
    def import_files(self, source_paths):
        """Import files to the intake folder"""
        if not self.file_processor:
            return
            
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(source_paths))
        self.progress_bar.setValue(0)
        
        # Copy files
        results = self.file_processor.copy_to_intake(source_paths)
        
        # Process results
        success_count = 0
        error_messages = []
        
        for success, src_path, dest_path, error_msg in results:
            if success:
                success_count += 1
            else:
                error_messages.append(f"Failed to copy {os.path.basename(src_path)}: {error_msg}")
            self.progress_bar.setValue(self.progress_bar.value() + 1)
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Show results
        self.refresh_original_files()
        
        if error_messages:
            errors = "\n".join(error_messages)
            QMessageBox.warning(
                self,
                "Import Results",
                f"Successfully imported {success_count} files.\n\nErrors:\n{errors}"
            )
        else:
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {success_count} files."
            )
            
    def clear_selection(self):
        """Clear the selection in the original files list"""
        self.original_list.clearSelection()
        
    def process_files(self):
        """Process selected files from intake folder"""
        if not self.file_processor:
            return
            
        # Get selected files
        selected_items = self.original_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select files to process.")
            return
            
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(selected_items))
        self.progress_bar.setValue(0)
        
        success_count = 0
        error_messages = []
        
        for item in selected_items:
            filename = item.text()
            filepath = os.path.join(self.intake_folder, filename)
            
            # Process file to extract metadata and get new filename
            success, metadata, result = self.file_processor.process_file(filepath)
            
            if success:
                # Move file to preprocessed folder
                move_success, new_path, error = self.file_processor.move_to_preprocessed(filepath, result)
                if move_success:
                    success_count += 1
                else:
                    error_messages.append(f"Failed to move {filename}: {error}")
            else:
                error_messages.append(f"Failed to process {filename}: {result}")
                
            self.progress_bar.setValue(self.progress_bar.value() + 1)
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Refresh lists
        self.refresh_lists()
        
        # Show results
        if error_messages:
            errors = "\n".join(error_messages)
            QMessageBox.warning(
                self,
                "Processing Results",
                f"Successfully processed {success_count} files.\n\nErrors:\n{errors}"
            )
        else:
            QMessageBox.information(
                self,
                "Processing Complete",
                f"Successfully processed {success_count} files."
            )
            
    def move_back_to_intake(self):
        """Move selected files back to intake folder"""
        selected_items = self.processed_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select files to move back.")
            return
            
        for item in selected_items:
            filename = item.text()
            src_path = os.path.join(self.preprocessed_folder, filename)
            dest_path = os.path.join(self.intake_folder, filename)
            
            try:
                # Handle potential naming conflicts
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest_path):
                        new_filename = f"{base}_{counter}{ext}"
                        dest_path = os.path.join(self.intake_folder, new_filename)
                        counter += 1
                        
                shutil.move(src_path, dest_path)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to move {filename} back to intake folder:\n{str(e)}"
                )
                
        # Refresh lists
        self.refresh_lists()
        
    def show_ai_dialog(self):
        """Show dialog for AI assistance"""
        # Get selected files
        selected_items = self.original_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select files for AI analysis.")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("AI Assistance")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Selected files
        files_label = QLabel(f"Selected Files: {len(selected_items)}")
        layout.addWidget(files_label)
        
        # Instructions
        instructions = QLabel("Ask AI for help with analyzing these files:")
        layout.addWidget(instructions)
        
        # Query input
        query_edit = QTextEdit()
        query_edit.setPlaceholderText("Type your question here...")
        layout.addWidget(query_edit)
        
        # Response area
        response_label = QLabel("AI Response:")
        layout.addWidget(response_label)
        
        response_text = QTextEdit()
        response_text.setReadOnly(True)
        layout.addWidget(response_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        analyze_btn = QPushButton("Analyze Files")
        analyze_btn.clicked.connect(lambda: self.analyze_with_ai(
            selected_items,
            query_edit.toPlainText(),
            response_text
        ))
        button_layout.addWidget(analyze_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec_()
        
    def analyze_with_ai(self, items, query, response_widget):
        """
        Use AI to analyze selected files
        This is a placeholder - actual AI integration would go here
        """
        # TODO: Implement actual AI integration
        filenames = [item.text() for item in items]
        response = f"Analyzing {len(filenames)} files...\n\n"
        response += f"User Query: {query}\n\n"
        response += "This is a placeholder for AI analysis.\n"
        response += "When implemented, this will use the AI API to analyze the files."
        
        response_widget.setText(response)