#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Database manager for the Nova newspaper repository system.

This module implements a comprehensive database manager for the newspaper repository,
defining the complete schema with tables for geographic hierarchy, publications,
pages, articles, entities, and chronology. It provides connection management,
transaction support, and CRUD operations for all repository data.
"""

import os
import sqlite3
import json
import time
import logging
import threading
import queue
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, Iterator, Callable
from contextlib import contextmanager
import traceback

from .base_repository import (
    BaseRepository, RepositoryConfig, RepositoryError, 
    DatabaseError, TransactionError, RepositoryStatus
)


class QueryExecutionError(DatabaseError):
    """Exception raised when a query fails to execute."""
    def __init__(self, query: str, params: Any = None, details: Dict = None):
        message = f"Query execution failed: {query}"
        details = details or {}
        details.update({
            "query": query,
            "params": params
        })
        super().__init__(message, details)


class ConnectionError(DatabaseError):
    """Exception raised when database connection fails."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, details)


class MigrationError(DatabaseError):
    """Exception raised when database migration fails."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, details)


class SchemaVersionError(DatabaseError):
    """Exception raised when schema version is incompatible."""
    def __init__(self, current_version: int, required_version: int, details: Dict = None):
        message = f"Schema version mismatch: current={current_version}, required={required_version}"
        details = details or {}
        details.update({
            "current_version": current_version,
            "required_version": required_version
        })
        super().__init__(message, details)


class Connection:
    """Wrapper class for SQLite connection with transaction support."""
    
    def __init__(self, connection, in_transaction=False):
        self.connection = connection
        self.cursor = connection.cursor()
        self.in_transaction = in_transaction
    
    def execute(self, query, params=None):
        """Execute a query with parameters."""
        try:
            if params is None:
                return self.cursor.execute(query)
            return self.cursor.execute(query, params)
        except sqlite3.Error as e:
            raise QueryExecutionError(query, params, {"sqlite_error": str(e)})
    
    def executemany(self, query, params_list):
        """Execute a query with multiple parameter sets."""
        try:
            return self.cursor.executemany(query, params_list)
        except sqlite3.Error as e:
            raise QueryExecutionError(query, "multiple parameter sets", {"sqlite_error": str(e)})
    
    def executescript(self, script):
        """Execute a SQL script."""
        try:
            return self.cursor.executescript(script)
        except sqlite3.Error as e:
            raise QueryExecutionError("script", None, {"sqlite_error": str(e)})
    
    def fetchone(self):
        """Fetch one row from the result set."""
        return self.cursor.fetchone()
    
    def fetchall(self):
        """Fetch all rows from the result set."""
        return self.cursor.fetchall()
    
    def fetchmany(self, size=None):
        """Fetch multiple rows from the result set."""
        return self.cursor.fetchmany(size)
    
    def commit(self):
        """Commit the current transaction."""
        if not self.in_transaction:
            return
        
        try:
            self.connection.commit()
            self.in_transaction = False
        except sqlite3.Error as e:
            raise TransactionError(f"Failed to commit transaction: {str(e)}")
    
    def rollback(self):
        """Roll back the current transaction."""
        if not self.in_transaction:
            return
        
        try:
            self.connection.rollback()
            self.in_transaction = False
        except sqlite3.Error as e:
            raise TransactionError(f"Failed to roll back transaction: {str(e)}")
    
    def close(self):
        """Close the cursor and connection."""
        try:
            if self.cursor:
                self.cursor.close()
            
            if self.in_transaction:
                self.rollback()
            
            if self.connection:
                self.connection.close()
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to close connection: {str(e)}")


class ConnectionPool:
    """Connection pool for SQLite database connections."""
    
    def __init__(self, db_path: str, max_connections: int = 5, timeout: float = 5.0):
        """
        Initialize the connection pool.
        
        Args:
            db_path: Path to the SQLite database file
            max_connections: Maximum number of connections in the pool
            timeout: Timeout in seconds for getting a connection
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.pool = queue.Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.RLock()
        
        # Initialize SQLite for thread safety
        sqlite3.threadsafety = 1  # THREAD_SAFETY: Each thread can use its own connection
        
        # Fill the pool with initial connections
        for _ in range(max_connections):
            try:
                conn = self._create_connection()
                self.pool.put(conn)
            except Exception as e:
                logging.warning(f"Failed to create initial connection: {str(e)}")
    
    def _create_connection(self):
        """Create a new SQLite connection."""
        try:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                isolation_level=None  # Use explicit transaction control
            )
            conn.row_factory = sqlite3.Row  # Use row factory for named columns
            
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Performance optimizations
            conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
            conn.execute("PRAGMA synchronous = NORMAL")  # Less durability, more speed
            conn.execute("PRAGMA cache_size = 10000")  # Larger cache (in pages)
            conn.execute("PRAGMA temp_store = MEMORY")  # Store temp tables in memory
            
            return Connection(conn)
        
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to create database connection: {str(e)}")
    
    def get_connection(self):
        """Get a connection from the pool or create a new one if needed."""
        try:
            # Try to get connection from pool
            return self.pool.get(block=True, timeout=self.timeout)
        except queue.Empty:
            # If pool is empty, check if we can create a new connection
            with self.lock:
                if self.active_connections < self.max_connections:
                    self.active_connections += 1
                    try:
                        return self._create_connection()
                    except Exception as e:
                        self.active_connections -= 1
                        raise e
            
            # If we're at max connections, try again with longer timeout
            try:
                return self.pool.get(block=True, timeout=self.timeout * 2)
            except queue.Empty:
                raise ConnectionError("Connection pool exhausted, timed out waiting for a connection")
    
    def release_connection(self, connection):
        """Release a connection back to the pool."""
        try:
            # If connection was in a transaction, roll it back
            if connection.in_transaction:
                connection.rollback()
            
            # Put connection back in the pool
            self.pool.put(connection, block=False)
        except queue.Full:
            # If pool is full, close the connection
            connection.close()
            with self.lock:
                self.active_connections -= 1
    
    def close_all(self):
        """Close all connections in the pool."""
        # Get all connections from the pool and close them
        while not self.pool.empty():
            try:
                conn = self.pool.get(block=False)
                conn.close()
            except queue.Empty:
                break
            except Exception as e:
                logging.error(f"Error closing connection: {str(e)}")


