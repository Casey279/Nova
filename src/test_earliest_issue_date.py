"""
Test script to verify the earliest issue date detection functionality.

This script tests different approaches to detecting the earliest issue date
for newspapers in the Chronicling America database.
"""

import os
import logging
from datetime import datetime, date
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the improved client
from src.api.chronicling_america_improved import ImprovedChroniclingAmericaClient

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_earliest_issue_date(lccn):
    """Test the earliest issue date detection for a specific newspaper."""
    
    logger.info(f"Testing earliest issue date detection for LCCN: {lccn}")
    
    # Create a client instance
    output_dir = "./test_output"
    client = ImprovedChroniclingAmericaClient(output_dir)
    
    # Get the earliest issue date
    earliest_date = client.get_earliest_issue_date(lccn)
    
    if earliest_date:
        logger.info(f"Found earliest issue date: {earliest_date}")
    else:
        logger.warning(f"Could not find earliest issue date for {lccn}")
        
    return earliest_date

def test_date_based_search(lccn, start_date, end_date):
    """Test searching for pages with date-based filtering."""
    
    logger.info(f"Testing date-based search for LCCN: {lccn}")
    logger.info(f"Date range: {start_date} to {end_date}")
    
    # Create a client instance
    output_dir = "./test_output"
    client = ImprovedChroniclingAmericaClient(output_dir)
    
    # Get the earliest issue date first
    earliest_date = client.get_earliest_issue_date(lccn)
    if earliest_date:
        logger.info(f"Found earliest issue date: {earliest_date}")
        
        # If start_date is before earliest_date, it should be adjusted in the search
        if start_date < earliest_date:
            logger.info(f"Start date {start_date} is before earliest issue date {earliest_date}")
            logger.info(f"Expecting search to use {earliest_date} as the actual start date")
    
    # Search for pages
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=start_date,
        date_end=end_date,
        items_per_page=10,
        max_pages=1
    )
    
    logger.info(f"Found {len(pages)} pages")
    if pages:
        logger.info(f"First page issue date: {pages[0].issue_date}")
        logger.info(f"Last page issue date: {pages[-1].issue_date}")
    
    # Check if the start date was adjusted properly
    if pages and earliest_date and start_date < earliest_date:
        # The first page should not be before the earliest issue date
        assert pages[0].issue_date >= earliest_date, \
            f"First page date {pages[0].issue_date} is before earliest issue date {earliest_date}"
        logger.info("Start date adjustment works correctly!")
    
    return pages, pagination

def test_multiple_newspapers():
    """Test earliest issue date detection for multiple newspapers."""
    
    # List of LCCNs to test
    newspapers = [
        ("sn83045604", "Seattle Post-Intelligencer"),
        ("sn83025121", "Chicago Tribune"),
        ("sn83030213", "New York Tribune"),
        ("sn83030214", "New York Times"),
        ("sn84026749", "Washington Post")
    ]
    
    results = {}
    
    for lccn, name in newspapers:
        logger.info(f"\n\nTesting {name} ({lccn}):")
        earliest_date = test_earliest_issue_date(lccn)
        results[lccn] = (name, earliest_date)
    
    # Print summary
    logger.info("\n\nSummary of earliest issue dates:")
    for lccn, (name, earliest_date) in results.items():
        date_str = earliest_date.strftime("%B %d, %Y") if earliest_date else "Not found"
        logger.info(f"{name} ({lccn}): {date_str}")

def main():
    """Main function to run tests."""
    
    # Test for a specific newspaper
    lccn = "sn83045604"  # Seattle Post-Intelligencer
    
    # Get the earliest issue date
    earliest_date = test_earliest_issue_date(lccn)
    
    if earliest_date:
        # Test search with a date range that starts before the earliest issue
        # Use January 1st of the same year as the start date
        year = earliest_date.year
        test_start_date = date(year, 1, 1)
        test_end_date = date(year, 12, 31)
        
        logger.info(f"\nTesting search with date range: {test_start_date} to {test_end_date}")
        pages, pagination = test_date_based_search(lccn, test_start_date, test_end_date)
    
    # Test multiple newspapers
    logger.info("\n\nTesting earliest issue date for multiple newspapers:")
    test_multiple_newspapers()

if __name__ == "__main__":
    main()