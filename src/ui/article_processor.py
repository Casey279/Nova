# File: article_processor.py

import sys
import os
import cv2 
import shutil
import sqlite3
import pytesseract
import re
import numpy as np
import anthropic
from dotenv import load_dotenv
from PIL import Image, ImageEnhance
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog, QLabel, QSplitter, QStyle,
                             QGraphicsView, QGraphicsScene, QMessageBox, QLineEdit, QListWidget, QDialog, QFormLayout,  
                             QDialogButtonBox, QGroupBox, QSplitterHandle, QGridLayout, QSlider, QGraphicsRectItem, 
                             QGraphicsPixmapItem, QComboBox, QFrame, QApplication, QCompleter, QListWidgetItem, QStyledItemDelegate)
from PyQt5.QtGui import (QPixmap, QPainter, QPen, QBrush, QColor, QPalette, QTextCharFormat, QTextCursor, QFont, QIcon, 
                         QStandardItem, QStandardItemModel)
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal, QRectF, QPoint, QStringListModel, QRect   
from PIL import Image
from datetime import datetime
from database_manager import DatabaseManager
from enhanced_ocr import EnhancedOCRProcessor
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_assisted_ocr import AIAssistedOCRDialog



# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# This code should be added to article_processor.py

class CustomCompleter(QCompleter):
    """Enhanced completer with custom display for entity details"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterMode(Qt.MatchContains)
        self.setMaxVisibleItems(10)
        
        # Create model for storing rich data
        self.model = QStandardItemModel()
        self.setModel(self.model)
        
        # Set custom popup that shows details
        self.popup().setItemDelegate(DetailItemDelegate())
        self.popup().setStyleSheet("""
            QListView {
                border: 1px solid #ccc;
                background-color: #f8f8f8;
            }
            QListView::item {
                padding: 4px;
                border-bottom: 1px solid #eee;
            }
            QListView::item:selected {
                background-color: #e0e0e0;
                color: black;
            }
        """)
        
        # Store the details for items
        self.item_details = {}
        
    def update_completions(self, matches_data):
        """Update completer with matches data
        
        Args:
            matches_data: List of dicts with entity info
        """
        self.model.clear()
        self.item_details.clear()
        
        if not matches_data:
            return
        
        for match in matches_data:
            display_name = match['display_name']
            
            # Create standard item for the model
            item = QStandardItem(display_name)
            
            # Store source for styling
            item.setData(match['source'], Qt.UserRole + 1)
            
            # Store match type for styling
            item.setData(match['match_type'], Qt.UserRole + 2)
            
            # Add to model
            self.model.appendRow(item)
            
            # Store details for display in delegate
            self.item_details[display_name] = match
        
        # Make sure model is set
        self.setModel(self.model)


class DetailItemDelegate(QStyledItemDelegate):
    """Delegate for displaying items with details in completer popup"""
    
    def paint(self, painter, option, index):
        """Custom painting for completer items"""
        # Get data
        display_name = index.data(Qt.DisplayRole)
        source = index.data(Qt.UserRole + 1)
        match_type = index.data(Qt.UserRole + 2)
        
        # Get completer and details
        completer = self.parent().completer() if hasattr(self.parent(), 'completer') else None
        details = completer.item_details.get(display_name) if hasattr(completer, 'item_details') else None
        
        # Set up the painter
        painter.save()
        
        # Draw selection background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        
        # Calculate text area
        text_rect = option.rect.adjusted(4, 4, -4, -4)
        
        # Draw icon based on match type
        icon_rect = QRect(text_rect.left(), text_rect.top(), 20, 20)
        if match_type == 'exact':
            painter.setPen(QColor(0, 128, 0))  # Green
            painter.drawText(icon_rect, Qt.AlignCenter, "✓")
        elif match_type == 'alias':
            painter.setPen(QColor(0, 0, 255))  # Blue
            painter.drawText(icon_rect, Qt.AlignCenter, "≈")
        else:
            painter.setPen(QColor(128, 128, 128))  # Gray
            painter.drawText(icon_rect, Qt.AlignCenter, "○")
        
        # Draw display name with appropriate style
        name_rect = text_rect.adjusted(25, 0, 0, -20 if details and details.get('details') else 0)
        font = painter.font()
        if source == 'permanent':
            font.setBold(True)
        else:
            font.setItalic(True)
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, display_name)
        
        # Draw source indicator
        source_text = "(DB)" if source == 'permanent' else "(New)"
        source_color = QColor(0, 120, 0) if source == 'permanent' else QColor(120, 0, 0)
        source_rect = QRect(name_rect.right() - 40, name_rect.top(), 40, name_rect.height())
        painter.setPen(source_color)
        painter.drawText(source_rect, Qt.AlignRight | Qt.AlignVCenter, source_text)
        
        # Draw details if available
        if details and details.get('details'):
            detail_rect = QRect(name_rect.left(), name_rect.bottom(), 
                              text_rect.width() - 25, 20)
            font.setBold(False)
            font.setItalic(False)
            font.setPointSize(font.pointSize() - 1)
            painter.setFont(font)
            painter.setPen(QColor(100, 100, 100))
            detail_text = details.get('details')
            # Truncate details if too long
            if painter.fontMetrics().horizontalAdvance(detail_text) > detail_rect.width():
                detail_text = painter.fontMetrics().elidedText(
                    detail_text, Qt.ElideRight, detail_rect.width())
            painter.drawText(detail_rect, Qt.AlignLeft | Qt.AlignVCenter, detail_text)
        
        painter.restore()
    
    def sizeHint(self, option, index):
        """Determine size of items based on content"""
        size = super().sizeHint(option, index)
        
        # Get display name
        display_name = index.data(Qt.DisplayRole)
        
        # Get completer and details
        completer = self.parent().completer() if hasattr(self.parent(), 'completer') else None
        details = completer.item_details.get(display_name) if hasattr(completer, 'item_details') else None
        
        # Increase height if we have details
        if details and details.get('details'):
            size.setHeight(size.height() + 20)
        
        return size


class CustomSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setStyleSheet("background-color: lightgray")  # Change the color if desired


    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw custom icon or text here - you can customize this as needed
        painter.drawText(self.rect(), Qt.AlignCenter, "<>")  # Drawing "<>" in the middle of the handle

class CustomSplitter(QSplitter):
    def createHandle(self):
        return CustomSplitterHandle(self.orientation(), self)  # Use our custom handle


class ArticleProcessor(QWidget):
    name_added = pyqtSignal()

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.image_path = None
        self.current_event_id = None
        self.changes_made = False
        self.associated_characters = []
        self.associated_locations = []
        self.associated_entities = []
        self.metadata = {}
        self.setup_ai_client()  # Initialize AI client
        self.initUI()
        # Use a single timer for both setup operations
        QTimer.singleShot(0, self.post_init_setup)

    def set_project_folder(self, folder_path):
        """Set the current project folder path"""
        self.project_folder = folder_path

    def post_init_setup(self):
        """Handle all post-initialization setup"""
        self.setup_event_filters()
        self.set_initial_sizes()

    def initUI(self):
        layout = QHBoxLayout(self)
        self.splitter = CustomSplitter(Qt.Horizontal)

        # Define splitter positions
        self.left_split = 0.25
        self.center_split = 0.50
        self.right_split = 0.25

        # Create and add panels
        self.splitter.addWidget(self.create_left_panel())
        self.splitter.addWidget(self.create_center_panel())
        self.splitter.addWidget(self.create_right_panel())

        # Add this to your create_right_panel method, near the end before returning the panel
        test_basic_button = QPushButton("Test Basic Completer")
        test_basic_button.clicked.connect(self.test_basic_completion)
        layout.addWidget(test_basic_button)

        # Add this to your create_right_panel method before returning the panel
        test_character_button = QPushButton("Test Character Save")
        test_character_button.clicked.connect(self.test_character_save)
        layout.addWidget(test_character_button)

        layout.addWidget(self.splitter)
        

    def set_initial_sizes(self):
        window_width = self.width()
        # Set initial positions with right splitter at max position (0.80)
        self.left_split = 0.25  # Left panel at 25%
        self.center_split = 0.55  # Center panel fills to 80% (0.25 + 0.55 = 0.80)
        self.right_split = 0.20  # Right panel takes remaining 20%
        
        self.splitter.setSizes([
            int(window_width * self.left_split),
            int(window_width * self.center_split),
            int(window_width * self.right_split)
        ])

    def setup_event_filters(self):
        """Install event filters on the splitter handles."""
        self.splitter.handle(1).installEventFilter(self)
        self.splitter.handle(2).installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle splitter movement constraints."""
        if event.type() == QEvent.MouseMove:
            total_width = self.width()
            
            if obj == self.splitter.handle(1):  # Left splitter
                # Don't let left splitter move past 20% or 30% of window width
                min_pos = 0.20
                max_pos = 0.30
                current_pos = obj.mapToGlobal(event.pos()).x() / total_width
                
                if current_pos < min_pos:
                    self.left_split = min_pos
                elif current_pos > max_pos:
                    self.left_split = max_pos
                    
            elif obj == self.splitter.handle(2):  # Right splitter
                # Don't let right splitter move past 70% or 80% of window width
                min_pos = 0.70
                max_pos = 0.80
                current_pos = obj.mapToGlobal(event.pos()).x() / total_width
                
                if current_pos < min_pos:
                    self.center_split = min_pos - self.left_split
                elif current_pos > max_pos:
                    self.center_split = max_pos - self.left_split
                    
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update splitter sizes when window is resized
        self.set_initial_sizes()

    def create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        self.image_viewer = ZoomableGraphicsView()
        layout.addWidget(self.image_viewer)
        
        upload_button = QPushButton("Upload Image/File")
        upload_button.clicked.connect(self.upload_image)
        layout.addWidget(upload_button)
        
        cancel_button = QPushButton("Clear/Cancel")
        cancel_button.clicked.connect(self.cancel_file)
        layout.addWidget(cancel_button)
        
        return panel

    def create_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Header layout for the font size buttons
        header_layout = QHBoxLayout()
        header_layout.addStretch()  # Push the buttons to the right

        # Font size adjustment buttons
        decrease_font_button = QPushButton("-")
        decrease_font_button.setFixedSize(25, 25)
        decrease_font_button.clicked.connect(self.decrease_font_size)
        header_layout.addWidget(decrease_font_button)

        increase_font_button = QPushButton("+")
        increase_font_button.setFixedSize(25, 25)
        increase_font_button.clicked.connect(self.increase_font_size)
        header_layout.addWidget(increase_font_button)

        # Add header layout to the main layout
        layout.addLayout(header_layout)

        # Text editing/viewing area
        self.ocr_text_edit = QTextEdit()
        layout.addWidget(self.ocr_text_edit)

        # Create OCR button layout
        ocr_button_layout = QHBoxLayout()

        # Run OCR button
        ocr_button = QPushButton("Run OCR")
        ocr_button.clicked.connect(self.run_ocr)
        ocr_button_layout.addWidget(ocr_button)

        # Clear OCR text button
        clear_ocr_button = QPushButton("Clear OCR Text")
        clear_ocr_button.clicked.connect(self.ocr_text_edit.clear)
        ocr_button_layout.addWidget(clear_ocr_button)


        # Enhanced OCR button
        enhanced_ocr_button = QPushButton("Enhanced OCR")
        enhanced_ocr_button.clicked.connect(self.open_enhanced_ocr)
        ocr_button_layout.addWidget(enhanced_ocr_button)

        # AI Assisted OCR button
        smart_ocr_button = QPushButton("AI Assisted OCR")
        smart_ocr_button.clicked.connect(self.run_ai_assisted_ocr)  # Changed method name here
        ocr_button_layout.addWidget(smart_ocr_button)

        # Add name processing button
        process_names_button = QPushButton("Process Names")
        process_names_button.clicked.connect(self.process_names)
        ocr_button_layout.addWidget(process_names_button)

        # Add the OCR button layout to main layout
        layout.addLayout(ocr_button_layout)

        panel.setLayout(layout)
        return panel
    
    def setup_ai_client(self):
        """Initialize AI client with API key from environment"""
        load_dotenv()  # Try .env file first
        api_key = os.getenv('ANTHROPIC_API_KEY')  # Then system environment
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set up your API key.")
        self.client = anthropic.Anthropic(api_key=api_key)    

    def increase_font_size(self):
        """Increase the font size in the OCR text area."""
        current_font = self.ocr_text_edit.font()
        current_size = current_font.pointSize()
        if current_size < 30:  # Limit maximum font size
            current_font.setPointSize(current_size + 1)
            self.ocr_text_edit.setFont(current_font)

    def decrease_font_size(self):
        """Decrease the font size in the OCR text area."""
        current_font = self.ocr_text_edit.font()
        current_size = current_font.pointSize()
        if current_size > 8:  # Limit minimum font size
            current_font.setPointSize(current_size - 1)
            self.ocr_text_edit.setFont(current_font)

    def create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)  # Reduce overall margins

        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        recall_button = QPushButton("Recall Last Entered")
        recall_button.clicked.connect(self.recall_last_entry)
        layout.addWidget(recall_button)
        
        prev_button = QPushButton("< Previous")
        prev_button.clicked.connect(self.load_previous_event)
        next_button = QPushButton("Next >")
        next_button.clicked.connect(self.load_next_event)
        
        nav_layout.addWidget(prev_button)
        nav_layout.addWidget(next_button)
        layout.addLayout(nav_layout)

        # Metadata button
        metadata_button = QPushButton("Add Additional Metadata")
        metadata_button.clicked.connect(self.open_metadata_dialog)
        layout.addWidget(metadata_button)

        # **Event ID Display - Now Inside a Horizontal Layout**
        event_id_layout = QHBoxLayout()
        self.event_id_label = QLabel("Event ID: -")
        self.event_id_label.setStyleSheet(
            "font-weight: bold; color: black; padding: 1px 0px; margin: 0px 0px;"
        )  # Remove excess space
        
        event_id_layout.addWidget(self.event_id_label)
        event_id_layout.addStretch()  # Push it to the left
        layout.addLayout(event_id_layout)  # Add the compact layout

        # **Event info fields (Reduced Spacing)**
        form_layout = QFormLayout()
        form_layout.setSpacing(3)  # Further reduce vertical spacing
        self.event_date_input = QLineEdit()
        self.publication_date_input = QLineEdit()
        self.event_title_input = QLineEdit()
        self.source_type_input = QLineEdit()
        self.source_name_input = QLineEdit()
        
        form_layout.addRow("Event Date:", self.event_date_input)
        form_layout.addRow("Publication Date:", self.publication_date_input)
        form_layout.addRow("Event Title:", self.event_title_input)
        form_layout.addRow("Source Type:", self.source_type_input)
        form_layout.addRow("Source Name:", self.source_name_input)
        layout.addLayout(form_layout)

        # Associated items sections
        self.characters_widget = self.create_names_section("Characters")
        self.locations_widget = self.create_names_section("Locations")
        self.entities_widget = self.create_names_section("Entities")
        
        layout.addWidget(self.characters_widget)
        layout.addWidget(self.locations_widget)
        layout.addWidget(self.entities_widget)

        # Save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_data)
        layout.addWidget(save_button)

        panel.setLayout(layout)
        return panel




    def create_names_section(self, title):
        section = QGroupBox(title)
        layout = QVBoxLayout(section)

        # Input row
        input_layout = QHBoxLayout()
        name_input = QLineEdit()
        name_input.setPlaceholderText(f"Enter {title.lower()} found in Article")
        name_input.setFixedWidth(250)
        
        # Connect textChanged signal to update suggestions with modified method
        name_input.textChanged.connect(
            lambda text_input, title=title, input_widget=name_input:   
            self.update_name_suggestions(text_input, title.lower(), input_widget)
        )

        add_button = QPushButton("Add")
        input_layout.addWidget(name_input)
        input_layout.addWidget(add_button)
        layout.addLayout(input_layout)

        # Tags container with a grid layout
        tags_container = QWidget()
        tags_layout = QGridLayout(tags_container)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setHorizontalSpacing(10)
        tags_layout.setVerticalSpacing(5)
        layout.addWidget(tags_container)

        # Store tags layout reference
        setattr(self, f"{title.lower()}_tags_layout", tags_layout)

        # Connect add functionality
        add_button.clicked.connect(lambda: self.add_name_tag(name_input, title.lower()))
        name_input.returnPressed.connect(lambda: self.add_name_tag(name_input, title.lower()))

        return section

    def get_detailed_matching_names(self, text, category):
        """Get detailed matching names from database."""
        print(f"get_detailed_matching_names: Looking for '{text}' in {category}")
        matches = []
        
        try:
            if category == 'characters':
                self.db_manager.cursor.execute("""
                    SELECT CharacterID, DisplayName, FirstName, LastName, Aliases, 
                        BirthDate, DeathDate
                    FROM Characters
                    WHERE DisplayName LIKE ? OR FirstName LIKE ? OR 
                        LastName LIKE ? OR Aliases LIKE ?
                """, (f"%{text}%", f"%{text}%", f"%{text}%", f"%{text}%"))
                
                for row in self.db_manager.cursor.fetchall():
                    char_id, display_name, first_name, last_name, aliases, birth, death = row
                    
                    # Check match type
                    match_type = 'partial'
                    if display_name and display_name.lower() == text.lower():
                        match_type = 'exact'
                    elif aliases and text.lower() in [a.strip().lower() for a in aliases.split(';')]:
                        match_type = 'alias'
                    
                    # Build details string
                    details = []
                    if first_name or last_name:
                        details.append(f"{first_name or ''} {last_name or ''}".strip())
                    if birth:
                        details.append(f"Born: {birth}")
                    if death:
                        details.append(f"Died: {death}")
                    if aliases:
                        details.append(f"Aliases: {aliases}")
                    
                    matches.append({
                        'id': char_id,
                        'display_name': display_name,
                        'source': 'permanent',
                        'details': " | ".join(details) if details else "",
                        'match_type': match_type
                    })
                    
            elif category == 'locations':
                self.db_manager.cursor.execute("""
                    SELECT LocationID, DisplayName, LocationName, Aliases, 
                        Address, LocationType
                    FROM Locations 
                    WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ?
                """, (f"%{text}%", f"%{text}%", f"%{text}%"))
                
                for row in self.db_manager.cursor.fetchall():
                    loc_id, display_name, location_name, aliases, address, loc_type = row
                    
                    # Check match type
                    match_type = 'partial'
                    if display_name and display_name.lower() == text.lower():
                        match_type = 'exact'
                    elif aliases and text.lower() in [a.strip().lower() for a in aliases.split(';')]:
                        match_type = 'alias'
                    
                    # Build details string
                    details = []
                    if location_name and location_name != display_name:
                        details.append(location_name)
                    if loc_type:
                        details.append(f"Type: {loc_type}")
                    if address:
                        details.append(f"Address: {address}")
                    if aliases:
                        details.append(f"Aliases: {aliases}")
                    
                    matches.append({
                        'id': loc_id,
                        'display_name': display_name,
                        'source': 'permanent',
                        'details': " | ".join(details) if details else "",
                        'match_type': match_type
                    })
                    
            elif category == 'entities':
                self.db_manager.cursor.execute("""
                    SELECT EntityID, DisplayName, Name, Aliases, Type, 
                        EstablishedDate
                    FROM Entities 
                    WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ?
                """, (f"%{text}%", f"%{text}%", f"%{text}%"))
                
                for row in self.db_manager.cursor.fetchall():
                    ent_id, display_name, name, aliases, ent_type, established = row
                    
                    # Check match type
                    match_type = 'partial'
                    if display_name and display_name.lower() == text.lower():
                        match_type = 'exact'
                    elif aliases and text.lower() in [a.strip().lower() for a in aliases.split(';')]:
                        match_type = 'alias'
                    
                    # Build details string
                    details = []
                    if name and name != display_name:
                        details.append(name)
                    if ent_type:
                        details.append(f"Type: {ent_type}")
                    if established:
                        details.append(f"Est: {established}")
                    if aliases:
                        details.append(f"Aliases: {aliases}")
                    
                    matches.append({
                        'id': ent_id,
                        'display_name': display_name,
                        'source': 'permanent',
                        'details': " | ".join(details) if details else "",
                        'match_type': match_type
                    })

        except sqlite3.Error as e:
            print(f"Error fetching detailed name suggestions: {e}")

        # Sort matches - put exact matches first, then alias matches, then partial
        return sorted(matches, key=lambda m: (
            0 if m['match_type'] == 'exact' else 
            1 if m['match_type'] == 'alias' else 2,
            m['display_name']
        ))

    def update_name_suggestions(self, text_input, category, input_widget):
        """Update the completer with matching names from database."""
        # Create simple completer if it doesn't exist
        if not hasattr(input_widget, 'simple_completer'):
            input_widget.simple_completer = QCompleter([])
            input_widget.simple_completer.setCaseSensitivity(Qt.CaseInsensitive)
            input_widget.simple_completer.setFilterMode(Qt.MatchContains)
            input_widget.setCompleter(input_widget.simple_completer)
        
        try:
            # Only query if we have text
            if text_input and text_input.strip():
                matches = []
                
                # Query appropriate table based on category
                if category == 'characters':
                    self.db_manager.cursor.execute("""
                        SELECT DisplayName FROM Characters 
                        WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR Aliases LIKE ?
                    """, (f"%{text_input}%", f"%{text_input}%", f"%{text_input}%", f"%{text_input}%"))
                    
                elif category == 'locations':
                    self.db_manager.cursor.execute("""
                        SELECT DisplayName FROM Locations 
                        WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ?
                    """, (f"%{text_input}%", f"%{text_input}%", f"%{text_input}%"))
                    
                elif category == 'entities':
                    self.db_manager.cursor.execute("""
                        SELECT DisplayName FROM Entities 
                        WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ?
                    """, (f"%{text_input}%", f"%{text_input}%", f"%{text_input}%"))
                
                # Get all matches
                for row in self.db_manager.cursor.fetchall():
                    if row[0]:
                        matches.append(row[0])
                
                # Update the completer's model with the matches
                model = QStringListModel(matches)
                input_widget.simple_completer.setModel(model)
                
                # Force completion on first character
                if len(text_input) == 1:
                    input_widget.simple_completer.complete()
        
        except Exception as e:
            print(f"Error in update_name_suggestions: {str(e)}")

    def get_or_create_character(self, character_name):
        """Get character ID from permanent table or create new character if needed."""
        try:
            # First check if character exists
            character_id = self.db_manager.get_character_id_by_name(character_name)
            if character_id:
                return character_id

            # If not found, create in permanent table with reviewed=0
            print(f"Creating new character '{character_name}' in permanent table")
            
            # Parse name into first/last if possible
            name_parts = character_name.split()
            if len(name_parts) > 1:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
            else:
                first_name = character_name
                last_name = ""
                
            # Insert new character directly into permanent table
            character_id = self.db_manager.insert_character(
                display_name=character_name,
                first_name=first_name,
                last_name=last_name,
                reviewed=0  # Mark as needing review
            )
            print(f"Created character '{character_name}' with ID {character_id}")
            return character_id
                
        except Exception as e:
            print(f"Error in get_or_create_character: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    def get_or_create_location(self, location_name):
        """Get location ID from permanent table or create new location if needed."""
        try:
            # First check if location exists
            location_id = self.db_manager.get_location_id_by_name(location_name)
            if location_id:
                return location_id

            # If not found, create in permanent table with review status
            print(f"Creating new location '{location_name}' in permanent table")
            location_id = self.db_manager.insert_location(
                location_name=location_name,
                review_status='needs_review'
            )
            print(f"Created location '{location_name}' with ID {location_id}")
            return location_id
                
        except Exception as e:
            print(f"Error in get_or_create_location: {str(e)}")
            return None

    def get_or_create_entity(self, entity_name):
        """Get entity ID from permanent table or create new entity if needed."""
        try:
            # First check if entity exists
            entity_id = self.db_manager.get_entity_id_by_name(entity_name)
            if entity_id:
                return entity_id

            # If not found, create in permanent table with review status
            print(f"Creating new entity '{entity_name}' in permanent table")
            entity_id = self.db_manager.insert_entity(
                entity_name=entity_name,
                review_status='needs_review'
            )
            print(f"Created entity '{entity_name}' with ID {entity_id}")
            return entity_id
                
        except Exception as e:
            print(f"Error in get_or_create_entity: {str(e)}")
            return None        
        
    def get_or_create_source(self, source_name, source_type='N'):
        """Get source ID from permanent table or create new source if needed."""
        try:
            # First check if source exists
            source_id = self.db_manager.check_source_exists(source_name)
            if source_id:
                return source_id

            # If not found, create in permanent table with review status
            print(f"Creating new source '{source_name}' in permanent table")
            source_id = self.db_manager.add_preliminary_source(source_name)
            print(f"Created source '{source_name}' with ID {source_id}")
            return source_id
                
        except Exception as e:
            print(f"Error in get_or_create_source: {str(e)}")
            return None        

    def get_matching_names(self, text, category):
        """Get matching names from both permanent and transient tables."""
        print(f"Looking for '{text}' in {category} tables")
        matches = set()  # Using set to avoid duplicates
        
        try:
            # Query permanent tables
            if category == 'characters':
                print("Querying permanent Characters table")
                query = """
                    SELECT DisplayName, FirstName, LastName, Aliases 
                    FROM Characters 
                    WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR Aliases LIKE ?
                """
                self.db_manager.cursor.execute(query, 
                    (f"%{text}%", f"%{text}%", f"%{text}%", f"%{text}%"))
                
                permanent_results = self.db_manager.cursor.fetchall()
                print(f"Found {len(permanent_results)} matches in permanent Characters table")
                
                # Process results
                for row in permanent_results:
                    display_name, first_name, last_name, aliases = row
                    print(f"Match: {display_name}, {first_name}, {last_name}, {aliases}")
                    
                    if display_name:
                        matches.add(display_name)
                    if first_name and text.lower() in first_name.lower():
                        # Add full name if first name matches
                        if last_name:
                            matches.add(f"{first_name} {last_name}")
                        else:
                            matches.add(first_name)
                    if last_name and text.lower() in last_name.lower():
                        # Add full name if last name matches
                        if first_name:
                            matches.add(f"{first_name} {last_name}")
                        else:
                            matches.add(last_name)
                    if aliases:
                        for alias in aliases.split(';'):
                            alias = alias.strip()
                            if alias and text.lower() in alias.lower():
                                matches.add(alias)
                
            elif category == 'locations':
                print("Querying permanent Locations table")
                self.db_manager.cursor.execute("""
                    SELECT DisplayName, LocationName, Aliases FROM Locations 
                    WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ?
                """, (f"%{text}%", f"%{text}%", f"%{text}%"))
                
                for row in self.db_manager.cursor.fetchall():
                    if row[0]:  # Add DisplayName
                        matches.add(row[0])
                    if row[1] and text.lower() in row[1].lower():  # Add LocationName if match
                        matches.add(row[1])
                    if row[2]:  # Add Aliases
                        for alias in row[2].split(';'):
                            alias = alias.strip()
                            if alias and text.lower() in alias.lower():
                                matches.add(alias)
                        
            elif category == 'entities':
                print("Querying permanent Entities table")
                self.db_manager.cursor.execute("""
                    SELECT DisplayName, Name, Aliases FROM Entities 
                    WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ?
                """, (f"%{text}%", f"%{text}%", f"%{text}%"))
                
                for row in self.db_manager.cursor.fetchall():
                    if row[0]:  # Add DisplayName
                        matches.add(row[0])
                    if row[1] and text.lower() in row[1].lower():  # Add Name if match
                        matches.add(row[1])
                    if row[2]:  # Add Aliases
                        for alias in row[2].split(';'):
                            alias = alias.strip()
                            if alias and text.lower() in alias.lower():
                                matches.add(alias)

            # Query transient tables
            if hasattr(self, 'transient_manager'):
                if category == 'characters':
                    print("Querying transient Characters table")
                    self.transient_manager.cursor.execute("""
                        SELECT DisplayName, FirstName, LastName, Aliases FROM TransientCharacters 
                        WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR Aliases LIKE ?
                    """, (f"%{text}%", f"%{text}%", f"%{text}%", f"%{text}%"))
                    
                    transient_results = self.transient_manager.cursor.fetchall()
                    print(f"Found {len(transient_results)} matches in transient Characters table")
                    
                    # Process transient results
                    for row in transient_results:
                        display_name, first_name, last_name, aliases = row
                        print(f"Transient match: {display_name}, {first_name}, {last_name}, {aliases}")
                        
                        if display_name:
                            matches.add(display_name)
                        if first_name and text.lower() in first_name.lower():
                            # Add full name if first name matches
                            if last_name:
                                matches.add(f"{first_name} {last_name}")
                            else:
                                matches.add(first_name)
                        if last_name and text.lower() in last_name.lower():
                            # Add full name if last name matches
                            if first_name:
                                matches.add(f"{first_name} {last_name}")
                            else:
                                matches.add(last_name)
                        if aliases:
                            for alias in aliases.split(';'):
                                alias = alias.strip()
                                if alias and text.lower() in alias.lower():
                                    matches.add(alias)
                    
                elif category == 'locations':
                    print("Querying transient Locations table")
                    self.transient_manager.cursor.execute("""
                        SELECT DisplayName, LocationName, Aliases FROM TransientLocations 
                        WHERE DisplayName LIKE ? OR LocationName LIKE ? OR Aliases LIKE ?
                    """, (f"%{text}%", f"%{text}%", f"%{text}%"))
                    
                    for row in self.transient_manager.cursor.fetchall():
                        if row[0]:  # Add DisplayName
                            matches.add(row[0])
                        if row[1] and text.lower() in row[1].lower():  # Add LocationName if match
                            matches.add(row[1])
                        if row[2]:  # Add Aliases
                            for alias in row[2].split(';'):
                                alias = alias.strip()
                                if alias and text.lower() in alias.lower():
                                    matches.add(alias)
                    
                elif category == 'entities':
                    print("Querying transient Entities table")
                    self.transient_manager.cursor.execute("""
                        SELECT DisplayName, Name, Aliases FROM TransientEntities 
                        WHERE DisplayName LIKE ? OR Name LIKE ? OR Aliases LIKE ?
                    """, (f"%{text}%", f"%{text}%", f"%{text}%"))
                    
                    for row in self.transient_manager.cursor.fetchall():
                        if row[0]:  # Add DisplayName
                            matches.add(row[0])
                        if row[1] and text.lower() in row[1].lower():  # Add Name if match
                            matches.add(row[1])
                        if row[2]:  # Add Aliases
                            for alias in row[2].split(';'):
                                alias = alias.strip()
                                if alias and text.lower() in alias.lower():
                                    matches.add(alias)

        except sqlite3.Error as e:
            print(f"Error fetching name suggestions: {e}")
            import traceback
            traceback.print_exc()

        # Convert set to sorted list
        result = sorted(list(matches))
        print(f"Returning matched names: {result}")
        return result

    def add_name_tag(self, input_widget, category):
        # Retrieve the name from the input widget
        name = input_widget.text().strip()
        if name:
            # Create a tag container for the tag's visual appearance
            tag_container = QWidget()
            tag_layout = QHBoxLayout(tag_container)
            tag_layout.setContentsMargins(0, 0, 0, 0)
            tag_layout.setSpacing(5)

            # Create the tag button with DisplayName
            tag_button = QPushButton(name)
            tag_button.setStyleSheet("border-radius: 10px; padding: 5px; background-color: lightgray;")
            tag_button.setFlat(True)

            # Create remove button
            remove_button = QPushButton("X")
            remove_button.setStyleSheet("background: none; color: red; font-weight: bold;")
            remove_button.setFixedSize(15, 15)
            remove_button.clicked.connect(lambda: self.remove_name_tag(tag_container, category, name))

            # Add tag button and remove button to the tag layout
            tag_layout.addWidget(tag_button)
            tag_layout.addWidget(remove_button)

            # Add tag container to the grid layout for the category
            tags_layout = getattr(self, f"{category}_tags_layout")
            current_count = tags_layout.count()
            row = current_count // 3  # Calculate the row based on current count and max columns (3)
            col = current_count % 3  # Calculate the column based on current count and max columns (3)
            tags_layout.addWidget(tag_container, row, col)

            # Append the name to the associated list for saving
            getattr(self, f'associated_{category}').append(name)

            # Clear the input field after adding the tag
            input_widget.clear()




    def remove_name_tag(self, tag_container, category, name):
        tags_layout = getattr(self, f"{category}_tags_layout")
        tag_container.setParent(None)  # Remove the widget from the grid
        getattr(self, f'associated_{category}').remove(name)

        # Reorganize grid layout
        self.reorganize_grid_layout(tags_layout)


    def load_associated_tags(self, event_id):
        """Consolidated method to load and display associated tags."""
        associations = self.db_manager.get_event_associations(event_id)
        
        # Clear all existing tags
        for category in ['characters', 'locations', 'entities']:
            tags_layout = getattr(self, f"{category}_tags_layout")
            while tags_layout.count():
                item = tags_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            
            # Clear associated lists
            getattr(self, f'associated_{category}').clear()
            
            # Add new tags
            for name in associations[category]:
                self.add_name_tag_from_load(name, category)

    def add_name_tag_from_load(self, name, category):
        """Add a tag when loading event data."""
        # Reuse add_name_tag logic
        input_widget = QLineEdit()
        input_widget.setText(name)
        self.add_name_tag(input_widget, category)
        input_widget.deleteLater()

    # File and Image Handling
    def upload_image(self):
        """Upload and display an image or text file from the project's preprocessed folder"""
        if not hasattr(self, 'project_folder') or not self.project_folder:
            QMessageBox.warning(self, "No Project", "Please open a project first.")
            return
            
        default_folder = os.path.join(self.project_folder, "Assets", "preprocessed")
        
        if not os.path.exists(default_folder):
            QMessageBox.warning(self, "Error", "Preprocessed folder not found in current project.")
            return
            
        file_name, _ = QFileDialog.getOpenFileName(
            None,   
            "Open File",   
            default_folder,
            "All Files (*);;Image Files (*.png *.jpg *.jpeg);;Text Files (*.txt)"
        )

        if file_name:
            self.image_path = file_name
            
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                self.image_viewer.display_image(file_name)
                text_file = os.path.splitext(file_name)[0] + ".txt"
                if os.path.exists(text_file):
                    self.load_text_from_file(text_file)
                else:
                    self.ocr_text_edit.clear()
            elif file_name.lower().endswith('.txt'):
                self.load_text_from_file(file_name)
                self.find_and_display_image(file_name)
            else:
                QMessageBox.warning(None, "File Error", "Please select a valid image or text file.")
                return

            self.extract_metadata_from_filename()


    def extract_metadata_from_filename(self):
        """Extracts metadata from a filename, attempting to identify a date automatically."""
        if not self.image_path:
            return

        filename = os.path.basename(self.image_path)
        detected_date = self.detect_date_in_filename(filename)

        # If a date is found, autofill event date
        if detected_date:
            self.publication_date_input.setText(detected_date)

        # Prompt user for missing metadata
        QMessageBox.information(self, "Manual Metadata Entry",
                                "Filename parsing has been relaxed. Please manually enter missing metadata.")

    def detect_date_in_filename(self, filename):
        """Attempts to detect a date in a filename using multiple date patterns, including three-letter months."""
        date_patterns = [
            r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})',  # YYYY-MM-DD, YYYY_MM_DD, YYYYMMDD
            r'(\d{2})[-_]?(\d{2})[-_]?(\d{4})',  # MM-DD-YYYY or DD-MM-YYYY
            r'([A-Za-z]{3})[-_]?(\d{1,2})[-_]?(\d{4})',  # Mon-DD-YYYY (Apr-05-1892, Apr_05_1892)
            r'(\d{4})[-_]?([A-Za-z]{3})[-_]?(\d{1,2})',  # YYYY-Mon-DD (1892-Apr-05, 1892_Apr_5)
        ]

        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                groups = match.groups()
                try:
                    # Convert matched date to YYYY-MM-DD format
                    if len(groups) == 3:
                        if groups[0].isdigit():  # YYYY-MM-DD
                            return f"{groups[0]}-{groups[1]}-{groups[2]}"
                        elif groups[2].isdigit():  # Mon-DD-YYYY
                            return f"{groups[2]}-{self.convert_month_to_number(groups[0])}-{groups[1]}"
                        elif groups[1].isalpha():  # YYYY-Mon-DD
                            return f"{groups[0]}-{self.convert_month_to_number(groups[1])}-{groups[2]}"
                except Exception:
                    continue  # Skip errors and try the next pattern

        return None  # Return None if no date was found


    def convert_month_to_number(self, month):
        """Converts a full month name or three-letter abbreviation to its numeric representation."""
        months = {
            'January': '01', 'February': '02', 'March': '03', 'April': '04',
            'May': '05', 'June': '06', 'July': '07', 'August': '08',
            'September': '09', 'October': '10', 'November': '11', 'December': '12',
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        return months.get(month.capitalize(), '00')  # Handles both full and abbreviated month names



    def reorganize_grid_layout(self, grid_layout):
        widgets = []
        for i in range(grid_layout.count()):
            item = grid_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widgets.append(widget)

        # Clear the layout
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        # Re-add widgets to the layout in a 3-wide grid
        for index, widget in enumerate(widgets):
            row = index // 3
            col = index % 3
            grid_layout.addWidget(widget, row, col)


    def load_text_from_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.ocr_text_edit.setText(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load text file: {str(e)}")

    def find_and_display_image(self, text_file_path):
        for ext in ['.jpg', '.jpeg', '.png']:
            image_file = os.path.splitext(text_file_path)[0] + ext
            if os.path.exists(image_file):
                self.image_viewer.display_image(image_file)
                break

    def run_ocr(self):
        if self.image_path:
            try:
                img = Image.open(self.image_path)
                ocr_result = pytesseract.image_to_string(img)
                self.ocr_text_edit.setText(ocr_result)
                self.changes_made = True
            except Exception as e:
                self.ocr_text_edit.setText(f"An error occurred during OCR: {e}")
        else:
            self.ocr_text_edit.setText("No image selected for OCR.")


    def load_event_content(self, event_id):
        """Load event content and set status to editing."""
        try:
            # Set event to editing status
            self.db_manager.cursor.execute("""
                UPDATE Events 
                SET Status = 'editing' 
                WHERE EventID = ? AND Status = 'active'
            """, (event_id,))
            self.db_manager.conn.commit()

            # Load event data
            self.db_manager.cursor.execute("""
                SELECT EventDate, PublicationDate, EventTitle, EventText, 
                    SourceType, SourceName, FilePath, QualityScore
                FROM Events 
                WHERE EventID = ?
            """, (event_id,))
            event_data = self.db_manager.cursor.fetchone()

            if event_data:
                self.current_event_id = event_id
                self.event_id_label.setText(f"Event ID: {event_id}")
                
                # Load basic event details
                self.event_date_input.setText(event_data[0] or '')
                self.publication_date_input.setText(event_data[1] or '')
                self.event_title_input.setText(event_data[2] or '')
                self.ocr_text_edit.setText(event_data[3] or '')
                self.source_type_input.setText(event_data[4] or '')
                self.source_name_input.setText(event_data[5] or '')

                # Load image if available
                if event_data[6]:
                    self.image_path = event_data[6]
                    self.image_viewer.display_image(self.image_path)

                # Store quality score
                self.quality_score = event_data[7]

                # Load associated tags
                self.load_associated_tags(event_id)

                # Reset change tracking
                self.changes_made = False
                
        except sqlite3.Error as e:
            print(f"Error loading event: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load event: {e}")

    def cleanup_editing_status(self):
        """Reset editing status when leaving an event without saving."""
        if self.current_event_id:
            try:
                self.db_manager.cursor.execute("""
                    UPDATE Events 
                    SET Status = 'active' 
                    WHERE EventID = ? AND Status = 'editing'
                """, (self.current_event_id,))
                self.db_manager.conn.commit()
            except sqlite3.Error as e:
                print(f"Error cleaning up editing status: {e}")

    def recall_last_entry(self):
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT EventID FROM Events ORDER BY EventID DESC LIMIT 1")
            result = cursor.fetchone()

            if result:
                self.load_event_content(result[0])
            else:
                QMessageBox.information(self, "No Entries", "No entries are available to recall.")
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Database Error", f"Failed to recall last entry: {str(e)}")

    def load_previous_event(self):
        if not self.current_event_id:
            QMessageBox.information(self, "No Event", "No event is currently loaded.")
            return

        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("""
                SELECT EventID FROM Events 
                WHERE EventID < ? 
                ORDER BY EventID DESC LIMIT 1
            """, (self.current_event_id,))
            result = cursor.fetchone()

            if result:
                self.load_event_content(result[0])
            else:
                QMessageBox.information(self, "No More Events", "This is the first event in the database.")
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Database Error", f"Failed to load previous event: {str(e)}")

    def load_next_event(self):
            if not self.current_event_id:
                QMessageBox.information(self, "No Event", "No event is currently loaded.")
                return

            try:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("""
                    SELECT EventID FROM Events 
                    WHERE EventID > ? 
                    ORDER BY EventID ASC LIMIT 1
                """, (self.current_event_id,))
                result = cursor.fetchone()

                if result:
                    self.load_event_content(result[0])
                else:
                    QMessageBox.information(self, "No More Events", "This is the last event in the database.")
            except sqlite3.Error as e:
                QMessageBox.warning(self, "Database Error", f"Failed to load next event: {str(e)}")

    def cancel_file(self):
        """Handle cancellation of file processing."""
        if self.changes_made:
            reply = QMessageBox.warning(None, 'Warning', 
                "Unsaved changes will be lost. Do you want to proceed?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        self.clear_all_fields()

    def process_names(self):
        """Process text for potential names after OCR"""
        if not self.ocr_text_edit.toPlainText():
            QMessageBox.warning(self, "No Text", "Please perform OCR first.")
            return

        # Store the current text for reference
        self.original_text = self.ocr_text_edit.toPlainText()
        
        # Clear any existing highlights
        cursor = self.ocr_text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        
        # Initialize format for highlighting
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(255, 255, 200))  # Light yellow background
        
        # Find potential names and highlight them
        self.detected_names = []  # Store detected names for processing
        text = self.original_text
        
        # Simple name detection (we'll enhance this later)
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
            cursor = self.ocr_text_edit.textCursor()
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(name))
            cursor.mergeCharFormat(highlight_format)
        
        if self.detected_names:
            self.process_next_name()
        else:
            QMessageBox.information(self, "Name Detection", "No potential names found.")

    def process_next_name(self):
        """Process the next detected name"""
        if not hasattr(self, 'current_name_index'):
            self.current_name_index = 0
        
        if self.current_name_index < len(self.detected_names):
            name, pos = self.detected_names[self.current_name_index]
            
            # Get existing matches for this name
            existing_matches = self.get_existing_matches(name)
            
            # Create and show the dialog
            dialog = SmartNameDialog(name, existing_matches)
            if dialog.exec_():
                # Handle the dialog result
                self.handle_name_result(dialog)
            
            self.current_name_index += 1
        else:
            QMessageBox.information(self, "Complete", "All names have been processed.")
            self.current_name_index = 0

    def get_existing_matches(self, name):
        """Get existing matches for a name from the database"""
        matches = []
        
        # Search in Characters
        cursor = self.db_manager.conn.cursor()
        cursor.execute("""
            SELECT CharacterID, DisplayName, FirstName, LastName, Aliases
            FROM Characters
            WHERE DisplayName LIKE ? OR FirstName LIKE ? OR LastName LIKE ? OR Aliases LIKE ?
        """, (f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%"))
        
        for row in cursor.fetchall():
            matches.append({
                'type': 'Character',
                'id': row[0],
                'display_name': row[1],
                'details': f"{row[2]} {row[3]}",
                'aliases': row[4]
            })
        
        # Similar queries for Locations and Entities...
        # (We can add these once you show me those table structures)
        
        return matches

    def handle_name_result(self, dialog):
        """Handle the result from the SmartNameDialog"""
        if dialog.result() == QDialog.Accepted:
            if dialog.selected_entry:
                # Handle existing entry selection
                self.add_name_to_right_panel(
                    dialog.selected_entry['display_name'],
                    dialog.category_combo.currentText()
                )
            elif dialog.search_field.text():
                # Handle new entry
                self.add_name_to_right_panel(
                    dialog.search_field.text(),
                    dialog.category_combo.currentText()
                )

    def add_name_to_right_panel(self, name, category):
        """Add a name to the appropriate section in the right panel"""
        category = category.lower()
        if category == "character":
            self.add_name_tag(QLineEdit(name), "characters")
        elif category == "location":
            self.add_name_tag(QLineEdit(name), "locations")
        elif category == "entity":
            self.add_name_tag(QLineEdit(name), "entities")

    def open_metadata_dialog(self):
        metadata_dialog = QDialog()
        metadata_dialog.setWindowTitle("Add Additional Metadata")
        layout = QFormLayout()

        # Create a dictionary to store the input fields
        input_fields = {}

        # Event Date (read-only)
        event_date = QLineEdit(self.event_date_input.text())
        event_date.setReadOnly(True)
        layout.addRow("Event Date:", event_date)

        # Add other fields here
        fields = [
            ('publication_date', "Publication Date (if different than Event Date):"),
            ('journal_title', "Journal/Book Title:"),
            ('volume', "Volume/Edition:"),
            ('issue_number', "Issue Number:"),
            ('page_number', "Page Number:"),
            ('column_number', "Column Number:"),
            ('authors', "Author(s):"),
            ('doi_url', "DOI or URL:"),
            ('archive_location', "Archive Location:")
        ]

        for field, label in fields:
            input_fields[field] = QLineEdit(self.metadata.get(field, ''))
            layout.addRow(label, input_fields[field])

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(metadata_dialog.accept)
        button_box.rejected.connect(metadata_dialog.reject)
        layout.addWidget(button_box)

        metadata_dialog.setLayout(layout)

        if metadata_dialog.exec_() == QDialog.Accepted:
            for field, input_widget in input_fields.items():
                if input_widget.text():
                    self.metadata[field] = input_widget.text()
            QMessageBox.information(None, "Metadata Ready", "Metadata has been prepared for saving.")
        else:
            QMessageBox.information(None, "Cancelled", "No changes were made to the metadata.")

    def populate_metadata_from_filename(self):
        if self.image_path:
            filename = os.path.basename(self.image_path)
            try:
                filename_data = self.parse_filename(filename)
                if filename_data:
                    date_part = filename_data['event_date']
                    self.event_date_input.setText(date_part)
                    self.metadata['publication_date'] = date_part
                    self.event_title_input.setText(filename_data['event_title'])
                    self.source_type_input.setText(filename_data['source_type'])
                    self.source_name_input.setText(filename_data['source_name'])
                    self.metadata['page_number'] = filename_data['page_number']
            except ValueError as e:
                QMessageBox.warning(self, "Filename Error", str(e))

    def parse_filename(self, filename):
        try:
            parts = filename.split('_')
            if len(parts) < 5:
                raise ValueError("Filename does not match the expected format.")
            
            date = parts[0]
            event_title = parts[1]
            source_type_code = parts[2]
            source_name = parts[3]
            page_number = parts[4]
            
            source_code = parts[5].split('.')[0] if len(parts) > 5 else 'XX'
            
            source_type_mapping = {
                'N': 'N - Newspaper',
                'B': 'B - Book',
                'J': 'J - Journal',
                'M': 'M - Magazine',
                'W': 'W - Wikipedia',
                'D': 'D - Diary/Personal Journal',
                'L': 'L - Letter/Correspondence',
                'G': 'G - Government Document',
                'C': 'C - Court Record',
                'R': 'R - Religious Record',
                'S': 'S - Ship Record/Manifest',
                'P': 'P - Photograph',
                'A': 'A - Academic Paper',
                'T': 'T - Trade Publication',
                'I': 'I - Interview Transcript',
                'O': 'O - Other'
            }
            
            source_type_full = source_type_mapping.get(source_type_code, source_type_code)
            
            actual_source_name = source_name
            if source_code != 'XX':
                cursor = self.db_manager.conn.cursor()
                cursor.execute("SELECT SourceName FROM Sources WHERE SourceCode = ?", (source_code,))
                result = cursor.fetchone()
                if result:
                    actual_source_name = result[0]
            
            return {
                'event_date': date,
                'event_title': event_title,
                'source_type': source_type_full,
                'source_name': actual_source_name,
                'page_number': page_number,
                'source_code': source_code
            }
            
        except Exception as e:
            QMessageBox.warning(self, "Filename Error", 
                f"The filename does not match the expected format. Please enter the metadata manually.\n\nError: {str(e)}")
            return None

    def is_default_title(self, title):
        """
        Check if the title is a default title (with or without numbering).
        Returns True for titles like "Enter Event Title", "Enter Event Title(2)", etc.
        """
        # Remove any leading/trailing whitespace
        title = title.strip()
        
        # Check for exact match of default title
        if title == "Enter Event Title":
            return True
            
        # Check for numbered versions like "Enter Event Title(2)"
        if title.startswith("Enter Event Title("):
            # Check if it ends with a closing parenthesis
            if title.endswith(")"):
                # Try to extract and convert the number
                try:
                    # Get the text between "Enter Event Title(" and ")"
                    number_part = title[len("Enter Event Title("):-1]
                    # Try to convert it to an integer
                    int(number_part)
                    # If we get here, it's a valid numbered default title
                    return True
                except ValueError:
                    # If we can't convert to integer, it's not a default title
                    return False
                    
        return False

    def run_ai_assisted_ocr(self):
        """Run AI-assisted OCR process"""
        if not self.image_path:
            QMessageBox.warning(self, "No Image", "Please load an image first.")
            return

        dialog = AIAssistedOCRDialog(self, self.image_path)
        if dialog.exec_():
            # Get result from dialog
            self.ocr_text_edit.setText(dialog.get_result())
            self.changes_made = True

    def insert_character(self, display_name, first_name=None, last_name=None, reviewed=0, **kwargs):
        """Insert a new character into the Characters table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO Characters (
                    DisplayName, FirstName, LastName, Reviewed
                ) VALUES (?, ?, ?, ?)
            """, (display_name, first_name, last_name, reviewed))
            self.conn.commit()
            cursor.execute("SELECT CharacterID FROM Characters WHERE DisplayName = ?", (display_name,))
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting character: {e}")
            return None

    def insert_location(self, location_name, review_status='needs_review', **kwargs):
        """Insert a new location into the Locations table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO Locations (
                    DisplayName, LocationName, ReviewStatus
                ) VALUES (?, ?, ?)
            """, (location_name, location_name, review_status))
            self.conn.commit()
            cursor.execute("SELECT LocationID FROM Locations WHERE DisplayName = ?", (location_name,))
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting location: {e}")
            return None

    def insert_entity(self, display_name, review_status='needs_review', **kwargs):
        """Insert a new entity into the Entities table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO Entities (
                    DisplayName, Name, ReviewStatus
                ) VALUES (?, ?, ?)
            """, (display_name, display_name, review_status))
            self.conn.commit()
            cursor.execute("SELECT EntityID FROM Entities WHERE DisplayName = ?", (display_name,))
            return cursor.fetchone()[0]
        except Error as e:
            print(f"Error inserting entity: {e}")
            return None

    def save_data(self):
        try:
            # Check if modifying an existing event or creating a new one
            is_new_event = self.current_event_id is None

            # Validate title
            title = self.event_title_input.text().strip()
            if self.is_default_title(title):
                QMessageBox.warning(self, "Invalid Title", 
                                "Please provide a meaningful title for this event before saving.")
                self.event_title_input.setFocus()
                return

            # Get basic event data
            event_date = self.event_date_input.text().strip()
            publication_date = self.publication_date_input.text().strip()
            source_type = self.source_type_input.text().strip()
            source_name = self.source_name_input.text().strip()
            text_content = self.ocr_text_edit.toPlainText().strip()

            # Check required fields
            if not publication_date or not title:
                QMessageBox.warning(self, "Missing Data", "Publication Date and Event Title are required fields.")
                return

            # Check if any changes were made to an existing event
            existing_data = self.db_manager.get_event_by_id(self.current_event_id) if not is_new_event else None
            changes_detected = is_new_event or self.detect_changes(existing_data)

            if not changes_detected:
                QMessageBox.information(self, "No Changes Detected", 
                                    "No changes were made. The event was not updated.")
                return

            # Show confirmation dialog before saving
            save_dialog = self.prepare_save_dialog(is_new_event, existing_data)
            if save_dialog.exec_() != QDialog.Accepted:
                return

            # Define directory paths for saving
            entered_events_dir = os.path.join("C:", "AI", "Nova", "assets", "EnteredEvents")
            os.makedirs(entered_events_dir, exist_ok=True)

            # Handle source first
            source_id = self.db_manager.get_or_create_source(source_name, source_type) if source_name else None

            # Start transaction
            self.db_manager.cursor.execute("BEGIN TRANSACTION")

            try:
                if is_new_event:
                    # Insert new event
                    self.db_manager.cursor.execute("""
                        INSERT INTO Events (
                            EventDate, PublicationDate, EventTitle, EventText, 
                            SourceType, SourceName, SourceID, Status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                    """, (event_date, publication_date, title, text_content, 
                        source_type, source_name, source_id))
                    event_id = self.db_manager.cursor.lastrowid
                else:
                    # Archive the old version
                    self.db_manager.cursor.execute("""
                        UPDATE Events 
                        SET Status = 'archived' 
                        WHERE EventID = ?
                    """, (self.current_event_id,))
                    
                    # Create new version
                    self.db_manager.cursor.execute("""
                        INSERT INTO Events (
                            EventDate, PublicationDate, EventTitle, EventText,
                            SourceType, SourceName, SourceID, Status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                    """, (event_date, publication_date, title, text_content,
                        source_type, source_name, source_id))
                    event_id = self.db_manager.cursor.lastrowid

                # Handle file paths if image exists
                if self.image_path:
                    original_filename = os.path.splitext(os.path.basename(self.image_path))[0]
                    text_file_path = os.path.join(entered_events_dir, f"{original_filename}.txt")
                    with open(text_file_path, 'w', encoding='utf-8') as f:
                        f.write(text_content)

                    new_image_path = os.path.join(entered_events_dir, os.path.basename(self.image_path))
                    shutil.copy2(self.image_path, new_image_path)

                    self.db_manager.cursor.execute("""
                        UPDATE Events 
                        SET Filename = ?, FilePath = ? 
                        WHERE EventID = ?
                    """, (os.path.basename(new_image_path), new_image_path, event_id))

                # Clear old associations if this is an edit
                if not is_new_event:
                    self.db_manager.clear_event_associations(event_id)

                # Process associated items
                for character in self.associated_characters:
                    character_id = self.db_manager.get_or_create_character(character)
                    if character_id:
                        self.db_manager.link_event_character(event_id, character_id)

                for location in self.associated_locations:
                    location_id = self.db_manager.get_or_create_location(location)
                    if location_id:
                        self.db_manager.link_event_location(event_id, location_id)

                for entity in self.associated_entities:
                    entity_id = self.db_manager.get_or_create_entity(entity)
                    if entity_id:
                        self.db_manager.link_event_entity(event_id, entity_id)

                # Process metadata
                for key, value in self.metadata.items():
                    if value:
                        self.db_manager.insert_event_metadata(event_id, key, value)

                # Commit changes
                self.db_manager.conn.commit()
                self.current_event_id = event_id
                QMessageBox.information(self, "Success", f"Event saved successfully with ID: {event_id}")
                self.clear_all_fields()

            except Exception as e:
                self.db_manager.conn.rollback()
                QMessageBox.critical(self, "Save Failed", f"Error while saving: {str(e)}")
                raise

        except Exception as e:
            print(f"Error in save_data: {str(e)}")



    def detect_changes(self, existing_data):
        """Compare the current fields against existing event data to determine if any changes were made."""
        if not existing_data:
            return True  # If no existing data, assume it's a new event
            
        try:
            event_fields = {
                "event_date": self.event_date_input.text(),
                "publication_date": self.publication_date_input.text(),
                "title": self.event_title_input.text().strip(),
                "source_type": self.source_type_input.text(),
                "source_name": self.source_name_input.text(),
                "text_content": self.ocr_text_edit.toPlainText()
            }

            for key, new_value in event_fields.items():
                # Handle possible None values safely
                old_value = ""
                if key in existing_data and existing_data[key] is not None:
                    old_value = str(existing_data[key]).strip()
                    
                new_value = str(new_value).strip()
                
                if old_value != new_value:
                    print(f"Change detected in {key}: '{old_value}' -> '{new_value}'")
                    return True  # Found a change

            return False  # No changes detected
            
        except Exception as e:
            print(f"Error in detect_changes: {str(e)}")
            # If we have an error, assume there are changes to be safe
            return True

    def update_event_associations(self, event_id):
        """Update character, location, and entity associations for the given event."""
        # Remove previous associations
        self.db_manager.remove_event_associations(event_id)

        # Add updated associations
        for character in self.associated_characters:
            character_id = self.db_manager.insert_or_get_character(character)
            self.db_manager.link_event_character(event_id, character_id)

        for location in self.associated_locations:
            location_id = self.db_manager.insert_or_get_location(location)
            self.db_manager.link_event_location(event_id, location_id)

        for entity in self.associated_entities:
            entity_id = self.db_manager.insert_or_get_entity(entity)
            self.db_manager.link_event_entity(event_id, entity_id)

    def compare_event_data(self, existing_data):
        """Compare existing data with current form data."""
        changes = []
        current_data = {
            "Event Date": self.event_date_input.text(),
            "Publication Date": self.publication_date_input.text(),
            "Title": self.event_title_input.text(),
            "Source Type": self.source_type_input.text(),
            "Source Name": self.source_name_input.text(),
            "Text Content": self.ocr_text_edit.toPlainText()
        }

        if existing_data:
            for field, new_value in current_data.items():
                old_value = str(existing_data.get(field.lower().replace(" ", "_"), "")).strip()
                new_value = str(new_value).strip()
                if old_value != new_value:
                    changes.append((field, old_value, new_value))

        return changes


    def prepare_save_dialog(self, is_new_event, existing_data=None):
        save_info = QDialog(self)
        save_info.setWindowTitle("Confirm Save")
        layout = QVBoxLayout(save_info)
        
        info_text = QTextEdit()
        info_text.setReadOnly(True)

        # **Display Event ID and Save Type**
        save_details = [f"Event ID: {'(New Transient Event Prepared For Entry)' if is_new_event else self.current_event_id}"]
        save_details.append("\nThe following information will be saved:\n")

        # **Modify Dialog Based on New vs. Update**
        if is_new_event:
            save_details.append("(New Event will be created)")
        else:
            save_details.append("(Existing Event will be updated)")
            save_details.append("\nChanges Detected:\n")

            # Show modified fields only
            for field_name, old_value, new_value in self.compare_event_data(existing_data):
                save_details.append(f"- {field_name}: {old_value} → {new_value}")

        # Add main event details
        save_details.extend([
            "\nEvent Details:",
            f"- Event Date: {self.event_date_input.text()}",
            f"- Publication Date: {self.publication_date_input.text()}",
            f"- Title: {self.event_title_input.text()}",
            f"- Source Type: {self.source_type_input.text()}",
            f"- Source Name: {self.source_name_input.text()}\n"
        ])

        # Add associated items
        if self.associated_characters:
            save_details.append("\nCharacters:")
            for char in self.associated_characters:
                save_details.append(f"- {char}")

        if self.associated_locations:
            save_details.append("\nLocations:")
            for loc in self.associated_locations:
                save_details.append(f"- {loc}")

        if self.associated_entities:
            save_details.append("\nEntities:")
            for ent in self.associated_entities:
                save_details.append(f"- {ent}")

        info_text.setText("\n".join(save_details))
        info_text.setMinimumSize(400, 300)
        layout.addWidget(info_text)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(save_info.accept)
        button_box.rejected.connect(save_info.reject)
        layout.addWidget(button_box)
        
        return save_info


    def clear_all_fields(self):
        """Clear all input fields after successful save"""
        try:
            self.event_date_input.clear()
            self.publication_date_input.clear()
            self.event_title_input.clear()
            self.source_type_input.clear()
            self.source_name_input.clear()
            self.ocr_text_edit.clear()
            
            # Clear associated items
            for category in ['characters', 'locations', 'entities']:
                tags_layout = getattr(self, f"{category}_tags_layout")
                while tags_layout.count():
                    item = tags_layout.takeAt(0)
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                
                # Clear associated lists
                getattr(self, f'associated_{category}').clear()

            # Clear metadata
            self.metadata.clear()
            
            # Clear image
            self.image_path = None
            if hasattr(self, 'image_viewer') and self.image_viewer.scene():
                self.image_viewer.scene().clear()
            
            # Reset flags
            self.changes_made = False
            self.current_event_id = None
            
        except Exception as e:
            print(f"Error in clear_all_fields: {str(e)}")

    def open_enhanced_ocr(self):
        if not self.image_path:
            QMessageBox.warning(self, "No Image", "Please load an image first.")
            return
            
        dialog = EnhancedOCRDialog(self, self.image_path)
        dialog.exec_()

    def test_character_save(self):
        """Test function to add a character directly to database"""
        try:
            # Test insert a character
            test_name = f"Test Character {datetime.now().strftime('%H:%M:%S')}"
            character_id = self.db_manager.insert_character(
                display_name=test_name,
                first_name="Test",
                last_name="Character",
                aliases="TestAlias1; TestAlias2"
            )
            
            if character_id:
                self.db_manager.cursor.execute(
                    "SELECT * FROM Characters WHERE CharacterID = ?", 
                    (character_id,)
                )
                result = self.db_manager.cursor.fetchone()
                
                if result:
                    columns = [description[0] for description in self.db_manager.cursor.description]
                    char_data = dict(zip(columns, result))
                    details = "\n".join([f"{col}: {val}" for col, val in char_data.items()])
                    
                    QMessageBox.information(
                        self, 
                        "Character Added Successfully", 
                        f"Added character to Characters table:\n{details}"
                    )
                else:
                    QMessageBox.warning(
                        self, 
                        "Character Not Found", 
                        "Character was not found after insertion."
                    )
                    
                # Test name matching
                matches = self.get_matching_names("Test", "characters")
                match_text = "\n".join(matches) if matches else "No matches found"
                QMessageBox.information(
                    self,
                    "Matching Test",
                    f"get_matching_names results for 'Test':\n{match_text}"
                )
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            QMessageBox.critical(
                self, 
                "Error Testing Character Save", 
                f"An error occurred:\n{str(e)}\n\nTraceback:\n{tb}"
            )

    def test_db_connections(self):
        """Debug function to test database connections and character retrieval"""
        try:
            # Test permanent database
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM Characters")
            perm_count = self.db_manager.cursor.fetchone()[0]
            
            # Test transient database
            self.transient_manager.cursor.execute("SELECT COUNT(*) FROM TransientCharacters")
            trans_count = self.transient_manager.cursor.fetchone()[0]
            
            # Get some sample characters from permanent DB
            self.db_manager.cursor.execute("""
                SELECT CharacterID, DisplayName FROM Characters LIMIT 3
            """)
            perm_chars = self.db_manager.cursor.fetchall()
            
            # Get some sample characters from transient DB
            self.transient_manager.cursor.execute("""
                SELECT CharacterID, DisplayName FROM TransientCharacters LIMIT 3
            """)
            trans_chars = self.transient_manager.cursor.fetchall()
            
            # Show results
            message = f"""Database Connection Test:
            
    Permanent Characters count: {perm_count}
    Sample permanent characters: {', '.join([row[1] for row in perm_chars]) if perm_chars else 'None'}

    Transient Characters count: {trans_count}
    Sample transient characters: {', '.join([row[1] for row in trans_chars]) if trans_chars else 'None'}
            """
            
            QMessageBox.information(self, "Database Test", message)
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Error testing database connections: {str(e)}") 

    def test_dropdown(self):
        """Test the dropdown functionality with sample data"""
        print("Running test_dropdown...")
        
        # Try to find the character input field more reliably
        name_input = None
        for widget in self.findChildren(QLineEdit):
            if hasattr(widget, 'placeholderText') and "character" in widget.placeholderText().lower():
                name_input = widget
                print(f"Found character input field with placeholder: {widget.placeholderText()}")
                break
        
        if not name_input:
            print("Couldn't find character input by placeholder, trying direct search in Characters widget")
            if hasattr(self, 'characters_widget'):
                for widget in self.characters_widget.findChildren(QLineEdit):
                    print(f"Found input in characters_widget with placeholder: {widget.placeholderText()}")
                    name_input = widget
                    break
        
        if not name_input:
            QMessageBox.warning(self, "Test Error", "Could not find name input field")
            return
        
        print(f"Using input field with placeholder: {name_input.placeholderText()}")
        
        # Create a test completer if needed
        if not hasattr(name_input, 'rich_completer'):
            print("Creating new rich completer")
            name_input.rich_completer = RichItemCompleter(name_input)
        
        # Create some sample matches
        sample_matches = [
            {
                'id': 1,
                'display_name': 'John Smith',
                'source': 'permanent',
                'details': 'Born: 1980 | Aliases: Johnny, JS',
                'match_type': 'exact'
            },
            {
                'id': 2,
                'display_name': 'Jane Smith',
                'source': 'permanent',
                'details': 'Born: 1982 | Died: 2020',
                'match_type': 'partial'
            },
            {
                'id': 't_3',
                'display_name': 'James Johnson',
                'source': 'transient',
                'details': 'New transient character',
                'match_type': 'alias'
            }
        ]
        
        # Update the completer with these matches
        print("Updating completer with sample matches")
        name_input.rich_completer.update_matches(sample_matches)
        
        # Focus the input field to ensure dropdown shows properly
        name_input.setFocus()
        
        QMessageBox.information(self, "Test Dropdown", 
                            "A test dropdown with 3 sample entries should appear below the Character input field")                   

    def test_basic_completion(self):
        """Test with a simple standard QCompleter to isolate issues"""
        print("Testing basic completion functionality")
        
        # Get the Character input field
        input_field = None
        for widget in self.findChildren(QLineEdit):
            if hasattr(widget, 'placeholderText') and "character" in widget.placeholderText().lower():
                input_field = widget
                break
        
        if not input_field:
            QMessageBox.warning(self, "Test Error", "Could not find input field for testing")
            return
        
        # Clear any existing completer
        input_field.setCompleter(None)
        
        # Create a simple string list completer
        simple_completer = QCompleter(["John Smith", "Jane Doe", "James Johnson"], input_field)
        simple_completer.setCaseSensitivity(Qt.CaseInsensitive)
        simple_completer.setFilterMode(Qt.MatchContains)
        
        # Set it on the input field
        input_field.setCompleter(simple_completer)
        
        # Focus the field
        input_field.setFocus()
        input_field.clear()
        
        QMessageBox.information(self, "Basic Completer Test", 
                            "A simple completer has been set up. Try typing 'j' in the character field.")

    def test_character_save(self):
        """Test function to add a character directly to the transient table"""
        try:
            # Check if transient table has the right structure
            self.transient_manager.cursor.execute("PRAGMA table_info(TransientCharacters)")
            columns = self.transient_manager.cursor.fetchall()
            print(f"TransientCharacters columns: {[col[1] for col in columns]}")
            
            # Insert a test character
            test_name = f"Test Character {datetime.now().strftime('%H:%M:%S')}"
            self.transient_manager.cursor.execute("""
                INSERT INTO TransientCharacters (
                    DisplayName, FirstName, LastName, Aliases
                ) VALUES (?, ?, ?, ?)
            """, (test_name, "Test", "Character", "TestAlias1; TestAlias2"))
            
            self.transient_manager.conn.commit()
            
            # Verify it was added
            self.transient_manager.cursor.execute(
                "SELECT * FROM TransientCharacters WHERE DisplayName = ?", 
                (test_name,)
            )
            result = self.transient_manager.cursor.fetchone()
            
            if result:
                columns = [description[0] for description in self.transient_manager.cursor.description]
                char_data = dict(zip(columns, result))
                details = "\n".join([f"{col}: {val}" for col, val in char_data.items()])
                
                QMessageBox.information(
                    self, 
                    "Character Added Successfully", 
                    f"Added character to TransientCharacters table:\n{details}"
                )
            else:
                QMessageBox.warning(
                    self, 
                    "Character Not Found", 
                    "Character was not found after insertion. This suggests a transaction issue."
                )
                
            # Check if the get_matching_names finds this character
            matches = self.get_matching_names("Test", "characters")
            match_text = "\n".join(matches) if matches else "No matches found"
            QMessageBox.information(
                self,
                "Matching Test",
                f"get_matching_names results for 'Test':\n{match_text}"
            )
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            QMessageBox.critical(
                self, 
                "Error Testing Character Save", 
                f"An error occurred:\n{str(e)}\n\nTraceback:\n{tb}"
            )

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setScene(QGraphicsScene(self))
        
        self.image_item = None
        self.selection_rect = None
        self.start_pos = None
        self.drawing_fill_color = QColor(255, 200, 200, 64)  # Light pink for active drawing

    def mousePressEvent(self, event):
        if self.dragMode() == QGraphicsView.NoDrag and event.button() == Qt.LeftButton:
            self.start_pos = self.mapToScene(event.pos())
            if not self.selection_rect:
                self.selection_rect = QGraphicsRectItem()
                self.selection_rect.setPen(QPen(Qt.red, 2))
                self.selection_rect.setBrush(QBrush(self.drawing_fill_color))
                self.scene().addItem(self.selection_rect)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selection_rect and self.start_pos:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self.start_pos, current_pos).normalized()
            self.selection_rect.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.selection_rect and event.button() == Qt.LeftButton:
            self.start_pos = None
        super().mouseReleaseEvent(event)

    def display_image(self, file_path):
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.scene().clear()
            self.image_item = self.scene().addPixmap(pixmap)
            self.setSceneRect(self.scene().itemsBoundingRect())
            self.fitInView(self.image_item, Qt.KeepAspectRatio)

    def get_selection_rect(self):
        """Return the current selection rectangle in image coordinates."""
        if self.selection_rect:
            scene_rect = self.selection_rect.rect()
            if self.image_item:
                # Convert scene coordinates to image coordinates
                scene_to_image = self.image_item.transform().inverted()[0]
                return scene_to_image.mapRect(scene_rect)
        return None            

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale(factor, factor)


