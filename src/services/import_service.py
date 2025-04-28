# File: import_service.py

import os
import re
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional, BinaryIO
from datetime import datetime
from PyPDF2 import PdfReader
import docx
import zipfile
from io import BytesIO

from .base_service import BaseService, DatabaseError
from .source_service import SourceService

class ImportService(BaseService):
    """
    Service for handling file import operations.
    Provides methods for importing various file types and processing them.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the import service.
        
        Args:
            db_path: Path to the database
        """
        super().__init__(db_path)
        self.source_service = SourceService(db_path)
    
    def import_file(self, file_path: str) -> Dict[str, Any]:
        """
        Import a file into the database.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with import results
            
        Raises:
            DatabaseError: If import fails
            ValueError: If file type is not supported
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # Parse file metadata from filename
        metadata = self.parse_file_name(file_name)
        
        # Extract content based on file type
        if file_ext == '.txt':
            content = self.extract_text_from_txt(file_path)
        elif file_ext == '.pdf':
            content = self.extract_text_from_pdf(file_path)
        elif file_ext in ['.doc', '.docx']:
            content = self.extract_text_from_docx(file_path)
        elif file_ext in ['.csv', '.xls', '.xlsx']:
            content = self.extract_text_from_spreadsheet(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        # Add source to database
        metadata['content'] = content
        source_id = self.source_service.create_source(metadata)
        
        return {
            'source_id': source_id,
            'file_name': file_name,
            'metadata': metadata,
            'content_length': len(content)
        }
    
    def import_multiple_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Import multiple files into the database.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            List of dictionaries with import results
            
        Raises:
            DatabaseError: If import fails
        """
        results = []
        errors = []
        
        for file_path in file_paths:
            try:
                result = self.import_file(file_path)
                results.append(result)
            except Exception as e:
                errors.append({
                    'file_path': file_path,
                    'error': str(e)
                })
        
        return {
            'successful': results,
            'failed': errors
        }
    
    def parse_file_name(self, file_name: str) -> Dict[str, Any]:
        """
        Parse file name to extract metadata.
        
        Args:
            file_name: Name of the file
            
        Returns:
            Dictionary with extracted metadata
        """
        # Strip extension
        base_name = os.path.splitext(file_name)[0]
        
        # Default metadata
        metadata = {
            'title': base_name,
            'author': '',
            'source_type': 'document',
            'publication_date': None,
            'url': ''
        }
        
        # Advanced pattern matching for extracting metadata
        
        # Try to extract date using various patterns
        date_patterns = [
            # YYYY-MM-DD
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
            # MM-DD-YYYY
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"),
            # YYYY.MM.DD
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', lambda m: f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
            # DD.MM.YYYY
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', lambda m: f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"),
            # Just year (YYYY)
            (r'\b(\d{4})\b', lambda m: f"{int(m.group(1)):04d}-01-01")
        ]
        
        for pattern, date_formatter in date_patterns:
            match = re.search(pattern, base_name)
            if match:
                try:
                    date_str = date_formatter(match)
                    metadata['publication_date'] = date_str
                    
                    # Remove date from title
                    title = re.sub(pattern, '', base_name).strip('_- ')
                    if title:
                        metadata['title'] = title
                    
                    break
                except (ValueError, IndexError):
                    continue
        
        # Try to extract source/author if it's in brackets or parentheses
        source_patterns = [
            (r'\[([^\]]+)\]', 'source'),  # [Source]
            (r'\(([^\)]+)\)', 'source'),  # (Source)
            (r'by\s+([A-Za-z\s\.]+)', 'author'),  # by Author Name
            (r'from\s+([A-Za-z\s\.]+)', 'source')  # from Source Name
        ]
        
        for pattern, field in source_patterns:
            match = re.search(pattern, base_name)
            if match:
                metadata[field] = match.group(1).strip()
                
                # Remove matched text from title
                title = re.sub(pattern, '', metadata['title']).strip('_- ')
                if title:
                    metadata['title'] = title
        
        # Extract document type if present
        type_patterns = [
            (r'\b(article|book|letter|report|memo|newspaper|journal|diary|interview|transcript)\b', 'source_type')
        ]
        
        for pattern, field in type_patterns:
            match = re.search(pattern, base_name, re.IGNORECASE)
            if match:
                metadata[field] = match.group(1).lower()
                
                # Remove document type from title
                title = re.sub(pattern, '', metadata['title'], flags=re.IGNORECASE).strip('_- ')
                if title:
                    metadata['title'] = title
        
        return metadata
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """
        Extract text from a .txt file.
        
        Args:
            file_path: Path to the .txt file
            
        Returns:
            Extracted text
            
        Raises:
            IOError: If file cannot be read
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try different encodings if utf-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                raise IOError(f"Failed to read text file: {str(e)}")
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from a .pdf file.
        
        Args:
            file_path: Path to the .pdf file
            
        Returns:
            Extracted text
            
        Raises:
            IOError: If file cannot be read
        """
        try:
            reader = PdfReader(file_path)
            text = ""
            
            for page in reader.pages:
                text += page.extract_text() + "\n\n"
            
            return text
        except Exception as e:
            raise IOError(f"Failed to read PDF file: {str(e)}")
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """
        Extract text from a .docx file.
        
        Args:
            file_path: Path to the .docx file
            
        Returns:
            Extracted text
            
        Raises:
            IOError: If file cannot be read
        """
        try:
            doc = docx.Document(file_path)
            text = ""
            
            for para in doc.paragraphs:
                text += para.text + "\n"
            
            return text
        except Exception as e:
            raise IOError(f"Failed to read Word file: {str(e)}")
    
    def extract_text_from_spreadsheet(self, file_path: str) -> str:
        """
        Extract text from a spreadsheet file.
        
        Args:
            file_path: Path to the spreadsheet file
            
        Returns:
            Extracted text as formatted string
            
        Raises:
            IOError: If file cannot be read
        """
        try:
            df = pd.read_excel(file_path) if file_path.endswith(('.xls', '.xlsx')) else pd.read_csv(file_path)
            
            # Convert DataFrame to a formatted string
            text = df.to_string(index=False)
            
            # Add metadata about columns
            column_info = "Columns: " + ", ".join(df.columns.tolist())
            
            return column_info + "\n\n" + text
        except Exception as e:
            raise IOError(f"Failed to read spreadsheet file: {str(e)}")
    
    def get_file_mime_type(self, file_path: str) -> str:
        """
        Get the MIME type of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            MIME type string
        """
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"