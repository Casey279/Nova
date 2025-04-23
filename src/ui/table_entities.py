# File: table_entities.py

import sqlite3

class TableEntities:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = self.create_connection()

    def create_connection(self):
        """Create a database connection to the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            print(f"Connected to the database at {self.db_path}")
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return None

    def create_entities_table(self):
        """Create the Entities table with all necessary fields."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Entities (
                    EntityID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DisplayName TEXT UNIQUE,
                    Name TEXT,
                    Aliases TEXT,
                    Type TEXT,
                    Description TEXT,
                    EstablishedDate TEXT,
                    Affiliation TEXT,
                    KnownMembers TEXT,
                    Summary TEXT,
                    ImagePath TEXT
                )
            """)
            self.conn.commit()
            print("Entities table created successfully.")
        except sqlite3.Error as e:
            print(f"Error creating Entities table: {e}")

    def insert_entity(self, display_name, name, aliases, type_, description, established_date, affiliation, known_members, summary, image_path):
        """Insert a new entity into the Entities table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO Entities (DisplayName, Name, Aliases, Type, Description, EstablishedDate, Affiliation, KnownMembers, Summary, ImagePath)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (display_name, name, aliases, type_, description, established_date, affiliation, known_members, summary, image_path))
            self.conn.commit()
            print("Entity inserted successfully.")
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting entity: {e}")
            return None

    def get_all_entities(self):
        """Fetch all entities from the Entities table."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM Entities")
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching entities: {e}")
            return []

    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")
