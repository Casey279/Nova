# Create a new file called temporal_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QLineEdit, QPushButton, QDialogButtonBox)

class DateRangeDialog(QDialog):
    def __init__(self, parent=None, character_name="", role="", location_name=""):
        super().__init__(parent)
        self.setWindowTitle(f"Add Date Range - {character_name} at {location_name}")
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Date entry fields
        date_layout = QHBoxLayout()
        
        # Start Date
        start_layout = QVBoxLayout()
        start_layout.addWidget(QLabel("Start Year:"))
        self.start_year = QLineEdit()
        self.start_year.setPlaceholderText("YYYY")
        start_layout.addWidget(self.start_year)
        date_layout.addLayout(start_layout)
        
        # End Date
        end_layout = QVBoxLayout()
        end_layout.addWidget(QLabel("End Year:"))
        self.end_year = QLineEdit()
        self.end_year.setPlaceholderText("YYYY")
        end_layout.addWidget(self.end_year)
        date_layout.addLayout(end_layout)
        
        layout.addLayout(date_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_dates(self):
        return {
            'start_date': self.start_year.text() if self.start_year.text() else None,
            'end_date': self.end_year.text() if self.end_year.text() else None
        }