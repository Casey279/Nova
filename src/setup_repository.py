#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Repository Setup Script

This script initializes the repository environment, creates necessary directories,
and ensures all the required files are in place.
"""

import os
import sys
import logging
import sqlite3

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_directory(path):
    """Create directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"Created directory: {path}")
    else:
        logger.info(f"Directory already exists: {path}")
    return path

def init_database(db_path):
    """Initialize the repository database with basic tables."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create basic tables if they don't exist
        
        # Publications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lccn TEXT,
            publisher TEXT,
            location TEXT,
            start_year INTEGER,
            end_year INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # Issues table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publication_id INTEGER,
            issue_date TEXT,
            volume TEXT,
            number TEXT,
            edition TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (publication_id) REFERENCES publications (id)
        )
        ''')
        
        # Pages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER,
            page_number INTEGER,
            image_path TEXT,
            thumbnail_path TEXT,
            ocr_text TEXT,
            ocr_completed BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (issue_id) REFERENCES issues (id)
        )
        ''')
        
        # Processing queue table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_queue (
            id TEXT PRIMARY KEY,
            page_id TEXT,
            operation TEXT,
            parameters TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 1,
            retries INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            result TEXT
        )
        ''')
        
        # Bulk processing tasks table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bulk_processing_tasks (
            bulk_id TEXT PRIMARY KEY,
            created_at TEXT,
            updated_at TEXT,
            task_data TEXT
        )
        ''')
        
        conn.commit()
        logger.info(f"Database initialized: {db_path}")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def setup_repository():
    """Set up the repository environment."""
    try:
        # Get base directory (script directory's parent)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logger.info(f"Base directory: {base_dir}")
        
        # Create repository directory
        repo_dir = os.path.join(base_dir, "src", "newspaper_repository")
        if not os.path.exists(repo_dir):
            os.makedirs(repo_dir)
            logger.info(f"Created repository directory: {repo_dir}")
        
        # Create subdirectories
        ensure_directory(os.path.join(repo_dir, "original"))
        ensure_directory(os.path.join(repo_dir, "processed"))
        ensure_directory(os.path.join(repo_dir, "ocr_results"))
        ensure_directory(os.path.join(repo_dir, "article_clips"))
        ensure_directory(os.path.join(repo_dir, "logs"))
        ensure_directory(os.path.join(repo_dir, "temp"))
        
        # Create database
        db_path = os.path.join(repo_dir, "repository.db")
        init_database(db_path)
        
        logger.info("Repository setup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error setting up repository: {e}")
        return False

if __name__ == "__main__":
    success = setup_repository()
    sys.exit(0 if success else 1)