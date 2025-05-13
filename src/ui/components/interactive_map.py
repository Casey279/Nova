"""
Interactive SVG Map Widget

This module provides a widget that displays a clickable US map for selecting states.
States change color on hover and selection, using proper SVG manipulation.
"""

import os
import xml.dom.minidom as minidom
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QGridLayout, 
                            QSizePolicy, QGraphicsView, QGraphicsScene)
from PyQt5.QtSvg import QSvgRenderer, QGraphicsSvgItem
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF, QByteArray
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QTransform

# State data: abbreviation -> (full name, clickable on map)
# Some small states need special handling
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
    "WY": ("Wyoming", True),
    "PR": ("Puerto Rico", False),    # Not on standard maps
    "VI": ("Virgin Islands", False)  # Not on standard maps
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


class InteractiveMapSvgView(QGraphicsView):
    """
    A custom QGraphicsView for displaying an interactive SVG map.
    Handles hover and selection events for state elements.
    """
    
    # Signal emitted when a state is selected
    state_selected = pyqtSignal(str)
    
    def __init__(self, svg_path, parent=None):
        """Initialize the view with the specified SVG file."""
        super().__init__(parent)
        
        # Create the scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Remove scrollbars and frame
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.NoFrame)
        
        # Enable anti-aliasing
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Disable scroll wheel zoom
        self.setDragMode(QGraphicsView.NoDrag)
        
        # Set transform properties
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        
        # Load SVG file
        self.svg_path = svg_path
        self.load_svg()
        
        # State tracking
        self.highlighted_state = None
        self.selected_state = None
        
        # Create hit areas for states
        self.create_state_hit_areas()
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        # Keep SVG aspect ratio
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Set a reasonable size
        self.setMinimumSize(380, 200)
        self.setMaximumSize(450, 250)
    
    def load_svg(self):
        """Load the SVG file and create an SVG item for the scene."""
        try:
            # Create the SVG renderer
            self.renderer = QSvgRenderer(self.svg_path)
            
            # Parse the SVG DOM
            self.svg_dom = minidom.parse(self.svg_path)
            
            # Create the SVG item
            self.svg_item = QGraphicsSvgItem()
            self.svg_item.setSharedRenderer(self.renderer)
            
            # Set cache mode to disable caching for instant color updates
            self.svg_item.setCacheMode(QGraphicsSvgItem.NoCache)
            
            # Add the SVG item to the scene
            self.scene.addItem(self.svg_item)
            
            # Set the scene rect to match the SVG's viewport
            view_box = self.renderer.viewBoxF()
            self.svg_width = view_box.width()
            self.svg_height = view_box.height()
            self.scene.setSceneRect(0, 0, self.svg_width, self.svg_height)
            
            # Fit the view to the SVG content
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            
        except Exception as e:
            print(f"Error loading SVG: {e}")
    
    def create_state_hit_areas(self):
        """Create hit areas for all states in the SVG."""
        self.state_hit_areas = {}
        
        # Find all path elements with class="state"
        path_elements = self.svg_dom.getElementsByTagName("path")
        for path in path_elements:
            if path.getAttribute("class") and "state" in path.getAttribute("class"):
                # Get the state class (e.g., "al" for Alabama)
                classes = path.getAttribute("class").split()
                state_class = None
                for cls in classes:
                    if len(cls) == 2 and cls.islower():  # 2-letter state code
                        state_class = cls
                        break
                
                if state_class:
                    # Create hit path from the SVG path
                    d = path.getAttribute("d")
                    if d:
                        # Create a QPainterPath for hit testing
                        painter_path = QPainterPath()
                        # Parse SVG path data to create QPainterPath
                        # This is simplified and may need more complete SVG path parsing
                        commands = d.replace(",", " ").split()
                        i = 0
                        while i < len(commands):
                            cmd = commands[i]
                            if cmd.upper() == 'M':
                                # Move to
                                i += 1
                                x = float(commands[i])
                                i += 1
                                y = float(commands[i])
                                painter_path.moveTo(x, y)
                            elif cmd.upper() == 'L':
                                # Line to
                                i += 1
                                x = float(commands[i])
                                i += 1
                                y = float(commands[i])
                                painter_path.lineTo(x, y)
                            elif cmd.upper() == 'Z':
                                # Close path
                                painter_path.closeSubpath()
                            else:
                                # If it's a coordinate pair after a command
                                try:
                                    x = float(cmd)
                                    i += 1
                                    y = float(commands[i])
                                    # Continue the last command
                                    if painter_path.elementCount() > 0:
                                        painter_path.lineTo(x, y)
                                    else:
                                        painter_path.moveTo(x, y)
                                except (ValueError, IndexError):
                                    # Skip invalid commands
                                    pass
                            i += 1
                        
                        # Store the path and original element
                        self.state_hit_areas[state_class] = {
                            'path': painter_path,
                            'element': path,
                            'original_fill': path.getAttribute('fill') or '#D0D0D0'
                        }
    
    def resizeEvent(self, event):
        """Handle resize events to maintain aspect ratio."""
        super().resizeEvent(event)
        # Fit the view to the SVG while keeping aspect ratio
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def mousePressEvent(self, event):
        """Handle mouse press events to select states."""
        super().mousePressEvent(event)

        # Get mouse position in view coordinates
        pos = event.pos()
        print(f"Mouse clicked at view position: {pos.x()}, {pos.y()}")

        # Convert view coordinates to scene coordinates
        scene_pos = self.mapToScene(pos)
        print(f"Converted to scene position: {scene_pos.x()}, {scene_pos.y()}")

        # Scale to SVG coordinates (orig SVG is 959x593)
        svg_width_scale = self.svg_width / self.viewport().width()
        svg_height_scale = self.svg_height / self.viewport().height()

        # Get the state at position
        state_code = self.get_state_at_position(scene_pos)

        # Try both original and scaled coordinates
        if not state_code:
            # Try direct viewport coordinates
            state_code = self.get_state_at_position(QPointF(pos.x() * svg_width_scale,
                                                          pos.y() * svg_height_scale))

        if state_code:
            print(f"State found: {state_code}")
            # Find the corresponding state abbreviation
            state_abbrev = state_code.upper()
            if state_abbrev in STATE_DATA and STATE_DATA[state_abbrev][1]:
                # If state is clickable on map, select it
                self.select_state(state_code)
                self.state_selected.emit(state_abbrev)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events to highlight states."""
        super().mouseMoveEvent(event)

        # Get mouse position in view coordinates
        pos = event.pos()

        # Convert view coordinates to scene coordinates
        scene_pos = self.mapToScene(pos)

        # Try to find state at position
        state_code = self.get_state_at_position(scene_pos)

        # If that didn't work, try viewport scaled coordinates
        if not state_code:
            # Scale to SVG coordinates (orig SVG is 959x593)
            svg_width_scale = self.svg_width / self.viewport().width()
            svg_height_scale = self.svg_height / self.viewport().height()

            # Try direct viewport coordinates
            state_code = self.get_state_at_position(QPointF(pos.x() * svg_width_scale,
                                                          pos.y() * svg_height_scale))

        # If moving to a different state, update highlighting
        if state_code != self.highlighted_state:
            print(f"Hover state changed from {self.highlighted_state} to {state_code}")

            # Restore previous highlighted state
            if self.highlighted_state and self.highlighted_state != self.selected_state:
                self.update_state_fill(self.highlighted_state, 'normal')

            # Highlight new state
            self.highlighted_state = state_code
            if state_code and state_code != self.selected_state:
                self.update_state_fill(state_code, 'hover')

            # Update the view
            self.update()
    
    def leaveEvent(self, event):
        """Handle mouse leave events to clear highlighting."""
        super().leaveEvent(event)
        
        # Clear highlight when mouse leaves the widget
        if self.highlighted_state and self.highlighted_state != self.selected_state:
            self.update_state_fill(self.highlighted_state, 'normal')
            self.highlighted_state = None
            self.update()
    
    def get_state_at_position(self, pos):
        """Find the state at the given scene position."""
        # Add debug info
        print(f"Looking for state at scene position: {pos.x()}, {pos.y()}")

        # Check SVG hit areas
        for state_code, state_info in self.state_hit_areas.items():
            path = state_info['path']

            # Check if the point is inside the path
            if path.contains(pos):
                print(f"Found state: {state_code}")
                return state_code

        # Simplified hit testing using state rectangles as fallback
        state_rects = {
            "al": QRectF(640, 340, 40, 60),   # Alabama
            "ak": QRectF(100, 350, 100, 80),  # Alaska
            "az": QRectF(380, 250, 60, 60),   # Arizona
            "ar": QRectF(580, 300, 50, 40),   # Arkansas
            "ca": QRectF(280, 200, 90, 100),  # California
            "co": QRectF(440, 220, 60, 40),   # Colorado
            "fl": QRectF(730, 400, 50, 50),   # Florida
            "ga": QRectF(720, 360, 40, 40),   # Georgia
            "hi": QRectF(230, 380, 100, 50),  # Hawaii
            "id": QRectF(380, 150, 60, 60),   # Idaho
            "il": QRectF(640, 230, 40, 60),   # Illinois
            "in": QRectF(680, 240, 30, 40),   # Indiana
            "ia": QRectF(580, 220, 50, 30),   # Iowa
            "ks": QRectF(520, 250, 60, 30),   # Kansas
            "ky": QRectF(680, 280, 60, 30),   # Kentucky
            "la": QRectF(580, 340, 50, 40),   # Louisiana
            "me": QRectF(830, 100, 50, 50),   # Maine
            "mi": QRectF(680, 200, 40, 40),   # Michigan
            "mn": QRectF(580, 150, 40, 50),   # Minnesota
            "ms": QRectF(640, 340, 40, 50),   # Mississippi
            "mo": QRectF(580, 250, 50, 50),   # Missouri
            "mt": QRectF(440, 150, 80, 40),   # Montana
            "ne": QRectF(520, 220, 60, 30),   # Nebraska
            "nv": QRectF(330, 200, 50, 50),   # Nevada
            "nm": QRectF(440, 260, 60, 50),   # New Mexico
            "ny": QRectF(800, 170, 40, 40),   # New York
            "nc": QRectF(760, 310, 60, 30),   # North Carolina
            "nd": QRectF(520, 160, 40, 30),   # North Dakota
            "oh": QRectF(700, 240, 40, 40),   # Ohio
            "ok": QRectF(520, 280, 60, 40),   # Oklahoma
            "or": QRectF(330, 160, 50, 40),   # Oregon
            "pa": QRectF(780, 210, 50, 30),   # Pennsylvania
            "sc": QRectF(760, 340, 40, 40),   # South Carolina
            "sd": QRectF(520, 190, 40, 30),   # South Dakota
            "tn": QRectF(660, 310, 70, 20),   # Tennessee
            "tx": QRectF(480, 320, 80, 80),   # Texas
            "ut": QRectF(380, 210, 60, 40),   # Utah
            "va": QRectF(760, 280, 50, 30),   # Virginia
            "wa": QRectF(330, 130, 50, 30),   # Washington
            "wv": QRectF(740, 260, 40, 30),   # West Virginia
            "wi": QRectF(620, 180, 40, 40),   # Wisconsin
            "wy": QRectF(440, 190, 60, 30),   # Wyoming
        }

        # Check if point is in any state rect (use as fallback)
        for state_code, rect in state_rects.items():
            if rect.contains(pos):
                print(f"Found state using rect: {state_code}")
                return state_code

        return None
    
    def select_state(self, state_code):
        """Select a state and update its appearance."""
        # Deselect previous state
        if self.selected_state:
            self.update_state_fill(self.selected_state, 'normal')
        
        # Select new state
        self.selected_state = state_code
        if state_code:
            self.update_state_fill(state_code, 'selected')
        
        # Update the view
        self.update()
    
    def update_state_fill(self, state_code, state_type):
        """Update a state's fill color based on its state (normal, hover, selected)."""
        if state_code not in self.state_hit_areas:
            return
        
        # Get the state info
        state_info = self.state_hit_areas[state_code]
        element = state_info['element']
        
        # Set fill color based on state
        if state_type == 'normal':
            # Set to original color
            fill_color = state_info['original_fill']
        elif state_type == 'hover':
            # Set hover color (darker gray)
            fill_color = '#A0A0A0'
        elif state_type == 'selected':
            # Set selection color (red)
            fill_color = '#CC3333'
        
        # Update the element's fill color
        element.setAttribute('fill', fill_color)
        
        # Update the SVG content
        self.update_svg_content()
    
    def update_svg_content(self):
        """Update the SVG content with the modified DOM."""
        try:
            # Convert the modified DOM back to XML
            svg_string = self.svg_dom.toxml()
            print(f"Updating SVG content, modified state elements...")

            # Update the renderer with the new SVG content
            success = self.renderer.load(QByteArray(svg_string.encode()))
            if not success:
                print("ERROR: Failed to load updated SVG")

            # Force a redraw of the scene and view
            self.svg_item.update()
            self.scene.update()
            self.viewport().update()

            # Use a simpler approach for immediate color changes
            # Find the state element in DOM and apply style directly
            for state_code, fill_color in [
                (self.highlighted_state, '#A0A0A0'),
                (self.selected_state, '#CC3333')
            ]:
                if state_code and state_code in self.state_hit_areas:
                    # This is a direct way to force visual update
                    element = self.state_hit_areas[state_code]['element']
                    element.setAttribute('style', f'fill:{fill_color};')

        except Exception as e:
            print(f"Error updating SVG content: {e}")


class InteractiveMapWidget(QWidget):
    """
    A widget that displays a clickable US map for selecting states.
    
    The widget includes the interactive map and small-state buttons for states that are
    too small to click on the map.
    """
    
    # Signal emitted when a state is selected (state abbreviation)
    state_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the widget with the US map and small-state buttons."""
        super().__init__(parent)
        
        # Set up the main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Get the path to the SVG file
        svg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                                "assets", "uimaps", "clickable_us_map.svg")
        
        # Create the interactive SVG map
        self.map_view = InteractiveMapSvgView(svg_path)
        self.map_view.state_selected.connect(self.on_state_selected)
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
        # Update the visual selection in the map
        state_code = state_abbrev.lower()
        self.map_view.select_state(state_code)
        
        # Emit the signal to inform parent widgets about the selection
        self.state_selected.emit(state_abbrev)
    
    def set_selected_state(self, state_abbrev):
        """Set the selected state programmatically."""
        # Only proceed if the state abbreviation is valid
        if state_abbrev in STATE_DATA:
            state_code = state_abbrev.lower()
            self.map_view.select_state(state_code)
            return True
        return False