# File: TabEvents.py

import sqlite3

def create_tab_events_table(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the TabEvents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS TabEvents (
            EventID INTEGER,
            CharacterID INTEGER,
            LocationID INTEGER,
            EntityID INTEGER,
            PRIMARY KEY (EventID, CharacterID, LocationID, EntityID),
            FOREIGN KEY (EventID) REFERENCES Events(EventID),
            FOREIGN KEY (CharacterID) REFERENCES Characters(CharacterID),
            FOREIGN KEY (LocationID) REFERENCES Locations(LocationID),
            FOREIGN KEY (EntityID) REFERENCES Entities(EntityID)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    db_path = "C:\\AI\\Nova\\src\\nova_database.db"
    create_tab_events_table(db_path)
