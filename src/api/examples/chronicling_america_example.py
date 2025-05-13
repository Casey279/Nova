"""
Example usage of the ChroniclingAmerica API client.

This script demonstrates how to use the ChroniclingAmerica API client
to search and download newspaper content.
"""

import os
import sys
import logging
from datetime import date

# Add the parent directory to the path to import the module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.chronicling_america import ChroniclingAmericaClient

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    """Demonstrate the usage of ChroniclingAmericaClient."""
    # Create a client with a temporary download directory
    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
    client = ChroniclingAmericaClient(output_directory=download_dir)
    
    # Example 1: Search for newspapers
    print("\n=== Example 1: Search for newspapers in Washington ===")
    newspapers = client.search_newspapers(state='Washington')
    print(f"Found {len(newspapers)} newspapers")
    for i, newspaper in enumerate(newspapers[:5]):  # Show first 5 results
        print(f"{i+1}. {newspaper.title} ({newspaper.start_year}-{newspaper.end_year or 'present'})")
        print(f"   LCCN: {newspaper.lccn}")
        print(f"   Publication place: {newspaper.place_of_publication}")
    
    # Example 2: Search for pages with a specific keyword
    print("\n=== Example 2: Search for pages containing 'gold rush' ===")
    pages, pagination = client.search_pages(
        keywords='gold rush',
        state='Washington',
        date_start='1898-01-01',
        date_end='1900-12-31'
    )
    print(f"Found {pagination['total_items']} pages across {pagination['total_pages']} result pages")
    for i, page in enumerate(pages[:3]):  # Show first 3 results
        print(f"{i+1}. {page.title} - {page.issue_date} (Page {page.sequence})")
        print(f"   URL: {page.url}")
    
    # Example 3: Download content for a specific page
    if pages:
        print("\n=== Example 3: Download content for the first page ===")
        page = pages[0]
        download_results = client.download_page_content(
            page, 
            formats=['pdf', 'ocr'],  # Download only PDF and OCR text
            save_files=True
        )
        print("Downloaded files:")
        for fmt, path in download_results.items():
            print(f"  {fmt}: {path}")
    
    # Example 4: Search and download in one operation (limited to 1 page of results)
    print("\n=== Example 4: Search and download in one operation ===")
    all_results = client.search_and_download(
        keywords='railway accident',
        state='Washington',
        date_start='1900-01-01',
        date_end='1900-12-31',
        max_pages=1,  # Only process the first page of results
        formats=['pdf', 'ocr']  # Download only PDF and OCR text
    )
    print(f"Downloaded {len(all_results)} pages")
    
    # Example 5: Integration with repository (simulation)
    print("\n=== Example 5: Repository integration simulation ===")
    # Create a simple mock repository manager
    class MockRepositoryManager:
        def add_newspaper_page(self, **kwargs):
            print(f"Adding page to repository: {kwargs['publication_name']} - {kwargs['publication_date']}")
            return f"page_{id(kwargs)}"
        
        def add_to_processing_queue(self, page_id, operation):
            print(f"Queuing page {page_id} for {operation} processing")
    
    mock_repo = MockRepositoryManager()
    page_ids = client.integrate_with_repository(all_results, mock_repo)
    print(f"Added {len(page_ids)} pages to the repository")

if __name__ == "__main__":
    main()