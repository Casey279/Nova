# File: ocr_service.py

import os
import tempfile
from typing import List, Dict, Any, Tuple, Optional, BinaryIO
import pytesseract
from PIL import Image
import cv2
import numpy as np

from .base_service import BaseService, DatabaseError
from .config_service import ConfigService

class OCRService(BaseService):
    """
    Service for handling OCR (Optical Character Recognition) operations.
    Provides methods for extracting text from images and scanned documents.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the OCR service.
        
        Args:
            db_path: Path to the database
        """
        super().__init__(db_path)
        self.config_service = ConfigService()
        
        # Get tesseract path from config
        tesseract_path = self.config_service.get_setting('ocr', 'tesseract_path')
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    def perform_ocr(self, image_path: str, enhanced: bool = False) -> str:
        """
        Perform OCR on an image.
        
        Args:
            image_path: Path to the image file
            enhanced: Whether to use enhanced OCR preprocessing
            
        Returns:
            Extracted text
            
        Raises:
            ValueError: If image cannot be processed
        """
        try:
            if enhanced:
                return self.perform_enhanced_ocr(image_path)
            else:
                return self.perform_basic_ocr(image_path)
        except Exception as e:
            raise ValueError(f"OCR processing failed: {str(e)}")
    
    def perform_basic_ocr(self, image_path: str) -> str:
        """
        Perform basic OCR on an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text
        """
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text
    
    def perform_enhanced_ocr(self, image_path: str) -> str:
        """
        Perform enhanced OCR with preprocessing on an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text
        """
        # Read image using OpenCV
        img = cv2.imread(image_path)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to get a binary image
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        
        # Apply dilation and erosion to remove noise
        kernel = np.ones((1, 1), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=1)
        binary = cv2.erode(binary, kernel, iterations=1)
        
        # Apply Gaussian blur to reduce noise further
        processed = cv2.GaussianBlur(binary, (5, 5), 0)
        
        # Save processed image to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp:
            temp_path = temp.name
            cv2.imwrite(temp_path, processed)
        
        try:
            # Perform OCR on processed image
            text = pytesseract.image_to_string(Image.open(temp_path))
            return text
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def extract_text_from_pdf_with_ocr(self, pdf_path: str, enhanced: bool = False) -> str:
        """
        Extract text from a PDF using OCR.
        
        Args:
            pdf_path: Path to the PDF file
            enhanced: Whether to use enhanced OCR preprocessing
            
        Returns:
            Extracted text
            
        Raises:
            ValueError: If PDF cannot be processed
        """
        try:
            # This would require converting PDF pages to images
            # and performing OCR on each image
            # For simplicity, we'll just outline the approach here
            
            # Convert PDF to images using a library like pdf2image
            # For each image, perform OCR
            # Combine the results
            
            # This method would need to be implemented fully with pdf2image
            return "PDF OCR not yet implemented"
        except Exception as e:
            raise ValueError(f"PDF OCR processing failed: {str(e)}")
    
    def perform_ai_assisted_ocr(self, image_path: str) -> str:
        """
        Perform AI-assisted OCR on an image.
        
        This is a placeholder for future implementation using AI models
        to enhance OCR results.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text
        """
        # First get basic OCR results
        basic_result = self.perform_enhanced_ocr(image_path)
        
        # This is where you would send the image and/or basic OCR results
        # to an AI model for improvement and correction
        # For now, we just return the basic results
        
        return basic_result
    
    def detect_tables_in_image(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Detect tables in an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            List of detected tables with their coordinates
            
        Raises:
            ValueError: If image cannot be processed
        """
        try:
            # This would implement table detection logic
            # For simplicity, we'll just outline the approach here
            
            # Use OpenCV to detect rectangular structures
            # or use a specialized library for table detection
            
            # Return detected table regions
            return []
        except Exception as e:
            raise ValueError(f"Table detection failed: {str(e)}")