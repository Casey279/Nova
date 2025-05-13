"""
Checkpoint system for resumable downloads from Chronicling America.

This module provides classes and functions for saving and loading checkpoint
information about ChroniclingAmerica downloads in progress. This allows
interrupted large downloads to be resumed later.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DownloadCheckpoint:
    """
    Class for managing download checkpoints.
    """
    
    def __init__(self, base_dir: str):
        """
        Initialize the checkpoint manager.
        
        Args:
            base_dir: Base directory for saving checkpoint files
        """
        self.base_dir = base_dir
        self.checkpoint_dir = os.path.join(base_dir, "checkpoints")
        
        # Create checkpoint directory if it doesn't exist
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def generate_checkpoint_id(self, search_params: Dict[str, Any]) -> str:
        """
        Generate a unique ID for a checkpoint based on search parameters.
        
        Args:
            search_params: Dictionary of search parameters
            
        Returns:
            A unique string identifier
        """
        # Create a deterministic identifier based on search parameters
        components = []
        
        # Include key parameters in the ID
        lccn = search_params.get('lccn', '')
        if lccn:
            components.append(f"lccn_{lccn}")
        
        state = search_params.get('state', '')
        if state:
            components.append(f"state_{state}")
        
        date_start = search_params.get('date_start', '')
        date_end = search_params.get('date_end', '')
        if date_start and date_end:
            components.append(f"dates_{date_start}_to_{date_end}")
        
        keywords = search_params.get('keywords', '')
        if keywords:
            # Use only the first few words for the ID, sanitized
            safe_keywords = "".join(c if c.isalnum() else "_" for c in keywords[:30])
            components.append(f"kw_{safe_keywords}")
        
        # Add a timestamp part for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        components.append(timestamp)
        
        # Join with underscores and create a safe filename
        return "_".join(components)
    
    def get_checkpoint_path(self, checkpoint_id: str) -> str:
        """
        Get the full path to a checkpoint file.
        
        Args:
            checkpoint_id: Checkpoint identifier
            
        Returns:
            Full path to the checkpoint file
        """
        return os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")
    
    def save_checkpoint(self, 
                      checkpoint_id: str, 
                      search_params: Dict[str, Any],
                      completed_pages: List[Dict[str, Any]],
                      pending_pages: List[Dict[str, Any]],
                      download_formats: List[str],
                      max_pages: int = 100) -> bool:
        """
        Save a download checkpoint.
        
        Args:
            checkpoint_id: Unique checkpoint identifier
            search_params: Original search parameters
            completed_pages: List of completed page downloads
            pending_pages: List of pages yet to be downloaded
            download_formats: List of formats to download
            max_pages: Maximum pages to download
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create checkpoint data
            checkpoint_data = {
                'checkpoint_id': checkpoint_id,
                'search_params': search_params,
                'completed_pages': completed_pages,
                'pending_pages': pending_pages,
                'download_formats': download_formats,
                'max_pages': max_pages,
                'timestamp': datetime.now().isoformat(),
                'total_pages': len(completed_pages) + len(pending_pages),
                'completed_count': len(completed_pages)
            }
            
            # Save to file
            checkpoint_path = self.get_checkpoint_path(checkpoint_id)
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2)
                
            logger.info(f"Saved checkpoint to {checkpoint_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {str(e)}")
            return False
    
    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a download checkpoint.
        
        Args:
            checkpoint_id: Checkpoint identifier
            
        Returns:
            Checkpoint data dictionary if successful, None otherwise
        """
        try:
            checkpoint_path = self.get_checkpoint_path(checkpoint_id)
            
            if not os.path.exists(checkpoint_path):
                logger.warning(f"Checkpoint file not found: {checkpoint_path}")
                return None
            
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
                
            logger.info(f"Loaded checkpoint from {checkpoint_path}")
            return checkpoint_data
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {str(e)}")
            return None
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint file.
        
        Args:
            checkpoint_id: Checkpoint identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            checkpoint_path = self.get_checkpoint_path(checkpoint_id)
            
            if os.path.exists(checkpoint_path):
                os.remove(checkpoint_path)
                logger.info(f"Deleted checkpoint: {checkpoint_path}")
                return True
            else:
                logger.warning(f"Checkpoint not found: {checkpoint_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {str(e)}")
            return False
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        List all available checkpoints.
        
        Returns:
            List of dictionaries with checkpoint information
        """
        checkpoints = []
        
        try:
            # Get all JSON files in the checkpoint directory
            for filename in os.listdir(self.checkpoint_dir):
                if not filename.endswith('.json'):
                    continue
                
                checkpoint_id = os.path.splitext(filename)[0]
                checkpoint_path = os.path.join(self.checkpoint_dir, filename)
                
                try:
                    # Read basic info from the checkpoint file
                    with open(checkpoint_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Extract key information for display
                    checkpoint_info = {
                        'id': checkpoint_id,
                        'timestamp': data.get('timestamp', ''),
                        'total_pages': data.get('total_pages', 0),
                        'completed_count': data.get('completed_count', 0),
                        'percent_complete': round(data.get('completed_count', 0) / max(data.get('total_pages', 1), 1) * 100, 1),
                        'search_params': data.get('search_params', {}),
                        'formats': data.get('download_formats', []),
                        'path': checkpoint_path
                    }
                    
                    checkpoints.append(checkpoint_info)
                except Exception as e:
                    logger.warning(f"Error reading checkpoint {filename}: {str(e)}")
            
            # Sort by timestamp (newest first)
            checkpoints.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
        except Exception as e:
            logger.error(f"Error listing checkpoints: {str(e)}")
        
        return checkpoints
    
    def format_checkpoint_info(self, checkpoint_info: Dict[str, Any]) -> str:
        """
        Format checkpoint information for display.
        
        Args:
            checkpoint_info: Checkpoint information dictionary
            
        Returns:
            Formatted string for display
        """
        # Extract search parameters
        search_params = checkpoint_info.get('search_params', {})
        lccn = search_params.get('lccn', '')
        state = search_params.get('state', '')
        date_start = search_params.get('date_start', '')
        date_end = search_params.get('date_end', '')
        keywords = search_params.get('keywords', '')
        
        # Format timestamp
        timestamp_str = checkpoint_info.get('timestamp', '')
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        except:
            formatted_time = timestamp_str
        
        # Create display text
        display_text = f"Download checkpoint from {formatted_time}\n"
        
        # Add search parameters
        if lccn:
            display_text += f"LCCN: {lccn}\n"
        if state:
            display_text += f"State: {state}\n"
        if date_start and date_end:
            display_text += f"Dates: {date_start} to {date_end}\n"
        if keywords:
            display_text += f"Keywords: {keywords}\n"
        
        # Add progress information
        total = checkpoint_info.get('total_pages', 0)
        completed = checkpoint_info.get('completed_count', 0)
        percent = checkpoint_info.get('percent_complete', 0)
        
        display_text += f"Progress: {completed} of {total} pages ({percent}% complete)\n"
        display_text += f"Formats: {', '.join(checkpoint_info.get('formats', []))}"
        
        return display_text