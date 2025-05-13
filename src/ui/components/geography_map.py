"""
Geographic US Map Widget with accurate state highlighting

This module provides a widget that displays a geographically accurate US map
where states change color on hover and selection.
"""

import os
import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, 
                           QSizePolicy, QLabel, QGridLayout)
from PyQt5.QtSvg import QSvgRenderer, QGraphicsSvgItem
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QTransform

# State data: abbreviation -> (full name, clickable on map)
STATE_DATA = {
    "AL": ("Alabama", True),
    "AK": ("Alaska", True),
    "AZ": ("Arizona", True),
    "AR": ("Arkansas", True),
    "CA": ("California", True),
    "CO": ("Colorado", True),
    "CT": ("Connecticut", False),  # Small state, needs sidebar
    "DE": ("Delaware", False),     # Small state, needs sidebar
    "DC": ("District of Columbia", False),  # Not on standard maps
    "FL": ("Florida", True),
    "GA": ("Georgia", True),
    "HI": ("Hawaii", True),
    "ID": ("Idaho", True),
    "IL": ("Illinois", True),
    "IN": ("Indiana", True),
    "IA": ("Iowa", True),
    "KS": ("Kansas", True),
    "KY": ("Kentucky", True),
    "LA": ("Louisiana", True),
    "ME": ("Maine", True),
    "MD": ("Maryland", False),     # Small state, needs sidebar
    "MA": ("Massachusetts", False), # Small state, needs sidebar
    "MI": ("Michigan", True),
    "MN": ("Minnesota", True),
    "MS": ("Mississippi", True),
    "MO": ("Missouri", True),
    "MT": ("Montana", True),
    "NE": ("Nebraska", True),
    "NV": ("Nevada", True),
    "NH": ("New Hampshire", False), # Small state, needs sidebar
    "NJ": ("New Jersey", False),    # Small state, needs sidebar
    "NM": ("New Mexico", True),
    "NY": ("New York", True),
    "NC": ("North Carolina", True),
    "ND": ("North Dakota", True),
    "OH": ("Ohio", True),
    "OK": ("Oklahoma", True),
    "OR": ("Oregon", True),
    "PA": ("Pennsylvania", True),
    "RI": ("Rhode Island", False),  # Small state, needs sidebar
    "SC": ("South Carolina", True),
    "SD": ("South Dakota", True),
    "TN": ("Tennessee", True),
    "TX": ("Texas", True),
    "UT": ("Utah", True),
    "VT": ("Vermont", False),       # Small state, needs sidebar
    "VA": ("Virginia", True),
    "WA": ("Washington", True),
    "WV": ("West Virginia", True),
    "WI": ("Wisconsin", True),
    "WY": ("Wyoming", True)
}


class StateButton(QLabel):
    """
    A clickable label that represents a small state.
    
    When clicked, the clicked signal is emitted with the state's abbreviation.
    """
    
    # Signal emitted when the button is clicked (state abbreviation)
    clicked = pyqtSignal(str)
    
    def __init__(self, state_abbrev, state_name, parent=None):
        """Initialize the button with the state abbreviation and name."""
        super().__init__(parent)
        
        self.state_abbrev = state_abbrev
        self.state_name = state_name
        
        # Set the text to the state abbreviation
        self.setText(state_abbrev)
        
        # Set the tooltip to the state name
        self.setToolTip(state_name)
        
        # Set up the appearance
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #999;
                border-radius: 3px;
                padding: 3px;
                background-color: #f0f0f0;
                font-weight: bold;
            }
            QLabel:hover {
                background-color: #e0e0e0;
                border-color: #666;
            }
        """)
        
        # Set cursor to pointing hand
        self.setCursor(Qt.PointingHandCursor)
    
    def mousePressEvent(self, event):
        """Handle mouse press events to emit the clicked signal."""
        self.clicked.emit(self.state_abbrev)
        super().mousePressEvent(event)


class StateItem(QGraphicsSvgItem):
    """
    An interactive SVG item for a state on the map.
    
    This item detects mouse hover and selection events
    and updates its appearance accordingly.
    """
    
    def __init__(self, state_id, element_id, state_name, renderer, parent=None):
        """Initialize the state item."""
        super().__init__(parent)
        
        self.state_id = state_id
        self.element_id = element_id
        self.state_name = state_name
        
        # Store original bounds
        self.setSharedRenderer(renderer)
        
        # Set element ID if it exists
        if renderer.elementExists(element_id):
            self.setElementId(element_id)
        
        # Enable hover events
        self.setAcceptHoverEvents(True)
        
        # State flags
        self.hovered = False
        self.selected = False
    
    def hoverEnterEvent(self, event):
        """Handle mouse hover enter events."""
        self.hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle mouse hover leave events."""
        self.hovered = False
        self.update()
        super().hoverLeaveEvent(event)
    
    def paint(self, painter, option, widget=None):
        """
        Paint the state with visual feedback for hovering and selection.
        
        This overrides the default paint method to add custom styling.
        """
        # Disable caching for responsive updates
        self.setCacheMode(QGraphicsSvgItem.NoCache)
        
        # Draw underlying SVG
        super().paint(painter, option, widget)
        
        # If hovered or selected, draw overlay fill
        if self.hovered or self.selected:
            # Get the bounding rect
            rect = self.boundingRect()
            
            # Create a semi-transparent fill
            if self.selected:
                color = QColor(220, 50, 50, 150)  # Red, semi-transparent
            elif self.hovered:
                color = QColor(120, 120, 120, 100)  # Gray, semi-transparent
            
            # Apply fill
            painter.fillRect(rect, color)
            
            # Draw a border
            if self.selected:
                pen = QPen(QColor(180, 0, 0), 1.5)
            else:
                pen = QPen(QColor(80, 80, 80), 1.5)
                
            painter.setPen(pen)
            painter.drawRect(rect)


