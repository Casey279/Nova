# File: document_intake_tab.py

import os
import re
import shutil
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit,
                            QLabel, QPushButton, QFileDialog, QListWidget, QRadioButton,
                            QTextEdit, QMessageBox, QGraphicsView, QGraphicsScene, QButtonGroup, QCheckBox,
                            QGraphicsPixmapItem, QGraphicsRectItem, QListWidgetItem, QGroupBox, QComboBox, QGraphicsItem)
from ui.components.table_panel import TablePanel
from PyQt5.QtGui import QPixmap, QPen, QColor, QIcon, QImage, QPainter, QBrush
from PyQt5.QtCore import Qt, QRectF, QSize, QPointF
from PIL import Image
import pytesseract
from database_manager import DatabaseManager  # Add this import


class DocumentViewer(QGraphicsView):
    def __init__(self, preview_list=None):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Core attributes
        self.preview_list = preview_list
        self.pixmap_item = None
        self.current_selection = None
        self.is_selecting = False
        self.zoom_level = 1.0
        self.clipped_areas = []
        self.start_pos = None  # Add this to track initial click position
        self.selections = []  # Initialize selections list
        
        # Colors for visual feedback
        self.highlight_color = QColor(255, 255, 0, 64)  # Light yellow for saved highlights
        self.drawing_fill_color = QColor(255, 200, 200, 64)  # Light pink for active drawing


    def load_image(self, file_path):
        print(f"Loading image: {file_path}")
        pixmap = QPixmap(file_path)
        if self.pixmap_item:
            self.scene.removeItem(self.pixmap_item)
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def set_selection_mode(self, enabled):
        print(f"Selection mode: {'enabled' if enabled else 'disabled'}")
        self.is_selecting = enabled
        if enabled:
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            if self.current_selection:
                self.current_selection.setFlag(QGraphicsItem.ItemIsMovable, False)
            self.setDragMode(QGraphicsView.ScrollHandDrag)

    def mousePressEvent(self, event):
        if self.is_selecting and event.button() == Qt.LeftButton and not self.current_selection:
            self.start_pos = self.mapToScene(event.pos())
            self.current_selection = ResizableRectItem(
                self.start_pos.x(), 
                self.start_pos.y(), 
                0, 
                0
            )
            self.current_selection.setPen(QPen(QColor(255, 0, 0), 2))
            self.current_selection.setBrush(QBrush(self.drawing_fill_color))
            self.scene.addItem(self.current_selection)
            print(f"Started new selection at {self.start_pos}")
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_selection and self.is_selecting and self.start_pos:
            current_pos = self.mapToScene(event.pos())
            
            # Calculate the rect using the start position and current position
            x = min(self.start_pos.x(), current_pos.x())
            y = min(self.start_pos.y(), current_pos.y())
            width = abs(current_pos.x() - self.start_pos.x())
            height = abs(current_pos.y() - self.start_pos.y())
            
            # Update the selection rectangle
            self.current_selection.setPos(x, y)
            self.current_selection.setRect(0, 0, width, height)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_selection and self.is_selecting and event.button() == Qt.LeftButton:
            self.current_selection.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.start_pos = None  # Reset start position
            print("Selection complete")
        super().mouseReleaseEvent(event)

    def clear_selection(self):
        if self.current_selection:
            self.scene.removeItem(self.current_selection)
            self.current_selection = None
            print("Selection cleared")

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.1 if event.angleDelta().y() > 0 else 0.9
            self.zoom_level *= factor
            self.scale(factor, factor)
            print(f"Zoom level: {self.zoom_level:.2f}x")
        else:
            super().wheelEvent(event)



