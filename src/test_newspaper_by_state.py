#!/usr/bin/env python3
"""
Test script to fetch newspapers by state from Chronicling America API.
This helps us understand the structure of the response.
"""

import os
import sys
import logging
import requests
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_newspapers_by_state(state_name):
    """
    Retrieve newspapers by state name using the Chronicling America API.

    Args:
        state_name: Full state name (e.g., "Washington", "Colorado")

    Returns:
        List of newspaper dictionaries
    """
    # The API uses an OpenSearch endpoint for titles
    url = "https://chroniclingamerica.loc.gov/search/titles/results/"

    # Parameters for the search
    params = {
        'terms': state_name,  # Search for the state name in the title records
        'format': 'json'      # Return JSON format
    }

    logger.info(f"API Request: {url}?terms={state_name}&format=json")

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Extract items from the response
        if 'items' in data:
            items = data['items']
        else:
            items = []

        logger.info(f"API Response: status_code={response.status_code}, items={len(items)}")
        return items

    except Exception as e:
        logger.error(f"Error fetching newspapers for {state_name}: {e}")
        return []

def main():
    """Test retrieving newspapers by state."""
    # Create a temporary output directory for saving results
    output_dir = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_dir, exist_ok=True)

    # Test with a few different states using full state names
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
    result_file = os.path.join(output_dir, "newspapers_by_state.json")
    with open(result_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    logger.info(f"Saved all results to {result_file}")

if __name__ == "__main__":
    main()