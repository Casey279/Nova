#!/usr/bin/env python3
"""
Direct URL Downloader for ChroniclingAmerica Seattle Post-Intelligencer (1892)

This specialized downloader:
1. Generates dates for 1892 excluding Mondays (P-I wasn't published on Mondays)
2. Constructs direct URLs for each date following the ChroniclingAmerica pattern
3. Downloads JP2 images, PDF files, and OCR text for each page
4. Uses conservative rate limiting and smart retry logic
5. Implements comprehensive checkpointing and resume capability
6. Organizes downloads by date for easy access
"""

import argparse
import logging
import os
import datetime
import calendar
import json
import time
import requests
import pickle
import sys
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Set, Optional, Any, Union, Generator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
API_URL = "https://chroniclingamerica.loc.gov"
DEFAULT_OUTPUT_DIR = "./chron_america_pi"
DEFAULT_WORKERS = 2
DEFAULT_REQUEST_DELAY = 5  # seconds between requests
MAX_RETRIES = 3
CHECKPOINT_INTERVAL = 5  # minutes
DEFAULT_MAX_PAGES = 20  # maximum pages to try per issue

class DirectUrlDownloader:
    """Specialized downloader for ChroniclingAmerica using direct URL construction"""
    
    def __init__(self, output_dir, lccn="sn83045604", year=1892, 
                 months=None, workers=DEFAULT_WORKERS, request_delay=DEFAULT_REQUEST_DELAY,
                 sample=False, max_pages=DEFAULT_MAX_PAGES):
        """
        Initialize the downloader
        
        Args:
            output_dir: Directory to save downloaded files
            lccn: Library of Congress Control Number for the newspaper
            year: Year to download
            months: List of month numbers (1-12) to download
            workers: Number of concurrent download workers
            request_delay: Delay between requests in seconds
            sample: If True, only download a few dates for testing
            max_pages: Maximum page numbers to try per issue
        """
        self.output_dir = Path(output_dir)
        self.lccn = lccn
        self.year = year
        self.months = months if months else list(range(1, 13))  # Default: all months
        self.workers = workers
        self.request_delay = request_delay
        self.sample = sample
        self.max_pages = max_pages
        
        # Create session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ChroniclingAmericaDownloader/4.0 (research project)",
            "Accept": "text/html,application/xhtml+xml,application/xml,image/jpeg,*/*"
        })
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Checkpoint state
        self.checkpoint_file = self.output_dir / f"{lccn}_{year}_checkpoint.pkl"
        self.last_checkpoint_time = time.time()
        self.checkpoint_data = {
            "dates_checked": set(),  # Dates we've already checked
            "successful_dates": set(),  # Dates that have issues
            "downloaded_files": {},  # Dictionary mapping dates to lists of files
            "total_files_downloaded": 0,
            "last_request_time": 0,  # Last time a request was made
            "start_time": time.time(),
            "config": {
                "lccn": lccn,
                "year": year,
                "months": months,
                "sample": sample,
                "max_pages": max_pages
            }
        }
        
        # Load existing checkpoint if available
        self._load_checkpoint()
    
    def _save_checkpoint(self, force=False):
        """
        Save checkpoint data to disk
        
        Args:
            force: If True, save even if interval hasn't elapsed
        """
        now = time.time()
        if force or (now - self.last_checkpoint_time > CHECKPOINT_INTERVAL * 60):
            try:
                # Update timestamp
                self.checkpoint_data["last_updated"] = datetime.datetime.now().isoformat()
                self.checkpoint_data["elapsed_time"] = now - self.checkpoint_data["start_time"]
                
                with open(self.checkpoint_file, 'wb') as f:
                    pickle.dump(self.checkpoint_data, f)
                
                logger.info(f"Checkpoint saved to {self.checkpoint_file}")
                self.last_checkpoint_time = now
                
                # Also save a human-readable summary
                summary_file = self.output_dir / f"{self.lccn}_{self.year}_progress.json"
                summary = {
                    "lccn": self.lccn,
                    "year": self.year,
                    "months": self.months,
                    "dates_checked": len(self.checkpoint_data["dates_checked"]),
                    "successful_dates": len(self.checkpoint_data["successful_dates"]),
                    "total_files_downloaded": self.checkpoint_data["total_files_downloaded"],
                    "elapsed_time": now - self.checkpoint_data["start_time"],
                    "last_updated": datetime.datetime.now().isoformat()
                }
                
                with open(summary_file, 'w') as f:
                    json.dump(summary, f, indent=2)
                
            except Exception as e:
                logger.error(f"Error saving checkpoint: {str(e)}")
    
    def _load_checkpoint(self):
        """Load checkpoint data if available"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'rb') as f:
                    loaded_data = pickle.load(f)
                
                # Verify this is the same configuration
                config = loaded_data.get("config", {})
                if (config.get("lccn") == self.lccn and
                    config.get("year") == self.year):
                    
                    # Configuration matches, load the data
                    self.checkpoint_data = loaded_data
                    logger.info(f"Resumed from checkpoint: {len(self.checkpoint_data['dates_checked'])} "
                               f"dates checked, {len(self.checkpoint_data['successful_dates'])} "
                               f"successful dates, {self.checkpoint_data['total_files_downloaded']} files downloaded")
                    
                    # Don't reset the start time from the checkpoint
                    elapsed = time.time() - self.checkpoint_data["start_time"]
                    logger.info(f"Elapsed time: {elapsed/60:.1f} minutes")
                else:
                    logger.info("Configuration changed, starting fresh download")
            except Exception as e:
                logger.error(f"Error loading checkpoint: {str(e)}")
                logger.info("Starting fresh download")
    
    def wait_if_needed(self):
        """Wait to respect rate limiting"""
        now = time.time()
        last_request = self.checkpoint_data["last_request_time"]
        
        # Add some randomness to the delay
        delay = self.request_delay * (0.8 + random.random() * 0.4)  # ±20% variation
        
        if now - last_request < delay:
            wait_time = delay - (now - last_request)
            time.sleep(wait_time)
        
        # Update last request time
        self.checkpoint_data["last_request_time"] = time.time()
    
    def make_request(self, url, method="GET", stream=False, retry_count=MAX_RETRIES):
        """
        Make a request with rate limiting and retry logic
        
        Args:
            url: URL to request
            method: HTTP method (GET, HEAD, etc.)
            stream: Whether to stream the response
            retry_count: Number of retries on failure
            
        Returns:
            Response object or None on failure
        """
        self.wait_if_needed()
        
        for attempt in range(retry_count + 1):
            try:
                response = self.session.request(
                    method=method, 
                    url=url, 
                    stream=stream,
                    timeout=30
                )
                
                # For 404 errors, we can just return None immediately - no need to retry
                # This is expected for checking URLs that don't exist
                if response.status_code == 404:
                    return None
                
                # Return response if successful
                if response.status_code == 200:
                    return response
                
                # Handle specific error codes
                if response.status_code in (429, 503, 504, 502):
                    # Rate limit or server busy, back off
                    
                    # If it's not our last attempt, wait and try again
                    if attempt < retry_count:
                        backoff = min(2 ** attempt * 5 + random.uniform(0, 3), 60)
                        logger.warning(f"Request failed with status {response.status_code}, "
                                    f"retrying in {backoff:.2f} seconds (attempt {attempt+1}/{retry_count})")
                        time.sleep(backoff)
                        continue
                
                logger.error(f"Request failed with status {response.status_code}: {url}")
                return None
                
            except (requests.RequestException, ConnectionError, TimeoutError) as e:
                if attempt < retry_count:
                    backoff = min(2 ** attempt * 5 + random.uniform(0, 3), 60)
                    logger.warning(f"Request error: {str(e)}, retrying in {backoff:.2f} seconds "
                                 f"(attempt {attempt+1}/{retry_count})")
                    time.sleep(backoff)
                else:
                    logger.error(f"Request failed after {retry_count} retries: {url}")
                    logger.error(f"Error: {str(e)}")
                    return None
        
        return None
    
    def generate_dates(self) -> Generator[datetime.date, None, None]:
        """
        Generate dates for 1892, excluding Mondays (Seattle P-I wasn't published on Mondays)
        
        Returns:
            Generator yielding datetime.date objects
        """
        # Generate all dates for the months we care about
        for month in self.months:
            # Get number of days in this month
            _, days_in_month = calendar.monthrange(self.year, month)
            
            # Generate dates for this month
            for day in range(1, days_in_month + 1):
                date = datetime.date(self.year, month, day)
                
                # Skip Mondays (weekday 0)
                if date.weekday() != 0:
                    yield date
    
    def download_file(self, url, output_path):
        """
        Download a file
        
        Args:
            url: URL to download
            output_path: Path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file already exists and skip if it does
        if output_path.exists():
            file_size = output_path.stat().st_size
            if file_size > 0:
                logger.debug(f"File already exists ({file_size} bytes), skipping: {output_path}")
                return True
            else:
                logger.warning(f"File exists but is empty, re-downloading: {output_path}")
        
        # First, check if the file exists with a HEAD request
        head_response = self.make_request(url, method="HEAD")
        if not head_response:
            logger.warning(f"File not found: {url}")
            return False
        
        # Download the file
        response = self.make_request(url, stream=True)
        if not response:
            return False
        
        try:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded: {url} -> {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving file {url}: {str(e)}")
            # If the file was created but is incomplete, remove it
            if output_path.exists():
                output_path.unlink()
            return False
    
    def process_date(self, date):
        """
        Process a single date, checking for newspaper pages and downloading files
        
        Args:
            date: Date to process (datetime.date)
            
        Returns:
            Dictionary with information about downloaded files
        """
        date_str = date.strftime("%Y-%m-%d")
        
        # Skip if we've already checked this date
        if date_str in self.checkpoint_data["dates_checked"]:
            if date_str in self.checkpoint_data["successful_dates"]:
                logger.debug(f"Date {date_str} already processed successfully, skipping")
            else:
                logger.debug(f"Date {date_str} already checked (no issue found), skipping")
            return None
        
        logger.info(f"Processing date: {date_str}")
        
        # Create directory for this date
        date_dir = self.output_dir / f"{self.lccn}_{date_str}"
        
        # Check if this date has an issue by trying to access the first page
        # Format: https://chroniclingamerica.loc.gov/lccn/sn83045604/1892-01-01/ed-1/seq-1.jp2
        base_url = f"{API_URL}/lccn/{self.lccn}/{date_str}/ed-1"
        
        # Use HEAD request to check if first page exists
        check_url = f"{base_url}/seq-1.jp2"
        resp = self.make_request(check_url, method="HEAD")
        
        if not resp:
            # No issue found for this date
            logger.info(f"No issue found for date {date_str}")
            self.checkpoint_data["dates_checked"].add(date_str)
            self._save_checkpoint()
            return None
        
        # Issue exists for this date, try to download all pages
        logger.info(f"Found issue for date {date_str}")
        self.checkpoint_data["successful_dates"].add(date_str)
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Track downloads for this date
        downloaded_files = []
        
        # Try page numbers sequentially until we get a 404
        for page_num in range(1, self.max_pages + 1):
            page_base_url = f"{base_url}/seq-{page_num}"
            page_exists = False
            
            # File types to download
            file_urls = {
                "jp2": f"{page_base_url}.jp2",
                "pdf": f"{page_base_url}.pdf",
                "ocr_txt": f"{page_base_url}/ocr.txt"
            }
            
            # Try to download each file type
            for file_type, url in file_urls.items():
                filename = f"page_{page_num:04d}"
                
                if file_type == "jp2":
                    output_path = date_dir / f"{filename}.jp2"
                elif file_type == "pdf":
                    output_path = date_dir / f"{filename}.pdf"
                elif file_type == "ocr_txt":
                    output_path = date_dir / f"{filename}_ocr.txt"
                else:
                    continue
                
                if self.download_file(url, output_path):
                    downloaded_files.append(str(output_path))
                    page_exists = True
            
            # If this page doesn't exist, we've reached the end of the issue
            if not page_exists:
                break
        
        # Update checkpoint
        self.checkpoint_data["dates_checked"].add(date_str)
        if downloaded_files:
            self.checkpoint_data["downloaded_files"][date_str] = downloaded_files
            self.checkpoint_data["total_files_downloaded"] += len(downloaded_files)
        
        self._save_checkpoint()
        
        logger.info(f"Completed date {date_str}: {len(downloaded_files)} files downloaded")
        return {
            "date": date_str,
            "files": downloaded_files
        }
    
    def run(self):
        """
        Main method to run the downloader
        
        Returns:
            Summary dictionary
        """
        logger.info(f"Starting Seattle P-I direct URL downloader")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Target: {self.lccn} for year {self.year}")
        
        month_names = [calendar.month_name[m] for m in self.months]
        logger.info(f"Months: {', '.join(month_names)}")
        
        if self.sample:
            logger.info("Running in SAMPLE MODE - downloading limited dates")
        
        # Generate dates to download
        dates = list(self.generate_dates())
        
        # Filter to dates we haven't checked yet
        dates_to_process = [
            date for date in dates 
            if date.strftime("%Y-%m-%d") not in self.checkpoint_data["dates_checked"]
        ]
        
        # In sample mode, limit to a few dates
        if self.sample and len(dates_to_process) > 5:
            # Take one date from each month in our range
            sampled_dates = []
            for month in self.months:
                month_dates = [d for d in dates_to_process if d.month == month]
                if month_dates:
                    sampled_dates.append(random.choice(month_dates))
            
            if sampled_dates:
                dates_to_process = sampled_dates[:5]
            else:
                dates_to_process = dates_to_process[:5]
            
            logger.info(f"Sample mode: limiting to {len(dates_to_process)} dates for testing")
        
        if not dates_to_process:
            logger.info("No new dates to process")
            return self.checkpoint_data
        
        logger.info(f"Processing {len(dates_to_process)} dates")
        
        # Process dates sequentially to better respect rate limits
        start_time = time.time()
        for i, date in enumerate(dates_to_process):
            # Process the date
            self.process_date(date)
            
            # Update progress
            progress = (i + 1) / len(dates_to_process)
            elapsed = time.time() - start_time
            
            # Calculate ETA
            if i > 0 and elapsed > 0:
                dates_per_second = (i + 1) / elapsed
                eta_seconds = (len(dates_to_process) - (i + 1)) / dates_per_second
                eta_str = str(datetime.timedelta(seconds=int(eta_seconds)))
                
                logger.info(f"Progress: {i+1}/{len(dates_to_process)} dates ({progress:.1%}), "
                          f"ETA: {eta_str}")
        
        # Final checkpoint
        self._save_checkpoint(force=True)
        
        # Write a human-readable summary report
        elapsed = time.time() - start_time
        self._write_summary_report(elapsed)
        
        logger.info(f"Download complete in {elapsed:.2f} seconds")
        return self.checkpoint_data
    
    def _write_summary_report(self, elapsed=0):
        """Write summary report to disk"""
        # Build summary dictionary
        summary = {
            "lccn": self.lccn,
            "year": self.year,
            "months": self.months,
            "dates_checked": len(self.checkpoint_data.get("dates_checked", set())),
            "successful_dates": len(self.checkpoint_data.get("successful_dates", set())),
            "files_downloaded": self.checkpoint_data.get("total_files_downloaded", 0),
            "elapsed_time": elapsed,
            "completed_at": datetime.datetime.now().isoformat(),
            "files_by_date": {
                date: len(files) 
                for date, files in self.checkpoint_data.get("downloaded_files", {}).items()
            }
        }
        
        # Write the summary
        summary_path = self.output_dir / f"{self.lccn}_{self.year}_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Summary saved to {summary_path}")
        return summary

def main():
    parser = argparse.ArgumentParser(description="Download Seattle Post-Intelligencer from 1892 using direct URLs")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory for downloaded files")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Number of concurrent download workers")
    parser.add_argument("--lccn", default="sn83045604", help="LCCN of the newspaper to download")
    parser.add_argument("--year", type=int, default=1892, help="Year to download")
    parser.add_argument("--months", type=int, nargs="+", help="Months to download (1-12)")
    parser.add_argument("--delay", type=float, default=DEFAULT_REQUEST_DELAY, help="Delay between requests in seconds")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="Maximum pages to try per issue")
    
    # Special options
    parser.add_argument("--sample", action="store_true", help="Sample mode - download a limited set of dates")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint if available")
    
    args = parser.parse_args()
    
    # Process months if provided
    if args.months:
        for m in args.months:
            if not (1 <= m <= 12):
                logger.error(f"Invalid month: {m}. Months must be between 1 and 12.")
                return 1
    
    # Check for existing checkpoint if resume flag is set
    if args.resume:
        checkpoint_file = Path(args.output) / f"{args.lccn}_{args.year}_checkpoint.pkl"
        if checkpoint_file.exists():
            logger.info(f"Resume flag set, will use checkpoint file at {checkpoint_file}")
        else:
            logger.warning(f"Resume flag set but no checkpoint file found at {checkpoint_file}")
    elif Path(args.output).exists():
        checkpoint_file = Path(args.output) / f"{args.lccn}_{args.year}_checkpoint.pkl"
        if checkpoint_file.exists():
            logger.info(f"Existing checkpoint found at {checkpoint_file}, but --resume not specified. "
                      f"Run with --resume to continue from checkpoint.")
    
    # Create downloader and run
    downloader = DirectUrlDownloader(
        output_dir=args.output, 
        lccn=args.lccn,
        year=args.year,
        months=args.months,
        workers=args.workers,
        request_delay=args.delay,
        sample=args.sample,
        max_pages=args.max_pages
    )
    
    downloader.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())