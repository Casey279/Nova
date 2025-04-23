# File: sources_tab.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QMessageBox, 
                          QPushButton, QLineEdit, QSplitter, QFormLayout, QFileDialog, 
                          QDialog, QComboBox, QDialogButtonBox, QFrame, QListWidgetItem,
                          QTextEdit, QScrollArea)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont
from database_manager import DatabaseManager


class SourcesTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_manager = DatabaseManager(db_path)
        self.current_source_id = None
        self.image_path = None
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout()
        self.setLayout(layout)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        left_panel = self.create_source_list_section()
        splitter.addWidget(left_panel)

        center_panel = self.create_source_details_section()
        splitter.addWidget(center_panel)

        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([200, 400, 200])
        self.load_sources_list()

    def create_source_list_section(self):
        left_panel = QWidget()
        layout = QVBoxLayout(left_panel)

        layout.addWidget(QLabel("Source List"))
        
        self.source_list = QListWidget()
        self.source_list.itemSelectionChanged.connect(self.on_source_selected)
        layout.addWidget(self.source_list)

        add_source_button = QPushButton("Add New Source")
        add_source_button.clicked.connect(self.open_add_source_dialog)
        layout.addWidget(add_source_button)

        return left_panel

    def create_source_details_section(self):
        center_panel = QWidget()
        layout = QVBoxLayout(center_panel)

        # Status indicator
        self.review_status_label = QLabel()
        self.review_status_label.setStyleSheet("QLabel { color: red; }")
        layout.addWidget(self.review_status_label)

        # Source Name at the top
        self.source_name_label = QLabel()
        self.source_name_label.setAlignment(Qt.AlignCenter)
        self.source_name_label.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(self.source_name_label)

        # Upper Section: Image and Vitals
        upper_section = QFrame()
        upper_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        upper_section.setLineWidth(2)
        upper_layout = QHBoxLayout(upper_section)

        # Image Section
        image_section = QWidget()
        image_layout = QVBoxLayout(image_section)
        
        self.source_image_label = QLabel()
        self.source_image_label.setFixedSize(200, 200)
        self.source_image_label.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.source_image_label)

        upload_button = QPushButton("Upload/Change Image")
        upload_button.clicked.connect(self.upload_image)
        image_layout.addWidget(upload_button)
        
        upper_layout.addWidget(image_section)

        # Vitals Section
        vitals_section = QWidget()
        vitals_layout = QFormLayout(vitals_section)
        vitals_layout.setVerticalSpacing(10)

        self.source_type_label = QLabel()
        self.aliases_text_edit = QTextEdit()
        self.aliases_text_edit.setReadOnly(True)
        self.aliases_text_edit.setMaximumHeight(60)
        self.publisher_label = QLabel()
        self.location_label = QLabel()
        self.established_date_label = QLabel()
        self.discontinued_date_label = QLabel()

        vitals_layout.addRow("<b>Type:</b>", self.source_type_label)
        vitals_layout.addRow("<b>Aliases:</b>", self.aliases_text_edit)
        vitals_layout.addRow("<b>Publisher:</b>", self.publisher_label)
        vitals_layout.addRow("<b>Location:</b>", self.location_label)
        vitals_layout.addRow("<b>Established:</b>", self.established_date_label)
        vitals_layout.addRow("<b>Discontinued:</b>", self.discontinued_date_label)

        upper_layout.addWidget(vitals_section)
        layout.addWidget(upper_section)

        # Lower Section: Additional Information
        lower_section = QScrollArea()
        lower_section.setWidgetResizable(True)
        lower_widget = QWidget()
        lower_layout = QVBoxLayout(lower_widget)

        # Political Affiliations
        self.political_affiliations_text = QTextEdit()
        self.political_affiliations_text.setReadOnly(True)
        self.political_affiliations_text.setMaximumHeight(100)
        political_title = QLabel("<b>Political Affiliations:</b>")
        lower_layout.addWidget(political_title)
        lower_layout.addWidget(self.political_affiliations_text)
        lower_layout.addSpacing(10)

        # Summary
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(150)
        summary_title = QLabel("<b>Summary:</b>")
        lower_layout.addWidget(summary_title)
        lower_layout.addWidget(self.summary_text)
        
        lower_section.setWidget(lower_widget)
        layout.addWidget(lower_section)

        # Action Buttons
        button_layout = QHBoxLayout()
        
        self.edit_button = QPushButton("Edit Source")
        self.edit_button.clicked.connect(self.edit_source)
        button_layout.addWidget(self.edit_button)

        self.mark_reviewed_button = QPushButton("Mark as Reviewed")
        self.mark_reviewed_button.clicked.connect(self.mark_source_reviewed)
        self.mark_reviewed_button.setEnabled(False)
        button_layout.addWidget(self.mark_reviewed_button)

        layout.addLayout(button_layout)

        return center_panel

    def create_right_panel(self):
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        right_layout.addWidget(QLabel("Associated Articles:"))

        self.article_list = QListWidget()
        self.article_list.itemClicked.connect(self.display_article_content)
        right_layout.addWidget(self.article_list)

        # Date Filtering Section
        filter_label = QLabel("Filter Articles by Date:")
        right_layout.addWidget(filter_label)

        date_filter_layout = QVBoxLayout()

        # Start Date Section
        start_date_layout = QHBoxLayout()
        start_date_layout.addWidget(QLabel("Start Date:"))

        self.start_year_edit = QLineEdit()
        self.start_year_edit.setPlaceholderText("YYYY")
        self.start_year_edit.setFixedWidth(60)
        self.start_month_edit = QLineEdit()
        self.start_month_edit.setPlaceholderText("MM")
        self.start_month_edit.setFixedWidth(40)
        self.start_day_edit = QLineEdit()
        self.start_day_edit.setPlaceholderText("DD")
        self.start_day_edit.setFixedWidth(40)

        start_date_layout.addWidget(self.start_year_edit)
        start_date_layout.addWidget(self.start_month_edit)
        start_date_layout.addWidget(self.start_day_edit)
        date_filter_layout.addLayout(start_date_layout)

        # End Date Section
        end_date_layout = QHBoxLayout()
        end_date_layout.addWidget(QLabel("End Date:"))

        self.end_year_edit = QLineEdit()
        self.end_year_edit.setPlaceholderText("YYYY")
        self.end_year_edit.setFixedWidth(60)
        self.end_month_edit = QLineEdit()
        self.end_month_edit.setPlaceholderText("MM")
        self.end_month_edit.setFixedWidth(40)
        self.end_day_edit = QLineEdit()
        self.end_day_edit.setPlaceholderText("DD")
        self.end_day_edit.setFixedWidth(40)

        end_date_layout.addWidget(self.end_year_edit)
        end_date_layout.addWidget(self.end_month_edit)
        end_date_layout.addWidget(self.end_day_edit)
        date_filter_layout.addLayout(end_date_layout)

        # Filter Buttons
        filter_buttons_layout = QHBoxLayout()
        apply_filter_button = QPushButton("Apply Filter")
        apply_filter_button.clicked.connect(self.apply_date_filter)
        clear_filter_button = QPushButton("Clear Filter")
        clear_filter_button.clicked.connect(self.clear_date_filter)
        
        filter_buttons_layout.addWidget(apply_filter_button)
        filter_buttons_layout.addWidget(clear_filter_button)
        date_filter_layout.addLayout(filter_buttons_layout)

        right_layout.addLayout(date_filter_layout)

        # Article Text Viewer
        self.article_text_view = QTextEdit()
        self.article_text_view.setReadOnly(True)
        right_layout.addWidget(self.article_text_view)

        # Clear Viewer Button
        clear_viewer_button = QPushButton("Clear Viewer")
        clear_viewer_button.clicked.connect(self.clear_viewer)
        right_layout.addWidget(clear_viewer_button)

        right_panel.setLayout(right_layout)
        return right_panel

    def load_sources_list(self):
        self.source_list.clear()
        sources = self.db_manager.get_all_sources()
        for source in sources:
            item = QListWidgetItem(f"{source['SourceName']}")
            # Set different colors based on review status
            if source['ReviewStatus'] == 'preliminary':
                item.setForeground(Qt.gray)  # Gray for preliminary entries
            elif source['ReviewStatus'] == 'needs_review':
                item.setForeground(Qt.red)   # Red for needs review
            item.setData(Qt.UserRole, source['SourceID'])
            self.source_list.addItem(item)

    def on_source_selected(self):
        selected_item = self.source_list.currentItem()
        if not selected_item:
            return

        source_id = selected_item.data(Qt.UserRole)
        source_data = self.db_manager.get_source_by_id(source_id)

        if source_data:
            self.current_source_id = source_data['SourceID']
            
            # Update review status
            if source_data.get('ReviewStatus') == 'needs_review':
                self.review_status_label.setText("⚠️ Needs Review")
                self.review_status_label.show()
                self.mark_reviewed_button.setEnabled(True)
            else:
                self.review_status_label.hide()
                self.mark_reviewed_button.setEnabled(False)
            
            # Update labels
            self.source_name_label.setText(source_data['SourceName'])
            
            # Map source type to full description
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
            self.source_type_label.setText(source_type_mapping.get(source_data['SourceType'], source_data['SourceType']))
            
            # Format and display aliases
            aliases_text = source_data.get('Aliases')
            if aliases_text:
                # Split by semicolon and join with newlines for better visibility
                aliases_list = [alias.strip() for alias in aliases_text.split(';')]
                self.aliases_text_edit.setPlainText('\n'.join(aliases_list))
            else:
                self.aliases_text_edit.setPlainText('N/A')
            
            self.publisher_label.setText(source_data.get('Publisher') or 'N/A')
            self.location_label.setText(source_data.get('Location') or 'N/A')
            self.established_date_label.setText(source_data.get('EstablishedDate') or 'N/A')
            self.discontinued_date_label.setText(source_data.get('DiscontinuedDate') or 'N/A')
            
            # Update new fields
            self.political_affiliations_text.setPlainText(source_data.get('PoliticalAffiliations') or 'N/A')
            self.summary_text.setPlainText(source_data.get('Summary') or 'N/A')

            if source_data.get('ImagePath'):
                pixmap = QPixmap(source_data['ImagePath'])
                self.source_image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.source_image_label.setText("No Image Available")

            # Load associated articles for the source
            self.load_source_articles()

    def mark_source_reviewed(self):
        if not self.current_source_id:
            return
            
        reply = QMessageBox.question(
            self,
            "Mark as Reviewed",
            "Are you sure this source's information is complete and correct?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db_manager.update_source_status(self.current_source_id, 'reviewed')
            self.review_status_label.hide()
            self.mark_reviewed_button.setEnabled(False)
            
            # Refresh the source list
            self.load_sources_list()
            
            # Reselect the current source to maintain selection
            for i in range(self.source_list.count()):
                if self.source_list.item(i).data(Qt.UserRole) == self.current_source_id:
                    self.source_list.setCurrentRow(i)
                    break
                    
            QMessageBox.information(self, "Success", "Source marked as reviewed.")

    def load_source_articles(self):
        self.article_list.clear()
        if self.current_source_id:
            articles = self.db_manager.get_events_by_source(self.current_source_id)
            for article in articles:
                item = QListWidgetItem(f"{article['EventDate']} - {article['EventTitle']} (ID: {article['EventID']})")
                item.setData(Qt.UserRole, article['EventID'])
                self.article_list.addItem(item)

    def apply_date_filter(self):
        if not self.current_source_id:
            return
            
        start_date = f"{self.start_year_edit.text()}-{self.start_month_edit.text()}-{self.start_day_edit.text()}"
        end_date = f"{self.end_year_edit.text()}-{self.end_month_edit.text()}-{self.end_day_edit.text()}"

        self.article_list.clear()
        articles = self.db_manager.get_events_by_source_and_date(self.current_source_id, start_date, end_date)
        
        for article in articles:
            item = QListWidgetItem(f"{article['EventDate']} - {article['EventTitle']} (ID: {article['EventID']})")
            item.setData(Qt.UserRole, article['EventID'])
            self.article_list.addItem(item)

    def clear_date_filter(self):
        self.start_year_edit.clear()
        self.start_month_edit.clear()
        self.start_day_edit.clear()
        self.end_year_edit.clear()
        self.end_month_edit.clear()
        self.end_day_edit.clear()
        
        self.load_source_articles()

    def clear_viewer(self):
        self.article_text_view.clear()

    def display_article_content(self, item):
        event_id = item.data(Qt.UserRole)
        event_content = self.db_manager.get_event_by_id(event_id)
        
        if event_content:
            self.article_text_view.setText(
                f"Title: {event_content['EventTitle']}\n"
                f"Date: {event_content['EventDate']}\n\n"
                f"{event_content['EventText']}"
            )
        else:
            self.article_text_view.setText("Content not available")

    def upload_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg)")
        if file_name and self.current_source_id:
            self.image_path = file_name
            pixmap = QPixmap(file_name)
            self.source_image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
            # Get current source data to preserve other fields
            source_data = self.db_manager.get_source_by_id(self.current_source_id)
            if source_data:
                self.db_manager.update_source(
                    self.current_source_id,
                    source_data['SourceName'],
                    source_data['SourceType'],
                    source_data.get('Abbreviation'),
                    source_data.get('Publisher', ''),
                    source_data.get('Location', ''),
                    source_data.get('EstablishedDate', ''),
                    source_data.get('DiscontinuedDate', ''),
                    file_name,  # New image path
                    source_data.get('Aliases', ''),
                    source_data.get('PoliticalAffiliations', ''),
                    source_data.get('Summary', '')
                )

    def edit_source(self):
        if not self.current_source_id:
            return
            
        dialog = EditSourceDialog(self.db_manager, self.current_source_id)
        if dialog.exec_() == QDialog.Accepted:
            self.load_sources_list()
            for i in range(self.source_list.count()):
                if self.source_list.item(i).data(Qt.UserRole) == self.current_source_id:
                    self.source_list.setCurrentRow(i)
                    break

    def open_add_source_dialog(self):
        dialog = AddSourceDialog(self.db_manager)
        if dialog.exec_() == QDialog.Accepted:
            self.load_sources_list()

