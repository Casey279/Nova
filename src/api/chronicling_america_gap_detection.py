"""
Gap Detection module for Chronicling America newspapers

This module provides functionality to detect gaps in newspaper availability
and analyze content coverage within date ranges. It can be used with the
ImprovedChroniclingAmericaClient to enhance search capabilities with smart
gap handling.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewspaperGapDetector:
    """
    Detects and analyzes gaps in newspaper content availability.
    Works with the ImprovedChroniclingAmericaClient for Chronicling America collections.
    """
    
    def __init__(self, 
                 content_checker_func: Callable[[str, date], bool],
                 knowledge_file: str = "newspaper_gaps.json"):
        """
        Initialize the gap detector.
        
        Args:
            content_checker_func: Function that checks if content exists for a given 
                                 LCCN and date. Should return True if content exists.
            knowledge_file: Path to the JSON file to store discovered gap information
        """
        self.check_date_has_content = content_checker_func
        self.knowledge_file = knowledge_file
        self.known_gaps = {}
        self.known_latest_dates = {}
        
        # Load existing gap knowledge if available
        self._load_knowledge()
    
    def _load_knowledge(self):
        """Load gap information from the knowledge file if it exists."""
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file, 'r') as f:
                    data = json.load(f)
                    
                # Convert string dates back to date objects
                gaps_data = data.get('gaps', {})
                latest_dates = data.get('latest_dates', {})
                
                # Process gaps
                for lccn, lccn_gaps in gaps_data.items():
                    self.known_gaps[lccn] = []
                    for gap in lccn_gaps:
                        try:
                            start = datetime.strptime(gap['start'], "%Y-%m-%d").date()
                            end = datetime.strptime(gap['end'], "%Y-%m-%d").date()
                            self.known_gaps[lccn].append({
                                'start': start,
                                'end': end,
                                'verified': gap.get('verified', False)
                            })
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Error parsing gap data for {lccn}: {e}")
                
                # Process latest dates
                for lccn, date_str in latest_dates.items():
                    try:
                        self.known_latest_dates[lccn] = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError as e:
                        logger.warning(f"Error parsing latest date for {lccn}: {e}")
                        
                logger.info(f"Loaded gap knowledge for {len(self.known_gaps)} newspapers")
                
            except Exception as e:
                logger.warning(f"Error loading gap knowledge: {e}")
                self.known_gaps = {}
                self.known_latest_dates = {}
    
    def _save_knowledge(self):
        """Save gap information to the knowledge file."""
        try:
            # Convert date objects to strings for JSON serialization
            gaps_data = {}
            for lccn, lccn_gaps in self.known_gaps.items():
                gaps_data[lccn] = []
                for gap in lccn_gaps:
                    gaps_data[lccn].append({
                        'start': gap['start'].isoformat(),
                        'end': gap['end'].isoformat(),
                        'verified': gap.get('verified', False)
                    })
            
            # Convert latest dates to strings
            latest_dates = {lccn: d.isoformat() for lccn, d in self.known_latest_dates.items()}
            
            # Combine data
            data = {
                'gaps': gaps_data,
                'latest_dates': latest_dates,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.knowledge_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Saved gap knowledge for {len(self.known_gaps)} newspapers")
            
        except Exception as e:
            logger.warning(f"Error saving gap knowledge: {e}")
    
    def update_latest_date(self, lccn: str, latest_date: date):
        """
        Update our knowledge of the latest issue date for a newspaper.
        
        Args:
            lccn: Library of Congress Control Number
            latest_date: The latest date content is available
        """
        current_latest = self.known_latest_dates.get(lccn)
        
        # Only update if the new date is more recent or we don't have one
        if not current_latest or latest_date > current_latest:
            self.known_latest_dates[lccn] = latest_date
            self._save_knowledge()
            logger.info(f"Updated latest issue date for {lccn} to {latest_date}")
        
    def verify_latest_date(self, lccn: str, supposed_latest_date: date) -> Optional[date]:
        """
        Verify if the supposed latest issue date actually has content,
        and find the actual latest date with content if needed.
        
        Args:
            lccn: Library of Congress Control Number
            supposed_latest_date: The date that's supposed to be the latest
            
        Returns:
            The actual latest date with content, or None if verification failed
        """
        # First check if we already know this
        if lccn in self.known_latest_dates:
            known_latest = self.known_latest_dates[lccn]
            # If our known date is later than or same as the supposed date, use it
            if known_latest >= supposed_latest_date:
                return known_latest
        
        # Check if the supposed latest date actually has content
        has_content = self.check_date_has_content(lccn, supposed_latest_date)
        
        if has_content:
            # Supposed date is correct
            self.update_latest_date(lccn, supposed_latest_date)
            return supposed_latest_date
        
        # Supposed date doesn't have content - search backward to find actual content
        logger.info(f"Supposed latest date {supposed_latest_date} has no content. Searching backward...")
        
        # Start by looking 1 day, 1 week, 1 month, 3 months, 6 months, 1 year back
        check_offsets = [1, 7, 30, 90, 180, 365]
        
        for offset in check_offsets:
            check_date = supposed_latest_date - timedelta(days=offset)
            has_content = self.check_date_has_content(lccn, check_date)
            
            if has_content:
                # Found content, now refine using binary search
                logger.info(f"Found content at {check_date}, refining...")
                actual_latest = self.binary_search_boundary(
                    lccn, 
                    check_date,  # Lower bound (has content)
                    supposed_latest_date,  # Upper bound (no content)
                    looking_for_content=False  # We're looking for the last date WITH content
                )
                
                # Update our knowledge
                self.update_latest_date(lccn, actual_latest)
                return actual_latest
        
        # Couldn't find content in any of our backward checks
        logger.warning(f"Could not verify latest date for {lccn}, no content found in backward checks")
        return None
        
    def binary_search_boundary(
        self, 
        lccn: str, 
        lower_bound: date, 
        upper_bound: date, 
        looking_for_content: bool
    ) -> date:
        """
        Use binary search to find the exact boundary between content and no content.
        
        Args:
            lccn: Library of Congress Control Number
            lower_bound: Lower date bound
            upper_bound: Upper date bound
            looking_for_content: If True, find first date WITH content; if False, find last date WITH content
            
        Returns:
            The boundary date
        """
        current_lower = lower_bound
        current_upper = upper_bound
        
        # Ensure lower bound has content and upper bound doesn't (or vice versa)
        lower_has_content = self.check_date_has_content(lccn, current_lower)
        upper_has_content = self.check_date_has_content(lccn, current_upper)
        
        if lower_has_content == upper_has_content:
            # Both bounds have the same content status, can't find boundary
            logger.warning(f"Cannot find boundary: both bounds have same content status ({lower_has_content})")
            return current_lower if lower_has_content else current_upper
            
        # Binary search
        while (current_upper - current_lower).days > 1:
            # Check the middle date
            mid_date = current_lower + timedelta(days=(current_upper - current_lower).days // 2)
            mid_has_content = self.check_date_has_content(lccn, mid_date)
            
            if looking_for_content:
                # Looking for first date WITH content
                if mid_has_content:
                    # This date has content, so the boundary is at or before this date
                    current_upper = mid_date
                else:
                    # No content, so the boundary is after this date
                    current_lower = mid_date
            else:
                # Looking for last date WITH content
                if mid_has_content:
                    # This date has content, so the boundary is at or after this date
                    current_lower = mid_date
                else:
                    # No content, so the boundary is before this date
                    current_upper = mid_date
        
        # At this point, lower and upper bounds are adjacent dates
        # Return the appropriate bound based on what we're looking for
        if looking_for_content:
            # Return the first date WITH content
            return current_upper if upper_has_content else current_lower
        else:
            # Return the last date WITH content
            return current_lower if lower_has_content else current_upper
    
    def detect_consecutive_gaps(
        self, 
        lccn: str, 
        start_date: date, 
        end_date: date, 
        threshold: int = 5
    ) -> Optional[date]:
        """
        Detect if there are consecutive days without content.
        If threshold days in a row have no content, start probing with expanding windows.
        
        Args:
            lccn: Library of Congress Control Number
            start_date: Start date to check
            end_date: End date to check
            threshold: Number of consecutive days without content to trigger probing
            
        Returns:
            The next date with content, or None if no more content is found
        """
        current_date = start_date
        empty_days = 0
        
        while current_date <= end_date:
            has_content = self.check_date_has_content(lccn, current_date)
            
            if has_content:
                empty_days = 0
            else:
                empty_days += 1
                
                if empty_days >= threshold:
                    # Reached threshold of consecutive empty days
                    logger.info(f"Found {threshold} consecutive days without content starting at {current_date - timedelta(days=threshold-1)}")
                    
                    # Probe with expanding windows
                    next_content = self.probe_future_content(lccn, current_date, end_date)
                    
                    if next_content:
                        logger.info(f"Found future content at {next_content}")
                        return next_content
                    else:
                        logger.info(f"No more content found after {current_date - timedelta(days=threshold)}")
                        return None
            
            current_date += timedelta(days=1)
        
        return None
    
    def probe_future_content(self, lccn: str, current_date: date, end_date: date) -> Optional[date]:
        """
        Probe future dates with expanding windows to find the next date with content.
        
        Args:
            lccn: Library of Congress Control Number
            current_date: Current date (without content)
            end_date: End date to limit search
            
        Returns:
            The next date with content, or None if no more content is found
        """
        # Probe offsets: 14 days (2 weeks), 30 days (1 month), 90 days (3 months),
        # 180 days (6 months), 365 days (1 year), 730 days (2 years)
        probe_offsets = [14, 30, 90, 180, 365, 730]
        
        for offset in probe_offsets:
            probe_date = current_date + timedelta(days=offset)
            
            # Don't probe beyond end date
            if probe_date > end_date:
                return None
                
            logger.info(f"Probing {offset} days ahead at {probe_date}")
            has_content = self.check_date_has_content(lccn, probe_date)
            
            if has_content:
                # Found content in the future
                # Use binary search to find the exact first date with content
                next_content_date = self.binary_search_boundary(
                    lccn,
                    current_date,  # Lower bound (no content)
                    probe_date,    # Upper bound (has content)
                    looking_for_content=True  # Find first date WITH content
                )
                
                return next_content_date
        
        # No content found in any of the probes
        return None
    
    def analyze_gaps(
        self, 
        lccn: str, 
        start_date: date, 
        end_date: date, 
        thoroughness: str = "normal"
    ) -> List[Dict[str, Any]]:
        """
        Analyze gaps in newspaper content for a date range.
        
        Args:
            lccn: Library of Congress Control Number
            start_date: Start date of the range to analyze
            end_date: End date of the range to analyze
            thoroughness: "thorough" (check every day), "normal" (check every week),
                         or "quick" (check every month)
            
        Returns:
            List of dictionaries with gap information (start, end, verified)
        """
        logger.info(f"Analyzing gaps for {lccn} from {start_date} to {end_date} with {thoroughness} thoroughness")
        
        # Determine sampling frequency based on thoroughness
        if thoroughness == "thorough":
            sampling_days = 1  # Check every day (slow but thorough)
        elif thoroughness == "normal":
            sampling_days = 7  # Check every week
        else:  # "quick"
            sampling_days = 30  # Check approximately every month
            
        # Initialize gap detection
        gaps = []
        current_gap = None
        
        # Sample dates in the range
        current_date = start_date
        while current_date <= end_date:
            has_content = self.check_date_has_content(lccn, current_date)
            
            if not has_content:
                # No content, start or continue a gap
                if current_gap is None:
                    current_gap = {
                        "start": current_date,
                        "end": current_date,
                        "verified": False
                    }
                else:
                    current_gap["end"] = current_date
            else:
                # Content found, end any current gap
                if current_gap is not None:
                    gaps.append(current_gap)
                    current_gap = None
            
            # Move to next sample date
            current_date += timedelta(days=sampling_days)
        
        # Add the final gap if there is one
        if current_gap:
            gaps.append(current_gap)
        
        # For gaps over a certain size, refine the boundaries
        if thoroughness != "thorough" and gaps:
            refined_gaps = []
            
            for gap in gaps:
                # Only refine gaps above a certain size
                gap_days = (gap["end"] - gap["start"]).days
                
                if gap_days > sampling_days * 2:
                    logger.info(f"Refining large gap: {gap['start']} to {gap['end']} ({gap_days} days)")
                    
                    # Find exact first day without content
                    start_boundary = self.binary_search_boundary(
                        lccn,
                        max(start_date, gap["start"] - timedelta(days=sampling_days)),  # Last known content
                        gap["start"],  # First known no-content
                        looking_for_content=False  # Find last date WITH content
                    )
                    
                    # Find exact last day without content
                    end_boundary = self.binary_search_boundary(
                        lccn,
                        gap["end"],  # Last known no-content
                        min(end_date, gap["end"] + timedelta(days=sampling_days)),  # First known content after gap
                        looking_for_content=True  # Find first date WITH content
                    )
                    
                    # Add the refined gap
                    refined_gaps.append({
                        "start": start_boundary + timedelta(days=1),  # First day with no content
                        "end": end_boundary - timedelta(days=1),     # Last day with no content
                        "verified": True
                    })
                else:
                    # Small gap, just use as-is
                    refined_gaps.append(gap)
            
            gaps = refined_gaps
        
        # Store the discovered gaps in our knowledge base
        if lccn not in self.known_gaps:
            self.known_gaps[lccn] = []
            
        # Merge with existing knowledge
        for gap in gaps:
            # Check if this gap overlaps with any known gaps
            overlaps = False
            for known_gap in self.known_gaps[lccn]:
                # Check for overlap
                if (gap["start"] <= known_gap["end"] and gap["end"] >= known_gap["start"]):
                    overlaps = True
                    # Expand the known gap if needed
                    known_gap["start"] = min(known_gap["start"], gap["start"])
                    known_gap["end"] = max(known_gap["end"], gap["end"])
                    known_gap["verified"] = known_gap["verified"] or gap["verified"]
                    break
                    
            if not overlaps:
                # New gap, add it
                self.known_gaps[lccn].append(gap)
        
        # Save updated knowledge
        self._save_knowledge()
        
        return gaps

# Utility functions
def format_gap_for_display(gap: Dict[str, Any]) -> str:
    """Format a gap dictionary for display to the user."""
    start = gap["start"].strftime("%b %d, %Y")
    end = gap["end"].strftime("%b %d, %Y")
    days = (gap["end"] - gap["start"]).days + 1
    
    if days == 1:
        return f"{start} (1 day)"
    else:
        return f"{start} to {end} ({days} days)"

def generate_chronicling_america_url(lccn: str, start_date: Optional[date] = None, end_date: Optional[date] = None) -> str:
    """Generate a URL to the Chronicling America website for a newspaper and date range."""
    base_url = "https://chroniclingamerica.loc.gov/search/pages/results/"
    
    params = [f"lccn={lccn}"]
    
    if start_date:
        params.append(f"date1={start_date.strftime('%m/%d/%Y')}")
    
    if end_date:
        params.append(f"date2={end_date.strftime('%m/%d/%Y')}")
    
    params.append("sort=date")  # Sort by date
    params.append("rows=100")   # Show 100 results per page
    
    return f"{base_url}?{'&'.join(params)}"