#!/usr/bin/env python3
"""
Test Workflow for Newspaper Repository

This script tests the complete workflow:
1. Downloads sample newspaper pages from ChroniclingAmerica
2. Processes them with the OCR pipeline
3. Extracts articles from the pages
4. Adds them to the repository
5. Verifies all components work together correctly

This is intended as an integration test to ensure all components 
of the newspaper repository system work together properly.
"""

import os
import sys
import time
import json
import requests
import logging
import argparse
import re
import traceback
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TestWorkflow')

# Add parent directory to path to import repository modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import repository modules
from newspaper_repository.repository_database import RepositoryDatabaseManager
from newspaper_repository.file_manager import FileManager
from newspaper_repository.ocr_processor import OCRProcessor
from newspaper_repository.background_service import BackgroundProcessingService

class TestWorkflow:
    """Test the complete workflow for the newspaper repository."""
    
    def __init__(self, base_dir, db_path=None):
        """
        Initialize the test workflow.
        
        Args:
            base_dir: Base directory for the repository
            db_path: Path to the repository database
        """
        self.base_dir = os.path.abspath(base_dir)
        
        # Use default database path if not provided
        if db_path is None:
            db_path = os.path.join(self.base_dir, "repository.db")
        self.db_path = db_path
        
        # Create directories
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "download"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "temp"), exist_ok=True)
        
        # Initialize components
        self.db_manager = RepositoryDatabaseManager(self.db_path)
        self.file_manager = FileManager(self.base_dir)
        self.ocr_processor = OCRProcessor()
        
        # Initialize background service
        self.background_service = BackgroundProcessingService(
            db_path=self.db_path,
            base_directory=self.base_dir,
            max_retries=2,
            retry_delay=30,
            max_concurrent_tasks=1
        )
        
        # Test metadata
        self.test_results = {
            "download": {},
            "ocr": {},
            "segmentation": {},
            "article_extraction": {},
            "overall": {
                "success": False,
                "message": "",
                "start_time": datetime.now().isoformat(),
                "end_time": None
            }
        }
    
    def download_sample_pages(self, count=2):
        """
        Download sample newspaper pages from ChroniclingAmerica.
        
        Args:
            count: Number of pages to download
            
        Returns:
            List of downloaded file paths
        """
        logger.info(f"Downloading {count} sample pages from ChroniclingAmerica...")
        
        # Start timer
        start_time = time.time()
        
        # Use known working newspapers
        # These are confirmed to exist in ChroniclingAmerica
        KNOWN_PAPERS = [
            {
                "lccn": "sn83030214",  # New York Tribune
                "date": "1922-05-15",
                "edition": "1",
                "sequence": "1"
            },
            {
                "lccn": "sn84026749",  # New-York Daily Tribune
                "date": "1920-01-01", 
                "edition": "1",
                "sequence": "1"
            },
            {
                "lccn": "sn83030273",  # The Evening World (New York)
                "date": "1921-09-01",
                "edition": "1",
                "sequence": "1"
            },
            {
                "lccn": "sn83045487",  # Chicago Daily Tribune
                "date": "1923-02-15",
                "edition": "1", 
                "sequence": "1"
            },
            {
                "lccn": "sn87062268",  # The Washington Times
                "date": "1924-03-10",
                "edition": "1",
                "sequence": "1"
            }
        ]
        
        try:
            # Try the ChroniclingAmerica API first
            downloaded_files = []
            papers_to_try = min(count, len(KNOWN_PAPERS))
            
            # Attempt to download each known paper
            for i, paper in enumerate(KNOWN_PAPERS[:papers_to_try]):
                logger.info(f"Attempting to download known paper {i+1}/{papers_to_try}: "
                           f"LCCN {paper['lccn']} from {paper['date']}")
                
                downloaded_file = self._download_specific_page(
                    paper['lccn'], 
                    paper['date'], 
                    paper['edition'], 
                    paper['sequence'],
                    i
                )
                
                if downloaded_file:
                    downloaded_files.append(downloaded_file)
            
            # If we didn't get enough pages, try the API search
            if len(downloaded_files) < count:
                logger.info(f"Got {len(downloaded_files)} pages from known papers, "
                          f"trying API search for {count - len(downloaded_files)} more...")
                
                api_files = self._download_from_api(count - len(downloaded_files))
                downloaded_files.extend(api_files)
            
            # Update test results
            self.test_results["download"] = {
                "success": len(downloaded_files) > 0,
                "count": len(downloaded_files),
                "files": [meta for _, meta in downloaded_files],
                "time_taken": time.time() - start_time,
                "message": f"Downloaded {len(downloaded_files)} of {count} requested pages"
            }
            
            return downloaded_files
            
        except Exception as e:
            logger.error(f"Error during download: {e}")
            self.test_results["download"] = {
                "success": False,
                "message": f"Error: {str(e)}",
                "time_taken": time.time() - start_time
            }
            return []
    
    def _download_specific_page(self, lccn, date, edition, sequence, index=0):
        """
        Download a specific newspaper page by LCCN, date, edition, and sequence.
        
        Args:
            lccn: Library of Congress Control Number
            date: Publication date (YYYY-MM-DD)
            edition: Edition number
            sequence: Page sequence number
            index: Index for logging purposes
            
        Returns:
            Tuple of (file_path, metadata) or None if download fails
        """
        # Format date as YYYYMMDD for URL
        date_no_hyphens = date.replace('-', '')
        
        # Construct URLs to try
        urls_to_try = [
            # Updated to use http as requested
            f"http://chroniclingamerica.loc.gov/iiif/2/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}/full/full/0/default.jpg",
            
            # Modern IIIF image API pattern (most reliable)
            f"http://chroniclingamerica.loc.gov/iiif/2/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}/full/pct:100/0/default.jpg",
            
            # Standard JP2 URL pattern
            f"http://chroniclingamerica.loc.gov/lccn/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}.jp2",
            
            # PDF URL pattern (converted to image)
            f"http://chroniclingamerica.loc.gov/lccn/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}.pdf",
            
            # Try image tiles URL
            f"http://chroniclingamerica.loc.gov/tiles/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}/image_full.jpg",
            
            # Alternative URL format
            f"http://chroniclingamerica.loc.gov/data/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}/image_full.jpg",
            
            # Try fallback to HTTPS if HTTP fails
            f"https://chroniclingamerica.loc.gov/iiif/2/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}/full/full/0/default.jpg",
            
            # HTTPS IIIF pattern
            f"https://chroniclingamerica.loc.gov/iiif/2/{lccn}/{date_no_hyphens}/ed-{edition}/seq-{sequence}/full/pct:100/0/default.jpg"
        ]
        
        # Get newspaper title information
        title = "Unknown"
        try:
            title_url = f"https://chroniclingamerica.loc.gov/lccn/{lccn}.json"
            title_response = requests.get(title_url)
            if title_response.status_code == 200:
                title_data = title_response.json()
                title = title_data.get("name", "Unknown")
                logger.info(f"Found newspaper title: {title}")
        except Exception as e:
            logger.warning(f"Could not get newspaper title information: {e}")
        
        # Try each URL until one works
        file_path = None
        metadata = None
        successful_url = None
        
        for url_index, url in enumerate(urls_to_try):
            try:
                # Clean up URL by removing double slashes (except in http:// or https://)
                url = re.sub(r'(?<!:)\/\/', '/', url)
                
                logger.info(f"Trying URL {url_index+1}/{len(urls_to_try)}: {url}")
                
                # Make HEAD request first to check if URL exists
                head_response = requests.head(url, timeout=10)
                
                if head_response.status_code != 200:
                    logger.warning(f"URL returned status code {head_response.status_code}, trying next URL")
                    continue
                
                # Download the image
                logger.info(f"URL exists, downloading image...")
                img_response = requests.get(url, timeout=30)
                img_response.raise_for_status()
                
                # Create sanitized filename
                sanitized_title = "".join(c if c.isalnum() else "_" for c in title)
                filename = f"{sanitized_title}_{date}_{sequence}.jpg"
                file_path = os.path.join(self.base_dir, "download", filename)
                
                # Save image
                with open(file_path, "wb") as f:
                    f.write(img_response.content)
                
                # Create metadata
                metadata = {
                    "title": title,
                    "date": date,
                    "lccn": lccn,
                    "sequence": sequence,
                    "edition": edition,
                    "image_url": url,
                    "file_path": file_path
                }
                
                logger.info(f"Successfully downloaded page {index+1} from {url}")
                successful_url = url
                break
                
            except Exception as e:
                logger.warning(f"Failed to download from URL {url}: {e}")
        
        if successful_url:
            logger.info(f"Successfully downloaded page from {successful_url}")
            return (file_path, metadata)
        else:
            logger.error(f"All URL patterns failed for LCCN {lccn}, date {date}, "
                       f"edition {edition}, sequence {sequence}")
            return None
    
    def _download_from_api(self, count):
        """
        Download pages using the ChroniclingAmerica API search.
        
        Args:
            count: Number of pages to download
            
        Returns:
            List of (file_path, metadata) tuples
        """
        # ChroniclingAmerica API base URL (using http as requested)
        api_base = "http://chroniclingamerica.loc.gov/search/pages/results/"
        
        # Parameters for API request - updated for 1920s newspapers
        params = {
            "state": "New York",
            "dateFilterType": "range",
            "date1": "1920",
            "date2": "1925",
            "language": "English",
            "sequence": "1",  # First page of issues
            "sort": "date",
            "rows": "10",  # As requested
            "format": "json"
        }
        
        # Define multiple search attempts with different parameters
        search_attempts = [
            {"state": "New York", "date1": "1920", "date2": "1925"},
            {"state": "California", "date1": "1922", "date2": "1924"},
            {"state": "Illinois", "date1": "1921", "date2": "1925"},
            {"state": "Pennsylvania", "date1": "1920", "date2": "1923"}
        ]
        
        downloaded_files = []
        
        # Try each search configuration until we get enough files
        for attempt_idx, search_params in enumerate(search_attempts):
            if len(downloaded_files) >= count:
                break
                
            # Update search parameters
            params.update(search_params)
            
            try:
                # Log the full URL for debugging
                full_url = api_base + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
                logger.info(f"Attempt {attempt_idx+1}: Querying ChroniclingAmerica API: {full_url}")
                
                # Make the request
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        response = requests.get(api_base, params=params, timeout=30)
                        response.raise_for_status()
                        break
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                        if retry < max_retries - 1:
                            logger.warning(f"Request attempt {retry+1} failed: {e}. Retrying...")
                        else:
                            raise
                
                logger.info(f"API response status code: {response.status_code}")
                
                # Parse the response
                try:
                    search_data = response.json()
                    items = search_data.get("items", [])
                    logger.info(f"API returned {len(items)} items")
                    
                    # Log the first item for debugging
                    if items:
                        logger.info(f"Sample item structure: {json.dumps(items[0], indent=2)}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse API response as JSON: {e}")
                    logger.debug(f"Response content: {response.content[:500]}...")
                    continue
                
                if not items:
                    logger.warning(f"No items found in search results for attempt {attempt_idx+1}")
                    continue
                
                # Process each item to extract image URLs directly from API response
                for i, item in enumerate(items):
                    if len(downloaded_files) >= count:
                        break
                        
                    try:
                        # Extract metadata
                        title = item.get("title_normal", "Unknown")
                        date = item.get("date", "Unknown")
                        lccn = item.get("lccn", "Unknown")
                        sequence = item.get("sequence", "1")
                        edition = item.get("edition", "1")
                        
                        # Extract image URL directly from API response
                        # Look for various possible URL fields
                        image_url = None
                        
                        # Try getting URL from the json response directly
                        url_candidates = [
                            item.get("image_url"),
                            item.get("pdf_url"),
                            item.get("jp2_url"),
                            item.get("thumbnail_url")
                        ]
                        
                        # If we have an id, construct the IIIF URL
                        if item.get("id"):
                            identifier = item.get("id")
                            # Remove leading/trailing slashes
                            identifier = identifier.strip('/')
                            iiif_url = f"http://chroniclingamerica.loc.gov/iiif/2/{identifier}/full/full/0/default.jpg"
                            url_candidates.append(iiif_url)
                        
                        # Try each possible URL
                        for url in url_candidates:
                            if url and self._is_valid_url(url):
                                image_url = url
                                break
                        
                        logger.info(f"Found image URL from API: {image_url}")
                        
                        # If we found a valid URL, download it directly
                        if image_url:
                            downloaded_file = self._download_from_url(
                                image_url, title, date, lccn, sequence, edition
                            )
                            if downloaded_file:
                                downloaded_files.append(downloaded_file)
                                continue
                        
                        # If direct URL fails, fall back to our structured URL approach
                        logger.info(f"Falling back to structured URL approach for item {i+1}")
                        downloaded_file = self._download_specific_page(
                            lccn, date, edition, sequence, i
                        )
                        
                        if downloaded_file:
                            downloaded_files.append(downloaded_file)
                        
                    except Exception as e:
                        logger.error(f"Error processing item {i+1}: {e}")
                        logger.error(traceback.format_exc())
                
            except Exception as e:
                logger.error(f"Error during API search attempt {attempt_idx+1}: {e}")
                logger.error(traceback.format_exc())
        
        return downloaded_files
    
    def _is_valid_url(self, url):
        """Check if a URL is valid by making a HEAD request."""
        if not url:
            return False
        
        try:
            logger.info(f"Checking URL validity: {url}")
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"URL validation failed: {e}")
            return False
    
    def _download_from_url(self, url, title, date, lccn, sequence, edition):
        """
        Download a page directly from a URL.
        
        Args:
            url: Direct URL to the image
            title: Newspaper title
            date: Publication date
            lccn: Library of Congress Control Number
            sequence: Page sequence number
            edition: Edition number
            
        Returns:
            Tuple of (file_path, metadata) or None if download fails
        """
        try:
            logger.info(f"Downloading directly from URL: {url}")
            
            # Clean up URL by removing double slashes (except in http:// or https://)
            url = re.sub(r'(?<!:)\/\/', '/', url)
            
            # Download the image
            max_retries = 3
            for retry in range(max_retries):
                try:
                    img_response = requests.get(url, timeout=30)
                    img_response.raise_for_status()
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if retry < max_retries - 1:
                        logger.warning(f"Download attempt {retry+1} failed: {e}. Retrying...")
                    else:
                        raise
            
            # Create sanitized filename
            sanitized_title = "".join(c if c.isalnum() else "_" for c in title)
            filename = f"{sanitized_title}_{date}_{sequence}.jpg"
            file_path = os.path.join(self.base_dir, "download", filename)
            
            # Save image
            with open(file_path, "wb") as f:
                f.write(img_response.content)
            
            # Create metadata
            metadata = {
                "title": title,
                "date": date,
                "lccn": lccn,
                "sequence": sequence,
                "edition": edition,
                "image_url": url,
                "file_path": file_path
            }
            
            logger.info(f"Successfully downloaded page from {url}")
            return (file_path, metadata)
            
        except Exception as e:
            logger.warning(f"Failed to download from URL {url}: {e}")
            return None
    
    def import_pages_to_repository(self, downloaded_files):
        """
        Import downloaded pages to the repository.
        
        Args:
            downloaded_files: List of (file_path, metadata) tuples
            
        Returns:
            List of page IDs
        """
        logger.info(f"Importing {len(downloaded_files)} pages to repository...")
        page_ids = []
        
        for file_path, metadata in downloaded_files:
            try:
                # Parse publication date
                publication_date = metadata.get("date", "")
                try:
                    # Try to convert to YYYY-MM-DD format if not already
                    if len(publication_date) == 8:  # YYYYMMDD
                        publication_date = f"{publication_date[:4]}-{publication_date[4:6]}-{publication_date[6:8]}"
                except Exception:
                    pass
                
                # Add page to repository
                page_id = self.db_manager.add_newspaper_page(
                    source_name=metadata.get("title", "Unknown"),
                    publication_date=publication_date,
                    page_number=int(metadata.get("sequence", 1)),
                    filename=os.path.basename(file_path),
                    origin="chroniclingamerica",
                    metadata={
                        "lccn": metadata.get("lccn", ""),
                        "pdf_url": metadata.get("pdf_url", ""),
                        "jp2_url": metadata.get("jp2_url", "")
                    }
                )
                
                # Save original file to repository
                original_path = self.file_manager.save_original_page(
                    source_file_path=file_path,
                    origin="chroniclingamerica",
                    source_name=metadata.get("title", "Unknown"),
                    publication_date=publication_date,
                    page_number=int(metadata.get("sequence", 1))
                )
                
                # Update page record with image path
                self.db_manager.update_newspaper_page(
                    page_id,
                    image_path=original_path
                )
                
                page_ids.append(page_id)
                logger.info(f"Imported page {page_id}: {metadata.get('title', '')} {publication_date}")
                
            except Exception as e:
                logger.error(f"Error importing page {file_path}: {e}")
        
        logger.info(f"Imported {len(page_ids)} pages to repository")
        
        # Update test results
        self.test_results["import"] = {
            "success": len(page_ids) > 0,
            "count": len(page_ids),
            "page_ids": page_ids,
            "message": f"Imported {len(page_ids)} of {len(downloaded_files)} pages"
        }
        
        return page_ids
    
    def process_pages_with_background_service(self, page_ids):
        """
        Process pages with the background service.
        
        Args:
            page_ids: List of page IDs to process
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing {len(page_ids)} pages with background service...")
        
        # Start timer
        start_time = time.time()
        
        # Register a progress callback
        self.background_service.register_progress_callback(self._progress_callback)
        
        # Add tasks to the background service
        tasks = []
        for page_id in page_ids:
            # Add OCR task
            ocr_task_id = self.background_service.add_task(
                page_id=str(page_id),
                operation="ocr",
                parameters={"save_segments": True},
                priority=1
            )
            tasks.append((ocr_task_id, "ocr", page_id))
            
            # Add segmentation task
            segment_task_id = self.background_service.add_task(
                page_id=str(page_id),
                operation="segment",
                priority=2
            )
            tasks.append((segment_task_id, "segment", page_id))
            
            # Add article extraction task
            extract_task_id = self.background_service.add_task(
                page_id=str(page_id),
                operation="extract_articles",
                priority=3
            )
            tasks.append((extract_task_id, "extract_articles", page_id))
        
        # Start the background service
        logger.info("Starting background service...")
        self.background_service.start()
        
        # Wait for all tasks to complete
        completed = False
        timeout = 600  # 10 minutes max
        elapsed = 0
        check_interval = 5  # Check every 5 seconds
        
        while not completed and elapsed < timeout:
            # Sleep for the check interval
            time.sleep(check_interval)
            elapsed += check_interval
            
            # Get service status
            status = self.background_service.get_queue_status()
            
            # Check if all tasks are completed
            if status["queue_size"] == 0 and len(status["in_progress_tasks"]) == 0:
                completed = True
                break
            
            # Print progress
            logger.info(f"Progress: {status['queue_size']} tasks in queue, "
                      f"{len(status['in_progress_tasks'])} tasks in progress")
        
        # Stop the background service
        logger.info("Stopping background service...")
        self.background_service.stop()
        
        # Unregister callback
        self.background_service.unregister_progress_callback(self._progress_callback)
        
        # Get processing results
        processing_time = time.time() - start_time
        
        if not completed:
            logger.error(f"Processing timed out after {timeout} seconds")
            self.test_results["processing"] = {
                "success": False,
                "message": f"Processing timed out after {timeout} seconds",
                "time_taken": processing_time
            }
        else:
            logger.info(f"Processing completed in {processing_time:.2f} seconds")
            
            # Get statistics
            stats = self.background_service.stats
            
            self.test_results["processing"] = {
                "success": True,
                "tasks_processed": stats["tasks_processed"],
                "tasks_succeeded": stats["tasks_succeeded"],
                "tasks_failed": stats["tasks_failed"],
                "tasks_retried": stats["tasks_retried"],
                "time_taken": processing_time,
                "message": f"Processed {stats['tasks_processed']} tasks "
                         f"({stats['tasks_succeeded']} succeeded, {stats['tasks_failed']} failed)"
            }
        
        return self.test_results["processing"]
    
    def _progress_callback(self, update):
        """
        Callback for progress updates from the background service.
        
        Args:
            update: Progress update dictionary
        """
        update_type = update["type"]
        data = update["data"]
        
        if update_type == "task_started":
            logger.info(f"Task started: {data.get('task_id', 'unknown')} "
                      f"({data.get('page_id', 'unknown')} - {data.get('operation', 'unknown')})")
        
        elif update_type == "task_completed":
            logger.info(f"Task completed: {data.get('task_id', 'unknown')} "
                      f"({data.get('page_id', 'unknown')} - {data.get('operation', 'unknown')})")
            
            # Store result in test results
            operation = data.get('operation', 'unknown')
            if operation in self.test_results:
                if "tasks" not in self.test_results[operation]:
                    self.test_results[operation]["tasks"] = []
                
                self.test_results[operation]["tasks"].append({
                    "task_id": data.get('task_id', 'unknown'),
                    "page_id": data.get('page_id', 'unknown'),
                    "result": data.get('result', {}),
                    "processing_time": data.get('processing_time', 0)
                })
        
        elif update_type == "task_failed":
            logger.error(f"Task failed: {data.get('task_id', 'unknown')} "
                       f"({data.get('page_id', 'unknown')} - {data.get('operation', 'unknown')}): "
                       f"{data.get('error', 'Unknown error')}")
            
            # Store error in test results
            operation = data.get('operation', 'unknown')
            if operation in self.test_results:
                if "errors" not in self.test_results[operation]:
                    self.test_results[operation]["errors"] = []
                
                self.test_results[operation]["errors"].append({
                    "task_id": data.get('task_id', 'unknown'),
                    "page_id": data.get('page_id', 'unknown'),
                    "error": data.get('error', 'Unknown error'),
                    "retries": data.get('retries', 0)
                })
        
        elif update_type == "task_progress":
            # Only log progress for every 20%
            progress = data.get('progress', 0) * 100
            if progress % 20 < 1:  # Log at approx 0%, 20%, 40%, 60%, 80%, 100%
                logger.info(f"Task progress: {data.get('task_id', 'unknown')} "
                          f"({data.get('page_id', 'unknown')} - {data.get('operation', 'unknown')}): "
                          f"{progress:.0f}% - {data.get('message', '')}")
    
    def verify_results(self, page_ids):
        """
        Verify the results of the processing.
        
        Args:
            page_ids: List of page IDs that were processed
            
        Returns:
            Dictionary with verification results
        """
        logger.info("Verifying processing results...")
        
        verification_results = {
            "pages_checked": len(page_ids),
            "pages_success": 0,
            "pages_with_ocr": 0,
            "pages_with_segments": 0,
            "pages_with_articles": 0,
            "total_segments": 0,
            "total_articles": 0,
            "details": []
        }
        
        for page_id in page_ids:
            page_result = {
                "page_id": page_id,
                "success": False,
                "has_ocr": False,
                "has_segments": False,
                "has_articles": False,
                "segment_count": 0,
                "article_count": 0
            }
            
            try:
                # Get page information
                page = self.db_manager.get_newspaper_page(page_id)
                if not page:
                    logger.error(f"Page {page_id} not found in database")
                    verification_results["details"].append(page_result)
                    continue
                
                # Check OCR
                page_result["has_ocr"] = page.get("ocr_status") == "completed"
                
                # Check segments
                segments = self.db_manager.get_segments_for_page(page_id)
                page_result["has_segments"] = len(segments) > 0
                page_result["segment_count"] = len(segments)
                verification_results["total_segments"] += len(segments)
                
                # Check articles
                articles = self.db_manager.get_articles_for_page(page_id)
                page_result["has_articles"] = len(articles) > 0
                page_result["article_count"] = len(articles)
                verification_results["total_articles"] += len(articles)
                
                # Determine overall success
                page_result["success"] = (
                    page_result["has_ocr"] and 
                    page_result["has_segments"] and 
                    page_result["has_articles"]
                )
                
                # Update counts
                if page_result["success"]:
                    verification_results["pages_success"] += 1
                if page_result["has_ocr"]:
                    verification_results["pages_with_ocr"] += 1
                if page_result["has_segments"]:
                    verification_results["pages_with_segments"] += 1
                if page_result["has_articles"]:
                    verification_results["pages_with_articles"] += 1
                
                verification_results["details"].append(page_result)
                
                logger.info(f"Page {page_id} verification: "
                          f"OCR {'✓' if page_result['has_ocr'] else '✗'}, "
                          f"Segments {page_result['segment_count']}, "
                          f"Articles {page_result['article_count']}")
                
            except Exception as e:
                logger.error(f"Error verifying page {page_id}: {e}")
                verification_results["details"].append(page_result)
        
        # Calculate success rate
        success_rate = (verification_results["pages_success"] / 
                        verification_results["pages_checked"] * 100
                       ) if verification_results["pages_checked"] > 0 else 0
        
        verification_results["success_rate"] = success_rate
        verification_results["success"] = success_rate >= 50  # At least 50% success
        
        if verification_results["success"]:
            verification_results["message"] = (
                f"Verification successful: {verification_results['pages_success']} out of "
                f"{verification_results['pages_checked']} pages were processed correctly "
                f"({success_rate:.1f}%)"
            )
        else:
            verification_results["message"] = (
                f"Verification failed: Only {verification_results['pages_success']} out of "
                f"{verification_results['pages_checked']} pages were processed correctly "
                f"({success_rate:.1f}%)"
            )
        
        logger.info(verification_results["message"])
        
        # Update test results
        self.test_results["verification"] = verification_results
        
        return verification_results
    
    def run_workflow_test(self):
        """
        Run the complete workflow test.
        
        Returns:
            Dictionary with test results
        """
        try:
            logger.info("Starting workflow test...")
            
            # Step 1: Download sample pages
            downloaded_files = self.download_sample_pages(count=2)
            if not downloaded_files:
                logger.error("Download failed, aborting test")
                self.test_results["overall"] = {
                    "success": False,
                    "message": "Download failed, aborting test",
                    "start_time": self.test_results["overall"]["start_time"],
                    "end_time": datetime.now().isoformat()
                }
                return self.test_results
            
            # Step 2: Import pages to repository
            page_ids = self.import_pages_to_repository(downloaded_files)
            if not page_ids:
                logger.error("Import failed, aborting test")
                self.test_results["overall"] = {
                    "success": False,
                    "message": "Import failed, aborting test",
                    "start_time": self.test_results["overall"]["start_time"],
                    "end_time": datetime.now().isoformat()
                }
                return self.test_results
            
            # Step 3: Process pages with background service
            processing_results = self.process_pages_with_background_service(page_ids)
            if not processing_results["success"]:
                logger.error("Processing failed")
                self.test_results["overall"] = {
                    "success": False,
                    "message": f"Processing failed: {processing_results['message']}",
                    "start_time": self.test_results["overall"]["start_time"],
                    "end_time": datetime.now().isoformat()
                }
                return self.test_results
            
            # Step 4: Verify results
            verification_results = self.verify_results(page_ids)
            
            # Final result
            self.test_results["overall"] = {
                "success": verification_results["success"],
                "message": verification_results["message"],
                "start_time": self.test_results["overall"]["start_time"],
                "end_time": datetime.now().isoformat(),
                "total_time": 0  # Will be calculated below
            }
            
            # Calculate total time
            try:
                start = datetime.fromisoformat(self.test_results["overall"]["start_time"])
                end = datetime.fromisoformat(self.test_results["overall"]["end_time"])
                total_seconds = (end - start).total_seconds()
                self.test_results["overall"]["total_time"] = total_seconds
                
                logger.info(f"Workflow test completed in {total_seconds:.2f} seconds")
            except Exception as e:
                logger.error(f"Error calculating total time: {e}")
            
            return self.test_results
            
        except Exception as e:
            logger.error(f"Error in workflow test: {e}")
            self.test_results["overall"] = {
                "success": False,
                "message": f"Workflow test error: {str(e)}",
                "start_time": self.test_results["overall"]["start_time"],
                "end_time": datetime.now().isoformat()
            }
            return self.test_results
    
    def save_results(self, output_path=None):
        """
        Save test results to a JSON file.
        
        Args:
            output_path: Path to save results (defaults to test_results.json in base_dir)
            
        Returns:
            Path to the saved file
        """
        if output_path is None:
            output_path = os.path.join(self.base_dir, "test_results.json")
        
        try:
            with open(output_path, "w") as f:
                json.dump(self.test_results, f, indent=2)
            
            logger.info(f"Test results saved to {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"Error saving test results: {e}")
            return None
    
    def print_summary(self):
        """Print a summary of the test results."""
        if not self.test_results["overall"].get("end_time"):
            logger.warning("Test has not completed yet")
            return
        
        print("\n" + "="*80)
        print("NEWSPAPER REPOSITORY WORKFLOW TEST SUMMARY")
        print("="*80)
        
        # Overall result
        overall = self.test_results["overall"]
        status = "✓ PASSED" if overall["success"] else "✗ FAILED"
        print(f"\nOverall Result: {status}")
        print(f"Message: {overall['message']}")
        
        try:
            start = datetime.fromisoformat(overall["start_time"])
            end = datetime.fromisoformat(overall["end_time"])
            duration = end - start
            print(f"Duration: {duration}")
        except:
            pass
        
        # Download
        print("\n" + "-"*80)
        print("STEP 1: DOWNLOAD")
        download = self.test_results.get("download", {})
        status = "✓ PASSED" if download.get("success", False) else "✗ FAILED"
        print(f"Result: {status}")
        print(f"Downloaded: {download.get('count', 0)} pages")
        print(f"Time taken: {download.get('time_taken', 0):.2f} seconds")
        
        # Import
        print("\n" + "-"*80)
        print("STEP 2: IMPORT")
        imp = self.test_results.get("import", {})
        status = "✓ PASSED" if imp.get("success", False) else "✗ FAILED"
        print(f"Result: {status}")
        print(f"Imported: {imp.get('count', 0)} pages")
        print(f"Page IDs: {imp.get('page_ids', [])}")
        
        # Processing
        print("\n" + "-"*80)
        print("STEP 3: PROCESSING")
        proc = self.test_results.get("processing", {})
        status = "✓ PASSED" if proc.get("success", False) else "✗ FAILED"
        print(f"Result: {status}")
        print(f"Tasks processed: {proc.get('tasks_processed', 0)}")
        print(f"Tasks succeeded: {proc.get('tasks_succeeded', 0)}")
        print(f"Tasks failed: {proc.get('tasks_failed', 0)}")
        print(f"Tasks retried: {proc.get('tasks_retried', 0)}")
        print(f"Time taken: {proc.get('time_taken', 0):.2f} seconds")
        
        # Verification
        print("\n" + "-"*80)
        print("STEP 4: VERIFICATION")
        ver = self.test_results.get("verification", {})
        status = "✓ PASSED" if ver.get("success", False) else "✗ FAILED"
        print(f"Result: {status}")
        print(f"Pages checked: {ver.get('pages_checked', 0)}")
        print(f"Pages successful: {ver.get('pages_success', 0)}")
        print(f"Pages with OCR: {ver.get('pages_with_ocr', 0)}")
        print(f"Pages with segments: {ver.get('pages_with_segments', 0)}")
        print(f"Pages with articles: {ver.get('pages_with_articles', 0)}")
        print(f"Total segments: {ver.get('total_segments', 0)}")
        print(f"Total articles: {ver.get('total_articles', 0)}")
        print(f"Success rate: {ver.get('success_rate', 0):.1f}%")
        
        # Print details for each page
        if "details" in ver:
            print("\nPage details:")
            for page in ver["details"]:
                status = "✓" if page.get("success", False) else "✗"
                print(f"  Page {page.get('page_id', 'unknown')}: {status} "
                      f"OCR: {'✓' if page.get('has_ocr', False) else '✗'}, "
                      f"Segments: {page.get('segment_count', 0)}, "
                      f"Articles: {page.get('article_count', 0)}")
        
        print("\n" + "="*80)


def main():
    """Main function to run the test workflow."""
    parser = argparse.ArgumentParser(description="Test workflow for newspaper repository")
    parser.add_argument("--base-dir", default="./test_repository",
                      help="Base directory for test repository")
    parser.add_argument("--db-path", default=None,
                      help="Path to repository database (defaults to {base_dir}/repository.db)")
    parser.add_argument("--results", default=None,
                      help="Path to save test results (defaults to {base_dir}/test_results.json)")
    
    args = parser.parse_args()
    
    # Create test workflow
    test = TestWorkflow(base_dir=args.base_dir, db_path=args.db_path)
    
    # Run test
    results = test.run_workflow_test()
    
    # Save results
    test.save_results(args.results)
    
    # Print summary
    test.print_summary()
    
    # Return success/failure
    return 0 if results["overall"]["success"] else 1


if __name__ == "__main__":
    sys.exit(main())