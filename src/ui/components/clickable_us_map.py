"""
Clickable US Map Widget

This module provides a widget that displays a clickable US map for selecting states.
"""

import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QSizePolicy
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF, QSizeF
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush

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

# State to SVG class mapping - lowercase class names in the SVG
STATE_SVG_CLASSES = {
    "AL": "al",
    "AK": "ak",
    "AZ": "az",
    "AR": "ar",
    "CA": "ca",
    "CO": "co",
    "CT": "ct",
    "DE": "de",
    "FL": "fl",
    "GA": "ga",
    "HI": "hi",
    "ID": "id",
    "IL": "il",
    "IN": "in",
    "IA": "ia",
    "KS": "ks",
    "KY": "ky",
    "LA": "la",
    "ME": "me",
    "MD": "md",
    "MA": "ma",
    "MI": "mi",
    "MN": "mn",
    "MS": "ms",
    "MO": "mo",
    "MT": "mt",
    "NE": "ne",
    "NV": "nv",
    "NH": "nh",
    "NJ": "nj",
    "NM": "nm",
    "NY": "ny",
    "NC": "nc",
    "ND": "nd",
    "OH": "oh",
    "OK": "ok",
    "OR": "or",
    "PA": "pa",
    "RI": "ri",
    "SC": "sc",
    "SD": "sd",
    "TN": "tn",
    "TX": "tx",
    "UT": "ut",
    "VT": "vt",
    "VA": "va",
    "WA": "wa",
    "WV": "wv",
    "WI": "wi",
    "WY": "wy"
}


