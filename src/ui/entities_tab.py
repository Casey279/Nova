# File: entities_tab.py

import os
import sqlite3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
                           QLabel, QLineEdit, QTextEdit, QFormLayout, QScrollArea, 
                           QSplitter, QListWidgetItem, QFileDialog, QMessageBox, QFrame,
                           QDialog, QDialogButtonBox)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt
from database_manager import DatabaseManager
from pathlib import Path

class EntityDialog(QDialog):
    def __init__(self, parent=None, entity_data=None):
        super().__init__(parent)
        self.entity_data = entity_data
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Entity Details")
        layout = QVBoxLayout(self)

        # Entity details form
        form_layout = QFormLayout()

        self.fields = {}
        # Basic fields
        for field in ['DisplayName', 'Name', 'Aliases', 'Type', 'EstablishedDate', 'Affiliation']:
            self.fields[field] = QLineEdit()
            if self.entity_data:
                self.fields[field].setText(str(self.entity_data.get(field, '')))
            form_layout.addRow(field, self.fields[field])

        # TextEdit fields for longer content
        for field in ['Description', 'Summary']:
            self.fields[field] = QTextEdit()
            if self.entity_data:
                self.fields[field].setPlainText(str(self.entity_data.get(field, '')))
            form_layout.addRow(field, self.fields[field])

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_entity_data(self):
        data = {}
        for field, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                data[field] = widget.text()
            else:  # QTextEdit
                data[field] = widget.toPlainText()
        
        if self.entity_data and 'ImagePath' in self.entity_data:
            data['ImagePath'] = self.entity_data['ImagePath']
        else:
            data['ImagePath'] = None
            
        # Don't include KnownMembers in the data as it's handled separately
        return data

