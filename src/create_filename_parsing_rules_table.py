import sqlite3

# Path to your database
db_path = "C:/AI/Nova/src/nova_database.db"

# Create the table for filename parsing rules
def create_filename_parsing_rules_table(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create FilenameParsingRules table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS FilenameParsingRules (
        RuleID INTEGER PRIMARY KEY AUTOINCREMENT,
        Pattern TEXT NOT NULL,
        SourceName TEXT,
        DatePosition INTEGER,
        TitlePosition INTEGER,
        Notes TEXT
    );
    """)
    
    conn.commit()
    conn.close()
    print("FilenameParsingRules table created successfully.")

if __name__ == "__main__":
    create_filename_parsing_rules_table(db_path)
