import os
import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QFileDialog, QGraphicsView, QGraphicsScene, 
                            QGraphicsRectItem, QMessageBox)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QBrush, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QRect

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

class DocumentPanel(QWidget):
    """
    Panel for displaying and interacting with document images.
    
    Responsibilities:
    - Image loading and display
    - Zooming and panning
    - Region selection for OCR
    """
    
    # Signals
    image_loaded = pyqtSignal(str)  # Emits path when new image is loaded
    region_selected = pyqtSignal(QRect)  # Emits when region is selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = None
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Image viewer with zooming capability
        self.image_viewer = ZoomableGraphicsView()
        layout.addWidget(self.image_viewer)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.upload_button = QPushButton("Upload Image/File")
        self.upload_button.clicked.connect(self.upload_image)
        button_layout.addWidget(self.upload_button)
        
        self.clear_button = QPushButton("Clear/Cancel")
        self.clear_button.clicked.connect(self.clear_image)
        button_layout.addWidget(self.clear_button)
        
        # Add selection mode toggle
        self.selection_toggle = QPushButton("Toggle Selection Mode")
        self.selection_toggle.setCheckable(True)
        self.selection_toggle.toggled.connect(self.toggle_selection_mode)
        button_layout.addWidget(self.selection_toggle)
        
        layout.addLayout(button_layout)
    
    def upload_image(self):
        """Open file dialog to select an image file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All Files (*)"
        )
        if file_path:
            self.display_image(file_path)
            self.image_loaded.emit(file_path)
    
    def display_image(self, file_path):
        """Display an image from the given file path"""
        self.image_path = file_path
        self.image_viewer.display_image(file_path)
    
    def clear_image(self):
        """Clear the current image and selection"""
        self.image_path = None
        if self.image_viewer.scene():
            self.image_viewer.scene().clear()
            
        # Reset selection
        self.image_viewer.selection_rect = None
        self.image_viewer.start_pos = None
    
    def toggle_selection_mode(self, enabled):
        """Toggle between selection and pan modes"""
        if enabled:
            self.image_viewer.setDragMode(QGraphicsView.NoDrag)
        else:
            self.image_viewer.setDragMode(QGraphicsView.ScrollHandDrag)
    
    def get_image_path(self):
        """Return the current image path"""
        return self.image_path
    
    def get_selection(self):
        """Get the current selection rectangle"""
        return self.image_viewer.get_selection_rect()
    
    def set_project_folder(self, folder_path):
        """Set the current project folder path for file operations"""
        self.project_folder = folder_path
    
    def find_and_display_image(self, text_file_path):
        """Find and display corresponding image for a text file"""
        for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']:
            image_file = os.path.splitext(text_file_path)[0] + ext
            if os.path.exists(image_file):
                self.display_image(image_file)
                return True
        return False