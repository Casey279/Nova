import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QPushButton, QMessageBox, QHeaderView)
from PyQt5.QtCore import Qt
from database_manager import DatabaseManager

class ViewTableDataTab(QWidget):
    def __init__(self, db_path):
        super().__init__()
        self.db_manager = DatabaseManager(db_path)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Dropdown to select the table to view
        self.table_selector = QComboBox()
        self.table_selector.addItems(["Events", "Characters", "Locations", "Entities"])  # Add more tables as needed
        self.table_selector.currentIndexChanged.connect(self.load_table_data)
        layout.addWidget(QLabel("Select Table"))
        layout.addWidget(self.table_selector)

        # Table display area
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)  # Prevent editing for now
        self.table_widget.horizontalHeader().setStretchLastSection(True)  # Stretch the last column to fit the width
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # Stretch columns to fit the view
        layout.addWidget(self.table_widget)

        # Button to delete selected rows
        self.delete_button = QPushButton("Delete Selected Row(s)")
        self.delete_button.clicked.connect(self.delete_selected_rows)
        layout.addWidget(self.delete_button)

        self.setLayout(layout)

    def load_table_data(self):
        selected_table = self.table_selector.currentText()
        table_data = self.db_manager.get_table_data(selected_table)

        # Populate table_widget with data
        if table_data:
            self.table_widget.setRowCount(len(table_data))
            self.table_widget.setColumnCount(len(table_data[0]))
            self.table_widget.setHorizontalHeaderLabels([key for key in table_data[0].keys()])

            for row_idx, row_data in enumerate(table_data):
                for col_idx, (key, value) in enumerate(row_data.items()):
                    self.table_widget.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

        # Lock column headers to stay in view during scrolling (handled automatically by QTableWidget)

    def delete_selected_rows(self):
        selected_table = self.table_selector.currentText()
        selected_rows = self.table_widget.selectionModel().selectedRows()

        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a row to delete.")
            return

        confirm = QMessageBox.question(self, "Confirm Deletion", "Are you sure you want to delete the selected row(s)?", 
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if confirm == QMessageBox.Yes:
            for row in selected_rows:
                row_id = self.table_widget.item(row.row(), 0).text()  # Assuming the primary key is in the first column
                self.db_manager.delete_row(selected_table, row_id)

            self.load_table_data()  # Reload the table to reflect changes