class ResizableRectItem(QGraphicsRectItem):
    def __init__(self, x, y, width, height, parent=None):
        super().__init__(x, y, width, height, parent)
        self.setFlags(QGraphicsItem.ItemIsSelectable | 
                     QGraphicsItem.ItemIsMovable)
        self.handles = []
        self.createHandles()
        self.resizing = False
        self.current_handle = None

    def createHandles(self):
        self.handles = []
        rect = self.rect()
        positions = [
            (rect.topLeft(), 'TL'),
            (rect.topRight(), 'TR'),
            (rect.bottomLeft(), 'BL'),
            (rect.bottomRight(), 'BR'),
            (QPointF(rect.center().x(), rect.top()), 'T'),
            (QPointF(rect.center().x(), rect.bottom()), 'B'),
            (QPointF(rect.left(), rect.center().y()), 'L'),
            (QPointF(rect.right(), rect.center().y()), 'R')
        ]
        
        for pos, handle_type in positions:
            # Increase size from 12x12 to 24x24 to make handles easier to grab
            handle = HandleItem(pos.x(), pos.y(), 24, 24, handle_type, self)
            self.handles.append(handle)


    def updateHandles(self):
        rect = self.rect()
        positions = [
            (rect.topLeft(), 'TL'),
            (rect.topRight(), 'TR'),
            (rect.bottomLeft(), 'BL'),
            (rect.bottomRight(), 'BR'),
            (QPointF(rect.center().x(), rect.top()), 'T'),
            (QPointF(rect.center().x(), rect.bottom()), 'B'),
            (QPointF(rect.left(), rect.center().y()), 'L'),
            (QPointF(rect.right(), rect.center().y()), 'R')
        ]
        
        for handle, (pos, _) in zip(self.handles, positions):
            handle.setPos(pos)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        self.updateHandles()

class HandleItem(QGraphicsRectItem):
    def __init__(self, x, y, width, height, handle_type, parent=None):
        super().__init__(0, 0, width, height, parent)
        self.handle_type = handle_type
        self.setPos(x - width/2, y - height/2)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black))
        self.setFlags(QGraphicsItem.ItemIsMovable | 
                     QGraphicsItem.ItemIsSelectable)
        self.setCursor(self.getCursor())

    def getCursor(self):
        if self.handle_type in ['TL', 'BR']:
            return Qt.SizeFDiagCursor
        elif self.handle_type in ['TR', 'BL']:
            return Qt.SizeBDiagCursor
        elif self.handle_type in ['T', 'B']:
            return Qt.SizeVerCursor
        else:
            return Qt.SizeHorCursor

    def mousePressEvent(self, event):
        if self.parentItem():
            self.parentItem().resizing = True
            self.parentItem().current_handle = self
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.parentItem():
            self.parentItem().resizing = False
            self.parentItem().current_handle = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.parentItem():
            parent = self.parentItem()
            pos = parent.mapFromScene(event.scenePos())
            rect = parent.rect()

            if self.handle_type == 'BR':
                rect.setBottomRight(pos)
            elif self.handle_type == 'TL':
                rect.setTopLeft(pos)
            elif self.handle_type == 'TR':
                rect.setTopRight(pos)
            elif self.handle_type == 'BL':
                rect.setBottomLeft(pos)
            elif self.handle_type == 'T':
                rect.setTop(pos.y())
            elif self.handle_type == 'B':
                rect.setBottom(pos.y())
            elif self.handle_type == 'L':
                rect.setLeft(pos.x())
            elif self.handle_type == 'R':
                rect.setRight(pos.x())

            parent.setRect(rect)
            parent.updateHandles()        


