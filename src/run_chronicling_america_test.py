#!/usr/bin/env python3
"""
Test script for running a search using the improved ChroniclingAmerica client.

This script demonstrates how to use the improved client to search for
newspaper pages in a specific date range.
"""

import os
import logging
import sys
import json
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.chronicling_america_improved import ImprovedChroniclingAmericaClient

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Run a test search and display results."""
    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Create client
    client = ImprovedChroniclingAmericaClient(output_dir)
    
    # Parameters for Seattle Post-Intelligencer in April 1891
    lccn = "sn83045604"
    date_start = "1891-04-01"
    date_end = "1891-04-30"
    
    # Search for pages - use max_pages=2 to get more results
    logger.info(f"Searching for Seattle P-I issues from {date_start} to {date_end}")
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=date_start,
        date_end=date_end,
        max_pages=2  # Get up to 2 pages of results
    )
    
    # Display results
    logger.info(f"Found {len(pages)} total pages")
    logger.info(f"Pagination info: {pagination}")
    
    # Group by date
    pages_by_date = {}
    for page in pages:
        date_str = page.issue_date.isoformat()
        if date_str not in pages_by_date:
            pages_by_date[date_str] = []
        pages_by_date[date_str].append(page)
    
    # Show distribution by date
    logger.info(f"Found pages for {len(pages_by_date)} unique dates:")
    for date_str, date_pages in sorted(pages_by_date.items()):
        logger.info(f"  {date_str}: {len(date_pages)} pages")
    
    # Save results to JSON for reference
    results = {
        "search_params": {
            "lccn": lccn,
            "date_start": date_start,
            "date_end": date_end
        },
        "total_pages_found": len(pages),
        "unique_dates": len(pages_by_date),
        "pagination_info": pagination,
        "date_distribution": {
            date_str: len(date_pages) 
            for date_str, date_pages in sorted(pages_by_date.items())
        }
    }
    
    output_file = os.path.join(output_dir, "search_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")
    
    # Download a sample page if we have results
    if pages:
        logger.info("Downloading a sample page...")
        sample_page = pages[0]
        
        download_formats = ["jp2"]
        result = client.download_page_content(sample_page, formats=download_formats)
        
        if result:
            logger.info(f"Downloaded formats: {', '.join(result.keys())}")
            for fmt, path in result.items():
                logger.info(f"  {fmt}: {path}")
        else:
            logger.warning("Failed to download sample page")

if __name__ == "__main__":
    main()