class DatabaseManager(BaseRepository):
    """Database manager for the newspaper repository."""
    
    # Current schema version - increment when schema changes
    SCHEMA_VERSION = 1
    
    def __init__(self, config: RepositoryConfig):
        """
        Initialize the database manager.
        
        Args:
            config: Repository configuration
        """
        super().__init__(config)
        
        self.db_path = config.database_path
        self.connection_pool = None
        self.current_schema_version = 0
        
        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def initialize(self) -> bool:
        """
        Initialize the database.
        
        Returns:
            True if initialization was successful
        """
        try:
            self._set_status(RepositoryStatus.INITIALIZING)
            
            # Create connection pool
            self.connection_pool = ConnectionPool(
                self.db_path,
                max_connections=5,
                timeout=5.0
            )
            
            # Check if database exists
            if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
                self.logger.info(f"Creating new database at {self.db_path}")
                self._create_schema()
            else:
                self.logger.info(f"Using existing database at {self.db_path}")
                self._verify_schema()
                self._update_schema_if_needed()
            
            self._set_status(RepositoryStatus.OK)
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            self._set_status(RepositoryStatus.ERROR, e)
            return False
    
    def close(self) -> None:
        """Close the database connection."""
        if self.connection_pool:
            self.connection_pool.close_all()
            self.connection_pool = None
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.
        
        Usage:
            with db_manager.transaction() as conn:
                conn.execute("INSERT INTO table VALUES (?)", (value,))
        """
        connection = None
        
        try:
            # Get connection from pool
            connection = self.connection_pool.get_connection()
            
            # Begin transaction
            connection.execute("BEGIN")
            connection.in_transaction = True
            
            yield connection
            
            # Commit transaction on success
            connection.commit()
        
        except Exception as e:
            # Roll back transaction on error
            if connection and connection.in_transaction:
                connection.rollback()
            raise e
        
        finally:
            # Release connection back to pool
            if connection:
                self.connection_pool.release_connection(connection)
    
    def execute_query(self, query: str, params: Any = None) -> sqlite3.Cursor:
        """
        Execute a query outside of a transaction.
        
        Args:
            query: SQL query to execute
            params: Query parameters
        
        Returns:
            SQLite cursor object
        """
        connection = None
        
        try:
            # Get connection from pool
            connection = self.connection_pool.get_connection()
            
            # Execute query
            result = connection.execute(query, params)
            
            return result
        
        finally:
            # Release connection back to pool
            if connection:
                self.connection_pool.release_connection(connection)
    
    def execute_query_fetchone(self, query: str, params: Any = None) -> Optional[sqlite3.Row]:
        """
        Execute a query and fetch one result.
        
        Args:
            query: SQL query to execute
            params: Query parameters
        
        Returns:
            First row of result or None
        """
        connection = None
        
        try:
            # Get connection from pool
            connection = self.connection_pool.get_connection()
            
            # Execute query
            cursor = connection.execute(query, params)
            result = cursor.fetchone()
            
            return result
        
        finally:
            # Release connection back to pool
            if connection:
                self.connection_pool.release_connection(connection)
    
    def execute_query_fetchall(self, query: str, params: Any = None) -> List[sqlite3.Row]:
        """
        Execute a query and fetch all results.
        
        Args:
            query: SQL query to execute
            params: Query parameters
        
        Returns:
            All rows of result
        """
        connection = None
        
        try:
            # Get connection from pool
            connection = self.connection_pool.get_connection()
            
            # Execute query
            cursor = connection.execute(query, params)
            result = cursor.fetchall()
            
            return result
        
        finally:
            # Release connection back to pool
            if connection:
                self.connection_pool.release_connection(connection)
    
    def execute_many(self, query: str, params_list: List[Any]) -> None:
        """
        Execute a query with multiple parameter sets.
        
        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
        """
        if not params_list:
            return
        
        connection = None
        
        try:
            # Get connection from pool
            connection = self.connection_pool.get_connection()
            
            # Begin transaction
            connection.execute("BEGIN")
            connection.in_transaction = True
            
            # Execute query
            connection.executemany(query, params_list)
            
            # Commit transaction
            connection.commit()
        
        except Exception as e:
            # Roll back transaction on error
            if connection and connection.in_transaction:
                connection.rollback()
            raise e
        
        finally:
            # Release connection back to pool
            if connection:
                self.connection_pool.release_connection(connection)
    
    def with_transaction(self, func, *args, **kwargs):
        """
        Execute a function within a transaction.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
        
        Returns:
            Result of the function
        """
        with self.transaction() as conn:
            return func(conn, *args, **kwargs)
    
    def _backup_database(self, temp_dir: str) -> Optional[str]:
        """
        Create a backup of the repository database.
        
        Args:
            temp_dir: Temporary directory to store the backup
        
        Returns:
            Path to the database backup file
        """
        if not os.path.exists(self.db_path):
            return None
        
        backup_path = os.path.join(temp_dir, "repository.db")
        
        try:
            # Create a connection for the backup
            conn = sqlite3.connect(self.db_path)
            backup_conn = sqlite3.connect(backup_path)
            
            conn.backup(backup_conn)
            
            backup_conn.close()
            conn.close()
            
            return backup_path
        
        except Exception as e:
            self.logger.error(f"Database backup failed: {str(e)}")
            return None
    
    def _restore_database(self, temp_dir: str) -> bool:
        """
        Restore the repository database from a backup.
        
        Args:
            temp_dir: Temporary directory with extracted backup files
        
        Returns:
            True if database restore was successful
        """
        backup_path = os.path.join(temp_dir, "repository.db")
        
        if not os.path.exists(backup_path):
            self.logger.warning("Database backup file not found in backup")
            return False
        
        try:
            # Close connection pool
            if self.connection_pool:
                self.connection_pool.close_all()
                self.connection_pool = None
            
            # Restore database file
            shutil.copy2(backup_path, self.db_path)
            
            # Recreate connection pool
            self.connection_pool = ConnectionPool(
                self.db_path,
                max_connections=5,
                timeout=5.0
            )
            
            # Verify schema
            self._verify_schema()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Database restore failed: {str(e)}")
            return False
    
    def _verify_database_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the repository database.
        
        Returns:
            Dictionary with verification results
        """
        results = {
            "success": True,
            "errors": [],
            "warnings": []
        }
        
        connection = None
        
        try:
            # Get connection from pool
            connection = self.connection_pool.get_connection()
            
            # Check database integrity
            cursor = connection.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            
            if integrity_result != "ok":
                results["errors"].append(f"Database integrity check failed: {integrity_result}")
                results["success"] = False
            
            # Check foreign key constraints
            cursor = connection.execute("PRAGMA foreign_key_check")
            fk_violations = cursor.fetchall()
            
            if fk_violations:
                results["errors"].append(f"Foreign key violations found: {len(fk_violations)}")
                results["success"] = False
            
            # Check schema version
            try:
                cursor = connection.execute("PRAGMA user_version")
                version = cursor.fetchone()[0]
                
                if version != self.SCHEMA_VERSION:
                    results["warnings"].append(
                        f"Schema version mismatch: current={version}, expected={self.SCHEMA_VERSION}"
                    )
            except Exception as e:
                results["warnings"].append(f"Could not check schema version: {str(e)}")
        
        except Exception as e:
            results["errors"].append(f"Database verification failed: {str(e)}")
            results["success"] = False
        
        finally:
            # Release connection back to pool
            if connection:
                self.connection_pool.release_connection(connection)
        
        return results
    
    def _create_schema(self) -> None:
        """Create the database schema."""
        schema_script = self._get_schema_script()
        
        try:
            with self.transaction() as conn:
                conn.executescript(schema_script)
                conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
                self.current_schema_version = self.SCHEMA_VERSION
        
        except Exception as e:
            raise DatabaseError(f"Failed to create schema: {str(e)}")
    
    def _verify_schema(self) -> None:
        """Verify that the database has the correct schema."""
        try:
            # Check schema version
            result = self.execute_query_fetchone("PRAGMA user_version")
            self.current_schema_version = result[0]
            
            # Check required tables
            required_tables = [
                "SchemaHistory", "RegionTypes", "Regions", "PublicationTypes",
                "Publications", "Issues", "Pages", "PageRegions", "Articles",
                "GlobalPeople", "GlobalPlaces", "GlobalThings", "EntityMentions",
                "Relationships", "ChronologyEvents", "ChronologyArticles",
                "ChronologyEntities"
            ]
            
            for table in required_tables:
                result = self.execute_query_fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                
                if not result:
                    raise DatabaseError(f"Required table '{table}' not found in database")
        
        except Exception as e:
            raise DatabaseError(f"Schema verification failed: {str(e)}")
    
    def _update_schema_if_needed(self) -> None:
        """Update the database schema if needed."""
        if self.current_schema_version == self.SCHEMA_VERSION:
            return
        
        if self.current_schema_version > self.SCHEMA_VERSION:
            raise SchemaVersionError(
                self.current_schema_version,
                self.SCHEMA_VERSION
            )
        
        try:
            # Get migration scripts for versions between current and target
            migrations = []
            
            for version in range(self.current_schema_version + 1, self.SCHEMA_VERSION + 1):
                migration_script = self._get_migration_script(version)
                
                if migration_script:
                    migrations.append((version, migration_script))
            
            # Apply migrations in order
            for version, script in migrations:
                self.logger.info(f"Applying migration to schema version {version}")
                
                with self.transaction() as conn:
                    conn.executescript(script)
                    conn.execute(f"PRAGMA user_version = {version}")
                    
                    # Record migration in history
                    conn.execute(
                        """
                        INSERT INTO SchemaHistory (
                            version, applied_at, description
                        ) VALUES (?, ?, ?)
                        """,
                        (version, datetime.now().isoformat(), f"Migration to version {version}")
                    )
                
                self.current_schema_version = version
        
        except Exception as e:
            raise MigrationError(f"Schema migration failed: {str(e)}")
    
    def _get_schema_script(self) -> str:
        """Get the SQL script for creating the schema."""
        return """
        -- SchemaHistory table to track migrations
        CREATE TABLE IF NOT EXISTS SchemaHistory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL,
            description TEXT
        );
        
        -- RegionTypes table
        CREATE TABLE IF NOT EXISTS RegionTypes (
            region_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            hierarchy_level INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Regions table with hierarchical relationships
        CREATE TABLE IF NOT EXISTS Regions (
            region_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            region_type_id INTEGER NOT NULL,
            parent_region_id INTEGER,
            canonical_name TEXT,
            alternate_names TEXT,
            geo_data TEXT,  -- JSON with geographic data
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (region_type_id) REFERENCES RegionTypes(region_type_id),
            FOREIGN KEY (parent_region_id) REFERENCES Regions(region_id),
            UNIQUE (name, region_type_id, parent_region_id)
        );
        
        -- PublicationTypes table
        CREATE TABLE IF NOT EXISTS PublicationTypes (
            publication_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Publications table
        CREATE TABLE IF NOT EXISTS Publications (
            publication_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            publication_type_id INTEGER NOT NULL,
            region_id INTEGER NOT NULL,  -- Where published
            publisher TEXT,
            start_date TEXT,
            end_date TEXT,
            frequency TEXT,
            language TEXT,
            lccn TEXT,  -- Library of Congress Control Number
            oclc TEXT,  -- Online Computer Library Center number
            issn TEXT,
            nova_source_id INTEGER,  -- Link to Nova Sources table
            canonical_name TEXT,
            alternate_names TEXT,
            publication_code TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (publication_type_id) REFERENCES PublicationTypes(publication_type_id),
            FOREIGN KEY (region_id) REFERENCES Regions(region_id),
            UNIQUE (name, region_id)
        );
        
        -- Issues table
        CREATE TABLE IF NOT EXISTS Issues (
            issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            publication_id INTEGER NOT NULL,
            publication_date TEXT NOT NULL,
            volume TEXT,
            issue_number TEXT,
            edition TEXT,
            page_count INTEGER,
            special_issue BOOLEAN DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (publication_id) REFERENCES Publications(publication_id),
            UNIQUE (publication_id, publication_date, edition)
        );
        
        -- Pages table
        CREATE TABLE IF NOT EXISTS Pages (
            page_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            image_path TEXT,
            image_format TEXT,
            width INTEGER,
            height INTEGER,
            dpi INTEGER,
            ocr_status TEXT DEFAULT 'pending',
            ocr_processed_at TEXT,
            ocr_engine TEXT,
            ocr_confidence REAL,
            has_text_content BOOLEAN DEFAULT 0,
            has_article_segmentation BOOLEAN DEFAULT 0,
            notes TEXT,
            source_url TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (issue_id) REFERENCES Issues(issue_id),
            UNIQUE (issue_id, page_number)
        );
        
        -- PageRegions table
        CREATE TABLE IF NOT EXISTS PageRegions (
            region_id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER NOT NULL,
            region_type TEXT NOT NULL,  -- 'article', 'advertisement', 'image', 'masthead', etc.
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            ocr_text TEXT,
            confidence REAL,
            article_id INTEGER,
            image_path TEXT,
            metadata TEXT,  -- JSON with additional metadata
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (page_id) REFERENCES Pages(page_id),
            FOREIGN KEY (article_id) REFERENCES Articles(article_id)
        );
        
        -- Articles table
        CREATE TABLE IF NOT EXISTS Articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL,
            title TEXT,
            subtitle TEXT,
            author TEXT,
            article_type TEXT,  -- 'news', 'editorial', 'advertisement', etc.
            category TEXT,
            full_text TEXT,
            word_count INTEGER,
            start_page INTEGER,
            continued_pages TEXT,  -- JSON array of page numbers
            placement TEXT,  -- 'front_page', 'above_fold', etc.
            importance INTEGER,  -- 1-10 scale of article importance
            nova_event_id INTEGER,  -- Link to Nova Events table
            is_imported_to_nova BOOLEAN DEFAULT 0,
            import_status TEXT,
            import_date TEXT,
            language TEXT,
            ocr_quality REAL,  -- Overall OCR quality score
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (issue_id) REFERENCES Issues(issue_id)
        );
        
        -- GlobalPeople table (repository for people/characters)
        CREATE TABLE IF NOT EXISTS GlobalPeople (
            person_id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            prefix TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            suffix TEXT,
            birth_date TEXT,
            death_date TEXT,
            gender TEXT,
            nationality TEXT,
            occupation TEXT,
            titles TEXT,
            alternate_names TEXT,
            nova_character_id INTEGER,  -- Link to Nova Characters table
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (display_name)
        );
        
        -- GlobalPlaces table (repository for places/locations)
        CREATE TABLE IF NOT EXISTS GlobalPlaces (
            place_id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            place_type TEXT,
            address TEXT,
            region_id INTEGER,
            geo_coordinates TEXT,  -- JSON with lat/long
            start_date TEXT,  -- When the place came into existence
            end_date TEXT,  -- When the place ceased to exist
            alternate_names TEXT,
            nova_location_id INTEGER,  -- Link to Nova Locations table
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (region_id) REFERENCES Regions(region_id),
            UNIQUE (display_name)
        );
        
        -- GlobalThings table (repository for things/organizations/entities)
        CREATE TABLE IF NOT EXISTS GlobalThings (
            thing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            thing_type TEXT,
            description TEXT,
            founded_date TEXT,
            dissolved_date TEXT,
            alternate_names TEXT,
            nova_entity_id INTEGER,  -- Link to Nova Entities table
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (display_name)
        );
        
        -- EntityMentions table
        CREATE TABLE IF NOT EXISTS EntityMentions (
            mention_id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            entity_type TEXT NOT NULL,  -- 'person', 'place', 'thing'
            entity_id INTEGER NOT NULL,  -- ID from corresponding Global* table
            mention_text TEXT NOT NULL,
            context TEXT,  -- Text surrounding the mention
            start_position INTEGER,  -- Character position in full_text
            confidence REAL,
            is_verified BOOLEAN DEFAULT 0,
            verified_by TEXT,
            verified_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (article_id) REFERENCES Articles(article_id)
        );
        
        -- Relationships table (links between entities)
        CREATE TABLE IF NOT EXISTS Relationships (
            relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,  -- 'person', 'place', 'thing'
            source_id INTEGER NOT NULL,
            target_type TEXT NOT NULL,  -- 'person', 'place', 'thing'
            target_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,  -- 'employee', 'owner', 'member', 'related', etc.
            start_date TEXT,
            end_date TEXT,
            confidence REAL,
            is_verified BOOLEAN DEFAULT 0,
            source_article_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_article_id) REFERENCES Articles(article_id)
        );
        
        -- ChronologyEvents table (for timeline)
        CREATE TABLE IF NOT EXISTS ChronologyEvents (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date TEXT NOT NULL,
            end_date TEXT,  -- For events spanning multiple days
            title TEXT NOT NULL,
            description TEXT,
            event_type TEXT,
            importance INTEGER,  -- 1-10 scale of event importance
            confidence REAL,
            is_verified BOOLEAN DEFAULT 0,
            region_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (region_id) REFERENCES Regions(region_id)
        );
        
        -- ChronologyArticles table (links articles to chronology events)
        CREATE TABLE IF NOT EXISTS ChronologyArticles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            relationship TEXT,  -- 'primary', 'related', 'context', etc.
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES ChronologyEvents(event_id),
            FOREIGN KEY (article_id) REFERENCES Articles(article_id),
            UNIQUE (event_id, article_id)
        );
        
        -- ChronologyEntities table (links entities to chronology events)
        CREATE TABLE IF NOT EXISTS ChronologyEntities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            entity_type TEXT NOT NULL,  -- 'person', 'place', 'thing'
            entity_id INTEGER NOT NULL,
            role TEXT,  -- 'participant', 'location', 'witness', etc.
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES ChronologyEvents(event_id),
            UNIQUE (event_id, entity_type, entity_id)
        );
        
        -- Create indexes for better query performance
        CREATE INDEX IF NOT EXISTS idx_regions_parent ON Regions(parent_region_id);
        CREATE INDEX IF NOT EXISTS idx_regions_type ON Regions(region_type_id);
        CREATE INDEX IF NOT EXISTS idx_publications_region ON Publications(region_id);
        CREATE INDEX IF NOT EXISTS idx_publications_type ON Publications(publication_type_id);
        CREATE INDEX IF NOT EXISTS idx_issues_publication ON Issues(publication_id);
        CREATE INDEX IF NOT EXISTS idx_issues_date ON Issues(publication_date);
        CREATE INDEX IF NOT EXISTS idx_pages_issue ON Pages(issue_id);
        CREATE INDEX IF NOT EXISTS idx_page_regions_page ON PageRegions(page_id);
        CREATE INDEX IF NOT EXISTS idx_page_regions_article ON PageRegions(article_id);
        CREATE INDEX IF NOT EXISTS idx_articles_issue ON Articles(issue_id);
        CREATE INDEX IF NOT EXISTS idx_articles_nova_event ON Articles(nova_event_id);
        CREATE INDEX IF NOT EXISTS idx_entity_mentions_article ON EntityMentions(article_id);
        CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON EntityMentions(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_source ON Relationships(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_relationships_target ON Relationships(target_type, target_id);
        CREATE INDEX IF NOT EXISTS idx_chronology_events_date ON ChronologyEvents(event_date);
        CREATE INDEX IF NOT EXISTS idx_chronology_articles_event ON ChronologyArticles(event_id);
        CREATE INDEX IF NOT EXISTS idx_chronology_articles_article ON ChronologyArticles(article_id);
        CREATE INDEX IF NOT EXISTS idx_chronology_entities_event ON ChronologyEntities(event_id);
        CREATE INDEX IF NOT EXISTS idx_chronology_entities_entity ON ChronologyEntities(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_global_people_nova ON GlobalPeople(nova_character_id);
        CREATE INDEX IF NOT EXISTS idx_global_places_nova ON GlobalPlaces(nova_location_id);
        CREATE INDEX IF NOT EXISTS idx_global_things_nova ON GlobalThings(nova_entity_id);
        
        -- Insert default data
        INSERT INTO RegionTypes (name, description, hierarchy_level)
        VALUES 
            ('Country', 'Nation or sovereign state', 1),
            ('State/Province', 'State, province, or major administrative division', 2),
            ('County', 'County or equivalent administrative division', 3),
            ('City/Town', 'City, town, or other municipality', 4);
            
        INSERT INTO PublicationTypes (name, description)
        VALUES 
            ('Newspaper', 'Daily or weekly newspaper'),
            ('Magazine', 'Periodical magazine or journal'),
            ('Book', 'Book or monograph'),
            ('Newsletter', 'Organizational newsletter'),
            ('Pamphlet', 'Pamphlet or leaflet');
        """
    
    def _get_migration_script(self, version: int) -> Optional[str]:
        """
        Get the SQL script for migrating to a specific schema version.
        
        Args:
            version: Schema version to migrate to
        
        Returns:
            SQL migration script or None if no migration is needed
        """
        # No migrations defined yet, as this is the initial schema
        return None
    
    # Additional utility methods for common operations
    
    def get_publication_by_name(self, name: str, region_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get a publication by name and optional region.
        
        Args:
            name: Publication name
            region_id: Optional region ID for disambiguation
        
        Returns:
            Publication data or None if not found
        """
        query = """
            SELECT p.*, pt.name as publication_type, r.name as region_name
            FROM Publications p
            JOIN PublicationTypes pt ON p.publication_type_id = pt.publication_type_id
            JOIN Regions r ON p.region_id = r.region_id
            WHERE p.name = ?
        """
        params = [name]
        
        if region_id is not None:
            query += " AND p.region_id = ?"
            params.append(region_id)
        
        result = self.execute_query_fetchone(query, params)
        
        if not result:
            return None
        
        return dict(result)
    
    def add_publication(self, name: str, publication_type_id: int, region_id: int, 
                        publisher: Optional[str] = None, start_date: Optional[str] = None,
                        end_date: Optional[str] = None, **kwargs) -> int:
        """
        Add a new publication.
        
        Args:
            name: Publication name
            publication_type_id: Publication type ID
            region_id: Region ID
            publisher: Publisher name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            **kwargs: Additional fields
        
        Returns:
            ID of the new publication
        """
        fields = ["name", "publication_type_id", "region_id", "publisher", "start_date", "end_date"]
        values = [name, publication_type_id, region_id, publisher, start_date, end_date]
        
        # Add any additional fields from kwargs
        for field, value in kwargs.items():
            fields.append(field)
            values.append(value)
        
        fields_str = ", ".join(fields)
        placeholders = ", ".join(["?"] * len(fields))
        
        query = f"""
            INSERT INTO Publications ({fields_str})
            VALUES ({placeholders})
        """
        
        with self.transaction() as conn:
            conn.execute(query, values)
            return conn.cursor.lastrowid
    
    def add_issue(self, publication_id: int, publication_date: str, 
                 volume: Optional[str] = None, issue_number: Optional[str] = None,
                 edition: Optional[str] = None, page_count: Optional[int] = None) -> int:
        """
        Add a new issue.
        
        Args:
            publication_id: Publication ID
            publication_date: Publication date (YYYY-MM-DD)
            volume: Volume
            issue_number: Issue number
            edition: Edition
            page_count: Number of pages
        
        Returns:
            ID of the new issue
        """
        query = """
            INSERT INTO Issues (
                publication_id, publication_date, volume, issue_number, 
                edition, page_count
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        
        with self.transaction() as conn:
            conn.execute(query, (
                publication_id, publication_date, volume, issue_number,
                edition, page_count
            ))
            return conn.cursor.lastrowid
    
    def add_page(self, issue_id: int, page_number: int, image_path: Optional[str] = None,
                image_format: Optional[str] = None) -> int:
        """
        Add a new page.
        
        Args:
            issue_id: Issue ID
            page_number: Page number
            image_path: Path to page image
            image_format: Image format (jp2, jpg, etc.)
        
        Returns:
            ID of the new page
        """
        query = """
            INSERT INTO Pages (
                issue_id, page_number, image_path, image_format
            ) VALUES (?, ?, ?, ?)
        """
        
        with self.transaction() as conn:
            conn.execute(query, (issue_id, page_number, image_path, image_format))
            return conn.cursor.lastrowid
    
    def add_article(self, issue_id: int, title: Optional[str] = None, 
                   author: Optional[str] = None, article_type: Optional[str] = None,
                   full_text: Optional[str] = None, start_page: Optional[int] = None) -> int:
        """
        Add a new article.
        
        Args:
            issue_id: Issue ID
            title: Article title
            author: Article author
            article_type: Article type
            full_text: Full text content
            start_page: Starting page number
        
        Returns:
            ID of the new article
        """
        query = """
            INSERT INTO Articles (
                issue_id, title, author, article_type, full_text, start_page
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        
        with self.transaction() as conn:
            conn.execute(query, (issue_id, title, author, article_type, full_text, start_page))
            return conn.cursor.lastrowid
    
    def get_or_create_region(self, name: str, region_type_id: int, 
                            parent_region_id: Optional[int] = None) -> int:
        """
        Get a region by name or create it if it doesn't exist.
        
        Args:
            name: Region name
            region_type_id: Region type ID
            parent_region_id: Parent region ID
        
        Returns:
            ID of the existing or new region
        """
        # Check if region exists
        query = """
            SELECT region_id FROM Regions
            WHERE name = ? AND region_type_id = ?
        """
        params = [name, region_type_id]
        
        if parent_region_id is not None:
            query += " AND parent_region_id = ?"
            params.append(parent_region_id)
        elif parent_region_id is None:
            query += " AND parent_region_id IS NULL"
        
        result = self.execute_query_fetchone(query, params)
        
        if result:
            return result[0]
        
        # Create new region
        insert_query = """
            INSERT INTO Regions (name, region_type_id, parent_region_id)
            VALUES (?, ?, ?)
        """
        
        with self.transaction() as conn:
            conn.execute(insert_query, (name, region_type_id, parent_region_id))
            return conn.cursor.lastrowid
    
    def link_article_to_nova_event(self, article_id: int, nova_event_id: int) -> bool:
        """
        Link an article to a Nova event.
        
        Args:
            article_id: Article ID
            nova_event_id: Nova event ID
        
        Returns:
            True if successful
        """
        query = """
            UPDATE Articles
            SET nova_event_id = ?, is_imported_to_nova = 1, 
                import_status = 'imported', import_date = ?
            WHERE article_id = ?
        """
        
        with self.transaction() as conn:
            conn.execute(query, (nova_event_id, datetime.now().isoformat(), article_id))
            return True
    
    def search_articles(self, search_term: str, 
                       publication_id: Optional[int] = None,
                       start_date: Optional[str] = None, 
                       end_date: Optional[str] = None,
                       article_type: Optional[str] = None,
                       limit: int = 50) -> List[Dict]:
        """
        Search articles by content and metadata.
        
        Args:
            search_term: Text to search for
            publication_id: Optional publication ID filter
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            article_type: Optional article type filter
            limit: Maximum number of results
        
        Returns:
            List of matching articles
        """
        query = """
            SELECT a.*, i.publication_date, p.name as publication_name
            FROM Articles a
            JOIN Issues i ON a.issue_id = i.issue_id
            JOIN Publications p ON i.publication_id = p.publication_id
            WHERE a.full_text LIKE ? OR a.title LIKE ?
        """
        
        params = [f"%{search_term}%", f"%{search_term}%"]
        
        if publication_id is not None:
            query += " AND i.publication_id = ?"
            params.append(publication_id)
        
        if start_date is not None:
            query += " AND i.publication_date >= ?"
            params.append(start_date)
        
        if end_date is not None:
            query += " AND i.publication_date <= ?"
            params.append(end_date)
        
        if article_type is not None:
            query += " AND a.article_type = ?"
            params.append(article_type)
        
        query += " ORDER BY i.publication_date DESC LIMIT ?"
        params.append(limit)
        
        results = self.execute_query_fetchall(query, params)
        return [dict(row) for row in results]
    
    def get_articles_by_date_range(self, start_date: str, end_date: str, 
                                 publication_id: Optional[int] = None,
                                 limit: int = 100) -> List[Dict]:
        """
        Get articles within a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            publication_id: Optional publication ID filter
            limit: Maximum number of results
        
        Returns:
            List of articles
        """
        query = """
            SELECT a.*, i.publication_date, p.name as publication_name
            FROM Articles a
            JOIN Issues i ON a.issue_id = i.issue_id
            JOIN Publications p ON i.publication_id = p.publication_id
            WHERE i.publication_date BETWEEN ? AND ?
        """
        
        params = [start_date, end_date]
        
        if publication_id is not None:
            query += " AND i.publication_id = ?"
            params.append(publication_id)
        
        query += " ORDER BY i.publication_date DESC LIMIT ?"
        params.append(limit)
        
        results = self.execute_query_fetchall(query, params)
        return [dict(row) for row in results]
    
    def get_person_mentions(self, person_id: int, limit: int = 50) -> List[Dict]:
        """
        Get mentions of a person in articles.
        
        Args:
            person_id: Person ID
            limit: Maximum number of results
        
        Returns:
            List of mentions with article context
        """
        query = """
            SELECT em.*, a.title as article_title, i.publication_date,
                   p.name as publication_name
            FROM EntityMentions em
            JOIN Articles a ON em.article_id = a.article_id
            JOIN Issues i ON a.issue_id = i.issue_id
            JOIN Publications p ON i.publication_id = p.publication_id
            WHERE em.entity_type = 'person' AND em.entity_id = ?
            ORDER BY i.publication_date DESC
            LIMIT ?
        """
        
        results = self.execute_query_fetchall(query, (person_id, limit))
        return [dict(row) for row in results]
    
    def get_chronology_events(self, start_date: str, end_date: str, 
                             region_id: Optional[int] = None,
                             limit: int = 100) -> List[Dict]:
        """
        Get chronology events within a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            region_id: Optional region ID filter
            limit: Maximum number of results
        
        Returns:
            List of chronology events
        """
        query = """
            SELECT ce.*, r.name as region_name
            FROM ChronologyEvents ce
            LEFT JOIN Regions r ON ce.region_id = r.region_id
            WHERE ce.event_date BETWEEN ? AND ?
        """
        
        params = [start_date, end_date]
        
        if region_id is not None:
            query += " AND ce.region_id = ?"
            params.append(region_id)
        
        query += " ORDER BY ce.event_date, ce.importance DESC LIMIT ?"
        params.append(limit)
        
        results = self.execute_query_fetchall(query, params)
        return [dict(row) for row in results]
    
    def get_event_articles(self, event_id: int) -> List[Dict]:
        """
        Get articles linked to a chronology event.
        
        Args:
            event_id: Chronology event ID
        
        Returns:
            List of articles
        """
        query = """
            SELECT a.*, ca.relationship, i.publication_date,
                   p.name as publication_name
            FROM ChronologyArticles ca
            JOIN Articles a ON ca.article_id = a.article_id
            JOIN Issues i ON a.issue_id = i.issue_id
            JOIN Publications p ON i.publication_id = p.publication_id
            WHERE ca.event_id = ?
            ORDER BY i.publication_date
        """
        
        results = self.execute_query_fetchall(query, (event_id,))
        return [dict(row) for row in results]
    
    def get_event_entities(self, event_id: int) -> Dict[str, List[Dict]]:
        """
        Get entities linked to a chronology event.
        
        Args:
            event_id: Chronology event ID
        
        Returns:
            Dictionary with entity types as keys and lists of entities as values
        """
        query = """
            SELECT ce.*, ce.entity_type
            FROM ChronologyEntities ce
            WHERE ce.event_id = ?
        """
        
        results = self.execute_query_fetchall(query, (event_id,))
        
        entities = {
            "person": [],
            "place": [],
            "thing": []
        }
        
        for row in results:
            row_dict = dict(row)
            entity_type = row_dict["entity_type"]
            entity_id = row_dict["entity_id"]
            
            # Get entity details based on type
            if entity_type == "person":
                person = self.get_person(entity_id)
                if person:
                    entities["person"].append({**person, "role": row_dict["role"]})
            
            elif entity_type == "place":
                place = self.get_place(entity_id)
                if place:
                    entities["place"].append({**place, "role": row_dict["role"]})
            
            elif entity_type == "thing":
                thing = self.get_thing(entity_id)
                if thing:
                    entities["thing"].append({**thing, "role": row_dict["role"]})
        
        return entities
    
    def get_person(self, person_id: int) -> Optional[Dict]:
        """
        Get a person by ID.
        
        Args:
            person_id: Person ID
        
        Returns:
            Person data or None if not found
        """
        query = """
            SELECT * FROM GlobalPeople
            WHERE person_id = ?
        """
        
        result = self.execute_query_fetchone(query, (person_id,))
        return dict(result) if result else None
    
    def get_place(self, place_id: int) -> Optional[Dict]:
        """
        Get a place by ID.
        
        Args:
            place_id: Place ID
        
        Returns:
            Place data or None if not found
        """
        query = """
            SELECT gp.*, r.name as region_name
            FROM GlobalPlaces gp
            LEFT JOIN Regions r ON gp.region_id = r.region_id
            WHERE gp.place_id = ?
        """
        
        result = self.execute_query_fetchone(query, (place_id,))
        return dict(result) if result else None
    
    def get_thing(self, thing_id: int) -> Optional[Dict]:
        """
        Get a thing by ID.
        
        Args:
            thing_id: Thing ID
        
        Returns:
            Thing data or None if not found
        """
        query = """
            SELECT * FROM GlobalThings
            WHERE thing_id = ?
        """
        
        result = self.execute_query_fetchone(query, (thing_id,))
        return dict(result) if result else None
    
    def get_or_create_person(self, display_name: str, nova_character_id: Optional[int] = None,
                           **kwargs) -> int:
        """
        Get a person by name or create them if they don't exist.
        
        Args:
            display_name: Person display name
            nova_character_id: Optional Nova character ID
            **kwargs: Additional fields
        
        Returns:
            ID of the existing or new person
        """
        # Check if person exists
        query = """
            SELECT person_id FROM GlobalPeople
            WHERE display_name = ?
        """
        
        result = self.execute_query_fetchone(query, (display_name,))
        
        if result:
            # Update Nova character ID if provided and not already set
            if nova_character_id is not None:
                update_query = """
                    UPDATE GlobalPeople
                    SET nova_character_id = ?, updated_at = ?
                    WHERE person_id = ? AND (nova_character_id IS NULL OR nova_character_id != ?)
                """
                
                self.execute_query(
                    update_query,
                    (nova_character_id, datetime.now().isoformat(), result[0], nova_character_id)
                )
            
            return result[0]
        
        # Create new person
        fields = ["display_name"]
        values = [display_name]
        
        if nova_character_id is not None:
            fields.append("nova_character_id")
            values.append(nova_character_id)
        
        # Add any additional fields from kwargs
        for field, value in kwargs.items():
            fields.append(field)
            values.append(value)
        
        fields_str = ", ".join(fields)
        placeholders = ", ".join(["?"] * len(fields))
        
        insert_query = f"""
            INSERT INTO GlobalPeople ({fields_str})
            VALUES ({placeholders})
        """
        
        with self.transaction() as conn:
            conn.execute(insert_query, values)
            return conn.cursor.lastrowid
    
    def get_or_create_place(self, display_name: str, nova_location_id: Optional[int] = None,
                           **kwargs) -> int:
        """
        Get a place by name or create it if it doesn't exist.
        
        Args:
            display_name: Place display name
            nova_location_id: Optional Nova location ID
            **kwargs: Additional fields
        
        Returns:
            ID of the existing or new place
        """
        # Check if place exists
        query = """
            SELECT place_id FROM GlobalPlaces
            WHERE display_name = ?
        """
        
        result = self.execute_query_fetchone(query, (display_name,))
        
        if result:
            # Update Nova location ID if provided and not already set
            if nova_location_id is not None:
                update_query = """
                    UPDATE GlobalPlaces
                    SET nova_location_id = ?, updated_at = ?
                    WHERE place_id = ? AND (nova_location_id IS NULL OR nova_location_id != ?)
                """
                
                self.execute_query(
                    update_query,
                    (nova_location_id, datetime.now().isoformat(), result[0], nova_location_id)
                )
            
            return result[0]
        
        # Create new place
        fields = ["display_name"]
        values = [display_name]
        
        if nova_location_id is not None:
            fields.append("nova_location_id")
            values.append(nova_location_id)
        
        # Add any additional fields from kwargs
        for field, value in kwargs.items():
            fields.append(field)
            values.append(value)
        
        fields_str = ", ".join(fields)
        placeholders = ", ".join(["?"] * len(fields))
        
        insert_query = f"""
            INSERT INTO GlobalPlaces ({fields_str})
            VALUES ({placeholders})
        """
        
        with self.transaction() as conn:
            conn.execute(insert_query, values)
            return conn.cursor.lastrowid
    
    def add_entity_mention(self, article_id: int, entity_type: str, entity_id: int,
                         mention_text: str, context: Optional[str] = None,
                         start_position: Optional[int] = None,
                         confidence: Optional[float] = None) -> int:
        """
        Add an entity mention to an article.
        
        Args:
            article_id: Article ID
            entity_type: Entity type ('person', 'place', 'thing')
            entity_id: Entity ID
            mention_text: Mention text
            context: Context around the mention
            start_position: Character position in article text
            confidence: Confidence score
        
        Returns:
            ID of the new mention
        """
        query = """
            INSERT INTO EntityMentions (
                article_id, entity_type, entity_id, mention_text,
                context, start_position, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        with self.transaction() as conn:
            conn.execute(
                query,
                (article_id, entity_type, entity_id, mention_text, context, start_position, confidence)
            )
            return conn.cursor.lastrowid
    
    def add_chronology_event(self, event_date: str, title: str, 
                           description: Optional[str] = None,
                           event_type: Optional[str] = None,
                           region_id: Optional[int] = None,
                           importance: int = 5) -> int:
        """
        Add a chronology event.
        
        Args:
            event_date: Event date (YYYY-MM-DD)
            title: Event title
            description: Event description
            event_type: Event type
            region_id: Region ID
            importance: Importance (1-10)
        
        Returns:
            ID of the new event
        """
        query = """
            INSERT INTO ChronologyEvents (
                event_date, title, description, event_type,
                region_id, importance
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        
        with self.transaction() as conn:
            conn.execute(
                query,
                (event_date, title, description, event_type, region_id, importance)
            )
            return conn.cursor.lastrowid
    
    def link_article_to_event(self, event_id: int, article_id: int, relationship: str = 'primary') -> int:
        """
        Link an article to a chronology event.
        
        Args:
            event_id: Chronology event ID
            article_id: Article ID
            relationship: Relationship type ('primary', 'related', etc.)
        
        Returns:
            ID of the new link
        """
        query = """
            INSERT OR IGNORE INTO ChronologyArticles (
                event_id, article_id, relationship
            ) VALUES (?, ?, ?)
        """
        
        with self.transaction() as conn:
            conn.execute(query, (event_id, article_id, relationship))
            return conn.cursor.lastrowid
    
    def optimize_database(self) -> bool:
        """
        Optimize the database for better performance.
        
        Returns:
            True if optimization was successful
        """
        try:
            with self.transaction() as conn:
                # Analyze tables for query optimization
                conn.execute("ANALYZE")
                
                # Reindex to optimize indexes
                conn.execute("REINDEX")
                
                # Vacuum to reclaim space and defragment
                conn.execute("VACUUM")
                
                return True
        
        except Exception as e:
            self.logger.error(f"Database optimization failed: {str(e)}")
            return False