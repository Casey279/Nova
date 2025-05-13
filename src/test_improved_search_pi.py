"""
Test script to verify that our improved search functionality
correctly uses the earliest issue date for the Seattle Post-Intelligencer.
"""

import os
import sys
import json
import logging
from datetime import datetime, date, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our improved client
from src.api.chronicling_america_improved import ImprovedChroniclingAmericaClient
from src.api.chronicling_america_earliest_dates import get_earliest_date, get_newspaper_title

def test_earliest_date():
    """Test that we can get the earliest issue date for the Seattle Post-Intelligencer."""
    lccn = "sn83045604"  # Seattle Post-Intelligencer
    
    # Check if we have the earliest date in our database
    earliest_date = get_earliest_date(lccn)
    title = get_newspaper_title(lccn)
    
    if earliest_date:
        logger.info(f"Found earliest issue date for {title} ({lccn}): {earliest_date}")
    else:
        logger.warning(f"Could not find earliest issue date for {lccn} in our database")
        
    # Create a client and try to get the earliest issue date
    output_dir = "./test_output"
    client = ImprovedChroniclingAmericaClient(output_dir)
    
    client_date = client.get_earliest_issue_date(lccn)
    if client_date:
        logger.info(f"Client found earliest issue date: {client_date}")
    else:
        logger.warning(f"Client could not find earliest issue date")
        
    return earliest_date or client_date

def test_search_with_early_date():
    """Test searching for pages with a date range that starts before the first issue."""
    lccn = "sn83045604"  # Seattle Post-Intelligencer
    
    # First, get the earliest issue date
    earliest_date = test_earliest_date()
    
    if not earliest_date:
        logger.error("Could not determine earliest issue date, aborting test")
        return
    
    # Start date is January 1st of the same year as the earliest issue
    start_year = earliest_date.year
    start_date = date(start_year, 1, 1)
    
    # End date is one month after the earliest issue
    end_date = earliest_date + timedelta(days=30)
    
    logger.info(f"Testing search with date range from {start_date} to {end_date}")
    logger.info(f"Earliest issue is on {earliest_date}")
    logger.info(f"Expecting search to start from {earliest_date} instead of {start_date}")
    
    # Create a client
    output_dir = "./test_output"
    client = ImprovedChroniclingAmericaClient(output_dir)
    
    # Search for pages
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=start_date,
        date_end=end_date,
        items_per_page=10,
        max_pages=1
    )
    
    # Print information about the results
    logger.info(f"Found {len(pages)} pages")
    
    if pages:
        # Sort the pages by date
        pages.sort(key=lambda p: p.issue_date)
        
        # Check the earliest date in the results
        earliest_result_date = pages[0].issue_date
        logger.info(f"Earliest date in results: {earliest_result_date}")
        
        # Check if the earliest date in the results is on or after the earliest issue date
        if earliest_result_date < earliest_date:
            logger.error(f"ERROR: Found pages before the earliest issue date")
            logger.error(f"Earliest result date: {earliest_result_date}")
            logger.error(f"Earliest issue date: {earliest_date}")
        else:
            logger.info(f"SUCCESS: All results are on or after the earliest issue date")
            
        # Print all the dates in the results
        logger.info("Dates in results:")
        for i, page in enumerate(pages[:20]):  # Show first 20 pages
            logger.info(f"  {i+1}. {page.issue_date}")
            
        if len(pages) > 20:
            logger.info(f"  ... and {len(pages) - 20} more")
    else:
        logger.warning("No pages found in the search results")

def main():
    """Main function to run tests."""
    test_search_with_early_date()

if __name__ == "__main__":
    main()