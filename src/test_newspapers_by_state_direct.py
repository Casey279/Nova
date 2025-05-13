#!/usr/bin/env python3
"""
Test script to fetch newspapers directly by state from Chronicling America
using the direct newspapers URL with state parameter.
"""

import os
import sys
import logging
import requests
import json
import re

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_newspapers_by_state(state_name):
    """
    Retrieve newspapers by state using the direct Chronicling America newspapers endpoint.
    
    Args:
        state_name: Full state name (e.g., "Washington", "Colorado")
        
    Returns:
        List of newspaper dictionaries
    """
    # The direct URL for newspapers by state
    url = f"https://chroniclingamerica.loc.gov/newspapers/"
    
    # Parameters for the query
    params = {
        'state': state_name,
        'format': 'json'
    }
    
    logger.info(f"API Request: {url}?state={state_name}&format=json")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # Try to parse as JSON
        try:
            data = response.json()
            
            # Extract newspapers from the JSON response
            if 'newspapers' in data:
                newspapers = data['newspapers']
                logger.info(f"Found {len(newspapers)} newspapers in JSON response")
                return newspapers
            else:
                logger.warning("No 'newspapers' key in JSON response")
                return []
                
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract information from HTML
            logger.info("Response is not JSON, trying to parse HTML directly")

            # Just get the raw HTML response
            html = response.text

            # Let's try using regex to extract newspaper data
            # This is a simpler approach without BeautifulSoup
            newspapers = []

            # Extract newspaper data using regex patterns
            # Looking for LCCN, title, location, years
            lccn_pattern = r'href="/lccn/([^/]+)/"'
            title_pattern = r'<td class="[^"]*title[^"]*">\s*<a[^>]*>(.*?)</a>\s*</td>'
            place_pattern = r'<td class="[^"]*place[^"]*">(.*?)</td>'
            year_pattern = r'<td class="[^"]*year[^"]*">(.*?)</td>'

            # Find all LCCNs
            lccns = re.findall(lccn_pattern, html)
            titles = re.findall(title_pattern, html)
            places = re.findall(place_pattern, html)
            years = re.findall(year_pattern, html)

            # Group the data based on the available information
            if lccns and titles and places and len(years) >= len(lccns) * 2:
                for i in range(len(lccns)):
                    # For each newspaper, we need start_year and end_year (two year entries)
                    year_idx = i * 2
                    if year_idx + 1 < len(years):
                        newspaper = {
                            'title': titles[i] if i < len(titles) else f"Newspaper {i+1}",
                            'lccn': lccns[i],
                            'place_of_publication': places[i] if i < len(places) else "",
                            'start_year': years[year_idx],
                            'end_year': years[year_idx + 1] or None
                        }
                        newspapers.append(newspaper)

            if newspapers:
                logger.info(f"Found {len(newspapers)} newspapers using regex extraction")
                return newspapers
            else:
                # Fallback to a simple approach - just extract the LCCNs
                if lccns:
                    logger.info(f"Found {len(lccns)} LCCNs, but couldn't extract complete information")
                    return [{'lccn': lccn, 'title': f"Newspaper with LCCN {lccn}"} for lccn in lccns]
                else:
                    logger.warning("No newspaper data could be extracted from HTML")
                    return []
    
    except Exception as e:
        logger.error(f"Error fetching newspapers for {state_name}: {e}")
        return []

def main():
    """Test retrieving newspapers by state."""
    # Create a temporary output directory for saving results
    output_dir = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Test with a few different states
    states_to_test = ["Washington", "Colorado", "New York"]
    
    all_results = {}
    
    for state in states_to_test:
        logger.info(f"Fetching newspapers for state: {state}")
        
        # Call the API
        newspapers = get_newspapers_by_state(state)
        
        # Log results
        logger.info(f"Found {len(newspapers)} newspapers for {state}")
        
        # Store results for saving
        all_results[state] = newspapers
        
        # Show first few newspapers
        for i, newspaper in enumerate(newspapers[:5]):
            title = newspaper.get('title', 'Unknown Title')
            lccn = newspaper.get('lccn', 'Unknown LCCN')
            place = newspaper.get('place_of_publication', 'Unknown Location')
            start_year = newspaper.get('start_year', 'Unknown')
            end_year = newspaper.get('end_year', 'present')
            
            logger.info(f"  {i+1}. {title} (LCCN: {lccn})")
            logger.info(f"     Place: {place}, Years: {start_year}-{end_year}")
        
        if len(newspapers) > 5:
            logger.info(f"  ... and {len(newspapers) - 5} more")
        
        logger.info("-" * 50)
    
    # Save all results to a JSON file for reference
    result_file = os.path.join(output_dir, "newspapers_by_state_direct.json")
    with open(result_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"Saved all results to {result_file}")

if __name__ == "__main__":
    main()