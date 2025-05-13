#!/usr/bin/env python3
# Repository Browser UI Component
# A three-panel UI for browsing the newspaper repository

import os
import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                            QTreeView, QListView, QTableView, QLabel,
                            QLineEdit, QPushButton, QComboBox, QDateEdit,
                            QToolBar, QAction, QMenu, QAbstractItemView,
                            QHeaderView, QFrame, QScrollArea, QTextBrowser,
                            QFileDialog, QMessageBox, QTabWidget, QInputDialog)
from PyQt5.QtCore import (Qt, QSize, QDate, QModelIndex, QSortFilterProxyModel,
                         pyqtSignal, pyqtSlot, QItemSelectionModel, QThread)
from PyQt5.QtGui import QIcon, QPixmap, QStandardItemModel, QStandardItem

# Import Nova components
from src.ui.components.base_tab import BaseTab
from src.ui.components.detail_panel import DetailPanel
from src.ui.components.search_panel import SearchPanel
from src.repository.database_manager import RepositoryDatabaseManager
from src.repository.publication_repository import PublicationRepository

# Import repository UI components
try:
    from src.ui.repository_import import RepositoryImport
    from src.ui.repository_config import RepositoryConfig
except ImportError:
    # Fallback imports for development
    pass

class RepositoryTreeModel(QStandardItemModel):
    """Tree model for repository navigation by geography and publication"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(["Repository"])
        self.root_item = self.invisibleRootItem()
        
    def populate_model(self, repository):
        """Populate the tree view with regions and publications"""
        self.root_item.removeRows(0, self.root_item.rowCount())
        
        # First level: Regions
        regions = repository.get_regions()
        
        for region in regions:
            region_item = QStandardItem(region['name'])
            region_item.setData(region['id'], Qt.UserRole)
            region_item.setData("region", Qt.UserRole + 1)
            self.root_item.appendRow(region_item)
            
            # Second level: States/Provinces
            states = repository.get_states_by_region(region['id'])
            for state in states:
                state_item = QStandardItem(state['name'])
                state_item.setData(state['id'], Qt.UserRole)
                state_item.setData("state", Qt.UserRole + 1)
                region_item.appendRow(state_item)
                
                # Third level: Cities
                cities = repository.get_cities_by_state(state['id'])
                for city in cities:
                    city_item = QStandardItem(city['name'])
                    city_item.setData(city['id'], Qt.UserRole)
                    city_item.setData("city", Qt.UserRole + 1)
                    state_item.appendRow(city_item)
                    
                    # Fourth level: Publications
                    publications = repository.get_publications_by_city(city['id'])
                    for pub in publications:
                        pub_item = QStandardItem(pub['name'])
                        pub_item.setData(pub['id'], Qt.UserRole)
                        pub_item.setData("publication", Qt.UserRole + 1)
                        city_item.appendRow(pub_item)


class IssueListModel(QStandardItemModel):
    """Model for displaying newspaper issues"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(["Date", "Issue", "Pages"])
        
    def populate_issues(self, repository, publication_id=None, start_date=None, end_date=None):
        """Populate with issues from a specific publication and date range"""
        self.removeRows(0, self.rowCount())
        
        if not publication_id:
            return
            
        issues = repository.get_issues(
            publication_id=publication_id,
            start_date=start_date,
            end_date=end_date
        )
        
        for issue in issues:
            date_item = QStandardItem(issue['date'])
            issue_item = QStandardItem(issue['title'])
            page_count = QStandardItem(str(issue['page_count']))
            
            date_item.setData(issue['id'], Qt.UserRole)
            
            self.appendRow([date_item, issue_item, page_count])


