#!/usr/bin/env python3
import os
import sys
import argparse
import logging
from pathlib import Path

from repository_database import RepositoryDatabaseManager
from file_manager import FileManager
from ocr_processor import OCRProcessor
from main_db_connector import MainDBConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('integration_test')

def setup_test_environment():
    """Create temporary test directories and database"""
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    (test_dir / "sample_newspapers").mkdir(exist_ok=True)
    (test_dir / "repository").mkdir(exist_ok=True)
    
    # Return path to test directory
    return test_dir

def test_full_workflow(test_dir, sample_image_path):
    """Test the complete workflow from newspaper page to main database"""
    logger.info("Starting full workflow test")
    
    # Initialize components
    repo_db_path = test_dir / "repository" / "newspaper_repo.db"
    repo_db = RepositoryDatabaseManager(str(repo_db_path))
    file_mgr = FileManager(str(test_dir / "repository"))
    ocr_processor = OCRProcessor()
    
    # For testing purposes, we'll mock the main database connector
    # In a real scenario, you would connect to the actual Nova database
    main_connector = MainDBConnector(repo_db, "mock_connection_to_main_db")
    
    # Step 1: Import a newspaper page
    logger.info(f"Importing newspaper page from {sample_image_path}")
    
    # Parse metadata from filename (simplified for test)
    newspaper_name = "Test Newspaper"
    publication_date = "1900-01-01"
    page_number = 1
    source_id = "test_source"
    
    # Add page to repository
    page_id = repo_db.add_newspaper_page(
        newspaper_name=newspaper_name,
        publication_date=publication_date,
        page_number=page_number,
        source_id=source_id,
        source_url="https://example.com/test",
        ocr_status="pending"
    )
    
    # Save the page image file
    original_path = file_mgr.save_original_page(
        page_id=page_id,
        newspaper_name=newspaper_name,
        publication_date=publication_date,
        page_number=page_number,
        file_path=sample_image_path
    )
    
    logger.info(f"Saved original page: {original_path}")
    
    # Step 2: Process page with OCR
    logger.info("Processing page with OCR")
    repo_db.update_ocr_status(page_id, "processing")
    
    try:
        # Extract text with OCR
        ocr_text, hocr_output = ocr_processor.process_page(original_path)
        
        # Save OCR output
        ocr_path = file_mgr.save_ocr_text(
            page_id=page_id,
            newspaper_name=newspaper_name,
            publication_date=publication_date,
            page_number=page_number,
            ocr_text=ocr_text
        )
        
        hocr_path = file_mgr.save_hocr_output(
            page_id=page_id,
            newspaper_name=newspaper_name,
            publication_date=publication_date,
            page_number=page_number,
            hocr_content=hocr_output
        )
        
        # Update page record with OCR info
        repo_db.update_page_ocr_data(page_id, ocr_path, hocr_path)
        repo_db.update_ocr_status(page_id, "completed")
        
        logger.info(f"OCR processing completed. Text saved to {ocr_path}")
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        repo_db.update_ocr_status(page_id, "failed")
        return False
    
    # Step 3: Analyze page layout and extract article segments
    logger.info("Extracting article segments")
    try:
        segments = ocr_processor.analyze_layout_and_extract_segments(hocr_path, original_path)
        
        logger.info(f"Extracted {len(segments)} article segments")
        
        # Save each segment
        for i, segment in enumerate(segments):
            segment_id = repo_db.add_article_segment(
                page_id=page_id,
                position_data=segment.position_data,
                text_content=segment.text_content,
                headline=segment.headline if hasattr(segment, 'headline') else None,
                keywords=segment.keywords if hasattr(segment, 'keywords') else [],
                processing_status="extracted"
            )
            
            # Save segment image
            if segment.image_data:
                segment_img_path = file_mgr.save_article_segment_image(
                    segment_id=segment_id,
                    newspaper_name=newspaper_name,
                    publication_date=publication_date,
                    segment_number=i,
                    image_data=segment.image_data
                )
                
                # Update segment with image path
                repo_db.update_segment_image_path(segment_id, segment_img_path)
            
            logger.info(f"Saved article segment {segment_id}")
    except Exception as e:
        logger.error(f"Segment extraction failed: {str(e)}")
        return False
    
    # Step 4: Transfer selected segments to main database
    logger.info("Transferring segments to main database")
    try:
        # Get segments (in a real scenario, you might select only certain segments)
        segments = repo_db.get_article_segments_by_page(page_id)
        
        # For each segment, check if it's a duplicate and if not, import to main DB
        for segment in segments:
            # Check for duplicates
            potential_duplicates = main_connector.find_potential_duplicates(segment.text_content)
            
            if not potential_duplicates:
                # Import to main database
                event_id = main_connector.import_segment_as_event(
                    segment_id=segment.id,
                    title=segment.headline or f"Article from {newspaper_name} on {publication_date}",
                    date=publication_date,
                    text_content=segment.text_content,
                    source_id=source_id
                )
                
                logger.info(f"Imported segment {segment.id} as event {event_id}")
                
                # Mark as imported in repository
                repo_db.update_segment_status(segment.id, "imported", event_id)
            else:
                # Mark as duplicate
                repo_db.update_segment_status(
                    segment.id, 
                    "duplicate", 
                    potential_duplicates[0]  # ID of the first matching event
                )
                
                logger.info(f"Marked segment {segment.id} as duplicate of event {potential_duplicates[0]}")
        
        logger.info("Transfer to main database completed")
        return True
        
    except Exception as e:
        logger.error(f"Transfer to main database failed: {str(e)}")
        return False

def cleanup_test_environment(test_dir):
    """Clean up test files and directories"""
    # In a real test, you might want to remove test files
    # For now, we'll keep them for inspection
    logger.info(f"Test data available at {test_dir}")

def main():
    parser = argparse.ArgumentParser(description='Test the newspaper repository integration')
    parser.add_argument('--image', required=True, help='Path to a sample newspaper page image')
    args = parser.parse_args()
    
    if not os.path.exists(args.image):
        logger.error(f"Sample image not found: {args.image}")
        return 1
    
    # Setup test environment
    test_dir = setup_test_environment()
    
    # Run the integration test
    success = test_full_workflow(test_dir, args.image)
    
    # Cleanup
    cleanup_test_environment(test_dir)
    
    if success:
        logger.info("Integration test completed successfully")
        return 0
    else:
        logger.error("Integration test failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())