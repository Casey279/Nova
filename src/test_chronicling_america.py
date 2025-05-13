#!/usr/bin/env python3
# Test script for Chronicling America API calls

import requests
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chronicling_america_search(keywords=None, lccn=None, state=None, date_start=None, date_end=None, page=1, rows=20):
    """Test different search parameters with the Chronicling America API."""
    
    base_url = "https://chroniclingamerica.loc.gov"
    search_url = f"{base_url}/search/pages/results/"
    
    # Build the parameters
    params = {
        'format': 'json',
        'page': page,
        'rows': rows
    }
    
    # Add optional parameters
    if keywords:
        params['andtext'] = keywords
    if lccn:
        params['lccn'] = lccn
    if state:
        params['state'] = state
    if date_start:
        # Convert YYYY-MM-DD to YYYYMMDD
        date_obj = datetime.strptime(date_start, "%Y-%m-%d")
        params['date1'] = date_obj.strftime("%Y%m%d")
    if date_end:
        # Convert YYYY-MM-DD to YYYYMMDD
        date_obj = datetime.strptime(date_end, "%Y-%m-%d")
        params['date2'] = date_obj.strftime("%Y%m%d")
    
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
    
    # Show first item details if any
    if items:
        first_item = items[0]
        logger.info(f"First item: {json.dumps(first_item, indent=2)[:500]}...")
    
    return total_items, items

def run_tests():
    """Run a series of tests with different parameter combinations."""
    
    # Test cases
    test_cases = [
        # Very broad search
        {"name": "Broad search", "params": {}},
        
        # LCCN only - Seattle Post-Intelligencer
        {"name": "LCCN only", "params": {"lccn": "sn83045604"}},
        
        # Date range only - April 1891
        {"name": "Date range only", "params": {"date_start": "1891-04-01", "date_end": "1891-04-30"}},
        
        # State only - Washington
        {"name": "State only", "params": {"state": "WA"}},
        
        # LCCN + Date range
        {"name": "LCCN + Date range", "params": {"lccn": "sn83045604", "date_start": "1891-04-01", "date_end": "1891-04-30"}},
        
        # LCCN + State
        {"name": "LCCN + State", "params": {"lccn": "sn83045604", "state": "WA"}},
        
        # Date range + State
        {"name": "Date range + State", "params": {"date_start": "1891-04-01", "date_end": "1891-04-30", "state": "WA"}},
        
        # All parameters - LCCN + Date range + State
        {"name": "All parameters", "params": {"lccn": "sn83045604", "date_start": "1891-04-01", "date_end": "1891-04-30", "state": "WA"}},
        
        # Test with broader date range - full year 1891
        {"name": "Broader date range", "params": {"lccn": "sn83045604", "date_start": "1891-01-01", "date_end": "1891-12-31", "state": "WA"}},
        
        # Test with different LCCN - New York Tribune
        {"name": "Different newspaper", "params": {"lccn": "sn83030214", "date_start": "1891-04-01", "date_end": "1891-04-30"}}
    ]
    
    # Run each test
    for test in test_cases:
        logger.info(f"\n=== TEST: {test['name']} ===")
        total, items = test_chronicling_america_search(**test['params'])
        logger.info(f"=== RESULT: {total} items found ===\n")

if __name__ == "__main__":
    logger.info("Starting Chronicling America API tests")
    run_tests()
    logger.info("Tests completed")