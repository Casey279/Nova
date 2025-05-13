"""
Script to parse the state newspaper listings from Chronicling America
to extract the earliest issue dates.
"""

import os
import re
import requests
import logging
from datetime import datetime, date
import json
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_date(date_str):
    """Parse a date string in YYYY-MM-DD format to a formatted date."""
    try:
        if not date_str:
            return None
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        return date_obj.strftime("%B %d, %Y")  # Format as "Month Day, Year"
    except ValueError:
        logger.warning(f"Invalid date format: {date_str}")
        return None

def parse_state_newspapers(state="Washington"):
    """
    Parse the newspaper listings for a specific state to extract earliest issue dates.
    
    Args:
        state: State name (default: Washington)
        
    Returns:
        Dict mapping LCCNs to earliest issue dates
    """
    # Chronicling America base URL
    base_url = "https://chroniclingamerica.loc.gov"
    
    # Get the HTML page that lists newspapers for this state
    url = f"{base_url}/newspapers/?state={state}&ethnicity=&language="
    logger.info(f"Fetching {url}...")
    
    headers = {
        "User-Agent": "NovaHistoricalDatabase/1.0",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.loc.gov/collections/chronicling-america/",
        "Connection": "keep-alive"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            html = response.text
            
            # Save the HTML for debugging
            with open(f"{state}_newspapers.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"Saved HTML to {state}_newspapers.html")
            
            # Extract the table rows - the table structure is now clear after our investigation
            # <tr>
            #    <td class="first left_no_border"><a href="/newspapers/washington/">Washington</a></td>
            #    <td><a href="/lccn/sn87093056/"><strong>Adams County news. [volume]</strong></a><br />Ritzville, Wash., 1898-1906</td>
            #    <td><a href="/lccn/sn87093056/issues/"><img src="/media/images/calendar_icon.8112d58cf20c.gif" alt="calendar"/></a></td>
            #    <td>1979</td>
            #    <td><a href="/lccn/sn87093220/1890-10-23/ed-1/">1890-10-23</a></td>
            #    <td><a href="/lccn/sn87093220/1917-06-29/ed-1/">1917-06-29</a></td>
            #    <td class="last"><a href="/lccn/sn87093220/">Yes</a></td>
            # </tr>
            
            # Pattern to match each row in the table
            pattern = r'<tr>\s*<td[^>]*>.*?</td>\s*<td>.*?<a href="/lccn/([^/]+)/".*?<strong>(.*?)</strong>.*?</td>.*?<td>.*?</td>\s*<td>.*?</td>\s*<td><a href="[^"]*">(\d{4}-\d{2}-\d{2})</a></td>\s*<td>'
            
            matches = re.findall(pattern, html, re.DOTALL)
            
            if not matches:
                logger.warning(f"No newspaper rows found for {state} with pattern 1")
                
                # Try a more flexible pattern
                pattern2 = r'<tr>.*?<a href="/lccn/([^/]+)/.*?<strong>(.*?)</strong>.*?<td><a href="[^"]*">(\d{4}-\d{2}-\d{2})</a></td>'
                matches = re.findall(pattern2, html, re.DOTALL)
                
                if not matches:
                    logger.warning(f"No newspaper rows found for {state} with pattern 2")
                    return {}
            
            logger.info(f"Found {len(matches)} newspapers for {state}")
            
            results = {}
            
            # Process each match
            for lccn, title, earliest_date_str in matches:
                formatted_date = parse_date(earliest_date_str)
                
                results[lccn] = {
                    "title": title.strip(),
                    "earliest_date": formatted_date,
                    "raw_date": earliest_date_str
                }
                
                logger.info(f"Found {title.strip()} ({lccn}): {formatted_date}")
            
            return results
            
        else:
            logger.error(f"Error getting state newspapers page: {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"Error parsing state newspapers: {e}")
        return {}

def parse_multiple_states():
    """Parse newspapers from multiple states."""
    
    # List of states to parse
    states = ["Washington", "California", "New York", "Illinois", "District of Columbia"]
    
    all_results = {}
    
    for state in states:
        logger.info(f"\n\nParsing newspapers from {state}:")
        state_results = parse_state_newspapers(state)
        all_results[state] = state_results
    
    # Print summary
    logger.info("\n\nSummary of earliest issue dates by state:")
    
    for state, newspapers in all_results.items():
        logger.info(f"\n{state}: {len(newspapers)} newspapers")
        
        # Print a few examples
        for i, (lccn, data) in enumerate(list(newspapers.items())[:5]):
            date_str = data['earliest_date'] if data['earliest_date'] else "Not found"
            logger.info(f"  {data['title']} ({lccn}): {date_str}")
            
        if len(newspapers) > 5:
            logger.info(f"  ... and {len(newspapers) - 5} more")
    
    # Save results to a JSON file
    with open('earliest_dates_by_state.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info("\nResults saved to earliest_dates_by_state.json")
    
    # Create a flat version with just LCCN -> date mappings
    flat_results = {}
    for state, newspapers in all_results.items():
        for lccn, data in newspapers.items():
            flat_results[lccn] = {
                "title": data['title'],
                "earliest_date": data['earliest_date'],
                "raw_date": data.get('raw_date'),
                "state": state
            }
    
    # Save flat results to a JSON file
    with open('earliest_dates_flat.json', 'w') as f:
        json.dump(flat_results, f, indent=2)
    
    logger.info("Flat results saved to earliest_dates_flat.json")
    
    return flat_results

def main():
    """Main function."""
    
    # Parse newspapers from multiple states
    flat_results = parse_multiple_states()
    
    # Check for specific LCCNs
    lccns_to_check = [
        "sn83045604",  # Seattle Post-Intelligencer
        "sn83025121",  # Chicago Tribune
        "sn83030213",  # New York Tribune
        "sn83030214",  # New York Times
        "sn84026749",  # Washington Post
    ]
    
    logger.info("\nChecking specific newspapers:")
    
    for lccn in lccns_to_check:
        if lccn in flat_results:
            data = flat_results[lccn]
            logger.info(f"{data['title']} ({lccn}): {data['earliest_date']} [{data['state']}]")
        else:
            logger.info(f"{lccn}: Not found in parsed results")

if __name__ == "__main__":
    main()