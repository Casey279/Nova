"""
Enhanced search worker class with checkpoint support for resumable downloads.

This module extends the SearchWorker class to add support for 
checkpointing and resumable downloads.
"""

import os
import sys
import logging
import time
from typing import Dict, List, Any, Optional, Callable

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from PyQt5.QtCore import QThread, pyqtSignal

# Import the DownloadCheckpoint class
from .download_checkpoint import DownloadCheckpoint

# Try to import the ChroniclingAmerica client with the same logic as ImportService
try:
    # Try relative import first
    from ..api.chronicling_america_improved import ImprovedChroniclingAmericaClient as ChroniclingAmericaClient
    USING_IMPROVED_CLIENT = True
    logger.info("ResumableSearchWorker: Using improved client")
except ImportError as e:
    # Try absolute import
    try:
        # Add parent dir to path if needed
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from api.chronicling_america_improved import ImprovedChroniclingAmericaClient as ChroniclingAmericaClient
        USING_IMPROVED_CLIENT = True
        logger.info("ResumableSearchWorker: Using improved client via absolute import")
    except ImportError:
        # Fall back to the original client
        try:
            from ..api.chronicling_america import ChroniclingAmericaClient
            USING_IMPROVED_CLIENT = False
            logger.info("ResumableSearchWorker: Using original client")
        except ImportError:
            try:
                from api.chronicling_america import ChroniclingAmericaClient
                USING_IMPROVED_CLIENT = False
                logger.info("ResumableSearchWorker: Using original client via absolute import")
            except ImportError:
                logger.error("ResumableSearchWorker: ChroniclingAmericaClient not available")
                ChroniclingAmericaClient = None
                USING_IMPROVED_CLIENT = False

