"""
Simple US Map Widget

This module provides a simple, reliable widget for displaying a clickable US map.
It uses a direct painting approach to avoid SVG complexity.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath

# State data with coordinates for simplified map painting
STATES = {
    # State abbreviation: (name, x, y, width, height, clickable)
    "AL": ("Alabama", 650, 350, 30, 40, True),
    "AK": ("Alaska", 150, 400, 60, 40, True),
    "AZ": ("Arizona", 300, 320, 40, 40, True),
    "AR": ("Arkansas", 570, 340, 30, 30, True),
    "CA": ("California", 200, 290, 60, 50, True),
    "CO": ("Colorado", 420, 280, 40, 30, True),
    "CT": ("Connecticut", 795, 220, 15, 15, False),
    "DE": ("Delaware", 785, 250, 10, 10, False),
    "DC": ("District of Columbia", 780, 260, 8, 8, False),
    "FL": ("Florida", 700, 400, 40, 40, True),
    "GA": ("Georgia", 680, 350, 30, 30, True),
    "HI": ("Hawaii", 250, 430, 40, 20, True),
    "ID": ("Idaho", 300, 220, 40, 40, True),
    "IL": ("Illinois", 600, 280, 25, 40, True),
    "IN": ("Indiana", 630, 280, 20, 30, True),
    "IA": ("Iowa", 550, 260, 40, 30, True),
    "KS": ("Kansas", 500, 300, 40, 30, True),
    "KY": ("Kentucky", 650, 300, 40, 25, True),
    "LA": ("Louisiana", 570, 380, 30, 30, True),
    "ME": ("Maine", 800, 180, 25, 25, True),
    "MD": ("Maryland", 760, 260, 20, 20, False),
    "MA": ("Massachusetts", 790, 210, 20, 15, False),
    "MI": ("Michigan", 620, 230, 30, 30, True),
    "MN": ("Minnesota", 550, 220, 30, 30, True),
    "MS": ("Mississippi", 600, 360, 25, 30, True),
    "MO": ("Missouri", 560, 300, 40, 30, True),
    "MT": ("Montana", 350, 200, 60, 30, True),
    "NE": ("Nebraska", 480, 260, 40, 30, True),
    "NV": ("Nevada", 250, 260, 40, 40, True),
    "NH": ("New Hampshire", 795, 200, 15, 15, False),
    "NJ": ("New Jersey", 780, 240, 15, 20, False),
    "NM": ("New Mexico", 360, 340, 40, 40, True),
    "NY": ("New York", 750, 220, 30, 25, True),
    "NC": ("North Carolina", 710, 310, 40, 25, True),
    "ND": ("North Dakota", 480, 210, 40, 25, True),
    "OH": ("Ohio", 670, 260, 30, 30, True),
    "OK": ("Oklahoma", 480, 330, 50, 30, True),
    "OR": ("Oregon", 230, 220, 50, 30, True),
    "PA": ("Pennsylvania", 720, 250, 40, 25, True),
    "RI": ("Rhode Island", 800, 220, 10, 10, False),
    "SC": ("South Carolina", 700, 330, 30, 25, True),
    "SD": ("South Dakota", 480, 230, 40, 30, True),
    "TN": ("Tennessee", 650, 320, 50, 20, True),
    "TX": ("Texas", 450, 360, 80, 70, True),
    "UT": ("Utah", 300, 270, 40, 40, True),
    "VT": ("Vermont", 780, 200, 15, 15, False),
    "VA": ("Virginia", 740, 280, 40, 25, True),
    "WA": ("Washington", 230, 180, 50, 30, True),
    "WV": ("West Virginia", 700, 280, 30, 25, True),
    "WI": ("Wisconsin", 580, 230, 30, 30, True),
    "WY": ("Wyoming", 370, 240, 40, 30, True),
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


class SimpleMapWidget(QWidget):
    """
    A simple, clickable US map widget.
    """
    
    # Signal emitted when a state is selected (state abbreviation)
    state_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the widget with the map."""
        super().__init__(parent)
        
        # Set up widget properties
        self.setMinimumSize(400, 250)
        self.setMaximumSize(500, 300)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Set cursor to pointing hand
        self.setCursor(Qt.PointingHandCursor)
        
        # State tracking
        self.highlighted_state = None
        self.selected_state = None
        
        # Set up the main layout (for buttons)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a grid for small-state buttons
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
        for abbrev, (name, _, _, _, _, clickable) in STATES.items():
            if not clickable:
                button = StateButton(abbrev, name)
                button.clicked.connect(self.state_selected)
                small_states_layout.addWidget(button, row, col)
                col += 1
                if col >= 4:  # 4 buttons per row
                    col = 0
                    row += 1
        
        self.layout.addStretch(1)  # Add space after map
        self.layout.addLayout(small_states_layout)
    
    def paintEvent(self, event):
        """Paint the US map."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        background_rect = QRect(0, 0, self.width(), self.height() - 50)  # Leave space for buttons
        painter.fillRect(background_rect, QColor(240, 240, 240))
        
        # Calculate scale factors to adjust state positions and sizes
        width_scale = self.width() / 850.0
        height_scale = (self.height() - 50) / 500.0
        
        # Draw states
        for abbrev, (name, x, y, width, height, clickable) in STATES.items():
            if not clickable:
                continue
                
            # Calculate scaled position and size
            scaled_x = int(x * width_scale)
            scaled_y = int(y * height_scale)
            scaled_width = int(width * width_scale)
            scaled_height = int(height * height_scale)
            
            # Create a rectangle for the state
            state_rect = QRect(scaled_x, scaled_y, scaled_width, scaled_height)
            
            # Choose fill color based on state
            if abbrev == self.selected_state:
                fill_color = QColor(204, 51, 51)  # Red
            elif abbrev == self.highlighted_state:
                fill_color = QColor(150, 150, 150)  # Dark gray
            else:
                fill_color = QColor(208, 208, 208)  # Light gray
            
            # Draw state shape (rounded rectangle)
            painter.setPen(QPen(Qt.white, 1))
            painter.setBrush(QBrush(fill_color))
            painter.drawRoundedRect(state_rect, 5, 5)
            
            # Draw state abbreviation (for larger states)
            if width >= 40 and height >= 30:
                painter.setPen(QPen(Qt.black, 1))
                font = painter.font()
                font.setBold(True)
                font.setPointSize(8)
                painter.setFont(font)
                painter.drawText(state_rect, Qt.AlignCenter, abbrev)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events to highlight states."""
        # Find state under the mouse
        pos = event.pos()
        state = self.get_state_at_position(pos)
        
        # If moving to a different state, update highlighting
        if state != self.highlighted_state:
            self.highlighted_state = state
            self.update()  # Trigger repaint
    
    def mousePressEvent(self, event):
        """Handle mouse press events to select states."""
        # Find state under the mouse
        pos = event.pos()
        state = self.get_state_at_position(pos)
        
        if state:
            # Update selected state
            self.selected_state = state
            self.update()  # Trigger repaint
            
            # Emit signal
            self.state_selected.emit(state)
    
    def leaveEvent(self, event):
        """Handle mouse leave events to clear highlighting."""
        self.highlighted_state = None
        self.update()  # Trigger repaint
    
    def get_state_at_position(self, pos):
        """Find the state at the given position."""
        # Calculate scale factors
        width_scale = self.width() / 850.0
        height_scale = (self.height() - 50) / 500.0
        
        # Check each state
        for abbrev, (name, x, y, width, height, clickable) in STATES.items():
            if not clickable:
                continue
                
            # Calculate scaled position and size
            scaled_x = int(x * width_scale)
            scaled_y = int(y * height_scale)
            scaled_width = int(width * width_scale)
            scaled_height = int(height * height_scale)
            
            # Create a rectangle for the state
            state_rect = QRect(scaled_x, scaled_y, scaled_width, scaled_height)
            
            # Check if mouse is inside the state
            if state_rect.contains(pos):
                return abbrev
        
        return None
    
    def set_selected_state(self, state_abbrev):
        """Set the selected state programmatically."""
        if state_abbrev in STATES:
            self.selected_state = state_abbrev
            self.update()  # Trigger repaint
            return True
        return False