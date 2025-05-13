#!/usr/bin/env python3
"""
Test script for the improved ChroniclingAmerica search functionality.
This script tests the search behavior with and without the date range limits.
"""

import os
import sys
import logging
from datetime import datetime, date

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the improved client
from api.chronicling_america_improved import ImprovedChroniclingAmericaClient

def run_test_search():
    """Run test searches to verify the improved functionality."""
    # Create output directory
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize client
    client = ImprovedChroniclingAmericaClient(output_directory=output_dir)
    
    # Test case 1: Seattle Post-Intelligencer with adjusted date range
    print("\n=== TEST CASE 1: Seattle Post-Intelligencer (sn83045604) with wide date range ===")
    print("This should automatically adjust to the newspaper's publication dates")
    
    lccn = "sn83045604"  # Seattle Post-Intelligencer
    date_start = "1800-01-01"  # Before the newspaper started
    date_end = "1888-12-31"  # Early period of the newspaper
    
    print(f"Searching for LCCN {lccn} from {date_start} to {date_end}")
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=date_start,
        date_end=date_end,
        max_pages=1
    )
    
    print(f"Found {len(pages)} pages, total items: {pagination.get('total_items', 0)}")
    if pages:
        print("\nFirst 5 results:")
        for i, page in enumerate(pages[:5]):
            print(f"  {i+1}. {page.issue_date} - {page.title} (Page {page.sequence})")
    
    # Test case 2: Using a narrower date range
    print("\n=== TEST CASE 2: Seattle Post-Intelligencer with narrow date range ===")
    
    date_start = "1888-07-01"
    date_end = "1888-07-31"
    
    print(f"Searching for LCCN {lccn} from {date_start} to {date_end}")
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=date_start,
        date_end=date_end,
        max_pages=1
    )
    
    print(f"Found {len(pages)} pages, total items: {pagination.get('total_items', 0)}")
    if pages:
        print("\nAll results:")
        for i, page in enumerate(pages):
            print(f"  {i+1}. {page.issue_date} - {page.title} (Page {page.sequence})")
    
    # Test case 3: Using a different newspaper with Monday issues
    print("\n=== TEST CASE 3: New York Tribune (sn83030214) including Mondays ===")
    
    lccn = "sn83030214"  # New York Tribune
    date_start = "1880-01-01"
    date_end = "1880-01-31"
    
    print(f"Searching for LCCN {lccn} from {date_start} to {date_end}")
    pages, pagination = client.search_pages(
        lccn=lccn,
        date_start=date_start,
        date_end=date_end,
        max_pages=1
    )
    
    print(f"Found {len(pages)} pages, total items: {pagination.get('total_items', 0)}")
    if pages:
        print("\nAll results:")
        day_counts = {}
        for i, page in enumerate(pages):
            weekday = page.issue_date.strftime("%A")
            if weekday not in day_counts:
                day_counts[weekday] = 0
            day_counts[weekday] += 1
            print(f"  {i+1}. {page.issue_date} ({weekday}) - {page.title} (Page {page.sequence})")
        
        print("\nResults by day of week:")
        for day, count in day_counts.items():
            print(f"  {day}: {count} pages")

if __name__ == "__main__":
    run_test_search()