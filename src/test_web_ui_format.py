#!/usr/bin/env python3
"""
Test script for using the exact web UI format for date filtering
Based on the URL from Chronicling America's advanced search
"""

import os
import logging
import time
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the Python path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the improved client
from api.chronicling_america_improved import ImprovedChroniclingAmericaClient

def test_web_ui_format_search():
    """Test using the exact web UI format for date filtering."""
    
    # Create a client with a temporary output directory
    output_dir = os.path.join(os.path.dirname(__file__), "..", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Testing search with web UI date format for Seattle P-I in April 1891")
    
    # Create client
    client = ImprovedChroniclingAmericaClient(output_directory=output_dir)
    
    # Search parameters - exact match to the web UI
    lccn = "sn83045604"  # Seattle Post-Intelligencer
    date_start = "1891-04-01"
    date_end = "1891-04-30"
    
    # Search for pages
    logger.info(f"Searching for pages: lccn={lccn}, date_start={date_start}, date_end={date_end}")
    start_time = time.time()
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=date_start,
        date_end=date_end,
        max_pages=2  # Get more pages to find more results
    )
    
    # Report results
    elapsed = time.time() - start_time
    logger.info(f"Search completed in {elapsed:.2f} seconds")
    logger.info(f"Found {len(pages)} pages from {pagination.get('total_items', 0)} total items")
    
    # Count results by date
    date_counts = {}
    for page in pages:
        date_str = page.issue_date.strftime('%Y-%m-%d')
        if date_str in date_counts:
            date_counts[date_str] += 1
        else:
            date_counts[date_str] = 1
    
    # Print dates summary
    logger.info("Pages found by date:")
    for date_str, count in sorted(date_counts.items()):
        logger.info(f"  {date_str}: {count} pages")
    
    # Download the first page if any results were found
    if pages:
        logger.info(f"Testing download for the first page")
        page = pages[0]
        result = client.download_page_content(
            page, 
            formats=['jp2'], 
            save_files=True
        )
        
        # Check result
        if 'jp2' in result:
            logger.info(f"Successfully downloaded JP2: {result['jp2']}")
            return True
        else:
            logger.error(f"Failed to download JP2")
            return False
    else:
        logger.warning(f"No pages found to download")
        return False

if __name__ == "__main__":
    logger.info("Starting test with web UI date format")
    success = test_web_ui_format_search()
    
    if success:
        logger.info("TEST PASSED: Successfully found and downloaded Seattle P-I pages from April 1891")
        sys.exit(0)
    else:
        logger.error("TEST FAILED: Could not find or download Seattle P-I pages from April 1891")
        sys.exit(1)