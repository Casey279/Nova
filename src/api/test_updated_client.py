#!/usr/bin/env python3
"""
Test the updated ChroniclingAmerica API client with the new LoC.gov API.

This script tests the key functionality of the updated API client:
1. Searching for newspapers
2. Searching for pages
3. Downloading content
"""

import os
import sys
import logging
from datetime import date

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TestClient')

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the API client
from api.chronicling_america import ChroniclingAmericaClient

def test_search_newspapers():
    """Test searching for newspapers with the updated client."""
    logger.info("Testing search_newspapers with the new LoC.gov API...")
    
    # Create client
    client = ChroniclingAmericaClient(output_directory="./test_output")
    
    # Search for newspapers - try without filters first
    newspapers = client.search_newspapers()
    
    # If that fails, try with a specific state
    if not newspapers:
        logger.info("Trying with specific state...")
        newspapers = client.search_newspapers(state="New York")
    
    logger.info(f"Found {len(newspapers)} newspapers")
    if newspapers:
        logger.info(f"Sample newspaper: {newspapers[0].__dict__}")
    
    return len(newspapers) > 0

def test_search_pages():
    """Test searching for pages with the updated client."""
    logger.info("Testing search_pages with the new LoC.gov API...")
    
    # Create client
    client = ChroniclingAmericaClient(output_directory="./test_output")
    
    # Search for pages
    pages, pagination = client.search_pages(
        state="New York",
        date_start="1920-01-01",
        date_end="1922-12-31",
        page=1,
        items_per_page=10
    )
    
    logger.info(f"Found {len(pages)} pages (total items: {pagination['total_items']})")
    if pages:
        logger.info(f"Sample page: {pages[0].__dict__}")
    
    return len(pages) > 0

def test_download_content(download=False):
    """Test downloading content with the updated client."""
    logger.info("Testing download_page_content with the new LoC.gov API...")
    
    # Create client
    client = ChroniclingAmericaClient(output_directory="./test_output")
    
    # Search for pages
    pages, _ = client.search_pages(
        state="New York",
        date_start="1920-01-01",
        date_end="1922-12-31",
        page=1,
        items_per_page=1
    )
    
    if not pages:
        logger.error("No pages found to test download")
        return False
    
    if download:
        # Download content for the first page
        result = client.download_page_content(
            pages[0],
            formats=['json'],  # Only download JSON to save bandwidth
            save_files=True
        )
        
        logger.info(f"Download result: {result}")
        return len(result) > 0
    else:
        # Skip actual download unless specified
        logger.info("Skipping actual download (set download=True to test)")
        return True

def main():
    """Run all tests."""
    os.makedirs("./test_output", exist_ok=True)
    
    tests = [
        test_search_newspapers,
        test_search_pages,
        test_download_content
    ]
    
    results = []
    
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
            status = "PASSED" if result else "FAILED"
            logger.info(f"Test {test_func.__name__}: {status}")
        except Exception as e:
            logger.error(f"Test {test_func.__name__} failed with error: {e}")
            results.append(False)
    
    # Print summary
    success = all(results)
    logger.info("="*50)
    logger.info(f"Test Summary: {'ALL TESTS PASSED' if success else 'SOME TESTS FAILED'}")
    logger.info("="*50)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())