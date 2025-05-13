"""
Module that provides the earliest issue dates for newspapers in the Chronicling America database.

This data is extracted from the Chronicling America website and stored locally for faster access.
It allows the ImprovedChroniclingAmericaClient to quickly determine the earliest issue date for a 
newspaper without having to fetch it every time.
"""

import os
import json
import logging
from datetime import datetime, date
from typing import Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hardcoded dates for important newspapers, in case the data file is not available
# These dates are in the format "YYYY-MM-DD"
IMPORTANT_NEWSPAPERS = {
    "sn83045604": {  # Seattle Post-Intelligencer
        "title": "The Seattle post-intelligencer",
        "earliest_date": "May 11, 1888",
        "raw_date": "1888-05-11",
        "latest_date": "December 31, 1900",  # Available through 1900 on Chronicling America
        "raw_latest_date": "1900-12-31"
    },
    "sn83030213": {  # New York Tribune
        "title": "New-York daily tribune",
        "earliest_date": "April 22, 1842",
        "raw_date": "1842-04-22",
        "latest_date": "April 12, 1866",
        "raw_latest_date": "1866-04-12"
    },
    "sn83030214": {  # New York Times
        "title": "New-York tribune",
        "earliest_date": "April 10, 1866",
        "raw_date": "1866-04-10",
        "latest_date": "December 31, 1922",
        "raw_latest_date": "1922-12-31"
    },
    "sn84026749": {  # Washington Post
        "title": "The Washington times",
        "earliest_date": "December 01, 1902",
        "raw_date": "1902-12-01",
        "latest_date": "December 31, 1920",
        "raw_latest_date": "1920-12-31"
    }
}

def parse_date(date_str: str) -> Optional[date]:
    """
    Parse a date string to a date object.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        date object or None if unable to parse
    """
    if not date_str:
        return None
        
    # Try different formats
    formats = [
        "%Y-%m-%d",  # YYYY-MM-DD
        "%B %d, %Y"  # Month Day, Year
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
            
    logger.warning(f"Could not parse date: {date_str}")
    return None

class NewspaperDateProvider:
    """
    Provider for issue dates (earliest and latest) of newspapers in the Chronicling America database.
    """

    def __init__(self, data_file: str = "newspaper_dates.json"):
        """
        Initialize the provider.

        Args:
            data_file: Path to the JSON file containing newspaper dates data
        """
        self.data_file = data_file
        self.newspaper_dates = {}

        # Load data from the file
        self._load_data()

    def _load_data(self):
        """Load newspaper dates data from the JSON file or use hardcoded data."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.newspaper_dates = json.load(f)
                logger.info(f"Loaded {len(self.newspaper_dates)} newspaper date entries from {self.data_file}")
            except Exception as e:
                logger.warning(f"Error loading newspaper dates from file: {e}")
                self.newspaper_dates = IMPORTANT_NEWSPAPERS
        else:
            logger.info(f"Newspaper dates file {self.data_file} not found, using hardcoded data")
            self.newspaper_dates = IMPORTANT_NEWSPAPERS

    def get_earliest_date(self, lccn: str) -> Optional[date]:
        """
        Get the earliest issue date for a newspaper.

        Args:
            lccn: Library of Congress Control Number

        Returns:
            date object of the earliest issue or None if not found
        """
        if lccn in self.newspaper_dates:
            # First try the raw date, which is in YYYY-MM-DD format
            raw_date = self.newspaper_dates[lccn].get("raw_date")
            if raw_date:
                parsed_date = parse_date(raw_date)
                if parsed_date:
                    return parsed_date

            # If raw date parsing failed, try the formatted date
            formatted_date = self.newspaper_dates[lccn].get("earliest_date")
            if formatted_date:
                return parse_date(formatted_date)

        # Check hardcoded data if not found in the loaded data
        if lccn in IMPORTANT_NEWSPAPERS and lccn not in self.newspaper_dates:
            raw_date = IMPORTANT_NEWSPAPERS[lccn].get("raw_date")
            if raw_date:
                parsed_date = parse_date(raw_date)
                if parsed_date:
                    return parsed_date

            formatted_date = IMPORTANT_NEWSPAPERS[lccn].get("earliest_date")
            if formatted_date:
                return parse_date(formatted_date)

        return None

    def get_latest_date(self, lccn: str) -> Optional[date]:
        """
        Get the latest issue date for a newspaper.

        Args:
            lccn: Library of Congress Control Number

        Returns:
            date object of the latest issue or None if not found
        """
        if lccn in self.newspaper_dates:
            # First try the raw latest date, which is in YYYY-MM-DD format
            raw_date = self.newspaper_dates[lccn].get("raw_latest_date")
            if raw_date:
                parsed_date = parse_date(raw_date)
                if parsed_date:
                    return parsed_date

            # If raw date parsing failed, try the formatted date
            formatted_date = self.newspaper_dates[lccn].get("latest_date")
            if formatted_date:
                return parse_date(formatted_date)

        # Check hardcoded data if not found in the loaded data
        if lccn in IMPORTANT_NEWSPAPERS and lccn not in self.newspaper_dates:
            raw_date = IMPORTANT_NEWSPAPERS[lccn].get("raw_latest_date")
            if raw_date:
                parsed_date = parse_date(raw_date)
                if parsed_date:
                    return parsed_date

            formatted_date = IMPORTANT_NEWSPAPERS[lccn].get("latest_date")
            if formatted_date:
                return parse_date(formatted_date)

        return None

    def get_newspaper_title(self, lccn: str) -> Optional[str]:
        """
        Get the title of a newspaper.

        Args:
            lccn: Library of Congress Control Number

        Returns:
            Newspaper title or None if not found
        """
        if lccn in self.newspaper_dates:
            return self.newspaper_dates[lccn].get("title")

        if lccn in IMPORTANT_NEWSPAPERS:
            return IMPORTANT_NEWSPAPERS[lccn].get("title")

        return None

# Create a singleton instance
newspaper_date_provider = NewspaperDateProvider()

# Function to get earliest date
def get_earliest_date(lccn: str) -> Optional[date]:
    """
    Get the earliest issue date for a newspaper.

    Args:
        lccn: Library of Congress Control Number

    Returns:
        date object of the earliest issue or None if not found
    """
    return newspaper_date_provider.get_earliest_date(lccn)

# Function to get latest date
def get_latest_date(lccn: str) -> Optional[date]:
    """
    Get the latest issue date for a newspaper.

    Args:
        lccn: Library of Congress Control Number

    Returns:
        date object of the latest issue or None if not found
    """
    return newspaper_date_provider.get_latest_date(lccn)

# Function to get newspaper title
def get_newspaper_title(lccn: str) -> Optional[str]:
    """
    Get the title of a newspaper.

    Args:
        lccn: Library of Congress Control Number

    Returns:
        Newspaper title or None if not found
    """
    return newspaper_date_provider.get_newspaper_title(lccn)