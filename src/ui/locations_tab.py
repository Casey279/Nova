# File: locations_tab.py

import sys
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
                           QLabel, QLineEdit, QTextEdit, QFormLayout, QScrollArea, 
                           QSplitter, QListWidgetItem, QFileDialog, QMessageBox, QFrame,
                           QDialog, QDialogButtonBox)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt
from database_manager import DatabaseManager

class LocationDialog(QDialog):
    def __init__(self, parent=None, location_data=None):
        super().__init__(parent)
        self.location_data = location_data
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Location Details")
        layout = QVBoxLayout(self)

        # Location details form
        form_layout = QFormLayout()

        self.fields = {}
        for field in ['DisplayName', 'LocationName', 'Aliases', 'Address', 'LocationType', 
                    'YearBuilt', 'Owners', 'Managers', 'Employees']:
            self.fields[field] = QLineEdit()
            if self.location_data:
                self.fields[field].setText(str(self.location_data.get(field, '')))
            form_layout.addRow(field, self.fields[field])

        # Summary field as QTextEdit
        self.fields['Summary'] = QTextEdit()
        if self.location_data:
            self.fields['Summary'].setPlainText(str(self.location_data.get('Summary', '')))
        form_layout.addRow('Summary:', self.fields['Summary'])

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_location_data(self):
        data = {field: widget.text() if isinstance(widget, QLineEdit) else 
                widget.toPlainText() for field, widget in self.fields.items()}
        if self.location_data and 'ImagePath' in self.location_data:
            data['ImagePath'] = self.location_data['ImagePath']
        else:
            data['ImagePath'] = None
        return data

class LocationsTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.current_location_id = None
        self.last_viewed_articles = {}
        self.initUI()
        self.load_locations()

    def initUI(self):
        layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)

        # Left panel - Location list
        left_panel = self.create_left_panel()
        self.splitter.addWidget(left_panel)

        # Middle panel - Location details
        middle_panel = self.create_middle_panel()
        self.splitter.addWidget(middle_panel)

        # Right panel - Associated articles
        right_panel = self.create_right_panel()
        self.splitter.addWidget(right_panel)

        layout.addWidget(self.splitter)

        # Set initial sizes (20%, 50%, 30%)
        self.splitter.setSizes([int(self.width() * 0.2), 
                              int(self.width() * 0.5), 
                              int(self.width() * 0.3)])

    def create_left_panel(self):
        left_panel = QWidget()
        layout = QVBoxLayout(left_panel)

        # Location list
        self.location_list = QListWidget()
        self.location_list.itemClicked.connect(self.display_location_details)
        layout.addWidget(self.location_list)

        # Add and Delete buttons
        add_button = QPushButton("Add New Location")
        add_button.clicked.connect(self.add_new_location)
        layout.addWidget(add_button)

        delete_button = QPushButton("Delete Location")
        delete_button.clicked.connect(self.delete_location)
        layout.addWidget(delete_button)

        return left_panel

    def create_middle_panel(self):
        middle_panel = QWidget()
        layout = QVBoxLayout(middle_panel)

        # Review status label at the top
        self.review_status_label = QLabel()
        self.review_status_label.setStyleSheet("QLabel { color: red; }")
        self.review_status_label.hide()
        layout.addWidget(self.review_status_label)

        # Location Name at the top
        self.location_name_label = QLabel()
        self.location_name_label.setAlignment(Qt.AlignCenter)
        self.location_name_label.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(self.location_name_label)

        # Upper Section: Image and Vitals
        upper_section = QFrame()
        upper_section.setFrameStyle(QFrame.Box | QFrame.Raised)
        upper_section.setLineWidth(2)
        upper_layout = QHBoxLayout(upper_section)

        # Image Section
        image_section = self.create_image_section()
        upper_layout.addWidget(image_section)

        # Vitals Section
        vitals_section = self.create_vitals_section()
        upper_layout.addWidget(vitals_section)

        layout.addWidget(upper_section)

        # Lower Section: Additional Information
        lower_section = QScrollArea()
        lower_section.setWidgetResizable(True)
        lower_widget = QWidget()
        self.lower_layout = QVBoxLayout(lower_widget)
        lower_section.setWidget(lower_widget)
        layout.addWidget(lower_section)

        # Button layout at the bottom
        button_layout = QHBoxLayout()
        
        self.edit_location_button = QPushButton("Edit Location")
        self.edit_location_button.clicked.connect(self.edit_location)
        button_layout.addWidget(self.edit_location_button)

        self.mark_reviewed_button = QPushButton("Mark as Reviewed")
        self.mark_reviewed_button.clicked.connect(self.mark_location_reviewed)
        self.mark_reviewed_button.setEnabled(False)
        button_layout.addWidget(self.mark_reviewed_button)

        layout.addLayout(button_layout)  # Make sure this line is present

        middle_panel.setLayout(layout)
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

        self.vitals_labels = {}
        fields = ['Name', 'Aliases', 'Address', 'LocationType', 'YearBuilt', 
                 'Owners', 'Managers', 'Employees']

        for field in fields:
            if field == 'Aliases':
                self.vitals_labels[field] = QTextEdit()
                self.vitals_labels[field].setReadOnly(True)
                self.vitals_labels[field].setMaximumHeight(60)
            else:
                self.vitals_labels[field] = QLabel()
            
            field_label = QLabel(f"{field}:")
            field_label.setFont(QFont("Arial", 10, QFont.Bold))
            layout.addRow(field_label, self.vitals_labels[field])

        return vitals_widget

    def create_right_panel(self):
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        # Associated Articles section
        right_layout.addWidget(QLabel("Associated Articles:"))
        
        self.article_list = QListWidget()
        self.article_list.itemClicked.connect(self.display_article_content)
        right_layout.addWidget(self.article_list)

        # Date Filtering Section
        filter_label = QLabel("Filter Articles by Date:")
        right_layout.addWidget(filter_label)

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
        right_layout.addLayout(start_date_layout)

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
        right_layout.addLayout(end_date_layout)

        # Filter Buttons - each on their own line
        apply_filter_button = QPushButton("Apply Date Filter")
        apply_filter_button.clicked.connect(self.apply_date_filter)
        right_layout.addWidget(apply_filter_button)

        clear_filter_button = QPushButton("Clear Filter")
        clear_filter_button.clicked.connect(self.clear_date_filter)
        right_layout.addWidget(clear_filter_button)

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

    def mark_location_reviewed(self):
        if not self.current_location_id:
            return
            
        reply = QMessageBox.question(
            self,
            "Mark as Reviewed",
            "Are you sure this location's information is complete and correct?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db_manager.update_location_status(self.current_location_id, 'reviewed')
            self.review_status_label.hide()
            self.mark_reviewed_button.setEnabled(False)
            
            # Refresh the location list
            self.load_locations()
            
            # Reselect the current location
            for i in range(self.location_list.count()):
                if self.location_list.item(i).data(Qt.UserRole) == self.current_location_id:
                    self.location_list.setCurrentRow(i)
                    break
            
            QMessageBox.information(self, "Success", "Location marked as reviewed.")

    def load_locations(self):
        self.location_list.clear()
        locations = self.db_manager.get_all_locations()
        for location in locations:
            item = QListWidgetItem(location['DisplayName'])
            item.setData(Qt.UserRole, location['LocationID'])
            
            # Set color based on review status
            if location['ReviewStatus'] == 'needs_review':
                item.setForeground(Qt.red)
                
            self.location_list.addItem(item)

    def display_location_details(self, item):
        location_id = item.data(Qt.UserRole)
        self.current_location_id = location_id
        location_data = self.db_manager.get_location_by_id(location_id)

        if location_data:
            # Update location name at top
            self.location_name_label.setText(location_data['DisplayName'])

            # Update image
            if location_data.get('ImagePath'):
                pixmap = QPixmap(location_data['ImagePath'])
                self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.image_label.setText("No Image")

            # Update review status
            if location_data.get('ReviewStatus') == 'needs_review':
                self.review_status_label.setText("⚠️ Needs Review")
                self.review_status_label.show()
                self.mark_reviewed_button.setEnabled(True)
            else:
                self.review_status_label.hide()
                self.mark_reviewed_button.setEnabled(False)    

            # Update vitals section
            self.vitals_labels['Name'].setText(location_data['LocationName'])
            self.vitals_labels['Aliases'].setPlainText(location_data.get('Aliases', ''))
            self.vitals_labels['Address'].setText(location_data.get('Address', ''))
            self.vitals_labels['LocationType'].setText(location_data.get('LocationType', ''))
            self.vitals_labels['YearBuilt'].setText(location_data.get('YearBuilt', ''))
            self.vitals_labels['Owners'].setText(location_data.get('Owners', ''))
            self.vitals_labels['Managers'].setText(location_data.get('Managers', ''))
            self.vitals_labels['Employees'].setText(location_data.get('Employees', ''))

            # Update lower section
            self.clear_layout(self.lower_layout)

            # Add Summary section
            summary_label = QLabel("<b>Summary:</b>")
            summary_label.setFont(QFont("Arial", 10, QFont.Bold))
            self.lower_layout.addWidget(summary_label)

            if location_data.get('Summary'):
                summary_text = QTextEdit()
                summary_text.setPlainText(location_data['Summary'])
                summary_text.setReadOnly(True)
                summary_text.setMinimumHeight(100)
                self.lower_layout.addWidget(summary_text)
            else:
                empty_summary = QLabel("No summary available")
                self.lower_layout.addWidget(empty_summary)

            # Load associated articles
            self.load_associated_articles()

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
        if not self.current_location_id:
            return

        articles = self.db_manager.get_articles_by_location(self.current_location_id)
        for article in articles:
            item = QListWidgetItem(f"{article[0]} - {article[1]}")
            item.setData(Qt.UserRole, article[2])  # Store EventID
            self.article_list.addItem(item)

    def display_article_content(self, item):
        event_id = item.data(Qt.UserRole)
        self.db_manager.cursor.execute("""
            SELECT e.EventText, e.EventTitle, e.EventDate
            FROM Events e
            WHERE e.EventID = ?
        """, (event_id,))
        content = self.db_manager.cursor.fetchone()
        
        if content:
            event_text, event_title, event_date = content
            self.article_text_view.setText(f"Title: {event_title}\nDate: {event_date}\n\n{event_text}")
            self.last_viewed_articles[self.current_location_id] = item
        else:
            self.article_text_view.setText("No content available for this article.")

    def apply_date_filter(self):
        start_date = self.start_date_input.text()
        end_date = self.end_date_input.text()
        
        if not (start_date and end_date):
            QMessageBox.warning(self, "Invalid Input", "Please enter both start and end dates.")
            return

        self.article_list.clear()
        filtered_articles = self.db_manager.get_articles_by_location_and_date(
            self.current_location_id, start_date, end_date)
        
        for article in filtered_articles:
            item = QListWidgetItem(f"{article[0]} - {article[1]}")
            item.setData(Qt.UserRole, article[2])
            self.article_list.addItem(item)

    def clear_date_filter(self):
        self.start_date_input.clear()
        self.end_date_input.clear()
        self.load_associated_articles()

    def clear_viewer(self):
        """Clears the article text viewer content."""
        self.article_text_view.clear()        

    def add_new_location(self):
        dialog = LocationDialog(self)
        if dialog.exec_():
            location_data = dialog.get_location_data()
            try:
                location_id = self.db_manager.insert_location(
                    display_name=location_data['DisplayName'],
                    location_name=location_data['LocationName'],
                    aliases=location_data['Aliases'],
                    address=location_data['Address'],
                    location_type=location_data['LocationType'],
                    year_built=location_data['YearBuilt'],
                    owners=location_data['Owners'],
                    managers=location_data['Managers'],
                    employees=location_data['Employees'],
                    summary=location_data['Summary'],
                    image_path=location_data.get('ImagePath')
                    # Removed from_article_processor parameter
                )
                
                # Update character associations
                self.update_character_associations(location_id, 
                                                location_data['Owners'], 
                                                location_data['Managers'],
                                                location_data['Employees'])
                
                self.load_locations()
                QMessageBox.information(self, "Success", "Location added successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add location: {str(e)}")

    def edit_location(self):
            if not self.current_location_id:
                QMessageBox.warning(self, "Warning", "Please select a location to edit.")
                return

            location_data = self.db_manager.get_location_by_id(self.current_location_id)
            if location_data:
                dialog = LocationDialog(self, location_data)
                if dialog.exec_():
                    updated_data = dialog.get_location_data()
                    try:
                        self.db_manager.update_location(
                            location_id=self.current_location_id,
                            display_name=updated_data['DisplayName'],
                            location_name=updated_data['LocationName'],
                            aliases=updated_data['Aliases'],
                            address=updated_data['Address'],
                            location_type=updated_data['LocationType'],
                            year_built=updated_data['YearBuilt'],
                            owners=updated_data['Owners'],
                            managers=updated_data['Managers'],
                            employees=updated_data['Employees'],
                            summary=updated_data['Summary'],
                            image_path=updated_data.get('ImagePath')
                        )
                        
                        # Update character associations
                        self.update_character_associations(self.current_location_id, 
                                                        updated_data['Owners'], 
                                                        updated_data['Managers'],
                                                        updated_data['Employees'])
                        
                        self.load_locations()
                        # Refresh the display
                        for i in range(self.location_list.count()):
                            if self.location_list.item(i).data(Qt.UserRole) == self.current_location_id:
                                self.location_list.setCurrentRow(i)
                                break
                                
                        QMessageBox.information(self, "Success", "Location updated successfully!")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to update location: {str(e)}")

    def delete_location(self):
        if not self.current_location_id:
            QMessageBox.warning(self, "Warning", "Please select a location to delete.")
            return

        reply = QMessageBox.question(self, 'Delete Location', 
                                   'Are you sure you want to delete this location?',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Remove character associations first
                self.update_character_associations(self.current_location_id, "", "", "")
                
                # Delete the location
                self.db_manager.delete_location(self.current_location_id)
                self.load_locations()
                self.clear_location_display()
                QMessageBox.information(self, "Success", "Location deleted successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete location: {str(e)}")

    def clear_location_display(self):
        """Clear all location display fields"""
        self.location_name_label.clear()
        self.image_label.clear()
        
        for label in self.vitals_labels.values():
            if isinstance(label, QLabel):
                label.clear()
            elif isinstance(label, QTextEdit):
                label.clear()
        
        self.clear_layout(self.lower_layout)
        self.article_list.clear()
        self.article_text_view.clear()
        self.current_location_id = None

    def change_photo(self):
        if not self.current_location_id:
            QMessageBox.warning(self, "Warning", "Please select a location first.")
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        
        if file_name:
            try:
                # Update the image in the database
                self.db_manager.update_location_image(self.current_location_id, file_name)
                
                # Update the display
                pixmap = QPixmap(file_name)
                if not pixmap.isNull():
                    self.image_label.setPixmap(
                        pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    raise Exception("Failed to load the image")
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update image: {str(e)}")

    def update_character_associations(self, location_id, owners, managers, employees):
        """Update character associations in the database"""
        try:
            # Clear existing associations for this location
            self.db_manager.cursor.execute("DELETE FROM LocationOccupations WHERE LocationID = ?", (location_id,))
            
            # Helper function to add occupations
            def add_occupations(character_names, role_type):
                if character_names:
                    for name in character_names.split(';'):
                        name = name.strip()
                        character_id = self.db_manager.get_character_id_by_name(name)
                        if character_id:
                            self.db_manager.add_location_occupation(
                                location_id=location_id,
                                character_id=character_id,
                                role_type=role_type
                            )
            
            # Add new associations
            add_occupations(owners, 'Owner')
            add_occupations(managers, 'Manager')
            add_occupations(employees, 'Employee')
            
            self.db_manager.conn.commit()
            
        except Exception as e:
            print(f"Error updating character associations: {str(e)}")

    def closeEvent(self, event):
        """Handle cleanup when closing the tab"""
        self.db_manager.close_connection()
        event.accept()

class AddLocationDialog(LocationDialog):
    """Dialog for adding a new location"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Location")

class EditLocationDialog(LocationDialog):
    """Dialog for editing an existing location"""
    def __init__(self, parent=None, location_data=None):
        super().__init__(parent, location_data)
        self.setWindowTitle("Edit Location")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    db_path = "path/to/your/database.db"  # Replace with actual path
    window = LocationsTab(db_path)
    window.show()
    sys.exit(app.exec_())                