class GridPreviewWidget(QWidget):
    def __init__(self, columns=4, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.cells = []
        self.setMinimumHeight(400)
        self.grid_color = QColor(200, 200, 200)  # Light grey

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        cell_width = width / self.columns

        painter.setPen(QPen(self.grid_color, 1, Qt.DashLine))
        for i in range(1, self.columns):
            x = i * cell_width
            painter.drawLine(x, 0, x, height)

        for i, pixmap in enumerate(self.cells):
            if pixmap:
                row = i // self.columns
                col = i % self.columns
                x = col * cell_width
                y = row * cell_width
                target_rect = QRectF(x, y, cell_width, cell_width)
                painter.drawPixmap(target_rect, pixmap, pixmap.rect())

    def add_clipping(self, pixmap):
        self.cells.append(pixmap)
        self.update()


class DocumentIntakeTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.intake_dir = os.path.join(os.path.dirname(os.path.dirname(db_path)), "assets", "intake")
        self.multi_column_dir = os.path.join(self.intake_dir, "multi_column")
        self.preprocessed_dir = os.path.join(os.path.dirname(os.path.dirname(db_path)), "assets", "preprocessed")
        
        # Initialize highlight color, current selection, and selections
        self.highlight_color = QColor(255, 255, 0, 64)  # Semi-transparent yellow
        self.current_selection = None  # Initialize current_selection here
        self.selections = []  # Initialize selections here

        # Create preview_list at initialization
        self.preview_list = QListWidget()
        self.preview_list.setIconSize(QSize(150, 150))
        self.preview_list.setViewMode(QListWidget.IconMode)
        self.preview_list.setResizeMode(QListWidget.Adjust)
        self.preview_list.setWrapping(True)
        self.preview_list.setSpacing(5)
        self.preview_list.setMovement(QListWidget.Static)        

        # Other setup code
        print(f"Intake directory path: {self.intake_dir}")
        print(f"Directory exists: {os.path.exists(self.intake_dir)}")
        
        for directory in [self.intake_dir, self.multi_column_dir, self.preprocessed_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")
                        
        self.current_folder_type = 'intake'
        self.current_file = None
        self.initUI()


    def initUI(self):
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Create panels in the correct order
        left_panel = self.create_left_panel()
        right_panel = self.create_right_panel()  # Create right panel first!
        center_panel = self.create_center_panel()  # Now create center panel
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)

        splitter.setSizes([200, 600, 200])
        layout.addWidget(splitter)

    def create_left_panel(self):
        # Modify existing method to add batch processing button
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Create a TablePanel for the file list
        self.file_list_panel = TablePanel()
        self.file_list_panel.item_selected.connect(self.load_file)
        layout.addWidget(self.file_list_panel)

        folder_buttons = QHBoxLayout()
        intake_button = QPushButton("Intake Files")
        intake_button.clicked.connect(lambda: self.switch_folder('intake'))
        
        mc_button = QPushButton("Multi-Column Files")
        mc_button.clicked.connect(lambda: self.switch_folder('multicolumn'))
        
        batch_button = QPushButton("Batch Process")  # Add this button
        batch_button.clicked.connect(self.batch_process_files)  # Add this connection
        
        folder_buttons.addWidget(intake_button)
        folder_buttons.addWidget(mc_button)
        folder_buttons.addWidget(batch_button)  # Add this button
        layout.addLayout(folder_buttons)

        self.refresh_file_list()
        return widget

    def create_center_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.document_viewer = DocumentViewer(self.preview_list)
        layout.addWidget(self.document_viewer)

        controls = QHBoxLayout()

        # Toggle between Draw Mode and Pan Mode
        self.selection_toggle = QPushButton("Toggle Selection Mode")
        self.selection_toggle.setCheckable(True)
        self.selection_toggle.toggled.connect(lambda enabled: self.document_viewer.set_selection_mode(enabled))
        controls.addWidget(self.selection_toggle)

        # Clear Selection
        clear_button = QPushButton("Clear Selection")
        clear_button.clicked.connect(self.document_viewer.clear_selection)
        controls.addWidget(clear_button)

        # Save Selection
        save_selections_button = QPushButton("Save Selection for Stitching")
        save_selections_button.clicked.connect(self.save_selections)
        controls.addWidget(save_selections_button)

        layout.addLayout(controls)
        return widget

      

    def create_right_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Add Event Title input section near the top
        title_group = QGroupBox("Event Title")
        title_layout = QVBoxLayout()
        
        # Create and assign to class member
        self.event_title_input = QLineEdit()
        self.event_title_input.setPlaceholderText("Enter Event Title")
        self.event_title_input.focusInEvent = self.on_title_focus
        title_layout.addWidget(self.event_title_input)
        
        title_group.setLayout(title_layout)
        layout.addWidget(title_group)

        # Add source type dropdown
        source_type_group = QGroupBox("Source Type")
        source_type_layout = QVBoxLayout()
        
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems([
            "N - Newspaper",
            "B - Book",
            "J - Journal",
            "M - Magazine",
            "W - Wikipedia",
            "D - Diary/Personal Journal",
            "L - Letter/Correspondence",
            "G - Government Document",
            "C - Court Record",
            "R - Religious Record",
            "S - Ship Record/Manifest",
            "P - Photograph",
            "A - Academic Paper",
            "T - Trade Publication",
            "I - Interview Transcript",
            "O - Other"
        ])
        source_type_layout.addWidget(self.source_type_combo)
        source_type_group.setLayout(source_type_layout)
        layout.addWidget(source_type_group)

        layout_group = QGroupBox("Layout Options")
        layout_controls = QVBoxLayout()
        
        self.layout_type = QButtonGroup()
        grid_radio = QRadioButton("Grid Layout (4 columns)")
        grid_radio.setChecked(True)  # Always checked since it's the only option
        
        self.layout_type.addButton(grid_radio, 1)
        layout_controls.addWidget(grid_radio)
        layout_group.setLayout(layout_controls)
        layout.addWidget(layout_group)

        # Preview list with grid layout
        self.preview_list = QListWidget()
        self.preview_list.setIconSize(QSize(150, 150))
        self.preview_list.setViewMode(QListWidget.IconMode)
        self.preview_list.setResizeMode(QListWidget.Adjust)
        self.preview_list.setWrapping(True)  # Enable wrapping for grid layout
        self.preview_list.setSpacing(5)  # Space between items
        self.preview_list.setMovement(QListWidget.Static)  # Prevent item dragging
        layout.addWidget(QLabel("Clippings:"))
        layout.addWidget(self.preview_list)

        reorder_layout = QHBoxLayout()
        up_button = QPushButton("↑")
        down_button = QPushButton("↓")
        up_button.clicked.connect(self.move_clipping_up)
        down_button.clicked.connect(self.move_clipping_down)
        reorder_layout.addWidget(up_button)
        reorder_layout.addWidget(down_button)
        layout.addLayout(reorder_layout)

        stitch_button = QPushButton("Stitch and Save")
        stitch_button.clicked.connect(self.stitch_and_save)
        layout.addWidget(stitch_button)

        # Add File Management section
        file_management_group = QGroupBox("File Management")
        file_mgmt_layout = QVBoxLayout()
        
        # Add checkbox for archiving original
        self.archive_checkbox = QCheckBox("Archive original when done")
        file_mgmt_layout.addWidget(self.archive_checkbox)
        
        # Add Done With Page button
        done_button = QPushButton("Done With Page")
        done_button.clicked.connect(self.handle_page_completion)
        file_mgmt_layout.addWidget(done_button)
        
        file_management_group.setLayout(file_mgmt_layout)
        layout.addWidget(file_management_group)
        
        return widget

    def on_title_focus(self, event):
        if not self.current_file:
            QMessageBox.warning(self, "No File Selected", 
                "Please select a file from the left panel first.")
            self.event_title_input.clearFocus()
            return
        super(QLineEdit, self.event_title_input).focusInEvent(event)  

    def handle_page_completion(self):
        if not self.current_file:
            self.clear_all_panels()
            return
            
        try:
            if self.archive_checkbox.isChecked() and os.path.exists(self.current_file):
                archive_dir = os.path.join(os.path.dirname(self.multi_column_dir), "archives")
                if not os.path.exists(archive_dir):
                    os.makedirs(archive_dir)
                archive_path = os.path.join(archive_dir, os.path.basename(self.current_file))
                shutil.move(self.current_file, archive_path)
            elif os.path.exists(self.current_file):
                os.remove(self.current_file)
        except Exception as e:
            print(f"Error handling file: {str(e)}")
        finally:
            self.clear_all_panels()



    def clear_all_panels(self):
        """Clear all panels and reset state"""
        self.document_viewer.scene.clear()
        self.document_viewer.pixmap_item = None
        self.document_viewer.selections.clear()
        self.document_viewer.clipped_areas.clear()
        self.preview_list.clear()
        self.refresh_file_list() 
    
    def parse_filename(self, filename):
        """Parse filename to extract source info and add appropriate source code."""
        try:
            # Remove extension and any Copy prefix
            base_name = os.path.splitext(filename)[0]
            if base_name.startswith('Copy'):
                base_name = base_name[4:]
                
            # Remove trailing space and parenthetical numbers like " (1)"
            base_name = re.sub(r'\s*\(\d+\)$', '', base_name)
                
            # Remove 'Page' or 'page' if present
            base_name = base_name.replace('_Page_', '_').replace('_page_', '_')
            
            parts = base_name.split('_')
            
            # Find the part containing a 4-digit year for date
            year_index = -1
            for i, part in enumerate(parts):
                if len(part) >= 4 and part[:4].isdigit():
                    year_index = i
                    break
            
            if year_index == -1:
                raise ValueError("No year found in filename")
                
            # Everything before the date is the source name
            source_name_parts = parts[:year_index]
            source_name = ' '.join(source_name_parts).strip()
            
            # Handle date parsing - support both hyphenated and underscore dates
            if year_index + 2 < len(parts):  # Check if we have year_month_day
                year = parts[year_index]
                month = parts[year_index + 1].zfill(2)  # Ensure 2 digits
                day = parts[year_index + 2].zfill(2)    # Ensure 2 digits
                date_part = f"{year}-{month}-{day}"
            else:
                # Handle already-hyphenated date
                date_parts = parts[year_index].split('-')
                if len(date_parts) == 3:
                    year, month, day = date_parts
                    date_part = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:
                    date_part = parts[year_index]  # Just use what we have
            
            # Get page number (last numeric part, removing any trailing parenthetical)
            page_number = next((re.sub(r'\s*\(\d+\)$', '', part) 
                            for part in reversed(parts) 
                            if part.split('(')[0].isdigit()), '')
            
            # Check for multi-column designation
            is_multicolumn = '_MC' in filename
            if is_multicolumn:
                return {
                    'source_name': source_name,
                    'date': date_part,
                    'page': page_number,
                    'is_multicolumn': True,
                    'original_filename': filename
                }

            # Determine source code by checking against Sources table
            source_code = 'XX'  # Default code
            cursor = self.db_manager.conn.cursor()
            
            # First try exact match
            cursor.execute("SELECT SourceCode, Aliases FROM Sources")
            sources = cursor.fetchall()
            
            for db_source_code, aliases in sources:
                if aliases:
                    # Split aliases and convert to lowercase for comparison
                    alias_list = [alias.strip().lower() for alias in aliases.split(';')]
                    # Convert source name to lowercase and replace spaces with underscores
                    source_name_check = source_name.lower().replace(' ', '_')
                    
                    # Check each alias
                    for alias in alias_list:
                        alias_check = alias.lower().replace(' ', '_')
                        if alias_check in source_name_check or source_name_check in alias_check:
                            source_code = db_source_code
                            break
                    
                    if source_code != 'XX':  # Found a match
                        break
                
            return {
                'source_name': source_name,
                'date': date_part,
                'page': page_number,
                'source_code': source_code,
                'is_multicolumn': False
            }
            
        except Exception as e:
            print(f"Error parsing filename {filename}: {str(e)}")
            return None

    def batch_process_files(self):
        intake_files = [f for f in os.listdir(self.intake_dir) 
                    if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if not intake_files:
            QMessageBox.information(self, "Batch Process", "No files to process in intake folder.")
            return
        
        processed_count = 0
        skipped_count = 0
        
        for filename in intake_files:
            file_info = self.parse_filename(filename)
            if file_info:
                # Check source and handle if new
                source_name = file_info['source_name']
                source_id = self.check_and_handle_source(source_name)
                
                base_name, ext = os.path.splitext(filename)
                is_multicolumn = base_name.endswith('_MC')
                
                if is_multicolumn:
                    # For multi-column files, just move to multi-column folder with _MC removed
                    new_filename = base_name[:-3] + ext  # Remove _MC
                    dest_folder = self.multi_column_dir
                else:
                    # For single-column files, create standardized filename
                    new_filename = self.create_standardized_filename(file_info, filename)
                    dest_folder = self.preprocessed_dir
                
                # Move file to appropriate folder
                src_path = os.path.join(self.intake_dir, filename)
                dest_path = os.path.join(dest_folder, new_filename)
                
                try:
                    shutil.move(src_path, dest_path)
                    processed_count += 1
                except Exception as e:
                    print(f"Error moving file {filename}: {str(e)}")
                    skipped_count += 1
            else:
                skipped_count += 1
        
        self.refresh_file_list()
        QMessageBox.information(self, "Batch Process Complete", 
                            f"Processed: {processed_count}\nSkipped: {skipped_count}")

    def create_standardized_filename(self, file_info, original_filename):
        """Create standardized filename with all required fields."""
        _, ext = os.path.splitext(original_filename)
        
        # For multi-column files being moved to multi-column folder, keep original
        if file_info.get('is_multicolumn') and self.current_folder_type == 'multicolumn':
            return file_info.get('original_filename')
        
        # For files going to preprocessed (both single and multi-column), use standard format
        date = file_info.get('date', '')
        source_name = file_info.get('source_name', '')
        page_number = file_info.get('page', '')
        source_code = file_info.get('source_code', 'XX')
        
        # Get source type from the source in database, default to 'N'
        source_type = 'N'  # Default
        if source_code != 'XX':
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT SourceType FROM Sources WHERE SourceCode = ?", (source_code,))
            result = cursor.fetchone()
            if result:
                source_type = result[0]
        
        # Create base filename pattern
        counter = 0
        while True:
            # Create event title with counter if needed
            event_title = "Enter Event Title" if counter == 0 else f"Enter Event Title({counter})"
            
            # Create full filename
            final_filename = f"{date}_{event_title}_{source_type}_{source_name}_{page_number}_{source_code}{ext}"
            
            # Check if file exists
            if not os.path.exists(os.path.join(self.preprocessed_dir, final_filename)):
                break
                
            counter += 1
        
        return final_filename

    def switch_folder(self, folder_type):
        print(f"Switching to folder: {folder_type}")
        self.current_folder_type = folder_type
        self.refresh_file_list()
        
        self.selection_toggle.setEnabled(folder_type == 'multicolumn')
        if folder_type != 'multicolumn':
            self.selection_toggle.setChecked(False)

    def refresh_file_list(self):
        folder_path = self.multi_column_dir if self.current_folder_type == 'multicolumn' else self.intake_dir
        print(f"Refreshing file list from: {folder_path}")
        
        # Create a list to store files
        file_list = []
        
        if os.path.exists(folder_path):
            try:
                # Get all files in directory and its immediate subdirectories
                all_files = []
                for root, dirs, files in os.walk(folder_path):
                    print(f"Checking directory: {root}")
                    print(f"Found subdirectories: {dirs}")
                    print(f"Found files: {files}")
                    
                    # Only include files in the immediate directory, not subdirectories
                    if root == folder_path:
                        all_files.extend(files)
                
                print(f"All files found: {all_files}")
                
                for file in all_files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        print(f"Adding file to list: {file}")
                        file_list.append(file)
                    else:
                        print(f"Skipping non-image file: {file}")
                        
            except Exception as e:
                print(f"Error accessing directory: {str(e)}")
        else:
            print(f"Directory does not exist: {folder_path}")
        
        # Update the TablePanel with the file list
        self.file_list_panel.clear()
        self.file_list_panel.populate_table(file_list)
        
        print(f"Total files in list: {len(file_list)}")

    def load_file(self, item):
        if not item:
            return
            
        # Get the file name from the item
        # For TablePanel, item is a QListWidgetItem
        file_name = item.text()
        folder_path = self.multi_column_dir if self.current_folder_type == 'multicolumn' else self.intake_dir
        file_path = os.path.join(folder_path, file_name)
        
        if os.path.exists(file_path):
            print(f"Loading file: {file_path}")
            self.current_file = file_path
            self.document_viewer.load_image(file_path)
            self.document_viewer.clear_selection()
            self.preview_list.clear()
        else:
            print(f"File not found: {file_path}")
            QMessageBox.warning(self, "Error", f"File not found: {file_path}")

    def toggle_selection_mode(self, enabled):
        self.document_viewer.set_selection_mode(enabled)

    def move_clipping_up(self):
        current_row = self.preview_list.currentRow()
        if current_row > 0:
            item = self.preview_list.takeItem(current_row)
            self.preview_list.insertItem(current_row - 1, item)
            self.preview_list.setCurrentRow(current_row - 1)

    def move_clipping_down(self):
        current_row = self.preview_list.currentRow()
        if current_row < self.preview_list.count() - 1:
            item = self.preview_list.takeItem(current_row)
            self.preview_list.insertItem(current_row + 1, item)
            self.preview_list.setCurrentRow(current_row + 1)

    def save_selections(self):
        if not self.document_viewer.current_selection:
            QMessageBox.warning(self, "Warning", "No selection made")
            return

        selection = self.document_viewer.current_selection
        
        # Get the actual rect in scene coordinates
        rect = QRectF(selection.pos(), selection.pos() + QPointF(selection.rect().width(), selection.rect().height()))
        
        # Create highlight using rect coordinates
        highlight = QGraphicsRectItem(rect)
        highlight.setPen(QPen(self.document_viewer.highlight_color))
        highlight.setBrush(QBrush(self.document_viewer.highlight_color))
        self.document_viewer.scene.addItem(highlight)
        self.document_viewer.clipped_areas.append(highlight)
        
        # Process the clipping
        if self.document_viewer.pixmap_item:
            clipped_pixmap = self.document_viewer.pixmap_item.pixmap().copy(rect.toRect())
            item = QListWidgetItem()
            item.setData(Qt.UserRole, clipped_pixmap)
            icon = QIcon(clipped_pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            item.setIcon(icon)
            self.preview_list.addItem(item)
        
        # Remove the selection rectangle
        self.document_viewer.scene.removeItem(selection)
        self.document_viewer.current_selection = None
        
        # Switch back to pan mode
        self.selection_toggle.setChecked(False)





    def clear_viewer(self):
        self.scene.clear()
        self.pixmap_item = None
        self.clipped_areas.clear()

    def stitch_and_save(self):
        if self.preview_list.count() == 0:
            QMessageBox.warning(self, "Warning", "No clippings to stitch")
            return

        # Create stitched image
        clippings = []
        for i in range(self.preview_list.count()):
            pixmap = self.preview_list.item(i).data(Qt.UserRole)
            clippings.append(pixmap)

        stitched_image = self.create_grid_layout(clippings) if self.layout_type.checkedId() == 1 else self.create_vertical_layout(clippings)
        
        if not stitched_image:
            return

        # Parse original filename to get file info
        file_info = self.parse_filename(os.path.basename(self.current_file))
        if not file_info:
            QMessageBox.warning(self, "Error", "Could not parse filename")
            return
            
        # Use the same standardization method as single-column files
        new_filename = self.create_standardized_filename(file_info, self.current_file)
        
        # Check for existing files and add numbering in title if needed
        counter = 0
        base_name, ext = os.path.splitext(new_filename)
        final_filename = new_filename
        while os.path.exists(os.path.join(self.preprocessed_dir, final_filename)):
            counter += 1
            final_filename = f"{base_name}({counter}){ext}"

        save_path = os.path.join(self.preprocessed_dir, final_filename)
        stitched_image.save(save_path)
        
        self.preview_list.clear()
        QMessageBox.information(self, "Success", "Article saved to preprocessed folder.")

    def check_and_handle_source(self, source_name):
        """Check if source exists and handle if new"""
        source_id = self.db_manager.check_source_exists(source_name)
        
        if not source_id:
            source_id = self.db_manager.add_preliminary_source(source_name)
            QMessageBox.information(
                self,
                "New Source Detected",
                f"A new source '{source_name}' has been added to the database.\n"
                "Please review and complete the source details in the Sources Tab."
            )
            
            # Get reference to main window
            main_window = self.window()
            if main_window and hasattr(main_window, 'sources_tab'):
                main_window.sources_tab.load_sources_list()
                
        return source_id

    def create_grid_layout(self, clippings):
        if not clippings:
            return None

        columns = 4
        rows = (len(clippings) + columns - 1) // columns
        
        # Find maximum dimensions for grid cells
        max_width = max(pixmap.width() for pixmap in clippings)
        max_height = max(pixmap.height() for pixmap in clippings)
        
        spacing = 20  # pixels
        total_width = (max_width * columns) + (spacing * (columns - 1))
        total_height = (max_height * rows) + (spacing * (rows - 1))

        stitched_image = QImage(total_width, total_height, QImage.Format_RGB32)
        stitched_image.fill(Qt.white)
        painter = QPainter(stitched_image)

        # Reorder clippings for vertical-first ordering
        ordered_positions = []
        for col in range(columns):
            for row in range(rows):
                ordered_positions.append((row, col))

        # Place each clipping in the grid
        for i, pixmap in enumerate(clippings):
            if i >= len(ordered_positions):
                break
                
            row, col = ordered_positions[i]
            x = col * (max_width + spacing)
            y = row * (max_height + spacing)
            
            x_offset = (max_width - pixmap.width()) // 2
            y_offset = (max_height - pixmap.height()) // 2
            
            painter.drawPixmap(x + x_offset, y + y_offset, pixmap)

        painter.end()
        return stitched_image


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    ex = DocumentIntakeTab("path/to/your/database.db")
    ex.show()
    sys.exit(app.exec_())