from database_manager import DatabaseManager

def initialize_database():
    db_path = "C:\\AI\\Nova\\src\\nova_database.db"
    db_manager = DatabaseManager(db_path)
    db_manager.close_connection()

if __name__ == "__main__":
    initialize_database()
