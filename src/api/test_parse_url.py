"""
Test script to manually parse the HTML from the newspaper listing page to get earliest issue date.
This script does not require BeautifulSoup, it uses a simple regex approach.
"""

import os
import re
import requests
import logging
from datetime import datetime, date
import json

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_earliest_issue_date(lccn):
    """
    Get the earliest issue date for a newspaper using direct HTML parsing with regex.
    
    Args:
        lccn: Library of Congress Control Number
        
    Returns:
        date string of the earliest issue or None if not found
    """
    # Chronicling America base URL
    base_url = "https://chroniclingamerica.loc.gov"
    
    # Get the HTML page that lists this newspaper
    url = f"{base_url}/lccn/{lccn}"
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
            
            # Try to find the earliest issue date using regex
            # Pattern: typically in a format like <span>May 11, 1888</span> within the earliest issue area
            
            # First try a more specific pattern for the earliest issue element
            pattern1 = r'<th[^>]*>Earliest Issue</th>\s*<td[^>]*>(.*?)</td>'
            match1 = re.search(pattern1, html, re.IGNORECASE | re.DOTALL)
            
            if match1:
                html_content = match1.group(1).strip()
                # Now extract the date from this content
                date_pattern = r'([A-Z][a-z]+ \d{1,2}, \d{4})'
                date_match = re.search(date_pattern, html_content)
                if date_match:
                    date_str = date_match.group(1)
                    logger.info(f"Found earliest issue date with pattern 1: {date_str}")
                    return date_str
            
            # Try a broader pattern that might capture other formats
            pattern2 = r'earliest[-\s]issue.*?([A-Z][a-z]+ \d{1,2}, \d{4})'
            match2 = re.search(pattern2, html, re.IGNORECASE | re.DOTALL)
            
            if match2:
                date_str = match2.group(1)
                logger.info(f"Found earliest issue date with pattern 2: {date_str}")
                return date_str
                
            # If we still haven't found it, try a fallback - look for the issues.json data
            logger.info(f"Could not find earliest issue date in HTML, trying issues.json...")
            
            # Use the issues.json API endpoint
            issues_url = f"{base_url}/lccn/{lccn}/issues.json"
            issues_response = requests.get(issues_url, headers=headers)
            
            if issues_response.status_code == 200:
                issues_data = issues_response.json()
                issues = issues_data.get('issues', [])
                
                if issues:
                    # Sort issues by date
                    issues.sort(key=lambda x: x.get('date_issued', ''))
                    first_issue = issues[0]
                    earliest_issue_date_str = first_issue.get('date_issued', '')
                    
                    if earliest_issue_date_str:
                        try:
                            # Parse the date string to date object
                            earliest_date = datetime.strptime(earliest_issue_date_str, "%Y-%m-%d").date()
                            # Format as Month Day, Year
                            formatted_date = earliest_date.strftime("%B %d, %Y")
                            logger.info(f"Found earliest issue date from API: {formatted_date}")
                            return formatted_date
                        except ValueError:
                            logger.warning(f"Invalid date format for earliest issue from API: {earliest_issue_date_str}")
            
            # If all attempts failed, return None
            logger.warning(f"Could not find earliest issue date for {lccn}")
            return None
        else:
            logger.error(f"Error getting newspaper page: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting earliest issue date: {e}")
        return None

def test_newspapers():
    """Test earliest issue date detection for multiple newspapers."""
    
    # List of LCCNs to test
    newspapers = [
        ("sn83045604", "Seattle Post-Intelligencer"),
        ("sn83025121", "Chicago Tribune"),
        ("sn83030213", "New York Tribune"),
        ("sn83030214", "New York Times"),
        ("sn84026749", "Washington Post")
    ]
    
    results = {}
    
    for lccn, name in newspapers:
        logger.info(f"\n\nTesting {name} ({lccn}):")
        earliest_date_str = get_earliest_issue_date(lccn)
        results[lccn] = (name, earliest_date_str)
    
    # Print summary
    logger.info("\n\nSummary of earliest issue dates:")
    for lccn, (name, earliest_date_str) in results.items():
        date_str = earliest_date_str if earliest_date_str else "Not found"
        logger.info(f"{name} ({lccn}): {date_str}")
    
    # Save results to a JSON file
    with open('earliest_dates.json', 'w') as f:
        json_results = {lccn: {"name": name, "earliest_date": date} for lccn, (name, date) in results.items()}
        json.dump(json_results, f, indent=2)
    
    logger.info("\nResults saved to earliest_dates.json")

def main():
    """Main function."""
    
    # Test getting the earliest issue date for a specific newspaper
    lccn = "sn83045604"  # Seattle Post-Intelligencer
    name = "Seattle Post-Intelligencer"
    
    logger.info(f"Testing earliest issue date for {name} ({lccn})...")
    
    earliest_date_str = get_earliest_issue_date(lccn)
    
    if earliest_date_str:
        logger.info(f"Earliest issue date for {name}: {earliest_date_str}")
    else:
        logger.warning(f"Could not find earliest issue date for {name}")
    
    # Test multiple newspapers
    logger.info("\nTesting earliest issue date for multiple newspapers...")
    test_newspapers()

if __name__ == "__main__":
    main()