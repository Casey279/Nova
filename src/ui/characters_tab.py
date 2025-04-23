# File: characters_tab.py

import os
import sqlite3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
                             QLabel, QLineEdit, QTextEdit, QFormLayout, QScrollArea, QDialogButtonBox,
                             QSplitter, QListWidgetItem, QFileDialog, QMessageBox, QFrame, QComboBox,
                             QDialog, QSplitterHandle, QDateEdit)
from PyQt5.QtGui import QFont, QPixmap, QPainter
from PyQt5.QtCore import Qt, QEvent, QTimer
from database_manager import DatabaseManager


class CharacterDialog(QDialog):
    def __init__(self, parent=None, character_data=None):
        super().__init__(parent)
        self.character_data = character_data
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Character Details")
        layout = QVBoxLayout(self)

        # Character details form
        form_layout = QFormLayout()

        self.fields = {}
        field_names = ['Prefix', 'FirstName', 'MiddleName', 'LastName', 'Suffix', 
                      'DisplayName', 'Aliases', 'Gender', 'BirthDate', 'DeathDate',
                      'Height', 'Weight', 'Hair', 'Eyes', 'Occupation', 'Family',
                      'Affiliations', 'FindAGrave', 'ClifftonStrengths', 
                      'Enneagram', 'MyersBriggs']

        for field in field_names:
            self.fields[field] = QLineEdit()
            if self.character_data and field in self.character_data:
                value = self.character_data[field]
                # Only set text if value is not None and not empty
                if value and str(value).strip():
                    self.fields[field].setText(str(value))
            form_layout.addRow(field, self.fields[field])

        # TextEdit fields
        text_fields = ['BackgroundSummary', 'PersonalityTraits']
        for field in text_fields:
            self.fields[field] = QTextEdit()
            if self.character_data and field in self.character_data:
                value = self.character_data[field]
                # Only set text if value is not None and not empty
                if value and str(value).strip():
                    self.fields[field].setPlainText(str(value))
            form_layout.addRow(field, self.fields[field])

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def get_character_data(self):
        """Get the character data from the form fields."""
        data = {}
        for field, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                value = widget.text().strip()
            else:  # QTextEdit
                value = widget.toPlainText().strip()
            data[field] = value if value else None
        
        # Preserve the ImagePath from the original data if it exists
        if self.character_data and 'ImagePath' in self.character_data:
            data['ImagePath'] = self.character_data['ImagePath']
        else:
            data['ImagePath'] = None
        return data

class CustomSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setStyleSheet("background-color: lightgray")  # You can adjust the color as needed

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw custom text/icon in the middle of the handle (e.g., "<>")
        painter.drawText(self.rect(), Qt.AlignCenter, "<>")  # Drawing "<>" in the middle of the handle

class CustomSplitter(QSplitter):
    def createHandle(self):
        return CustomSplitterHandle(self.orientation(), self)  # Use our custom handle

class CharactersTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.current_character_id = None
        self.last_viewed_articles = {}  # Add this line to store last viewed articles
        self.start_date = None
        self.end_date = None

        self.initUI()  # Initialize the UI first
        self.load_characters()  # Now load characters after the UI is set up
        QTimer.singleShot(0, self.setup_event_filters)  # Install event filters after UI initialization


    def initUI(self):
        layout = QHBoxLayout(self)
        self.splitter = CustomSplitter(Qt.Horizontal)  # Use the custom splitter here

        # Left panel: Character list
        left_panel = self.create_left_panel()
        self.splitter.addWidget(left_panel)

        # Middle panel: Character details
        middle_panel = self.create_middle_panel()
        self.splitter.addWidget(middle_panel)

        # Right panel: Associated articles
        right_panel = self.create_right_panel()  # Adjusted to add date filters and "Clear Viewer" button
        self.splitter.addWidget(right_panel)

        layout.addWidget(self.splitter)

        # Set initial sizes (33%, 33%, 33%)
        self.splitter.setSizes([int(self.width() * 0.125), int(self.width() * 0.75), int(self.width() * 0.125)])

        # Set movement restrictions and handle width
        self.splitter.setHandleWidth(15)  # Adjust width of the divider handle
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, False)


    def setup_event_filters(self):
        # Install event filters on the splitter handles
        self.splitter.handle(1).installEventFilter(self)
        self.splitter.handle(2).installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            if obj == self.splitter.handle(1):  # Left handle
                position = obj.mapToGlobal(event.pos()).x()
                if position < int(self.width() * 0.10):
                    self.splitter.setSizes([int(self.width() * 0.10), int(self.width() * 0.60), int(self.width() * 0.30)])
                elif position > int(self.width() * 0.40):
                    self.splitter.setSizes([int(self.width() * 0.40), int(self.width() * 0.50), int(self.width() * 0.20)])
            elif obj == self.splitter.handle(2):  # Right handle
                position = obj.mapToGlobal(event.pos()).x()
                if position < int(self.width() * 0.60):
                    self.splitter.setSizes([int(self.width() * 0.30), int(self.width() * 0.50), int(self.width() * 0.10)])
                elif position > int(self.width() * 0.90):
                    self.splitter.setSizes([int(self.width() * 0.10), int(self.width() * 0.60), int(self.width() * 0.30)])
        return super().eventFilter(obj, event)



    def create_left_panel(self):
        left_panel = QWidget()
        layout = QVBoxLayout(left_panel)

        view_layout = QHBoxLayout()
        view_layout.addWidget(QLabel("View:"))
        self.view_dropdown = QComboBox()
        self.view_dropdown.addItems(["All Characters", "Primary Characters", "Secondary Characters", "Tertiary Characters", "Quaternary Characters"])
        self.view_dropdown.currentTextChanged.connect(self.load_characters)
        view_layout.addWidget(self.view_dropdown)
        layout.addLayout(view_layout)

        self.character_list = QListWidget()
        self.character_list.itemClicked.connect(self.display_character_details)
        layout.addWidget(self.character_list)

        add_button = QPushButton("Add New Character")
        add_button.clicked.connect(self.add_new_character)
        layout.addWidget(add_button)

        delete_button = QPushButton("Delete Character")
        delete_button.clicked.connect(self.delete_character)
        layout.addWidget(delete_button)

        return left_panel

    def create_middle_panel(self):
        middle_panel = QWidget()
        layout = QVBoxLayout(middle_panel)

        # Display Name at the top
        self.display_name_label = QLabel()
        self.display_name_label.setAlignment(Qt.AlignCenter)
        self.display_name_label.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(self.display_name_label)

        # Upper Section: Image and Vitals
        upper_section = QFrame()
        upper_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        upper_section.setLineWidth(2)
        upper_layout = QHBoxLayout(upper_section)

        # Create image section
        self.image_section = self.create_image_section()
        upper_layout.addWidget(self.image_section)

        # Create and store vitals section (initialize as empty container)
        self.vitals_section_container = QWidget()
        self.vitals_section_layout = QVBoxLayout(self.vitals_section_container)
        
        # Add an empty placeholder for vitals initially
        self.vitals_section = QLabel("No character selected")  # Placeholder text
        self.vitals_section_layout.addWidget(self.vitals_section)

        upper_layout.addWidget(self.vitals_section_container)

        layout.addWidget(upper_section)

        # Lower Section: Additional Information
        lower_section = QScrollArea()
        lower_section.setWidgetResizable(True)
        lower_widget = QWidget()
        self.lower_layout = QVBoxLayout(lower_widget)
        lower_section.setWidget(lower_widget)
        layout.addWidget(lower_section)

        # Buttons: Edit Character and Mark Reviewed
        button_layout = QHBoxLayout()
        
        # Edit Character button
        self.edit_character_button = QPushButton("Edit Character")
        self.edit_character_button.clicked.connect(self.edit_character)
        button_layout.addWidget(self.edit_character_button)

        # Mark Reviewed button
        self.mark_reviewed_button = QPushButton("Mark Reviewed")
        self.mark_reviewed_button.clicked.connect(self.mark_character_reviewed)
        button_layout.addWidget(self.mark_reviewed_button)

        layout.addLayout(button_layout)

        return middle_panel



    def create_right_panel(self):
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        # Label for the article list
        right_layout.addWidget(QLabel("Associated Articles:"))

        # Associated articles list
        self.article_list = QListWidget()
        self.article_list.itemClicked.connect(self.display_article_content)
        right_layout.addWidget(self.article_list)

        # New Section for Date Filtering
        filter_label = QLabel("Filter Articles by Date:")
        right_layout.addWidget(filter_label)

        # Create a layout for the date fields and buttons
        date_filter_layout = QVBoxLayout()

        # Start Date Section
        start_date_layout = QHBoxLayout()
        start_date_label = QLabel("Start Date:")
        start_date_layout.addWidget(start_date_label)

        self.start_year_edit = QLineEdit()
        self.start_year_edit.setPlaceholderText("YYYY")
        self.start_year_edit.setFixedWidth(60)  # Adjust as needed
        self.start_month_edit = QLineEdit()
        self.start_month_edit.setPlaceholderText("MM")
        self.start_month_edit.setFixedWidth(40)  # Adjust as needed
        self.start_day_edit = QLineEdit()
        self.start_day_edit.setPlaceholderText("DD")
        self.start_day_edit.setFixedWidth(40)  # Adjust as needed
        start_date_layout.addWidget(self.start_year_edit)
        start_date_layout.addWidget(self.start_month_edit)
        start_date_layout.addWidget(self.start_day_edit)

        date_filter_layout.addLayout(start_date_layout)

        # End Date Section
        end_date_layout = QHBoxLayout()
        end_date_label = QLabel("End Date:")
        end_date_layout.addWidget(end_date_label)

        self.end_year_edit = QLineEdit()
        self.end_year_edit.setPlaceholderText("YYYY")
        self.end_year_edit.setFixedWidth(60)  # Adjust as needed
        self.end_month_edit = QLineEdit()
        self.end_month_edit.setPlaceholderText("MM")
        self.end_month_edit.setFixedWidth(40)  # Adjust as needed
        self.end_day_edit = QLineEdit()
        self.end_day_edit.setPlaceholderText("DD")
        self.end_day_edit.setFixedWidth(40)  # Adjust as needed
        end_date_layout.addWidget(self.end_year_edit)
        end_date_layout.addWidget(self.end_month_edit)
        end_date_layout.addWidget(self.end_day_edit)

        date_filter_layout.addLayout(end_date_layout)

        # Apply Filter Button (Stacked text)
        apply_filter_button = QPushButton("Apply Date Filter")
        apply_filter_button.clicked.connect(self.apply_date_filter)
        apply_filter_layout = QVBoxLayout()
        apply_filter_layout.addWidget(apply_filter_button)

        # Add the apply filter button next to the date fields
        date_filter_layout.addLayout(apply_filter_layout)

        # Clear Filter Button
        self.clear_date_filter_button = QPushButton("Clear Filter")
        self.clear_date_filter_button.clicked.connect(self.clear_date_filter)
        date_filter_layout.addWidget(self.clear_date_filter_button)

        # Add the date filter section to the right layout
        right_layout.addLayout(date_filter_layout)

        # Event text viewer
        self.article_text_view = QTextEdit()
        self.article_text_view.setReadOnly(True)
        right_layout.addWidget(self.article_text_view)

        # Clear Viewer Button (Move to bottom of the text viewer)
        self.clear_viewer_button = QPushButton("Clear Viewer")
        self.clear_viewer_button.clicked.connect(self.clear_viewer)
        right_layout.addWidget(self.clear_viewer_button)

        right_panel.setLayout(right_layout)
        return right_panel


    def apply_date_filter(self):
        """Apply the date range filter to the associated articles list."""
        start_date = f"{self.start_date_year.text()}-{self.start_date_month.text()}-{self.start_date_day.text()}"
        end_date = f"{self.end_date_year.text()}-{self.end_date_month.text()}-{self.end_date_day.text()}"

        # Clear the list first
        self.article_list.clear()

        # Fetch filtered articles from the database (implement filtering in database manager)
        filtered_articles = self.db_manager.get_articles_by_character_and_date(self.current_character_id, start_date, end_date)

        for article in filtered_articles:
            item = QListWidgetItem(f"{article[0]} - {article[1]}")  # Display EventDate and EventTitle
            item.setData(Qt.UserRole, article[2])  # Store EventID as the user role data
            self.article_list.addItem(item)

    def clear_viewer(self):
        """Clears the event text viewer content."""
        self.article_text_view.clear()


    def clear_date_filter(self):
        """Clears the date range filter and resets the article list."""
        self.start_date_year.clear()
        self.start_date_month.clear()
        self.start_date_day.clear()
        self.end_date_year.clear()
        self.end_date_month.clear()
        self.end_date_day.clear()
        
        # Reload all articles without the date filter
        self.load_associated_articles()



    def view_article(self, item):
        """Displays the content of the selected article in the text viewer."""
        selected_article = item.text()  # Get the text of the selected article
        
        # Fetch article content based on the article title or other identifier
        article_content = self.db_manager.get_article_content_by_title(selected_article)
        
        if article_content:
            self.article_text_view.setText(article_content)
        else:
            self.article_text_view.setText(f"Content not found for {selected_article}")

    
    def load_articles(self):
        """Fetch and display articles based on date range filters."""
        # Implement logic here to fetch articles filtered by the date range
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        # Your SQL query to filter based on date range
        # For example:
        query = """
            SELECT EventDate, EventTitle, EventText FROM Events e
            JOIN EventCharacters ec ON e.EventID = ec.EventID
            WHERE ec.CharacterID = ? 
        """
        params = [self.current_character_id]
        if self.start_date_edit.date().isValid():
            query += " AND e.EventDate >= ?"
            params.append(start_date)
        if self.end_date_edit.date().isValid():
            query += " AND e.EventDate <= ?"
            params.append(end_date)

        self.cursor.execute(query, params)
        articles = self.cursor.fetchall()

        self.article_list.clear()
        for article in articles:
            self.article_list.addItem(f"{article[0]} - {article[1]}")    

    def load_characters(self, view=None):
        """Load characters into the left panel, filtering based on the selected view."""
        # Default to "All Characters" if no view is provided
        view = view or self.view_dropdown.currentText()

        # Clear the current list
        self.character_list.clear()

        # Build query based on selected view
        if view == "All Characters":
            query = "SELECT CharacterID, DisplayName, Reviewed FROM Characters ORDER BY DisplayName"
            params = []
        else:
            # Map the view to the correct hierarchy table
            hierarchy_tables = {
                "Primary Characters": "PrimaryCharacters",
                "Secondary Characters": "SecondaryCharacters",
                "Tertiary Characters": "TertiaryCharacters",
                "Quaternary Characters": "QuaternaryCharacters",
            }
            table = hierarchy_tables.get(view)
            query = f"""
                SELECT c.CharacterID, c.DisplayName, c.Reviewed
                FROM Characters c
                JOIN {table} h ON c.CharacterID = h.CharacterID
                ORDER BY c.DisplayName
            """
            params = []

        # Execute the query and populate the list
        try:
            self.cursor.execute(query, params)
            characters = self.cursor.fetchall()

            for character in characters:
                item = QListWidgetItem(character[1])  # DisplayName
                item.setData(Qt.UserRole, character[0])  # Store CharacterID

                # Highlight unreviewed characters in red
                if character[2] == 0:  # Reviewed == 0
                    item.setForeground(Qt.red)
                self.character_list.addItem(item)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error", f"Failed to load characters: {e}")


    def display_character_details(self, item):
        """Display the details of the selected character in the center panel."""
        previous_character_id = self.current_character_id
        self.current_character_id = item.data(Qt.UserRole)

        self.cursor.execute("SELECT * FROM Characters WHERE CharacterID = ?", (self.current_character_id,))
        character = self.cursor.fetchone()

        # Clear the previous content
        self.clear_layout(self.lower_layout)

        if previous_character_id != self.current_character_id:
            self.article_text_view.clear()

        if character:
            columns = [column[0] for column in self.cursor.description]
            character_dict = dict(zip(columns, character))

            # Update display name
            self.display_name_label.setText(character_dict.get('DisplayName', 'Unknown'))

            # Update image
            if character_dict.get('ImagePath'):
                pixmap = QPixmap(character_dict['ImagePath'])
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.image_label.clear()
                self.image_label.setText("No Image")

            # Update the current level label
            current_level = self.get_character_level(self.current_character_id)
            self.current_level_label.setText(f"Current Level: {current_level}")

            # Reset the dropdown to "Change Level"
            self.level_dropdown.setCurrentIndex(0)

            # Update the vitals section
            self.update_vitals_section(character_dict)

            # Add Associations first
            field_label = QLabel("<b>Associations:</b>")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            self.lower_layout.addWidget(field_label)

            # Get and display associations
            occupations = self.db_manager.get_character_occupations(self.current_character_id)
            if occupations:
                for occupation in occupations:
                    location_name = occupation[0]
                    role_type = occupation[1]
                    start_date = occupation[2]
                    end_date = occupation[3]

                    # Create and add the AssociationWidget
                    association_widget = AssociationWidget(
                        location_name=location_name,
                        role=role_type,
                        character_id=self.current_character_id,
                        db_manager=self.db_manager
                    )

                    # If we have existing dates, set them
                    if start_date or end_date:
                        date_text = f", {start_date or ''}-{end_date or ''}"
                        association_widget.date_label.setText(f"{date_text})")
                        association_widget.add_dates_btn.hide()
                        association_widget.edit_dates_btn.show()

                    self.lower_layout.addWidget(association_widget)

                self.lower_layout.addSpacing(10)

            # Add remaining fields
            self.add_additional_fields(self.lower_layout, character_dict)

            # Load associated articles
            self.load_associated_articles()

    def update_vitals_section(self, character_dict):
        """Update the vitals section with the latest character details."""
        # Clear the vitals section layout before updating
        for i in reversed(range(self.vitals_section_layout.count())):
            widget = self.vitals_section_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # Create a new vitals section with updated character data
        self.vitals_section = self.create_vitals_section(character_dict)

        # Add the updated vitals section to the container
        self.vitals_section_layout.addWidget(self.vitals_section)




    def load_associated_articles(self):
        """Load articles associated with the selected character."""
        self.article_list.clear()
        if not self.current_character_id:
            return

        try:
            associated_articles = self.db_manager.get_articles_by_character(self.current_character_id)
            
            for article in associated_articles:
                # Format: "YYYY-MM-DD - Event Title"
                date = article[0] if article[0] else "No Date"
                title = article[1] if article[1] else "Untitled"
                item = QListWidgetItem(f"{date} - {title}")
                item.setData(Qt.UserRole, article[2])  # Store EventID
                # Store EventText for display without needing another query
                item.setData(Qt.UserRole + 1, article[3])
                self.article_list.addItem(item)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load associated articles: {str(e)}")



    def create_image_section(self, character_dict=None):
        """Create the image section of the profile. character_dict is optional and only needed when displaying details."""
        image_widget = QWidget()
        layout = QVBoxLayout(image_widget)

        # Image Display
        self.image_label = QLabel()
        self.image_label.setFixedSize(200, 200)
        if character_dict and character_dict.get('ImagePath'):
            pixmap = QPixmap(character_dict['ImagePath'])
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.image_label)

        # Change Photo Button
        change_photo_button = QPushButton("Change Photo")
        change_photo_button.clicked.connect(self.change_photo)
        layout.addWidget(change_photo_button)

        # Current Level Display (Optional)
        self.current_level_label = QLabel("Current Level: Tertiary")  # Default value
        self.current_level_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(self.current_level_label)

        # Dropdown for Changing Level
        self.level_dropdown = QComboBox()
        self.level_dropdown.addItems(["Change Level", "Primary", "Secondary", "Tertiary", "Quaternary"])
        self.level_dropdown.setCurrentIndex(0)  # Default to "Change Level"
        self.level_dropdown.currentTextChanged.connect(self.change_character_level)
        layout.addWidget(self.level_dropdown)

        return image_widget



    def create_vitals_section(self, character_dict=None):
        vitals_widget = QWidget()
        layout = QFormLayout(vitals_widget)
        layout.setVerticalSpacing(10)

        fields = [
            ('Name', lambda d: f"{d.get('FirstName', '')} {d.get('LastName', '')}"),
            ('Aliases', 'Aliases'),
            ('Gender', 'Gender'),
            ('BirthDate', 'BirthDate'),
            ('DeathDate', 'DeathDate'),
            ('Height', 'Height'),
            ('Weight', 'Weight'),
            ('Eyes', 'Eyes'),
            ('Hair', 'Hair'),
            ('Occupation', 'Occupation')
        ]

        for label, field in fields:
            field_label = QLabel(f"{label}:")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            
            if label == 'Aliases':
                aliases_text = QTextEdit()
                if character_dict:
                    aliases_text.setPlainText(str(character_dict.get(field, '')))
                aliases_text.setReadOnly(True)
                aliases_text.setMaximumHeight(40)
                layout.addRow(field_label, aliases_text)
            else:
                field_value = QLabel()
                if character_dict:
                    if callable(field):
                        value = field(character_dict)
                    else:
                        value = str(character_dict.get(field, ''))
                    field_value.setText(value)
                field_value.setWordWrap(True)
                layout.addRow(field_label, field_value)

        return vitals_widget

    def add_additional_fields(self, layout, character_dict):
        # Define fields without Associations
        fields = [('Affiliations', 'Affiliations'), 
                ('BackgroundSummary', 'Background'), 
                'PersonalityTraits', 
                'Family', 
                'FindAGrave']

        for field in fields:
            field_name = field[1] if isinstance(field, tuple) else field
            db_field = field[0] if isinstance(field, tuple) else field
            
            # Create label
            field_label = QLabel(f"<b>{field_name}:</b>")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            layout.addWidget(field_label)
            
            # Create value label
            value_label = QLabel(character_dict.get(db_field, ''))
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(value_label)
            
            layout.addSpacing(10)

    def display_article_content(self, item):
        """Display the content of the selected article in the text viewer."""
        if not item:
            return
            
        try:
            # Get the stored event text directly from the item
            event_text = item.data(Qt.UserRole + 1)
            if event_text:
                self.article_text_view.setText(event_text)
            else:
                self.article_text_view.setText("No content available for this article.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to display article content: {str(e)}")


    def change_photo(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            pixmap = QPixmap(file_name)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.update_image_path(file_name)
            else:
                QMessageBox.warning(self, "Error", "Failed to load the selected image.")

    def update_image_path(self, file_path):
        try:
            self.cursor.execute('''
                UPDATE Characters
                SET ImagePath = ?
                WHERE CharacterID = ?
            ''', (file_path, self.current_character_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating image path: {str(e)}")
            QMessageBox.critical(self, "Database Error", f"Error updating image path: {str(e)}")

    def mark_character_reviewed(self):
        if not self.current_character_id:
            QMessageBox.warning(self, "No Character Selected", "Please select a character to mark as reviewed.")
            return

        try:
            # Update the Reviewed status in the database
            self.cursor.execute("UPDATE Characters SET Reviewed = 1 WHERE CharacterID = ?", (self.current_character_id,))
            self.conn.commit()

            # Refresh the character list to update the display color
            self.load_characters()
            QMessageBox.information(self, "Marked as Reviewed", "Character has been marked as reviewed.")

        except sqlite3.Error as e:
            print(f"Error marking character as reviewed: {e}")
            QMessageBox.warning(self, "Database Error", f"Failed to mark character as reviewed: {e}")


    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def add_new_character(self):
        dialog = CharacterDialog(self)
        if dialog.exec_():
            character_data = dialog.get_character_data()
            try:
                # Insert the new character with DisplayName as a primary field
                self.cursor.execute('''
                    INSERT INTO Characters (
                        FirstName, LastName, DisplayName, Aliases, Gender, BirthDate, DeathDate,
                        Height, Weight, Hair, Eyes, Occupation, Affiliations, BackgroundSummary,
                        PersonalityTraits, ClifftonStrengths, Enneagram, MyersBriggs, FindAGrave
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    character_data['FirstName'], 
                    character_data['LastName'], 
                    character_data['DisplayName'],  # Ensures DisplayName is saved as expected
                    character_data['Aliases'], 
                    character_data['Gender'], 
                    character_data['BirthDate'],
                    character_data['DeathDate'], 
                    character_data['Height'], 
                    character_data['Weight'],
                    character_data['Hair'], 
                    character_data['Eyes'], 
                    character_data['Occupation'],
                    character_data['Affiliations'], 
                    character_data['BackgroundSummary'],
                    character_data['PersonalityTraits'], 
                    character_data['ClifftonStrengths'],
                    character_data['Enneagram'], 
                    character_data['MyersBriggs'], 
                    character_data['FindAGrave']
                ))
                self.conn.commit()
                # Reload character list to reflect the new entry, which will use DisplayName in the display
                self.load_characters()
                QMessageBox.information(self, "Success", "New character added successfully!")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to add character: {str(e)}")


    def edit_character(self):
        if not self.current_character_id:
            QMessageBox.warning(self, "Warning", "Please select a character to edit.")
            return

        current_item = self.character_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a character to edit.")
            return

        # Get current character data
        self.cursor.execute("SELECT * FROM Characters WHERE CharacterID = ?", (self.current_character_id,))
        character = self.cursor.fetchone()
        if character:
            columns = [column[0] for column in self.cursor.description]
            character_dict = dict(zip(columns, character))
            
            dialog = CharacterDialog(self, character_dict)
            if dialog.exec_():
                updated_data = dialog.get_character_data()
                try:
                    self.cursor.execute('''
                        UPDATE Characters SET
                        FirstName = ?, LastName = ?, DisplayName = ?, Aliases = ?, Gender = ?,
                        BirthDate = ?, DeathDate = ?, Height = ?, Weight = ?, Hair = ?, Eyes = ?,
                        Occupation = ?, Affiliations = ?, BackgroundSummary = ?,
                        PersonalityTraits = ?, ClifftonStrengths = ?, Enneagram = ?, MyersBriggs = ?,
                        FindAGrave = ?
                        WHERE CharacterID = ?
                    ''', (updated_data['FirstName'], updated_data['LastName'], updated_data['DisplayName'],
                        updated_data['Aliases'], updated_data['Gender'], updated_data['BirthDate'],
                        updated_data['DeathDate'], updated_data['Height'], updated_data['Weight'],
                        updated_data['Hair'], updated_data['Eyes'], updated_data['Occupation'],
                        updated_data['Affiliations'], updated_data['BackgroundSummary'],
                        updated_data['PersonalityTraits'], updated_data['ClifftonStrengths'],
                        updated_data['Enneagram'], updated_data['MyersBriggs'], updated_data['FindAGrave'],
                        self.current_character_id))
                    self.conn.commit()
                    
                    # After updating character, update all entities' KnownMembers
                    if 'Affiliations' in updated_data:
                        self.db_manager.update_character_affiliations(
                            self.current_character_id, 
                            updated_data['Affiliations']
                        )
                    
                    self.load_characters()
                    
                    # Safely refresh the display
                    if self.character_list.currentItem():
                        self.display_character_details(self.character_list.currentItem())
                    QMessageBox.information(self, "Success", "Character updated successfully!")
                except sqlite3.Error as e:
                    QMessageBox.critical(self, "Error", f"Failed to update character: {str(e)}")
        else:
            QMessageBox.warning(self, "Error", "Failed to retrieve character data.")

    def delete_character(self):
        if not self.current_character_id:
            QMessageBox.warning(self, "Warning", "Please select a character to delete.")
            return

        reply = QMessageBox.question(self, 'Delete Character', 'Are you sure you want to delete this character?',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # Delete the character from the Characters table
                self.cursor.execute("DELETE FROM Characters WHERE CharacterID = ?", (self.current_character_id,))
                
                # Delete the character's associations from the EventCharacters junction table
                self.cursor.execute("DELETE FROM EventCharacters WHERE CharacterID = ?", (self.current_character_id,))
                
                self.conn.commit()
                self.load_characters()
                QMessageBox.information(self, "Success", "Character deleted successfully!")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to delete character: {str(e)}")

    def get_character_level(self, character_id):
        """Retrieve the hierarchy level for a specific character."""
        levels = ["Primary", "Secondary", "Tertiary", "Quaternary"]
        for level in levels:
            table = f"{level}Characters"
            self.cursor.execute(f"SELECT 1 FROM {table} WHERE CharacterID = ?", (character_id,))
            if self.cursor.fetchone():
                return level
        return "Tertiary"  # Default level if no match


    def change_character_level(self, new_level):
        """Change the hierarchy level of the selected character."""
        if new_level == "Change Level" or not self.current_character_id:
            return

        levels = {
            "Primary": "PrimaryCharacters",
            "Secondary": "SecondaryCharacters",
            "Tertiary": "TertiaryCharacters",
            "Quaternary": "QuaternaryCharacters",
        }
        new_table = levels[new_level]

        try:
            # Remove the character from all hierarchy tables
            for table in levels.values():
                self.cursor.execute(f"DELETE FROM {table} WHERE CharacterID = ?", (self.current_character_id,))

            # Add the character to the new hierarchy table
            self.cursor.execute(f"INSERT INTO {new_table} (CharacterID) VALUES (?)", (self.current_character_id,))
            self.conn.commit()

            # Update the left panel list to remove the character from the current view
            self.load_characters()

            # Update the center panel to reflect the new level
            self.current_level_label.setText(f"Current Level: {new_level}")
            self.level_dropdown.setCurrentIndex(0)  # Reset dropdown to "Change Level"

            QMessageBox.information(self, "Success", f"Character moved to {new_level} level.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error", f"Failed to change character level: {str(e)}")




class AssociationWidget(QWidget):
    def __init__(self, location_name, role, character_id, db_manager, parent=None):
        super().__init__(parent)
        self.location_name = location_name
        self.role = role
        self.character_id = character_id
        self.db_manager = db_manager
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Base text
        self.text_label = QLabel(f"{self.location_name} ({self.role}")
        layout.addWidget(self.text_label)
        
        # Date display (initially empty)
        self.date_label = QLabel(")")
        layout.addWidget(self.date_label)
        
        # Add dates button
        self.add_dates_btn = QPushButton("+Dates")
        self.add_dates_btn.setMaximumWidth(50)
        self.add_dates_btn.clicked.connect(self.add_dates)
        layout.addWidget(self.add_dates_btn)
        
        # Edit dates button (initially hidden)
        self.edit_dates_btn = QPushButton("Edit")
        self.edit_dates_btn.setMaximumWidth(40)
        self.edit_dates_btn.clicked.connect(self.edit_dates)
        self.edit_dates_btn.hide()
        layout.addWidget(self.edit_dates_btn)
        
        layout.addStretch()

    def add_dates(self):
        dialog = DateRangeDialog(self, self.location_name, self.role)
        if dialog.exec_():
            dates = dialog.get_dates()
            if dates['start_date'] or dates['end_date']:
                # Get LocationID
                location_id = self.db_manager.get_location_id_by_name(self.location_name)
                if location_id:
                    # Update the database
                    self.db_manager.update_location_occupation_dates(
                        location_id,
                        self.character_id,
                        self.role,
                        dates['start_date'],
                        dates['end_date']
                    )
                    # Update the display
                    date_text = f", {dates['start_date'] or ''}-{dates['end_date'] or ''}"
                    self.date_label.setText(f"{date_text})")
                    self.add_dates_btn.hide()
                    self.edit_dates_btn.show()

    def edit_dates(self):
        dialog = DateRangeDialog(self, self.location_name, self.role)
        if dialog.exec_():
            dates = dialog.get_dates()
            if dates['start_date'] or dates['end_date']:
                location_id = self.db_manager.get_location_id_by_name(self.location_name)
                if location_id:
                    # Update the database
                    self.db_manager.update_location_occupation_dates(
                        location_id,
                        self.character_id,
                        self.role,
                        dates['start_date'],
                        dates['end_date']
                    )
                    # Update the display
                    date_text = f", {dates['start_date'] or ''}-{dates['end_date'] or ''}"
                    self.date_label.setText(f"{date_text})")         



class DateRangeDialog(QDialog):
    def __init__(self, parent=None, location_name="", role=""):
        super().__init__(parent)
        self.setWindowTitle(f"Add Dates - {location_name} ({role})")
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Start Year
        self.start_year = QLineEdit()
        self.start_year.setPlaceholderText("YYYY")
        self.start_year.setFixedWidth(60)
        form_layout.addRow("Start Year:", self.start_year)

        # End Year
        self.end_year = QLineEdit()
        self.end_year.setPlaceholderText("YYYY")
        self.end_year.setFixedWidth(60)
        form_layout.addRow("End Year:", self.end_year)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_dates(self):
        return {
            'start_date': self.start_year.text() if self.start_year.text() else None,
            'end_date': self.end_year.text() if self.end_year.text() else None
        }