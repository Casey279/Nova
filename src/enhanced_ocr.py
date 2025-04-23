# File: enhanced_ocr.py

import cv2
import numpy as np
from PIL import Image, ImageEnhance
import pytesseract
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class TextRegion:
    """Represents a detected text region in the image"""
    x: int
    y: int
    width: int
    height: int
    text: str = ""
    confidence: float = 0.0

class EnhancedOCRProcessor:
    def __init__(self):
        # Default enhancement settings
        self.default_settings = {
            'contrast': 1.2,
            'brightness': 1.1,
            'sharpness': 1.3
        }

    def process_image(self, image_path: str) -> str:
        """Main processing pipeline for OCR"""
        # Read image
        original_image = cv2.imread(image_path)
        if original_image is None:
            raise ValueError("Could not read image")

        # Convert to grayscale
        gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)

        # Detect text regions
        regions = self.detect_text_regions(gray)

        # Sort regions by position (top to bottom, left to right)
        regions = self.sort_regions(regions)

        # Process each region
        all_text = []
        for region in regions:
            # Extract region from original image
            roi = original_image[region.y:region.y + region.height, 
                               region.x:region.x + region.width]
            
            # Convert to PIL Image for processing
            pil_roi = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
            
            # Enhance region
            enhanced_roi = self.enhance_region(pil_roi)
            
            # Perform OCR on enhanced region
            text = pytesseract.image_to_string(enhanced_roi)
            region.text = text.strip()
            
            if region.text:  # Only add non-empty text
                all_text.append(region.text)

        # Combine all text
        return '\n\n'.join(all_text)

    def detect_text_regions(self, gray_image: np.ndarray) -> List[TextRegion]:
        """Detect potential text regions in the image"""
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray_image)
        
        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # Dilate to connect text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(binary, kernel, iterations=3)

        # Find contours
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Convert contours to TextRegions
        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter out very small regions
            if w < 30 or h < 30:
                continue
                
            # Filter out regions that are too large
            if w > gray_image.shape[1] * 0.95 or h > gray_image.shape[0] * 0.95:
                continue

            regions.append(TextRegion(x=x, y=y, width=w, height=h))

        return regions

    def sort_regions(self, regions: List[TextRegion]) -> List[TextRegion]:
        """Sort regions by position (top to bottom, left to right)"""
        # Define threshold for considering regions to be on the same line
        y_threshold = 20

        # Group regions by their y-coordinate
        y_groups = {}
        for region in regions:
            y_center = region.y + region.height // 2
            assigned = False
            
            # Check if region belongs to an existing group
            for group_y in y_groups.keys():
                if abs(group_y - y_center) < y_threshold:
                    y_groups[group_y].append(region)
                    assigned = True
                    break
            
            # If not assigned to any group, create new group
            if not assigned:
                y_groups[y_center] = [region]

        # Sort regions within each group by x-coordinate
        sorted_regions = []
        for y in sorted(y_groups.keys()):
            line_regions = sorted(y_groups[y], key=lambda r: r.x)
            sorted_regions.extend(line_regions)

        return sorted_regions

    def enhance_region(self, image: Image.Image) -> Image.Image:
        """Apply enhancements to improve OCR accuracy"""
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')

            # Apply enhancements
            image = ImageEnhance.Contrast(image).enhance(self.default_settings['contrast'])
            image = ImageEnhance.Brightness(image).enhance(self.default_settings['brightness'])
            image = ImageEnhance.Sharpness(image).enhance(self.default_settings['sharpness'])

            # Resize if too small
            if image.width < 300 or image.height < 300:
                scale = max(300 / image.width, 300 / image.height)
                new_size = (int(image.width * scale), int(image.height * scale))
                image = image.resize(new_size, Image.Refilter.LANCZOS)

            return image
        except Exception as e:
            print(f"Error enhancing region: {str(e)}")
            return image  # Return original image if enhancement fails

    def debug_visualization(self, image_path: str, output_path: str = None):
        """Create a debug visualization of detected regions"""
        # Read image
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect regions
        regions = self.detect_text_regions(gray)
        
        # Draw regions
        debug_image = image.copy()
        for idx, region in enumerate(regions):
            cv2.rectangle(
                debug_image,
                (region.x, region.y),
                (region.x + region.width, region.y + region.height),
                (0, 255, 0),
                2
            )
            cv2.putText(
                debug_image,
                f"Region {idx}",
                (region.x, region.y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1
            )
        
        if output_path:
            cv2.imwrite(output_path, debug_image)
        
        return debug_image