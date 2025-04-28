# File: base_service.py

import sqlite3
from typing import List, Dict, Any, Tuple, Optional, Union

class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass

class BaseService:
    """
    Base service class for database operations.
    Provides common functionality for database access.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the service with a database path.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
    
    def connect(self) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
        """
        Connect to the database and return connection and cursor.
        
        Returns:
            A tuple containing (connection, cursor)
            
        Raises:
            DatabaseError: If connection fails
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            return conn, cursor
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to connect to database: {str(e)}")
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[Tuple]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query to execute
            params: Parameters for the query
            
        Returns:
            List of result rows
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            conn, cursor = self.connect()
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            return results
        except sqlite3.Error as e:
            raise DatabaseError(f"Query execution failed: {str(e)}")
    
    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query and return affected row count.
        
        Args:
            query: SQL query to execute
            params: Parameters for the query
            
        Returns:
            Number of affected rows
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            conn, cursor = self.connect()
            cursor.execute(query, params)
            row_count = cursor.rowcount
            conn.commit()
            conn.close()
            return row_count
        except sqlite3.Error as e:
            raise DatabaseError(f"Update operation failed: {str(e)}")
    
    def execute_transaction(self, queries: List[Dict[str, Any]]) -> None:
        """
        Execute multiple queries as a transaction.
        
        Args:
            queries: List of dictionaries with 'query' and 'params' keys
            
        Raises:
            DatabaseError: If transaction fails
        """
        try:
            conn, cursor = self.connect()
            
            for query_data in queries:
                cursor.execute(query_data['query'], query_data['params'])
            
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            raise DatabaseError(f"Transaction failed: {str(e)}")
    
    def get_last_insert_id(self) -> int:
        """
        Get the ID of the last inserted row.
        
        Returns:
            Last insert ID
            
        Raises:
            DatabaseError: If operation fails
        """
        try:
            conn, cursor = self.connect()
            cursor.execute("SELECT last_insert_rowid()")
            last_id = cursor.fetchone()[0]
            conn.close()
            return last_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get last insert ID: {str(e)}")