class EnhancedOCRDialog(QDialog):
    def __init__(self, parent=None, image_path=None):
        super().__init__(parent)
        self.image_path = image_path
        self.current_selection = None
        self.selections = []
        self.enhancement_values = {
            'contrast': 1.0,
            'brightness': 1.0,
            'sharpness': 1.0
        }
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Enhanced OCR Processing")
        self.setMinimumSize(1200, 800)
        
        # Main layout
        main_layout = QHBoxLayout(self)
        
        # Left side - Image viewer and toggle
        left_panel = QVBoxLayout()
        
        self.image_viewer = ZoomableGraphicsView()
        if self.image_path:
            self.image_viewer.display_image(self.image_path)
        left_panel.addWidget(self.image_viewer, stretch=1)
        
        # Add toggle and clear buttons below viewer
        button_container = QHBoxLayout()
        
        self.selection_toggle = QPushButton("Toggle Selection Mode")
        self.selection_toggle.setCheckable(True)
        self.selection_toggle.toggled.connect(self.toggle_selection_mode)
        button_container.addWidget(self.selection_toggle)
        
        clear_selection_button = QPushButton("Clear Selection")
        clear_selection_button.clicked.connect(self.clear_selection)
        button_container.addWidget(clear_selection_button)
        
        left_panel.addLayout(button_container)
        
        # Create a widget to hold the left panel layout
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        main_layout.addWidget(left_widget, stretch=2)
        
        # Right side - Controls and preview
        right_widget = QWidget()
        right_panel = QVBoxLayout(right_widget)
        
        # Enhancement controls
        controls_group = QGroupBox("Enhancement Controls")
        controls_layout = QVBoxLayout()
        
        # Add sliders
        self.sliders = {}
        for control in ['Contrast', 'Brightness', 'Sharpness']:
            slider_layout = QHBoxLayout()
            label = QLabel(f"{control}:")
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(200)
            slider.setValue(100)  # Default value (1.0)
            slider.valueChanged.connect(lambda v, c=control.lower(): self.update_enhancement(c, v/100))
            value_label = QLabel("1.0")
            slider.valueChanged.connect(lambda v, l=value_label: l.setText(f"{v/100:.1f}"))
            
            slider_layout.addWidget(label)
            slider_layout.addWidget(slider)
            slider_layout.addWidget(value_label)
            controls_layout.addLayout(slider_layout)
            self.sliders[control.lower()] = slider
            
        controls_group.setLayout(controls_layout)
        right_panel.addWidget(controls_group)
        
        # OCR Preview
        preview_group = QGroupBox("OCR Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QTextEdit()
        preview_layout.addWidget(self.preview_text)
        
        # Create button layout before adding buttons
        button_layout = QHBoxLayout()
        
        # Run OCR button
        run_ocr_button = QPushButton("Run OCR on Selection")
        run_ocr_button.clicked.connect(self.run_selection_ocr)
        button_layout.addWidget(run_ocr_button)
        
        # Clear button
        clear_button = QPushButton("Clear Preview")
        clear_button.clicked.connect(self.preview_text.clear)
        button_layout.addWidget(clear_button)
        
        # Add to main button
        add_button = QPushButton("Add to Main")
        add_button.clicked.connect(self.add_to_main)
        button_layout.addWidget(add_button)
        
        # Add button layout to preview layout
        preview_layout.addLayout(button_layout)
        
        preview_group.setLayout(preview_layout)
        right_panel.addWidget(preview_group)
        
        main_layout.addWidget(right_widget, stretch=1)

    def toggle_selection_mode(self, enabled):
        """Toggle between selection and pan modes"""
        if enabled:
            self.image_viewer.setDragMode(QGraphicsView.NoDrag)
        else:
            self.image_viewer.setDragMode(QGraphicsView.ScrollHandDrag)   

    def update_enhancement(self, control_name, value):
        """Update image enhancement based on slider values"""
        self.enhancement_values[control_name] = value
        self.apply_enhancements(preview=True)  # Added preview parameter

    def apply_enhancements(self, preview=False):
        """Apply current enhancement values to selected area"""
        if not self.image_viewer.selection_rect:
            return

        try:
            # Get the selected area
            rect = self.image_viewer.get_selection_rect()
            if rect and self.image_path:
                img = Image.open(self.image_path)
                # Crop to selection
                selection = img.crop((rect.left(), rect.top(), rect.right(), rect.bottom()))
                
                # Apply enhancements
                if selection:
                    if self.enhancement_values['contrast'] != 1.0:
                        selection = ImageEnhance.Contrast(selection).enhance(self.enhancement_values['contrast'])
                    if self.enhancement_values['brightness'] != 1.0:
                        selection = ImageEnhance.Brightness(selection).enhance(self.enhancement_values['brightness'])
                    if self.enhancement_values['sharpness'] != 1.0:
                        selection = ImageEnhance.Sharpness(selection).enhance(self.enhancement_values['sharpness'])
                    
                    # Convert enhanced selection to QPixmap
                    enhanced_pixmap = self.pil_to_qpixmap(selection)
                    
                    # Update the preview in the viewer
                    if preview:
                        # Remove old preview if it exists
                        if hasattr(self, 'preview_item'):
                            self.image_viewer.scene().removeItem(self.preview_item)
                        
                        # Create new preview item
                        self.preview_item = QGraphicsPixmapItem(enhanced_pixmap)
                        self.preview_item.setPos(rect.left(), rect.top())
                        self.image_viewer.scene().addItem(self.preview_item)
                        
                        # Make sure preview stays on top
                        self.preview_item.setZValue(1)
                        if self.image_viewer.selection_rect:
                            self.image_viewer.selection_rect.setZValue(2)

        except Exception as e:
            QMessageBox.warning(self, "Enhancement Error", str(e))

    def run_selection_ocr(self):
        """Run OCR on the selected and enhanced area"""
        if not self.image_viewer.selection_rect:
            QMessageBox.warning(self, "No Selection", "Please select an area first.")
            return

        try:
            # Get the selected area
            rect = self.image_viewer.get_selection_rect()
            if rect and self.image_path:
                # Open and crop image
                img = Image.open(self.image_path)
                selection = img.crop((rect.left(), rect.top(), rect.right(), rect.bottom()))
                
                # Apply current enhancements
                if self.enhancement_values['contrast'] != 1.0:
                    selection = ImageEnhance.Contrast(selection).enhance(self.enhancement_values['contrast'])
                if self.enhancement_values['brightness'] != 1.0:
                    selection = ImageEnhance.Brightness(selection).enhance(self.enhancement_values['brightness'])
                if self.enhancement_values['sharpness'] != 1.0:
                    selection = ImageEnhance.Sharpness(selection).enhance(self.enhancement_values['sharpness'])

                # Convert to grayscale for better OCR
                selection = selection.convert("L")
                
                # Run OCR
                ocr_result = pytesseract.image_to_string(selection)
                
                # Display result in preview
                self.preview_text.setText(ocr_result)

        except Exception as e:
            QMessageBox.warning(self, "OCR Error", f"Error during OCR: {str(e)}")

    def clear_selection(self):
        """Clear the current selection box and enhancement preview"""
        if hasattr(self, 'preview_item'):
            self.image_viewer.scene().removeItem(self.preview_item)
            self.preview_item = None
        if self.image_viewer.selection_rect:
            self.image_viewer.scene().removeItem(self.image_viewer.selection_rect)
            self.image_viewer.selection_rect = None            

    def pil_to_qpixmap(self, pil_image):
        """Convert PIL image to QPixmap"""
        import numpy as np
        from PyQt5.QtGui import QImage
        
        # Convert PIL image to numpy array
        img_array = np.array(pil_image)
        height, width = img_array.shape[:2]
        
        # Create QImage from numpy array
        if len(img_array.shape) == 2:  # Grayscale
            qimage = QImage(img_array.data, width, height, width, QImage.Format_Grayscale8)
        else:  # RGB/RGBA
            bytes_per_line = 3 * width
            qimage = QImage(img_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        return QPixmap.fromImage(qimage)                     

    def add_to_main(self):
        """Add the preview text to the main OCR text area and highlight the processed area"""
        preview_text = self.preview_text.toPlainText()
        if preview_text:
            # Add text to main window
            main_text_edit = self.parent().ocr_text_edit
            if main_text_edit.toPlainText():
                main_text_edit.append("\n")
            main_text_edit.append(preview_text)
            
            # Create yellow highlight for processed area
            if self.image_viewer.selection_rect:
                rect = self.image_viewer.selection_rect.rect()
                highlight = QGraphicsRectItem(rect)
                highlight.setPen(QPen(QColor(255, 255, 0, 64)))
                highlight.setBrush(QBrush(QColor(255, 255, 0, 64)))
                self.image_viewer.scene().addItem(highlight)
                
                # Remove the red selection rectangle
                self.image_viewer.scene().removeItem(self.image_viewer.selection_rect)
                self.image_viewer.selection_rect = None
            
            # Clear the preview
            self.preview_text.clear()


class SmartNameDialog(QDialog):
    def __init__(self, name, existing_matches=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Name")
        self.name = name
        self.existing_matches = existing_matches or []
        self.category = None
        self.selected_entry = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Name display
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        name_label = QLabel(self.name)
        name_label.setFont(QFont("Arial", 10, QFont.Bold))
        name_layout.addWidget(name_label)
        layout.addLayout(name_layout)

        # Category selection
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Character", "Location", "Entity"])
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        category_layout.addWidget(self.category_combo)
        layout.addLayout(category_layout)

        # Existing entries section
        matches_group = QGroupBox("Existing Entries")
        matches_layout = QVBoxLayout()
        
        # Search/filter field
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Type to search or add new entry...")
        self.search_field.textChanged.connect(self.update_matches)
        matches_layout.addWidget(self.search_field)
        
        # Matches list
        self.matches_list = QListWidget()
        self.matches_list.itemClicked.connect(self.on_match_selected)
        matches_layout.addWidget(self.matches_list)
        
        matches_group.setLayout(matches_layout)
        layout.addWidget(matches_group)

        # Action buttons
        button_layout = QHBoxLayout()
        
        self.add_new_btn = QPushButton("Add as New")
        self.add_alias_btn = QPushButton("Add as Alias")
        self.ignore_btn = QPushButton("Ignore")
        self.next_btn = QPushButton("Next")
        
        for btn in [self.add_new_btn, self.add_alias_btn, self.ignore_btn, self.next_btn]:
            button_layout.addWidget(btn)
            
        layout.addLayout(button_layout)                 

