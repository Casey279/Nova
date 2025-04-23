# File: start_tab.py

import os
import shutil
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
    QMessageBox, QFileDialog, QDialog, QListWidget, QScrollArea,
    QFrame, QGridLayout, QLineEdit, QSizePolicy, QComboBox, QListWidget
)
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize, pyqtSignal

# Add proper path for database_manager import
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_manager import DatabaseManager

def showInfoMessage(parent, title, message):
    """Show a properly styled information message box."""
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(QMessageBox.Information)
    
    # Explicitly style message box elements
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: white;
        }
        QLabel {
            color: black;
            background-color: transparent;
        }
        QPushButton {
            background-color: #4682B4;
            color: white;
            border: 1px solid #2B547E;
            border-radius: 4px;
            padding: 5px 15px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #5890c7;
        }
    """)
    
    return msg_box.exec_()

class ProjectDialog(QDialog):
    def __init__(self, parent=None, existing_projects=None):
        super().__init__(parent)
        self.existing_projects = existing_projects or []
        self.project_name = None
        self.is_training_project = False
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Create New Project")
        self.setFixedWidth(400)
        layout = QVBoxLayout()
        
        # Project type selection
        type_label = QLabel("Select project type:")
        layout.addWidget(type_label)
        
        self.project_type = QComboBox()
        self.project_type.addItem("Create New Project")
        self.project_type.addItem("Create Training Project")
        self.project_type.currentIndexChanged.connect(self.on_project_type_changed)
        layout.addWidget(self.project_type)
        
        # Instructions
        self.instructions = QLabel("Enter a name for your new project:\n(Letters, numbers, and spaces only)")
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)
        
        # Project name input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Project Name")
        self.name_input.textChanged.connect(self.validate_input)
        layout.addWidget(self.name_input)
        
        # Validation message (hidden by default)
        self.validation_msg = QLabel()
        self.validation_msg.setStyleSheet("color: red;")
        self.validation_msg.hide()
        layout.addWidget(self.validation_msg)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Create")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Add explicit styling for the dialog
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                color: black;
                background-color: transparent;
            }
            QLineEdit {
                color: black;
                background-color: white;
            }
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: 1px solid #2B547E;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5890c7;
            }
            QComboBox {
                color: black;
                background-color: white;
            }
        """)

        self.setLayout(layout)
        
        # Set default values
        self.on_project_type_changed(0)
    
    def on_project_type_changed(self, index):
        """Handle project type selection change"""
        if index == 1:  # Training Project
            self.is_training_project = True
            self.name_input.setText("Training Project")
            self.name_input.setEnabled(False)
            self.instructions.setText("This will create a Training Project with sample data to help you learn the system.")
        else:  # Regular project
            self.is_training_project = False
            self.name_input.clear()
            self.name_input.setEnabled(True)
            self.instructions.setText("Enter a name for your new project:\n(Letters, numbers, and spaces only)")
        
        self.validate_input()
    
    def validate_input(self):
        name = self.name_input.text().strip()
        
        # Skip validation for Training Project
        if self.is_training_project and name == "Training Project":
            self.validation_msg.hide()
            self.ok_button.setEnabled(True)
            self.project_name = name
            return
        
        if not name:
            self.validation_msg.setText("Project name cannot be empty")
            self.validation_msg.show()
            self.ok_button.setEnabled(False)
            return
            
        if name in self.existing_projects:
            self.validation_msg.setText("Project name already exists")
            self.validation_msg.show()
            self.ok_button.setEnabled(False)
            return
            
        if not name.replace(" ", "").isalnum():
            self.validation_msg.setText("Only letters, numbers, and spaces allowed")
            self.validation_msg.show()
            self.ok_button.setEnabled(False)
            return
            
        self.validation_msg.hide()
        self.ok_button.setEnabled(True)
        self.project_name = name
    
    def get_project_name(self):
        return self.project_name
    
    def is_training(self):
        return self.is_training_project