class AddSourceDialog(QDialog):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Add New Source")  # or "Edit Source" for EditSourceDialog
        self.setGeometry(200, 200, 400, 600)  # Made taller to accommodate new fields

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.source_name_input = QLineEdit()
        
        self.source_type_input = QComboBox()
        self.source_type_input.addItems([
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

        # Source Code field
        self.source_code_input = QLineEdit()
        self.source_code_input.setPlaceholderText("PI, TNT, etc. Leave empty for uncommon sources")
        
        self.aliases_input = QTextEdit()
        self.aliases_input.setPlaceholderText("Enter aliases separated by semicolons (e.g., Daily Intelligencer; Weekly Post-Intelligencer)")
        self.aliases_input.setMaximumHeight(100)
        
        self.publisher_input = QLineEdit()
        self.location_input = QLineEdit()
        self.established_date_input = QLineEdit()
        self.discontinued_date_input = QLineEdit()

        # Political Affiliations field
        self.political_affiliations_input = QTextEdit()
        self.political_affiliations_input.setPlaceholderText("Enter political affiliations and biases...")
        self.political_affiliations_input.setMaximumHeight(100)
        
        # Summary field
        self.summary_input = QTextEdit()
        self.summary_input.setPlaceholderText("Enter a summary of the source's history, significance, and any other relevant details...")
        self.summary_input.setMinimumHeight(100)

        form_layout.addRow("Source Name:", self.source_name_input)
        form_layout.addRow("Source Type:", self.source_type_input)
        form_layout.addRow("Source Code:", self.source_code_input)
        form_layout.addRow("Aliases:", self.aliases_input)
        form_layout.addRow("Publisher:", self.publisher_input)
        form_layout.addRow("Location:", self.location_input)
        form_layout.addRow("Established Date:", self.established_date_input)
        form_layout.addRow("Discontinued Date:", self.discontinued_date_input)
        form_layout.addRow("Political Affiliations:", self.political_affiliations_input)
        form_layout.addRow("Summary:", self.summary_input)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_source)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_source(self):
        source_type = self.source_type_input.currentText()[:1]
        aliases = '; '.join([alias.strip() for alias in self.aliases_input.toPlainText().splitlines() if alias.strip()])
        source_code = self.source_code_input.text().strip() or 'XX'  # Default to 'XX' if empty

        self.db_manager.insert_source(
            source_name=self.source_name_input.text(),
            source_type=source_type,
            publisher=self.publisher_input.text(),
            location=self.location_input.text(),
            established_date=self.established_date_input.text(),
            discontinued_date=self.discontinued_date_input.text(),
            image_path=None,
            aliases=aliases,
            review_status='reviewed',
            source_code=source_code,
            political_affiliations=self.political_affiliations_input.toPlainText(),
            summary=self.summary_input.toPlainText()
        )
        self.accept()

class EditSourceDialog(AddSourceDialog):
    def __init__(self, db_manager, source_id):
        self.source_id = source_id
        super().__init__(db_manager)
        self.setWindowTitle("Edit Source")
        self.setGeometry(200, 200, 400, 500)  # Restore the geometry
        self.load_source_data()

    def initUI(self):
        self.setWindowTitle("Add New Source")  # or "Edit Source" for EditSourceDialog
        self.setGeometry(200, 200, 400, 600)  # Made taller to accommodate new fields

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.source_name_input = QLineEdit()
        
        self.source_type_input = QComboBox()
        self.source_type_input.addItems([
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

        # Source Code field
        self.source_code_input = QLineEdit()
        self.source_code_input.setPlaceholderText("PI, TNT, etc. Leave empty for uncommon sources")
        
        self.aliases_input = QTextEdit()
        self.aliases_input.setPlaceholderText("Enter aliases separated by semicolons (e.g., Daily Intelligencer; Weekly Post-Intelligencer)")
        self.aliases_input.setMaximumHeight(100)
        
        self.publisher_input = QLineEdit()
        self.location_input = QLineEdit()
        self.established_date_input = QLineEdit()
        self.discontinued_date_input = QLineEdit()

        # Political Affiliations field
        self.political_affiliations_input = QTextEdit()
        self.political_affiliations_input.setPlaceholderText("Enter political affiliations and biases...")
        self.political_affiliations_input.setMaximumHeight(100)
        
        # Summary field
        self.summary_input = QTextEdit()
        self.summary_input.setPlaceholderText("Enter a summary of the source's history, significance, and any other relevant details...")
        self.summary_input.setMinimumHeight(100)

        form_layout.addRow("Source Name:", self.source_name_input)
        form_layout.addRow("Source Type:", self.source_type_input)
        form_layout.addRow("Source Code:", self.source_code_input)
        form_layout.addRow("Aliases:", self.aliases_input)
        form_layout.addRow("Publisher:", self.publisher_input)
        form_layout.addRow("Location:", self.location_input)
        form_layout.addRow("Established Date:", self.established_date_input)
        form_layout.addRow("Discontinued Date:", self.discontinued_date_input)
        form_layout.addRow("Political Affiliations:", self.political_affiliations_input)
        form_layout.addRow("Summary:", self.summary_input)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_source)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_source_data(self):
        source_data = self.db_manager.get_source_by_id(self.source_id)
        if source_data:
            self.source_name_input.setText(source_data['SourceName'])
            
            # Fix the source type combo box handling
            source_type = source_data['SourceType']
            for i in range(self.source_type_input.count()):
                if self.source_type_input.itemText(i).startswith(source_type):
                    self.source_type_input.setCurrentIndex(i)
                    break
            
            # Load source code
            self.source_code_input.setText(source_data.get('SourceCode', ''))
            
            # Load all other fields
            aliases = source_data.get('Aliases', '')
            if aliases:
                aliases_list = [alias.strip() for alias in aliases.split(';')]
                self.aliases_input.setPlainText('\n'.join(aliases_list))
            
            self.publisher_input.setText(source_data.get('Publisher', '') or '')
            self.location_input.setText(source_data.get('Location', '') or '')
            self.established_date_input.setText(source_data.get('EstablishedDate', '') or '')
            self.discontinued_date_input.setText(source_data.get('DiscontinuedDate', '') or '')
            self.political_affiliations_input.setPlainText(source_data.get('PoliticalAffiliations', '') or '')
            self.summary_input.setPlainText(source_data.get('Summary', '') or '')

    def save_source(self):
        print("Saving source edit...")  # Debug print
        source_type = self.source_type_input.currentText()[:1]
        aliases = '; '.join([alias.strip() for alias in self.aliases_input.toPlainText().splitlines() if alias.strip()])
        source_code = self.source_code_input.text().strip() or 'XX'

        self.db_manager.update_source(
            source_id=self.source_id,  # Important - this is needed for update
            source_name=self.source_name_input.text(),
            source_type=source_type,
            publisher=self.publisher_input.text(),
            location=self.location_input.text(),
            established_date=self.established_date_input.text(),
            discontinued_date=self.discontinued_date_input.text(),
            image_path=None,
            aliases=aliases,
            political_affiliations=self.political_affiliations_input.toPlainText(),
            summary=self.summary_input.toPlainText(),
            source_code=source_code
        )
        self.accept()

    def mark_source_reviewed(self):
        if not self.current_source_id:
            return
            
        reply = QMessageBox.question(
            self,
            "Mark as Reviewed",
            "Are you sure this source's information is complete and correct?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db_manager.update_source_status(self.current_source_id, 'reviewed')
            self.review_status_label.hide()
            self.mark_reviewed_button.setEnabled(False)
            
            # Refresh the source list
            self.load_sources_list()
            
            # Reselect the current source to maintain selection
            for i in range(self.source_list.count()):
                if self.source_list.item(i).data(Qt.UserRole) == self.current_source_id:
                    self.source_list.setCurrentRow(i)
                    break
                    
            QMessageBox.information(self, "Success", "Source marked as reviewed.")        