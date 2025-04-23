# File: table_characters.py

import sqlite3
from sqlite3 import Error

class CharactersTable:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.create_connection()
        self.create_table()

    def create_connection(self):
        """Create a database connection to SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            print(f"Connected to database at {self.db_path}")
        except Error as e:
            print(f"Error connecting to database: {e}")

    def create_table(self):
        """Create the Characters table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS Characters (
                                CharacterID INTEGER PRIMARY KEY AUTOINCREMENT,
                                FirstName TEXT,
                                LastName TEXT,
                                DisplayName TEXT,
                                Aliases TEXT,
                                Gender TEXT,
                                BirthDate TEXT,
                                DeathDate TEXT,
                                Height TEXT,
                                Weight TEXT,
                                Hair TEXT,
                                Eyes TEXT,
                                Occupation TEXT,
                                Affiliations TEXT,
                                ImagePath TEXT,
                                BackgroundSummary TEXT,
                                PersonalityTraits TEXT,
                                ClifftonStrengths TEXT,
                                Enneagram TEXT,
                                MyersBriggs TEXT,
                                FindAGrave TEXT
                            )''')
            self.conn.commit()
            print("Characters Table created successfully.")
        except Error as e:
            print(f"Error creating Characters table: {e}")

    def insert_character(self, first_name, last_name, display_name, aliases, gender, birth_date, death_date, height, weight, hair, eyes, occupation, affiliations, image_path, background_summary, personality_traits, cliffton_strengths, enneagram, myers_briggs):
        """Insert a new character into the Characters table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO Characters 
                (FirstName, LastName, DisplayName, Aliases, Gender, BirthDate, DeathDate, Height, Weight, Hair, Eyes, Occupation, Affiliations, ImagePath, BackgroundSummary, PersonalityTraits, ClifftonStrengths, Enneagram, MyersBriggs) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (first_name, last_name, display_name, aliases, gender, birth_date, death_date, height, weight, hair, eyes, occupation, affiliations, image_path, background_summary, personality_traits, cliffton_strengths, enneagram, myers_briggs))
            self.conn.commit()
            print("Character inserted successfully.")
        except Error as e:
            print(f"Error inserting character: {e}")

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")
