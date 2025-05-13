#!/usr/bin/env python3
"""Test ChroniclingAmerica client directly"""

import sys
import os
import traceback

# Add src to path
sys.path.append(os.path.abspath('.'))

def test_chronicling_america_client():
    """Test creating and using the ChroniclingAmerica client"""
    print("Testing ChroniclingAmerica client...")
    
    try:
        # Import the client
        print("Importing client...")
        from api.chronicling_america_improved import ImprovedChroniclingAmericaClient
        
        # Create the client
        print("Creating client...")
        output_dir = os.path.join(os.getcwd(), "test_output")
        os.makedirs(output_dir, exist_ok=True)
        client = ImprovedChroniclingAmericaClient(output_directory=output_dir)
        
        # Test a simple search
        print("Testing search...")
        pages, pagination = client.search_pages(
            state="Washington",
            date_start="1892-01-01",
            date_end="1892-01-03",
            page=1,
            max_pages=1
        )
        
        print(f"Search results: {len(pages)} pages, {pagination}")
        
        # Print the first page details if available
        if pages:
            print("\nFirst page details:")
            print(f"Title: {pages[0].title}")
            print(f"Date: {pages[0].issue_date}")
            print(f"URL: {pages[0].page_url}")
        
        return True
        
    except Exception as e:
        print(f"Error testing ChroniclingAmerica client: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_chronicling_america_client()
    if success:
        print("\n✅ ChroniclingAmerica client test successful")
    else:
        print("\n❌ ChroniclingAmerica client test failed")