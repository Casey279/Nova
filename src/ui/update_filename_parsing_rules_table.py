import sqlite3

def update_filename_parsing_rules_table(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='FilenameParsingRules'")
    if cursor.fetchone() is None:
        # Create the table if it doesn't exist
        print("Creating FilenameParsingRules table...")
        cursor.execute("""
            CREATE TABLE FilenameParsingRules (
                RuleID INTEGER PRIMARY KEY AUTOINCREMENT,
                Pattern TEXT NOT NULL,
                SourceLabel TEXT,
                DatePosition INTEGER,
                SourcePosition INTEGER,
                PagePosition INTEGER,
                Notes TEXT
            )
        """)
    else:
        # Check if the new columns already exist
        cursor.execute("PRAGMA table_info(FilenameParsingRules)")
        existing_columns = [info[1] for info in cursor.fetchall()]

        # Add missing columns
        if "SourceLabel" not in existing_columns:
            print("Adding SourceLabel column...")
            cursor.execute("ALTER TABLE FilenameParsingRules ADD COLUMN SourceLabel TEXT")

        if "DatePosition" not in existing_columns:
            print("Adding DatePosition column...")
            cursor.execute("ALTER TABLE FilenameParsingRules ADD COLUMN DatePosition INTEGER")

        if "SourcePosition" not in existing_columns:
            print("Adding SourcePosition column...")
            cursor.execute("ALTER TABLE FilenameParsingRules ADD COLUMN SourcePosition INTEGER")

        if "PagePosition" not in existing_columns:
            print("Adding PagePosition column...")
            cursor.execute("ALTER TABLE FilenameParsingRules ADD COLUMN PagePosition INTEGER")

        if "Notes" not in existing_columns:
            print("Adding Notes column...")
            cursor.execute("ALTER TABLE FilenameParsingRules ADD COLUMN Notes TEXT")

    conn.commit()
    conn.close()
    print("Database schema updated successfully.")

# Path to your database
db_path = "C:/AI/Nova/src/nova_database.db"
update_filename_parsing_rules_table(db_path)
