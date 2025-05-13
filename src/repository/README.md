# Newspaper Repository System

A comprehensive system for managing historical newspaper archives - including downloading, processing, and analyzing newspaper content.

## Overview

The Newspaper Repository System provides a complete solution for:

- Downloading newspaper content from various sources (e.g., Chronicling America)
- Processing newspaper images with OCR to extract text and articles
- Storing newspaper content in a structured database with advanced search capabilities
- Managing geographic hierarchies, publications, issues, pages, and articles
- Integrating with the main Nova application database

## Components

The system consists of several key components:

### Database Manager (`database_manager.py`)

Manages the database schema, connections, and operations:

- Complete database schema with tables for geographic hierarchy, publications, issues, pages, articles, entities
- Connection pooling and transaction support
- CRUD operations for all tables
- Database maintenance and backup operations

### Publication Repository (`publication_repository.py`)

Manages newspaper publications and their content:

- Geographic hierarchy handling
- Publication metadata management
- Issue and page tracking
- Article extraction and storage
- Search capabilities

### Downloader (`downloader.py`)

Manages downloading content from external sources:

- Queue system with priorities
- Rate limiting with adaptive backoff
- Progress tracking
- Support for multiple downloaders (e.g., ChroniclingAmerica)

### OCR Processor (`ocr_processor.py`)

Processes newspaper images to extract text and articles:

- Multi-stage pipeline for preprocessing, OCR, and segmentation
- Queue system for processing with error handling
- Article boundary detection
- OCR cleanup and post-processing

### Search Engine (`search_engine.py`)

Provides advanced search capabilities:

- Full-text search for articles and entities
- Faceted search with filters
- Entity-based search and co-occurrence analysis
- Search suggestions and trending topics

### CLI Interface (`newspaper_cli.py`)

Command-line interface for interacting with the repository:

- Commands for downloading, processing, and querying content
- Operation scheduling and automation
- Database maintenance tools

### Main DB Connector (`main_db_connector.py`)

Connects the repository with the main Nova application database:

- Synchronizes sources between systems
- Imports entities and locations from main database
- Exports articles as documents to main database
- Maps relationships between repository and main database

### Background Service (`background_service.py`)

Runs automated tasks in the background:

- Scheduled downloads of new content
- OCR processing queue management
- Database maintenance operations
- Synchronization with main application

### Configuration (`config.py`)

Manages system configuration:

- Configuration loading from files
- Validation of configuration settings
- Default configuration values
- Runtime configuration updates

## Installation

1. Install required dependencies:

```
pip install -r requirements.txt
```

2. Set up the database:

```
python newspaper_cli.py setup
```

## Usage

The system can be used through the command-line interface:

### Download Publications

Download newspaper content from a source:

```
python newspaper_cli.py download --source chroniclingamerica --publication sn12345678 --start-date 1900-01-01 --end-date 1900-12-31
```

### Process with OCR

Process downloaded content with OCR:

```
python newspaper_cli.py process --publication sn12345678
```

### Search Content

Search for articles:

```
python newspaper_cli.py search "search query" --publication sn12345678 --start-date 1900-01-01 --end-date 1900-12-31
```

### List Publications

List publications in the repository:

```
python newspaper_cli.py list --source chroniclingamerica
```

### Export Articles

Export articles to file:

```
python newspaper_cli.py export --output articles.json --publication sn12345678 --format json
```

### Run Background Service

Run the background service for automated tasks:

```
python background_service.py
```

## API

The system provides a programmatic API through its component classes:

```python
from repository.database_manager import DatabaseManager
from repository.publication_repository import PublicationRepository
from repository.downloader import DownloadManager
from repository.ocr_processor import OCRProcessor
from repository.search_engine import SearchEngine

# Initialize components
db_manager = DatabaseManager(db_path="newspaper_repository.db")
pub_repo = PublicationRepository(config={"base_path": "/path/to/repository"}, db_manager=db_manager)
search = SearchEngine(db_manager=db_manager)

# Search for articles
articles = search.search_articles(query="historical event", start_date="1900-01-01", limit=10)

# Get publication statistics
stats = pub_repo.get_statistics(publication_id="sn12345678")
```

## Configuration

The system can be configured through a JSON or YAML configuration file:

```json
{
  "database": {
    "path": "/path/to/newspaper_repository.db",
    "pool_size": 5,
    "backup_directory": "/path/to/backups"
  },
  "repository": {
    "base_path": "/path/to/repository",
    "temp_path": "/path/to/temp"
  },
  "downloader": {
    "max_workers": 3,
    "retry_attempts": 3
  },
  "downloaders": {
    "chroniclingamerica": {
      "base_url": "https://chroniclingamerica.loc.gov/api/",
      "rate_limit": 5
    }
  },
  "ocr": {
    "max_workers": 2,
    "use_gpu": false,
    "engine": "tesseract"
  }
}
```

## Integration with Main Application

To integrate with the main Nova application:

1. Configure the main database path:

```json
{
  "main_database": {
    "path": "/path/to/nova_database.db"
  }
}
```

2. Run synchronization:

```python
from repository.main_db_connector import MainDatabaseConnector

connector = MainDatabaseConnector(
    repo_db_path="/path/to/newspaper_repository.db",
    main_db_path="/path/to/nova_database.db"
)

# Import entities from main database
connector.import_entities_to_repository()

# Sync articles to main database as documents
connector.sync_articles_to_documents()
```

## License

This software is proprietary and confidential.

Copyright © 2025 Nova.