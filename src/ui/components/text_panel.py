import os
import sys
import cv2
import pytesseract
import anthropic
from PIL import Image, ImageEnhance
from dotenv import load_dotenv
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QTextEdit, QMessageBox, QDialog, QLineEdit,
                            QLabel, QSlider)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCharFormat, QTextCursor, QFont, QColor

# Import from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from enhanced_ocr import EnhancedOCRProcessor
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ai_assisted_ocr import AIAssistedOCRDialog


class TextPanel(QWidget):
    """
    Panel for OCR processing and text editing.
    
    Responsibilities:
    - OCR processing with various methods
    - Text display and editing
    - Font size controls
    """
    
    # Signals
    text_changed = pyqtSignal(str)  # Emits when text content changes
    ocr_requested = pyqtSignal(str, object)  # Emits when OCR is requested for region
    names_detected = pyqtSignal(list)  # Emits list of detected names
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = None
        self.original_text = None
        self.detected_names = []
        self.current_name_index = 0
        self.setup_ai_client()
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Font size controls
        font_controls = QHBoxLayout()
        font_controls.addStretch()
        
        decrease_font_button = QPushButton("-")
        decrease_font_button.setFixedSize(25, 25)
        decrease_font_button.clicked.connect(self.decrease_font_size)
        font_controls.addWidget(decrease_font_button)
        
        increase_font_button = QPushButton("+")
        increase_font_button.setFixedSize(25, 25)
        increase_font_button.clicked.connect(self.increase_font_size)
        font_controls.addWidget(increase_font_button)
        
        layout.addLayout(font_controls)
        
        # Text editing area
        self.text_edit = QTextEdit()
        self.text_edit.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.text_edit)
        
        # OCR controls
        ocr_controls = QHBoxLayout()
        
        self.ocr_button = QPushButton("Run OCR")
        self.ocr_button.clicked.connect(self.run_ocr)
        ocr_controls.addWidget(self.ocr_button)
        
        self.clear_button = QPushButton("Clear OCR Text")
        self.clear_button.clicked.connect(self.text_edit.clear)
        ocr_controls.addWidget(self.clear_button)
        
        self.enhanced_ocr_button = QPushButton("Enhanced OCR")
        self.enhanced_ocr_button.clicked.connect(self.run_enhanced_ocr)
        ocr_controls.addWidget(self.enhanced_ocr_button)
        
        self.ai_ocr_button = QPushButton("AI Assisted OCR")
        self.ai_ocr_button.clicked.connect(self.run_ai_assisted_ocr)
        ocr_controls.addWidget(self.ai_ocr_button)
        
        self.process_names_button = QPushButton("Process Names")
        self.process_names_button.clicked.connect(self.process_names)
        ocr_controls.addWidget(self.process_names_button)
        
        layout.addLayout(ocr_controls)
    
    def setup_ai_client(self):
        """Initialize AI client with API key from environment"""
        load_dotenv()
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("Warning: ANTHROPIC_API_KEY not found in environment")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
    
    def set_image_path(self, path):
        """Set the current image path for OCR processing"""
        self.image_path = path
        
    def on_text_changed(self):
        """Handle text changes and emit signal"""
        self.text_changed.emit(self.text_edit.toPlainText())
    
    def run_ocr(self):
        """Run basic OCR on the current image"""
        if not self.image_path:
            QMessageBox.warning(self, "No Image", "Please load an image first")
            return
            
        try:
            img = Image.open(self.image_path)
            ocr_result = pytesseract.image_to_string(img)
            self.text_edit.setText(ocr_result)
        except Exception as e:
            self.text_edit.setText(f"OCR error: {str(e)}")
    
    def run_enhanced_ocr(self):
        """Run enhanced OCR with preprocessing"""
        if not self.image_path:
            QMessageBox.warning(self, "No Image", "Please load an image first")
            return
            
        try:
            # Create OCR processor
            processor = EnhancedOCRProcessor()
            
            # Process the image
            processor.process_image(self.image_path)
            
            # Get OCR result
            ocr_result = processor.get_text()
            
            # Update text edit
            if ocr_result:
                self.text_edit.setText(ocr_result)
            else:
                QMessageBox.warning(self, "OCR Failed", "Enhanced OCR did not produce any text")
                
        except Exception as e:
            QMessageBox.warning(self, "OCR Error", f"Enhanced OCR failed: {str(e)}")
    
    def run_ai_assisted_ocr(self):
        """Run AI-assisted OCR using Claude"""
        if not self.image_path:
            QMessageBox.warning(self, "No Image", "Please load an image first")
            return
            
        if not self.client:
            QMessageBox.warning(self, "API Key Missing", 
                              "Anthropic API key not found. Please set ANTHROPIC_API_KEY in environment.")
            return
            
        try:
            dialog = AIAssistedOCRDialog(self, self.image_path, self.client)
            if dialog.exec_() == QDialog.Accepted and dialog.final_text:
                self.text_edit.setText(dialog.final_text)
        except Exception as e:
            QMessageBox.warning(self, "AI OCR Error", f"AI-assisted OCR failed: {str(e)}")
    
    def run_region_ocr(self, region, settings=None):
        """Run OCR on a specific region of the image"""
        if not self.image_path or not region:
            return
            
        try:
            # Open the image
            img = Image.open(self.image_path)
            
            # Crop to region
            region_img = img.crop((region.left(), region.top(), 
                                  region.right(), region.bottom()))
            
            # Apply enhancements if provided
            if settings:
                if 'contrast' in settings:
                    region_img = ImageEnhance.Contrast(region_img).enhance(settings['contrast'])
                if 'brightness' in settings:
                    region_img = ImageEnhance.Brightness(region_img).enhance(settings['brightness'])
                if 'sharpness' in settings:
                    region_img = ImageEnhance.Sharpness(region_img).enhance(settings['sharpness'])
            
            # Run OCR
            ocr_result = pytesseract.image_to_string(region_img)
            
            # Update text edit - append if there's existing text
            if self.text_edit.toPlainText():
                self.text_edit.append("\n" + ocr_result)
            else:
                self.text_edit.setText(ocr_result)
                
        except Exception as e:
            QMessageBox.warning(self, "Region OCR Error", f"Region OCR failed: {str(e)}")
    
    def get_text(self):
        """Get the current text content"""
        return self.text_edit.toPlainText()
        
    def set_text(self, text):
        """Set the text content"""
        self.text_edit.setText(text)
    
    def increase_font_size(self):
        """Increase the font size of the text edit"""
        current_font = self.text_edit.font()
        current_size = current_font.pointSize()
        if current_size < 30:  # Limit maximum font size
            current_font.setPointSize(current_size + 1)
            self.text_edit.setFont(current_font)
    
    def decrease_font_size(self):
        """Decrease the font size of the text edit"""
        current_font = self.text_edit.font()
        current_size = current_font.pointSize()
        if current_size > 8:  # Limit minimum font size
            current_font.setPointSize(current_size - 1)
            self.text_edit.setFont(current_font)
    
    def load_text_from_file(self, file_path):
        """Load text from a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.text_edit.setText(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load text file: {str(e)}")
    
    def process_names(self):
        """Process text for potential names after OCR"""
        if not self.text_edit.toPlainText():
            QMessageBox.warning(self, "No Text", "Please perform OCR first.")
            return

        # Store the current text for reference
        self.original_text = self.text_edit.toPlainText()
        
        # Clear any existing highlights
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        
        # Initialize format for highlighting
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(255, 255, 200))  # Light yellow background
        
        # Find potential names and highlight them
        self.detected_names = []  # Store detected names for processing
        text = self.original_text
        
        # Simple name detection
        words = text.split()
        for i, word in enumerate(words):
            if (word[0].isupper() and  # First letter is uppercase
                len(word) > 1 and      # More than one letter
                not word.isupper()):   # Not all uppercase (to avoid acronyms)
                
                # Check if it's part of a multi-word name
                name_parts = [word]
                next_idx = i + 1
                while next_idx < len(words) and words[next_idx][0].isupper():
                    name_parts.append(words[next_idx])
                    next_idx += 1
                
                full_name = " ".join(name_parts)
                self.detected_names.append((full_name, text.find(full_name)))
        
        # Highlight the names
        for name, pos in self.detected_names:
            cursor = self.text_edit.textCursor()
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(name))
            cursor.mergeCharFormat(highlight_format)
        
        if self.detected_names:
            # Reset the index for processing
            self.current_name_index = 0
            # Emit signal with detected names
            self.names_detected.emit([name for name, _ in self.detected_names])
            QMessageBox.information(self, "Name Detection", 
                                   f"Found {len(self.detected_names)} potential names.")
        else:
            QMessageBox.information(self, "Name Detection", "No potential names found.")
    
    def get_detected_names(self):
        """Return the list of detected names"""
        return [name for name, _ in self.detected_names]