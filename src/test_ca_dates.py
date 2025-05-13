#!/usr/bin/env python3
# Test script to try different date parameter approaches

import requests
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_date_approaches():
    """Test different date parameter approaches with the Chronicling America API."""
    
    base_url = "https://chroniclingamerica.loc.gov"
    search_url = f"{base_url}/search/pages/results/"
    
    # Different date parameter approaches to test
    date_approaches = [
        {
            "name": "Standard date1/date2",
            "params": {
                'format': 'json',
                'lccn': 'sn83045604',
                'date1': '18910401',
                'date2': '18910430'
            }
        },
        {
            "name": "With dateFilterType=range",
            "params": {
                'format': 'json',
                'lccn': 'sn83045604',
                'date1': '18910401',
                'date2': '18910430',
                'dateFilterType': 'range'
            }
        },
        {
            "name": "Date format with dashes",
            "params": {
                'format': 'json',
                'lccn': 'sn83045604',
                'date1': '1891-04-01',
                'date2': '1891-04-30'
            }
        },
        {
            "name": "Year only",
            "params": {
                'format': 'json',
                'lccn': 'sn83045604',
                'year': '1891'
            }
        },
        {
            "name": "Date with searchType=advanced",
            "params": {
                'format': 'json',
                'lccn': 'sn83045604',
                'date1': '18910401',
                'date2': '18910430',
                'searchType': 'advanced'
            }
        },
        {
            "name": "With ortext=april",
            "params": {
                'format': 'json',
                'lccn': 'sn83045604',
                'date1': '18910401',
                'date2': '18910430',
                'ortext': 'april'
            }
        }
    ]
    
    # Run each test
    for approach in date_approaches:
        logger.info(f"\n=== Testing: {approach['name']} ===")
        params = approach['params']
        
        # Log the request
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{search_url}?{param_str}"
        logger.info(f"API request: {full_url}")
        
        # Make the request
        response = requests.get(search_url, params=params)
        if response.status_code != 200:
            logger.error(f"API error: Status {response.status_code}")
            continue
            
        # Parse the response
        data = response.json()
        total_items = data.get('totalItems', 0)
        items = data.get('items', [])
        
        # Log results summary
        logger.info(f"Results: {total_items} total items, {len(items)} on first page")
        
        # Check first few items for date
        if items:
            logger.info(f"First 3 items:")
            for i, item in enumerate(items[:3]):
                date = item.get('date', '')
                # Format date if needed (from YYYYMMDD to YYYY-MM-DD)
                if date and len(date) == 8:
                    formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
                else:
                    formatted_date = date
                
                logger.info(f"  Item {i+1}: Date = {formatted_date}")

if __name__ == "__main__":
    logger.info("Testing different date parameter approaches")
    test_date_approaches()
    logger.info("Tests completed")