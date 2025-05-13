# File: ocr_processor.py

import os
import cv2
import numpy as np
import pytesseract
import tempfile
from PIL import Image, ImageEnhance, ImageFilter
import re
import json
from typing import List, Dict, Tuple, Optional, Any, Union
import logging
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCRProcessor')

@dataclass
class ArticleSegment:
    """Class for storing information about an article segment."""
    id: Optional[int]  # Database ID if available
    headline: Optional[str]
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    image_path: Optional[str] = None
    

class OCRProcessor:
    """
    Processes newspaper pages with OCR to extract text and article segments.
    
    Handles:
    - Full page OCR processing
    - HOCR generation with position data
    - Article segmentation
    - Image clip extraction
    """
    
    # Default OCR settings
    DEFAULT_OCR_CONFIG = r'--oem 3 --psm 3'
    DEFAULT_HOCR_CONFIG = r'--oem 3 --psm 3 hocr'
    
    # Article detection settings
    MIN_ARTICLE_HEIGHT = 300  # Minimum height for article bounding box
    MIN_ARTICLE_WIDTH = 300   # Minimum width for article bounding box
    MIN_TEXT_DENSITY = 0.02   # Minimum text density (ratio of text to area)
    
    def __init__(self, db_manager=None, file_manager=None):
        """
        Initialize the OCR processor.
        
        Args:
            db_manager: Repository database manager instance
            file_manager: File manager instance
        """
        self.db_manager = db_manager
        self.file_manager = file_manager
        
        # Verify Tesseract is available
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.error(f"Tesseract is not installed or not in PATH: {e}")
            raise RuntimeError("Tesseract OCR is not available")
    
    def preprocess_image(self, image_path: str, enhance: bool = True) -> np.ndarray:
        """
        Preprocess an image to improve OCR results.
        
        Args:
            image_path: Path to the image file
            enhance: Whether to enhance the image
            
        Returns:
            Preprocessed image as a numpy array
        """
        # Check file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
            
        try:
            # Load image
            img = Image.open(image_path)
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Apply image enhancements if requested
            if enhance:
                # Increase contrast
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
                
                # Increase sharpness
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(1.5)
                
                # Apply a slight blur to reduce noise
                img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3))
            
            # Convert PIL image to CV2 format (numpy array)
            img_array = np.array(img)
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            return img_array
            
        except Exception as e:
            logger.error(f"Error preprocessing image {image_path}: {e}")
            raise
    
    def process_page_ocr(self, image_path: str, config: Optional[str] = None) -> Tuple[str, float]:
        """
        Process a newspaper page with OCR to extract text.
        
        Args:
            image_path: Path to the image file
            config: Tesseract configuration string
            
        Returns:
            Tuple of (extracted text, confidence)
        """
        try:
            # Preprocess the image
            img_array = self.preprocess_image(image_path)
            
            # Convert to grayscale for OCR
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            
            # Use default config if none provided
            ocr_config = config or self.DEFAULT_OCR_CONFIG
            
            # Run OCR using Tesseract
            ocr_data = pytesseract.image_to_data(
                gray, 
                config=ocr_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence for non-empty text
            confidences = [conf for i, conf in enumerate(ocr_data['conf']) 
                          if conf != -1 and ocr_data['text'][i].strip()]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Get the full text
            text = pytesseract.image_to_string(gray, config=ocr_config)
            
            # Clean up the text
            text = self._clean_ocr_text(text)
            
            return text, avg_confidence
            
        except Exception as e:
            logger.error(f"Error processing OCR for {image_path}: {e}")
            raise
    
    def generate_hocr(self, image_path: str, config: Optional[str] = None) -> str:
        """
        Generate HOCR output with position information.
        
        Args:
            image_path: Path to the image file
            config: Tesseract configuration string
            
        Returns:
            HOCR output string
        """
        try:
            # Preprocess the image
            img_array = self.preprocess_image(image_path)
            
            # Convert to grayscale for OCR
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            
            # Use default HOCR config if none provided
            hocr_config = config or self.DEFAULT_HOCR_CONFIG
            
            # Generate HOCR
            hocr_output = pytesseract.image_to_pdf_or_hocr(
                gray,
                extension='hocr',
                config=hocr_config
            )
            
            # Convert bytes to string
            hocr_text = hocr_output.decode('utf-8')
            
            return hocr_text
            
        except Exception as e:
            logger.error(f"Error generating HOCR for {image_path}: {e}")
            raise
    
    def analyze_page_layout(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Analyze page layout to identify potential article regions.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            List of dictionaries containing region information
        """
        try:
            # Preprocess the image
            img_array = self.preprocess_image(image_path)
            original_height, original_width = img_array.shape[:2]
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            
            # Apply thresholding
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find contours
            contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Find potential article regions by looking for large contours
            regions = []
            for i, contour in enumerate(contours):
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by size
                if (w > self.MIN_ARTICLE_WIDTH and h > self.MIN_ARTICLE_HEIGHT and
                    w < original_width * 0.9 and h < original_height * 0.9):
                    
                    # Calculate contour area and density
                    area = cv2.contourArea(contour)
                    rect_area = w * h
                    density = area / rect_area if rect_area > 0 else 0
                    
                    # Only keep regions with reasonable density
                    if density > self.MIN_TEXT_DENSITY:
                        regions.append({
                            'id': i,
                            'bbox': (x, y, w, h),
                            'area': area,
                            'density': density
                        })
            
            # Sort regions by y-coordinate (top to bottom)
            regions.sort(key=lambda r: r['bbox'][1])
            
            return regions
            
        except Exception as e:
            logger.error(f"Error analyzing page layout for {image_path}: {e}")
            raise
    
    def identify_article_segments(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Identify article segments on a page using a combination of layout and OCR.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            List of dictionaries containing article segment information
        """
        try:
            # Get page regions from layout analysis
            regions = self.analyze_page_layout(image_path)
            
            # Generate HOCR for the whole page
            hocr_text = self.generate_hocr(image_path)
            
            # Parse HOCR to extract text blocks
            hocr_blocks = self._parse_hocr_blocks(hocr_text)
            
            # Match regions with text blocks
            article_segments = []
            
            # Get image dimensions
            img = Image.open(image_path)
            img_width, img_height = img.size
            
            for region in regions:
                region_bbox = region['bbox']
                rx, ry, rw, rh = region_bbox
                
                # Find text blocks that overlap with this region
                region_blocks = []
                for block in hocr_blocks:
                    block_bbox = block['bbox']
                    bx, by, bw, bh = block_bbox
                    
                    # Check for overlap
                    overlap = (
                        rx < bx + bw and
                        rx + rw > bx and
                        ry < by + bh and
                        ry + rh > by
                    )
                    
                    if overlap:
                        region_blocks.append(block)
                
                # If we found text blocks in this region
                if region_blocks:
                    # Sort blocks by y-coordinate
                    region_blocks.sort(key=lambda b: b['bbox'][1])
                    
                    # First block might be a headline
                    headline = region_blocks[0]['text'] if len(region_blocks) > 1 else None
                    
                    # Combine all block text for the article
                    article_text = "\n\n".join(block['text'] for block in region_blocks)
                    
                    # Calculate average confidence
                    total_conf = sum(block['confidence'] for block in region_blocks)
                    avg_conf = total_conf / len(region_blocks) if region_blocks else 0
                    
                    # Add to article segments
                    article_segments.append({
                        'headline': headline,
                        'text': article_text,
                        'confidence': avg_conf,
                        'bbox': region_bbox,
                        'blocks': region_blocks,
                        'normalized_bbox': (
                            rx / img_width,
                            ry / img_height,
                            rw / img_width,
                            rh / img_height
                        )
                    })
            
            return article_segments
            
        except Exception as e:
            logger.error(f"Error identifying article segments for {image_path}: {e}")
            raise
    
    def extract_article_images(self, image_path: str, 
                             article_segments: List[Dict[str, Any]], 
                             output_dir: str) -> List[Dict[str, Any]]:
        """
        Extract image clips of identified article segments.
        
        Args:
            image_path: Path to the image file
            article_segments: List of article segment dictionaries
            output_dir: Directory to save the extracted images
            
        Returns:
            Updated list of article segments with image paths
        """
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Load the image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")
                
            # Process each article segment
            updated_segments = []
            for i, segment in enumerate(article_segments):
                # Get bounding box
                x, y, w, h = segment['bbox']
                
                # Add some margin (5% on each side)
                margin_x = int(w * 0.05)
                margin_y = int(h * 0.05)
                
                # Calculate new coordinates with margin
                x1 = max(0, x - margin_x)
                y1 = max(0, y - margin_y)
                x2 = min(img.shape[1], x + w + margin_x)
                y2 = min(img.shape[0], y + h + margin_y)
                
                # Extract the article image
                article_img = img[y1:y2, x1:x2]
                
                # Generate output filename
                output_filename = f"article_{i+1}.jpg"
                output_path = os.path.join(output_dir, output_filename)
                
                # Save the image
                cv2.imwrite(output_path, article_img)
                
                # Update segment with image path
                segment_copy = segment.copy()
                segment_copy['image_path'] = output_path
                
                # Update the bbox to account for margins
                segment_copy['bbox'] = (x1, y1, x2-x1, y2-y1)
                
                updated_segments.append(segment_copy)
            
            return updated_segments
            
        except Exception as e:
            logger.error(f"Error extracting article images from {image_path}: {e}")
            raise
    
    def process_page(self, image_path: str, page_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Process a newspaper page with full OCR and article segmentation.
        
        Args:
            image_path: Path to the image file
            page_id: Database ID of the page (if available)
            
        Returns:
            Dictionary with OCR results and article segments
        """
        try:
            # Create temp directory for article images
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract plain text with OCR
                text, confidence = self.process_page_ocr(image_path)
                
                # Generate HOCR output
                hocr_text = self.generate_hocr(image_path)
                
                # Identify article segments
                article_segments = self.identify_article_segments(image_path)
                
                # Extract article images
                article_segments = self.extract_article_images(
                    image_path, article_segments, temp_dir
                )
                
                # Convert to ArticleSegment objects
                segments = []
                for i, segment in enumerate(article_segments):
                    article = ArticleSegment(
                        id=None,  # Will be set when saved to database
                        headline=segment.get('headline'),
                        text=segment.get('text', ''),
                        confidence=segment.get('confidence', 0),
                        bbox=segment.get('bbox'),
                        image_path=segment.get('image_path')
                    )
                    segments.append(article)
                
                # Save results if database and file managers are available
                if page_id and self.db_manager and self.file_manager:
                    self._save_page_results(page_id, text, hocr_text, segments)
                
                # Return the results
                return {
                    'text': text,
                    'confidence': confidence,
                    'hocr': hocr_text,
                    'article_segments': segments,
                    'page_id': page_id
                }
                
        except Exception as e:
            logger.error(f"Error processing page {image_path}: {e}")
            raise
    
    def _save_page_results(self, page_id: int, text: str, hocr: str, 
                         segments: List[ArticleSegment]) -> None:
        """
        Save page processing results to database and files.
        
        Args:
            page_id: Database ID of the page
            text: Extracted OCR text
            hocr: HOCR output
            segments: List of ArticleSegment objects
        """
        try:
            # Get page info from database
            page_info = self.db_manager.get_newspaper_page(page_id)
            if not page_info:
                logger.warning(f"Page {page_id} not found in database")
                return
                
            # Save OCR text file
            text_path = self.file_manager.save_ocr_text(text, page_id)
            
            # Save HOCR file
            hocr_path = self.file_manager.save_hocr_content(hocr, page_id)
            
            # Update page OCR status in database
            self.db_manager.update_page_ocr_status(page_id, ocr_status=1)
            
            # Process each article segment
            for segment in segments:
                # Convert bounding box to position data
                position_data = {
                    'x': segment.bbox[0],
                    'y': segment.bbox[1],
                    'width': segment.bbox[2],
                    'height': segment.bbox[3]
                }
                
                # Save article segment to database
                segment_id = self.db_manager.add_article_segment(
                    page_id=page_id,
                    article_text=segment.text,
                    headline=segment.headline,
                    position_data=position_data
                )
                
                if not segment_id:
                    logger.warning(f"Failed to save article segment for page {page_id}")
                    continue
                
                # Update segment ID
                segment.id = segment_id
                
                # Save article image clip if available
                if segment.image_path and os.path.exists(segment.image_path):
                    clip_path = self.file_manager.save_article_clip(
                        segment.image_path,
                        page_id,
                        segment_id,
                        page_info['source_name'],
                        page_info['publication_date']
                    )
                    
                    # Update image path in database if saved successfully
                    if clip_path:
                        self.db_manager.cursor.execute("""
                            UPDATE article_segments
                            SET image_clip_path = ?
                            WHERE segment_id = ?
                        """, (clip_path, segment_id))
                        self.db_manager.conn.commit()
                
                # Save segment OCR text
                self.file_manager.save_ocr_text(segment.text, page_id, segment_id)
                
        except Exception as e:
            logger.error(f"Error saving page results for page {page_id}: {e}")
            raise
    
    def process_queue_item(self, queue_item: Dict[str, Any]) -> bool:
        """
        Process an item from the processing queue.
        
        Args:
            queue_item: Queue item dictionary with file_path and queue_id
            
        Returns:
            True if processing was successful, False otherwise
        """
        if not self.db_manager or not self.file_manager:
            logger.error("Cannot process queue item: database or file manager not available")
            return False
            
        queue_id = queue_item.get('queue_id')
        file_path = queue_item.get('file_path')
        
        if not queue_id or not file_path:
            logger.error("Invalid queue item: missing queue_id or file_path")
            return False
            
        try:
            # Mark as processing
            self.db_manager.update_queue_status(queue_id, "processing")
            
            # Extract filename and path components
            filename = os.path.basename(file_path)
            
            # Parse filename to extract metadata
            # Format: [SOURCE]_[DATE]_[PAGENUMBER].[EXT]
            parts = os.path.splitext(filename)[0].split('_')
            if len(parts) < 3:
                raise ValueError(f"Invalid filename format: {filename}")
                
            source_name = parts[0]
            date_str = parts[1]
            
            # Try to parse page number
            page_number = 1
            if len(parts) > 2:
                try:
                    page_number = int(parts[2])
                except ValueError:
                    pass
            
            # Determine origin from file path
            if "chroniclingamerica" in file_path.lower():
                origin = "chroniclingamerica"
            elif "newspapers.com" in file_path.lower():
                origin = "newspapers.com"
            else:
                origin = "other"
            
            # Save to repository
            page_id = self.db_manager.add_newspaper_page(
                source_name=source_name,
                publication_date=date_str,
                page_number=page_number,
                filename=filename,
                origin=origin
            )
            
            if not page_id:
                raise ValueError(f"Failed to add page to database: {filename}")
            
            # Save original file
            original_path = self.file_manager.save_original_page(
                file_path, origin, source_name, date_str, page_number
            )
            
            if not original_path:
                raise ValueError(f"Failed to save original page: {filename}")
                
            # Update image path in database
            self.db_manager.cursor.execute("""
                UPDATE newspaper_pages
                SET image_path = ?
                WHERE page_id = ?
            """, (original_path, page_id))
            self.db_manager.conn.commit()
            
            # Process the page
            self.process_page(file_path, page_id)
            
            # Mark as completed
            self.db_manager.update_queue_status(queue_id, "completed")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing queue item {queue_id}: {e}")
            
            # Mark as error
            if self.db_manager:
                self.db_manager.update_queue_status(queue_id, "error", str(e))
                
            return False
    
    def _clean_ocr_text(self, text: str) -> str:
        """
        Clean OCR text by removing noise and fixing common issues.
        
        Args:
            text: Raw OCR text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
            
        # Remove control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Fix common OCR errors
        replacements = [
            # Fix broken words
            (r'(\w)-\n(\w)', r'\1\2'),
            # Remove excessive newlines
            (r'\n{3,}', '\n\n'),
            # Fix broken sentences
            (r'(\w)\n([a-z])', r'\1 \2'),
            # Fix spaces before punctuation
            (r'\s+([.,;:!?])', r'\1'),
            # Fix missing spaces after punctuation
            (r'([.,;:!?])([A-Za-z])', r'\1 \2'),
        ]
        
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)
            
        return text.strip()
    
    def _parse_hocr_blocks(self, hocr_text: str) -> List[Dict[str, Any]]:
        """
        Parse HOCR to extract text blocks with their positions.
        
        Args:
            hocr_text: HOCR content string
            
        Returns:
            List of dictionaries with block information
        """
        # Parse HOCR with BeautifulSoup
        soup = BeautifulSoup(hocr_text, 'html.parser')
        
        # Find all paragraph or text blocks
        blocks = []
        
        # Look for ocr_par elements (paragraphs)
        for par in soup.find_all(class_='ocr_par'):
            # Extract bounding box
            title = par.get('title', '')
            bbox_match = re.search(r'bbox (\d+) (\d+) (\d+) (\d+)', title)
            
            if bbox_match:
                x1, y1, x2, y2 = map(int, bbox_match.groups())
                width = x2 - x1
                height = y2 - y1
                
                # Extract text from paragraph
                text = par.get_text().strip()
                
                # Get word confidence values
                words = par.find_all(class_='ocrx_word')
                confidences = []
                
                for word in words:
                    word_title = word.get('title', '')
                    conf_match = re.search(r'x_wconf (\d+)', word_title)
                    if conf_match:
                        confidences.append(int(conf_match.group(1)))
                
                # Calculate average confidence
                avg_conf = sum(confidences) / len(confidences) if confidences else 0
                
                # Add to blocks
                blocks.append({
                    'text': text,
                    'bbox': (x1, y1, width, height),
                    'confidence': avg_conf
                })
        
        # If no paragraphs found, try lines
        if not blocks:
            for line in soup.find_all(class_='ocr_line'):
                # Extract bounding box
                title = line.get('title', '')
                bbox_match = re.search(r'bbox (\d+) (\d+) (\d+) (\d+)', title)
                
                if bbox_match:
                    x1, y1, x2, y2 = map(int, bbox_match.groups())
                    width = x2 - x1
                    height = y2 - y1
                    
                    # Extract text from line
                    text = line.get_text().strip()
                    
                    # Get word confidence values
                    words = line.find_all(class_='ocrx_word')
                    confidences = []
                    
                    for word in words:
                        word_title = word.get('title', '')
                        conf_match = re.search(r'x_wconf (\d+)', word_title)
                        if conf_match:
                            confidences.append(int(conf_match.group(1)))
                    
                    # Calculate average confidence
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0
                    
                    # Add to blocks
                    blocks.append({
                        'text': text,
                        'bbox': (x1, y1, width, height),
                        'confidence': avg_conf
                    })
        
        return blocks
        
    @dataclass
    class OCRResult:
        """Class for storing results from OCR processing."""
        text: str
        confidence: float
        hocr_path: str
        segments: List[ArticleSegment] = None
    
    def process_page(self, image_path: str, output_dir: Optional[str] = None) -> OCRResult:
        """
        Process a newspaper page with OCR to extract text, generate HOCR, and identify segments.
        
        Args:
            image_path: Path to the image file
            output_dir: Directory to save HOCR output (if None, a temp directory is used)
            
        Returns:
            OCRResult object with text, confidence, and path to HOCR file
        """
        try:
            logger.info(f"Processing page: {image_path}")
            
            # Generate output directory if not provided
            if output_dir is None:
                output_dir = tempfile.mkdtemp(prefix="ocr_")
            else:
                os.makedirs(output_dir, exist_ok=True)
                
            # Process OCR text
            text, confidence = self.process_page_ocr(image_path)
            
            # Generate and save HOCR
            hocr_text = self.generate_hocr(image_path)
            
            # Create output filename from input file
            base_filename = os.path.splitext(os.path.basename(image_path))[0]
            hocr_filename = f"{base_filename}_hocr.html"
            hocr_path = os.path.join(output_dir, hocr_filename)
            
            # Write HOCR to file
            with open(hocr_path, 'w', encoding='utf-8') as f:
                f.write(hocr_text)
                
            logger.info(f"OCR processing complete: {image_path} (confidence: {confidence:.2f})")
            logger.info(f"HOCR saved to: {hocr_path}")
            
            # Return results
            return self.OCRResult(
                text=text,
                confidence=confidence,
                hocr_path=hocr_path
            )
            
        except Exception as e:
            logger.error(f"Error processing page {image_path}: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def analyze_layout_from_hocr(self, hocr_path: str, image_path: str) -> List[ArticleSegment]:
        """
        Analyze layout from HOCR file to extract article segments.
        
        Args:
            hocr_path: Path to the HOCR file
            image_path: Path to the original image file
            
        Returns:
            List of ArticleSegment objects
        """
        try:
            logger.info(f"Analyzing layout from HOCR: {hocr_path}")
            
            # Read HOCR file
            with open(hocr_path, 'r', encoding='utf-8') as f:
                hocr_text = f.read()
                
            # Parse HOCR blocks
            blocks = self._parse_hocr_blocks(hocr_text)
            
            # Use layout analysis to group blocks into segments
            article_segments = []
            
            # Load image for dimensions and segment extraction
            img = cv2.imread(image_path)
            if img is None:
                raise FileNotFoundError(f"Could not load image: {image_path}")
                
            img_height, img_width = img.shape[:2]
            
            # Create temp directory for segment images
            segment_dir = os.path.join(os.path.dirname(hocr_path), "segments")
            os.makedirs(segment_dir, exist_ok=True)
            
            # Group blocks into segments
            # For simplicity here, each block is treated as a segment
            # A more sophisticated approach would group related blocks
            for i, block in enumerate(blocks):
                if len(block['text']) < 50:  # Skip very short blocks
                    continue
                    
                # Extract bounding box
                x, y, w, h = block['bbox']
                
                # Extract segment image
                if x >= 0 and y >= 0 and x + w <= img_width and y + h <= img_height:
                    segment_img = img[y:y+h, x:x+w]
                    
                    # Save segment image
                    segment_filename = f"segment_{i:04d}.jpg"
                    segment_path = os.path.join(segment_dir, segment_filename)
                    cv2.imwrite(segment_path, segment_img)
                    
                    # Create article segment
                    segment = ArticleSegment(
                        id=None,  # Will be assigned when saved to database
                        headline=None,  # Could try to detect headlines based on font size/position
                        text=block['text'],
                        confidence=block['confidence'],
                        bbox=(x, y, w, h),
                        image_path=segment_path
                    )
                    
                    article_segments.append(segment)
            
            logger.info(f"Identified {len(article_segments)} segments from {hocr_path}")
            return article_segments
            
        except Exception as e:
            logger.error(f"Error analyzing layout from HOCR {hocr_path}: {e}")
            logger.error(traceback.format_exc())
            raise