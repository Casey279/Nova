# File: import_service.py

import os
import re
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional, BinaryIO, Union
from datetime import datetime, date
from PyPDF2 import PdfReader
import docx
import zipfile
from io import BytesIO

from .base_service import BaseService, DatabaseError
from .source_service import SourceService

# Import API clients conditionally to avoid circular imports
try:
    # Try to import the improved client first
    # Make sure Python path is correctly set up
    import importlib
    import sys
    import os

    # Ensure we can access the API module
    api_module_name = 'api.chronicling_america_improved'
    try:
        # Try the relative import first
        from ..api.chronicling_america_improved import ImprovedChroniclingAmericaClient as ChroniclingAmericaClient
        from ..api.chronicling_america_improved import PageMetadata
        USING_IMPROVED_CLIENT = True
        # Successfully imported ImprovedChroniclingAmericaClient via relative import
    except ImportError as e:
        # Relative import failed, trying absolute import
        # Try absolute import
        try:
            # Add parent dir to path if needed
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            from api.chronicling_america_improved import ImprovedChroniclingAmericaClient as ChroniclingAmericaClient
            from api.chronicling_america_improved import PageMetadata
            USING_IMPROVED_CLIENT = True
            # Successfully imported ImprovedChroniclingAmericaClient via absolute import
        except ImportError as e:
            # Absolute import of improved client failed, trying fallback
            # Fall back to the original client
            try:
                # Try relative import first
                from ..api.chronicling_america import ChroniclingAmericaClient, PageMetadata
                USING_IMPROVED_CLIENT = False
                # Successfully imported ChroniclingAmericaClient via relative import
            except ImportError as e:
                # Relative fallback import failed, trying absolute fallback
                try:
                    from api.chronicling_america import ChroniclingAmericaClient, PageMetadata
                    USING_IMPROVED_CLIENT = False
                    # Successfully imported ChroniclingAmericaClient via absolute import
                except ImportError as e:
                    # All import attempts failed
                    # Define placeholders for type hinting if no client is available
                    class PageMetadata:
                        pass
                    ChroniclingAmericaClient = None
