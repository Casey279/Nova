#!/usr/bin/env python3
# File: test_repository_system.py

import os
import sys
import unittest
import tempfile
import shutil
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
import io
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import repository components
from src.newspaper_repository.repository_database import RepositoryDatabaseManager
from src.newspaper_repository.file_manager import FileManager
from src.newspaper_repository.ocr_processor import OCRProcessor, ArticleSegment
from src.newspaper_repository.main_db_connector import MainDBConnector

class TestRepositoryDatabase(unittest.TestCase):
    """Test cases for the repository database operations."""
    
    def setUp(self):
        """Set up test environment with in-memory database."""
        # Create in-memory database
        self.db = RepositoryDatabaseManager(":memory:")
        
        # Initialize database schema
        self.db.init_db()
        
        # Test data
        self.test_page_data = {
            "newspaper_name": "Test Gazette",
            "publication_date": "1900-01-01",
            "page_number": 1,
            "source_id": "test_source",
            "source_url": "https://example.com/test",
            "ocr_status": "pending"
        }
        
        self.test_segment_data = {
            "page_id": 1,
            "position_data": '{"x": 100, "y": 100, "width": 300, "height": 500}',
            "text_content": "This is a test article segment.",
            "headline": "Test Headline",
            "processing_status": "extracted"
        }
    
    def test_init_db(self):
        """Test that database initialization creates expected tables."""
        # Get list of tables
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in self.db.cursor.fetchall()]
        
        # Check that expected tables exist
        expected_tables = [
            "newspaper_pages", 
            "article_segments", 
            "article_keywords",
            "processing_queue"
        ]
        
        for table in expected_tables:
            self.assertIn(table, tables)
    
    def test_add_newspaper_page(self):
        """Test adding a newspaper page to the database."""
        # Add page
        page_id = self.db.add_newspaper_page(**self.test_page_data)
        
        # Verify page was added
        self.assertIsNotNone(page_id)
        self.assertEqual(page_id, 1)  # First page should have ID 1
        
        # Retrieve page and verify data
        self.db.cursor.execute("SELECT * FROM newspaper_pages WHERE page_id = ?", (page_id,))
        page = self.db.cursor.fetchone()
        
        self.assertEqual(page["newspaper_name"], self.test_page_data["newspaper_name"])
        self.assertEqual(page["publication_date"], self.test_page_data["publication_date"])
        self.assertEqual(page["page_number"], self.test_page_data["page_number"])
        self.assertEqual(page["source_id"], self.test_page_data["source_id"])
        self.assertEqual(page["ocr_status"], self.test_page_data["ocr_status"])
    
    def test_add_article_segment(self):
        """Test adding an article segment to the database."""
        # First add a page to reference
        page_id = self.db.add_newspaper_page(**self.test_page_data)
        
        # Add segment
        segment_id = self.db.add_article_segment(**self.test_segment_data)
        
        # Verify segment was added
        self.assertIsNotNone(segment_id)
        self.assertEqual(segment_id, 1)  # First segment should have ID 1
        
        # Retrieve segment and verify data
        self.db.cursor.execute("SELECT * FROM article_segments WHERE segment_id = ?", (segment_id,))
        segment = self.db.cursor.fetchone()
        
        self.assertEqual(segment["page_id"], self.test_segment_data["page_id"])
        self.assertEqual(segment["position_data"], self.test_segment_data["position_data"])
        self.assertEqual(segment["text_content"], self.test_segment_data["text_content"])
        self.assertEqual(segment["headline"], self.test_segment_data["headline"])
        self.assertEqual(segment["processing_status"], self.test_segment_data["processing_status"])
    
    def test_add_article_keywords(self):
        """Test adding keywords to an article segment."""
        # Add page and segment first
        page_id = self.db.add_newspaper_page(**self.test_page_data)
        segment_id = self.db.add_article_segment(**self.test_segment_data)
        
        # Add keywords
        keywords = ["test", "newspaper", "article"]
        for keyword in keywords:
            self.db.add_keyword(segment_id, keyword)
        
        # Verify keywords were added
        self.db.cursor.execute("SELECT keyword FROM article_keywords WHERE segment_id = ?", (segment_id,))
        db_keywords = [row["keyword"] for row in self.db.cursor.fetchall()]
        
        for keyword in keywords:
            self.assertIn(keyword, db_keywords)
    
    def test_update_ocr_status(self):
        """Test updating OCR status for a page."""
        # Add page
        page_id = self.db.add_newspaper_page(**self.test_page_data)
        
        # Update OCR status
        new_status = "completed"
        self.db.update_ocr_status(page_id, new_status)
        
        # Verify status was updated
        self.db.cursor.execute("SELECT ocr_status FROM newspaper_pages WHERE page_id = ?", (page_id,))
        status = self.db.cursor.fetchone()["ocr_status"]
        
        self.assertEqual(status, new_status)
    
    def test_update_segment_status(self):
        """Test updating processing status for an article segment."""
        # Add page and segment
        page_id = self.db.add_newspaper_page(**self.test_page_data)
        segment_id = self.db.add_article_segment(**self.test_segment_data)
        
        # Update status to indicate import to main database
        new_status = "imported"
        event_id = 42  # Fake event ID in main database
        self.db.update_segment_status(segment_id, new_status, event_id)
        
        # Verify status and link were updated
        self.db.cursor.execute(
            "SELECT processing_status, linked_event_id FROM article_segments WHERE segment_id = ?", 
            (segment_id,)
        )
        row = self.db.cursor.fetchone()
        
        self.assertEqual(row["processing_status"], new_status)
        self.assertEqual(row["linked_event_id"], event_id)
    
    def test_get_segments_by_page(self):
        """Test retrieving all segments for a specific page."""
        # Add page
        page_id = self.db.add_newspaper_page(**self.test_page_data)
        
        # Add multiple segments
        segment_ids = []
        for i in range(3):
            segment_data = self.test_segment_data.copy()
            segment_data["headline"] = f"Test Headline {i+1}"
            segment_id = self.db.add_article_segment(**segment_data)
            segment_ids.append(segment_id)
        
        # Retrieve segments for page
        segments = self.db.get_segments_by_page_id(page_id)
        
        # Verify correct number of segments returned
        self.assertEqual(len(segments), 3)
        
        # Verify segment data
        headlines = [s.headline for s in segments]
        for i in range(3):
            self.assertIn(f"Test Headline {i+1}", headlines)
    
    def test_add_to_processing_queue(self):
        """Test adding items to the processing queue."""
        # Add a page
        page_id = self.db.add_newspaper_page(**self.test_page_data)
        
        # Add page to processing queue
        queue_id = self.db.add_to_processing_queue("page_ocr", page_id, "pending")
        
        # Verify queue item was added
        self.assertIsNotNone(queue_id)
        
        # Retrieve queue item
        self.db.cursor.execute("SELECT * FROM processing_queue WHERE queue_id = ?", (queue_id,))
        queue_item = self.db.cursor.fetchone()
        
        self.assertEqual(queue_item["item_type"], "page_ocr")
        self.assertEqual(queue_item["item_id"], page_id)
        self.assertEqual(queue_item["status"], "pending")
    
    def test_search_pages(self):
        """Test searching for newspaper pages."""
        # Add multiple pages with different newspapers
        newspapers = ["Daily Times", "Morning Herald", "Evening News"]
        for i, name in enumerate(newspapers):
            page_data = self.test_page_data.copy()
            page_data["newspaper_name"] = name
            page_data["publication_date"] = f"1900-01-{i+1:02d}"
            self.db.add_newspaper_page(**page_data)
        
        # Search for a specific newspaper
        results = self.db.search_pages_by_newspaper("Herald")
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].newspaper_name, "Morning Herald")
        
        # Search by date
        results = self.db.search_pages_by_date("1900-01-03")
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].newspaper_name, "Evening News")

