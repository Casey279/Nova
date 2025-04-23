# File: table_events.py

import sqlite3
from sqlite3 import Error

class EventsTable:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.create_connection()
        self.create_table()

    def create_connection(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"Connected to database at {self.db_path}")
        except Error as e:
            print(f"Error connecting to database: {e}")

    def create_table(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Events (
                    EventID INTEGER PRIMARY KEY AUTOINCREMENT,
                    EventDate TEXT,
                    EventTitle TEXT,
                    EventText TEXT,
                    SourceType TEXT,
                    SourceName TEXT,
                    Filename TEXT,
                    FilePath TEXT,
                    SourceID INTEGER,
                    FOREIGN KEY (SourceID) REFERENCES Sources(SourceID)
                )
            """)
            self.conn.commit()
            print("Events Table created successfully.")
        except Error as e:
            print(f"Error creating Events table: {e}")

    def close_connection(self):
        if self.conn:
            self.conn.close()
            print("Database connection closed.")