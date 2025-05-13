#!/usr/bin/env python3
"""
Newspaper Structure Analyzer

This module analyzes newspaper pages to identify their structural components
(columns, paragraphs, headlines, etc.) before applying OCR. This approach
improves OCR accuracy by processing each element separately and maintains
the structural relationships for proper reassembly.

Key components:
1. Page preprocessing (binarization, deskewing, noise removal)
2. Column detection
3. Element classification (headlines, paragraphs, images, etc.)
4. Element relationship mapping
5. Database storage of structural elements
"""

import os
import sys
import cv2
import numpy as np
import logging
import sqlite3
import pytesseract
from PIL import Image
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NewspaperStructureAnalyzer:
    """
    Class for analyzing and decomposing newspaper page structure.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the structure analyzer.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn = None
        self.create_connection()
        
        # Check Tesseract installation
        try:
            tesseract_version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {tesseract_version}")
        except Exception as e:
            logger.error(f"Tesseract not properly installed or configured: {e}")
            logger.error("Please make sure Tesseract OCR is installed and in your PATH")
            sys.exit(1)
    
    def create_connection(self):
        """Create a database connection to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            sys.exit(1)
    
    def process_page(self, page_id: int, image_path: str) -> bool:
        """
        Process a newspaper page to identify its structural elements.
        
        Args:
            page_id: ID of the page in the NewspaperPages table
            image_path: Path to the page image file
            
        Returns:
            True if processing was successful, False otherwise
        """
        logger.info(f"Processing page {page_id} from {image_path}")
        
        # Check if page exists
        if not self._verify_page_exists(page_id):
            logger.error(f"Page ID {page_id} not found in database")
            return False
        
        # Check if image file exists
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
        
        try:
            # Load and preprocess the image
            img, binary_img = self._preprocess_image(image_path)
            if img is None or binary_img is None:
                logger.error("Failed to preprocess image")
                return False
            
            # Get image dimensions
            height, width = img.shape[:2]
            logger.info(f"Image dimensions: {width}x{height}")
            
            # Detect columns
            columns = self._detect_columns(binary_img)
            logger.info(f"Detected {len(columns)} columns")
            
            # Clear any existing elements for this page
            self._clear_existing_elements(page_id)
            
            # Store columns in database
            column_ids = []
            for i, column in enumerate(columns):
                column_id = self._store_page_element(
                    page_id=page_id,
                    element_type="COLUMN",
                    element_identifier=f"COL_{chr(65+i)}",  # A, B, C, etc.
                    sequence_order=i+1,
                    x1=column[0],
                    y1=column[1],
                    x2=column[2],
                    y2=column[3]
                )
                column_ids.append(column_id)
                
                # Process elements within this column
                self._process_column_elements(binary_img, page_id, column_id, column)
            
            # Analyze relationships between elements
            self._analyze_element_relationships(page_id)
            
            logger.info(f"Completed structural analysis for page {page_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing page {page_id}: {e}", exc_info=True)
            return False
    
    def process_batch(self, batch: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Process a batch of pages.
        
        Args:
            batch: List of dictionaries with page_id and image_path
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        successful = 0
        failed = 0
        
        for item in batch:
            page_id = item.get('page_id')
            image_path = item.get('image_path')
            
            if page_id is None or image_path is None:
                logger.error("Missing page_id or image_path in batch item")
                failed += 1
                continue
            
            success = self.process_page(page_id, image_path)
            if success:
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Batch processing completed: {successful} successful, {failed} failed")
        return successful, failed
    
    def _verify_page_exists(self, page_id: int) -> bool:
        """Check if a page exists in the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT PageID FROM NewspaperPages WHERE PageID = ?", (page_id,))
        return cursor.fetchone() is not None
    
    def _clear_existing_elements(self, page_id: int):
        """Clear any existing elements for this page."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM PageElements WHERE PageID = ?", (page_id,))
        self.conn.commit()
        logger.info(f"Cleared existing elements for page {page_id}")
    
    def _store_page_element(self, page_id: int, element_type: str, element_identifier: str,
                          sequence_order: int, x1: int, y1: int, x2: int, y2: int,
                          parent_id: Optional[int] = None) -> int:
        """Store a page element in the database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO PageElements (
                PageID, ElementType, ElementIdentifier, SequenceOrder,
                ParentElementID, X1, Y1, X2, Y2, ProcessingStatus
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (page_id, element_type, element_identifier, sequence_order,
              parent_id, x1, y1, x2, y2, 'pending'))
        self.conn.commit()
        return cursor.lastrowid
    
    def _preprocess_image(self, image_path: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Preprocess the image for better structure detection.
        
        Returns:
            Tuple of (original_image, binary_image)
        """
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to read image: {image_path}")
                return None, None
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply deskewing if needed
            # gray = self._deskew(gray)
            
            # Apply noise reduction
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            
            # Apply adaptive thresholding for binarization
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Morphological operations to enhance text regions
            kernel = np.ones((3, 3), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            return img, binary
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return None, None
    
    def _detect_columns(self, binary_img: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect columns in the newspaper page.
        
        Returns:
            List of column coordinates (x1, y1, x2, y2)
        """
        height, width = binary_img.shape
        
        # Project the binary image onto the horizontal axis
        h_projection = np.sum(binary_img, axis=0) / height
        
        # Smooth the projection
        h_projection = np.convolve(h_projection, np.ones(20)/20, mode='same')
        
        # Find potential column separators (vertical whitespace)
        threshold = 0.05  # Threshold for whitespace
        separators = []
        in_separator = False
        
        for x in range(width):
            if h_projection[x] < threshold:
                if not in_separator:
                    in_separator = True
                    separator_start = x
            else:
                if in_separator:
                    in_separator = False
                    separator_end = x
                    if separator_end - separator_start > 10:  # Minimum separator width
                        separators.append((separator_start, separator_end))
        
        # If no separators found, treat as single column
        if not separators:
            return [(0, 0, width, height)]
        
        # Create columns from separators
        columns = []
        prev_end = 0
        
        for sep_start, sep_end in separators:
            if sep_start > prev_end + 10:  # Minimum column width
                columns.append((prev_end, 0, sep_start, height))
            prev_end = sep_end
        
        # Add last column if needed
        if prev_end < width - 10:
            columns.append((prev_end, 0, width, height))
        
        return columns
    
    def _process_column_elements(self, binary_img: np.ndarray, page_id: int, 
                               column_id: int, column: Tuple[int, int, int, int]):
        """
        Process elements within a column (paragraphs, headlines, etc.).
        
        Args:
            binary_img: Preprocessed binary image
            page_id: ID of the page
            column_id: ID of the parent column element
            column: Column coordinates (x1, y1, x2, y2)
        """
        # Extract column region
        x1, y1, x2, y2 = column
        column_img = binary_img[y1:y2, x1:x2]
        
        # Find horizontal whitespace to separate elements
        v_projection = np.sum(column_img, axis=1) / (x2 - x1)
        
        # Smooth the projection
        v_projection = np.convolve(v_projection, np.ones(10)/10, mode='same')
        
        # Find potential element separators
        threshold = 0.05  # Threshold for whitespace
        element_bounds = []
        in_element = False
        element_start = 0
        
        for y in range(len(v_projection)):
            if v_projection[y] > threshold:
                if not in_element:
                    in_element = True
                    element_start = y
            else:
                if in_element:
                    in_element = False
                    element_end = y
                    if element_end - element_start > 15:  # Minimum element height
                        element_bounds.append((element_start, element_end))
        
        # Add last element if needed
        if in_element and len(v_projection) - element_start > 15:
            element_bounds.append((element_start, len(v_projection)))
        
        # Store elements
        for i, (elem_y1, elem_y2) in enumerate(element_bounds):
            # Determine element type (simplified for now)
            elem_type = "PARAGRAPH"
            if i == 0 and elem_y2 - elem_y1 < 60:  # Simplified headline detection
                elem_type = "HEADLINE"
            elif i == 1 and elem_y2 - elem_y1 < 40 and i > 0:  # Simplified subheadline detection
                elem_type = "SUBHEADLINE"
            
            # Absolute coordinates in original image
            abs_y1 = y1 + elem_y1
            abs_y2 = y1 + elem_y2
            
            element_id = self._store_page_element(
                page_id=page_id,
                element_type=elem_type,
                element_identifier=f"{chr(65 + columns.index(column))}{i+1}",  # A1, A2, B1, etc.
                sequence_order=i+1,
                parent_id=column_id,
                x1=x1,
                y1=abs_y1,
                x2=x2,
                y2=abs_y2
            )
    
    def _analyze_element_relationships(self, page_id: int):
        """
        Analyze relationships between elements within a page.
        
        This includes identifying article continuations, related headlines, etc.
        """
        # This is a placeholder for more sophisticated relationship analysis
        # For now, we'll assume elements in sequence within the same column are related
        cursor = self.conn.cursor()
        
        # Get all elements for this page, ordered by column (parent) and sequence
        cursor.execute("""
            SELECT ElementID, ParentElementID, ElementType, SequenceOrder
            FROM PageElements
            WHERE PageID = ?
            ORDER BY ParentElementID, SequenceOrder
        """, (page_id,))
        
        elements = cursor.fetchall()
        
        # Group elements by parent (column)
        element_groups = {}
        for element_id, parent_id, element_type, seq_order in elements:
            if parent_id not in element_groups:
                element_groups[parent_id] = []
            element_groups[parent_id].append((element_id, element_type, seq_order))
        
        # Process each column's elements
        for parent_id, column_elements in element_groups.items():
            current_article_elements = []
            
            for element_id, element_type, seq_order in column_elements:
                # If we encounter a headline, it may signal the start of a new article
                if element_type == "HEADLINE" and current_article_elements:
                    # Create an article entry for the previous elements
                    article_id = self._create_article(page_id, current_article_elements)
                    
                    # Start a new article
                    current_article_elements = [(element_id, element_type)]
                else:
                    current_article_elements.append((element_id, element_type))
            
            # Create an article for the remaining elements
            if current_article_elements:
                article_id = self._create_article(page_id, current_article_elements)
    
    def _create_article(self, page_id: int, elements: List[Tuple[int, str]]) -> int:
        """
        Create an article from a list of related elements.
        
        Args:
            page_id: ID of the page
            elements: List of element IDs and types that make up the article
            
        Returns:
            Article ID
        """
        cursor = self.conn.cursor()
        
        # Get source ID for this page
        cursor.execute("SELECT SourceID FROM NewspaperPages WHERE PageID = ?", (page_id,))
        source_id = cursor.fetchone()[0]
        
        # Create a new article
        cursor.execute("""
            INSERT INTO Articles (SourceID, ProcessingStatus)
            VALUES (?, ?)
        """, (source_id, 'pending'))
        
        article_id = cursor.lastrowid
        
        # Update article ID for all elements
        element_ids = [elem_id for elem_id, _ in elements]
        placeholders = ','.join('?' for _ in element_ids)
        cursor.execute(f"""
            UPDATE PageElements 
            SET ArticleID = ? 
            WHERE ElementID IN ({placeholders})
        """, [article_id] + element_ids)
        
        self.conn.commit()
        return article_id

def main():
    """Main entry point for the script."""
    if len(sys.argv) < 3:
        print("Usage: python newspaper_structure_analyzer.py <db_path> <image_path> [page_id]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    image_path = sys.argv[2]
    
    # If page_id is not provided, try to derive it from the filename
    if len(sys.argv) > 3:
        page_id = int(sys.argv[3])
    else:
        # Try to extract page ID from filename
        try:
            filename = os.path.basename(image_path)
            # Assume format like "sn83045604_18920417_seq1.jp2"
            if "_seq" in filename:
                lccn = filename.split("_")[0]
                date = filename.split("_")[1]
                sequence = int(filename.split("_seq")[1].split(".")[0])
                
                analyzer = NewspaperStructureAnalyzer(db_path)
                cursor = analyzer.conn.cursor()
                cursor.execute("""
                    SELECT PageID FROM NewspaperPages 
                    WHERE LCCN = ? AND IssueDate = ? AND Sequence = ?
                """, (lccn, f"{date[:4]}-{date[4:6]}-{date[6:8]}", sequence))
                
                result = cursor.fetchone()
                if result:
                    page_id = result[0]
                else:
                    print(f"Could not find page for {filename} in database")
                    sys.exit(1)
            else:
                print("Could not derive page_id from filename. Please provide page_id as argument.")
                sys.exit(1)
        except Exception as e:
            print(f"Error deriving page_id from filename: {e}")
            print("Please provide page_id as argument.")
            sys.exit(1)
    
    # Process the page
    analyzer = NewspaperStructureAnalyzer(db_path)
    success = analyzer.process_page(page_id, image_path)
    
    if success:
        print(f"Successfully processed page {page_id}")
        sys.exit(0)
    else:
        print(f"Failed to process page {page_id}")
        sys.exit(1)

if __name__ == "__main__":
    main()