class TestFileManager(unittest.TestCase):
    """Test cases for the file manager operations."""
    
    def setUp(self):
        """Set up test environment with temporary directory."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize file manager
        self.file_manager = FileManager(self.temp_dir)
        
        # Generate a simple test image
        self.test_image = self._create_test_image()
        
        # Sample test data
        self.page_id = 1
        self.newspaper_name = "Test Gazette"
        self.publication_date = "1900-01-01"
        self.page_number = 1
        
        # Create a sample image file
        self.image_file = os.path.join(self.temp_dir, "test_image.jpg")
        self.test_image.save(self.image_file)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_image(self, width=800, height=1200):
        """Create a test image for testing."""
        # Create a blank white image
        image = Image.new('RGB', (width, height), color='white')
        
        # Draw some text to simulate a newspaper
        draw = ImageDraw.Draw(image)
        
        # Try to get a font, use default if not available
        try:
            font = ImageFont.truetype("Arial", 30)
        except IOError:
            font = ImageFont.load_default()
        
        # Add newspaper title
        draw.text((width//2-100, 50), "TEST GAZETTE", fill='black', font=font)
        
        # Add a headline
        draw.text((width//2-150, 150), "TEST HEADLINE", fill='black', font=font)
        
        # Add some article text
        article_text = "This is a test article for OCR processing."
        draw.text((50, 250), article_text, fill='black', font=font)
        
        # Add a horizontal line to simulate column division
        draw.line([(50, 350), (width-50, 350)], fill='black', width=2)
        
        # Add some more text
        draw.text((50, 400), "More test content goes here.", fill='black', font=font)
        
        return image
    
    def test_directory_structure(self):
        """Test that the correct directory structure is created."""
        # Verify that required directories are created
        required_dirs = [
            "original_pages",
            "ocr_text",
            "hocr_output",
            "article_segments",
            "enhanced_segments"
        ]
        
        for dir_name in required_dirs:
            dir_path = os.path.join(self.temp_dir, dir_name)
            self.assertTrue(os.path.isdir(dir_path), f"Directory {dir_name} not created")
    
    def test_save_original_page(self):
        """Test saving an original newspaper page image."""
        # Save the original page
        saved_path = self.file_manager.save_original_page(
            self.page_id,
            self.newspaper_name,
            self.publication_date,
            self.page_number,
            self.image_file
        )
        
        # Verify file exists
        self.assertTrue(os.path.exists(saved_path))
        
        # Verify file is in correct location
        expected_dir = os.path.join(self.temp_dir, "original_pages")
        self.assertTrue(saved_path.startswith(expected_dir))
        
        # Verify file has correct format
        expected_filename = f"{self.page_id}_Test_Gazette_1900-01-01_p1.jpg"
        self.assertTrue(saved_path.endswith(expected_filename))
    
    def test_save_ocr_text(self):
        """Test saving OCR text output."""
        # Test OCR text
        ocr_text = "This is a test OCR text output."
        
        # Save OCR text
        saved_path = self.file_manager.save_ocr_text(
            self.page_id,
            self.newspaper_name,
            self.publication_date,
            self.page_number,
            ocr_text
        )
        
        # Verify file exists
        self.assertTrue(os.path.exists(saved_path))
        
        # Verify file is in correct location
        expected_dir = os.path.join(self.temp_dir, "ocr_text")
        self.assertTrue(saved_path.startswith(expected_dir))
        
        # Verify file has correct format
        expected_filename = f"{self.page_id}_Test_Gazette_1900-01-01_p1.txt"
        self.assertTrue(saved_path.endswith(expected_filename))
        
        # Verify file contents
        with open(saved_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertEqual(content, ocr_text)
    
    def test_save_hocr_output(self):
        """Test saving HOCR output."""
        # Test HOCR content
        hocr_content = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8" /></head>
<body>
  <div class='ocr_page'>
    <span class='ocr_line'>This is a test OCR line.</span>
  </div>
</body>
</html>"""
        
        # Save HOCR output
        saved_path = self.file_manager.save_hocr_output(
            self.page_id,
            self.newspaper_name,
            self.publication_date,
            self.page_number,
            hocr_content
        )
        
        # Verify file exists
        self.assertTrue(os.path.exists(saved_path))
        
        # Verify file is in correct location
        expected_dir = os.path.join(self.temp_dir, "hocr_output")
        self.assertTrue(saved_path.startswith(expected_dir))
        
        # Verify file has correct format
        expected_filename = f"{self.page_id}_Test_Gazette_1900-01-01_p1.hocr"
        self.assertTrue(saved_path.endswith(expected_filename))
        
        # Verify file contents
        with open(saved_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertEqual(content, hocr_content)
    
    def test_save_article_segment_image(self):
        """Test saving an article segment image."""
        # Create a small image representing a segment
        segment_image = Image.new('RGB', (400, 300), color='white')
        
        # Save segment image
        segment_id = 101
        saved_path = self.file_manager.save_article_segment_image(
            segment_id,
            self.newspaper_name,
            self.publication_date,
            1,  # segment number
            segment_image
        )
        
        # Verify file exists
        self.assertTrue(os.path.exists(saved_path))
        
        # Verify file is in correct location
        expected_dir = os.path.join(self.temp_dir, "article_segments")
        self.assertTrue(saved_path.startswith(expected_dir))
        
        # Verify file has correct format
        expected_filename = f"{segment_id}_Test_Gazette_1900-01-01_seg1.jpg"
        self.assertTrue(saved_path.endswith(expected_filename))
    
    def test_get_file_path(self):
        """Test getting file path for a specific file type."""
        # Test getting original page path
        path = self.file_manager.get_file_path(
            "original_pages",
            self.page_id,
            self.newspaper_name,
            self.publication_date,
            self.page_number,
            extension="jpg"
        )
        
        # Verify path is correct
        expected_dir = os.path.join(self.temp_dir, "original_pages")
        expected_filename = f"{self.page_id}_Test_Gazette_1900-01-01_p1.jpg"
        expected_path = os.path.join(expected_dir, expected_filename)
        
        self.assertEqual(path, expected_path)

class TestOCRProcessor(unittest.TestCase):
    """Test cases for the OCR processor operations."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize OCR processor
        self.ocr_processor = OCRProcessor()
        
        # Generate a test image
        self.test_image = self._create_test_image()
        self.image_path = os.path.join(self.temp_dir, "test_page.jpg")
        self.test_image.save(self.image_path)
        
        # Create a sample HOCR file
        self.hocr_content = self._create_sample_hocr()
        self.hocr_path = os.path.join(self.temp_dir, "test_page.hocr")
        with open(self.hocr_path, 'w', encoding='utf-8') as f:
            f.write(self.hocr_content)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_image(self, width=800, height=1200):
        """Create a test image for OCR testing."""
        # Create a blank white image
        image = Image.new('RGB', (width, height), color='white')
        
        # Draw some text to simulate a newspaper
        draw = ImageDraw.Draw(image)
        
        # Try to get a font, use default if not available
        try:
            font = ImageFont.truetype("Arial", 30)
        except IOError:
            font = ImageFont.load_default()
        
        # Add newspaper title
        draw.text((width//2-100, 50), "TEST GAZETTE", fill='black', font=font)
        
        # Add a headline
        draw.text((width//2-150, 150), "TEST HEADLINE", fill='black', font=font)
        
        # Add some article text
        article_text = "This is a test article for OCR processing."
        draw.text((50, 250), article_text, fill='black', font=font)
        
        # Add a horizontal line to simulate column division
        draw.line([(50, 350), (width-50, 350)], fill='black', width=2)
        
        # Add some more text
        draw.text((50, 400), "More test content goes here.", fill='black', font=font)
        
        return image
    
    def _create_sample_hocr(self):
        """Create a sample HOCR file for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
  <head>
    <title>OCR Output</title>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
    <meta name='ocr-system' content='tesseract' />
  </head>
  <body>
    <div class='ocr_page' id='page_1' title='image "test_page.jpg"; bbox 0 0 800 1200; ppageno 0'>
      <div class='ocr_carea' id='block_1_1' title="bbox 300 50 500 100">
        <p class='ocr_par' id='par_1_1'>
          <span class='ocr_line' id='line_1_1' title="bbox 300 50 500 80">
            <span class='ocrx_word' id='word_1_1' title="bbox 300 50 400 80">TEST</span>
            <span class='ocrx_word' id='word_1_2' title="bbox 410 50 500 80">GAZETTE</span>
          </span>
        </p>
      </div>
      <div class='ocr_carea' id='block_1_2' title="bbox 250 150 550 180">
        <p class='ocr_par' id='par_1_2'>
          <span class='ocr_line' id='line_1_2' title="bbox 250 150 550 180">
            <span class='ocrx_word' id='word_1_3' title="bbox 250 150 350 180">TEST</span>
            <span class='ocrx_word' id='word_1_4' title="bbox 360 150 550 180">HEADLINE</span>
          </span>
        </p>
      </div>
      <div class='ocr_carea' id='block_1_3' title="bbox 50 250 750 300">
        <p class='ocr_par' id='par_1_3'>
          <span class='ocr_line' id='line_1_3' title="bbox 50 250 750 280">
            <span class='ocrx_word' id='word_1_5' title="bbox 50 250 100 280">This</span>
            <span class='ocrx_word' id='word_1_6' title="bbox 110 250 130 280">is</span>
            <span class='ocrx_word' id='word_1_7' title="bbox 140 250 150 280">a</span>
            <span class='ocrx_word' id='word_1_8' title="bbox 160 250 210 280">test</span>
            <span class='ocrx_word' id='word_1_9' title="bbox 220 250 300 280">article</span>
            <span class='ocrx_word' id='word_1_10' title="bbox 310 250 340 280">for</span>
            <span class='ocrx_word' id='word_1_11' title="bbox 350 250 400 280">OCR</span>
            <span class='ocrx_word' id='word_1_12' title="bbox 410 250 520 280">processing.</span>
          </span>
        </p>
      </div>
      <div class='ocr_carea' id='block_1_4' title="bbox 50 400 550 430">
        <p class='ocr_par' id='par_1_4'>
          <span class='ocr_line' id='line_1_4' title="bbox 50 400 550 430">
            <span class='ocrx_word' id='word_1_13' title="bbox 50 400 100 430">More</span>
            <span class='ocrx_word' id='word_1_14' title="bbox 110 400 150 430">test</span>
            <span class='ocrx_word' id='word_1_15' title="bbox 160 400 240 430">content</span>
            <span class='ocrx_word' id='word_1_16' title="bbox 250 400 300 430">goes</span>
            <span class='ocrx_word' id='word_1_17' title="bbox 310 400 360 430">here.</span>
          </span>
        </p>
      </div>
    </div>
  </body>
</html>"""
    
    @patch('src.newspaper_repository.ocr_processor.pytesseract')
    def test_process_page(self, mock_pytesseract):
        """Test processing a page with OCR."""
        # Mock pytesseract response
        mock_pytesseract.image_to_string.return_value = "This is test OCR output."
        mock_pytesseract.image_to_pdf_or_hocr.return_value = "Sample HOCR output"
        
        # Process the test image
        ocr_text, hocr_output = self.ocr_processor.process_page(self.image_path)
        
        # Verify pytesseract was called
        mock_pytesseract.image_to_string.assert_called_once()
        mock_pytesseract.image_to_pdf_or_hocr.assert_called_once()
        
        # Verify outputs
        self.assertEqual(ocr_text, "This is test OCR output.")
        self.assertEqual(hocr_output, "Sample HOCR output")
    
    def test_analyze_layout_from_hocr(self):
        """Test analyzing page layout from HOCR data."""
        # Analyze layout
        layout = self.ocr_processor.analyze_layout_from_hocr(self.hocr_path)
        
        # Verify layout contains expected areas
        self.assertEqual(len(layout), 4)
        
        # Verify areas have expected bounding boxes
        expected_boxes = [
            (300, 50, 500, 100),   # Newspaper title
            (250, 150, 550, 180),  # Headline
            (50, 250, 750, 300),   # Article text
            (50, 400, 550, 430)    # More content
        ]
        
        for i, area in enumerate(layout):
            self.assertEqual(area["bbox"], expected_boxes[i])
    
    def test_analyze_layout_and_extract_segments(self):
        """Test extracting article segments from page layout."""
        # Mock image to ensure test works without relying on external OCR
        with patch.object(self.ocr_processor, 'analyze_layout_from_hocr') as mock_analyze:
            # Mock layout analysis to return predictable areas
            mock_analyze.return_value = [
                {"bbox": (250, 150, 550, 180), "text": "TEST HEADLINE"},
                {"bbox": (50, 250, 750, 300), "text": "This is a test article for OCR processing."},
                {"bbox": (50, 400, 550, 430), "text": "More test content goes here."}
            ]
            
            # Mock extract_image_segment to return a dummy image
            with patch.object(self.ocr_processor, 'extract_image_segment') as mock_extract:
                mock_extract.return_value = Image.new('RGB', (100, 100))
                
                # Extract segments
                segments = self.ocr_processor.analyze_layout_and_extract_segments(
                    self.hocr_path, 
                    self.image_path
                )
                
                # Verify segments were extracted
                self.assertEqual(len(segments), 1)  # Should combine into one article
                
                # Verify segment properties
                segment = segments[0]
                self.assertIsInstance(segment, ArticleSegment)
                self.assertEqual(segment.headline, "TEST HEADLINE")
                self.assertIn("This is a test article", segment.text_content)
                self.assertIn("More test content", segment.text_content)
    
    def test_extract_image_segment(self):
        """Test extracting an image segment from the page."""
        # Extract a segment
        bbox = (50, 250, 750, 300)  # Coordinates for article text
        segment_img = self.ocr_processor.extract_image_segment(self.image_path, bbox)
        
        # Verify segment image properties
        self.assertIsInstance(segment_img, Image.Image)
        self.assertEqual(segment_img.width, bbox[2] - bbox[0])
        self.assertEqual(segment_img.height, bbox[3] - bbox[1])

class TestMainDBConnector(unittest.TestCase):
    """Test cases for the main database connector."""
    
    def setUp(self):
        """Set up test environment with in-memory databases."""
        # Create in-memory repository database
        self.repo_db = RepositoryDatabaseManager(":memory:")
        self.repo_db.init_db()
        
        # Create in-memory main database
        self.main_db_conn = sqlite3.connect(":memory:")
        self.main_db_conn.row_factory = sqlite3.Row
        
        # Initialize main database schema
        self.init_main_db_schema()
        
        # Initialize connector
        self.connector = MainDBConnector(self.repo_db, self.main_db_conn)
        
        # Add test data
        self.create_test_data()
    
    def init_main_db_schema(self):
        """Initialize a simplified schema for the main database."""
        cursor = self.main_db_conn.cursor()
        
        # Create simplified Events table
        cursor.execute("""
            CREATE TABLE Events (
                EventID INTEGER PRIMARY KEY AUTOINCREMENT,
                EventTitle TEXT,
                EventDate TEXT,
                EventText TEXT,
                SourceID INTEGER,
                page_number TEXT,
                created_date TEXT,
                modified_date TEXT,
                status TEXT,
                confidence REAL,
                verified INTEGER
            )
        """)
        
        # Create simplified Sources table
        cursor.execute("""
            CREATE TABLE Sources (
                SourceID INTEGER PRIMARY KEY AUTOINCREMENT,
                SourceName TEXT,
                SourceType TEXT,
                Publisher TEXT,
                EstablishedDate TEXT,
                ReviewStatus TEXT
            )
        """)
        
        # Create simplified Entities table
        cursor.execute("""
            CREATE TABLE Entities (
                EventID INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                entity_type TEXT
            )
        """)
        
        # Create simplified entity_mentions table
        cursor.execute("""
            CREATE TABLE entity_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                entity_id INTEGER
            )
        """)
        
        self.main_db_conn.commit()
    
    def create_test_data(self):
        """Create test data in both databases."""
        # Add a newspaper page to repository
        self.page_id = self.repo_db.add_newspaper_page(
            newspaper_name="Test Gazette",
            publication_date="1900-01-01",
            page_number=1,
            source_id="test_source",
            source_url="https://example.com/test",
            ocr_status="completed"
        )
        
        # Add an article segment
        position_data = '{"x": 100, "y": 100, "width": 300, "height": 500}'
        self.segment_id = self.repo_db.add_article_segment(
            page_id=self.page_id,
            position_data=position_data,
            text_content="This is a test article about historical events.",
            headline="Test Historical Article",
            processing_status="extracted"
        )
        
        # Add some keywords
        keywords = ["history", "test", "article"]
        for keyword in keywords:
            self.repo_db.add_keyword(self.segment_id, keyword)
        
        # Add a source to main database
        cursor = self.main_db_conn.cursor()
        cursor.execute("""
            INSERT INTO Sources (SourceName, SourceType, Publisher, ReviewStatus)
            VALUES (?, ?, ?, ?)
        """, ("Test Gazette", "Newspaper", "Test Publisher", "imported"))
        self.source_id = cursor.lastrowid
        self.main_db_conn.commit()
    
    def test_validate_connections(self):
        """Test that connections are validated correctly."""
        # This is implicitly tested in setUp, but we add a specific test
        # for better diagnostics if it fails
        
        # Method should not raise any exceptions
        self.connector._validate_connections()
        
        # Test with invalid connection should raise ValueError
        with self.assertRaises(ValueError):
            bad_db = MagicMock()
            bad_db.conn = None
            MainDBConnector(bad_db, self.main_db_conn)
    
    def test_import_segment_as_event(self):
        """Test importing a segment as an event in the main database."""
        # Import the segment
        event_id = self.connector.import_segment_as_event(
            self.segment_id,
            "Test Historical Article",
            "1900-01-01",
            "This is a test article about historical events.",
            str(self.source_id)
        )
        
        # Verify event was created
        self.assertIsNotNone(event_id)
        
        # Verify event data in main database
        cursor = self.main_db_conn.cursor()
        cursor.execute("SELECT * FROM Events WHERE EventID = ?", (event_id,))
        event = cursor.fetchone()
        
        self.assertEqual(event["EventTitle"], "Test Historical Article")
        self.assertEqual(event["EventDate"], "1900-01-01")
        self.assertEqual(event["EventText"], "This is a test article about historical events.")
        self.assertEqual(event["SourceID"], self.source_id)
        
        # Verify segment status updated in repository
        segment = self.repo_db.get_segment_by_id(self.segment_id)
        self.assertEqual(segment.processing_status, "imported")
        self.assertEqual(segment.linked_event_id, event_id)
    
    def test_find_potential_duplicates(self):
        """Test finding potential duplicates in the main database."""
        # Add an event to the main database
        cursor = self.main_db_conn.cursor()
        cursor.execute("""
            INSERT INTO Events (EventTitle, EventDate, EventText, SourceID)
            VALUES (?, ?, ?, ?)
        """, (
            "Historical Article", 
            "1900-01-01", 
            "This is an existing article about historical events.",
            self.source_id
        ))
        existing_event_id = cursor.lastrowid
        self.main_db_conn.commit()
        
        # Find potential duplicates for similar text
        duplicates = self.connector.find_potential_duplicates(
            "This is a test article about historical events.",
            "Test Historical Article",
            "1900-01-01"
        )
        
        # Verify duplicate was found
        self.assertIn(existing_event_id, duplicates)
    
    def test_mark_segment_as_duplicate(self):
        """Test marking a segment as a duplicate of an existing event."""
        # Add an event to the main database
        cursor = self.main_db_conn.cursor()
        cursor.execute("""
            INSERT INTO Events (EventTitle, EventDate, EventText, SourceID)
            VALUES (?, ?, ?, ?)
        """, (
            "Historical Article", 
            "1900-01-01", 
            "This is an existing article about historical events.",
            self.source_id
        ))
        existing_event_id = cursor.lastrowid
        self.main_db_conn.commit()
        
        # Mark segment as duplicate
        result = self.connector.mark_segment_as_duplicate(self.segment_id, existing_event_id)
        
        # Verify result
        self.assertTrue(result)
        
        # Verify segment status updated in repository
        segment = self.repo_db.get_segment_by_id(self.segment_id)
        self.assertEqual(segment.processing_status, "duplicate")
        self.assertEqual(segment.linked_event_id, existing_event_id)
    
    def test_batch_import_segments(self):
        """Test batch importing multiple segments."""
        # Add another segment
        position_data = '{"x": 400, "y": 100, "width": 300, "height": 500}'
        segment_id2 = self.repo_db.add_article_segment(
            page_id=self.page_id,
            position_data=position_data,
            text_content="This is another test article.",
            headline="Second Test Article",
            processing_status="extracted"
        )
        
        # Import both segments
        segment_ids = [self.segment_id, segment_id2]
        results = self.connector.batch_import_segments(segment_ids)
        
        # Verify results
        self.assertEqual(results['success_count'], 2)
        self.assertEqual(results['failure_count'], 0)
        
        # Verify both segments were imported
        for segment_id in segment_ids:
            segment = self.repo_db.get_segment_by_id(segment_id)
            self.assertEqual(segment.processing_status, "imported")
            self.assertIsNotNone(segment.linked_event_id)
    
    def test_get_event_details(self):
        """Test getting detailed information about an event."""
        # Add an event to the main database
        cursor = self.main_db_conn.cursor()
        cursor.execute("""
            INSERT INTO Events (EventTitle, EventDate, EventText, SourceID, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Historical Article", 
            "1900-01-01", 
            "This is an existing article about historical events.",
            self.source_id,
            "active"
        ))
        event_id = cursor.lastrowid
        self.main_db_conn.commit()
        
        # Get event details
        event = self.connector.get_event_details(event_id)
        
        # Verify event details
        self.assertEqual(event['EventID'], event_id)
        self.assertEqual(event['EventTitle'], "Historical Article")
        self.assertEqual(event['EventDate'], "1900-01-01")
        self.assertEqual(event['status'], "active")