except Exception as e:
    # Unexpected error during import
    # Define placeholders for type hinting if no client is available
    class PageMetadata:
        pass
    ChroniclingAmericaClient = None
    USING_IMPROVED_CLIENT = False

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
    
    def import_multiple_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Import multiple files into the database.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Dictionary with import results
            
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

    def check_if_newspaper_page_exists(self, lccn: str, issue_date: str, sequence: int) -> Optional[Dict[str, Any]]:
        """
        Check if a newspaper page already exists in the NewspaperPages table.

        Args:
            lccn: LCCN identifier
            issue_date: Issue date
            sequence: Page sequence number

        Returns:
            Page data as a dictionary if found, None otherwise
        """
        try:
            # Connect to the database
            conn, cursor = self.connect()

            # First check if the table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='NewspaperPages'")
            table_exists = cursor.fetchone() is not None
            if not table_exists:
                conn.close()
                return None

            # Check for an exact match in the NewspaperPages table by LCCN + issue_date + sequence
            # Make sure we're considering date formats correctly
            # First try exact match
            cursor.execute("""
                SELECT PageID, SourceID, LCCN, IssueDate, Sequence, ImagePath
                FROM NewspaperPages
                WHERE LCCN = ? AND IssueDate = ? AND Sequence = ?
            """, (lccn, issue_date, sequence))

            result = cursor.fetchone()

            if result:
                # Found an exact match
                conn.close()
                return {
                    'page_id': result[0],
                    'source_id': result[1],
                    'lccn': result[2],
                    'issue_date': result[3],
                    'sequence': result[4],
                    'image_path': result[5]
                }

            # Check all entries for this LCCN
            cursor.execute("SELECT PageID, IssueDate, Sequence FROM NewspaperPages WHERE LCCN = ?", (lccn,))
            all_pages = cursor.fetchall()


            conn.close()
            return None
        except Exception as e:
            print(f"Error checking if newspaper page exists: {str(e)}")
            return None

    def check_if_source_exists(self, source_name: str, lccn: str = None, sequence: int = None, issue_date: str = None, external_url: str = None) -> Optional[Dict[str, Any]]:
        """
        Check if a source with the given name already exists in the database.

        This is now a wrapper that:
        1. First checks if the newspaper page exists in the NewspaperPages table
        2. If found, returns info about the corresponding source
        3. If not found, checks if the newspaper source exists in the Sources table
        4. Returns None if neither the page nor the source exists

        Args:
            source_name: Name of the source to check
            lccn: LCCN identifier (optional)
            sequence: Page sequence number (optional)
            issue_date: Issue date (optional)
            external_url: External URL for the source (optional)

        Returns:
            Source data as a dictionary if found, None otherwise
        """
        try:
            # If we have LCCN, issue_date, and sequence, we're checking for a newspaper page
            if lccn and issue_date and sequence is not None:
                # IMPORTANT: First check if the page already exists in the NewspaperPages table
                # This should be the primary check, not the source name check
                page_info = self.check_if_newspaper_page_exists(lccn, issue_date, sequence)

                if page_info:
                    # Page exists, get the associated source info
                    source_id = page_info.get('source_id')
                    if source_id:
                        # Connect to the database
                        conn, cursor = self.connect()

                        # Get source info
                        cursor.execute("""
                            SELECT SourceID, SourceName, Aliases
                            FROM Sources
                            WHERE SourceID = ?
                        """, (source_id,))

                        result = cursor.fetchone()
                        conn.close()

                        if result:
                            return {
                                'id': result[0],
                                'name': result[1],
                                'aliases': result[2],
                                'page_exists': True,
                                'page_info': page_info
                            }

                # If we reach here, the page doesn't exist, but the source might
                # Try to find the source by LCCN
                conn, cursor = self.connect()
                cursor.execute("""
                    SELECT SourceID, SourceName, Aliases
                    FROM Sources
                    WHERE Aliases = ?
                """, (lccn,))  # Changed from LIKE to exact match

                result = cursor.fetchone()
                conn.close()

                if result:
                    return {
                        'id': result[0],
                        'name': result[1],
                        'aliases': result[2],
                        'page_exists': False
                    }

                return None

            # Otherwise, check for the source by LCCN first, then name
            conn, cursor = self.connect()

            # If LCCN is provided, try to find by exact LCCN match first
            if lccn:
                cursor.execute("""
                    SELECT SourceID, SourceName, Aliases
                    FROM Sources
                    WHERE Aliases = ?
                """, (lccn,))  # Changed from LIKE to exact match

                result = cursor.fetchone()

                if result:
                    conn.close()
                    return {
                        'id': result[0],
                        'name': result[1],
                        'aliases': result[2],
                        'page_exists': False  # CRITICAL FIX: Ensure page_exists is False when only finding the source
                    }

            # Try by exact source name as fallback
            cursor.execute("""
                SELECT SourceID, SourceName, Aliases
                FROM Sources
                WHERE SourceName = ?
            """, (source_name,))

            result = cursor.fetchone()

            if result:
                conn.close()
                return {
                    'id': result[0],
                    'name': result[1],
                    'aliases': result[2],
                    'page_exists': False  # CRITICAL FIX: Ensure page_exists is False when only finding the source
                }

            conn.close()
            return None
        except Exception as e:
            print(f"Error checking if source exists: {str(e)}")
            return None

    def get_or_create_source_by_lccn(self, lccn: str, source_name: str, source_type: str = 'newspaper') -> int:
        """
        Get a source ID by LCCN or create a new one if it doesn't exist.

        This ensures there's only ONE record in the Sources table for each newspaper.

        Args:
            lccn: LCCN identifier
            source_name: Name of the source (e.g., "The Seattle post-intelligencer")
            source_type: Type of source (default: 'newspaper')

        Returns:
            Source ID
        """
        try:
            # Connect to the database
            conn, cursor = self.connect()

            # Try to find the source by LCCN in the Aliases field
            cursor.execute("""
                SELECT SourceID
                FROM Sources
                WHERE Aliases = ?
            """, (lccn,))

            result = cursor.fetchone()

            if result:
                # Found existing source
                source_id = result[0]
                conn.close()
                return source_id
            else:

                # Clean up the source name (remove [volume] or other artifacts)
                if "[volume]" in source_name:
                    source_name = source_name.split("[volume]")[0].strip()

                # Remove any date or sequence info from the source name
                if " - " in source_name:
                    source_name = source_name.split(" - ")[0].strip()

                # Create a new source entry
                source_data = {
                    'SourceName': source_name,
                    'SourceType': source_type,
                    'Aliases': lccn,  # Store LCCN as alias for identification
                    'Publisher': '',
                    'Location': '',
                    'EstablishedDate': '',
                    'DiscontinuedDate': '',
                    'ImagePath': '',
                    'ReviewStatus': 'needs_review'
                }

                source_id = self.source_service.create_source(source_data)

                conn.close()
                return source_id
        except Exception as e:
            print(f"Error getting or creating source by LCCN: {str(e)}")
            # If an error occurs, fall back to creating a new source through the service
            return self.source_service.create_source({
                'SourceName': source_name,
                'SourceType': source_type,
                'Aliases': lccn
            })

    def add_newspaper_page(self, source_id: int, lccn: str, issue_date: str, sequence: int,
                         page_title: str, image_path: str = None, ocr_path: str = None,
                         pdf_path: str = None, json_path: str = None, external_url: str = None) -> int:
        """
        Add a new newspaper page to the NewspaperPages table.

        Args:
            source_id: ID of the source in the Sources table
            lccn: LCCN identifier
            issue_date: Issue date
            sequence: Page sequence number
            page_title: Title of the page
            image_path: Path to the image file (optional)
            ocr_path: Path to the OCR file (optional)
            pdf_path: Path to the PDF file (optional)
            json_path: Path to the JSON metadata file (optional)
            external_url: External URL to the page (optional)

        Returns:
            ID of the new page
        """


        try:
            # Connect to the database
            conn, cursor = self.connect()
            
            # First, check if the NewspaperPages table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='NewspaperPages'")
            table_exists = cursor.fetchone() is not None
            
            # If table doesn't exist, create it
            if not table_exists:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS NewspaperPages (
                    PageID INTEGER PRIMARY KEY AUTOINCREMENT,
                    SourceID INTEGER,
                    LCCN TEXT NOT NULL,
                    IssueDate TEXT NOT NULL,
                    Sequence INTEGER NOT NULL,
                    PageTitle TEXT,
                    PageNumber TEXT,
                    ImagePath TEXT,
                    OCRPath TEXT,
                    PDFPath TEXT,
                    JSONPath TEXT,
                    ExternalURL TEXT,
                    ImportDate TEXT,
                    ProcessedFlag INTEGER DEFAULT 0,
                    FOREIGN KEY (SourceID) REFERENCES Sources(SourceID),
                    UNIQUE(LCCN, IssueDate, Sequence)
                )
                """)
                conn.commit()

            # Get current date for import date
            import_date = datetime.now().strftime('%Y-%m-%d')

            # Insert the page
            cursor.execute("""
                INSERT INTO NewspaperPages
                (SourceID, LCCN, IssueDate, Sequence, PageTitle, ImagePath, OCRPath, PDFPath, JSONPath, ExternalURL, ImportDate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (source_id, lccn, issue_date, sequence, page_title, image_path, ocr_path, pdf_path, json_path, external_url, import_date))

            # Get the new page ID
            page_id = cursor.lastrowid

            # Commit the changes
            conn.commit()

            conn.close()
            return page_id
        except Exception as e:
            print(f"Error adding newspaper page: {str(e)}")
            return 0

    def import_from_chronicling_america(self,
                                       search_params: Dict[str, Any],
                                       download_dir: str,
                                       max_pages: int = 1,
                                       formats: List[str] = ['pdf', 'ocr']) -> Dict[str, Any]:
        """
        Import newspaper content from the Chronicling America API.

        Args:
            search_params: Dictionary with search parameters (keywords, dates, etc.)
            download_dir: Directory to save downloaded files
            max_pages: Maximum number of search result pages to process
            formats: List of formats to download ('pdf', 'jp2', 'ocr', 'json')

        Returns:
            Dictionary with import results

        Raises:
            ImportError: If ChroniclingAmericaClient is not available
            DatabaseError: If import fails
        """
        if ChroniclingAmericaClient is None:
            raise ImportError("ChroniclingAmericaClient is not available. "
                             "Make sure the api module is installed correctly.")

        # Create the client
        client = ChroniclingAmericaClient(output_directory=download_dir)

        # Prepare search parameters
        keywords = search_params.get('keywords')
        lccn = search_params.get('lccn')
        state = search_params.get('state')
        date_start = search_params.get('date_start')
        date_end = search_params.get('date_end')

        # Search and download newspaper pages
        if USING_IMPROVED_CLIENT:
            # For the improved client, we need to handle search and download separately
            # since it doesn't have a combined search_and_download method

            # First search for pages
            pages, pagination = client.search_pages(
                keywords=keywords,
                lccn=lccn,
                state=state,
                date_start=date_start,
                date_end=date_end,
                page=1,
                max_pages=max_pages
            )

            # Then download each page
            results = []
            total_pages = len(pages)

            # Progress callback
            def report_progress(current, page_title):
                # Log progress
                print(f"Downloading page {current} of {total_pages}: {page_title}")

            for i, page in enumerate(pages):
                try:
                    # Report progress if callback is defined
                    if hasattr(self, 'progress_callback') and callable(self.progress_callback):
                        self.progress_callback(i + 1, total_pages)
                    else:
                        # Use simple console reporting
                        report_progress(i + 1, page.title)

                    # Download the page content
                    download_result = client.download_page_content(
                        page_metadata=page,
                        formats=formats
                    )

                    # Add to results
                    if download_result:
                        results.append({
                            'page': page,
                            'files': download_result,
                            'success': True
                        })
                except Exception as e:
                    results.append({
                        'page': page,
                        'error': str(e),
                        'success': False
                    })
        else:
            # For the original client, we can use the combined search_and_download method
            results = client.search_and_download(
                keywords=keywords,
                lccn=lccn,
                state=state,
                date_start=date_start,
                date_end=date_end,
                max_pages=max_pages,
                formats=formats
            )

        # Import downloaded content into the database
        imported_sources = []
        errors = []
        skipped_sources = []  # Track items that already exist in the database

        for result in results:
            # Handle differently based on which client we're using
            if USING_IMPROVED_CLIENT:
                # For improved client, check if download was successful
                if not result.get('success', False):
                    # Add error and continue
                    error = result.get('error', 'Unknown error')
                    page = result.get('page')
                    errors.append({
                        'lccn': page.lccn if page else 'unknown',
                        'issue_date': page.issue_date if page else 'unknown',
                        'error': f"Failed to download: {error}"
                    })
                    continue

                # Get page metadata
                page = result.get('page')
                if not page:
                    continue

                # Get downloaded files
                files = result.get('files', {})

                # Extract content from OCR file if available
                content = ""
                ocr_path = files.get('ocr')
                if ocr_path and os.path.exists(ocr_path):
                    try:
                        with open(ocr_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except Exception as e:
                        # If OCR file can't be read, log an error but continue
                        errors.append({
                            'lccn': page.lccn,
                            'issue_date': page.issue_date,
                            'error': f"Failed to read OCR content: {str(e)}"
                        })

                # UPDATED LOGIC: First get or create the newspaper source (ONE record per newspaper)
                # Then add the individual page to the NewspaperPages table

                # Get base newspaper name (without date, sequence, etc.)
                base_name = page.title
                if "[volume]" in base_name:
                    base_name = base_name.split("[volume]")[0].strip()

                # IMPORTANT: First directly check if this exact page already exists
                # This is the critical check to avoid duplicates
                page_info = self.check_if_newspaper_page_exists(
                    lccn=page.lccn,
                    issue_date=page.issue_date,
                    sequence=page.sequence
                )

                if page_info:
                    # Page already exists, skip it
                    skipped_sources.append({
                        'source_id': page_info.get('source_id'),
                        'page_id': page_info.get('page_id'),
                        'lccn': page.lccn,
                        'issue_date': page.issue_date,
                        'title': page.title,
                        'sequence': page.sequence,
                        'reason': "Page already exists in database"
                    })
                    continue
                else:
                    # Page does not exist, proceed with import

                    # Get or create the source - this ensures we have only ONE record per newspaper
                    source_id = self.get_or_create_source_by_lccn(
                        lccn=page.lccn,
                        source_name=base_name,
                        source_type='newspaper'
                    )

                    # Prepare paths for the various formats
                    pdf_path = files.get('pdf')
                    jp2_path = files.get('jp2')
                    ocr_path = files.get('ocr')
                    json_path = files.get('json')

                    # Choose the primary image path
                    image_path = None
                    if jp2_path and os.path.exists(jp2_path):
                        image_path = jp2_path
                    elif pdf_path and os.path.exists(pdf_path):
                        image_path = pdf_path
            else:
                # Original client format
                metadata = result.get('metadata', {})

                # Extract content from OCR file if available
                content = ""
                ocr_path = result.get('ocr')
                if ocr_path and os.path.exists(ocr_path):
                    try:
                        with open(ocr_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except Exception as e:
                        # If OCR file can't be read, log an error but continue
                        errors.append({
                            'lccn': metadata.get('lccn'),
                            'issue_date': metadata.get('issue_date'),
                            'error': f"Failed to read OCR content: {str(e)}"
                        })

                # IMPORTANT: First directly check if this exact page already exists
                # This is the critical check to avoid duplicates
                page_info = self.check_if_newspaper_page_exists(
                    lccn=metadata.get('lccn'),
                    issue_date=metadata.get('issue_date'),
                    sequence=metadata.get('sequence')
                )

                if page_info:
                    # Page already exists, skip it
                    skipped_sources.append({
                        'source_id': page_info.get('source_id'),
                        'page_id': page_info.get('page_id'),
                        'lccn': metadata.get('lccn'),
                        'issue_date': metadata.get('issue_date'),
                        'title': metadata.get('title'),
                        'sequence': metadata.get('sequence'),
                        'reason': "Page already exists in database"
                    })
                    continue
                else:
                    # Page does not exist, proceed with import

                    # Get base newspaper name (without date, sequence, etc.)
                    base_name = metadata.get('title', '')
                    if "[volume]" in base_name:
                        base_name = base_name.split("[volume]")[0].strip()

                    # Get or create the source - this ensures we have only ONE record per newspaper
                    source_id = self.get_or_create_source_by_lccn(
                        lccn=metadata.get('lccn'),
                        source_name=base_name,
                        source_type='newspaper'
                    )

                    # Get paths for the various formats
                    pdf_path = result.get('pdf')
                    jp2_path = result.get('jp2')
                    ocr_path = result.get('ocr')
                    json_path = result.get('json')

                    # Choose the primary image path
                    image_path = None
                    if jp2_path and os.path.exists(jp2_path):
                        image_path = jp2_path
                    elif pdf_path and os.path.exists(pdf_path):
                        image_path = pdf_path

                    # Add page to NewspaperPages table
                    try:
                        if USING_IMPROVED_CLIENT:
                            page = result.get('page')

                            # We should only reach here if the page DOESN'T exist yet

                            # Add the newspaper page to the NewspaperPages table
                            page_id = self.add_newspaper_page(
                                source_id=source_id,
                                lccn=page.lccn,
                                issue_date=page.issue_date,
                                sequence=page.sequence,
                                page_title=page.title,
                                image_path=image_path,
                                ocr_path=ocr_path,
                                pdf_path=pdf_path,
                                json_path=json_path,
                                external_url=page.url
                            )

                            # Add to successful imports
                            if page_id > 0:
                                imported_sources.append({
                                    'source_id': source_id,
                                    'page_id': page_id,
                                    'lccn': page.lccn,
                                    'issue_date': page.issue_date,
                                    'title': page.title,
                                    'sequence': page.sequence,
                                    'success': True  # Mark as successful
                                })
                        else:
                            # Original client format
                            metadata = result.get('metadata', {})

                            # Add the newspaper page
                            page_id = self.add_newspaper_page(
                                source_id=source_id,
                                lccn=metadata.get('lccn'),
                                issue_date=metadata.get('issue_date'),
                                sequence=metadata.get('sequence'),
                                page_title=metadata.get('title'),
                                image_path=image_path,
                                ocr_path=ocr_path,
                                pdf_path=pdf_path,
                                json_path=json_path,
                                external_url=metadata.get('url')
                            )

                            # Add to successful imports
                            if page_id > 0:
                                imported_sources.append({
                                    'source_id': source_id,
                                    'page_id': page_id,
                                    'lccn': metadata.get('lccn'),
                                    'issue_date': metadata.get('issue_date'),
                                    'title': metadata.get('title'),
                                    'sequence': metadata.get('sequence'),
                                    'success': True  # Mark as successful
                                })
                    except Exception as e:
                        # Create error record based on which client we're using
                        if USING_IMPROVED_CLIENT:
                            page = result.get('page')
                            errors.append({
                                'lccn': page.lccn if page else 'unknown',
                                'issue_date': page.issue_date if page else 'unknown',
                                'error': f"Failed to create source: {str(e)}"
                            })
                        else:
                            # Original client
                            metadata = result.get('metadata', {})
                            errors.append({
                                'lccn': metadata.get('lccn'),
                                'issue_date': metadata.get('issue_date'),
                                'error': f"Failed to create source: {str(e)}"
                            })


        # Prepare the return data with improved message
        return_data = {
            'successful': imported_sources,
            'failed': errors,
            'skipped': skipped_sources,
            'total_downloaded': len(results),
            'total_imported': len(imported_sources),
            'total_skipped': len(skipped_sources),
            'message': f"""
Newspaper Pages:
- Downloaded: {len(results)} pages
- Created {1 if len(imported_sources) > 0 else 0} newspaper source record in Sources table
- Created {len(imported_sources)} newspaper page records in NewspaperPages table
- Skipped {len(skipped_sources)} pages (already in database)
"""
        }
        return return_data