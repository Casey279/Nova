#!/usr/bin/env python3
"""
Test script for downloading specific Post-Intelligencer pages from ChroniclingAmerica
"""

import argparse
import json
import logging
import os
import requests
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for the Post-Intelligencer
LCCN = "sn83045604"  # Seattle Post-Intelligencer
DEFAULT_OUTPUT_DIR = "./pi_downloads"

# We'll use specific known dates from my search results
KNOWN_DATES = [
    ("1892-07-24", "1"),  # Example found in search
    ("1892-09-03", "1"),
    ("1892-09-09", "1"),
    ("1892-11-24", "1"),
    ("1892-12-18", "1"),
    ("1892-12-25", "1")
]

def download_file(url, output_path):
    """Download a file from a URL to a specified path"""
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # First try a HEAD request to see if the file exists
        head_response = requests.head(url, allow_redirects=True)
        if head_response.status_code != 200:
            logger.warning(f"URL returned status code {head_response.status_code}: {url}")
            return False
        
        # If HEAD succeeded, do the actual download
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded: {url} -> {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False

def download_page(lccn, date, edition, output_dir, content_types):
    """Download all requested content types for a newspaper page"""
    date_str = date.replace("-", "")
    results = {}
    
    # Create a directory for this page
    page_dir = os.path.join(output_dir, f"{lccn}_{date_str}_ed{edition}")
    os.makedirs(page_dir, exist_ok=True)
    
    # Try to download each requested content type
    for content_type in content_types:
        if content_type == "image_jpeg":
            url = f"https://chroniclingamerica.loc.gov/iiif/2/{lccn}/{date_str}/ed-{edition}/seq-1/full/full/0/default.jpg"
            output_path = os.path.join(page_dir, "image.jpg")
            results["image_jpeg"] = download_file(url, output_path)
        
        elif content_type == "pdf":
            url = f"https://chroniclingamerica.loc.gov/lccn/{lccn}/{date_str}/ed-{edition}/seq-1.pdf"
            output_path = os.path.join(page_dir, "page.pdf")
            results["pdf"] = download_file(url, output_path)
        
        elif content_type == "ocr_txt":
            url = f"https://chroniclingamerica.loc.gov/lccn/{lccn}/{date_str}/ed-{edition}/seq-1/ocr.txt"
            output_path = os.path.join(page_dir, "ocr.txt")
            results["ocr_txt"] = download_file(url, output_path)
        
        elif content_type == "ocr_xml":
            url = f"https://chroniclingamerica.loc.gov/lccn/{lccn}/{date_str}/ed-{edition}/seq-1/ocr.xml"
            output_path = os.path.join(page_dir, "ocr.xml")
            results["ocr_xml"] = download_file(url, output_path)
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Test downloading specific Post-Intelligencer pages")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory for downloaded files")
    parser.add_argument("--content-types", nargs="+", 
                       choices=["image_jpeg", "pdf", "ocr_txt", "ocr_xml"],
                       default=["image_jpeg", "ocr_txt"],
                       help="Content types to download")
    parser.add_argument("--workers", type=int, default=2, help="Number of concurrent download workers")
    
    args = parser.parse_args()
    
    logger.info(f"Starting download of known Seattle Post-Intelligencer pages from 1892")
    logger.info(f"Output directory: {args.output}")
    logger.info(f"Content types: {args.content_types}")
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    # Download pages
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for date, edition in KNOWN_DATES:
            future = executor.submit(download_page, LCCN, date, edition, args.output, args.content_types)
            futures.append((date, edition, future))
        
        for date, edition, future in futures:
            try:
                result = future.result()
                results.append({
                    "date": date,
                    "edition": edition,
                    "results": result
                })
            except Exception as e:
                logger.error(f"Error processing page {date}, edition {edition}: {str(e)}")
    
    # Count successes and failures
    total_requests = len(KNOWN_DATES) * len(args.content_types)
    success_count = sum(
        1 for result in results 
        for content_type, success in result["results"].items() 
        if success
    )
    
    logger.info("====== DOWNLOAD SUMMARY ======")
    logger.info(f"Total pages attempted: {len(KNOWN_DATES)}")
    logger.info(f"Total downloads attempted: {total_requests}")
    logger.info(f"Successful downloads: {success_count}")
    logger.info(f"Success rate: {success_count/total_requests*100:.1f}%")
    
    # Save results to JSON
    results_path = os.path.join(args.output, "download_results.json")
    with open(results_path, 'w') as f:
        json.dump({
            "lccn": LCCN,
            "content_types": args.content_types,
            "date": datetime.datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    logger.info(f"Results saved to {results_path}")

if __name__ == "__main__":
    main()