#!/usr/bin/env python3
"""
ChroniclingAmerica Bulk Download Test Script

A standalone script to test bulk downloading from the Chronicling America API.
This script doesn't depend on any other parts of the Nova database system.

Features:
- Search for all pages from a specific newspaper for a given month
- Respect rate limits (10 bulk requests per 10 minutes)
- Detailed logging of all requests, responses, and errors
- Save downloaded files to a temporary folder
- Print a summary of successful and failed downloads
- Command-line parameters for newspaper LCCN, year, and month
"""

import argparse
import datetime
import json
import logging
import os
import requests
import sys
import time
from queue import Queue
from threading import Thread, Lock
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, quote

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bulk_download.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# API Constants
BASE_URL = "https://www.loc.gov/collections/chronicling-america"
API_URL = f"{BASE_URL}/search/"
CONTENT_TYPES = ["image_jpeg", "image_jp2", "pdf", "ocr_txt", "ocr_xml"]

# Rate limiting constants
MAX_REQUESTS_PER_WINDOW = 10
RATE_WINDOW_SECONDS = 600  # 10 minutes
REQUEST_BUFFER_TIME = 1.0  # Seconds to wait between requests


class RateLimiter:
    """Simple rate limiter to respect the API's limits."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in the time window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_timestamps = []
        self.lock = Lock()
    
    def wait_if_needed(self) -> float:
        """
        Wait if we've exceeded the rate limit.
        
        Returns:
            Time waited in seconds
        """
        with self.lock:
            now = time.time()
            
            # Remove timestamps older than the window
            window_start = now - self.window_seconds
            self.request_timestamps = [ts for ts in self.request_timestamps if ts >= window_start]
            
            # If we haven't reached the limit, we can proceed
            if len(self.request_timestamps) < self.max_requests:
                self.request_timestamps.append(now)
                return 0
            
            # Calculate how long to wait
            oldest_timestamp = self.request_timestamps[0]
            wait_time = oldest_timestamp + self.window_seconds - now
            
            if wait_time > 0:
                logger.info(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                
                # Add the new timestamp after waiting
                self.request_timestamps.pop(0)  # Remove the oldest
                self.request_timestamps.append(time.time())
                
                return wait_time
            else:
                # If wait time is negative, we can proceed
                self.request_timestamps.pop(0)  # Remove the oldest
                self.request_timestamps.append(now)
                return 0


class ChroniclingAmericaAPI:
    """Simple client for the Chronicling America API."""
    
    def __init__(self, output_dir: str):
        """
        Initialize the API client.
        
        Args:
            output_dir: Directory to save downloaded files
        """
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BulkDownloadTest/1.0 (https://github.com/yourusername/nova; your@email.com)"
        })
        self.rate_limiter = RateLimiter(MAX_REQUESTS_PER_WINDOW, RATE_WINDOW_SECONDS)
    
    def search_pages(self, lccn: str, year: int, month: int) -> List[Dict[str, Any]]:
        """
        Search for newspaper pages matching the given criteria.
        
        Args:
            lccn: Library of Congress Control Number for the newspaper
            year: Year to search for
            month: Month to search for
            
        Returns:
            List of page information dictionaries
        """
        # Format date strings
        date_start = f"{year}-{month:02d}-01"
        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1
        date_end = f"{next_year}-{next_month:02d}-01"
        
        logger.info(f"Searching for pages in {lccn} from {date_start} to {date_end}")
        
        # API parameters
        params = {
            'fo': 'json',
            'at': 'results',
            'c': 100,  # Maximum results per page
            'sp': 1,   # Start page
            'q': f"lccn:{lccn}",
            'dates': f"{date_start}/{date_end}",
            'format': 'newspapers'
        }
        
        all_results = []
        more_results = True
        page = 1
        
        while more_results:
            # Apply rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Make the request
            logger.info(f"Requesting page {page} of search results")
            try:
                params['sp'] = page
                response = self.session.get(API_URL, params=params)
                response.raise_for_status()
                
                # Log the request details
                logger.debug(f"GET {response.url}")
                logger.debug(f"Response status: {response.status_code}")
                
                # Parse the response
                data = response.json()
                
                # Extract results
                results = data.get('results', [])
                all_results.extend(results)
                
                # Check if there are more pages
                total_results = data.get('pagination', {}).get('total', 0)
                total_pages = (total_results + params['c'] - 1) // params['c']
                
                logger.info(f"Received {len(results)} results (page {page}/{total_pages})")
                
                if page >= total_pages or not results:
                    more_results = False
                else:
                    page += 1
                    # Add a small delay between requests
                    time.sleep(REQUEST_BUFFER_TIME)
                
            except requests.RequestException as e:
                logger.error(f"Error searching for pages: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response: {e.response.text}")
                more_results = False
        
        return all_results
    
    def download_page_contents(self, page_info: Dict[str, Any], content_types: List[str]) -> Dict[str, str]:
        """
        Download the specified content types for a newspaper page.
        
        Args:
            page_info: Page information from the search results
            content_types: List of content types to download
            
        Returns:
            Dictionary mapping content types to downloaded file paths
        """
        downloads = {}
        
        # Extract page ID and title for file naming
        item_id = page_info.get('id', '').split('/')[-1]
        title = page_info.get('title', 'unknown')
        date = page_info.get('date', 'unknown')
        
        # Clean the title for use in filenames
        safe_title = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in title)
        safe_title = safe_title[:50]  # Limit length
        
        # Create directory for this page
        page_dir = os.path.join(self.output_dir, f"{date}_{item_id}")
        os.makedirs(page_dir, exist_ok=True)
        
        # Get resources available for this page
        resources = page_info.get('resources', [])
        
        for content_type in content_types:
            # Find the URL for this content type
            resource_url = None
            for resource in resources:
                if resource.get('type') == content_type:
                    resource_url = resource.get('url')
                    break
            
            if not resource_url:
                logger.warning(f"Content type {content_type} not available for page {item_id}")
                continue
            
            # Determine file extension
            if content_type == 'image_jpeg':
                ext = 'jpg'
            elif content_type == 'image_jp2':
                ext = 'jp2'
            elif content_type == 'pdf':
                ext = 'pdf'
            elif content_type == 'ocr_txt':
                ext = 'txt'
            elif content_type == 'ocr_xml':
                ext = 'xml'
            else:
                ext = 'dat'
            
            # Construct output filename
            output_file = os.path.join(page_dir, f"{safe_title}_{content_type}.{ext}")
            
            # Apply rate limiting
            self.rate_limiter.wait_if_needed()
            
            # Download the file
            logger.info(f"Downloading {content_type} for page {item_id}")
            try:
                response = self.session.get(resource_url, stream=True)
                response.raise_for_status()
                
                # Log the request details
                logger.debug(f"GET {response.url}")
                logger.debug(f"Response status: {response.status_code}")
                
                # Save the file
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                downloads[content_type] = output_file
                logger.info(f"Successfully downloaded {content_type} to {output_file}")
                
                # Add a small delay between requests
                time.sleep(REQUEST_BUFFER_TIME)
                
            except requests.RequestException as e:
                logger.error(f"Error downloading {content_type} for page {item_id}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response: {e.response.text}")
        
        return downloads


class DownloadWorker(Thread):
    """Worker thread for downloading content."""
    
    def __init__(self, api: ChroniclingAmericaAPI, queue: Queue, content_types: List[str], 
                 results: Dict[str, Dict[str, Any]]):
        """
        Initialize the download worker.
        
        Args:
            api: ChroniclingAmericaAPI instance
            queue: Queue of pages to download
            content_types: List of content types to download
            results: Dictionary to store download results
        """
        super().__init__()
        self.api = api
        self.queue = queue
        self.content_types = content_types
        self.results = results
        self.lock = Lock()
    
    def run(self):
        """Process items from the queue until it's empty."""
        while True:
            try:
                # Get the next page from the queue
                page_info = self.queue.get(block=False)
            except:
                # Queue is empty
                break
            
            try:
                # Download the content
                item_id = page_info.get('id', '').split('/')[-1]
                downloads = self.api.download_page_contents(page_info, self.content_types)
                
                # Store the results
                with self.lock:
                    self.results[item_id] = {
                        'page_info': page_info,
                        'downloads': downloads,
                        'success': len(downloads) > 0,
                        'timestamp': datetime.datetime.now().isoformat()
                    }
            except Exception as e:
                logger.error(f"Error processing page: {e}")
                
                # Store the error
                item_id = page_info.get('id', '').split('/')[-1]
                with self.lock:
                    self.results[item_id] = {
                        'page_info': page_info,
                        'error': str(e),
                        'success': False,
                        'timestamp': datetime.datetime.now().isoformat()
                    }
            
            finally:
                # Mark the task as done
                self.queue.task_done()


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Bulk download test from Chronicling America')
    parser.add_argument('--lccn', required=True, help='Library of Congress Control Number')
    parser.add_argument('--year', type=int, required=True, help='Year to download')
    parser.add_argument('--month', type=int, required=True, help='Month to download (1-12)')
    parser.add_argument('--output', default='./downloads', help='Output directory')
    parser.add_argument('--content-types', nargs='+', default=['image_jpeg', 'ocr_txt'],
                        choices=CONTENT_TYPES, help='Content types to download')
    parser.add_argument('--workers', type=int, default=3, help='Number of download worker threads')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not 1 <= args.month <= 12:
        logger.error("Month must be between 1 and 12")
        return 1
    
    if args.year < 1800 or args.year > datetime.datetime.now().year:
        logger.warning(f"Year {args.year} seems unusual, but proceeding anyway")
    
    # Create output directory
    output_dir = os.path.join(args.output, f"{args.lccn}_{args.year}_{args.month:02d}")
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting bulk download for {args.lccn} ({args.year}-{args.month:02d})")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Content types: {args.content_types}")
    
    # Initialize API client
    api = ChroniclingAmericaAPI(output_dir)
    
    # Search for pages
    start_time = time.time()
    pages = api.search_pages(args.lccn, args.year, args.month)
    search_time = time.time() - start_time
    
    if not pages:
        logger.error("No pages found matching the criteria")
        return 1
    
    logger.info(f"Found {len(pages)} pages. Search completed in {search_time:.2f} seconds")
    
    # Create download queue
    download_queue = Queue()
    for page in pages:
        download_queue.put(page)
    
    # Create workers
    download_results = {}
    workers = []
    for _ in range(min(args.workers, len(pages))):
        worker = DownloadWorker(api, download_queue, args.content_types, download_results)
        worker.start()
        workers.append(worker)
    
    # Wait for all downloads to complete
    download_start_time = time.time()
    for worker in workers:
        worker.join()
    download_time = time.time() - download_start_time
    
    # Calculate statistics
    successful = sum(1 for r in download_results.values() if r.get('success', False))
    failed = len(download_results) - successful
    
    # Content type statistics
    content_counts = {ct: 0 for ct in args.content_types}
    for result in download_results.values():
        if 'downloads' in result:
            for content_type in result['downloads']:
                content_counts[content_type] = content_counts.get(content_type, 0) + 1
    
    # Print summary
    print("\n" + "="*50)
    print(f"DOWNLOAD SUMMARY for {args.lccn} ({args.year}-{args.month:02d})")
    print("="*50)
    print(f"Total pages found: {len(pages)}")
    print(f"Successfully processed: {successful} pages")
    print(f"Failed: {failed} pages")
    print("\nContent statistics:")
    for content_type, count in content_counts.items():
        print(f"  - {content_type}: {count} files")
    
    print("\nTime statistics:")
    print(f"  - Search time: {search_time:.2f} seconds")
    print(f"  - Download time: {download_time:.2f} seconds")
    print(f"  - Total time: {search_time + download_time:.2f} seconds")
    
    print(f"\nFiles saved to: {output_dir}")
    
    # Save results to JSON
    results_file = os.path.join(output_dir, "download_results.json")
    with open(results_file, 'w') as f:
        json.dump({
            "newspaper": args.lccn,
            "year": args.year,
            "month": args.month,
            "total_pages": len(pages),
            "successful": successful,
            "failed": failed,
            "content_counts": content_counts,
            "search_time": search_time,
            "download_time": download_time,
            "total_time": search_time + download_time,
            "results": download_results
        }, f, indent=2)
    
    print(f"Detailed results saved to: {results_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())