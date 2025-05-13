"""
Improved ChroniclingAmerica API Client

This module provides an optimized client for interacting with the Library of Congress
Chronicling America API to search and download historical newspaper content.

Key improvements:
- Better date filtering using a combination of API parameters and post-processing
- Improved error handling
- More robust results parsing
- Better handling of the API's response quirks
- Precise earliest issue date detection
"""

import os
import time
import json
import re
import requests
from typing import Dict, List, Optional, Union, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, date, timedelta
import logging
from copy import deepcopy

# Import the earliest date provider
from .chronicling_america_earliest_dates import get_earliest_date, get_latest_date, get_newspaper_title
from .chronicling_america_gap_detection import NewspaperGapDetector, format_gap_for_display, generate_chronicling_america_url

# Try to import BeautifulSoup, but don't require it
try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False
    # Define a fallback function for parsing HTML
    def extract_earliest_date_from_html(html_content, lccn):
        """
        Extract earliest issue date from HTML content using regex.
        
        Args:
            html_content: HTML content from the newspaper page
            lccn: Library of Congress Control Number
            
        Returns:
            date object of the earliest issue or None if not found
        """
        # Pattern to match the earliest issue date (typically format: "May 11, 1888")
        pattern = r'<th[^>]*>Earliest\s+Issue</th>\s*<td[^>]*>([A-Z][a-z]+\s+\d{1,2},\s+\d{4})</td>'
        match = re.search(pattern, html_content, re.IGNORECASE)
        
        if match:
            date_text = match.group(1).strip()
            try:
                earliest_date = datetime.strptime(date_text, "%B %d, %Y").date()
                return earliest_date
            except ValueError:
                pass
                
        return None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NewspaperMetadata:
    """Structured container for newspaper metadata"""
    lccn: str  # Library of Congress Control Number
    title: str
    place_of_publication: str
    start_year: int
    end_year: Optional[int]
    url: str
    publisher: Optional[str] = None
    language: Optional[List[str]] = None
    earliest_issue_date: Optional[date] = None  # Exact earliest issue date
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'NewspaperMetadata':
        """Create a NewspaperMetadata object from API JSON response"""
        return cls(
            lccn=json_data.get('lccn', ''),
            title=json_data.get('title', ''),
            place_of_publication=json_data.get('place_of_publication', ''),
            start_year=int(json_data.get('start_year', 0)),
            end_year=int(json_data.get('end_year', 0)) if json_data.get('end_year') else None,
            url=json_data.get('url', ''),
            publisher=json_data.get('publisher', None),
            language=json_data.get('language', []),
            earliest_issue_date=None  # Will be populated later if available
        )

@dataclass
class PageMetadata:
    """Structured container for newspaper page metadata"""
    lccn: str
    issue_date: date
    edition: Optional[int]
    sequence: int  # Page number within the issue
    url: str
    jp2_url: Optional[str]
    pdf_url: Optional[str]
    ocr_url: Optional[str]
    title: str
    page_number: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'PageMetadata':
        """Create a PageMetadata object from API JSON response"""
        # Parse the date string to date object
        issue_date_str = json_data.get('date', '')
        try:
            # Handle both YYYYMMDD and YYYY-MM-DD formats
            if issue_date_str and len(issue_date_str) == 8 and issue_date_str.isdigit():
                # Format YYYYMMDD to YYYY-MM-DD
                year = issue_date_str[:4]
                month = issue_date_str[4:6]
                day = issue_date_str[6:8]
                formatted_date_str = f"{year}-{month}-{day}"
                issue_date_obj = datetime.strptime(formatted_date_str, "%Y-%m-%d").date()
            else:
                # Standard format YYYY-MM-DD
                issue_date_obj = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Invalid date format: {issue_date_str}")
            issue_date_obj = date(1900, 1, 1)  # Fallback date
            
        return cls(
            lccn=json_data.get('lccn', ''),
            issue_date=issue_date_obj,
            edition=json_data.get('edition', None),
            sequence=json_data.get('sequence', 0),
            url=json_data.get('url', ''),
            jp2_url=json_data.get('jp2_url', None),
            pdf_url=json_data.get('pdf_url', None),
            ocr_url=json_data.get('ocr_url', None),
            title=json_data.get('title', ''),
            page_number=json_data.get('page_number', None)
        )


