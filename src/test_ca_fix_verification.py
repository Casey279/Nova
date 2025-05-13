#!/usr/bin/env python3
# Test script to verify our fix for date filtering in ChroniclingAmericaClient

import sys
import os
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import the api module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from api.chronicling_america import ChroniclingAmericaClient

def test_date_filtering():
    """Test our fix for date filtering in the ChroniclingAmericaClient."""
    
    # Create a client with a temporary output directory
    output_dir = os.path.join(os.path.dirname(__file__), "..", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    client = ChroniclingAmericaClient(output_directory=output_dir)
    
    # Test with Seattle Post-Intelligencer (sn83045604) in April 1891
    logger.info("Testing search for Seattle Post-Intelligencer (sn83045604) in April 1891")
    
    pages, pagination = client.search_pages(
        lccn="sn83045604",
        date_start="1891-04-01",
        date_end="1891-04-30"
    )
    
    # Log results summary
    total_items = pagination.get('total_items', 0)
    logger.info(f"Found {len(pages)} pages from {total_items} total items")
    
    # Check if we got any results
    if not pages:
        logger.error("No results found. The fix didn't work.")
        return False
    
    # Verify dates are within range
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
    
    # Calculate percentage of results in the correct date range
    if pages:
        success_rate = (in_range_count / len(pages)) * 100
        logger.info(f"Success rate: {success_rate:.2f}% ({in_range_count}/{len(pages)} pages in requested date range)")
        
        if success_rate >= 90:
            logger.info("Test PASSED: Most results are within the requested date range")
            return True
        else:
            logger.error("Test FAILED: Less than 90% of results are within the requested date range")
            return False
    else:
        logger.error("Test FAILED: No results found")
        return False


if __name__ == "__main__":
    logger.info("Running test to verify date filtering fix")
    success = test_date_filtering()
    
    if success:
        logger.info("All tests passed! The fix is working correctly.")
        sys.exit(0)
    else:
        logger.error("Tests failed. The fix needs more work.")
        sys.exit(1)