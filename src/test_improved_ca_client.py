#!/usr/bin/env python3
"""
Test script for the improved Chronicling America API client.

This script tests the ImprovedChroniclingAmericaClient's ability to search 
for newspaper pages within specific date ranges and retrieve multiple pages of results.
"""

import os
import logging
import json
from datetime import datetime, date, timedelta
from api.chronicling_america_improved import ImprovedChroniclingAmericaClient

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_search_seattle_pi_april_1891():
    """
    Test searching for Seattle Post-Intelligencer issues from April 1891.
    
    This specific test case is based on the user's requirements to find all issues
    from this newspaper in this specific month.
    """
    # Define test parameters
    output_dir = os.path.join(os.getcwd(), "test_output")
    lccn = "sn83045604"  # Seattle Post-Intelligencer
    start_date = "1891-04-01"
    end_date = "1891-04-30"
    
    # Create client
    client = ImprovedChroniclingAmericaClient(output_dir)
    
    # Get number of pages
    logger.info(f"Searching for Seattle P-I issues from {start_date} to {end_date}")
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=start_date,
        date_end=end_date,
        max_pages=5  # Get up to 5 pages of results to retrieve more pages
    )
    
    # Display results
    logger.info(f"Found {len(pages)} pages")
    logger.info(f"Pagination info: {pagination}")
    
    # Group pages by date to check coverage
    pages_by_date = {}
    for page in pages:
        date_str = page.issue_date.isoformat()
        if date_str not in pages_by_date:
            pages_by_date[date_str] = []
        pages_by_date[date_str].append(page)
    
    # Display page distribution by date
    logger.info(f"Found pages for {len(pages_by_date)} unique dates")
    for date_str, date_pages in sorted(pages_by_date.items()):
        logger.info(f"  {date_str}: {len(date_pages)} pages")
    
    # The Seattle P-I should have issues every day except Mondays in April 1891
    # Let's check how many dates we're missing
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    current_date = start_date_obj
    expected_dates = []
    
    while current_date <= end_date_obj:
        # Skip Mondays (0 = Monday)
        if current_date.weekday() != 0:  # Not a Monday
            expected_dates.append(current_date.isoformat())
        
        current_date += timedelta(days=1)
    
    # Check which dates are missing
    found_dates = set(pages_by_date.keys())
    expected_dates_set = set(expected_dates)
    
    missing_dates = expected_dates_set - found_dates
    unexpected_dates = found_dates - expected_dates_set
    
    if missing_dates:
        logger.warning(f"Missing {len(missing_dates)} expected dates: {sorted(missing_dates)}")
    else:
        logger.info("Found all expected dates!")
        
    if unexpected_dates:
        logger.warning(f"Found {len(unexpected_dates)} unexpected dates: {sorted(unexpected_dates)}")
    
    # Check how many pages we'd expect
    # Monday: No publication (0 pages)
    # Sunday: Usually more pages (16 pages)
    # Tuesday-Saturday: 8 pages each
    expected_page_count = 0
    for date_str in expected_dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        if date_obj.weekday() == 6:  # Sunday
            expected_page_count += 16
        else:  # Tuesday-Saturday
            expected_page_count += 8
    
    logger.info(f"Expected approximately {expected_page_count} pages")
    logger.info(f"Found {len(pages)} pages ({len(pages)/expected_page_count*100:.1f}% of expected)")
    
    # Print first page details
    if pages:
        first_page = pages[0]
        logger.info(f"First page details:")
        logger.info(f"  LCCN: {first_page.lccn}")
        logger.info(f"  Date: {first_page.issue_date}")
        logger.info(f"  Sequence: {first_page.sequence}")
        logger.info(f"  URL: {first_page.url}")
        logger.info(f"  JP2 URL: {first_page.jp2_url}")
    
    # Save results to JSON file for reference
    results = {
        "total_pages_found": len(pages),
        "unique_dates": len(pages_by_date),
        "expected_dates": len(expected_dates),
        "missing_dates": list(sorted(missing_dates)),
        "pagination": pagination,
        "date_distribution": {date: len(date_pages) for date, date_pages in pages_by_date.items()}
    }
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save results
    with open(os.path.join(output_dir, "search_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to {os.path.join(output_dir, 'search_results.json')}")
    
    return len(pages)

def main():
    """Run all tests"""
    logger.info("Running test for Seattle PI - April 1891")
    pages_found = test_search_seattle_pi_april_1891()
    
    logger.info(f"Test completed. Found {pages_found} pages.")

if __name__ == "__main__":
    main()