class GeographicMapView(QGraphicsView):
    """
    A graphics view that displays the interactive US map.
    
    When a state is clicked, the state_selected signal is emitted
    with the state's abbreviation.
    """
    
    # Signal emitted when a state is selected
    state_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the map view."""
        super().__init__(parent)
        
        # Set up the view
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        
        # Create scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        
        # Get path to SVG file
        svg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                                "assets", "uimaps", "us_states_map.svg")
        
        # Check if file exists
        if not os.path.exists(svg_path):
            print(f"ERROR: SVG map file not found at {svg_path}")
            return
        
        # Create SVG renderer
        self.renderer = QSvgRenderer(svg_path)
        
        # Add the base map to the scene
        self.base_item = QGraphicsSvgItem()
        self.base_item.setSharedRenderer(self.renderer)
        self.scene.addItem(self.base_item)
        
        # Map the state_id (abbr) to element class (lower case CSS class)
        self.state_elements = {
            abbr: abbr.lower() for abbr in STATE_DATA
        }
        
        # Debug by listing available elements in SVG if needed
        """
        element_ids = []
        for i in range(self.renderer.elementCount()):
            element_ids.append(self.renderer.elementAt(i).id())
        print(f"Found {len(element_ids)} elements: {', '.join(element_ids)}")
        """
        
        # Create state items and store references
        self.state_items = {}
        
        for state_id, (state_name, clickable) in STATE_DATA.items():
            if not clickable:
                continue
                
            element_id = self.state_elements.get(state_id)
            if element_id and self.renderer.elementExists(element_id):
                state_item = StateItem(state_id, element_id, state_name, self.renderer)
                self.scene.addItem(state_item)
                self.state_items[state_id] = state_item
        
        # Set up scene rect based on SVG dimensions
        self.setSceneRect(QRectF(self.renderer.viewBoxF()))
        
        # Currently selected state
        self.selected_state = None
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        
        # Set scene background color
        self.scene.setBackgroundBrush(QBrush(QColor(240, 240, 240)))
        
        # Fit content
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def resizeEvent(self, event):
        """Resize and maintain aspect ratio."""
        super().resizeEvent(event)
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def mousePressEvent(self, event):
        """Handle mouse press events to select states."""
        super().mousePressEvent(event)
        
        # Map event position to scene coordinates
        scene_pos = self.mapToScene(event.pos())
        
        # Find clicked state
        for state_id, state_item in self.state_items.items():
            if state_item.contains(state_item.mapFromScene(scene_pos)):
                self.select_state(state_id)
                break
    
    def select_state(self, state_id):
        """Select a state and update visuals."""
        # Deselect previous state
        if self.selected_state and self.selected_state in self.state_items:
            self.state_items[self.selected_state].selected = False
            self.state_items[self.selected_state].update()
        
        # Select new state
        self.selected_state = state_id
        if state_id in self.state_items:
            self.state_items[state_id].selected = True
            self.state_items[state_id].update()
        
        # Emit signal
        self.state_selected.emit(state_id)


class GeographicMapWidget(QWidget):
    """
    A widget that displays a clickable, geographically accurate US map.
    
    The widget includes an interactive map and small-state buttons for states that
    are too small to click on the map.
    """
    
    # Signal emitted when a state is selected (state abbreviation)
    state_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the widget with the map and small-state buttons."""
        super().__init__(parent)
        
        # Set up the main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the map view
        self.map_view = GeographicMapView()
        self.map_view.state_selected.connect(self.on_state_selected)
        
        # Set fixed size constraints
        self.map_view.setMinimumSize(380, 200)
        self.map_view.setMaximumSize(450, 250)
        
        # Add map to layout
        main_layout.addWidget(self.map_view)
        
        # Create a grid of buttons for small states
        small_states_layout = QGridLayout()
        small_states_layout.setContentsMargins(5, 0, 5, 0)
        small_states_layout.setSpacing(2)
        
        # Header for small states
        small_states_header = QLabel("Small Eastern States:")
        small_states_header.setAlignment(Qt.AlignCenter)
        small_states_header.setStyleSheet("font-weight: bold;")
        small_states_layout.addWidget(small_states_header, 0, 0, 1, 4)
        
        # Add buttons for small states
        row, col = 1, 0
        for abbrev, (name, clickable) in STATE_DATA.items():
            if not clickable:
                button = StateButton(abbrev, name)
                button.clicked.connect(self.on_state_selected)
                small_states_layout.addWidget(button, row, col)
                col += 1
                if col >= 4:  # 4 buttons per row
                    col = 0
                    row += 1
        
        main_layout.addLayout(small_states_layout)
        
        # Set the widget size policy
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
    
    def on_state_selected(self, state_abbrev):
        """Handle state selection from either the map or the small-state buttons."""
        # Update map visual selection
        self.map_view.select_state(state_abbrev)
        
        # Emit the signal to inform parent widgets
        self.state_selected.emit(state_abbrev)
    
    def set_selected_state(self, state_abbrev):
        """Set the selected state programmatically."""
        if state_abbrev in STATE_DATA:
            self.map_view.select_state(state_abbrev)
            return True
        return False