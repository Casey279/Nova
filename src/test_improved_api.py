#!/usr/bin/env python3
# Test script for the improved ChroniclingAmerica API client

import os
import logging
from datetime import datetime
from api.chronicling_america_improved import ImprovedChroniclingAmericaClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_seattle_pi_april_1891():
    """Test searching for Seattle Post-Intelligencer (sn83045604) in April 1891."""
    
    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), "..", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Create client
    client = ImprovedChroniclingAmericaClient(output_directory=output_dir)
    
    # Search for pages
    logger.info("Testing search for Seattle Post-Intelligencer in April 1891")
    pages, pagination = client.search_pages(
        lccn="sn83045604",
        date_start="1891-04-01",
        date_end="1891-04-30"
    )
    
    # Check results
    logger.info(f"Found {len(pages)} pages from {pagination['total_items']} total items")
    
    # Print out each page and check if it's in the correct date range
    in_range_count = 0
    for page in pages:
        issue_date = page.issue_date
        date_str = issue_date.strftime('%Y-%m-%d')
        
        # Check if date is in April 1891
        is_in_range = (
            issue_date.year == 1891 and
            issue_date.month == 4
        )
        
        if is_in_range:
            in_range_count += 1
            logger.info(f"✅ Found page from {date_str} - within requested range")
        else:
            logger.warning(f"❌ Found page from {date_str} - outside requested range")
    
    # Calculate success rate
    if pages:
        success_rate = (in_range_count / len(pages)) * 100
        logger.info(f"Success rate: {success_rate:.2f}% ({in_range_count}/{len(pages)} pages in requested date range)")
        
        if success_rate >= 90:
            logger.info("Test PASSED: Most results are within the requested date range")
            result = True
        else:
            logger.warning("Test WARNING: Less than 90% of results are within the requested date range")
            result = False
    else:
        logger.error("Test FAILED: No results found")
        result = False
    
    return result, pages

def test_download():
    """Test downloading page content."""
    
    # First run the search test to get pages
    result, pages = test_seattle_pi_april_1891()
    
    if not result or not pages:
        logger.error("Cannot run download test: Search test failed or returned no pages")
        return False
    
    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), "..", "test_output")
    
    # Create client
    client = ImprovedChroniclingAmericaClient(output_directory=output_dir)
    
    # Try to download the first page
    if pages:
        logger.info(f"Testing download for page from {pages[0].issue_date}")
        
        # Download PDF, JP2, and OCR
        download_result = client.download_page_content(
            pages[0],
            formats=['pdf', 'jp2', 'ocr'],
            save_files=True
        )
        
        # Check if download was successful
        formats_downloaded = list(download_result.keys())
        logger.info(f"Downloaded formats: {', '.join(formats_downloaded)}")
        
        if formats_downloaded:
            logger.info(f"Test PASSED: Successfully downloaded content in formats: {', '.join(formats_downloaded)}")
            result = True
        else:
            logger.error("Test FAILED: Could not download any content")
            result = False
    
    return result

if __name__ == "__main__":
    logger.info("Testing improved ChroniclingAmerica API client")
    
    search_result, _ = test_seattle_pi_april_1891()
    download_result = test_download()
    
    if search_result and download_result:
        logger.info("All tests PASSED!")
    else:
        logger.warning("Some tests FAILED or produced warnings.")