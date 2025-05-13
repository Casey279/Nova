#!/usr/bin/env python3
"""
Test script for parsing the Chronicling America HTML.
This helps debug the newspaper dropdown display issue.
"""

import os
import re
import sys

def parse_html(html_file):
    """Parse the HTML file to extract newspaper information."""
    print(f"Parsing HTML file: {html_file}")

    with open(html_file, 'r', encoding='utf-8') as f:
        html = f.read()

    # Extract table rows that contain newspaper information
    # Look for the specific pattern in the table structure
    newspaper_pattern = r'<tr>\s*<td[^>]*><a[^>]*>([^<]+)</a></td>\s*<td><a[^>]*><strong>([^<]+)</strong></a><br />([^<]+)</td>'
    newspaper_regex = re.compile(newspaper_pattern, re.DOTALL)
    matches = newspaper_regex.findall(html)

    if matches:
        print(f"Found {len(matches)} newspapers with the primary pattern")
        for i, match in enumerate(matches[:5]):
            print(f"  {i+1}. State: {match[0]}, Title: {match[1]}, Info: {match[2]}")
        return

    # If the primary pattern didn't work, try a more direct approach for the table rows
    row_pattern = r'<tr[^>]*>(.*?)</tr>'
    row_regex = re.compile(row_pattern, re.DOTALL)
    rows = row_regex.findall(html)

    newspapers = []
    for row_html in rows:
        # Check if this row has a title cell
        title_match = re.search(r'<td><a[^>]*><strong>([^<]+)</strong></a><br />([^<]+)</td>', row_html)
        if not title_match:
            continue

        # Extract LCCN from the href
        lccn_match = re.search(r'href="/lccn/([^/]+?)/"', row_html)
        lccn = lccn_match.group(1) if lccn_match else ""

        # Extract publication title and place/date information
        title = title_match.group(1)
        info = title_match.group(2)

        # Extract place (usually in format "City, State, Date-Date")
        place = ""
        if ',' in info:
            place_parts = info.split(',', 1)
            place = place_parts[0].strip()

        # Extract dates
        date_match = re.search(r'(\d{4})-(\d{4}|\d{2}\?\?)', info)
        date_range = ""
        if date_match:
            date_range = date_match.group(0)

        # Create display text in the requested format
        display_text = f"{title} ({lccn})"
        if place:
            display_text += f", {place}"
        if date_range:
            display_text += f", {date_range}"

        newspapers.append({
            'lccn': lccn,
            'title': title,
            'place': place,
            'date_range': date_range,
            'display_text': display_text
        })

    print(f"Found {len(newspapers)} newspapers with the alternative pattern")
    for i, newspaper in enumerate(newspapers[:5]):
        print(f"  {i+1}. {newspaper['display_text']}")

if __name__ == "__main__":
    # Check if HTML file exists
    html_file = os.path.join(os.getcwd(), "state_newspapers.html")
    if not os.path.exists(html_file):
        print(f"Error: HTML file not found at {html_file}")
        sys.exit(1)

    parse_html(html_file)