class ProjectListDialog(QDialog):
    def __init__(self, projects, parent=None):
        super().__init__(parent)
        self.projects = projects
        self.selected_project = None
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("All Projects")
        self.setFixedSize(400, 500)
        
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel("Select a project to open:")
        layout.addWidget(instructions)
        
        # Project list
        self.list_widget = QListWidget()
        for project in self.projects:
            self.list_widget.addItem(project)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        open_button = QPushButton("Open")
        open_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(open_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Add explicit styling for the dialog
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                color: black;
                background-color: transparent;
            }
            QLineEdit {
                color: black;
                background-color: white;
            }
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: 1px solid #2B547E;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5890c7;
            }
            QComboBox {
                color: black;
                background-color: white;
            }
        """)

        self.setLayout(layout)
    
    def get_selected_project(self):
        return self.list_widget.currentItem().text() if self.list_widget.currentItem() else None

class ProjectButton(QPushButton):
    def __init__(self, project_name, is_placeholder=False, last_modified=None):
        super().__init__()
        self.project_name = project_name
        self.is_placeholder = is_placeholder
        self.last_modified = last_modified
        self.initUI()
    
    def initUI(self):
        # Use a default folder icon
        if not self.is_placeholder:
            self.setIcon(self.style().standardIcon(self.style().SP_DirIcon))
            self.setIconSize(QSize(48, 48))
            self.setText(self.project_name)
            self.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #4682B4;
                    border-radius: 10px;
                    padding: 10px;
                    color: #2B547E;
                }
                QPushButton:hover {
                    background-color: #F0F8FF;
                    border: 2px solid #4682B4;
                }
            """)
        else:
            # Placeholder style - just an outline
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: 2px dashed #B0C4DE;
                    border-radius: 10px;
                    padding: 10px;
                    color: #B0C4DE;
                }
            """)
        
        # Set fixed size
        self.setFixedSize(120, 100)
        
        # Make it flat
        self.setFlat(True)

class CreateNewProjectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        # Set icon and text
        self.setIcon(self.style().standardIcon(self.style().SP_FileDialogNewFolder))
        self.setIconSize(QSize(48, 48))
        self.setText("Create New\nProject")
        
        # Style the button
        self.setStyleSheet("""
            QPushButton {
                background-color: #90EE90;
                border: 2px solid #2E8B57;
                border-radius: 10px;
                padding: 10px;
                color: #2B547E;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #98FB98;
                border: 2px solid #2E8B57;
            }
        """)
        
        # Set fixed size
        self.setFixedSize(120, 100)
        
        # Make it flat
        self.setFlat(True)

class StartTab(QWidget):
    project_opened_signal = pyqtSignal(str)  # Signal to notify when a project is opened

    def __init__(self, db_path, project_base_folder):
        super().__init__()
        self.db_path = db_path
        self.project_base_folder = project_base_folder
        self.current_project = None
        self.db_manager = None
        self.training_assets_folder = os.path.join("C:", "AI", "Nova", "training_assets")
        
        # Create projects folder if it doesn't exist
        if not os.path.exists(self.project_base_folder):
            os.makedirs(self.project_base_folder)
        
        self.projects = self.load_projects()
        
        # Create Training Project if it doesn't exist and this is first run
        if "Training Project" not in self.projects and len(self.projects) == 0:
            self.create_training_project()
        
        self.initUI()
    
    def initUI(self):
        # Create a new layout for the entire tab
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        
        # Create a background widget that will fill the entire tab
        background_widget = QWidget()
        background_widget.setObjectName("backgroundWidget")
        background_widget.setStyleSheet("#backgroundWidget { background-color: #1E5799; }")
        
        # Set up the main layout inside the background widget
        main_layout = QVBoxLayout(background_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Top section with Logo
        logo_section = QVBoxLayout()
        logo_section.setAlignment(Qt.AlignCenter)
        
        # Logo image - using absolute path and print statements for debugging
        logo_path = "C:/AI/Nova/assets/UIimages/NOVA_LOGO.png"  # Use forward slashes
        print(f"Looking for logo at: {logo_path}")
        print(f"File exists: {os.path.exists(logo_path)}")
        
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            print(f"Pixmap is null: {pixmap.isNull()}")
            if not pixmap.isNull():
                logo_label.setPixmap(pixmap.scaled(300, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                logo_label.setAlignment(Qt.AlignCenter)
                logo_section.addWidget(logo_label)
            else:
                # Fallback if pixmap is null
                self._create_text_logo(logo_section)
        else:
            # Fallback text logo if image not found
            self._create_text_logo(logo_section)
        
        # Hidden/placeholder subtitle field
        self.subtitle_label = QLabel("")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: white; font-size: 16px; background: transparent;")
        logo_section.addWidget(self.subtitle_label)
        
        main_layout.addLayout(logo_section)
        
        # Add some spacing between logo and project buttons
        main_layout.addSpacing(40)
        
        # Project buttons section
        projects_frame = QFrame()
        projects_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 20px;
            }
        """)

        projects_layout = QVBoxLayout(projects_frame)

        # Add header with manage projects button
        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignLeft)

        projects_label = QLabel("Projects")
        projects_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(projects_label)

        header_layout.addStretch()  # Push the manage button to the right

        manage_projects_btn = QPushButton("Manage Projects")
        manage_projects_btn.setStyleSheet("""
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: 1px solid #2B547E;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #5890c7;
            }
        """)
        manage_projects_btn.clicked.connect(self.show_manage_projects)
        header_layout.addWidget(manage_projects_btn)

        projects_layout.addLayout(header_layout)

        # Projects grid (centered)
        grid_container = QHBoxLayout()
        grid_container.setAlignment(Qt.AlignCenter)

        self.project_grid = QGridLayout()
        self.project_grid.setSpacing(20)
        self.project_grid.setAlignment(Qt.AlignCenter)

        # Create New Project button
        new_project_btn = CreateNewProjectButton()
        new_project_btn.clicked.connect(self.on_create_project)
        self.project_grid.addWidget(new_project_btn, 0, 0)

        # Add existing projects and placeholder buttons

        grid_container.addLayout(self.project_grid)
        projects_layout.addLayout(grid_container)

        # Add "See All" button if needed (will be shown/hidden in update_project_grid)
        self.see_all_layout = QHBoxLayout()
        self.see_all_layout.setAlignment(Qt.AlignRight)

        self.see_all_btn = QPushButton("See All Projects")
        self.see_all_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #add8e6;
            }
        """)
        self.see_all_btn.clicked.connect(self.show_all_projects)
        self.see_all_layout.addWidget(self.see_all_btn)
        projects_layout.addLayout(self.see_all_layout)

        # Hide see all button by default (will be shown in update_project_grid if needed)
        self.see_all_btn.hide()

        # Now call update_project_grid AFTER see_all_btn is created
        self.update_project_grid()

        main_layout.addWidget(projects_frame)
        main_layout.addStretch(1)  # Push everything up
        
        # Add the background widget to the tab layout
        tab_layout.addWidget(background_widget)
        
        # Set global stylesheet for the tab
        self.setStyleSheet("""
            QLabel { background: transparent; color: white; }
            QPushButton { background-color: transparent; }
            QComboBox { background-color: white; }
        """)

    def _create_text_logo(self, parent_layout):
        """Create a text logo as fallback"""
        logo_text = QLabel("NOVA")
        logo_text.setFont(QFont("Arial", 48, QFont.Bold))
        logo_text.setStyleSheet("color: white; background: transparent;")
        logo_text.setAlignment(Qt.AlignCenter)
        parent_layout.addWidget(logo_text)
    
    def load_projects(self):
        """Load existing projects and sort by last modified time"""
        projects = []
        if os.path.exists(self.project_base_folder):
            for folder in os.listdir(self.project_base_folder):
                folder_path = os.path.join(self.project_base_folder, folder)
                if os.path.isdir(folder_path):
                    db_path = os.path.join(folder_path, f"{folder}.db")
                    if os.path.exists(db_path):
                        projects.append((folder, os.path.getmtime(db_path)))
        
        # Sort by last modified time, newest first
        projects.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in projects]
    
    def update_project_grid(self):
        """Update the project grid with current projects and placeholders"""
        # Clear existing buttons first
        for i in reversed(range(self.project_grid.count())): 
            if i > 0:  # Skip the Create New Project button
                widget = self.project_grid.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
        
        # Add existing projects (up to 4)
        col = 1  # Start after the Create New Project button
        for project in self.projects[:4]:
            btn = ProjectButton(project)
            btn.clicked.connect(lambda checked, p=project: self.open_project(p))
            
            # Highlight the current project with green border
            if project == self.current_project:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: white;
                        border: 3px solid #00FF00;
                        border-radius: 10px;
                        padding: 10px;
                        color: #2B547E;
                    }
                    QPushButton:hover {
                        background-color: #F0F8FF;
                        border: 3px solid #00FF00;
                    }
                """)
            
            self.project_grid.addWidget(btn, 0, col)
            col += 1
        
        # Add placeholders for the remaining slots in first row
        while col < 5:  # Total of 5 positions (Create + 4 projects)
            btn = ProjectButton("", is_placeholder=True)
            btn.setEnabled(False)
            self.project_grid.addWidget(btn, 0, col)
            col += 1
        
        # Show or hide See All button based on projects count
        if len(self.projects) > 4:
            self.see_all_btn.show()
        else:
            self.see_all_btn.hide()
    
    def on_create_project(self):
        """Show project creation dialog"""
        dialog = ProjectDialog(self, self.projects)
        if dialog.exec_():
            project_name = dialog.get_project_name()
            if project_name:
                if dialog.is_training():
                    self.create_training_project()
                else:
                    self.create_new_project(project_name)
    
    def create_training_project(self):
        """Create the Training Project with sample data"""
        project_name = "Training Project"
        project_folder = os.path.join(self.project_base_folder, project_name)
        
        if not os.path.exists(project_folder):
            try:
                # Create main project folder
                os.makedirs(project_folder)
                
                # Create Assets folder
                assets_folder = os.path.join(project_folder, "Assets")
                os.makedirs(assets_folder)
                
                # Create dbase folder
                dbase_folder = os.path.join(project_folder, "dbase")
                os.makedirs(dbase_folder)
                
                # Create subfolders in Assets
                os.makedirs(os.path.join(assets_folder, "Intake-For_Preprocessing"))
                os.makedirs(os.path.join(assets_folder, "preprocessed"))
                os.makedirs(os.path.join(assets_folder, "ProcessedEvents"))
                
                # Create Profile_Photos and its subfolders
                profile_photos_folder = os.path.join(assets_folder, "Profile_Photos")
                os.makedirs(profile_photos_folder)
                os.makedirs(os.path.join(profile_photos_folder, "EntitiesPhotos"))
                os.makedirs(os.path.join(profile_photos_folder, "LocationsPhotos"))
                os.makedirs(os.path.join(profile_photos_folder, "CharacterPhotos"))
                os.makedirs(os.path.join(profile_photos_folder, "SourcesPhotos"))
                
                # Copy training assets if they exist
                self.copy_training_assets(project_folder)
                
                # Create database file
                db_path = os.path.join(project_folder, f"{project_name}.db")
                self.db_manager = DatabaseManager(db_path)
                
                # Update projects list and refresh display
                if project_name not in self.projects:
                    self.projects.insert(0, project_name)
                    self.update_project_grid()
                
                print(f"Training Project created successfully at {project_folder}")
                QMessageBox.information(self, "Success", "Training Project created successfully!")
            except Exception as e:
                print(f"Error creating Training Project: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to create Training Project: {str(e)}")
    
    def copy_training_assets(self, project_folder):
        """Copy training assets from the repository to the project folder"""
        # Check if training assets repository exists
        if not os.path.exists(self.training_assets_folder):
            print("Training assets folder not found")
            return
        
        try:
            # Copy articles to ProcessedEvents
            articles_src = os.path.join(self.training_assets_folder, "Articles")
            articles_dst = os.path.join(project_folder, "Assets", "ProcessedEvents")
            if os.path.exists(articles_src):
                for file in os.listdir(articles_src):
                    src_file = os.path.join(articles_src, file)
                    dst_file = os.path.join(articles_dst, file)
                    if os.path.isfile(src_file):
                        shutil.copy2(src_file, dst_file)
            
            # Copy profile photos
            profiles_src = os.path.join(self.training_assets_folder, "Profiles")
            if os.path.exists(profiles_src):
                # Copy character photos
                self.copy_directory_if_exists(
                    os.path.join(profiles_src, "Characters"),
                    os.path.join(project_folder, "Assets", "Profile_Photos", "CharacterPhotos")
                )
                # Copy location photos
                self.copy_directory_if_exists(
                    os.path.join(profiles_src, "Locations"),
                    os.path.join(project_folder, "Assets", "Profile_Photos", "LocationsPhotos")
                )
                # Copy entity photos
                self.copy_directory_if_exists(
                    os.path.join(profiles_src, "Entities"),
                    os.path.join(project_folder, "Assets", "Profile_Photos", "EntitiesPhotos")
                )
                # Copy source photos
                self.copy_directory_if_exists(
                    os.path.join(profiles_src, "Sources"),
                    os.path.join(project_folder, "Assets", "Profile_Photos", "SourcesPhotos")
                )
            
            print("Training assets copied successfully")
        except Exception as e:
            print(f"Error copying training assets: {str(e)}")
    
    def copy_directory_if_exists(self, src, dst):
        """Copy all files from src to dst if src exists"""
        if os.path.exists(src):
            for file in os.listdir(src):
                src_file = os.path.join(src, file)
                dst_file = os.path.join(dst, file)
                if os.path.isfile(src_file):
                    shutil.copy2(src_file, dst_file)
    
    def create_new_project(self, project_name):
        """Create a new project with database"""
        try:
            # Create project folder
            project_folder = os.path.join(self.project_base_folder, project_name)
            os.makedirs(project_folder)
            
            # Create Assets folder
            assets_folder = os.path.join(project_folder, "Assets")
            os.makedirs(assets_folder)
            
            # Create dbase folder
            dbase_folder = os.path.join(project_folder, "dbase")
            os.makedirs(dbase_folder)
            
            # Create subfolders in Assets
            os.makedirs(os.path.join(assets_folder, "Intake-For_Preprocessing"))
            os.makedirs(os.path.join(assets_folder, "preprocessed"))
            os.makedirs(os.path.join(assets_folder, "ProcessedEvents"))
            
            # Create Profile_Photos and its subfolders
            profile_photos_folder = os.path.join(assets_folder, "Profile_Photos")
            os.makedirs(profile_photos_folder)
            os.makedirs(os.path.join(profile_photos_folder, "EntitiesPhotos"))
            os.makedirs(os.path.join(profile_photos_folder, "LocationsPhotos"))
            os.makedirs(os.path.join(profile_photos_folder, "CharacterPhotos"))
            os.makedirs(os.path.join(profile_photos_folder, "SourcesPhotos"))
            
            # Create database file
            db_path = os.path.join(project_folder, f"{project_name}.db")
            self.db_manager = DatabaseManager(db_path)
            
            # Set as current project BEFORE updating the grid
            self.current_project = project_name
            self.db_path = db_path
            
            # Update projects list and refresh display
            self.projects.insert(0, project_name)
            self.update_project_grid()
            
            # Update UI indicators to show this is now the open project
            self.subtitle_label.setText(f"Current Project: {project_name.upper()} (Ready to use)")
            
            # Update main window title
            main_window = self.window()
            if hasattr(main_window, 'update_window_title'):
                main_window.update_window_title(project_name)
            self.project_opened_signal.emit(project_folder)    
            
            # Show success message
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Success")
            msg_box.setText(f"Project '{project_name}' created successfully and is now open!")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStyleSheet("""
                QMessageBox { background-color: white; }
                QLabel { color: black; background-color: transparent; }
                QPushButton {
                    background-color: #4682B4;
                    color: white;
                    border: 1px solid #2B547E;
                    border-radius: 4px;
                    padding: 5px 15px;
                    min-width: 80px;
                }
            """)
            msg_box.exec_()
            
        except Exception as e:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Failed to create project: {str(e)}")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setStyleSheet("""
                QMessageBox { background-color: white; }
                QLabel { color: black; background-color: transparent; }
                QPushButton {
                    background-color: #4682B4;
                    color: white;
                    border: 1px solid #2B547E;
                    border-radius: 4px;
                    padding: 5px 15px;
                    min-width: 80px;
                }
            """)
            msg_box.exec_()
    
    def open_project(self, project_name):
        """Open an existing project"""
        project_db = os.path.join(self.project_base_folder, project_name, f"{project_name}.db")
        
        if os.path.exists(project_db):
            try:
                # Update database connection
                self.db_path = project_db
                self.db_manager = DatabaseManager(project_db)
                self.current_project = project_name
                
                # Update the subtitle to show current project
                self.subtitle_label.setText(f"Current Project: {project_name.upper()}")
                
                # Move project to front of list and refresh display
                self.projects.remove(project_name)
                self.projects.insert(0, project_name)
                self.update_project_grid()
                
                # Attempt to update the main window title if possible
                try:
                    main_window = self.window()
                    if hasattr(main_window, 'update_window_title'):
                        main_window.update_window_title(project_name)
                except Exception:
                    # Silently ignore if updating the window title fails
                    pass
                    
                # Update subtitle with ready status
                self.subtitle_label.setText(f"Current Project: {project_name.upper()} (Ready to use)")
                main_window = self.window()
                if hasattr(main_window, 'update_window_title'):
                    main_window.update_window_title(project_name)
                
                # Emit signal for project opening
                project_folder = os.path.join(self.project_base_folder, project_name)
                self.project_opened_signal.emit(project_folder)
                
                # Show success message
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Project Opened")
                msg_box.setText(f"{project_name} is now Open and Ready To Be Worked With!")
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setStyleSheet("""
                    QMessageBox { background-color: white; }
                    QLabel { color: black; background-color: transparent; }
                    QPushButton {
                        background-color: #4682B4;
                        color: white;
                        border: 1px solid #2B547E;
                        border-radius: 4px;
                        padding: 5px 15px;
                        min-width: 80px;
                    }
                """)
                msg_box.exec_()
                
            except Exception as e:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Error")
                msg_box.setText(f"Failed to open project: {str(e)}")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setStyleSheet("""
                    QMessageBox { background-color: white; }
                    QLabel { color: black; background-color: transparent; }
                    QPushButton {
                        background-color: #4682B4;
                        color: white;
                        border: 1px solid #2B547E;
                        border-radius: 4px;
                        padding: 5px 15px;
                        min-width: 80px;
                    }
                """)
                msg_box.exec_()
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Error")
            msg_box.setText("Project database not found!")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("""
                QMessageBox { background-color: white; }
                QLabel { color: black; background-color: transparent; }
                QPushButton {
                    background-color: #4682B4;
                    color: white;
                    border: 1px solid #2B547E;
                    border-radius: 4px;
                    padding: 5px 15px;
                    min-width: 80px;
                }
            """)
            msg_box.exec_()

    def show_manage_projects(self):
        """Show the project management dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Projects")
        dialog.setMinimumSize(500, 400)
        
        # Set style sheet for the dialog
        dialog.setStyleSheet("""
            QDialog { background-color: white; }
            QLabel { color: black; }
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: 1px solid #2B547E;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #5890c7;
            }
            QPushButton#deleteBtn {
                background-color: #d9534f;
                border-color: #d43f3a;
            }
            QPushButton#deleteBtn:hover {
                background-color: #c9302c;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        # Add header
        label = QLabel("Select Projects to Manage")
        label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(label)
        
        # Add project list
        project_list = QListWidget()
        project_list.setSelectionMode(QListWidget.SingleSelection)
        for project in self.projects:
            project_list.addItem(project)
        layout.addWidget(project_list)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        delete_btn = QPushButton("Delete Selected Project")
        delete_btn.setObjectName("deleteBtn")
        delete_btn.clicked.connect(lambda: self.delete_selected_project(project_list, dialog))
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec_()

    def delete_selected_project(self, project_list, parent_dialog):
        """Delete the selected project from the list"""
        if not project_list.currentItem():
            # Show error if no project selected
            msg_box = QMessageBox(parent_dialog)
            msg_box.setWindowTitle("Error")
            msg_box.setText("Please select a project to delete.")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("""
                QMessageBox { background-color: white; }
                QLabel { color: black; background-color: transparent; }
                QPushButton {
                    background-color: #4682B4;
                    color: white;
                    border: 1px solid #2B547E;
                    border-radius: 4px;
                    padding: 5px 15px;
                    min-width: 80px;
                }
            """)
            msg_box.exec_()
            return
        
        project_name = project_list.currentItem().text()
        
        # Confirm deletion
        msg_box = QMessageBox(parent_dialog)
        msg_box.setWindowTitle("Confirm Deletion")
        msg_box.setText(f"Are you sure you want to delete '{project_name}'?\n\nThis will permanently remove all project data.")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        msg_box.setStyleSheet("""
            QMessageBox { background-color: white; }
            QLabel { color: black; background-color: transparent; }
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: 1px solid #2B547E;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
            }
        """)
        
        if msg_box.exec_() == QMessageBox.Yes:
            try:
                # Delete the project
                project_folder = os.path.join(self.project_base_folder, project_name)
                
                # Close database connection if it's the current project
                if self.current_project == project_name:
                    if self.db_manager:
                        self.db_manager.close_connection()
                    self.current_project = None
                    self.subtitle_label.setText("")
                    
                    # Update main window title
                    main_window = self.window()
                    if hasattr(main_window, 'update_window_title'):
                        main_window.update_window_title()
                
                # Delete the project folder
                shutil.rmtree(project_folder)
                
                # Update projects list
                if project_name in self.projects:
                    self.projects.remove(project_name)
                
                # Update list widget
                for i in range(project_list.count()):
                    if project_list.item(i).text() == project_name:
                        project_list.takeItem(i)
                        break
                
                # Refresh the grid
                self.update_project_grid()
                
                # Show success message
                msg_box = QMessageBox(parent_dialog)
                msg_box.setWindowTitle("Project Deleted")
                msg_box.setText(f"Project '{project_name}' has been deleted.")
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setStyleSheet("""
                    QMessageBox { background-color: white; }
                    QLabel { color: black; background-color: transparent; }
                    QPushButton {
                        background-color: #4682B4;
                        color: white;
                        border: 1px solid #2B547E;
                        border-radius: 4px;
                        padding: 5px 15px;
                        min-width: 80px;
                    }
                """)
                msg_box.exec_()
                
            except Exception as e:
                # Show error message
                msg_box = QMessageBox(parent_dialog)
                msg_box.setWindowTitle("Error")
                msg_box.setText(f"Failed to delete project: {str(e)}")
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setStyleSheet("""
                    QMessageBox { background-color: white; }
                    QLabel { color: black; background-color: transparent; }
                    QPushButton {
                        background-color: #4682B4;
                        color: white;
                        border: 1px solid #2B547E;
                        border-radius: 4px;
                        padding: 5px 15px;
                        min-width: 80px;
                    }
                """)
                msg_box.exec_()

    def show_all_projects(self):
        """Show dialog with all projects in a scrollable grid"""
        dialog = QDialog(self)
        dialog.setWindowTitle("All Projects")
        dialog.setMinimumSize(800, 600)
        
        # Set style for dialog
        dialog.setStyleSheet("""
            QDialog { background-color: white; }
            QLabel { color: black; }
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: 1px solid #2B547E;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #5890c7;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        # Add header
        label = QLabel("All Projects")
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(label)
        
        # Create scroll area for projects
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Create widget to hold the grid
        scroll_content = QWidget()
        grid_layout = QGridLayout(scroll_content)
        grid_layout.setSpacing(20)
        
        # Populate grid with project buttons (5 per row)
        col = 0
        row = 0
        for project in self.projects:
            btn = ProjectButton(project)
            
            # Highlight the current project with green border
            if project == self.current_project:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: white;
                        border: 3px solid #00FF00;
                        border-radius: 10px;
                        padding: 10px;
                        color: #2B547E;
                    }
                    QPushButton:hover {
                        background-color: #F0F8FF;
                        border: 3px solid #00FF00;
                    }
                """)
            
            btn.clicked.connect(lambda checked, p=project: self.open_project_from_dialog(p, dialog))
            grid_layout.addWidget(btn, row, col)
            
            col += 1
            if col >= 5:  # Move to next row after 5 columns
                col = 0
                row += 1
        
        # Add new project button at the end
        new_project_btn = CreateNewProjectButton()
        new_project_btn.clicked.connect(lambda: self.on_create_project_from_dialog(dialog))
        grid_layout.addWidget(new_project_btn, row, col)
        
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        
        dialog.exec_()

    def open_project_from_dialog(self, project_name, dialog):
        """Open a project and close the dialog"""
        dialog.accept()
        self.open_project(project_name)
    
    # Note: No need to reorder projects here since open_project already does that

    def on_create_project_from_dialog(self, dialog):
        """Create a new project from the all projects dialog"""
        dialog.accept()
        self.on_create_project()      

    def placeholder_method(self):
        pass          

            