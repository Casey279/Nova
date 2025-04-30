# File: table_events.py

import sqlite3
from sqlite3 import Error

class EventsTable:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.create_connection()
        

    def create_connection(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"Connected to database at {self.db_path}")
        except Error as e:
            print(f"Error connecting to database: {e}")

    def close_connection(self):
        if self.conn:
            self.conn.close()
            print("Database connection closed.")