class ImprovedChroniclingAmericaClient:
    """
    Improved client for interacting with the Library of Congress Chronicling America API.
    
    This client provides optimized methods to search and download historical newspaper 
    content from the Chronicling America database.
    """
    
    # Chronicling America API endpoints
    BASE_URL = "https://chroniclingamerica.loc.gov"
    API_URL = f"{BASE_URL}/search/pages/results/"  # The pages search API
    NEWSPAPERS_URL = f"{BASE_URL}/newspapers.json"  # Gets a list of all newspapers
    
    # Default request headers
    HEADERS = {
        "User-Agent": "NovaHistoricalDatabase/1.0",
        "Accept": "application/json",
        "Referer": "https://www.loc.gov/collections/chronicling-america/",
        "Connection": "keep-alive"
    }
    
    # Rate limiting parameters - increased to be more conservative with the new API
    REQUEST_DELAY = 1.0  # Seconds between requests
    MAX_RETRIES = 3      # Number of retries for failed requests
    BACKOFF_FACTOR = 2.0 # Exponential backoff factor
    
    def __init__(self, output_directory: str, request_delay: float = REQUEST_DELAY):
        """
        Initialize the improved ChroniclingAmerica API client.

        Args:
            output_directory: Directory to save downloaded files
            request_delay: Seconds to wait between API requests (for rate limiting)
        """
        self.output_directory = output_directory
        self.request_delay = request_delay
        self.last_request_time = 0

        # Create output directory structure if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)

        # Create subdirectories for different content types
        self.jp2_directory = os.path.join(output_directory, "jp2")
        self.pdf_directory = os.path.join(output_directory, "pdf")
        self.ocr_directory = os.path.join(output_directory, "ocr")
        self.json_directory = os.path.join(output_directory, "json")

        for directory in [self.jp2_directory, self.pdf_directory,
                         self.ocr_directory, self.json_directory]:
            os.makedirs(directory, exist_ok=True)

        # Cache for issue dates (lccn -> date)
        self.earliest_issue_cache = {}
        self.latest_issue_cache = {}

        # Initialize gap detector for smart date range handling
        gap_knowledge_file = os.path.join(output_directory, "newspaper_gaps.json")
        self.gap_detector = NewspaperGapDetector(
            content_checker_func=self.check_date_has_content,
            knowledge_file=gap_knowledge_file
        )
    
    def _respect_rate_limit(self):
        """Ensure we don't exceed the rate limit by adding delays between requests"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.request_delay:
            time.sleep(self.request_delay - time_since_last_request)
            
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None, 
                     stream: bool = False) -> requests.Response:
        """
        Make an HTTP request with rate limiting, retries, and error handling.
        
        Args:
            url: The URL to request
            params: Optional query parameters
            stream: Whether to stream the response (for downloading large files)
            
        Returns:
            Response object from the request
        
        Raises:
            requests.RequestException: If the request fails after all retries
        """
        self._respect_rate_limit()
        
        # Ensure we have the fo=json parameter for API requests if not streaming
        if not stream and params is not None and 'fo' not in params:
            params['fo'] = 'json'
        
        # Initialize retry counter
        retries = 0
        last_error = None
        
        # Try the request with exponential backoff
        while retries <= self.MAX_RETRIES:
            try:
                # Log the full URL and parameters for debugging
                param_str = "&".join([f"{k}={v}" for k, v in (params or {}).items()])
                full_url = f"{url}?{param_str}" if param_str else url
                logger.info(f"API Request: {full_url}")
                
                response = requests.get(url, params=params, headers=self.HEADERS, stream=stream)
                response.raise_for_status()
                
                # Log response details for debugging
                if not stream:
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        try:
                            data = response.json()
                            items_count = 0
                            if 'items' in data:
                                items_count = len(data['items'])
                            elif 'results' in data:
                                items_count = len(data['results'])
                            elif 'content' in data and 'results' in data['content']:
                                items_count = len(data['content']['results'])
                                
                            logger.info(f"API Response: status_code={response.status_code}, content_length={len(response.content)}, items={items_count}")
                        except Exception as e:
                            logger.warning(f"Could not parse JSON response: {e}")
                
                return response
            
            except requests.RequestException as e:
                last_error = e
                retries += 1
                
                if retries <= self.MAX_RETRIES:
                    # Calculate backoff time
                    backoff_time = self.request_delay * (self.BACKOFF_FACTOR ** (retries - 1))
                    logger.warning(f"Request failed (attempt {retries}/{self.MAX_RETRIES}): {e}")
                    logger.warning(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
                else:
                    # All retries failed
                    logger.error(f"API request failed after {self.MAX_RETRIES} retries: {e}")
                    raise
    
    def get_earliest_issue_date(self, lccn: str) -> Optional[date]:
        """
        Get the earliest issue date for a newspaper.

        This method uses multiple sources:
        1. Check the local cache first
        2. Check the earliest_dates module
        3. Try to parse the HTML from the newspaper listing page
        4. Use the issues.json API endpoint

        Args:
            lccn: Library of Congress Control Number

        Returns:
            date object of the earliest issue or None if not found
        """
        # Check cache first
        if lccn in self.earliest_issue_cache:
            logger.info(f"Using cached earliest issue date for {lccn}")
            return self.earliest_issue_cache[lccn]

        # Check earliest_dates module
        earliest_date = get_earliest_date(lccn)
        if earliest_date:
            logger.info(f"Found earliest issue date from module: {earliest_date}")
            self.earliest_issue_cache[lccn] = earliest_date
            return earliest_date

        # If not found in module, try to fetch it from the API
        logger.info(f"Trying to fetch earliest issue date for {lccn} from API")

        # APPROACH 1: Parse the HTML from the newspaper listing page
        try:
            # Get the HTML page that lists this newspaper
            url = f"{self.BASE_URL}/lccn/{lccn}"
            self._respect_rate_limit()
            response = requests.get(url, headers=self.HEADERS)

            if response.status_code == 200:
                html_content = response.text

                # Parse the HTML using BeautifulSoup if available, otherwise use regex
                if HAS_BEAUTIFULSOUP:
                    # Use BeautifulSoup to parse the HTML
                    soup = BeautifulSoup(html_content, 'html.parser')

                    # Look for the earliest issue info
                    # It's usually in a specific layout with labeled fields
                    earliest_issue_element = soup.select_one('span[class*="earliest-issue"]')
                    if earliest_issue_element:
                        date_text = earliest_issue_element.get_text().strip()
                        logger.info(f"Found earliest issue element with text: {date_text}")

                        # Parse the date text (typically format: "May 11, 1888")
                        try:
                            earliest_date = datetime.strptime(date_text, "%B %d, %Y").date()
                            logger.info(f"Successfully parsed earliest issue date: {earliest_date}")
                            self.earliest_issue_cache[lccn] = earliest_date
                            return earliest_date
                        except ValueError:
                            logger.warning(f"Could not parse earliest issue date: {date_text}")

                    # If not found directly, try alternative search in the metadata
                    if not earliest_date:
                        # Look for earliest issue in the metadata section
                        meta_section = soup.select_one('.newspaper-metadata')
                        if meta_section:
                            issue_rows = meta_section.select('tr')
                            for row in issue_rows:
                                label = row.select_one('th')
                                value = row.select_one('td')
                                if label and value and 'earliest' in label.get_text().lower():
                                    date_text = value.get_text().strip()
                                    logger.info(f"Found earliest issue in metadata: {date_text}")
                                    try:
                                        earliest_date = datetime.strptime(date_text, "%B %d, %Y").date()
                                        logger.info(f"Successfully parsed earliest issue date from metadata: {earliest_date}")
                                        self.earliest_issue_cache[lccn] = earliest_date
                                        return earliest_date
                                    except ValueError:
                                        logger.warning(f"Could not parse earliest issue date from metadata: {date_text}")
                else:
                    # Fall back to regex-based parsing
                    earliest_date = extract_earliest_date_from_html(html_content, lccn)
                    if earliest_date:
                        logger.info(f"Found earliest issue date using regex: {earliest_date}")
                        self.earliest_issue_cache[lccn] = earliest_date
                        return earliest_date

        except Exception as e:
            logger.warning(f"Error parsing HTML for earliest issue date: {e}")

        # APPROACH 2: If HTML parsing didn't work, try the issues.json API
        try:
            issues_url = f"{self.BASE_URL}/lccn/{lccn}/issues.json"
            self._respect_rate_limit()
            issues_response = requests.get(issues_url, headers=self.HEADERS)

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
                            logger.info(f"Found earliest issue date from API: {earliest_date}")
                            self.earliest_issue_cache[lccn] = earliest_date
                            return earliest_date
                        except ValueError:
                            logger.warning(f"Invalid date format for earliest issue from API: {earliest_issue_date_str}")

        except Exception as e:
            logger.warning(f"Error getting earliest issue date from API: {e}")

        # If we couldn't find the earliest issue date, return None
        logger.warning(f"Could not find earliest issue date for {lccn}")
        return None

    def check_date_has_content(self, lccn: str, check_date: date) -> bool:
        """
        Check if a specific date has newspaper content available.

        Args:
            lccn: Library of Congress Control Number
            check_date: Date to check for content

        Returns:
            True if content exists for this date, False otherwise
        """
        try:
            # Format date for URL
            date_str = check_date.strftime("%Y-%m-%d")

            # Use a HEAD request to check if the issue exists
            # Format: https://chroniclingamerica.loc.gov/lccn/sn83045604/1892-01-01/ed-1/seq-1.jp2
            url = f"{self.BASE_URL}/lccn/{lccn}/{date_str}/ed-1/seq-1.jp2"

            self._respect_rate_limit()
            response = requests.head(url, headers=self.HEADERS)

            # If we get a 200 response, content exists for this date
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Error checking content for {lccn} on {check_date}: {e}")
            return False

    def get_latest_issue_date(self, lccn: str) -> Optional[date]:
        """
        Get the latest issue date for a newspaper.

        This method uses multiple sources:
        1. Check the local cache first
        2. Check the date provider module
        3. Try to parse the HTML from the newspaper listing page
        4. Use the issues.json API endpoint

        Args:
            lccn: Library of Congress Control Number

        Returns:
            date object of the latest issue or None if not found
        """
        # Check cache first
        if lccn in self.latest_issue_cache:
            logger.info(f"Using cached latest issue date for {lccn}")
            return self.latest_issue_cache[lccn]

        # Check dates module
        latest_date = get_latest_date(lccn)
        if latest_date:
            logger.info(f"Found latest issue date from module: {latest_date}")
            self.latest_issue_cache[lccn] = latest_date
            return latest_date

        # If not found in module, try to fetch it from the API
        logger.info(f"Trying to fetch latest issue date for {lccn} from API")

        # APPROACH 1: Parse the HTML from the newspaper listing page
        try:
            # Get the HTML page that lists this newspaper
            url = f"{self.BASE_URL}/lccn/{lccn}"
            self._respect_rate_limit()
            response = requests.get(url, headers=self.HEADERS)

            if response.status_code == 200:
                html_content = response.text

                # Parse the HTML using BeautifulSoup if available, otherwise use regex
                if HAS_BEAUTIFULSOUP:
                    # Use BeautifulSoup to parse the HTML
                    soup = BeautifulSoup(html_content, 'html.parser')

                    # Look for the latest issue in the metadata section
                    meta_section = soup.select_one('.newspaper-metadata')
                    if meta_section:
                        issue_rows = meta_section.select('tr')
                        for row in issue_rows:
                            label = row.select_one('th')
                            value = row.select_one('td')
                            if label and value and 'latest' in label.get_text().lower():
                                date_text = value.get_text().strip()
                                logger.info(f"Found latest issue in metadata: {date_text}")
                                try:
                                    latest_date = datetime.strptime(date_text, "%B %d, %Y").date()
                                    logger.info(f"Successfully parsed latest issue date from metadata: {latest_date}")
                                    self.latest_issue_cache[lccn] = latest_date
                                    return latest_date
                                except ValueError:
                                    logger.warning(f"Could not parse latest issue date from metadata: {date_text}")
                else:
                    # Fall back to regex-based parsing for latest date
                    pattern = r'<th[^>]*>Latest\s+Issue</th>\s*<td[^>]*>([A-Z][a-z]+\s+\d{1,2},\s+\d{4})</td>'
                    match = re.search(pattern, html_content, re.IGNORECASE)

                    if match:
                        date_text = match.group(1).strip()
                        try:
                            latest_date = datetime.strptime(date_text, "%B %d, %Y").date()
                            logger.info(f"Found latest issue date using regex: {latest_date}")
                            self.latest_issue_cache[lccn] = latest_date
                            return latest_date
                        except ValueError:
                            logger.warning(f"Could not parse latest issue date: {date_text}")

        except Exception as e:
            logger.warning(f"Error parsing HTML for latest issue date: {e}")

        # APPROACH 2: If HTML parsing didn't work, try the issues.json API
        try:
            issues_url = f"{self.BASE_URL}/lccn/{lccn}/issues.json"
            self._respect_rate_limit()
            issues_response = requests.get(issues_url, headers=self.HEADERS)

            if issues_response.status_code == 200:
                issues_data = issues_response.json()
                issues = issues_data.get('issues', [])

                if issues:
                    # Sort issues by date (descending)
                    issues.sort(key=lambda x: x.get('date_issued', ''), reverse=True)
                    last_issue = issues[0]
                    latest_issue_date_str = last_issue.get('date_issued', '')

                    if latest_issue_date_str:
                        try:
                            # Parse the date string to date object
                            latest_date = datetime.strptime(latest_issue_date_str, "%Y-%m-%d").date()
                            logger.info(f"Found latest issue date from API: {latest_date}")
                            self.latest_issue_cache[lccn] = latest_date
                            return latest_date
                        except ValueError:
                            logger.warning(f"Invalid date format for latest issue from API: {latest_issue_date_str}")

        except Exception as e:
            logger.warning(f"Error getting latest issue date from API: {e}")

        # If we couldn't find the latest issue date, return None
        logger.warning(f"Could not find latest issue date for {lccn}")
        return None
    
    def search_newspapers(self, 
                        state: Optional[str] = None,
                        county: Optional[str] = None,
                        title: Optional[str] = None,
                        year: Optional[int] = None) -> List[NewspaperMetadata]:
        """
        Search for newspapers in the Chronicling America database.
        
        Args:
            state: Filter by state (e.g., 'California', 'New York')
            county: Filter by county
            title: Filter by newspaper title
            year: Filter by year of publication
            
        Returns:
            List of NewspaperMetadata objects matching the criteria
        """
        # Build query parameters for the API
        params = {}
        
        # Add filter parameters
        if state:
            params['state'] = state
        if county:
            params['county'] = county
        if title:
            params['title'] = title
        if year:
            params['year'] = str(year)
            
        # Additional required parameters for the API
        params['fo'] = 'json'        # Request JSON format
        params['c'] = 100            # Results per page (max allowed)
        
        try:
            response = self._make_request(self.NEWSPAPERS_URL, params)
            data = response.json()
            
            # Extract newspapers from the API response
            newspapers = []
            
            # Different APIs may return different structures
            items = data.get('newspapers', [])
            if not items:
                # Try alternate response formats
                items = data.get('results', [])
                if not items and 'content' in data:
                    items = data.get('content', {}).get('results', [])
            
            # Process each item
            for item in items:
                try:
                    # Extract LCCN 
                    lccn = item.get('lccn', '')
                    if not lccn:
                        # Try to extract from URL
                        url_str = item.get('id', '') or item.get('url', '')
                        lccn_match = re.search(r'lccn/([^/]+)', url_str)
                        if lccn_match:
                            lccn = lccn_match.group(1)
                    
                    newspaper = NewspaperMetadata.from_json(item)
                    
                    # Try to get earliest issue date
                    earliest_date = self.get_earliest_issue_date(lccn)
                    if earliest_date:
                        newspaper.earliest_issue_date = earliest_date
                        logger.info(f"Added earliest issue date {earliest_date} for {newspaper.title}")
                    
                    newspapers.append(newspaper)
                except Exception as e:
                    logger.warning(f"Failed to parse newspaper data: {e}")
                    continue
            
            logger.info(f"Found {len(newspapers)} newspapers")
            return newspapers
            
        except requests.RequestException as e:
            logger.error(f"Failed to search newspapers: {e}")
            return []
    
    def search_pages(self,
                    keywords: Optional[str] = None,
                    lccn: Optional[str] = None,
                    state: Optional[str] = None,
                    date_start: Optional[Union[str, date]] = None,
                    date_end: Optional[Union[str, date]] = None,
                    page: int = 1,
                    items_per_page: int = 20,
                    max_pages: int = 1,
                    detect_gaps: bool = False,
                    gap_threshold: int = 5) -> Tuple[List[PageMetadata], Dict[str, Any]]:
        """
        Search for newspaper pages matching the given criteria.

        This improved method uses optimized strategies to find pages within the given date range.
        It can also detect gaps in newspaper availability and handle them intelligently.

        Args:
            keywords: Search terms
            lccn: Library of Congress Control Number for specific newspaper
            state: Filter by state (e.g., 'California', 'New York')
            date_start: Start date for search range (YYYY-MM-DD or date object)
            date_end: End date for search range (YYYY-MM-DD or date object)
            page: Page number for pagination (default: 1)
            items_per_page: Number of results per page (default: 20)
            max_pages: Maximum number of pages to retrieve (default: 1)
            detect_gaps: Whether to detect and analyze gaps in content availability (default: False)
            gap_threshold: Number of consecutive days without content to trigger gap detection (default: 5)

        Returns:
            Tuple containing:
                - List of PageMetadata objects
                - Dict with pagination info (total_items, pages, etc.)
        """
        # Convert date objects to strings if needed
        if isinstance(date_start, date):
            date_start_str = date_start.strftime("%Y-%m-%d")
        else:
            date_start_str = date_start
            
        if isinstance(date_end, date):
            date_end_str = date_end.strftime("%Y-%m-%d")
        else:
            date_end_str = date_end

        # Parse start and end dates for comparison
        start_date = None
        if date_start_str:
            try:
                start_date = datetime.strptime(date_start_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid start date format: {date_start_str}")
                
        end_date = None
        if date_end_str:
            try:
                end_date = datetime.strptime(date_end_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid end date format: {date_end_str}")

        # Log input parameters for debugging
        logger.info(f"Search parameters: keywords={keywords}, lccn={lccn}, state={state}, date_start={date_start_str}, date_end={date_end_str}, page={page}")

        # Track information about gaps and adjusted dates for return
        search_info = {
            'adjusted_dates': {},
            'gaps': [],
            'has_more_content': True
        }

        # If we have an LCCN and a start date, try to get the earliest issue date and use it
        if lccn and start_date:
            earliest_date = self.get_earliest_issue_date(lccn)
            if earliest_date and start_date < earliest_date:
                logger.info(f"Adjusting start date from {start_date} to {earliest_date} (first issue)")
                start_date = earliest_date
                date_start_str = start_date.strftime("%Y-%m-%d")

                # Record this adjustment
                search_info['adjusted_dates']['start'] = {
                    'original': date_start_str,
                    'adjusted': start_date.isoformat(),
                    'reason': 'first_issue'
                }

                # Log the adjusted search parameters
                logger.info(f"Adjusted search parameters: date_start={date_start_str}")

        # If we have an LCCN and an end date, try to get the latest issue date and use it
        if lccn and end_date:
            latest_date = self.get_latest_issue_date(lccn)
            if latest_date:
                # Verify that this latest date actually has content
                if detect_gaps:
                    verified_latest = self.gap_detector.verify_latest_date(lccn, latest_date)
                    if verified_latest and verified_latest != latest_date:
                        logger.info(f"Verified latest date differs from supposed latest date: {verified_latest} vs {latest_date}")
                        latest_date = verified_latest

                if end_date > latest_date:
                    logger.info(f"Adjusting end date from {end_date} to {latest_date} (last issue)")
                    end_date = latest_date
                    date_end_str = end_date.strftime("%Y-%m-%d")

                    # Record this adjustment
                    search_info['adjusted_dates']['end'] = {
                        'original': date_end_str,
                        'adjusted': end_date.isoformat(),
                        'reason': 'last_issue'
                    }

                    # Log the adjusted search parameters
                    logger.info(f"Adjusted search parameters: date_end={date_end_str}")

        # Extract date components for improved search
        # Important: We need to extract date components AFTER adjusting the dates for earliest/latest issue dates
        date_year = None
        date_month = None
        date_month_text = None

        # Use adjusted start date (now in start_date) to get year and month
        if start_date:
            date_year = start_date.year
            date_month = start_date.month

            # Convert month number to text for potential text search
            month_names = ["january", "february", "march", "april", "may", "june",
                           "july", "august", "september", "october", "november", "december"]
            if 1 <= date_month <= 12:
                date_month_text = month_names[date_month - 1]

            logger.info(f"Extracted date components from adjusted start date: year={date_year}, month={date_month} ({date_month_text})")

        # Build basic query parameters for the Chronicling America API
        base_params = {
            'format': 'json',   # Return JSON format
            'page': page,
            'rows': items_per_page  # Number of results per page
        }

        # Add search parameters (common to all strategies)
        if keywords:
            base_params['andtext'] = keywords
            logger.info(f"Using keyword filter: {keywords}")
        if lccn:
            base_params['lccn'] = lccn.strip()
            logger.info(f"Using LCCN filter: {lccn}")

        # We'll use multiple search strategies and combine results
        strategies = []

        # STRATEGY 1: Web UI date format (MM/DD/YYYY) - most accurate, matches the web UI exactly
        if date_start_str and date_end_str:
            strategy1 = deepcopy(base_params)
            strategy1['searchType'] = 'advanced'  # This is required for date filtering
            strategy1['dateFilterType'] = 'range'

            # Format dates as MM/DD/YYYY exactly as the web UI does
            # But use our already adjusted dates for earliest/latest issue constraints
            strategy1['date1'] = start_date.strftime("%m/%d/%Y")
            strategy1['date2'] = end_date.strftime("%m/%d/%Y")

            logger.info(f"Using web UI date format: {strategy1['date1']} to {strategy1['date2']}")

            # This is our primary strategy - try it first
            strategies.append(("Web UI date format", strategy1))

        # STRATEGY 2: Direct date URL construction - for specific cases
        if date_start_str and date_end_str and lccn:
            # This approach directly constructs URLs for each date and checks if they exist
            # Useful for cases where the API search might miss some pages

            logger.info("Using direct URL construction strategy for date range")

            # Generate all dates in the range, but only a reasonable number
            direct_pages = []
            date_range = []

            # Check if date range is too large (more than 2 years)
            date_diff = (end_date - start_date).days
            if date_diff > 730:  # ~2 years
                logger.warning(f"Date range too large ({date_diff} days). Limiting search to API-based methods.")
                # Skip direct URL strategy for large date ranges
                date_range = []
            else:
                # Generate all dates in the range - using the already adjusted start and end dates
                # which respect earliest and latest issue dates
                logger.info(f"Generating URLs for date range: {start_date} to {end_date} (adjusted for available issues)")
                current_date = start_date
                while current_date <= end_date:
                    date_range.append(current_date)
                    current_date += timedelta(days=1)

            strategy_direct = deepcopy(base_params)
            strategies.append(("Direct URL construction", strategy_direct))

        # STRATEGY 3: Year + month as text - fallback if web UI format fails
        if date_year and date_month_text:
            strategy3 = deepcopy(base_params)
            strategy3['year'] = str(date_year)
            strategy3['ortext'] = date_month_text
            logger.info(f"Using Year {date_year} + month '{date_month_text}' strategy - based on adjusted date range")
            strategies.append((f"Year {date_year} + month '{date_month_text}'", strategy3))

        # STRATEGY 4: Year only - last resort fallback
        if date_year:
            strategy4 = deepcopy(base_params)
            strategy4['year'] = str(date_year)
            logger.info(f"Using Year {date_year} only strategy - based on adjusted date range")
            strategies.append((f"Year {date_year} only", strategy4))
        
        # Combined results from all strategies
        all_pages = []
        pagination_info = {}
        
        # Try each search strategy
        for strategy_name, params in strategies:
            logger.info(f"Trying search strategy: {strategy_name}")

            # Special handling for direct URL construction strategy
            if strategy_name == "Direct URL construction":
                pages = []

                # For each date in the range, directly check if the issue exists
                for current_date in date_range:
                    date_str = current_date.strftime("%Y-%m-%d")
                    logger.info(f"Checking direct URL for date: {date_str}")

                    # Base URL for this date
                    # Format: https://chroniclingamerica.loc.gov/lccn/sn83045604/1892-01-01/ed-1/
                    base_url = f"{self.BASE_URL}/lccn/{lccn}/{date_str}/ed-1"

                    # Try up to 20 page numbers for this date
                    for page_num in range(1, 21):  # 20 pages max per issue
                        # Check if this page exists
                        page_url = f"{base_url}/seq-{page_num}"
                        jp2_url = f"{page_url}.jp2"

                        # Make a HEAD request to see if the page exists
                        try:
                            self._respect_rate_limit()
                            response = requests.head(jp2_url, headers=self.HEADERS)

                            # If page exists, create a PageMetadata object
                            if response.status_code == 200:
                                logger.info(f"Found page {page_num} for date {date_str}")

                                # Create page data
                                page_data = {
                                    'lccn': lccn,
                                    'date': current_date.strftime("%Y%m%d"),
                                    'sequence': page_num,
                                    'url': page_url,
                                    'title': f"Page {page_num}",
                                    'jp2_url': jp2_url,
                                    'pdf_url': f"{page_url}.pdf",
                                    'ocr_url': f"{page_url}/ocr/"
                                }

                                # Create PageMetadata object
                                page_obj = PageMetadata.from_json(page_data)
                                pages.append(page_obj)
                            else:
                                # If this page doesn't exist, try the next date
                                if page_num == 1:
                                    logger.info(f"No issue found for date {date_str}")
                                else:
                                    logger.info(f"No more pages for date {date_str} after page {page_num-1}")
                                break

                        except Exception as e:
                            logger.warning(f"Error checking page {page_num} for date {date_str}: {e}")
                            break

                if pages:
                    logger.info(f"Direct URL strategy found {len(pages)} pages")
                    all_pages.extend(pages)

                    # Create a mock pagination info since we're not using the API search
                    if not pagination_info:
                        pagination_info = {
                            'total_items': len(pages),
                            'total_pages': 1,
                            'current_page': 1
                        }

                # Continue to the next strategy even if we found pages
                continue

            # Standard API-based strategies
            try:
                # Make the API request with this strategy
                response = self._make_request(self.API_URL, params)
                data = response.json()

                # Extract pages from the API response
                pages = []
                items = data.get('items', [])
                
                # Debug log
                logger.info(f"Strategy '{strategy_name}' returned {len(items)} items")
                
                # Process each item
                for item in items:
                    try:
                        # Check if item is a dictionary (some APIs might return strings or other types)
                        if not isinstance(item, dict):
                            logger.warning(f"Item is not a dictionary: {type(item)}")
                            continue

                        # Extract data from API response based on its actual structure
                        # The API returns different formats than expected
                        lccn = item.get('lccn', '')
                        date_str = item.get('date', '')
                        sequence = item.get('sequence', 1)

                        # Get URL from id field
                        url = item.get('id', '')
                        if not url.startswith('http'):
                            # Convert relative URL to absolute URL
                            url = f"https://chroniclingamerica.loc.gov{url}"

                        # Get title (plain string in this API)
                        title = item.get('title', f"Page {sequence}")

                        # Construct URLs for different formats
                        jp2_url = f"{url.rstrip('/')}.jp2"
                        pdf_url = f"{url.rstrip('/')}.pdf"
                        ocr_url = f"{url.rstrip('/')}/ocr/"

                        # Create page metadata
                        page_data = {
                            'lccn': lccn,
                            'date': date_str,
                            'sequence': sequence,
                            'url': url,
                            'title': title,
                            'jp2_url': jp2_url,
                            'pdf_url': pdf_url,
                            'ocr_url': ocr_url
                        }
                        
                        # Create PageMetadata object
                        page_obj = PageMetadata.from_json(page_data)
                        pages.append(page_obj)
                    except Exception as e:
                        logger.warning(f"Failed to parse page data: {e}")
                        continue
                
                # If no pages found with this strategy, try the next one
                if not pages:
                    logger.info(f"Strategy '{strategy_name}' found no results, trying next strategy")
                    continue
                    
                # Apply post-processing filter for date range using adjusted dates
                filtered_pages = []

                # Use our adjusted start and end dates for filtering
                # These have already been adjusted for earliest/latest issue dates

                # Filter pages by date
                for page_obj in pages:
                    page_date = page_obj.issue_date

                    # Skip if before adjusted start date
                    if start_date and page_date < start_date:
                        logger.debug(f"Filtering out page from {page_date} (before adjusted start date {start_date})")
                        continue

                    # Skip if after adjusted end date
                    if end_date and page_date > end_date:
                        logger.debug(f"Filtering out page from {page_date} (after adjusted end date {end_date})")
                        continue

                    # Page is within adjusted date range, keep it
                    filtered_pages.append(page_obj)

                # Log filtering results
                logger.info(f"Date filtering: {len(filtered_pages)}/{len(pages)} pages are within the requested date range (adjusted for available issues)")
                pages = filtered_pages
                
                # If we got some results after filtering, add them to the combined results
                if pages:
                    all_pages.extend(pages)
                    
                    # Store pagination information from the most successful strategy
                    if not pagination_info:
                        total_items = data.get('totalItems', 0)
                        total_pages = (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 0
                        
                        pagination_info = {
                            'total_items': total_items,
                            'total_pages': total_pages,
                            'current_page': page
                        }
                        
                        logger.info(f"Strategy '{strategy_name}' provides pagination: page {page} of {total_pages}, total items: {total_items}")
                
            except Exception as e:
                logger.warning(f"Search strategy '{strategy_name}' failed: {e}")
                continue
        
        # If we have results but no pagination info, create a default one
        if all_pages and not pagination_info:
            pagination_info = {
                'total_items': len(all_pages),
                'total_pages': 1,
                'current_page': 1
            }

        # Remove duplicates based on LCCN + date + sequence
        unique_pages = {}
        for page in all_pages:
            key = f"{page.lccn}_{page.issue_date}_{page.sequence}"
            if key not in unique_pages:
                unique_pages[key] = page

        result_pages = list(unique_pages.values())

        # Sort results by date AND page number
        result_pages.sort(key=lambda p: (p.issue_date, p.sequence))

        # Log final results
        logger.info(f"Final results: Found {len(result_pages)} unique pages")

        # If we found no results across all strategies, return empty values
        if not result_pages:
            return [], {'total_items': 0, 'total_pages': 0, 'current_page': page, 'search_info': search_info}

        # If gap detection is enabled and we have an LCCN, analyze the date range
        if detect_gaps and lccn and start_date and end_date:
            # First check if there are large sections without content
            if len(result_pages) > 0:
                # Get the date range covered by the results
                result_dates = [p.issue_date for p in result_pages]
                min_result_date = min(result_dates)
                max_result_date = max(result_dates)

                # If the results don't cover the full requested range, this might indicate gaps
                if (min_result_date > start_date) or (max_result_date < end_date):
                    logger.info(f"Results don't cover full date range. Requested: {start_date} to {end_date}, Got: {min_result_date} to {max_result_date}")

                    # If we're automatically detecting consecutive empty days
                    if gap_threshold > 0:
                        logger.info(f"Checking for {gap_threshold} consecutive days without content")

                        # Check if there are consecutive days without content
                        next_content_date = self.gap_detector.detect_consecutive_gaps(
                            lccn,
                            start_date,
                            end_date,
                            threshold=gap_threshold
                        )

                        if next_content_date:
                            # Found a gap with content after it
                            logger.info(f"Found gap with content after it at {next_content_date}")
                            search_info['gaps'].append({
                                'type': 'consecutive_empty',
                                'threshold': gap_threshold,
                                'next_content': next_content_date.isoformat()
                            })
                        else:
                            # No more content in the requested range
                            logger.info("No more content found in requested range")
                            search_info['has_more_content'] = False

            # Add a link to Chronicling America for visual confirmation
            search_info['chronicling_america_url'] = generate_chronicling_america_url(
                lccn, start_date, end_date
            )

        # If max_pages is greater than 1 and we have a promising strategy, try to get more pages
        if max_pages > 1 and pagination_info.get('total_pages', 0) > 1:
            logger.info(f"Fetching more pages (max: {max_pages})...")

            # Find the best strategy to use for fetching more pages
            # Prioritize the Web UI date format strategy as it's the most accurate
            best_strategy = None
            best_strategy_name = None

            # First, look for Web UI date format strategy
            for strategy_name, params in strategies:
                if strategy_name == "Web UI date format" and "dateFilterType" in params and params["dateFilterType"] == "range":
                    best_strategy = params
                    best_strategy_name = strategy_name
                    logger.info(f"Using '{best_strategy_name}' strategy for pagination - this provides the most accurate results")
                    break

            # If Web UI strategy wasn't found, look for any other successful strategy
            if not best_strategy:
                for strategy_name, params in strategies:
                    if strategy_name.startswith("Year") and "year" in params:
                        best_strategy = params
                        best_strategy_name = strategy_name
                        logger.info(f"Using '{best_strategy_name}' strategy for pagination (fallback)")
                        break

            # If we found a good strategy, use it to fetch more pages
            if best_strategy:
                more_pages = []

                # Try additional pages
                for page_num in range(2, min(max_pages + 1, pagination_info.get('total_pages', 1) + 1)):
                    logger.info(f"Fetching page {page_num} using strategy '{best_strategy_name}'")

                    # Update page number in params
                    params_copy = deepcopy(best_strategy)
                    params_copy['page'] = page_num

                    try:
                        # Make the API request
                        more_response = self._make_request(self.API_URL, params_copy)
                        more_data = more_response.json()
                        more_items = more_data.get('items', [])

                        logger.info(f"Got {len(more_items)} items from page {page_num}")

                        # Process each item
                        page_results = []
                        for item in more_items:
                            if not isinstance(item, dict):
                                continue

                            # Process item as before...
                            # Extract data from API response
                            lccn = item.get('lccn', '')
                            date_str = item.get('date', '')
                            sequence = item.get('sequence', 1)

                            # Get URL from id field
                            url = item.get('id', '')
                            if not url.startswith('http'):
                                url = f"https://chroniclingamerica.loc.gov{url}"

                            # Get title
                            title = item.get('title', f"Page {sequence}")

                            # Construct URLs
                            jp2_url = f"{url.rstrip('/')}.jp2"
                            pdf_url = f"{url.rstrip('/')}.pdf"
                            ocr_url = f"{url.rstrip('/')}/ocr/"

                            # Create page data
                            page_data = {
                                'lccn': lccn,
                                'date': date_str,
                                'sequence': sequence,
                                'url': url,
                                'title': title,
                                'jp2_url': jp2_url,
                                'pdf_url': pdf_url,
                                'ocr_url': ocr_url
                            }

                            # Create PageMetadata object
                            page_obj = PageMetadata.from_json(page_data)
                            page_results.append(page_obj)

                        # Apply date filtering
                        if date_start_str or date_end_str:
                            filtered_results = []

                            start_date_obj = None
                            if date_start_str:
                                start_date_obj = datetime.strptime(date_start_str, "%Y-%m-%d").date() if isinstance(date_start_str, str) else date_start_str

                            end_date_obj = None
                            if date_end_str:
                                end_date_obj = datetime.strptime(date_end_str, "%Y-%m-%d").date() if isinstance(date_end_str, str) else date_end_str

                            for page_obj in page_results:
                                page_date = page_obj.issue_date

                                # Skip if outside date range
                                if start_date_obj and page_date < start_date_obj:
                                    continue
                                if end_date_obj and page_date > end_date_obj:
                                    continue

                                filtered_results.append(page_obj)

                            logger.info(f"Date filtering: {len(filtered_results)}/{len(page_results)} pages from page {page_num} are within the requested date range")
                            page_results = filtered_results

                        # Add to more_pages
                        more_pages.extend(page_results)

                    except Exception as e:
                        logger.warning(f"Error fetching page {page_num}: {e}")
                        break

                # Add all new pages
                for page_obj in more_pages:
                    # Add if not already in results
                    key = f"{page_obj.lccn}_{page_obj.issue_date}_{page_obj.sequence}"
                    if key not in unique_pages:
                        unique_pages[key] = page_obj
                        result_pages.append(page_obj)

                # Re-sort and re-count
                result_pages.sort(key=lambda p: (p.issue_date, p.sequence))
                logger.info(f"After fetching more pages: Found {len(result_pages)} unique pages total")

        # Add search_info to pagination_info for return
        pagination_info['search_info'] = search_info

        return result_pages, pagination_info
    
    def download_page_content(self, page_metadata: PageMetadata, 
                             formats: List[str] = ['pdf', 'jp2', 'ocr', 'json'],
                             save_files: bool = True) -> Dict[str, str]:
        """
        Download content for a specific newspaper page in specified formats.
        
        Args:
            page_metadata: PageMetadata object with URLs
            formats: List of formats to download ('pdf', 'jp2', 'ocr', 'json')
            save_files: Whether to save files to disk (True) or just return content
            
        Returns:
            Dictionary with format names as keys and local file paths as values
        """
        result = {}
        
        # Generate a base filename from metadata
        try:
            date_str = page_metadata.issue_date.strftime('%Y%m%d')
        except Exception:
            # If issue_date is not valid, use a placeholder
            date_str = "00000000"
            
        filename_base = f"{page_metadata.lccn}_{date_str}_seq{page_metadata.sequence}"
        
        # Build base URL for the newspaper page
        base_page_url = None
        if page_metadata.url:
            base_page_url = page_metadata.url
            if not base_page_url.endswith('/'):
                base_page_url += '/'
        
        # Download each requested format
        for fmt in formats:
            download_url = None
            output_path = None
            
            if fmt == 'pdf' and page_metadata.pdf_url:
                download_url = page_metadata.pdf_url
                output_path = os.path.join(self.pdf_directory, f"{filename_base}.pdf")
                
            elif fmt == 'jp2' and page_metadata.jp2_url:
                download_url = page_metadata.jp2_url
                output_path = os.path.join(self.jp2_directory, f"{filename_base}.jp2")
                
            elif fmt == 'ocr' and page_metadata.ocr_url:
                download_url = page_metadata.ocr_url
                output_path = os.path.join(self.ocr_directory, f"{filename_base}.txt")
                
            elif fmt == 'json' and base_page_url:
                # For JSON, we get the metadata endpoint
                download_url = f"{base_page_url}?fo=json"
                output_path = os.path.join(self.json_directory, f"{filename_base}.json")
            
            # If we have a URL and path, download the file
            if download_url and output_path:
                path = self._download_file(
                    download_url,
                    output_path,
                    save_file=save_files
                )
                if path:
                    result[fmt] = path
                    
        return result
    
    def _download_file(self, url: str, output_path: str, 
                      save_file: bool = True) -> Optional[str]:
        """
        Download a file from a URL and optionally save it to disk.
        
        Args:
            url: URL to download
            output_path: Path to save the file
            save_file: Whether to save the file to disk
            
        Returns:
            Path to the saved file if save_file=True, None otherwise
        """
        try:
            response = self._make_request(url, stream=True)
            
            if save_file:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Write the file
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Downloaded {url} to {output_path}")
                return output_path
            else:
                # Just return the content in memory
                return response.content
                
        except Exception as e:
            logger.error(f"Failed to download file from {url}: {e}")
            return None
    
    def batch_download_pages(self, 
                            page_metadata_list: List[PageMetadata],
                            formats: List[str] = ['pdf', 'jp2', 'ocr', 'json']) -> List[Dict[str, str]]:
        """
        Download multiple newspaper pages in a batch operation.
        
        Args:
            page_metadata_list: List of PageMetadata objects
            formats: List of formats to download for each page
            
        Returns:
            List of dictionaries with download results for each page
        """
        results = []
        
        for i, page_metadata in enumerate(page_metadata_list):
            logger.info(f"Downloading page {i+1}/{len(page_metadata_list)}: {page_metadata.lccn} - {page_metadata.issue_date}")
            
            # Download the page content
            download_result = self.download_page_content(page_metadata, formats)
            
            # Add metadata for reference
            download_result['metadata'] = {
                'lccn': page_metadata.lccn,
                'issue_date': page_metadata.issue_date.isoformat(),
                'sequence': page_metadata.sequence,
                'title': page_metadata.title
            }
            
            results.append(download_result)
        
        return results