class EntitiesTab(QWidget):
    def __init__(self,
                 db_path: str | None = None,
                 project_root: Path | None = None):
        super().__init__()
        self.db_path      = db_path
        self.project_root = Path(project_root) if project_root else None
        self.db_manager   = (DatabaseManager(db_path, project_root)
                             if db_path and project_root else None)
        self.initUI()

    def set_db_context(self, db_manager, project_root: Path):
        self.db_manager   = db_manager
        self.project_root = project_root
        # if you have a reload/refresh method, call it here

    def initUI(self):
        layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)

        # Left panel - Entity list
        left_panel = self.create_left_panel()
        self.splitter.addWidget(left_panel)

        # Middle panel - Entity details
        middle_panel = self.create_middle_panel()
        self.splitter.addWidget(middle_panel)

        # Right panel - Associated articles
        right_panel = self.create_right_panel()
        self.splitter.addWidget(right_panel)

        layout.addWidget(self.splitter)

        # Set initial sizes
        self.splitter.setSizes([200, 400, 200])

    def create_left_panel(self):
        left_panel = QWidget()
        layout = QVBoxLayout(left_panel)

        # Entity list
        self.entity_list = QListWidget()
        self.entity_list.itemClicked.connect(self.display_entity_details)
        layout.addWidget(self.entity_list)

        # Add and Delete buttons
        add_button = QPushButton("Add New Entity")
        add_button.clicked.connect(self.add_new_entity)
        layout.addWidget(add_button)

        delete_button = QPushButton("Delete Entity")
        delete_button.clicked.connect(self.delete_entity)
        layout.addWidget(delete_button)

        return left_panel

    def create_middle_panel(self):
        middle_panel = QWidget()
        layout = QVBoxLayout(middle_panel)

        # Entity Name at the top
        self.entity_name_label = QLabel()
        self.entity_name_label.setAlignment(Qt.AlignCenter)
        self.entity_name_label.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(self.entity_name_label)

        # Upper Section: Image and Vitals
        upper_section = QFrame()
        upper_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        upper_section.setLineWidth(2)
        upper_layout = QHBoxLayout(upper_section)

        # Image Section
        image_section = self.create_image_section()
        upper_layout.addWidget(image_section)

        # Vitals Section
        vitals_section = self.create_vitals_section()  # New method for vitals
        upper_layout.addWidget(vitals_section)

        layout.addWidget(upper_section)

        # Lower Section: Additional Information
        lower_section = QScrollArea()
        lower_section.setWidgetResizable(True)
        lower_widget = QWidget()
        self.lower_layout = QVBoxLayout(lower_widget)
        lower_section.setWidget(lower_widget)
        layout.addWidget(lower_section)

        button_layout = QHBoxLayout()
        
        self.edit_entity_button = QPushButton("Edit Entity")
        self.edit_entity_button.clicked.connect(self.edit_entity)
        button_layout.addWidget(self.edit_entity_button)

        self.mark_reviewed_button = QPushButton("Mark as Reviewed")
        self.mark_reviewed_button.clicked.connect(self.mark_entity_reviewed)
        self.mark_reviewed_button.setEnabled(False)
        button_layout.addWidget(self.mark_reviewed_button)

        layout.addLayout(button_layout)

        return middle_panel

    def create_image_section(self):
        image_widget = QWidget()
        layout = QVBoxLayout(image_widget)

        self.image_label = QLabel()
        self.image_label.setFixedSize(200, 200)
        layout.addWidget(self.image_label)

        change_photo_button = QPushButton("Change Photo")
        change_photo_button.clicked.connect(self.change_photo)
        layout.addWidget(change_photo_button)

        return image_widget
    
    def create_vitals_section(self):
        vitals_widget = QWidget()
        layout = QFormLayout(vitals_widget)
        layout.setVerticalSpacing(10)

        fields = [
            ('Name', 'Name'),
            ('Aliases', 'Aliases'),
            ('Type', 'Type'),
            ('Established Date', 'EstablishedDate'),
            ('Dissolved Date', 'DissolvedDate'),
            ('Affiliation', 'Affiliation')
        ]

        for label, field in fields:
            field_label = QLabel(f"{label}:")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))

            if label == 'Aliases':
                # Multi-line field
                self.vitals_labels[field] = QTextEdit()
                self.vitals_labels[field].setReadOnly(True)
                self.vitals_labels[field].setMaximumHeight(40)
                layout.addRow(field_label, self.vitals_labels[field])
            else:
                # Single-line field
                self.vitals_labels[field] = QLabel()
                self.vitals_labels[field].setWordWrap(True)
                layout.addRow(field_label, self.vitals_labels[field])

        return vitals_widget


    def create_right_panel(self):
        right_panel = QWidget()
        layout = QVBoxLayout(right_panel)

        # Associated Articles section
        layout.addWidget(QLabel("Associated Articles:"))

        self.article_list = QListWidget()
        self.article_list.itemClicked.connect(self.display_article_content)
        layout.addWidget(self.article_list)

        # Date Filtering
        filter_layout = QVBoxLayout()
        filter_label = QLabel("Filter Articles by Date:")
        filter_layout.addWidget(filter_label)

        # Start Date Section
        start_date_layout = QHBoxLayout()
        start_date_label = QLabel("Start Date:")
        start_date_layout.addWidget(start_date_label)

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
        filter_layout.addLayout(start_date_layout)

        # End Date Section
        end_date_layout = QHBoxLayout()
        end_date_label = QLabel("End Date:")
        end_date_layout.addWidget(end_date_label)

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
        filter_layout.addLayout(end_date_layout)

        # Filter Buttons
        apply_filter_button = QPushButton("Apply Date Filter")
        apply_filter_button.clicked.connect(self.apply_date_filter)
        filter_layout.addWidget(apply_filter_button)

        clear_filter_button = QPushButton("Clear Filter")
        clear_filter_button.clicked.connect(self.clear_date_filter)
        filter_layout.addWidget(clear_filter_button)

        layout.addLayout(filter_layout)

        # Article Text Viewer
        self.article_text_view = QTextEdit()
        self.article_text_view.setReadOnly(True)
        layout.addWidget(self.article_text_view)

        # Clear Viewer Button
        clear_viewer_button = QPushButton("Clear Viewer")
        clear_viewer_button.clicked.connect(self.clear_viewer)
        layout.addWidget(clear_viewer_button)

        return right_panel

    def mark_entity_reviewed(self):
        if not self.current_entity_id:
            return
            
        reply = QMessageBox.question(
            self,
            "Mark as Reviewed",
            "Are you sure this entity's information is complete and correct?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db_manager.update_entity_status(self.current_entity_id, 'reviewed')
            self.review_status_label.hide()
            self.mark_reviewed_button.setEnabled(False)
            
            # Refresh the entity list
            self.load_entities()
            
            # Reselect the current entity
            for i in range(self.entity_list.count()):
                if self.entity_list.item(i).data(Qt.UserRole) == self.current_entity_id:
                    self.entity_list.setCurrentRow(i)
                    break
            
            QMessageBox.information(self, "Success", "Entity marked as reviewed.")


    def display_entity_details(self, item):
        previous_entity_id = self.current_entity_id
        self.current_entity_id = item.data(Qt.UserRole)
        entity_data = self.db_manager.get_entity_by_id(self.current_entity_id)

        if entity_data:
            # Update entity name at the top
            self.entity_name_label.setText(entity_data['DisplayName'])

            # Clear the image label first, then update image if available
            self.image_label.clear()
            if entity_data.get('ImagePath'):
                pixmap = QPixmap(entity_data['ImagePath'])
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    self.image_label.setText("No Image")
            else:
                self.image_label.setText("No Image")

            # Update vitals section fields using `vitals_labels`
            for label_name, widget in self.vitals_labels.items():
                widget.clear()
                widget.setText(entity_data.get(label_name, '') if isinstance(widget, QLabel) else entity_data.get(label_name, ''))
            
            # Clear previous lower section and add additional information
            self.clear_layout(self.lower_layout)
            self.add_additional_fields(self.lower_layout, entity_data)

            # Load associated articles
            self.load_associated_articles()




    def add_additional_fields(self, layout, entity_data):
        # Clear the layout before adding new widgets
        self.clear_layout(layout)

        # Known Members Section
        known_members_label = QLabel("<b>Known Members:</b>")
        layout.addWidget(known_members_label)
        known_members = entity_data.get('KnownMembers', 'No known members')
        known_members_text = QLabel(known_members)
        layout.addWidget(known_members_text)
        
        # Description Section
        description_label = QLabel("<b>Description:</b>")
        layout.addWidget(description_label)
        description_text = QTextEdit(entity_data.get('Description', ''))
        description_text.setReadOnly(True)
        layout.addWidget(description_text)

        # Summary Section
        summary_label = QLabel("<b>Summary:</b>")
        layout.addWidget(summary_label)
        summary_text = QTextEdit(entity_data.get('Summary', ''))
        summary_text.setReadOnly(True)
        layout.addWidget(summary_text)

    def load_entities(self):
        self.entity_list.clear()
        entities = self.db_manager.get_all_entities()
        for entity in entities:
            item = QListWidgetItem(entity['DisplayName'])
            item.setData(Qt.UserRole, entity['EntityID'])
            self.entity_list.addItem(item)

    def add_new_entity(self):
        dialog = EntityDialog(self)
        if dialog.exec_():
            entity_data = dialog.get_entity_data()
            try:
                # Insert the basic entity data
                entity_id = self.db_manager.insert_entity(
                    display_name=entity_data['DisplayName'],
                    name=entity_data['Name'],
                    aliases=entity_data['Aliases'],
                    type_=entity_data['Type'],
                    description=entity_data['Description'],
                    established_date=entity_data['EstablishedDate'],
                    affiliation=entity_data['Affiliation'],
                    summary=entity_data['Summary'],
                    image_path=entity_data.get('ImagePath')
                )
                
                # After inserting, update the KnownMembers field
                if entity_id:
                    self.db_manager.update_known_members(entity_id)
                    
                self.load_entities()
                QMessageBox.information(self, "Success", "Entity added successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add entity: {str(e)}")

    def edit_entity(self):
        if not self.current_entity_id:
            QMessageBox.warning(self, "Warning", "Please select an entity to edit.")
            return

        entity_data = self.db_manager.get_entity_by_id(self.current_entity_id)
        if entity_data:
            dialog = EntityDialog(self, entity_data)
            if dialog.exec_():
                updated_data = dialog.get_entity_data()
                try:
                    self.db_manager.update_entity(
                        self.current_entity_id,
                        updated_data
                    )
                    self.load_entities()
                    
                    # Refresh the display
                    for i in range(self.entity_list.count()):
                        if self.entity_list.item(i).data(Qt.UserRole) == self.current_entity_id:
                            self.entity_list.setCurrentRow(i)
                            break
                            
                    QMessageBox.information(self, "Success", "Entity updated successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to update entity: {str(e)}")

    def delete_entity(self):
        if not self.current_entity_id:
            QMessageBox.warning(self, "Warning", "Please select an entity to delete.")
            return

        reply = QMessageBox.question(
            self, 'Delete Entity', 
            'Are you sure you want to delete this entity?',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.delete_entity(self.current_entity_id)
                self.load_entities()
                self.clear_entity_display()
                QMessageBox.information(self, "Success", "Entity deleted successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete entity: {str(e)}")

    def clear_entity_display(self):
        """Clear all entity display fields"""
        self.entity_name_label.clear()
        self.image_label.clear()  # Clear image here to ensure it's reset
        for label in self.vitals_labels.values():
            if isinstance(label, QLabel):
                label.clear()
            elif isinstance(label, QTextEdit):
                label.clear()
        self.clear_layout(self.lower_layout)
        self.article_list.clear()
        self.article_text_view.clear()
        self.current_entity_id = None


    def change_photo(self):
        if not self.current_entity_id:
            QMessageBox.warning(self, "Warning", "Please select an entity first.")
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        
        if file_name:
            try:
                self.db_manager.update_entity_image(self.current_entity_id, file_name)
                pixmap = QPixmap(file_name)
                if not pixmap.isNull():
                    self.image_label.setPixmap(
                        pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    raise Exception("Failed to load the image")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update image: {str(e)}")

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def load_associated_articles(self):
        self.article_list.clear()
        if self.current_entity_id:
            articles = self.db_manager.get_articles_by_entity(self.current_entity_id)
            for article in articles:
                item = QListWidgetItem(f"{article[0]} - {article[1]}")
                item.setData(Qt.UserRole, article[2])
                self.article_list.addItem(item)

    def display_article_content(self, item):
        event_id = item.data(Qt.UserRole)
        content = self.db_manager.get_event_content(event_id)
        if content:
            self.article_text_view.setText(content)
        else:
            self.article_text_view.setText("No content available for this article.")

    def apply_date_filter(self):
        if not self.current_entity_id:
            return
            
        start_date = f"{self.start_year_edit.text()}-{self.start_month_edit.text()}-{self.start_day_edit.text()}"
        end_date = f"{self.end_year_edit.text()}-{self.end_month_edit.text()}-{self.end_day_edit.text()}"
        
        self.article_list.clear()
        articles = self.db_manager.get_articles_by_entity_and_date(
            self.current_entity_id, start_date, end_date)
        
        for article in articles:
            item = QListWidgetItem(f"{article[0]} - {article[1]}")
            item.setData(Qt.UserRole, article[2])
            self.article_list.addItem(item)

    def clear_date_filter(self):
        self.start_year_edit.clear()
        self.start_month_edit.clear()
        self.start_day_edit.clear()
        self.end_year_edit.clear()
        self.end_month_edit.clear()
        self.end_day_edit.clear()
        self.load_associated_articles()

    def clear_viewer(self):
        self.article_text_view.clear()    