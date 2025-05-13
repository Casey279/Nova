"""
Dialog for managing download checkpoints.

This module provides a dialog for viewing, resuming, and deleting
download checkpoints from the ChroniclingAmerica downloader.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QListWidgetItem, QPushButton, QLabel, QMessageBox,
                            QTextEdit, QGroupBox, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal, QSize

from .download_checkpoint import DownloadCheckpoint

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CheckpointDialog(QDialog):
    """
    Dialog for managing download checkpoints.
    """
    
    # Signal emitted when user chooses to resume a checkpoint
    resume_checkpoint = pyqtSignal(str)
    
    def __init__(self, base_dir: str, parent=None):
        """
        Initialize the checkpoint dialog.
        
        Args:
            base_dir: Base directory where checkpoints are stored
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.base_dir = base_dir
        self.checkpoint_manager = DownloadCheckpoint(base_dir)
        self.selected_checkpoint = None
        
        self.setWindowTitle("Download Checkpoints")
        self.resize(800, 500)
        
        self.setup_ui()
        self.load_checkpoints()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Add title and explanation
        title_label = QLabel("<h2>Resume Interrupted Downloads</h2>")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        info_label = QLabel(
            "The following downloads were interrupted and can be resumed. "
            "Select a checkpoint to view details and resume downloading."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Create splitter for list and details
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Checkpoint list
        list_group = QGroupBox("Available Checkpoints")
        list_layout = QVBoxLayout(list_group)
        
        self.checkpoint_list = QListWidget()
        self.checkpoint_list.setAlternatingRowColors(True)
        self.checkpoint_list.currentItemChanged.connect(self.on_checkpoint_selected)
        list_layout.addWidget(self.checkpoint_list)
        
        # Progress count label
        self.progress_label = QLabel("No checkpoints available")
        list_layout.addWidget(self.progress_label)
        
        splitter.addWidget(list_group)
        
        # Checkpoint details
        details_group = QGroupBox("Checkpoint Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        splitter.addWidget(details_group)
        
        # Set initial splitter sizes
        splitter.setSizes([300, 500])
        
        # Button row
        button_layout = QHBoxLayout()
        
        self.resume_button = QPushButton("Resume Download")
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self.on_resume_clicked)
        
        self.delete_button = QPushButton("Delete Checkpoint")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.on_delete_clicked)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_checkpoints)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.resume_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def load_checkpoints(self):
        """Load and display available checkpoints."""
        self.checkpoint_list.clear()
        self.details_text.clear()
        self.selected_checkpoint = None
        self.resume_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        
        checkpoints = self.checkpoint_manager.list_checkpoints()
        
        if not checkpoints:
            self.progress_label.setText("No checkpoints available")
            item = QListWidgetItem("No checkpoints available")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.checkpoint_list.addItem(item)
            return
        
        self.progress_label.setText(f"Found {len(checkpoints)} checkpoint(s)")
        
        for checkpoint in checkpoints:
            # Create a descriptive label for the checkpoint
            label = self._create_checkpoint_label(checkpoint)
            
            # Create list item
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, checkpoint)
            
            # Add progress indicator based on percentage complete
            percent = checkpoint.get('percent_complete', 0)
            if percent < 25:
                status = "⏳ Just started"
            elif percent < 50:
                status = "⏳ In progress"
            elif percent < 75:
                status = "⏳ More than halfway"
            elif percent < 100:
                status = "⏳ Almost complete"
            else:
                status = "✅ Complete"
                
            item.setToolTip(f"{status} - {percent}% complete")
            
            # Add to list
            self.checkpoint_list.addItem(item)
    
    def _create_checkpoint_label(self, checkpoint: Dict[str, Any]) -> str:
        """
        Create a descriptive label for a checkpoint.
        
        Args:
            checkpoint: Checkpoint information
            
        Returns:
            Formatted string for display in the list
        """
        # Extract basic info
        timestamp = checkpoint.get('timestamp', '')
        try:
            timestamp_obj = datetime.fromisoformat(timestamp)
            time_str = timestamp_obj.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = timestamp
        
        # Get search parameters
        search_params = checkpoint.get('search_params', {})
        lccn = search_params.get('lccn', '')
        state = search_params.get('state', '')
        
        # Create description based on what's available
        description = f"Download from {time_str}"
        if lccn:
            description += f" - LCCN: {lccn}"
        elif state:
            description += f" - State: {state}"
        
        # Add progress info
        total = checkpoint.get('total_pages', 0)
        completed = checkpoint.get('completed_count', 0)
        percent = checkpoint.get('percent_complete', 0)
        
        return f"{description} ({completed}/{total} pages - {percent}% complete)"
    
    def on_checkpoint_selected(self, current, previous):
        """
        Handle checkpoint selection.
        
        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if not current:
            self.selected_checkpoint = None
            self.details_text.clear()
            self.resume_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return
        
        # Get checkpoint data
        checkpoint = current.data(Qt.UserRole)
        self.selected_checkpoint = checkpoint
        
        # Show details
        if checkpoint:
            # Format details for display
            details = self.checkpoint_manager.format_checkpoint_info(checkpoint)
            self.details_text.setText(details)
            
            # Enable buttons
            self.resume_button.setEnabled(True)
            self.delete_button.setEnabled(True)
    
    def on_resume_clicked(self):
        """Handle resume button click."""
        if not self.selected_checkpoint:
            return
        
        # Get checkpoint ID
        checkpoint_id = self.selected_checkpoint.get('id')
        if not checkpoint_id:
            QMessageBox.warning(
                self,
                "Invalid Checkpoint",
                "The selected checkpoint is invalid or corrupted."
            )
            return
        
        # Emit signal with checkpoint ID
        self.resume_checkpoint.emit(checkpoint_id)
        
        # Close dialog
        self.accept()
    
    def on_delete_clicked(self):
        """Handle delete button click."""
        if not self.selected_checkpoint:
            return
        
        # Get checkpoint ID
        checkpoint_id = self.selected_checkpoint.get('id')
        if not checkpoint_id:
            QMessageBox.warning(
                self,
                "Invalid Checkpoint",
                "The selected checkpoint is invalid or corrupted."
            )
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete this checkpoint?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Delete checkpoint
        success = self.checkpoint_manager.delete_checkpoint(checkpoint_id)
        
        if success:
            # Refresh list
            self.load_checkpoints()
            
            QMessageBox.information(
                self,
                "Checkpoint Deleted",
                "The checkpoint was successfully deleted."
            )
        else:
            QMessageBox.warning(
                self,
                "Deletion Failed",
                "Failed to delete the checkpoint. The file may be in use or have been moved."
            )