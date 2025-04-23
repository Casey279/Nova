# File: ai_assisted_ocr.py

import sys
import os
import cv2
import pytesseract
import anthropic
from dotenv import load_dotenv
from PIL import Image, ImageEnhance
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                            QLabel, QFrame, QGroupBox, QMessageBox, QApplication)
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtCore import Qt

class RegionBasedOCR:
    def __init__(self, image_path):
        self.image_path = image_path
        self.settings_a = {
            'contrast': 1.3,
            'brightness': 1.1,
            'sharpness': 1.4,
            'description': 'High detail enhancement'
        }
        self.settings_b = {
            'contrast': 1.5,
            'brightness': 0.9,
            'sharpness': 1.6,
            'description': 'High contrast enhancement'
        }

    def detect_regions(self, image):
        """Detect all text regions in image, ensuring complete coverage"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
          
        # Get dimensions for safety checks
        height, width = gray.shape
          
        # Use connected components to find text regions
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )
          
        # Dilate to connect text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 3))
        dilated = cv2.dilate(binary, kernel, iterations=3)
          
        # Find contours
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
          
        # Convert contours to regions, ensuring no gaps
        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Expand region slightly to ensure no text is cut off
            x = max(0, x - 5)
            y = max(0, y - 5)
            w = min(width - x, w + 10)
            h = min(height - y, h + 10)
            regions.append((x, y, w, h))
          
        # Sort regions top to bottom
        regions.sort(key=lambda r: r[1])
          
        return regions

    def process_region(self, image, region, settings):
        """Process a single region with given settings"""
        x, y, w, h = region
        roi = image[y:y+h, x:x+w]
          
        # Convert to PIL for enhancements
        pil_roi = Image.fromarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))
          
        # Apply enhancements
        pil_roi = ImageEnhance.Contrast(pil_roi).enhance(settings['contrast'])
        pil_roi = ImageEnhance.Brightness(pil_roi).enhance(settings['brightness'])
        pil_roi = ImageEnhance.Sharpness(pil_roi).enhance(settings['sharpness'])
          
        # OCR the region
        text = pytesseract.image_to_string(pil_roi)
          
        # Always return something, even if empty
        return text.strip() if text.strip() else "[unreadable text]"

    def process_full_image(self, settings):
        """Process entire image by regions"""
        # Read image
        image = cv2.imread(self.image_path)
        if image is None:
            raise ValueError("Could not read image")
              
        # Get regions
        regions = self.detect_regions(image)
          
        # Process each region
        region_texts = []
        for region in regions:
            text = self.process_region(image, region, settings)
            region_texts.append(text)
          
        # Combine with proper spacing
        return "\n\n".join(region_texts)

    def get_both_versions(self):
        """Process image with both enhancement settings"""
        try:
            version_a = self.process_full_image(self.settings_a)
            version_b = self.process_full_image(self.settings_b)
            return {
                'version_a': {
                    'text': version_a,
                    'settings': self.settings_a
                },
                'version_b': {
                    'text': version_b,
                    'settings': self.settings_b
                }
            }
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return None

class AIAssistedOCRDialog(QDialog):
    def __init__(self, parent=None, image_path=None):
        super().__init__(parent)
        self.image_path = image_path
        self.parent_widget = parent
        
        # Get the anthropic client from parent
        if parent and hasattr(parent, 'client'):
            self.client = parent.client
        else:
            # Initialize a new client if parent doesn't have one
            load_dotenv()
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found. Please set up your API key.")
            self.client = anthropic.Anthropic(api_key=api_key)
            
        self.best_result = None
        self.use_improved = False
        self.processor = RegionBasedOCR(image_path)
        self.initUI()
          
    def initUI(self):
        self.setWindowTitle("AI Assisted OCR")
        self.setMinimumSize(1200, 800)
          
        # Main layout
        layout = QHBoxLayout(self)
          
        # Left panel - Image viewer and OCR progress
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
          
        # Image viewer
        # Since ZoomableGraphicsView is imported from article_processor.py
        from article_processor import ZoomableGraphicsView
        self.image_viewer = ZoomableGraphicsView()
        if self.image_path:
            self.image_viewer.display_image(self.image_path)
        left_layout.addWidget(self.image_viewer)
          
        # Progress section
        progress_group = QGroupBox("OCR Progress")
        progress_layout = QVBoxLayout()
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMaximumHeight(150)
        progress_layout.addWidget(self.progress_text)
        progress_group.setLayout(progress_layout)
        left_layout.addWidget(progress_group)
          
        layout.addWidget(left_panel, stretch=2)
          
        # Middle panel - AI Improved Version
        middle_panel = QFrame()
        middle_layout = QVBoxLayout(middle_panel)
          
        # AI Improved output
        improved_group = QGroupBox("AI Improved Version")
        improved_layout = QVBoxLayout()
        self.improved_text = QTextEdit()
        improved_layout.addWidget(self.improved_text)
        improved_group.setLayout(improved_layout)
        middle_layout.addWidget(improved_group)
          
        # Process button
        self.start_button = QPushButton("Start AI Assisted OCR")
        self.start_button.clicked.connect(self.process_with_ai)
        middle_layout.addWidget(self.start_button)
          
        # Add Text to Main button
        self.add_improved_button = QPushButton("Add Text to Main")
        self.add_improved_button.clicked.connect(self.add_improved_to_main)
        self.add_improved_button.setEnabled(False)
        middle_layout.addWidget(self.add_improved_button)
          
        layout.addWidget(middle_panel, stretch=3)
          
        # Right panel - For future functionality
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
          
        # Placeholder for future functionality
        future_label = QLabel("Future Functionality")
        future_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(future_label)
          
        layout.addWidget(right_panel, stretch=2)

    def process_with_ai(self):
        """Process image with AI assistance"""
        self.start_button.setEnabled(False)
        self.progress_text.clear()
        self.improved_text.clear()
          
        try:
            self.add_progress("Processing image with multiple settings...")
            versions = self.processor.get_both_versions()
              
            if not versions:
                raise Exception("Failed to process image")
                  
            self.add_progress("Analyzing and improving results...")
              
            # Have AI analyze and improve text
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": f"""Compare these two OCR versions of a historical newspaper article and create a clean version:

                    Version A ({versions['version_a']['settings']['description']}):  
                    {versions['version_a']['text']}

                    Version B ({versions['version_b']['settings']['description']}):  
                    {versions['version_b']['text']}

                    Please create a clean version that:  
                    1. Uses the better version as base  
                    2. Fixes obvious OCR errors  
                    3. Removes random characters and formatting artifacts  
                    4. Preserves original paragraph structure and quotes  
                    5. Maintains historical spelling and terms  
                    6. For any word or section that is completely unintelligible, replace with 'XXXXX' matching approximate length  
                    7. Keep all original content and meaning where clear

                    Format the text as it would appear in a newspaper, with proper paragraphs and quotation marks."""
                }]
            )
              
            # Show AI-improved version in the improved_text QTextEdit
            self.improved_text.setText(response.content[0].text)
              
            # Enable the Add Text to Main button
            self.add_improved_button.setEnabled(True)
              
        except Exception as e:
            self.add_progress(f"Error: {str(e)}")
            QMessageBox.warning(self, "Processing Error", str(e))
        finally:
            self.start_button.setEnabled(True)

    def add_progress(self, message):
        """Add a progress message"""
        self.progress_text.append(message)
        QApplication.processEvents()

    def add_improved_to_main(self):
        improved_text = self.improved_text.toPlainText()
        main_text = self.parent_widget.ocr_text_edit.toPlainText()

        if main_text:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setText("There is existing text in the main window.")
            msg_box.setInformativeText("Do you want to overwrite the existing text or append the new text?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            msg_box.setDefaultButton(QMessageBox.Yes)
            msg_box.button(QMessageBox.Yes).setText("Overwrite")
            msg_box.button(QMessageBox.No).setText("Append")

            ret = msg_box.exec_()

            if ret == QMessageBox.Yes:
                self.parent_widget.ocr_text_edit.setPlainText(improved_text)
            elif ret == QMessageBox.No:
                self.parent_widget.ocr_text_edit.setPlainText(main_text + "\n\n" + improved_text)
            else:
                return  # Cancel was clicked
        else:
            self.parent_widget.ocr_text_edit.setPlainText(improved_text)

        self.accept()

    def get_result(self):
        """Return the processed text"""
        return self.improved_text.toPlainText()