class TestIntegration(unittest.TestCase):
    """Integration tests for the full repository system."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.temp_dir, "newspaper_repository")
        os.makedirs(self.repo_dir)
        
        # Initialize repository components
        self.repo_db = RepositoryDatabaseManager(os.path.join(self.repo_dir, "repository.db"))
        self.file_manager = FileManager(self.repo_dir)
        self.ocr_processor = OCRProcessor()
        
        # Create in-memory main database
        self.main_db_conn = sqlite3.connect(":memory:")
        self.main_db_conn.row_factory = sqlite3.Row
        
        # Initialize main database schema
        self.init_main_db_schema()
        
        # Initialize connector
        self.connector = MainDBConnector(self.repo_db, self.main_db_conn)
        
        # Create a test image
        self.test_image = self._create_test_image()
        self.image_path = os.path.join(self.temp_dir, "test_page.jpg")
        self.test_image.save(self.image_path)
        
        # Mock OCR results for testing
        self.mock_ocr_text = "TEST GAZETTE\n\nTEST HEADLINE\n\nThis is a test article for OCR processing.\n\nMore test content goes here."
        self.mock_hocr = self._create_sample_hocr()
    
    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir)
    
    def init_main_db_schema(self):
        """Initialize a simplified schema for the main database."""
        cursor = self.main_db_conn.cursor()
        
        # Create simplified Events table
        cursor.execute("""
            CREATE TABLE Events (
                EventID INTEGER PRIMARY KEY AUTOINCREMENT,
                EventTitle TEXT,
                EventDate TEXT,
                EventText TEXT,
                SourceID INTEGER,
                page_number TEXT,
                created_date TEXT,
                modified_date TEXT,
                status TEXT,
                confidence REAL,
                verified INTEGER
            )
        """)
        
        # Create simplified Sources table
        cursor.execute("""
            CREATE TABLE Sources (
                SourceID INTEGER PRIMARY KEY AUTOINCREMENT,
                SourceName TEXT,
                SourceType TEXT,
                Publisher TEXT,
                EstablishedDate TEXT,
                ReviewStatus TEXT
            )
        """)
        
        # Create simplified Entities table
        cursor.execute("""
            CREATE TABLE Entities (
                EventID INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                entity_type TEXT
            )
        """)
        
        # Create simplified entity_mentions table
        cursor.execute("""
            CREATE TABLE entity_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                entity_id INTEGER
            )
        """)
        
        self.main_db_conn.commit()
    
    def _create_test_image(self, width=800, height=1200):
        """Create a test image for OCR testing."""
        # Create a blank white image
        image = Image.new('RGB', (width, height), color='white')
        
        # Draw some text to simulate a newspaper
        draw = ImageDraw.Draw(image)
        
        # Try to get a font, use default if not available
        try:
            font = ImageFont.truetype("Arial", 30)
        except IOError:
            font = ImageFont.load_default()
        
        # Add newspaper title
        draw.text((width//2-100, 50), "TEST GAZETTE", fill='black', font=font)
        
        # Add a headline
        draw.text((width//2-150, 150), "TEST HEADLINE", fill='black', font=font)
        
        # Add some article text
        article_text = "This is a test article for OCR processing."
        draw.text((50, 250), article_text, fill='black', font=font)
        
        # Add a horizontal line to simulate column division
        draw.line([(50, 350), (width-50, 350)], fill='black', width=2)
        
        # Add some more text
        draw.text((50, 400), "More test content goes here.", fill='black', font=font)
        
        return image
    
    def _create_sample_hocr(self):
        """Create a sample HOCR file for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
  <head>
    <title>OCR Output</title>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
    <meta name='ocr-system' content='tesseract' />
  </head>
  <body>
    <div class='ocr_page' id='page_1' title='image "test_page.jpg"; bbox 0 0 800 1200; ppageno 0'>
      <div class='ocr_carea' id='block_1_1' title="bbox 300 50 500 100">
        <p class='ocr_par' id='par_1_1'>
          <span class='ocr_line' id='line_1_1' title="bbox 300 50 500 80">
            <span class='ocrx_word' id='word_1_1' title="bbox 300 50 400 80">TEST</span>
            <span class='ocrx_word' id='word_1_2' title="bbox 410 50 500 80">GAZETTE</span>
          </span>
        </p>
      </div>
      <div class='ocr_carea' id='block_1_2' title="bbox 250 150 550 180">
        <p class='ocr_par' id='par_1_2'>
          <span class='ocr_line' id='line_1_2' title="bbox 250 150 550 180">
            <span class='ocrx_word' id='word_1_3' title="bbox 250 150 350 180">TEST</span>
            <span class='ocrx_word' id='word_1_4' title="bbox 360 150 550 180">HEADLINE</span>
          </span>
        </p>
      </div>
      <div class='ocr_carea' id='block_1_3' title="bbox 50 250 750 300">
        <p class='ocr_par' id='par_1_3'>
          <span class='ocr_line' id='line_1_3' title="bbox 50 250 750 280">
            <span class='ocrx_word' id='word_1_5' title="bbox 50 250 100 280">This</span>
            <span class='ocrx_word' id='word_1_6' title="bbox 110 250 130 280">is</span>
            <span class='ocrx_word' id='word_1_7' title="bbox 140 250 150 280">a</span>
            <span class='ocrx_word' id='word_1_8' title="bbox 160 250 210 280">test</span>
            <span class='ocrx_word' id='word_1_9' title="bbox 220 250 300 280">article</span>
            <span class='ocrx_word' id='word_1_10' title="bbox 310 250 340 280">for</span>
            <span class='ocrx_word' id='word_1_11' title="bbox 350 250 400 280">OCR</span>
            <span class='ocrx_word' id='word_1_12' title="bbox 410 250 520 280">processing.</span>
          </span>
        </p>
      </div>
      <div class='ocr_carea' id='block_1_4' title="bbox 50 400 550 430">
        <p class='ocr_par' id='par_1_4'>
          <span class='ocr_line' id='line_1_4' title="bbox 50 400 550 430">
            <span class='ocrx_word' id='word_1_13' title="bbox 50 400 100 430">More</span>
            <span class='ocrx_word' id='word_1_14' title="bbox 110 400 150 430">test</span>
            <span class='ocrx_word' id='word_1_15' title="bbox 160 400 240 430">content</span>
            <span class='ocrx_word' id='word_1_16' title="bbox 250 400 300 430">goes</span>
            <span class='ocrx_word' id='word_1_17' title="bbox 310 400 360 430">here.</span>
          </span>
        </p>
      </div>
    </div>
  </body>