class ClickableUSMapWidget(QWidget):
    """
    A widget that displays a clickable US map for selecting states.
    
    The widget includes the map and small-state buttons for states that are
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
        
        # Create the clickable SVG map
        self.map_widget = ClickableUSMapSVG(svg_path)
        self.map_widget.state_selected.connect(self.on_state_selected)
        main_layout.addWidget(self.map_widget)
        
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
        # Print debug information
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"State selected in widget: {state_abbrev}")
        
        # Update the visual selection in the map
        if state_abbrev in STATE_SVG_CLASSES:
            # Get the SVG class for this state
            svg_class = STATE_SVG_CLASSES[state_abbrev]
            # Set this as the selected state in the map widget
            self.map_widget.selected_state = svg_class
            self.map_widget.update()

        # Emit the signal to inform parent widgets about the selection
        self.state_selected.emit(state_abbrev)

    def set_selected_state(self, state_abbrev):
        """Set the selected state programmatically."""
        # Only proceed if the state abbreviation is valid
        if state_abbrev in STATE_SVG_CLASSES:
            # Update the visual selection
            svg_class = STATE_SVG_CLASSES[state_abbrev]
            self.map_widget.selected_state = svg_class
            self.map_widget.update()
            return True
        return False


class ClickableUSMapSVG(QSvgWidget):
    """
    A clickable SVG widget that displays the US map.
    
    When a state is clicked, the state_selected signal is emitted with
    the state's abbreviation.
    """
    
    # Signal emitted when a state is selected (state abbreviation)
    state_selected = pyqtSignal(str)
    
    def __init__(self, svg_path, parent=None):
        """Initialize the widget with the specified SVG file."""
        super().__init__(parent)
        
        # Load the SVG
        if os.path.exists(svg_path):
            self.load(svg_path)
        else:
            print(f"WARNING: SVG map file not found at {svg_path}")

        # Set fixed size constraints - keep wide enough but not too tall
        self.setMinimumSize(380, 200)  # Minimum size for visibility
        self.setMaximumSize(450, 250)  # Maximum size to prevent excessive vertical space usage
        
        # Ensure the map maintains its aspect ratio
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        # Set cursor to pointing hand
        self.setCursor(Qt.PointingHandCursor)

        # Currently highlighted state
        self.highlighted_state = None

        # Currently selected state
        self.selected_state = None

        # Debug flag - set to False by default
        self.debug_mode = False
    
    def mousePressEvent(self, event):
        """Handle mouse press events to select states."""
        # Get the SVG element class name at the click position
        state_class = self.find_state_at_position(event.pos())

        if self.debug_mode:
            print(f"Mouse press at {event.pos().x()}, {event.pos().y()}, found state class: {state_class}")

        if state_class:
            # Find the corresponding state abbreviation
            for abbrev, svg_class in STATE_SVG_CLASSES.items():
                if svg_class == state_class:
                    # Print debug info
                    if self.debug_mode:
                        print(f"Selecting state: {abbrev} ({svg_class})")

                    # Update the selected state
                    self.selected_state = state_class
                    self.update()  # Trigger repaint

                    # Emit the signal with the state abbreviation
                    self.state_selected.emit(abbrev)
                    break

    def mouseMoveEvent(self, event):
        """Handle mouse move events to highlight hovered states."""
        state_class = self.find_state_at_position(event.pos())

        # If we've moved to a different state, update highlighting
        if state_class != self.highlighted_state:
            old_state = self.highlighted_state
            self.highlighted_state = state_class

            # Only show debug message when we enter or leave a state
            if self.debug_mode:
                if state_class and not old_state:
                    print(f"Entering state: {state_class}")
                elif old_state and not state_class:
                    print(f"Leaving state: {old_state}")

            # Always update the display when the highlighted state changes
            self.update()  # Trigger repaint

    def find_state_at_position(self, pos):
        """
        Find the state SVG element class at the given position.

        Uses the exact scaled coordinates to find which state was clicked.
        State boundaries are defined as rectangles relative to the 959x593 SVG size.

        Returns the state class name or None if not found.
        """
        # Get mouse coordinates relative to the widget
        x, y = pos.x(), pos.y()

        # Calculate scale factors based on widget size vs original SVG size
        width_scale = self.width() / 959.0
        height_scale = self.height() / 593.0

        if self.debug_mode:
            print(f"Click at position: ({x}, {y})")
            print(f"Widget size: {self.width()}x{self.height()}, scale factors: width={width_scale:.2f}, height={height_scale:.2f}")

        # State boundary definitions (original SVG coordinates)
        state_boundaries = {
            'AL': (700, 350, 730, 400),    # (x1, y1, x2, y2)
            'AK': (120, 350, 200, 430),
            'AZ': (400, 270, 460, 330),
            'AR': (600, 320, 650, 360),
            'CA': (300, 220, 390, 320),
            'CO': (460, 240, 520, 280),
            'FL': (750, 420, 800, 470),
            'GA': (740, 380, 780, 420),
            'HI': (250, 400, 350, 450),
            'ID': (400, 170, 460, 230),
            'IL': (660, 250, 700, 310),
            'IN': (700, 260, 730, 300),
            'IA': (600, 240, 650, 270),
            'KS': (540, 270, 600, 300),
            'KY': (700, 300, 760, 330),
            'LA': (600, 360, 650, 400),
            'ME': (850, 120, 900, 170),
            'MD': (800, 260, 830, 290),
            'MA': (860, 190, 890, 200),
            'MI': (700, 220, 740, 260),
            'MN': (600, 170, 640, 220),
            'MS': (660, 360, 700, 410),
            'MO': (600, 270, 650, 320),
            'MT': (460, 170, 540, 210),
            'NE': (540, 240, 600, 270),
            'NV': (350, 220, 400, 270),
            'NH': (860, 170, 880, 190),
            'NJ': (850, 240, 870, 260),
            'NM': (460, 280, 520, 330),
            'NY': (820, 190, 860, 230),
            'NC': (780, 330, 840, 360),
            'ND': (540, 180, 580, 210),
            'OH': (720, 260, 760, 300),
            'OK': (540, 300, 600, 340),
            'OR': (350, 180, 400, 220),
            'PA': (800, 230, 850, 260),
            'RI': (887, 200, 895, 210),
            'SC': (780, 360, 820, 400),
            'SD': (540, 210, 580, 240),
            'TN': (680, 330, 750, 350),
            'TX': (500, 340, 580, 420),
            'UT': (400, 230, 460, 270),
            'VT': (840, 170, 860, 190),
            'VA': (780, 300, 830, 330),
            'WA': (350, 150, 400, 180),
            'WV': (760, 280, 800, 310),
            'WI': (640, 200, 680, 240),
            'WY': (460, 210, 520, 240)
        }

        # Check each state against the mouse position, with scaled boundaries
        for abbrev, boundary in state_boundaries.items():
            # Only check states that are clickable on the map
            clickable = True
            if abbrev in STATE_DATA:
                clickable = STATE_DATA[abbrev][1]

            if not clickable:
                continue

            # Get the boundary coordinates
            x1, y1, x2, y2 = boundary

            # Scale the boundary coordinates
            scaled_x1 = x1 * width_scale
            scaled_y1 = y1 * height_scale
            scaled_x2 = x2 * width_scale
            scaled_y2 = y2 * height_scale

            # Check if the point is inside the scaled boundary
            if (scaled_x1 <= x <= scaled_x2) and (scaled_y1 <= y <= scaled_y2):
                svg_class = STATE_SVG_CLASSES.get(abbrev)
                if svg_class:
                    if self.debug_mode:
                        print(f"Hit state: {abbrev} ({svg_class})")

                    return svg_class

        return None
    
    def paintEvent(self, event):
        """
        Custom paint event to draw the SVG with state highlighting and selection.

        This implementation uses QSvgRenderer directly to render the SVG
        and adds visual effects for hover and selection states using manual drawing.
        """
        # Create a painter for the widget
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Get the SVG renderer
        renderer = self.renderer()
        if not renderer:
            # Fallback if no renderer available
            super().paintEvent(event)
            return

        # Calculate scale factors based on widget size vs original SVG size
        width_scale = self.width() / 959.0
        height_scale = self.height() / 593.0

        # First render the base SVG
        renderer.render(painter)

        # Debug current states
        if self.debug_mode:
            print(f"PaintEvent: highlighted={self.highlighted_state}, selected={self.selected_state}")

        # Define state boundaries for highlighting (using same dictionary from find_state_at_position)
        state_boundaries = {
            'AL': (700, 350, 730, 400),
            'AK': (120, 350, 200, 430),
            'AZ': (400, 270, 460, 330),
            'AR': (600, 320, 650, 360),
            'CA': (300, 220, 390, 320),
            'CO': (460, 240, 520, 280),
            'FL': (750, 420, 800, 470),
            'GA': (740, 380, 780, 420),
            'HI': (250, 400, 350, 450),
            'ID': (400, 170, 460, 230),
            'IL': (660, 250, 700, 310),
            'IN': (700, 260, 730, 300),
            'IA': (600, 240, 650, 270),
            'KS': (540, 270, 600, 300),
            'KY': (700, 300, 760, 330),
            'LA': (600, 360, 650, 400),
            'ME': (850, 120, 900, 170),
            'MD': (800, 260, 830, 290),
            'MA': (860, 190, 890, 200),
            'MI': (700, 220, 740, 260),
            'MN': (600, 170, 640, 220),
            'MS': (660, 360, 700, 410),
            'MO': (600, 270, 650, 320),
            'MT': (460, 170, 540, 210),
            'NE': (540, 240, 600, 270),
            'NV': (350, 220, 400, 270),
            'NH': (860, 170, 880, 190),
            'NJ': (850, 240, 870, 260),
            'NM': (460, 280, 520, 330),
            'NY': (820, 190, 860, 230),
            'NC': (780, 330, 840, 360),
            'ND': (540, 180, 580, 210),
            'OH': (720, 260, 760, 300),
            'OK': (540, 300, 600, 340),
            'OR': (350, 180, 400, 220),
            'PA': (800, 230, 850, 260),
            'RI': (887, 200, 895, 210),
            'SC': (780, 360, 820, 400),
            'SD': (540, 210, 580, 240),
            'TN': (680, 330, 750, 350),
            'TX': (500, 340, 580, 420),
            'UT': (400, 230, 460, 270),
            'VT': (840, 170, 860, 190),
            'VA': (780, 300, 830, 330),
            'WA': (350, 150, 400, 180),
            'WV': (760, 280, 800, 310),
            'WI': (640, 200, 680, 240),
            'WY': (460, 210, 520, 240)
        }

        # Apply hover effect if a state is highlighted
        if self.highlighted_state and self.highlighted_state != self.selected_state:
            for abbrev, svg_class in STATE_SVG_CLASSES.items():
                if svg_class == self.highlighted_state and abbrev in state_boundaries:
                    # Get the boundary coordinates and scale them
                    x1, y1, x2, y2 = state_boundaries[abbrev]
                    rect = QRectF(
                        x1 * width_scale,
                        y1 * height_scale,
                        (x2 - x1) * width_scale,
                        (y2 - y1) * height_scale
                    )

                    # Draw the highlighted state with a darker gray with stronger contrast
                    painter.fillRect(rect, QColor(100, 100, 100, 200))

                    # Add a border to show hover state more clearly
                    pen = QPen(QColor(50, 50, 50))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawRect(rect)

                    if self.debug_mode:
                        print(f"Highlighted state: {abbrev} at {rect}")
                    break

        # Apply selection effect if a state is selected
        if self.selected_state:
            for abbrev, svg_class in STATE_SVG_CLASSES.items():
                if svg_class == self.selected_state and abbrev in state_boundaries:
                    # Get the boundary coordinates and scale them
                    x1, y1, x2, y2 = state_boundaries[abbrev]
                    rect = QRectF(
                        x1 * width_scale,
                        y1 * height_scale,
                        (x2 - x1) * width_scale,
                        (y2 - y1) * height_scale
                    )

                    # Draw the selected state with bright red
                    painter.fillRect(rect, QColor(220, 30, 30, 200))

                    # Add a border for the selected state for better visibility
                    pen = QPen(QColor(150, 0, 0))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawRect(rect)

                    if self.debug_mode:
                        print(f"Selected state: {abbrev} at {rect}")
                    break


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