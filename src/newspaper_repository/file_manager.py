# File: file_manager.py

import os
import shutil
import datetime
import hashlib
import re
from pathlib import Path
from typing import Optional, Tuple

class FileManager:
    """
    Manages the organization and storage of newspaper repository files.
    
    Handles storage of:
    - Original newspaper page images
    - Processed page images
    - Article clip images
    - OCR results (text and HOCR)
    
    Maintains a structured directory hierarchy that aligns with database records.
    """
    
    # Standard directory names
    ORIGINAL_DIR = "original"
    PROCESSED_DIR = "processed"
    CLIPS_DIR = "article_clips"
    OCR_DIR = "ocr_results"
    TEXT_DIR = "text"
    HOCR_DIR = "hocr"
    
    def __init__(self, base_dir: str):
        """
        Initialize the file manager.
        
        Args:
            base_dir (str): Base directory for the newspaper repository
        """
        self.base_dir = os.path.abspath(base_dir)
        self.create_directory_structure()

    def create_directory_structure(self) -> None:
        """Create the necessary directory structure for the repository."""
        # Create main directories
        for dir_name in [self.ORIGINAL_DIR, self.PROCESSED_DIR, self.CLIPS_DIR, self.OCR_DIR]:
            full_path = os.path.join(self.base_dir, dir_name)
            os.makedirs(full_path, exist_ok=True)
            
        # Create OCR subdirectories
        for ocr_type in [self.TEXT_DIR, self.HOCR_DIR]:
            full_path = os.path.join(self.base_dir, self.OCR_DIR, ocr_type)
            os.makedirs(full_path, exist_ok=True)
            
        # Create directories for sources
        for source_dir in ["chroniclingamerica", "newspapers_com", "other"]:
            # For original files
            os.makedirs(os.path.join(self.base_dir, self.ORIGINAL_DIR, source_dir), exist_ok=True)
            # For processed files
            os.makedirs(os.path.join(self.base_dir, self.PROCESSED_DIR, source_dir), exist_ok=True)
            
        print(f"Created directory structure under {self.base_dir}")

    def get_source_directory(self, origin: str) -> str:
        """
        Convert origin string to standardized directory name.
        
        Args:
            origin (str): Origin source ('chroniclingamerica', 'newspapers.com', 'other')
            
        Returns:
            str: Standardized directory name
        """
        origin = origin.lower()
        if origin == "newspapers.com":
            return "newspapers_com"
        elif origin == "chroniclingamerica":
            return "chroniclingamerica"
        else:
            return "other"

    def generate_path_components(self, source_name: str, publication_date: str) -> Tuple[str, str, str]:
        """
        Generate path components based on source name and publication date.
        
        Args:
            source_name (str): Name of the newspaper source
            publication_date (str): Publication date in YYYY-MM-DD format
            
        Returns:
            Tuple[str, str, str]: Year, month, and sanitized source name
        """
        # Extract year and month from publication date
        if publication_date and len(publication_date) >= 10:
            year = publication_date[:4]
            month = publication_date[5:7]
        else:
            # Use current date as fallback
            now = datetime.datetime.now()
            year = str(now.year)
            month = str(now.month).zfill(2)
            
        # Sanitize source name for directory
        sanitized_source = re.sub(r'[^\w\s-]', '', source_name).strip().lower()
        sanitized_source = re.sub(r'[-\s]+', '_', sanitized_source)
        
        return year, month, sanitized_source

    def generate_file_path(self, directory_type: str, origin: str, source_name: str, 
                          publication_date: str, page_number: int, filename: str, 
                          extension: Optional[str] = None) -> str:
        """
        Generate a standardized file path.
        
        Args:
            directory_type (str): Type of directory ('original', 'processed', etc.)
            origin (str): Origin source
            source_name (str): Name of the newspaper source
            publication_date (str): Publication date in YYYY-MM-DD format
            page_number (int): Page number
            filename (str): Original filename
            extension (str, optional): File extension to override
            
        Returns:
            str: Full file path
        """
        source_dir = self.get_source_directory(origin)
        year, month, sanitized_source = self.generate_path_components(source_name, publication_date)
        
        # Create nested directory structure
        nested_path = os.path.join(
            self.base_dir,
            directory_type,
            source_dir,
            year,
            month,
            sanitized_source
        )
        
        # Create directory if it doesn't exist
        os.makedirs(nested_path, exist_ok=True)
        
        # Generate filename
        if extension:
            # Replace extension if provided
            base_name = os.path.splitext(os.path.basename(filename))[0]
            new_filename = f"{base_name}_{page_number:04d}.{extension}"
        else:
            # Keep original extension
            new_filename = f"{os.path.splitext(os.path.basename(filename))[0]}_{page_number:04d}{os.path.splitext(filename)[1]}"
            
        return os.path.join(nested_path, new_filename)

    def save_original_page(self, source_file_path: str, origin: str, source_name: str,
                          publication_date: str, page_number: int) -> str:
        """
        Save an original newspaper page file.
        
        Args:
            source_file_path (str): Path to the source file
            origin (str): Origin source
            source_name (str): Name of the newspaper source
            publication_date (str): Publication date in YYYY-MM-DD format
            page_number (int): Page number
            
        Returns:
            str: Path where the file was saved, or None if failed
        """
        try:
            if not os.path.exists(source_file_path):
                print(f"Source file not found: {source_file_path}")
                return None
                
            filename = os.path.basename(source_file_path)
            destination_path = self.generate_file_path(
                self.ORIGINAL_DIR, origin, source_name, publication_date, page_number, filename
            )
            
            # Copy the file
            shutil.copy2(source_file_path, destination_path)
            print(f"Saved original page to {destination_path}")
            return destination_path
            
        except Exception as e:
            print(f"Error saving original page: {e}")
            return None

    def save_processed_page(self, source_file_path: str, origin: str, source_name: str,
                           publication_date: str, page_number: int, extension: str = "jpg") -> str:
        """
        Save a processed newspaper page file.
        
        Args:
            source_file_path (str): Path to the processed file
            origin (str): Origin source
            source_name (str): Name of the newspaper source
            publication_date (str): Publication date in YYYY-MM-DD format
            page_number (int): Page number
            extension (str, optional): File extension to use
            
        Returns:
            str: Path where the file was saved, or None if failed
        """
        try:
            if not os.path.exists(source_file_path):
                print(f"Source file not found: {source_file_path}")
                return None
                
            filename = os.path.basename(source_file_path)
            destination_path = self.generate_file_path(
                self.PROCESSED_DIR, origin, source_name, publication_date, page_number, filename, extension
            )
            
            # Copy the file
            shutil.copy2(source_file_path, destination_path)
            print(f"Saved processed page to {destination_path}")
            return destination_path
            
        except Exception as e:
            print(f"Error saving processed page: {e}")
            return None

    def save_article_clip(self, source_file_path: str, page_id: int, segment_id: int, 
                         source_name: str, publication_date: str, extension: str = "jpg") -> str:
        """
        Save an article clip image.
        
        Args:
            source_file_path (str): Path to the clip image
            page_id (int): Database ID of the page
            segment_id (int): Database ID of the article segment
            source_name (str): Name of the newspaper source
            publication_date (str): Publication date in YYYY-MM-DD format
            extension (str, optional): File extension to use
            
        Returns:
            str: Path where the file was saved, or None if failed
        """
        try:
            if not os.path.exists(source_file_path):
                print(f"Source file not found: {source_file_path}")
                return None
                
            year, month, sanitized_source = self.generate_path_components(source_name, publication_date)
            
            # Create nested directory structure
            nested_path = os.path.join(
                self.base_dir,
                self.CLIPS_DIR,
                year,
                month,
                sanitized_source
            )
            
            # Create directory if it doesn't exist
            os.makedirs(nested_path, exist_ok=True)
            
            # Generate filename with page_id and segment_id
            filename = f"page_{page_id}_segment_{segment_id}.{extension}"
            destination_path = os.path.join(nested_path, filename)
            
            # Copy the file
            shutil.copy2(source_file_path, destination_path)
            print(f"Saved article clip to {destination_path}")
            return destination_path
            
        except Exception as e:
            print(f"Error saving article clip: {e}")
            return None

    def save_ocr_text(self, text_content: str, page_id: int, segment_id: Optional[int] = None) -> str:
        """
        Save OCR text result.
        
        Args:
            text_content (str): OCR text content
            page_id (int): Database ID of the page
            segment_id (int, optional): Database ID of the article segment
            
        Returns:
            str: Path where the file was saved, or None if failed
        """
        try:
            # Create nested directory structure
            nested_path = os.path.join(
                self.base_dir,
                self.OCR_DIR,
                self.TEXT_DIR
            )
            
            # Create directory if it doesn't exist
            os.makedirs(nested_path, exist_ok=True)
            
            # Generate filename based on whether it's for a page or segment
            if segment_id:
                filename = f"page_{page_id}_segment_{segment_id}.txt"
            else:
                filename = f"page_{page_id}.txt"
                
            destination_path = os.path.join(nested_path, filename)
            
            # Write the content to file
            with open(destination_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
                
            print(f"Saved OCR text to {destination_path}")
            return destination_path
            
        except Exception as e:
            print(f"Error saving OCR text: {e}")
            return None

    def save_hocr_content(self, hocr_content: str, page_id: int, segment_id: Optional[int] = None) -> str:
        """
        Save HOCR content result.
        
        Args:
            hocr_content (str): HOCR content
            page_id (int): Database ID of the page
            segment_id (int, optional): Database ID of the article segment
            
        Returns:
            str: Path where the file was saved, or None if failed
        """
        try:
            # Create nested directory structure
            nested_path = os.path.join(
                self.base_dir,
                self.OCR_DIR,
                self.HOCR_DIR
            )
            
            # Create directory if it doesn't exist
            os.makedirs(nested_path, exist_ok=True)
            
            # Generate filename based on whether it's for a page or segment
            if segment_id:
                filename = f"page_{page_id}_segment_{segment_id}.hocr"
            else:
                filename = f"page_{page_id}.hocr"
                
            destination_path = os.path.join(nested_path, filename)
            
            # Write the content to file
            with open(destination_path, 'w', encoding='utf-8') as f:
                f.write(hocr_content)
                
            print(f"Saved HOCR content to {destination_path}")
            return destination_path
            
        except Exception as e:
            print(f"Error saving HOCR content: {e}")
            return None

    def generate_temp_path(self, original_filename: str) -> str:
        """
        Generate a temporary file path for processing.
        
        Args:
            original_filename (str): Original filename
            
        Returns:
            str: Temporary file path
        """
        temp_dir = os.path.join(self.base_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate unique name with timestamp and hash
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename_hash = hashlib.md5(original_filename.encode()).hexdigest()[:8]
        
        # Keep original extension
        _, ext = os.path.splitext(original_filename)
        if not ext:
            ext = ".tmp"
            
        temp_filename = f"temp_{timestamp}_{filename_hash}{ext}"
        return os.path.join(temp_dir, temp_filename)

    def cleanup_temp_files(self, older_than_hours: int = 24) -> None:
        """
        Clean up temporary files older than specified hours.
        
        Args:
            older_than_hours (int): Hours threshold for deletion
        """
        temp_dir = os.path.join(self.base_dir, "temp")
        if not os.path.exists(temp_dir):
            return
            
        now = datetime.datetime.now()
        cutoff = now - datetime.timedelta(hours=older_than_hours)
        
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < cutoff:
                    try:
                        os.remove(file_path)
                        print(f"Removed old temp file: {file_path}")
                    except Exception as e:
                        print(f"Error removing temp file {file_path}: {e}")

    def get_page_ocr_text_path(self, page_id: int) -> str:
        """
        Get the path to a page's OCR text file.
        
        Args:
            page_id (int): Database ID of the page
            
        Returns:
            str: Path to the OCR text file
        """
        path = os.path.join(
            self.base_dir,
            self.OCR_DIR,
            self.TEXT_DIR,
            f"page_{page_id}.txt"
        )
        return path if os.path.exists(path) else None

    def get_segment_ocr_text_path(self, page_id: int, segment_id: int) -> str:
        """
        Get the path to a segment's OCR text file.
        
        Args:
            page_id (int): Database ID of the page
            segment_id (int): Database ID of the article segment
            
        Returns:
            str: Path to the OCR text file
        """
        path = os.path.join(
            self.base_dir,
            self.OCR_DIR,
            self.TEXT_DIR,
            f"page_{page_id}_segment_{segment_id}.txt"
        )
        return path if os.path.exists(path) else None

    def get_page_hocr_path(self, page_id: int) -> str:
        """
        Get the path to a page's HOCR file.
        
        Args:
            page_id (int): Database ID of the page
            
        Returns:
            str: Path to the HOCR file
        """
        path = os.path.join(
            self.base_dir,
            self.OCR_DIR,
            self.HOCR_DIR,
            f"page_{page_id}.hocr"
        )
        return path if os.path.exists(path) else None

    def get_segment_hocr_path(self, page_id: int, segment_id: int) -> str:
        """
        Get the path to a segment's HOCR file.
        
        Args:
            page_id (int): Database ID of the page
            segment_id (int): Database ID of the article segment
            
        Returns:
            str: Path to the HOCR file
        """
        path = os.path.join(
            self.base_dir,
            self.OCR_DIR,
            self.HOCR_DIR,
            f"page_{page_id}_segment_{segment_id}.hocr"
        )
        return path if os.path.exists(path) else None

    def read_ocr_text(self, page_id: int, segment_id: Optional[int] = None) -> str:
        """
        Read OCR text content.
        
        Args:
            page_id (int): Database ID of the page
            segment_id (int, optional): Database ID of the article segment
            
        Returns:
            str: Text content or None if file not found
        """
        try:
            if segment_id:
                path = self.get_segment_ocr_text_path(page_id, segment_id)
            else:
                path = self.get_page_ocr_text_path(page_id)
                
            if not path:
                return None
                
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            print(f"Error reading OCR text: {e}")
            return None

    def read_hocr_content(self, page_id: int, segment_id: Optional[int] = None) -> str:
        """
        Read HOCR content.
        
        Args:
            page_id (int): Database ID of the page
            segment_id (int, optional): Database ID of the article segment
            
        Returns:
            str: HOCR content or None if file not found
        """
        try:
            if segment_id:
                path = self.get_segment_hocr_path(page_id, segment_id)
            else:
                path = self.get_page_hocr_path(page_id)
                
            if not path:
                return None
                
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            print(f"Error reading HOCR content: {e}")
            return None

    def copy_to_export_folder(self, source_path: str, export_folder: str, new_filename: Optional[str] = None) -> str:
        """
        Copy a file to an export folder.
        
        Args:
            source_path (str): Path to the source file
            export_folder (str): Path to the export folder
            new_filename (str, optional): New filename to use
            
        Returns:
            str: Path to the exported file, or None if failed
        """
        try:
            if not os.path.exists(source_path):
                print(f"Source file not found: {source_path}")
                return None
                
            os.makedirs(export_folder, exist_ok=True)
            
            if new_filename:
                destination_path = os.path.join(export_folder, new_filename)
            else:
                destination_path = os.path.join(export_folder, os.path.basename(source_path))
                
            shutil.copy2(source_path, destination_path)
            return destination_path
            
        except Exception as e:
            print(f"Error copying to export folder: {e}")
            return None

    def list_files_by_date(self, date_str: str, file_type: str = "original") -> list:
        """
        List files for a specific date.
        
        Args:
            date_str (str): Date in YYYY-MM-DD format
            file_type (str): Type of files to list ('original', 'processed', 'clips')
            
        Returns:
            list: List of file paths
        """
        results = []
        
        try:
            if date_str and len(date_str) >= 10:
                year = date_str[:4]
                month = date_str[5:7]
                
                if file_type == "original":
                    base_path = os.path.join(self.base_dir, self.ORIGINAL_DIR)
                elif file_type == "processed":
                    base_path = os.path.join(self.base_dir, self.PROCESSED_DIR)
                elif file_type == "clips":
                    base_path = os.path.join(self.base_dir, self.CLIPS_DIR)
                else:
                    return []
                    
                # Look in all source directories
                for source_dir in ["chroniclingamerica", "newspapers_com", "other"]:
                    if file_type in ["original", "processed"]:
                        search_path = os.path.join(base_path, source_dir, year, month)
                    else:
                        search_path = os.path.join(base_path, year, month)
                        
                    if os.path.exists(search_path):
                        for root, _, files in os.walk(search_path):
                            for file in files:
                                results.append(os.path.join(root, file))
            
            return results
            
        except Exception as e:
            print(f"Error listing files by date: {e}")
            return []
            
    def delete_files_for_page(self, page_id: int) -> bool:
        """
        Delete all files associated with a page.
        
        Args:
            page_id (int): Database ID of the page
            
        Returns:
            bool: True if successful, False if any deletion failed
        """
        success = True
        
        # Delete OCR text
        text_path = self.get_page_ocr_text_path(page_id)
        if text_path and os.path.exists(text_path):
            try:
                os.remove(text_path)
            except Exception as e:
                print(f"Error deleting OCR text: {e}")
                success = False
                
        # Delete HOCR
        hocr_path = self.get_page_hocr_path(page_id)
        if hocr_path and os.path.exists(hocr_path):
            try:
                os.remove(hocr_path)
            except Exception as e:
                print(f"Error deleting HOCR file: {e}")
                success = False
                
        # Note: This doesn't delete original and processed images since they 
        # are organized by publication date and source rather than page_id
        # To delete those, you need to know the image paths from the database
        
        return success
        
    def delete_files_for_segment(self, page_id: int, segment_id: int) -> bool:
        """
        Delete all files associated with a segment.
        
        Args:
            page_id (int): Database ID of the page
            segment_id (int): Database ID of the segment
            
        Returns:
            bool: True if successful, False if any deletion failed
        """
        success = True
        
        # Delete OCR text
        text_path = self.get_segment_ocr_text_path(page_id, segment_id)
        if text_path and os.path.exists(text_path):
            try:
                os.remove(text_path)
            except Exception as e:
                print(f"Error deleting segment OCR text: {e}")
                success = False
                
        # Delete HOCR
        hocr_path = self.get_segment_hocr_path(page_id, segment_id)
        if hocr_path and os.path.exists(hocr_path):
            try:
                os.remove(hocr_path)
            except Exception as e:
                print(f"Error deleting segment HOCR file: {e}")
                success = False
                
        # Note: You'll need to handle article clip images separately,
        # as they require source_name and publication_date
        
        return success