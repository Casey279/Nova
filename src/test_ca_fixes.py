#!/usr/bin/env python3
# Test script for Chronicling America API calls with fixes

import requests
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chronicling_america_fixes():
    """Test our fixed approach to Chronicling America API"""
    
    base_url = "https://chroniclingamerica.loc.gov"
    search_url = f"{base_url}/search/pages/results/"
    
    # Build the parameters with our fixes
    params = {
        'format': 'json',
        'page': 1,
        'rows': 20,
        'lccn': 'sn83045604',  # Seattle Post-Intelligencer
        # No state parameter - we found it breaks the search
        'date1': '18910401',   # April 1, 1891
        'date2': '18910430',   # April 30, 1891
        'dateFilterType': 'range'  # Important for date filtering
    }
    
    # Log the request
    param_str = "&".join([f"{k}={v}" for k, v in params.items()])
    full_url = f"{search_url}?{param_str}"
    logger.info(f"Testing API request: {full_url}")
    
    # Make the request
    response = requests.get(search_url, params=params)
    response.raise_for_status()
    
    # Parse the response
    data = response.json()
    total_items = data.get('totalItems', 0)
    items = data.get('items', [])
    
    # Log the results
    logger.info(f"Response status: {response.status_code}")
    logger.info(f"Total items found: {total_items}")
    logger.info(f"First page items: {len(items)}")
    
    # Show first few items
    if items:
        logger.info(f"First {min(5, len(items))} items:")
        for i, item in enumerate(items[:5]):
            date = item.get('date', '')
            # Format date if needed (from YYYYMMDD to YYYY-MM-DD)
            if date and len(date) == 8:
                date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
            
            title = item.get('title', {})
            if isinstance(title, dict):
                title = title.get('name', 'Unknown')
            
            logger.info(f"  {i+1}. {title} (Date: {date}, LCCN: {item.get('lccn', '')})")
            
    # Check if items are within our date range
    if items:
        in_range_count = 0
        for item in items:
            date = item.get('date', '')
            if date and len(date) == 8:
                if '18910401' <= date <= '18910430':
                    in_range_count += 1
        
        logger.info(f"Items within date range April 1891: {in_range_count}/{len(items)}")
    
    return total_items, items

if __name__ == "__main__":
    logger.info("Starting Chronicling America API fixes test")
    test_chronicling_america_fixes()
    logger.info("Test completed")