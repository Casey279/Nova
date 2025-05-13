# Bulk Operations Guide

This guide explains how to perform bulk operations with the Newspaper Repository System. Bulk operations are useful for batch importing, processing, and managing large volumes of newspaper content.

## Table of Contents

- [Bulk Downloads](#bulk-downloads)
- [Bulk OCR Processing](#bulk-ocr-processing)
- [Bulk Entity Extraction](#bulk-entity-extraction)
- [Bulk Imports](#bulk-imports)
- [Bulk Exports](#bulk-exports)
- [Maintenance Operations](#maintenance-operations)

## Bulk Downloads

To download large volumes of newspaper content, use the `bulk_task.py` module or the CLI with appropriate parameters.

### Using the CLI

Download an entire publication:

```bash
python newspaper_cli.py download --source chroniclingamerica --publication sn12345678 --max-items 0
```

> Setting `--max-items 0` removes the limit and downloads all available issues.

Download multiple publications by date range:

```bash
python newspaper_cli.py download --source chroniclingamerica --publication sn12345678,sn87654321 --start-date 1900-01-01 --end-date 1910-12-31
```

### Using the API

For more complex bulk downloads, use the API:

```python
from repository.bulk_task import BulkTask
from repository.downloader import DownloadManager

# Initialize components
download_manager = DownloadManager(config={"base_path": "/path/to/repository"})

# Create a bulk task
bulk_task = BulkTask(
    task_type="download",
    parameters={
        "source": "chroniclingamerica",
        "publications": ["sn12345678", "sn87654321"],
        "date_range": {
            "start": "1900-01-01",
            "end": "1910-12-31"
        },
        "max_concurrent": 3,
        "rate_limit": 5
    }
)

# Execute the task
bulk_task.execute(download_manager=download_manager)

# Check status
status = bulk_task.get_status()
print(f"Downloaded {status['completed']} of {status['total']} items")
```

## Bulk OCR Processing

Process large volumes of newspaper pages with OCR.

### Using the CLI

Process all unprocessed issues for a publication:

```bash
python newspaper_cli.py process --publication sn12345678
```

Reprocess issues that were already processed:

```bash
python newspaper_cli.py process --publication sn12345678 --reprocess
```

### Using the API

For more control over OCR processing:

```python
from repository.bulk_task import BulkTask
from repository.ocr_processor import OCRProcessor
from repository.publication_repository import PublicationRepository
from repository.database_manager import DatabaseManager

# Initialize components
db_manager = DatabaseManager(db_path="newspaper_repository.db")
pub_repo = PublicationRepository(config={"base_path": "/path/to/repository"}, db_manager=db_manager)
ocr_processor = OCRProcessor(config={"base_path": "/path/to/repository"}, publication_repo=pub_repo)

# Create bulk OCR task
bulk_task = BulkTask(
    task_type="ocr",
    parameters={
        "publication_id": "sn12345678",
        "date_range": {
            "start": "1900-01-01",
            "end": "1900-12-31"
        },
        "max_concurrent": 2,
        "reprocess": False,
        "ocr_engine": "tesseract",
        "segment_articles": True
    }
)

# Execute the task
bulk_task.execute(ocr_processor=ocr_processor)

# Check status
status = bulk_task.get_status()
print(f"Processed {status['completed']} of {status['total']} pages")
```

## Bulk Entity Extraction

Extract entities from processed articles in bulk.

### Using the CLI

Extract entities from all articles in a publication:

```bash
python newspaper_cli.py extract-entities --publication sn12345678
```

Extract entities for a specific date range:

```bash
python newspaper_cli.py extract-entities --publication sn12345678 --start-date 1900-01-01 --end-date 1900-12-31
```

### Using the API

For more control over entity extraction:

```python
from repository.bulk_task import BulkTask
from repository.database_manager import DatabaseManager
from repository.publication_repository import PublicationRepository

# Initialize components
db_manager = DatabaseManager(db_path="newspaper_repository.db")
pub_repo = PublicationRepository(config={"base_path": "/path/to/repository"}, db_manager=db_manager)

# Create bulk entity extraction task
bulk_task = BulkTask(
    task_type="entity_extraction",
    parameters={
        "publication_id": "sn12345678",
        "date_range": {
            "start": "1900-01-01",
            "end": "1900-12-31"
        },
        "entity_types": ["person", "organization", "location"],
        "min_confidence": 0.7,
        "batch_size": 100
    }
)

# Execute the task
bulk_task.execute(publication_repo=pub_repo)

# Check status
status = bulk_task.get_status()
print(f"Processed {status['articles']} articles, extracted {status['entities']} entities")
```

## Bulk Imports

Import data from external sources in bulk.

### Import from Flat Files

```python
from repository.bulk_task import BulkTask
from repository.database_manager import DatabaseManager

# Initialize components
db_manager = DatabaseManager(db_path="newspaper_repository.db")

# Create bulk import task
bulk_task = BulkTask(
    task_type="import",
    parameters={
        "source_type": "csv",
        "source_path": "/path/to/articles.csv",
        "mapping": {
            "publication_id": "paper_id",
            "issue_date": "date",
            "page_number": "page",
            "title": "headline",
            "text": "content"
        },
        "batch_size": 1000
    }
)

# Execute the task
bulk_task.execute(db_manager=db_manager)

# Check status
status = bulk_task.get_status()
print(f"Imported {status['imported']} of {status['total']} records")
```

### Import from Another Database

```python
from repository.bulk_task import BulkTask
from repository.database_manager import DatabaseManager

# Initialize components
db_manager = DatabaseManager(db_path="newspaper_repository.db")

# Create bulk import task
bulk_task = BulkTask(
    task_type="import",
    parameters={
        "source_type": "sqlite",
        "source_path": "/path/to/other_db.sqlite",
        "source_query": "SELECT * FROM newspapers WHERE year > 1900",
        "mapping": {
            "publication_id": "paper_id",
            "issue_date": "date",
            "page_number": "page",
            "title": "headline",
            "text": "content"
        },
        "batch_size": 1000
    }
)

# Execute the task
bulk_task.execute(db_manager=db_manager)
```

## Bulk Exports

Export data in bulk for external use.

### Using the CLI

Export articles to JSON:

```bash
python newspaper_cli.py export --output articles.json --publication sn12345678 --format json
```

Export to CSV with filters:

```bash
python newspaper_cli.py export --output articles.csv --publication sn12345678 --start-date 1900-01-01 --end-date 1900-12-31 --format csv
```

### Using the API

For more control over exports:

```python
from repository.bulk_task import BulkTask
from repository.database_manager import DatabaseManager
from repository.publication_repository import PublicationRepository

# Initialize components
db_manager = DatabaseManager(db_path="newspaper_repository.db")
pub_repo = PublicationRepository(config={"base_path": "/path/to/repository"}, db_manager=db_manager)

# Create bulk export task
bulk_task = BulkTask(
    task_type="export",
    parameters={
        "output_format": "json",
        "output_path": "/path/to/export",
        "publication_id": "sn12345678",
        "date_range": {
            "start": "1900-01-01",
            "end": "1900-12-31"
        },
        "include_fields": ["title", "text", "issue_date", "page_number", "publication_title"],
        "batch_size": 1000
    }
)

# Execute the task
bulk_task.execute(publication_repo=pub_repo)

# Check status
status = bulk_task.get_status()
print(f"Exported {status['exported']} articles to {status['output_path']}")
```

## Maintenance Operations

Perform database maintenance operations in bulk.

### Using the CLI

Rebuild search indexes:

```bash
python newspaper_cli.py maintenance --rebuild-index
```

Vacuum database:

```bash
python newspaper_cli.py maintenance --vacuum
```

Create backup:

```bash
python newspaper_cli.py backup --output /path/to/backup.db
```

### Using the API

For scheduled maintenance:

```python
from repository.bulk_task import BulkTask
from repository.database_manager import DatabaseManager
from repository.search_engine import SearchEngine

# Initialize components
db_manager = DatabaseManager(db_path="newspaper_repository.db")
search_engine = SearchEngine(db_manager=db_manager)

# Create maintenance task
bulk_task = BulkTask(
    task_type="maintenance",
    parameters={
        "operations": ["vacuum", "analyze", "rebuild_index", "backup"],
        "backup_path": "/path/to/backups/newspaper_repo_backup.db"
    }
)

# Execute the task
bulk_task.execute(db_manager=db_manager, search_engine=search_engine)

# Check status
status = bulk_task.get_status()
print(f"Maintenance completed: {', '.join(status['completed_operations'])}")
```

## Scheduling Bulk Operations

Schedule bulk operations to run periodically using the background service:

```python
from repository.background_service import BackgroundService

# Initialize service
service = BackgroundService(config_path="config.json")

# Register custom bulk task
service.register_task(
    name="monthly_download",
    function=lambda: service.run_bulk_task(
        task_type="download",
        parameters={
            "source": "chroniclingamerica",
            "publications": ["sn12345678"],
            "date_range": "latest_month",
            "max_concurrent": 2
        }
    ),
    interval=30 * 24 * 60 * 60,  # 30 days
    enabled=True
)

# Start the service
service.start()
```

For more complex scheduling, use the `bulk_task.py` module directly with your own scheduling system.