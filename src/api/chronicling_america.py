"""
ChroniclingAmerica API Client

This module provides a client for interacting with the Library of Congress
Chronicling America API to search and download historical newspaper content.

The client supports:
- Searching for newspaper content by date, publication, location, and keywords
- Downloading newspaper pages in various formats (JP2, PDF, etc.)
- Extracting metadata from API responses
- Batch operations for downloading multiple pages
- Integration with the newspaper repository system
- Error handling and rate limiting
"""

import os
import time
import json
import re
import requests
from typing import Dict, List, Optional, Union, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, date
import logging

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
            language=json_data.get('language', [])
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
            # The API sometimes returns dates in YYYYMMDD format without dashes
            if issue_date_str and len(issue_date_str) == 8 and issue_date_str.isdigit():
                # Format YYYYMMDD to YYYY-MM-DD for consistent handling
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


class ChroniclingAmericaClient:
    """
    Client for interacting with the Library of Congress Chronicling America API.
    
    This client provides methods to search and download historical newspaper content
    from the Chronicling America database.
    """
    
    # Chronicling America API endpoints
    BASE_URL = "https://chroniclingamerica.loc.gov"
    API_URL = f"{BASE_URL}/search/pages/results/"  # The pages search API

    # Alternative API URL for the LoC.gov-based approach
    LOC_BASE_URL = "https://www.loc.gov/collections/chronicling-america"
    LOC_API_URL = f"{LOC_BASE_URL}/search/"

    # For newspapers, we query the main API with a filter for newspaper titles
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
        Initialize the ChroniclingAmerica API client.
        
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
                if not stream and 'application/json' in response.headers.get('Content-Type', ''):
                    try:
                        data = response.json()
                        logger.info(f"API Response: status_code={response.status_code}, content_length={len(response.content)}, items={len(data.get('results', data.get('content', {}).get('results', [])))}")
                    except Exception as e:
                        logger.warning(f"Could not parse JSON response: {e}")

                return response
            
            except requests.RequestException as e:
                last_error = e
                retries += 1
                
                if retries <= self.MAX_RETRIES:
                    # Calculate backoff time
                    backoff_time = self.REQUEST_DELAY * (self.BACKOFF_FACTOR ** (retries - 1))
                    logger.warning(f"Request failed (attempt {retries}/{self.MAX_RETRIES}): {e}")
                    logger.warning(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
                else:
                    # All retries failed
                    logger.error(f"API request failed after {self.MAX_RETRIES} retries: {e}")
                    raise
    
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
        # Build query parameters for the new LoC.gov API
        params = {}
        
        # Parameter mapping for the new API
        if state:
            params['state'] = state
        if county:
            params['county'] = county
        if title:
            params['title'] = title
        if year:
            params['year'] = str(year)
            
        # Additional required parameters for the new API
        params['fo'] = 'json'        # Request JSON format
        params['c'] = 100            # Results per page (max allowed)
        
        try:
            response = self._make_request(self.NEWSPAPERS_URL, params)
            data = response.json()
            
            # Extract newspapers from the new API response structure
            newspapers = []
            
            # The LoC.gov API may return different structures
            # Try different possible response formats
            items = data.get('results', [])
            if not items and 'content' in data:
                items = data.get('content', {}).get('results', [])
            
            # Process each item
            for item in items:
                try:
                    # Extract LCCN from the URL, ID, or related links
                    lccn = ""
                    
                    # Check in multiple places
                    url_str = item.get('id', '') or item.get('url', '')
                    
                    # Try direct pattern match
                    lccn_match = re.search(r'lccn/([^/]+)', url_str)
                    if lccn_match:
                        lccn = lccn_match.group(1)
                        
                    # If not found, check in related links
                    if not lccn and 'links' in item:
                        for link in item.get('links', []):
                            if isinstance(link, dict) and 'url' in link:
                                link_url = link.get('url', '')
                                lccn_match = re.search(r'lccn/([^/]+)', link_url)
                                if lccn_match:
                                    lccn = lccn_match.group(1)
                                    break
                                    
                    # If still not found, try to extract from item ID
                    if not lccn and '/' in url_str:
                        # Sometimes the item ID has an embedded LCCN-like value
                        parts = url_str.split('/')
                        for part in parts:
                            # Look for patterns like 'sn123456', 'sn45678', etc.
                            if re.match(r'^sn\d{5,}$', part):
                                lccn = part
                                break
                    
                    # Extract date range
                    date_str = item.get('date', '')
                    start_year = 0
                    end_year = None
                    
                    # Try to parse date range in various formats
                    if date_str:
                        # Format 1: "1879-1925"
                        date_match = re.search(r'(\d{4})(?:-(\d{4}))?', date_str)
                        if date_match:
                            start_year = int(date_match.group(1))
                            end_year = int(date_match.group(2)) if date_match.group(2) else None
                    
                    # Map the new API structure to our metadata format
                    newspaper_data = {
                        'lccn': lccn,
                        'title': item.get('title', ''),
                        'place_of_publication': item.get('location', ''),
                        'start_year': start_year,
                        'end_year': end_year,
                        'url': item.get('url', ''),
                        'publisher': item.get('publisher', None),
                        'language': item.get('language', [])
                    }
                    
                    newspapers.append(NewspaperMetadata.from_json(newspaper_data))
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
                    items_per_page: int = 20) -> Tuple[List[PageMetadata], Dict[str, Any]]:
        """
        Search for newspaper pages matching the given criteria.
        
        Args:
            keywords: Search terms
            lccn: Library of Congress Control Number for specific newspaper
            state: Filter by state (e.g., 'California', 'New York')
            date_start: Start date for search range (YYYY-MM-DD or date object)
            date_end: End date for search range (YYYY-MM-DD or date object)
            page: Page number for pagination (default: 1)
            items_per_page: Number of results per page (default: 20)
            
        Returns:
            Tuple containing:
                - List of PageMetadata objects
                - Dict with pagination info (total_items, pages, etc.)
        """
        # Convert date objects to strings if needed
        if isinstance(date_start, date):
            date_start = date_start.strftime("%Y-%m-%d")
        if isinstance(date_end, date):
            date_end = date_end.strftime("%Y-%m-%d")
        
        # Log input parameters for debugging
        logger.info(f"Search parameters: keywords={keywords}, lccn={lccn}, state={state}, date_start={date_start}, date_end={date_end}, page={page}")

        # Build query parameters for the native Chronicling America API
        params = {
            'format': 'json',  # Return JSON format
            'page': page,
            'rows': items_per_page  # Number of results per page
        }

        # Add search parameters
        if keywords:
            params['andtext'] = keywords  # Chronicling America uses 'andtext' for keyword search
            logger.info(f"Using keyword filter: {keywords}")
        if lccn:
            # Ensure LCCN is properly formatted
            lccn = lccn.strip()
            if lccn:
                params['lccn'] = lccn  # LCCN parameter
                logger.info(f"Using LCCN filter: {lccn}")
        if state:
            # IMPORTANT: Based on testing, the 'state' parameter isn't working correctly with the API
            # Just log that we're skipping it for now
            logger.warning(f"State parameter '{state}' was provided but is being skipped - API returns no results when state is included")
            # Don't add state to the params dictionary to avoid filtering out all results
        # Format dates correctly for the API
        if date_start:
            # Ensure date is formatted as YYYY-MM-DD
            if isinstance(date_start, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', date_start):
                # Based on testing, we need to use both date formatting options:
                # 1. YYYYMMDD format (without dashes) for the date1 parameter
                # 2. Add the searchType=advanced parameter for more accurate filtering
                date_obj = datetime.strptime(date_start, "%Y-%m-%d")
                params['date1'] = date_obj.strftime("%Y%m%d")
                logger.info(f"Using date start filter: {date_start} (API format: {params['date1']})")

                # Also add the year parameter for additional filtering accuracy
                params['year'] = date_obj.strftime("%Y")
                logger.info(f"Added year filter: {params['year']}")

                # Add searchType=advanced to ensure the API uses the date filter correctly
                params['searchType'] = 'advanced'
                logger.info("Added searchType=advanced parameter for more accurate date filtering")

                # Based on testing, dateFilterType=range helps narrow down results
                params['dateFilterType'] = 'range'
                logger.info("Added dateFilterType=range parameter")
            else:
                logger.warning(f"Invalid date_start format: {date_start}. Should be YYYY-MM-DD.")

        if date_end:
            # Ensure date is formatted as YYYY-MM-DD
            if isinstance(date_end, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', date_end):
                # Convert YYYY-MM-DD to format expected by the API (YYYYMMDD)
                date_obj = datetime.strptime(date_end, "%Y-%m-%d")
                params['date2'] = date_obj.strftime("%Y%m%d")
                logger.info(f"Using date end filter: {date_end} (API format: {params['date2']})")
            else:
                logger.warning(f"Invalid date_end format: {date_end}. Should be YYYY-MM-DD.")
        
        try:
            response = self._make_request(self.API_URL, params)
            data = response.json()
            
            # Extract pages from the Chronicling America API response
            pages = []

            # The API returns data in a specific structure
            items = data.get('items', [])

            # Debug log total items
            logger.info(f"API returned {len(items)} items")
                
            for item in items:
                try:
                    # Parse the item according to the Chronicling America API format

                    # Get LCCN from item directly - it's a top-level field
                    lccn = item.get('lccn', '')

                    # Get date - parse from the date string or edition
                    date_str = ""
                    try:
                        # The API returns a date field in the format YYYY-MM-DD
                        date_str = item.get('date', '')
                        if not date_str and 'edition' in item:
                            # Sometimes it's in the edition field
                            ed_date = item.get('edition', {}).get('date', '')
                            if ed_date:
                                date_str = ed_date
                    except Exception as e:
                        logger.debug(f"Error extracting date: {e}")
                        date_str = ""

                    # Extract sequence number - this is the page number
                    sequence = 1
                    try:
                        sequence_str = item.get('sequence', 1)
                        if isinstance(sequence_str, str) and sequence_str.isdigit():
                            sequence = int(sequence_str)
                        elif isinstance(sequence_str, int):
                            sequence = sequence_str
                    except Exception as e:
                        logger.debug(f"Error extracting sequence: {e}")
                        sequence = 1

                    # Extract title - combine publication and edition info
                    title = ""
                    try:
                        # Get title from the publication title
                        title = item.get('title', {}).get('name', '')

                        # Add edition info if available
                        if not title:
                            title = f"Page {sequence}"
                        elif 'edition' in item and 'label' in item['edition']:
                            title = f"{title}, {item['edition']['label']}"
                    except Exception as e:
                        logger.debug(f"Error extracting title: {e}")
                        title = f"Page {sequence}"
                    
                    # Extract URLs for different formats
                    url = item.get('id', '')  # The main page URL

                    # URLs for different formats - Chronicling America API provides them directly
                    pdf_url = item.get('pdf', '')
                    jp2_url = item.get('jp2', '')
                    ocr_url = item.get('ocr', '')

                    # If URLs aren't directly provided, try to construct them
                    if not pdf_url and url:
                        pdf_url = f"{url}.pdf"
                    if not jp2_url and url:
                        jp2_url = f"{url}.jp2"
                    if not ocr_url and url:
                        ocr_url = f"{url}/ocr/"

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

                    # Post-processing validation to ensure results match search criteria
                    is_valid = True

                    # If LCCN was specified, validate the result matches
                    if params.get('lccn') and lccn and params.get('lccn') != lccn:
                        logger.warning(f"Skipping result with LCCN '{lccn}' that doesn't match search LCCN '{params.get('lccn')}'")
                        is_valid = False

                    # If state was specified, try to verify
                    # (This is trickier because state might be in the title or metadata)

                    # If date range was specified, verify the result date is within range
                    # Using the date1/date2 params that we actually sent to the API
                    if params.get('date1') and date_str:
                        try:
                            # Parse date from API result (format YYYY-MM-DD)
                            result_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                            # Convert date1 param from YYYYMMDD to datetime object
                            date1_str = params.get('date1')
                            start_date = datetime.strptime(date1_str, "%Y%m%d").date()

                            if result_date < start_date:
                                logger.warning(f"Post-filtering: Skipping result with date '{date_str}' before search start date '{date1_str}'")
                                is_valid = False
                        except ValueError as e:
                            # If date parsing fails, keep the result but log a warning
                            logger.warning(f"Could not validate date range for item with date '{date_str}': {e}")

                    if params.get('date2') and date_str:
                        try:
                            # Parse date from API result (format YYYY-MM-DD)
                            result_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                            # Convert date2 param from YYYYMMDD to datetime object
                            date2_str = params.get('date2')
                            end_date = datetime.strptime(date2_str, "%Y%m%d").date()

                            if result_date > end_date:
                                logger.warning(f"Post-filtering: Skipping result with date '{date_str}' after search end date '{date2_str}'")
                                is_valid = False
                        except ValueError as e:
                            # If date parsing fails, keep the result but log a warning
                            logger.warning(f"Could not validate date range for item with date '{date_str}': {e}")

                    # Add to results only if valid
                    if is_valid:
                        pages.append(PageMetadata.from_json(page_data))
                    else:
                        logger.info(f"Filtered out result: {page_data['title']} ({date_str})")
                except Exception as e:
                    logger.warning(f"Failed to parse page data: {e}")
                    continue
            
            # Post-processing filter for date range
            # Apply manual date filtering to ensure results match the requested date range
            if date_start or date_end:
                filtered_pages = []

                if date_start:
                    start_date_obj = datetime.strptime(date_start, "%Y-%m-%d").date() if isinstance(date_start, str) else date_start
                else:
                    start_date_obj = None

                if date_end:
                    end_date_obj = datetime.strptime(date_end, "%Y-%m-%d").date() if isinstance(date_end, str) else date_end
                else:
                    end_date_obj = None

                for page in pages:
                    page_date = page.issue_date
                    if start_date_obj and page_date < start_date_obj:
                        logger.info(f"Post-filtering: Removing page from {page_date} before requested start date {start_date_obj}")
                        continue
                    if end_date_obj and page_date > end_date_obj:
                        logger.info(f"Post-filtering: Removing page from {page_date} after requested end date {end_date_obj}")
                        continue
                    filtered_pages.append(page)

                logger.info(f"Post-filtering: {len(filtered_pages)}/{len(pages)} pages are within the requested date range")
                pages = filtered_pages

            # Extract pagination information from the Chronicling America API response
            # The API returns pagination info in a specific structure
            total_items = data.get('totalItems', 0)
            total_pages = (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 0

            # Debug log pagination info
            logger.info(f"Pagination: page {page} of {total_pages}, total items: {total_items}")

            pagination = {
                'total_items': total_items,
                'total_pages': total_pages,
                'current_page': page
            }

            logger.info(f"Found {len(pages)} pages (page {page}/{pagination['total_pages']})")
            return pages, pagination
            
        except requests.RequestException as e:
            logger.error(f"Failed to search pages: {e}")
            return [], {'total_items': 0, 'total_pages': 0, 'current_page': page}
    
    def _get_image_url(self, item: Dict[str, Any], format_type: str) -> Optional[str]:
        """
        Extract image URLs of various formats from the LoC.gov API response item.
        
        Args:
            item: Result item from the API response
            format_type: Type of image URL to extract ('jp2', 'pdf', 'ocr')
            
        Returns:
            URL string or None if not found
        """
        # First check if the format is directly available in the resources
        resources = item.get('resources', [])
        for resource in resources:
            if resource.get('type', '').lower() == format_type.lower():
                return resource.get('url')
        
        # If not found in resources, try constructing from the item ID
        item_id = item.get('id', '')
        if not item_id:
            return None
            
        # Clean up ID to ensure it has the right format
        # Should look like: https://www.loc.gov/collections/chronicling-america/lccn/sn84026749/1899-01-01/ed-1/seq-1/
        if not item_id.endswith('/'):
            item_id += '/'
            
        # Generate URLs based on format type and pattern
        base_url = item_id
        
        if format_type == 'jp2':
            # Modern IIIF image API pattern for LoC.gov
            iiif_url = f"{base_url.rstrip('/')}/full/pct:100/0/default.jpg"
            return iiif_url
            
        elif format_type == 'pdf':
            # PDF URL pattern for LoC.gov
            return f"{base_url}newspaper.pdf"
            
        elif format_type == 'ocr':
            # OCR text URL pattern for LoC.gov
            return f"{base_url}ocr/"
            
        # If format not recognized
        return None
    
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
        
        # Build base URL for the newspaper page from LoC.gov pattern
        # The new base URL pattern for newspaper pages
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
    
    def search_and_download(self, 
                           keywords: Optional[str] = None,
                           lccn: Optional[str] = None,
                           state: Optional[str] = None,
                           date_start: Optional[Union[str, date]] = None,
                           date_end: Optional[Union[str, date]] = None,
                           max_pages: int = 1,
                           formats: List[str] = ['pdf', 'jp2', 'ocr', 'json']) -> List[Dict[str, str]]:
        """
        Search for newspaper pages and download the results.
        
        Args:
            keywords: Search terms
            lccn: Library of Congress Control Number for specific newspaper
            state: Filter by state
            date_start: Start date for search range
            date_end: End date for search range
            max_pages: Maximum number of search result pages to process
            formats: List of formats to download for each page
            
        Returns:
            List of dictionaries with download results
        """
        all_results = []
        
        for page_num in range(1, max_pages + 1):
            # Search for pages
            pages, pagination = self.search_pages(
                keywords=keywords,
                lccn=lccn,
                state=state,
                date_start=date_start,
                date_end=date_end,
                page=page_num
            )
            
            if not pages:
                break
                
            # Download the pages
            download_results = self.batch_download_pages(pages, formats)
            all_results.extend(download_results)
            
            # Check if we've reached the last page
            if page_num >= pagination['total_pages']:
                break
        
        return all_results
    
    def integrate_with_repository(self, download_results: List[Dict[str, str]], 
                                 repository_manager) -> List[str]:
        """
        Integrate downloaded pages with the newspaper repository system.
        
        Args:
            download_results: Results from batch_download_pages or search_and_download
            repository_manager: Instance of RepositoryDatabaseManager to use for integration
            
        Returns:
            List of IDs for the added pages in the repository
        """
        added_page_ids = []
        
        for result in download_results:
            metadata = result.get('metadata', {})
            
            # Extract paths to downloaded files
            jp2_path = result.get('jp2')
            pdf_path = result.get('pdf')
            ocr_path = result.get('ocr')
            json_path = result.get('json')
            
            # Skip if we don't have either JP2 or PDF
            if not (jp2_path or pdf_path):
                logger.warning(f"Skipping repository integration for {metadata.get('lccn')} - {metadata.get('issue_date')} as no image files available")
                continue
            
            # Extract additional metadata from JSON if available
            additional_metadata = {}
            if json_path:
                try:
                    with open(json_path, 'r') as f:
                        json_data = json.load(f)
                        
                        # Extract relevant fields from the new LoC.gov API JSON structure
                        # This is different from the old API format
                        additional_metadata = {
                            'newspaper_title': json_data.get('title', ''),
                            'issue_date': json_data.get('date', ''),
                            'publisher': json_data.get('publisher', []),
                            'place_of_publication': json_data.get('location', ''),
                            'state': self._extract_state_from_location(json_data.get('location', ''))
                        }
                        
                        # If newspaper_title is a complex object, try to extract the name
                        if isinstance(additional_metadata['newspaper_title'], dict):
                            additional_metadata['newspaper_title'] = additional_metadata['newspaper_title'].get('name', '')
                            
                        # If publisher is a list, try to join it
                        if isinstance(additional_metadata['publisher'], list):
                            additional_metadata['publisher'] = ', '.join(additional_metadata['publisher'])
                            
                except Exception as e:
                    logger.error(f"Error parsing JSON metadata: {e}")
                    logger.debug(f"JSON path: {json_path}")
            
            # Extract required values for ChroniclingAmerica pages
            lccn = metadata.get('lccn', '')
            publication_name = metadata.get('title', additional_metadata.get('newspaper_title', ''))
            publication_date = metadata.get('issue_date', additional_metadata.get('issue_date', ''))
            page_number = metadata.get('sequence', 0)
            
            # Build combined JSON metadata
            json_metadata = {
                'publisher': additional_metadata.get('publisher', ''),
                'place_of_publication': additional_metadata.get('place_of_publication', ''),
                'state': additional_metadata.get('state', ''),
                'json_path': json_path,
                'download_date': datetime.now().isoformat(),
                'api_version': 'loc.gov'  # Mark this as using the new API
            }
            
            # Log the metadata for debugging
            logger.debug(f"Metadata for {lccn} - {publication_date}: {json_metadata}")
            
            # Use the specific ChroniclingAmerica method if available
            try:
                # Check if the method exists
                if hasattr(repository_manager, 'add_chronicling_america_page'):
                    # Use the specific method for ChroniclingAmerica pages
                    page_id = repository_manager.add_chronicling_america_page(
                        lccn=lccn,
                        publication_name=publication_name,
                        publication_date=publication_date,
                        page_number=page_number,
                        image_path=jp2_path or pdf_path,
                        ocr_path=ocr_path,
                        json_metadata=json_metadata,
                        download_status="complete"
                    )
                else:
                    # Fall back to the generic method
                    # Format the filename more carefully
                    safe_date = publication_date.replace('-', '')
                    if not safe_date or not safe_date.isdigit():
                        safe_date = "00000000"
                    
                    # Make sure page_number is an integer
                    try:
                        page_num = int(page_number)
                    except (ValueError, TypeError):
                        page_num = 1
                        
                    page_id = repository_manager.add_newspaper_page(
                        source_name=publication_name,
                        publication_date=publication_date,
                        page_number=page_num,
                        filename=f"{lccn}_{safe_date}_{page_num}",
                        image_path=jp2_path or pdf_path,
                        origin="chroniclingamerica",
                        metadata={
                            'lccn': lccn,
                            'publisher': additional_metadata.get('publisher', ''),
                            'place_of_publication': additional_metadata.get('place_of_publication', ''),
                            'state': additional_metadata.get('state', ''),
                            'download_date': datetime.now().isoformat(),
                            'download_status': 'complete',
                            'json_path': json_path,
                            'api_version': 'loc.gov'  # Mark this as using the new API
                        }
                    )
                
                if page_id:
                    added_page_ids.append(page_id)
                    logger.info(f"Added page to repository: {page_id}")
                    
                    # Queue for OCR processing if OCR text wasn't downloaded
                    if not ocr_path and hasattr(repository_manager, 'add_to_queue'):
                        repository_manager.add_to_queue(jp2_path or pdf_path, priority=2)
                        logger.info(f"Queued page image for OCR processing")
                        
            except Exception as e:
                logger.error(f"Failed to add page to repository: {e}")
                logger.error(f"Error details: {str(e)}")
        
        # Update batch statistics if available
        if len(added_page_ids) > 0 and hasattr(repository_manager, 'get_chronicling_america_stats'):
            try:
                stats = repository_manager.get_chronicling_america_stats()
                logger.info(f"Repository now contains {stats['total_pages']} ChroniclingAmerica pages")
            except Exception as e:
                logger.error(f"Error getting repository stats: {e}")
        
        return added_page_ids
        
    def _extract_state_from_location(self, location: str) -> str:
        """
        Extract state information from a location string.
        
        Args:
            location: Location string (e.g., "New York, NY")
            
        Returns:
            State abbreviation or empty string if not found
        """
        if not location:
            return ""
            
        # Common state abbreviations and their full names
        state_mapping = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
        }
        
        # First try to find a state abbreviation at the end of the string
        # Pattern: "City, ST" or "City, ST."
        match = re.search(r',\s+([A-Z]{2})\.?$', location)
        if match:
            state_abbr = match.group(1)
            return state_abbr
        
        # Next, look for full state names in the string
        for abbr, full_name in state_mapping.items():
            if full_name in location:
                return abbr
        
        # If all else fails, return empty string
        return ""