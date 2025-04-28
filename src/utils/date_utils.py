# File: date_utils.py

import re
from typing import Optional, List, Dict, Tuple
from datetime import datetime, date

def parse_date(date_string: str) -> Optional[date]:
    """
    Parse a date string in various formats.
    
    Args:
        date_string: Date string to parse
        
    Returns:
        datetime.date object or None if parsing fails
    """
    if not date_string:
        return None
    
    # List of formats to try
    formats = [
        '%Y-%m-%d',  # ISO format: 2023-01-31
        '%d/%m/%Y',  # UK format: 31/01/2023
        '%m/%d/%Y',  # US format: 01/31/2023
        '%Y/%m/%d',  # Alternative ISO: 2023/01/31
        '%d-%m-%Y',  # Alternative UK: 31-01-2023
        '%m-%d-%Y',  # Alternative US: 01-31-2023
        '%d.%m.%Y',  # European: 31.01.2023
        '%m.%d.%Y',  # Alternative US: 01.31.2023
        '%Y.%m.%d',  # Alternative ISO: 2023.01.31
        '%b %d, %Y',  # Month name: Jan 31, 2023
        '%d %b %Y',  # Alternative month name: 31 Jan 2023
        '%B %d, %Y',  # Full month name: January 31, 2023
        '%d %B %Y',  # Alternative full month name: 31 January 2023
        '%Y',         # Just year: 2023
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            return dt.date()
        except ValueError:
            continue
    
    # If no format matched, try to extract a year
    year_match = re.search(r'\b(\d{4})\b', date_string)
    if year_match:
        try:
            year = int(year_match.group(1))
            if 1000 <= year <= 3000:  # Reasonable year range
                return date(year, 1, 1)
        except ValueError:
            pass
    
    return None

def format_date(dt: date, format_string: str = '%Y-%m-%d') -> str:
    """
    Format a date object as a string.
    
    Args:
        dt: Date object to format
        format_string: Format string to use
        
    Returns:
        Formatted date string
    """
    if not dt:
        return ""
    
    return dt.strftime(format_string)

def extract_dates_from_text(text: str) -> List[Tuple[str, date]]:
    """
    Extract potential dates from text.
    
    Args:
        text: Text to extract dates from
        
    Returns:
        List of tuples with (matched_text, date_object)
    """
    results = []
    
    # Patterns to match various date formats
    patterns = [
        r'\b\d{4}-\d{1,2}-\d{1,2}\b',  # ISO: 2023-01-31
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # UK/US: 31/01/2023 or 01/31/2023
        r'\b\d{4}/\d{1,2}/\d{1,2}\b',  # Alt ISO: 2023/01/31
        r'\b\d{1,2}-\d{1,2}-\d{4}\b',  # Alt UK/US: 31-01-2023 or 01-31-2023
        r'\b\d{1,2}\.\d{1,2}\.\d{4}\b',  # European: 31.01.2023
        r'\b\d{4}\.\d{1,2}\.\d{1,2}\b',  # Alt ISO: 2023.01.31
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',  # Month name: January 31, 2023
        r'\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b',  # Alt month name: 31 January 2023
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            matched_text = match.group(0)
            date_obj = parse_date(matched_text)
            if date_obj:
                results.append((matched_text, date_obj))
    
    return results

def is_date_in_range(dt: date, start: Optional[date] = None, end: Optional[date] = None) -> bool:
    """
    Check if a date is within a given range.
    
    Args:
        dt: Date to check
        start: Start date (inclusive)
        end: End date (inclusive)
        
    Returns:
        True if date is in range, False otherwise
    """
    if not dt:
        return False
    
    if start and dt < start:
        return False
    
    if end and dt > end:
        return False
    
    return True

def parse_date_range(range_string: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Parse a date range string like "1800-1850" or "Jan 1900 - Dec 1950".
    
    Args:
        range_string: Date range string
        
    Returns:
        Tuple of (start_date, end_date)
    """
    if not range_string:
        return None, None
    
    # Try to split on common range separators
    for separator in [' - ', '-', ' to ', ' until ', ' through ']:
        if separator in range_string:
            parts = range_string.split(separator, 1)
            start_date = parse_date(parts[0].strip())
            end_date = parse_date(parts[1].strip())
            return start_date, end_date
    
    # If no separator found, try to parse as a single date
    single_date = parse_date(range_string)
    if single_date:
        return single_date, single_date
    
    return None, None

def get_current_date() -> date:
    """
    Get the current date.
    
    Returns:
        Current date
    """
    return date.today()