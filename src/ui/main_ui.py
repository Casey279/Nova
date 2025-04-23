# File: main_ui.py

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTabWidget, QLabel, QSplitter, QPushButton, QTextEdit, 
                             QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from database_manager import DatabaseManager
from article_processor import ArticleProcessor  # Import ArticleProcessor class
from characters_tab import CharactersTab  # Import CharactersTab class
from events_tab import EventsTab
from locations_tab import LocationsTab  # Import the LocationsTab class
from entities_tab import EntitiesTab
from sources_tab import SourcesTab  # Import SourcesTab class
from brainstorming_tab import BrainstormingTab
from start_tab import StartTab
from ui.research_import_tab import ResearchImportTab




class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = "C:\\AI\\Nova\\src\\nova_database.db"
        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.add_status_column_to_events()
        self.db_manager.update_characters_table_structure()
        self.initUI()
        
        # Connect StartTab signals
        QTimer.singleShot(0, self.connect_start_tab_signals)

    def connect_start_tab_signals(self):
        """Connect signals from the StartTab after UI initialization"""
        if hasattr(self, 'start_tab'):
            # Assuming you have the start_tab property
            self.start_tab.project_opened_signal.connect(self.update_project_tabs)

    def initUI(self):
        # Set the size to 85-90% of the screen dimensions and center it
        screen = QApplication.primaryScreen().geometry()
        self.resize(int(screen.width() * 0.85), int(screen.height() * 0.85))
        self.center()

        layout = QVBoxLayout(self)

        # Top-level tabs
        self.tab_widget = QTabWidget()

        # Start Tab (no subtabs)
        self.start_tab = StartTab(self.db_path, "C:/AI/Nova/Projects")
        self.tab_widget.addTab(self.start_tab, "Start")

        # Research-Import Tab
        self.research_import_tab = ResearchImportTab(self.db_path)
        self.tab_widget.addTab(self.research_import_tab, "Research Import")


        # Preprocessing Tabs
        self.preprocessing_tabs = QWidget()
        self.tab_widget.addTab(self.preprocessing_tabs, "Preprocessing")
        self.create_preprocessing_tabs()

        # Main Tabs
        self.main_tabs = QWidget()
        self.tab_widget.addTab(self.main_tabs, "Main Tabs")
        self.create_main_tabs()

        # Table Data Tabs
        self.table_data_tabs = QWidget()
        self.tab_widget.addTab(self.table_data_tabs, "Table Data")
        self.create_table_data_tabs()

        # AI Assistant Tabs
        self.ai_assistant_tabs = QWidget()
        self.tab_widget.addTab(self.ai_assistant_tabs, "AI Assistant")
        self.create_ai_assistant_tabs()

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

        self.setWindowTitle("Historical Database UI")
        self.show()

        self.start_tab.project_opened_signal.connect(self.on_project_opened)

        # Add style for dialog buttons and text
        self.setStyleSheet("""
            QMessageBox {
                color: black;  /* Text color for message box */
            }
            QMessageBox QLabel {
                color: black;  /* Ensure labels inside message box are black */
                background: transparent;
            }
            QMessageBox QPushButton {
                background-color: #4682B4;
                color: white;
                border: 1px solid #2B547E;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #5890c7;
            }
        """)

    def center(self):
        # Center the window on the screen using QScreen
        frame_geometry = self.frameGeometry()
        screen_center = QApplication.primaryScreen().availableGeometry().center()
        frame_geometry.moveCenter(screen_center)
        self.move(frame_geometry.topLeft())

    def create_start_tab(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Welcome to the Historical Database UI"))
        self.start_tab.setLayout(layout)

    def update_project_tabs(self, project_folder):
        """Update all tabs with the current project folder"""
        if hasattr(self, 'research_import_tab'):
            self.research_import_tab.set_project_info(project_folder)
        # Add other tabs that need project info here        

    def create_preprocessing_tabs(self):
        layout = QVBoxLayout()
        preprocessing_sub_tabs = QTabWidget()

        # Add tabs for preprocessing
        self.article_processor_tab = ArticleProcessor(self.db_path)
        preprocessing_sub_tabs.addTab(self.article_processor_tab, "Article Processor")

        sources_tab = SourcesTab(self.db_path)
        preprocessing_sub_tabs.addTab(sources_tab, "Sources")

        layout.addWidget(preprocessing_sub_tabs)
        self.preprocessing_tabs.setLayout(layout)

    def create_main_tabs(self):
        layout = QVBoxLayout()
        main_sub_tabs = QTabWidget()
        
        # Add tabs for main features
        self.events_tab = EventsTab(self.db_path)
        self.characters_tab = CharactersTab(self.db_path)
        self.locations_tab = LocationsTab(self.db_path)
        self.entities_tab = EntitiesTab(self.db_path)
        
        main_sub_tabs.addTab(self.events_tab, "Events")
        main_sub_tabs.addTab(self.characters_tab, "Characters")
        main_sub_tabs.addTab(self.locations_tab, "Locations")
        main_sub_tabs.addTab(self.entities_tab, "Entities")
        
        # Connect tab switch signal
        main_sub_tabs.currentChanged.connect(self.on_tab_changed)
        
        layout.addWidget(main_sub_tabs)
        self.main_tabs.setLayout(layout)

    def on_tab_changed(self, index):
        """Refresh data when switching tabs, but check for unsaved changes first"""
        tab_widget = self.sender()
        current_tab = tab_widget.widget(index)
        
        # Check for unsaved changes in Article Processor
        if hasattr(self, 'article_processor_tab') and self.article_processor_tab.changes_made:
            msg = QMessageBox.warning(
                self,
                "Unsaved Changes",
                "There are unsaved changes in Article Processor. Would you like to keep editing?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if msg == QMessageBox.Yes:
                # Switch back to the Article Processor tab
                tab_widget.setCurrentIndex(tab_widget.indexOf(self.preprocessing_tabs))
                return
        
        # Check for unsaved changes in current tab
        if hasattr(current_tab, 'has_unsaved_changes') and current_tab.has_unsaved_changes():
            msg = QMessageBox.warning(
                self,
                "Unsaved Changes",
                "There are unsaved changes in the current tab. Would you like to keep editing?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if msg == QMessageBox.Yes:
                return
        
        # Proceed with refresh if no unsaved changes or user chooses to proceed
        if hasattr(current_tab, 'load_characters'):
            current_tab.load_characters()
        if hasattr(current_tab, 'load_locations'):
            current_tab.load_locations()
        if hasattr(current_tab, 'load_entities'):
            current_tab.load_entities()

    def on_project_opened(self, project_folder):
        """Handle project opened signal"""
        if hasattr(self, 'article_processor_tab'):
            self.article_processor_tab.set_project_folder(project_folder)

    def create_table_data_tabs(self):
        layout = QVBoxLayout()
        table_data_sub_tabs = QTabWidget()

        # Add tabs for table views
        table_data_sub_tabs.addTab(QWidget(), "Events Table")
        table_data_sub_tabs.addTab(QWidget(), "Characters Table")
        table_data_sub_tabs.addTab(QWidget(), "Locations Table")
        table_data_sub_tabs.addTab(QWidget(), "Entities Table")
        table_data_sub_tabs.addTab(QWidget(), "Sources Table")

        layout.addWidget(table_data_sub_tabs)
        self.table_data_tabs.setLayout(layout)

    def create_ai_assistant_tabs(self):
        layout = QVBoxLayout()
        ai_sub_tabs = QTabWidget()

        # Add AI-related tabs
        brainstorming_tab = BrainstormingTab(self.db_path)
        ai_sub_tabs.addTab(brainstorming_tab, "Brainstorming")

        ai_sub_tabs.addTab(QWidget(), "General Query")
        ai_sub_tabs.addTab(QWidget(), "Plot Development")

        layout.addWidget(ai_sub_tabs)
        self.ai_assistant_tabs.setLayout(layout)

    def closeEvent(self, event):
        # If changes have been made, prompt the user before closing
        if hasattr(self, 'article_processor_tab') and self.article_processor_tab.changes_made:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "You have unsaved changes. Are you sure you want to quit?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                self.article_processor_tab.save_data()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def create_three_panel_layout(self):
        # Create a three-panel layout with vertical splitters
        splitter = QSplitter(Qt.Horizontal)

        # Create labels to represent the content in each panel (replace with actual content later)
        left_panel = QLabel("Left Panel")
        center_panel = QLabel("Center Panel")
        right_panel = QLabel("Right Panel")

        # Add panels to the splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)

        # Set initial positions of the dividers (33%, 67%) and cast to integers
        splitter.setSizes([int(self.width() * 0.33), int(self.width() * 0.33), int(self.width() * 0.33)])

        # Set movement constraints for the dividers
        splitter.setStretchFactor(0, 1)  # Allow movement of the first divider
        splitter.setStretchFactor(1, 1)  # Allow movement of the second divider

        return splitter

    def create_table_data_tabs(self):
        layout = QVBoxLayout()

        # Create a QTabWidget for the second row of tabs under "Table Data"
        table_sub_tabs = QTabWidget()

        # Create empty placeholders for now
        table_sub_tabs.addTab(QWidget(), "Events Table")
        table_sub_tabs.addTab(QWidget(), "Characters Table")
        table_sub_tabs.addTab(QWidget(), "Locations Table")
        table_sub_tabs.addTab(QWidget(), "Entities Table")

        layout.addWidget(table_sub_tabs)
        self.table_data_tabs.setLayout(layout)

    def create_ai_assistant_tabs(self):
        layout = QVBoxLayout()
        ai_sub_tabs = QTabWidget()
        
        # Existing tabs
        ai_sub_tabs.addTab(QWidget(), "General Query")
        ai_sub_tabs.addTab(QWidget(), "Brainstorming")
        ai_sub_tabs.addTab(QWidget(), "Plot Development")
        
        
        layout.addWidget(ai_sub_tabs)
        self.ai_assistant_tabs.setLayout(layout)

    def closeEvent(self, event):
        # If changes have been made, prompt the user before closing
        if self.article_processor and self.article_processor.changes_made:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "You have unsaved changes. Are you sure you want to quit?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                self.article_processor.save_text_to_file()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def create_ai_assistant_tabs(self):
        layout = QVBoxLayout()
        ai_sub_tabs = QTabWidget()
        
        # Add the Brainstorming tab
        brainstorming_tab = BrainstormingTab(self.db_path)
        ai_sub_tabs.addTab(brainstorming_tab, "Brainstorming")
        
        # Other tabs as placeholders for now
        ai_sub_tabs.addTab(QWidget(), "General Query")
        ai_sub_tabs.addTab(QWidget(), "Plot Development")
        
        layout.addWidget(ai_sub_tabs)
        self.ai_assistant_tabs.setLayout(layout)

    def update_window_title(self, project_name=None):
        """Update window title to reflect current project"""
        base_title = "Historical Database UI"
        if project_name:
            self.setWindowTitle(f"{base_title} - {project_name.upper()}")
        else:
            self.setWindowTitle(base_title)


def main():
    try:
        print("Starting application...")
        app = QApplication(sys.argv)
        print("Created QApplication...")
        window = MainWindow()
        print("Created MainWindow...")
        window.show()  # Add this line
        print("Called show()...")
        result = app.exec_()
        print("App execution completed with result:", result)
        sys.exit(result)
    except Exception as e:
        print("Error in main:", str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()