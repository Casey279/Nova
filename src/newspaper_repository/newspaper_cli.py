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
logger = logging.getLogger('newspaper_cli')

class NewspaperRepositoryCLI:
    """Command-line interface for the Newspaper Repository System"""
    
    def __init__(self, repo_path, main_db_connection=None):
        self.repo_path = Path(repo_path)
        
        # Ensure repository directories exist
        self.repo_path.mkdir(exist_ok=True)
        
        # Initialize components
        self.repo_db_path = self.repo_path / "newspaper_repo.db"
        self.db = RepositoryDatabaseManager(str(self.repo_db_path))
        self.file_mgr = FileManager(str(self.repo_path))
        self.ocr_processor = OCRProcessor()
        
        # Initialize main DB connector if connection is provided
        self.main_connector = None
        if main_db_connection:
            self.main_connector = MainDBConnector(self.db, main_db_connection)
    
    def import_page(self, image_path, newspaper_name, publication_date, page_number, source_id, source_url=None):
        """Import a newspaper page into the repository"""
        logger.info(f"Importing newspaper page from {image_path}")
        
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None
        
        # Add page to repository database
        page_id = self.db.add_newspaper_page(
            newspaper_name=newspaper_name,
            publication_date=publication_date,
            page_number=page_number,
            source_id=source_id,
            source_url=source_url,
            ocr_status="pending"
        )
        
        # Save the page image file
        original_path = self.file_mgr.save_original_page(
            page_id=page_id,
            newspaper_name=newspaper_name,
            publication_date=publication_date,
            page_number=page_number,
            file_path=image_path
        )
        
        logger.info(f"Newspaper page imported as ID {page_id}")
        logger.info(f"Original image saved to {original_path}")
        
        return page_id
    
    def process_page(self, page_id):
        """Process a newspaper page with OCR and extract article segments"""
        logger.info(f"Processing page {page_id} with OCR")
        
        # Get page information
        page_info = self.db.get_page_by_id(page_id)
        if not page_info:
            logger.error(f"Page ID {page_id} not found")
            return False
        
        # Update status to processing
        self.db.update_ocr_status(page_id, "processing")
        
        try:
            # Get original image path
            original_path = page_info.image_path
            
            # Extract text with OCR
            ocr_text, hocr_output = self.ocr_processor.process_page(original_path)
            
            # Save OCR output
            ocr_path = self.file_mgr.save_ocr_text(
                page_id=page_id,
                newspaper_name=page_info.newspaper_name,
                publication_date=page_info.publication_date,
                page_number=page_info.page_number,
                ocr_text=ocr_text
            )
            
            hocr_path = self.file_mgr.save_hocr_output(
                page_id=page_id,
                newspaper_name=page_info.newspaper_name,
                publication_date=page_info.publication_date,
                page_number=page_info.page_number,
                hocr_content=hocr_output
            )
            
            # Update page record with OCR info
            self.db.update_page_ocr_data(page_id, ocr_path, hocr_path)
            
            # Extract article segments
            segments = self.ocr_processor.analyze_layout_and_extract_segments(hocr_path, original_path)
            
            logger.info(f"Extracted {len(segments)} article segments")
            
            # Save each segment
            for i, segment in enumerate(segments):
                segment_id = self.db.add_article_segment(
                    page_id=page_id,
                    position_data=segment.position_data,
                    text_content=segment.text_content,
                    headline=segment.headline if hasattr(segment, 'headline') else None,
                    keywords=segment.keywords if hasattr(segment, 'keywords') else [],
                    processing_status="extracted"
                )
                
                # Save segment image
                if segment.image_data:
                    segment_img_path = self.file_mgr.save_article_segment_image(
                        segment_id=segment_id,
                        newspaper_name=page_info.newspaper_name,
                        publication_date=page_info.publication_date,
                        segment_number=i,
                        image_data=segment.image_data
                    )
                    
                    # Update segment with image path
                    self.db.update_segment_image_path(segment_id, segment_img_path)
                
                logger.info(f"Saved article segment {segment_id}")
            
            # Update OCR status to completed
            self.db.update_ocr_status(page_id, "completed")
            
            logger.info(f"OCR processing completed for page {page_id}")
            return True
            
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            self.db.update_ocr_status(page_id, "failed")
            return False
    
    def import_to_main_db(self, segment_id):
        """Import a segment to the main Nova database"""
        if not self.main_connector:
            logger.error("Main database connector not initialized")
            return False
        
        try:
            # Get segment information
            segment = self.db.get_segment_by_id(segment_id)
            if not segment:
                logger.error(f"Segment ID {segment_id} not found")
                return False
            
            # Get page information
            page_info = self.db.get_page_by_id(segment.page_id)
            
            # Check for duplicates
            potential_duplicates = self.main_connector.find_potential_duplicates(segment.text_content)
            
            if potential_duplicates:
                # Mark as duplicate
                self.db.update_segment_status(
                    segment_id, 
                    "duplicate", 
                    potential_duplicates[0]  # ID of the first matching event
                )
                
                logger.info(f"Segment {segment_id} is a duplicate of event {potential_duplicates[0]}")
                return False
            
            # Import to main database
            event_id = self.main_connector.import_segment_as_event(
                segment_id=segment_id,
                title=segment.headline or f"Article from {page_info.newspaper_name} on {page_info.publication_date}",
                date=page_info.publication_date,
                text_content=segment.text_content,
                source_id=page_info.source_id
            )
            
            # Mark as imported in repository
            self.db.update_segment_status(segment_id, "imported", event_id)
            
            logger.info(f"Imported segment {segment_id} as event {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Import to main database failed: {str(e)}")
            return False
    
    def list_pages(self, limit=50, offset=0):
        """List newspaper pages in the repository"""
        pages = self.db.get_pages(limit=limit, offset=offset)
        
        if not pages:
            print("No newspaper pages found in repository")
            return
        
        print(f"{'ID':<6} {'Newspaper':<25} {'Date':<12} {'Page':<6} {'OCR Status':<12}")
        print("-" * 70)
        
        for page in pages:
            print(f"{page.id:<6} {page.newspaper_name[:23]:<25} {page.publication_date:<12} {page.page_number:<6} {page.ocr_status:<12}")
    
    def list_segments(self, page_id=None, limit=50, offset=0):
        """List article segments in the repository"""
        if page_id:
            segments = self.db.get_article_segments_by_page(page_id)
        else:
            segments = self.db.get_article_segments(limit=limit, offset=offset)
        
        if not segments:
            print("No article segments found")
            return
        
        print(f"{'ID':<6} {'Page ID':<8} {'Status':<12} {'Headline':<40}")
        print("-" * 70)
        
        for segment in segments:
            headline = segment.headline if segment.headline else "[No headline]"
            headline = headline[:38] + ".." if len(headline) > 40 else headline
            print(f"{segment.id:<6} {segment.page_id:<8} {segment.processing_status:<12} {headline:<40}")
    
    def show_segment(self, segment_id):
        """Display detailed information about an article segment"""
        segment = self.db.get_segment_by_id(segment_id)
        
        if not segment:
            print(f"Segment ID {segment_id} not found")
            return
        
        # Get page information
        page_info = self.db.get_page_by_id(segment.page_id)
        
        print(f"Segment ID: {segment.id}")
        print(f"Page: {page_info.newspaper_name}, {page_info.publication_date}, Page {page_info.page_number}")
        print(f"Status: {segment.processing_status}")
        
        if segment.linked_event_id:
            print(f"Linked to event ID: {segment.linked_event_id}")
        
        print("\nHeadline:")
        print(segment.headline if segment.headline else "[No headline]")
        
        print("\nContent:")
        print(segment.text_content[:500] + "..." if len(segment.text_content) > 500 else segment.text_content)
        
        if segment.image_path:
            print(f"\nImage: {segment.image_path}")
        
        if segment.keywords:
            print("\nKeywords:")
            print(", ".join(segment.keywords))