class ResumableSearchWorker(QThread):
    """
    Enhanced worker thread for searching and downloading from ChroniclingAmerica
    with checkpoint support for resumable downloads.
    """
    
    # Define signals
    progress_signal = pyqtSignal(int, int)  # current, total (for download phase)
    search_results_signal = pyqtSignal(list, dict, dict)  # results, pagination, extra_info
    finished_signal = pyqtSignal(dict)  # results from download/import
    error_signal = pyqtSignal(str)  # error message
    gap_signal = pyqtSignal(dict)  # Information about detected gaps
    checkpoint_signal = pyqtSignal(str, int, int)  # checkpoint_id, completed, total
    
    def __init__(self, 
                search_params: Dict[str, Any], 
                download_dir: str, 
                max_pages: int = 100,
                download_formats: Optional[List[str]] = None, 
                import_service = None,
                detect_gaps: bool = False, 
                gap_threshold: int = 5,
                checkpoint_id: Optional[str] = None,
                enable_checkpointing: bool = True,
                checkpoint_interval: int = 10):
        """
        Initialize the resumable search worker.
        
        Args:
            search_params: Parameters for the search
            download_dir: Directory to save downloads
            max_pages: Maximum number of search result pages
            download_formats: Formats to download
            import_service: ImportService instance for importing results
            detect_gaps: Whether to detect gaps in newspaper content
            gap_threshold: Number of consecutive days without content to trigger gap detection
            checkpoint_id: Optional ID of checkpoint to resume from
            enable_checkpointing: Whether to create checkpoints during download
            checkpoint_interval: How often to create checkpoints (number of pages)
        """
        super().__init__()
        self.search_params = search_params
        self.download_dir = download_dir
        self.max_pages = max_pages
        self.download_formats = download_formats or ['pdf', 'ocr']
        self.import_service = import_service
        self.download_results = []
        self.search_only = self.import_service is None
        self.detect_gaps = detect_gaps
        self.gap_threshold = gap_threshold
        
        # Checkpointing parameters
        self.checkpoint_manager = DownloadCheckpoint(download_dir)
        self.checkpoint_id = checkpoint_id
        self.enable_checkpointing = enable_checkpointing
        self.checkpoint_interval = checkpoint_interval
        self.completed_pages = []
        self.pending_pages = []
        
        # Track status
        self.is_cancelled = False
        self.current_page_index = 0
        self.total_pages = 0
        
        # Load existing checkpoint if provided
        if self.checkpoint_id:
            self.load_from_checkpoint(self.checkpoint_id)
    
    def load_from_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Load state from an existing checkpoint.
        
        Args:
            checkpoint_id: ID of the checkpoint to load
            
        Returns:
            True if successful, False otherwise
        """
        checkpoint_data = self.checkpoint_manager.load_checkpoint(checkpoint_id)
        if not checkpoint_data:
            logger.warning(f"Failed to load checkpoint: {checkpoint_id}")
            return False
        
        try:
            # Restore state from checkpoint
            self.search_params = checkpoint_data.get('search_params', self.search_params)
            self.completed_pages = checkpoint_data.get('completed_pages', [])
            self.pending_pages = checkpoint_data.get('pending_pages', [])
            self.download_formats = checkpoint_data.get('download_formats', self.download_formats)
            self.max_pages = checkpoint_data.get('max_pages', self.max_pages)
            
            # Update progress tracking
            self.current_page_index = len(self.completed_pages)
            self.total_pages = len(self.completed_pages) + len(self.pending_pages)
            
            logger.info(f"Loaded checkpoint: {checkpoint_id}")
            logger.info(f"Resuming from page {self.current_page_index + 1} of {self.total_pages}")
            
            return True
        except Exception as e:
            logger.error(f"Error loading checkpoint: {str(e)}")
            return False
    
    def save_checkpoint(self) -> str:
        """
        Save current state to a checkpoint.
        
        Returns:
            Checkpoint ID if successful, empty string otherwise
        """
        if not self.enable_checkpointing:
            return ""
            
        try:
            # Generate checkpoint ID if we don't have one yet
            if not self.checkpoint_id:
                self.checkpoint_id = self.checkpoint_manager.generate_checkpoint_id(self.search_params)
            
            # Save current state
            success = self.checkpoint_manager.save_checkpoint(
                self.checkpoint_id,
                self.search_params,
                self.completed_pages,
                self.pending_pages,
                self.download_formats,
                self.max_pages
            )
            
            if success:
                # Emit signal with progress info
                self.checkpoint_signal.emit(
                    self.checkpoint_id, 
                    len(self.completed_pages), 
                    len(self.completed_pages) + len(self.pending_pages)
                )
                return self.checkpoint_id
            
            return ""
        except Exception as e:
            logger.error(f"Error saving checkpoint: {str(e)}")
            return ""
    
    def cancel(self):
        """
        Cancel the current operation and save checkpoint.
        """
        logger.info("Cancelling download operation")
        self.is_cancelled = True
        
        # Save checkpoint before exiting
        if self.enable_checkpointing and (self.completed_pages or self.pending_pages):
            checkpoint_id = self.save_checkpoint()
            if checkpoint_id:
                logger.info(f"Saved checkpoint before cancellation: {checkpoint_id}")
    
    def run(self):
        """
        Run the search and download process with checkpoint support.
        """
        try:
            if not ChroniclingAmericaClient:
                self.error_signal.emit("ChroniclingAmerica API is not available")
                return
            
            # Create API client
            client = ChroniclingAmericaClient(output_directory=self.download_dir)
            
            # If we don't have any existing data (not resuming), perform search
            if not self.pending_pages and not self.completed_pages:
                # Extra info to pass back to the UI
                extra_info = {}
                
                # Check for newspaper metadata first
                lccn = self.search_params.get('lccn')
                if USING_IMPROVED_CLIENT and lccn:
                    # Try to get the title, earliest and latest issue dates
                    self._get_newspaper_metadata(client, lccn, extra_info)
                
                if self.search_only:
                    # Search only
                    pages, pagination = self._perform_search(client, extra_info)
                    
                    # Send results to UI with extra info
                    self.search_results_signal.emit(pages, pagination, extra_info)
                else:
                    # Search and download
                    self._perform_search_and_download(client, extra_info)
            else:
                # We're resuming from a checkpoint - start downloading pending pages
                self._resume_download_from_checkpoint(client)
        
        except Exception as e:
            logger.error(f"Error in ResumableSearchWorker: {str(e)}", exc_info=True)
            self.error_signal.emit(f"Error: {str(e)}")
    
    def _get_newspaper_metadata(self, client, lccn, extra_info):
        """
        Get newspaper metadata (title, earliest/latest dates) and update search parameters
        and extra_info.
        
        Args:
            client: ChroniclingAmericaClient instance
            lccn: LCCN to get metadata for
            extra_info: Dictionary to update with metadata
        """
        try:
            # Import helper module for dates
            from api.chronicling_america_earliest_dates import get_earliest_date, get_latest_date, get_newspaper_title
            
            # Get title if available
            title = get_newspaper_title(lccn)
            if title:
                extra_info['newspaper_title'] = title
            
            # Get earliest issue date - first from module, then from client
            earliest_date = get_earliest_date(lccn)
            if not earliest_date and hasattr(client, 'get_earliest_issue_date'):
                # Try to get it directly from the client
                earliest_date = client.get_earliest_issue_date(lccn)
            
            if earliest_date:
                # Store the earliest date in extra_info
                extra_info['earliest_issue_date'] = earliest_date.isoformat()
                
                # If we have a start date that's earlier than the earliest issue,
                # note this so the UI can show a message AND adjust the search parameters
                date_start = self.search_params.get('date_start')
                if date_start:
                    try:
                        from datetime import datetime
                        start_date = datetime.strptime(date_start, "%Y-%m-%d").date()
                        if start_date < earliest_date:
                            # Store for UI display
                            extra_info['adjusted_start_date'] = earliest_date.isoformat()
                            
                            # IMPORTANT: Actually modify the search parameters to use the earliest issue date
                            # This ensures the client won't search before the first available issue
                            earliest_date_str = earliest_date.strftime("%Y-%m-%d")
                            self.search_params['date_start'] = earliest_date_str
                            logger.info(f"Adjusted search start date from {date_start} to {earliest_date_str} (first issue)")
                    except (ValueError, TypeError):
                        pass
            
            # Get latest issue date - first from module, then from client
            latest_date = get_latest_date(lccn)
            if not latest_date and hasattr(client, 'get_latest_issue_date'):
                # Try to get it directly from the client
                latest_date = client.get_latest_issue_date(lccn)
            
            if latest_date:
                # Store the latest date in extra_info
                extra_info['latest_issue_date'] = latest_date.isoformat()
                
                # If we have an end date that's later than the latest issue,
                # note this so the UI can show a message AND adjust the search parameters
                date_end = self.search_params.get('date_end')
                if date_end:
                    try:
                        from datetime import datetime
                        end_date = datetime.strptime(date_end, "%Y-%m-%d").date()
                        if end_date > latest_date:
                            # Store for UI display
                            extra_info['adjusted_end_date'] = latest_date.isoformat()
                            
                            # IMPORTANT: Actually modify the search parameters to use the latest issue date
                            # This ensures the client won't search beyond the last available issue
                            latest_date_str = latest_date.strftime("%Y-%m-%d")
                            self.search_params['date_end'] = latest_date_str
                            logger.info(f"Adjusted search end date from {date_end} to {latest_date_str} (last issue)")
                    except (ValueError, TypeError):
                        pass
                        
        except Exception as e:
            logger.error(f"Error getting newspaper metadata: {str(e)}")
            # Continue with search even if metadata lookup fails
    
    def _perform_search(self, client, extra_info):
        """
        Perform search for pages.
        
        Args:
            client: ChroniclingAmericaClient instance
            extra_info: Dictionary for additional information
            
        Returns:
            Tuple of (pages, pagination)
        """
        pages, pagination = client.search_pages(
            keywords=self.search_params.get('keywords'),
            lccn=self.search_params.get('lccn'),
            state=self.search_params.get('state'),
            date_start=self.search_params.get('date_start'),
            date_end=self.search_params.get('date_end'),
            page=1,  # Start with first page
            max_pages=self.max_pages,  # Use the max_pages parameter
            detect_gaps=self.detect_gaps,  # Enable gap detection if requested
            gap_threshold=self.gap_threshold  # Use specified gap threshold
        )
        
        # If gap detection is enabled, check for gap information in the results
        if self.detect_gaps and 'search_info' in pagination:
            search_info = pagination.get('search_info', {})
            
            # Add search info to extra_info for UI display
            extra_info['search_info'] = search_info
            
            # If gaps were detected, emit the gap signal
            if search_info.get('gaps'):
                self.gap_signal.emit({
                    'gaps': search_info.get('gaps', []),
                    'has_more_content': search_info.get('has_more_content', True),
                    'chronicling_america_url': search_info.get('chronicling_america_url', '')
                })
        
        return pages, pagination
    
    def _perform_search_and_download(self, client, extra_info):
        """
        Perform search and download newspaper pages.
        
        Args:
            client: ChroniclingAmericaClient instance
            extra_info: Dictionary for additional information
        """
        # First search for pages
        pages, pagination = self._perform_search(client, extra_info)
        
        # Store pages for download
        self.pending_pages = pages
        self.total_pages = len(pages)
        
        # Create a new checkpoint before starting download
        if self.enable_checkpointing and self.total_pages > 0:
            self.checkpoint_id = self.checkpoint_manager.generate_checkpoint_id(self.search_params)
            self.save_checkpoint()
        
        # Download pages
        self._download_pages(client, extra_info)
    
    def _resume_download_from_checkpoint(self, client):
        """
        Resume downloading pages from a checkpoint.
        
        Args:
            client: ChroniclingAmericaClient instance
        """
        logger.info(f"Resuming download from checkpoint with {len(self.pending_pages)} pending pages")
        
        # Start downloading pages
        extra_info = {}  # We don't need to pass much extra info in resume mode
        self._download_pages(client, extra_info)
    
    def _download_pages(self, client, extra_info):
        """
        Download a list of pages with checkpoint support.
        
        Args:
            client: ChroniclingAmericaClient instance
            extra_info: Dictionary for additional information
        """
        if not self.pending_pages:
            logger.warning("No pages to download")
            self.finished_signal.emit({
                'successful': [],
                'failed': [],
                'skipped': [],
                'total_downloaded': 0,
                'total_imported': 0,
                'total_skipped': 0,
                'extra_info': extra_info
            })
            return
        
        # Prepare for downloading
        successful = []
        failed = []
        skipped = []
        
        # Track progress
        total_pages = len(self.pending_pages)
        self.progress_signal.emit(self.current_page_index, self.total_pages)
        
        # Process each page
        while self.pending_pages and not self.is_cancelled:
            # Get the next page to process
            page = self.pending_pages.pop(0)
            
            try:
                # Report progress
                self.progress_signal.emit(self.current_page_index + 1, self.total_pages)
                
                # First check if this page already exists in the database
                # This helps prevent re-downloading content we already have
                if self.import_service:
                    try:
                        # Check if the specific page exists (not just the source)
                        logger.info(f"Checking if page exists before download: LCCN={page.lccn}, issue_date={page.issue_date}, sequence={page.sequence}")
                        existing_page = self.import_service.check_if_newspaper_page_exists(
                            lccn=page.lccn,
                            issue_date=page.issue_date,
                            sequence=page.sequence
                        )

                        if existing_page:
                            # Page exists, get source info
                            source_id = existing_page.get('source_id')
                            logger.info(f"Found existing page with ID={existing_page.get('page_id')}, source_id={source_id}")

                            # Skip this page and track it
                            skipped.append({
                                'source_id': source_id,
                                'page_id': existing_page.get('page_id'),
                                'lccn': page.lccn,
                                'issue_date': page.issue_date,
                                'title': page.title,
                                'sequence': page.sequence,
                                'reason': "Page already exists in database"
                            })

                            # Track as completed for the checkpoint
                            page_metadata = self._extract_page_metadata(page)
                            page_metadata['skipped'] = True
                            page_metadata['reason'] = "Already exists in database"
                            self.completed_pages.append(page_metadata)

                            # Update progress
                            self.current_page_index += 1
                            continue
                        else:
                            logger.info(f"Page does not exist, will download and import")
                    except Exception as e:
                        logger.warning(f"Error checking if page exists: {str(e)}")
                        # Continue with download even if check fails
                
                # Download the page content
                download_result = client.download_page_content(
                    page_metadata=page,
                    formats=self.download_formats
                )
                
                # Track the result
                if download_result:
                    # Import to database if requested
                    if self.import_service:
                        import_result = self._import_page(page, download_result)
                        if import_result.get('success', False):
                            successful.append(import_result)
                        else:
                            failed.append({
                                'lccn': page.lccn,
                                'issue_date': page.issue_date,
                                'title': page.title,
                                'error': import_result.get('error', "Import failed")
                            })
                    else:
                        # Just track as downloaded
                        successful.append({
                            'lccn': page.lccn,
                            'issue_date': page.issue_date,
                            'title': page.title,
                            'sequence': page.sequence,
                            'files': download_result,
                            'success': True
                        })
                    
                    # Track as completed for the checkpoint
                    page_metadata = self._extract_page_metadata(page)
                    page_metadata['skipped'] = False
                    self.completed_pages.append(page_metadata)
                else:
                    # Download failed
                    failed.append({
                        'lccn': page.lccn,
                        'issue_date': page.issue_date,
                        'title': page.title,
                        'error': "Download failed"
                    })
            except Exception as e:
                logger.error(f"Error processing page: {str(e)}")
                # Add to failed list
                failed.append({
                    'lccn': getattr(page, 'lccn', 'unknown'),
                    'issue_date': getattr(page, 'issue_date', 'unknown'),
                    'title': getattr(page, 'title', 'unknown'),
                    'error': str(e)
                })
            
            # Update progress
            self.current_page_index += 1
            
            # Create checkpoint at specified intervals
            if (self.enable_checkpointing and 
                self.current_page_index % self.checkpoint_interval == 0 and
                self.pending_pages):  # Only checkpoint if we have more to do
                self.save_checkpoint()
            
            # Brief pause to allow UI updates and reducing system load
            time.sleep(0.1)
        
        # Create final results
        results = {
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'total_downloaded': len(successful),
            'total_imported': len(successful),
            'total_skipped': len(skipped),
            'extra_info': extra_info,
            'checkpoint_id': self.checkpoint_id if self.is_cancelled else None
        }
        
        # Delete checkpoint if completed successfully (not cancelled)
        if not self.is_cancelled and self.checkpoint_id:
            try:
                self.checkpoint_manager.delete_checkpoint(self.checkpoint_id)
                logger.info(f"Deleted completed checkpoint: {self.checkpoint_id}")
            except Exception as e:
                logger.error(f"Error deleting checkpoint: {str(e)}")
        
        # Signal completion
        self.finished_signal.emit(results)
    
    def _import_page(self, page, download_result):
        """
        Import a downloaded page to the database.

        Args:
            page: Page metadata
            download_result: Result of download operation

        Returns:
            Dictionary with import results
        """
        try:
            # Use our improved import_from_chronicling_america method structure
            # First get or create the source record for this newspaper
            logger.info(f"Importing newspaper page for LCCN={page.lccn}, issue_date={page.issue_date}, sequence={page.sequence}")

            # Get base name without volume, date, etc.
            base_name = page.title
            if "[volume]" in base_name:
                base_name = base_name.split("[volume]")[0].strip()

            # Get or create source
            logger.info(f"Getting or creating source with LCCN={page.lccn}, name={base_name}")
            source_id = self.import_service.get_or_create_source_by_lccn(
                lccn=page.lccn,
                source_name=base_name,
                source_type='newspaper'
            )

            # Prepare paths for various formats
            pdf_path = download_result.get('pdf')
            jp2_path = download_result.get('jp2')
            ocr_path = download_result.get('ocr')
            json_path = download_result.get('json')

            # Choose the primary image path
            image_path = None
            if jp2_path and os.path.exists(jp2_path):
                image_path = jp2_path
            elif pdf_path and os.path.exists(pdf_path):
                image_path = pdf_path

            # Check if page already exists first (should return None for new pages)
            logger.info(f"Checking if page exists for LCCN={page.lccn}, issue_date={page.issue_date}, sequence={page.sequence}")
            existing_page = self.import_service.check_if_newspaper_page_exists(
                lccn=page.lccn,
                issue_date=page.issue_date,
                sequence=page.sequence
            )

            if existing_page:
                # Page already exists, return info
                logger.info(f"Page already exists with ID={existing_page.get('page_id')}")
                return {
                    'source_id': source_id,
                    'page_id': existing_page.get('page_id'),
                    'lccn': page.lccn,
                    'issue_date': page.issue_date,
                    'title': page.title,
                    'sequence': page.sequence,
                    'skipped': True,
                    'success': True
                }

            # Add the newspaper page to the NewspaperPages table
            logger.info(f"Adding new page to NewspaperPages table")
            page_id = self.import_service.add_newspaper_page(
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

            # Return success with page ID
            logger.info(f"Successfully added page with ID={page_id}")
            return {
                'source_id': source_id,
                'page_id': page_id,
                'lccn': page.lccn,
                'issue_date': page.issue_date,
                'title': page.title,
                'sequence': page.sequence,
                'success': True
            }
        except Exception as e:
            logger.error(f"Error importing page: {str(e)}", exc_info=True)
            return {
                'lccn': page.lccn,
                'issue_date': page.issue_date,
                'title': page.title,
                'error': f"Failed to import: {str(e)}",
                'success': False
            }
    
    def _extract_page_metadata(self, page):
        """
        Extract serializable metadata from a page object.
        
        Args:
            page: Page object
            
        Returns:
            Dictionary with serializable metadata
        """
        return {
            'lccn': getattr(page, 'lccn', ''),
            'issue_date': getattr(page, 'issue_date', ''),
            'title': getattr(page, 'title', ''),
            'sequence': getattr(page, 'sequence', 0),
            'url': getattr(page, 'url', ''),
            # Add other fields as needed, ensuring they're JSON-serializable
        }