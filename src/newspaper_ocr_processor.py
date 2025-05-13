#!/usr/bin/env python3
"""
Newspaper OCR Processor

This module performs OCR on the structural elements of newspaper pages
that have been previously identified by the NewspaperStructureAnalyzer.
It processes each element individually to improve OCR accuracy and 
maintains the structural relationships for proper reassembly.

Key features:
1. Element-specific OCR processing
2. OCR parameter optimization based on element type
3. Storage of OCR results in the database
4. Article text assembly from individual elements
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

class NewspaperOcrProcessor:
    """
    Class for OCR processing of newspaper page elements.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the OCR processor.
        
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
    
    def process_page_elements(self, page_id: int, image_path: str) -> bool:
        """
        Process OCR for all elements of a newspaper page.
        
        Args:
            page_id: ID of the page in the NewspaperPages table
            image_path: Path to the page image file
            
        Returns:
            True if processing was successful, False otherwise
        """
        logger.info(f"Processing OCR for page {page_id} from {image_path}")
        
        # Check if page exists
        if not self._verify_page_exists(page_id):
            logger.error(f"Page ID {page_id} not found in database")
            return False
        
        # Check if image file exists
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
        
        try:
            # Load the image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to read image: {image_path}")
                return False
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Get all elements for this page that need OCR
            elements = self._get_page_elements(page_id)
            if not elements:
                logger.info(f"No elements found for page {page_id} or all elements already processed")
                return True
            
            logger.info(f"Found {len(elements)} elements to process")
            
            # Process each element
            successful = 0
            for element in elements:
                element_id = element[0]
                element_type = element[1]
                x1, y1, x2, y2 = element[2:6]
                
                # Extract element region
                element_img = gray[y1:y2, x1:x2]
                
                # Skip elements that are too small
                if element_img.shape[0] < 10 or element_img.shape[1] < 10:
                    logger.warning(f"Element {element_id} is too small, skipping")
                    continue
                
                # Perform OCR with parameters optimized for this element type
                ocr_text, confidence = self._perform_ocr(element_img, element_type)
                
                # Store OCR results
                if ocr_text:
                    self._update_element_ocr(element_id, ocr_text, confidence)
                    successful += 1
            
            # Update article text if all elements are processed
            self._assemble_article_text(page_id)
            
            logger.info(f"OCR processing completed for page {page_id}: {successful}/{len(elements)} elements successful")
            return True
            
        except Exception as e:
            logger.error(f"Error processing OCR for page {page_id}: {e}", exc_info=True)
            return False
    
    def process_batch(self, batch: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Process OCR for a batch of pages.
        
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
            
            success = self.process_page_elements(page_id, image_path)
            if success:
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Batch OCR processing completed: {successful} successful, {failed} failed")
        return successful, failed
    
    def _verify_page_exists(self, page_id: int) -> bool:
        """Check if a page exists in the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT PageID FROM NewspaperPages WHERE PageID = ?", (page_id,))
        return cursor.fetchone() is not None
    
    def _get_page_elements(self, page_id: int) -> List[Tuple]:
        """Get all elements for a page that need OCR processing."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT ElementID, ElementType, X1, Y1, X2, Y2
            FROM PageElements
            WHERE PageID = ? AND ProcessingStatus = 'pending'
            AND ElementType != 'COLUMN'  # Skip column elements
            ORDER BY SequenceOrder
        """, (page_id,))
        return cursor.fetchall()
    
    def _perform_ocr(self, element_img: np.ndarray, element_type: str) -> Tuple[str, float]:
        """
        Perform OCR on an element image with optimized parameters.
        
        Args:
            element_img: Image of the element
            element_type: Type of element (affects OCR parameters)
            
        Returns:
            Tuple of (ocr_text, confidence)
        """
        # Apply preprocessing based on element type
        preprocessed = self._preprocess_for_ocr(element_img, element_type)
        
        # Convert to PIL Image for Tesseract
        pil_img = Image.fromarray(preprocessed)
        
        # Set Tesseract configuration based on element type
        config = self._get_tesseract_config(element_type)
        
        # Perform OCR
        try:
            ocr_data = pytesseract.image_to_data(pil_img, config=config, output_type=pytesseract.Output.DICT)
            
            # Extract text and confidence
            text_parts = []
            confidences = []
            
            for i in range(len(ocr_data['text'])):
                if int(ocr_data['conf'][i]) > 0:  # Skip low confidence or empty results
                    text = ocr_data['text'][i].strip()
                    if text:
                        text_parts.append(text)
                        confidences.append(float(ocr_data['conf'][i]))
            
            if not text_parts:
                return "", 0.0
            
            # Join text parts with appropriate spacing
            ocr_text = ' '.join(text_parts)
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return ocr_text, avg_confidence
            
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return "", 0.0
    
    def _preprocess_for_ocr(self, img: np.ndarray, element_type: str) -> np.ndarray:
        """
        Preprocess an element image for optimal OCR results based on element type.
        
        Args:
            img: Image of the element
            element_type: Type of element
            
        Returns:
            Preprocessed image
        """
        # Apply different preprocessing based on element type
        if element_type in ["HEADLINE", "SUBHEADLINE"]:
            # For headlines, use stronger noise removal
            denoised = cv2.fastNlMeansDenoising(img, None, 15, 7, 21)
            
            # Increase contrast
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # Adaptive thresholding
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 15, 8
            )
            
            return binary
            
        elif element_type == "PARAGRAPH":
            # For paragraphs, more subtle preprocessing
            denoised = cv2.fastNlMeansDenoising(img, None, 10, 7, 21)
            
            # Moderate contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # Adaptive thresholding
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 5
            )
            
            return binary
            
        else:
            # For other types, basic preprocessing
            denoised = cv2.fastNlMeansDenoising(img, None, 10, 7, 21)
            
            # Adaptive thresholding
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            return binary
    
    def _get_tesseract_config(self, element_type: str) -> str:
        """
        Get Tesseract configuration based on element type.
        
        Args:
            element_type: Type of element
            
        Returns:
            Tesseract configuration string
        """
        # Base configuration for historical newspapers
        base_config = "--oem 1 --psm 6 -l eng"
        
        if element_type in ["HEADLINE", "SUBHEADLINE"]:
            # For headlines, use single line recognition
            return "--oem 1 --psm 7 -l eng"
            
        elif element_type == "PARAGRAPH":
            # For paragraphs, use block of text recognition
            return "--oem 1 --psm 6 -l eng"
            
        elif element_type == "CAPTION":
            # For captions, similar to paragraphs but with single line option
            return "--oem 1 --psm 6 -l eng"
            
        return base_config
    
    def _update_element_ocr(self, element_id: int, ocr_text: str, confidence: float):
        """
        Update element with OCR results.
        
        Args:
            element_id: ID of the element
            ocr_text: Extracted OCR text
            confidence: OCR confidence score
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE PageElements
            SET OCRText = ?, OCRConfidence = ?, ProcessingStatus = 'ocr_complete'
            WHERE ElementID = ?
        """, (ocr_text, confidence, element_id))
        self.conn.commit()
    
    def _assemble_article_text(self, page_id: int):
        """
        Assemble full article text from processed elements.
        
        Args:
            page_id: ID of the page
        """
        cursor = self.conn.cursor()
        
        # Get all articles associated with this page
        cursor.execute("""
            SELECT DISTINCT ArticleID
            FROM PageElements
            WHERE PageID = ? AND ArticleID IS NOT NULL
        """, (page_id,))
        
        article_ids = [row[0] for row in cursor.fetchall()]
        
        for article_id in article_ids:
            # Check if all elements for this article have been OCR processed
            cursor.execute("""
                SELECT COUNT(*)
                FROM PageElements
                WHERE ArticleID = ? AND ProcessingStatus != 'ocr_complete'
            """, (article_id,))
            
            pending_count = cursor.fetchone()[0]
            
            if pending_count == 0:
                # All elements have been processed, assemble the article text
                cursor.execute("""
                    SELECT ElementID, ElementType, OCRText, SequenceOrder
                    FROM PageElements
                    WHERE ArticleID = ? AND OCRText IS NOT NULL
                    ORDER BY SequenceOrder
                """, (article_id,))
                
                elements = cursor.fetchall()
                
                # Assemble text with appropriate formatting
                article_text = []
                article_title = None
                
                for element_id, element_type, ocr_text, sequence in elements:
                    if element_type == "HEADLINE":
                        article_title = ocr_text
                        article_text.append(f"{ocr_text}\n\n")
                    elif element_type == "SUBHEADLINE":
                        article_text.append(f"{ocr_text}\n\n")
                    elif element_type == "PARAGRAPH":
                        article_text.append(f"{ocr_text}\n\n")
                    elif element_type == "CAPTION":
                        article_text.append(f"[Caption: {ocr_text}]\n\n")
                    else:
                        article_text.append(f"{ocr_text}\n\n")
                
                full_text = ''.join(article_text).strip()
                
                # Update the article with assembled text
                cursor.execute("""
                    UPDATE Articles
                    SET FullText = ?, ArticleTitle = ?, ProcessingStatus = 'assembled'
                    WHERE ArticleID = ?
                """, (full_text, article_title, article_id))
                
                self.conn.commit()
                logger.info(f"Assembled text for article {article_id}")

def main():
    """Main entry point for the script."""
    if len(sys.argv) < 3:
        print("Usage: python newspaper_ocr_processor.py <db_path> <image_path> [page_id]")
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
                
                processor = NewspaperOcrProcessor(db_path)
                cursor = processor.conn.cursor()
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
    processor = NewspaperOcrProcessor(db_path)
    success = processor.process_page_elements(page_id, image_path)
    
    if success:
        print(f"Successfully processed OCR for page {page_id}")
        sys.exit(0)
    else:
        print(f"Failed to process OCR for page {page_id}")
        sys.exit(1)

if __name__ == "__main__":
    main()