def main():
    parser = argparse.ArgumentParser(description='Newspaper Repository System CLI')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Import page command
    import_parser = subparsers.add_parser('import', help='Import a newspaper page')
    import_parser.add_argument('--image', required=True, help='Path to newspaper page image')
    import_parser.add_argument('--newspaper', required=True, help='Newspaper name')
    import_parser.add_argument('--date', required=True, help='Publication date (YYYY-MM-DD)')
    import_parser.add_argument('--page', required=True, type=int, help='Page number')
    import_parser.add_argument('--source', required=True, help='Source ID')
    import_parser.add_argument('--url', help='Source URL')
    
    # Process page command
    process_parser = subparsers.add_parser('process', help='Process a newspaper page with OCR')
    process_parser.add_argument('--id', required=True, type=int, help='Page ID')
    
    # Import to main DB command
    import_main_parser = subparsers.add_parser('import-to-main', help='Import a segment to the main database')
    import_main_parser.add_argument('--id', required=True, type=int, help='Segment ID')
    import_main_parser.add_argument('--main-db', required=True, help='Main database connection string')
    
    # List pages command
    list_pages_parser = subparsers.add_parser('list-pages', help='List newspaper pages')
    list_pages_parser.add_argument('--limit', type=int, default=50, help='Maximum number of pages to list')
    list_pages_parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    
    # List segments command
    list_segments_parser = subparsers.add_parser('list-segments', help='List article segments')
    list_segments_parser.add_argument('--page-id', type=int, help='Filter by page ID')
    list_segments_parser.add_argument('--limit', type=int, default=50, help='Maximum number of segments to list')
    list_segments_parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    
    # Show segment command
    show_segment_parser = subparsers.add_parser('show-segment', help='Show segment details')
    show_segment_parser.add_argument('--id', required=True, type=int, help='Segment ID')
    
    # Common arguments
    parser.add_argument('--repo-path', default='./newspaper_repository', help='Path to newspaper repository')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize CLI
    cli = NewspaperRepositoryCLI(args.repo_path)
    
    # Execute command
    if args.command == 'import':
        cli.import_page(
            args.image, 
            args.newspaper, 
            args.date, 
            args.page, 
            args.source, 
            args.url
        )
    
    elif args.command == 'process':
        cli.process_page(args.id)
    
    elif args.command == 'import-to-main':
        # Initialize main DB connector
        cli.main_connector = MainDBConnector(cli.db, args.main_db)
        cli.import_to_main_db(args.id)
    
    elif args.command == 'list-pages':
        cli.list_pages(args.limit, args.offset)
    
    elif args.command == 'list-segments':
        cli.list_segments(args.page_id, args.limit, args.offset)
    
    elif args.command == 'show-segment':
        cli.show_segment(args.id)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())