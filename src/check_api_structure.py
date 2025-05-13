#!/usr/bin/env python3
# Script to check the structure of the ChroniclingAmerica API response

import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_api_structure():
    """Check the structure of the ChroniclingAmerica API response for Seattle PI in 1891."""
    
    # API endpoint for search
    url = "https://chroniclingamerica.loc.gov/search/pages/results/"
    
    # Query parameters
    params = {
        'format': 'json',
        'lccn': 'sn83045604',  # Seattle Post-Intelligencer
        'year': '1891',        # Year 1891
        'fo': 'json'
    }
    
    # Headers
    headers = {
        "User-Agent": "NovaHistoricalDatabase/1.0",
        "Accept": "application/json",
        "Referer": "https://www.loc.gov/collections/chronicling-america/",
        "Connection": "keep-alive"
    }
    
    # Make the request
    logger.info(f"Making API request to {url}")
    response = requests.get(url, params=params, headers=headers)
    
    # Check if request was successful
    if response.status_code != 200:
        logger.error(f"Request failed with status code {response.status_code}")
        return
    
    # Parse response
    try:
        data = response.json()
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        return
    
    # Check top-level structure
    logger.info("Top-level structure:")
    for key in data.keys():
        logger.info(f"  {key}: {type(data[key])}")
    
    # Check items structure (if exists)
    if 'items' in data:
        items = data['items']
        logger.info(f"Found {len(items)} items")
        
        # Check structure of first item
        if items:
            first_item = items[0]
            
            # Print out the keys and types for debugging
            logger.info("First item structure:")
            try:
                if isinstance(first_item, dict):
                    for key, value in first_item.items():
                        value_type = type(value)
                        value_preview = str(value)[:50] + '...' if len(str(value)) > 50 else value
                        logger.info(f"  {key}: {value_type} = {value_preview}")
                else:
                    logger.info(f"  Item is not a dictionary but a {type(first_item)}")
                    logger.info(f"  Item content: {first_item[:100]}..." if isinstance(first_item, (str, bytes)) else "Unknown format")
            except Exception as e:
                logger.error(f"Error analyzing first item: {e}")
    else:
        logger.info("No 'items' key found in response")
        
    # Save the full response to a file for further analysis
    with open("api_response.json", "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Full response saved to api_response.json")

if __name__ == "__main__":
    check_api_structure()