class PageThumbnailModel(QStandardItemModel):
    """Model for displaying page thumbnails"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def populate_pages(self, repository, issue_id):
        """Populate with pages from a specific issue"""
        self.removeRows(0, self.rowCount())
        if not issue_id:
            return
            
        pages = repository.get_pages(issue_id)
        
        for page in pages:
            page_item = QStandardItem()
            page_item.setData(page['id'], Qt.UserRole)
            
            # Load thumbnail if available
            if page['thumbnail_path'] and os.path.exists(page['thumbnail_path']):
                thumbnail = QPixmap(page['thumbnail_path'])
                page_item.setIcon(QIcon(thumbnail))
                
            page_item.setText(f"Page {page['page_number']}")
            self.appendRow(page_item)


class LeftPanel(QWidget):
    """Left panel for repository navigation"""
    
    region_selected = pyqtSignal(int)
    state_selected = pyqtSignal(int)
    city_selected = pyqtSignal(int)
    publication_selected = pyqtSignal(int)
    
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Search bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search publications...")
        layout.addWidget(self.search_box)
        
        # Tree view
        self.tree_model = RepositoryTreeModel()
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.tree_view)
        
        # Date filter
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addYears(-1))
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.end_date)
        
        layout.addLayout(date_layout)
        
        # Filter button
        self.filter_button = QPushButton("Apply Filter")
        layout.addWidget(self.filter_button)
        
        # Populate the tree
        self.tree_model.populate_model(self.repository)
        
        self.setLayout(layout)
        
    def on_selection_changed(self, selected, deselected):
        """Handle tree item selection"""
        if not selected.indexes():
            return
            
        index = selected.indexes()[0]
        item_id = self.tree_model.itemFromIndex(index).data(Qt.UserRole)
        item_type = self.tree_model.itemFromIndex(index).data(Qt.UserRole + 1)
        
        if item_type == "region":
            self.region_selected.emit(item_id)
        elif item_type == "state":
            self.state_selected.emit(item_id)
        elif item_type == "city":
            self.city_selected.emit(item_id)
        elif item_type == "publication":
            self.publication_selected.emit(item_id)


class MiddlePanel(QWidget):
    """Middle panel for issue and page browsing"""
    
    issue_selected = pyqtSignal(int)
    page_selected = pyqtSignal(int)
    
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.current_publication_id = None
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Issues list
        self.issue_model = IssueListModel()
        self.issue_view = QTableView()
        self.issue_view.setModel(self.issue_model)
        self.issue_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.issue_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.issue_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.issue_view.selectionModel().selectionChanged.connect(self.on_issue_selected)
        layout.addWidget(self.issue_view)
        
        # Page thumbnails
        layout.addWidget(QLabel("Pages:"))
        self.page_model = PageThumbnailModel()
        self.page_view = QListView()
        self.page_view.setModel(self.page_model)
        self.page_view.setViewMode(QListView.IconMode)
        self.page_view.setIconSize(QSize(150, 200))
        self.page_view.setResizeMode(QListView.Adjust)
        self.page_view.setUniformItemSizes(True)
        self.page_view.setWordWrap(True)
        self.page_view.selectionModel().selectionChanged.connect(self.on_page_selected)
        layout.addWidget(self.page_view)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous Issue")
        self.next_button = QPushButton("Next Issue")
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        layout.addLayout(nav_layout)
        
        self.setLayout(layout)
        
    def set_publication(self, publication_id, start_date=None, end_date=None):
        """Load issues for the selected publication"""
        self.current_publication_id = publication_id
        self.issue_model.populate_issues(
            self.repository, 
            publication_id,
            start_date,
            end_date
        )
        
    def on_issue_selected(self, selected, deselected):
        """Handle issue selection"""
        if not selected.indexes():
            return
            
        index = selected.indexes()[0]  # First column has the ID
        issue_id = self.issue_model.item(index.row(), 0).data(Qt.UserRole)
        self.issue_selected.emit(issue_id)
        
        # Load pages for this issue
        self.page_model.populate_pages(self.repository, issue_id)
        
    def on_page_selected(self, selected, deselected):
        """Handle page selection"""
        if not selected.indexes():
            return
            
        index = selected.indexes()[0]
        page_id = self.page_model.item(index.row()).data(Qt.UserRole)
        self.page_selected.emit(page_id)


class RightPanel(QWidget):
    """Right panel for article preview and details"""
    
    article_selected = pyqtSignal(int)
    import_article = pyqtSignal(int)
    
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.current_page_id = None
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Page preview
        layout.addWidget(QLabel("Page Preview:"))
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_label = QLabel()
        self.preview_scroll.setWidget(self.preview_label)
        layout.addWidget(self.preview_scroll)
        
        # OCR text
        layout.addWidget(QLabel("OCR Text:"))
        self.ocr_text = QTextBrowser()
        layout.addWidget(self.ocr_text)
        
        # Article selection
        self.article_box = QComboBox()
        layout.addWidget(QLabel("Articles on Page:"))
        layout.addWidget(self.article_box)
        
        # Article metadata
        metadata_layout = QVBoxLayout()
        metadata_frame = QFrame()
        metadata_frame.setFrameShape(QFrame.StyledPanel)
        metadata_frame.setLayout(metadata_layout)
        
        self.article_title = QLabel("Title: ")
        self.article_date = QLabel("Date: ")
        self.article_author = QLabel("Author: ")
        self.article_keywords = QLabel("Keywords: ")
        
        metadata_layout.addWidget(self.article_title)
        metadata_layout.addWidget(self.article_date)
        metadata_layout.addWidget(self.article_author)
        metadata_layout.addWidget(self.article_keywords)
        
        layout.addWidget(metadata_frame)
        
        # Import button
        self.import_button = QPushButton("Import to Database")
        self.import_button.clicked.connect(self.on_import_clicked)
        layout.addWidget(self.import_button)
        
        self.setLayout(layout)
        
    def set_page(self, page_id):
        """Display the selected page"""
        if not page_id:
            return
            
        self.current_page_id = page_id
        page_data = self.repository.get_page_data(page_id)
        
        # Load the page image
        if page_data['image_path'] and os.path.exists(page_data['image_path']):
            pixmap = QPixmap(page_data['image_path'])
            self.preview_label.setPixmap(pixmap)
            self.preview_label.setFixedSize(pixmap.size())
        else:
            self.preview_label.setText("Image not available")
            
        # Display OCR text
        if page_data['ocr_text']:
            self.ocr_text.setText(page_data['ocr_text'])
        else:
            self.ocr_text.setText("OCR text not available")
            
        # Populate article dropdown
        self.article_box.clear()
        articles = self.repository.get_articles(page_id)
        for article in articles:
            self.article_box.addItem(article['title'], article['id'])
        
        self.article_box.currentIndexChanged.connect(self.on_article_changed)
        
        # Display first article if available
        if self.article_box.count() > 0:
            self.on_article_changed(0)
            
    def on_article_changed(self, index):
        """Handle article selection"""
        if index < 0:
            return
            
        article_id = self.article_box.itemData(index)
        self.article_selected.emit(article_id)
        
        article_data = self.repository.get_article_data(article_id)
        
        # Update metadata display
        self.article_title.setText(f"Title: {article_data['title']}")
        self.article_date.setText(f"Date: {article_data['date']}")
        self.article_author.setText(f"Author: {article_data['author'] or 'Unknown'}")
        self.article_keywords.setText(f"Keywords: {article_data['keywords'] or 'None'}")
        
        # Highlight article text in OCR
        if article_data['text'] and article_data['text'] in self.ocr_text.toPlainText():
            cursor = self.ocr_text.textCursor()
            self.ocr_text.moveCursor(cursor.Start)
            found = self.ocr_text.find(article_data['text'])
        
    def on_import_clicked(self):
        """Handle article import button"""
        if self.article_box.currentIndex() >= 0:
            article_id = self.article_box.itemData(self.article_box.currentIndex())
            self.import_article.emit(article_id)


class RepositoryBrowser(BaseTab):
    """Repository Browser Tab"""

    def __init__(self, parent=None):
        super().__init__("Repository Browser", parent)
        self.db_manager = RepositoryDatabaseManager()
        self.repository = PublicationRepository(self.db_manager)
        self.initUI()
        self.connectSignals()

    def initUI(self):
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Create panels
        self.left_panel = LeftPanel(self.repository)
        self.middle_panel = MiddlePanel(self.repository)
        self.right_panel = RightPanel(self.repository)

        # Add panels to splitter
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.middle_panel)
        self.main_splitter.addWidget(self.right_panel)

        # Set initial sizes
        self.main_splitter.setSizes([200, 400, 400])

        # Add to layout
        self.main_layout.addWidget(self.main_splitter)

        # Create toolbar
        self.toolbar = QToolBar()
        self.refresh_action = QAction("Refresh", self)
        self.import_action = QAction("Import Content", self)
        self.export_action = QAction("Export", self)
        self.settings_action = QAction("Settings", self)

        self.toolbar.addAction(self.refresh_action)
        self.toolbar.addAction(self.import_action)
        self.toolbar.addAction(self.export_action)
        self.toolbar.addAction(self.settings_action)

        self.main_layout.addWidget(self.toolbar)

        # Import and Config dialogs
        self.import_dialog = None
        self.config_dialog = None
        
    def connectSignals(self):
        """Connect all signals between components"""
        # Left panel signals
        self.left_panel.publication_selected.connect(self.on_publication_selected)
        self.left_panel.filter_button.clicked.connect(self.apply_filters)

        # Middle panel signals
        self.middle_panel.issue_selected.connect(self.on_issue_selected)
        self.middle_panel.page_selected.connect(self.on_page_selected)

        # Right panel signals
        self.right_panel.import_article.connect(self.on_import_article)

        # Toolbar signals
        self.refresh_action.triggered.connect(self.refresh_repository)
        self.import_action.triggered.connect(self.open_import_dialog)
        self.export_action.triggered.connect(self.export_data)
        self.settings_action.triggered.connect(self.open_settings)
        
    def on_publication_selected(self, publication_id):
        """Handle publication selection from tree view"""
        start_date = self.left_panel.start_date.date().toPyDate()
        end_date = self.left_panel.end_date.date().toPyDate()
        
        self.middle_panel.set_publication(publication_id, start_date, end_date)
        
    def on_issue_selected(self, issue_id):
        """Handle issue selection from middle panel"""
        # Nothing to do here - middle panel updates itself
        pass
        
    def on_page_selected(self, page_id):
        """Handle page selection from middle panel"""
        self.right_panel.set_page(page_id)
        
    def apply_filters(self):
        """Apply date filters to current publication"""
        if self.middle_panel.current_publication_id:
            start_date = self.left_panel.start_date.date().toPyDate()
            end_date = self.left_panel.end_date.date().toPyDate()
            self.middle_panel.set_publication(
                self.middle_panel.current_publication_id,
                start_date,
                end_date
            )
        
    def on_import_article(self, article_id):
        """Handle article import request"""
        article_data = self.repository.get_article_data(article_id)
        
        # Here you would integrate with Nova's import system
        # For now, show a simple message
        QMessageBox.information(
            self,
            "Import Article",
            f"Article '{article_data['title']}' would be imported to the database."
        )
        
    def refresh_repository(self):
        """Refresh all data from repository"""
        self.left_panel.tree_model.populate_model(self.repository)
        
    def export_data(self):
        """Export current view to file"""
        # Simplified export functionality
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            "",
            "CSV Files (*.csv);;Text Files (*.txt)"
        )
        
        if not file_path:
            return
            
        QMessageBox.information(
            self,
            "Export",
            f"Would export current view to {file_path}"
        )
        
    def open_import_dialog(self):
        """Open repository import dialog"""
        try:
            if self.import_dialog is None:
                self.import_dialog = RepositoryImport()

            self.import_dialog.show()
            self.import_dialog.raise_()
            self.import_dialog.activateWindow()
        except (NameError, AttributeError) as e:
            # Fallback if import component is not available
            QMessageBox.information(
                self,
                "Import Content",
                "The repository import component is not available yet."
            )
            print(f"Import dialog error: {e}")

    def open_settings(self):
        """Open repository settings dialog"""
        try:
            if self.config_dialog is None:
                self.config_dialog = RepositoryConfig()

            self.config_dialog.show()
            self.config_dialog.raise_()
            self.config_dialog.activateWindow()
        except (NameError, AttributeError) as e:
            # Fallback if config component is not available
            QMessageBox.information(
                self,
                "Repository Settings",
                "The repository configuration component is not available yet."
            )
            print(f"Config dialog error: {e}")


# For testing purposes
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    browser = RepositoryBrowser()
    browser.show()
    sys.exit(app.exec_())