</html>"""
    
    @patch('src.newspaper_repository.ocr_processor.OCRProcessor.process_page')
    @patch('src.newspaper_repository.ocr_processor.OCRProcessor.analyze_layout_and_extract_segments')
    def test_full_workflow(self, mock_extract_segments, mock_process_page):
        """Test the full workflow from page import to database promotion."""
        # Mock OCR processing
        mock_process_page.return_value = (self.mock_ocr_text, self.mock_hocr)
        
        # Mock segment extraction
        segment = ArticleSegment(
            text_content="This is a test article for OCR processing.\n\nMore test content goes here.",
            headline="TEST HEADLINE",
            position_data='{"x": 50, "y": 150, "width": 700, "height": 300}',
            image_data=Image.new('RGB', (100, 100))
        )
        mock_extract_segments.return_value = [segment]
        
        # Step 1: Import a newspaper page
        page_id = self.repo_db.add_newspaper_page(
            newspaper_name="Test Gazette",
            publication_date="1900-01-01",
            page_number=1,
            source_id="test_source",
            source_url="https://example.com/test",
            ocr_status="pending"
        )
        
        # Save the page image
        original_path = self.file_manager.save_original_page(
            page_id=page_id,
            newspaper_name="Test Gazette",
            publication_date="1900-01-01",
            page_number=1,
            file_path=self.image_path
        )
        
        # Update page with image path
        self.repo_db.update_page_image_path(page_id, original_path)
        
        # Verify page was added
        page = self.repo_db.get_page_by_id(page_id)
        self.assertEqual(page.newspaper_name, "Test Gazette")
        self.assertEqual(page.ocr_status, "pending")
        
        # Step 2: Process page with OCR
        self.repo_db.update_ocr_status(page_id, "processing")
        
        # Extract text with OCR
        ocr_text, hocr_output = self.ocr_processor.process_page(original_path)
        
        # Save OCR outputs
        ocr_path = self.file_manager.save_ocr_text(
            page_id=page_id,
            newspaper_name="Test Gazette",
            publication_date="1900-01-01",
            page_number=1,
            ocr_text=ocr_text
        )
        
        hocr_path = self.file_manager.save_hocr_output(
            page_id=page_id,
            newspaper_name="Test Gazette",
            publication_date="1900-01-01",
            page_number=1,
            hocr_content=hocr_output
        )
        
        # Update page record with OCR info
        self.repo_db.update_page_ocr_data(page_id, ocr_path, hocr_path)
        
        # Step 3: Extract article segments
        segments = self.ocr_processor.analyze_layout_and_extract_segments(hocr_path, original_path)
        
        # Verify segments were extracted
        self.assertEqual(len(segments), 1)
        
        # Step 4: Save segment
        segment = segments[0]
        segment_id = self.repo_db.add_article_segment(
            page_id=page_id,
            position_data=segment.position_data,
            text_content=segment.text_content,
            headline=segment.headline,
            processing_status="extracted"
        )
        
        # Save segment image
        if segment.image_data:
            segment_img_path = self.file_manager.save_article_segment_image(
                segment_id=segment_id,
                newspaper_name="Test Gazette",
                publication_date="1900-01-01",
                segment_number=0,
                image_data=segment.image_data
            )
            
            # Update segment with image path
            self.repo_db.update_segment_image_path(segment_id, segment_img_path)
        
        # Mark OCR as completed
        self.repo_db.update_ocr_status(page_id, "completed")
        
        # Verify OCR status was updated
        page = self.repo_db.get_page_by_id(page_id)
        self.assertEqual(page.ocr_status, "completed")
        
        # Verify segment was saved
        db_segment = self.repo_db.get_segment_by_id(segment_id)
        self.assertEqual(db_segment.headline, "TEST HEADLINE")
        self.assertIn("This is a test article", db_segment.text_content)
        
        # Step 5: Import to main database
        # First create a source in main DB
        cursor = self.main_db_conn.cursor()
        cursor.execute("""
            INSERT INTO Sources (SourceName, SourceType, ReviewStatus)
            VALUES (?, ?, ?)
        """, ("Test Gazette", "Newspaper", "imported"))
        source_id = cursor.lastrowid
        self.main_db_conn.commit()
        
        # Import segment to main DB
        event_id = self.connector.import_segment_as_event(
            segment_id,
            "TEST HEADLINE",
            "1900-01-01",
            db_segment.text_content,
            str(source_id)
        )
        
        # Verify event was created
        self.assertIsNotNone(event_id)
        
        # Verify segment status was updated
        db_segment = self.repo_db.get_segment_by_id(segment_id)
        self.assertEqual(db_segment.processing_status, "imported")
        self.assertEqual(db_segment.linked_event_id, event_id)
        
        # Verify event in main database
        cursor.execute("SELECT * FROM Events WHERE EventID = ?", (event_id,))
        event = cursor.fetchone()
        
        self.assertEqual(event["EventTitle"], "TEST HEADLINE")
        self.assertEqual(event["EventDate"], "1900-01-01")
        self.assertIn("This is a test article", event["EventText"])

if __name__ == '__main__':
    unittest.main()