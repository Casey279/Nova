# Newspaper Repository System

A comprehensive system for collecting, processing, and integrating historical newspaper content into the Nova Historical Database.

## Overview

The Newspaper Repository System is designed to serve as an intermediate processing layer between raw newspaper sources (such as ChroniclingAmerica, Newspapers.com, etc.) and the structured events in the main Nova database. It handles:

- Storage and organization of newspaper page images
- OCR processing of newspaper content
- Extraction of individual article segments
- Maintaining a searchable repository of articles
- Background processing of content
- Full-text search across repositories
- Promoting selected articles to the main database as events

## Table of Contents

1. [Components](#components)
2. [Setup Instructions](#setup-instructions)
3. [API Documentation](#api-documentation)
4. [Usage Examples](#usage-examples)
5. [Integration with Nova](#integration-with-nova)
6. [Troubleshooting](#troubleshooting)
7. [Performance Optimization](#performance-optimization)

## Components

The system consists of the following main components:

1. **Repository Database Manager** (`repository_database.py`): Manages the SQLite database for storing newspaper pages, article segments, keywords, and the processing queue.

2. **File Manager** (`file_manager.py`): Handles file organization, saving, and retrieving for various types of files (original pages, OCR text, article segments, etc.).

3. **OCR Processor** (`ocr_processor.py`): Performs Optical Character Recognition and layout analysis on newspaper pages, extracting both text and article segments.

4. **Main DB Connector** (`main_db_connector.py`): Facilitates integration with the main Nova database, handling the transfer of article data and maintaining links between systems.

5. **Background Processing Service** (`background_service.py`): Manages asynchronous processing tasks in a separate thread, providing queue management, error handling, and progress updates.

6. **Search Engine** (`search_engine.py`): Provides full-text search capabilities across both the newspaper repository and main database, with support for advanced query syntax and faceted search.

7. **API Client** (`api/chronicling_america.py`): Client for interacting with external newspaper archives, specifically the Library of Congress Chronicling America API.

## Setup Instructions

### Prerequisites

1. Python 3.6+ with required packages (see `requirements.txt`)
2. Tesseract OCR installed on your system
3. Sufficient disk space for newspaper images and derived files
4. SQLite3 support

### Installation

1. Clone the repository or download the source code to your local machine.

2. Install required Python packages:

```bash
pip install -r requirements.txt
```

3. Install Tesseract OCR:

**Windows:**
Download and install from https://github.com/UB-Mannheim/tesseract/wiki

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

4. Create the repository structure:

```python
from newspaper_repository.file_manager import FileManager

# Initialize file manager with desired repository path
file_manager = FileManager("/path/to/repository")
# Directory structure is created automatically
```

5. Initialize the repository database:

```python
from newspaper_repository.repository_database import RepositoryDatabaseManager

# Initialize database manager
db_manager = RepositoryDatabaseManager("/path/to/repository/repository.db")
# Database and tables are created automatically
```

6. Initialize the search index:

```python
from newspaper_repository.search_engine import SearchEngine

# Initialize search engine
search_engine = SearchEngine(
    index_path="/path/to/repository/search_index.db",
    newspaper_db_path="/path/to/repository/repository.db",
    main_db_path="/path/to/nova_database.db"
)

# Build initial index (may take time for large collections)
search_engine.reindex_all()
```

### Configuration

The system configuration is managed through the `config.py` file:

```python
from newspaper_repository.config import RepositoryConfig, ConfigManager

# Get default configuration
config = ConfigManager.get_default_config()

# Update configuration
config.tesseract_path = "/path/to/tesseract"
config.repository_path = "/path/to/repository"
config.ocr_language = "eng"
config.max_concurrent_tasks = 4
config.default_search_options.fuzzy = True
config.default_search_options.fuzzy_threshold = 75

# Save configuration
ConfigManager.save_config(config, "/path/to/config.json")

# Load configuration
loaded_config = ConfigManager.load_config("/path/to/config.json")
```

Key configuration options:

| Option | Description | Default |
|--------|-------------|---------|
| repository_path | Base path for all repository files | ./repository |
| database_path | Path to the repository database | {repository_path}/repository.db |
| search_index_path | Path to the search index | {repository_path}/search_index.db |
| tesseract_path | Path to Tesseract executable | Default system path |
| ocr_language | Language for OCR processing | eng |
| max_concurrent_tasks | Maximum number of concurrent background tasks | 2 |
| retry_delay_seconds | Seconds to wait before retrying failed tasks | 300 |
| max_retries | Maximum number of retry attempts | 3 |
| default_search_options | Default options for search operations | See SearchOptions class |

## API Documentation

### RepositoryDatabaseManager

Manages all database operations for the newspaper repository.

#### Initialization

```python
db_manager = RepositoryDatabaseManager(db_path)
```

Parameters:
- `db_path` (str): Path to the SQLite database file

#### Newspaper Pages Methods

```python
# Add a new newspaper page
page_id = db_manager.add_newspaper_page(
    publication_name="The Daily Times",
    publication_date="1900-01-01",
    page_number=1,
    source_id="chroniclingamerica",
    source_type="newspaper",
    image_path="/path/to/image.jpg",
    ocr_text="",  # Optional, can be added later
    ocr_hocr_path="",  # Optional, can be added later
    metadata={"lccn": "sn86069873"}  # Optional metadata dictionary
)

# Get page by ID
page = db_manager.get_newspaper_page(page_id)

# Update newspaper page
db_manager.update_newspaper_page(
    page_id=page_id,
    ocr_text="Updated OCR text...",
    ocr_hocr_path="/path/to/hocr.html",
    status="completed"
)

# Get all pages
pages = db_manager.get_all_pages(limit=100, offset=0)

# Search pages by various criteria
pages = db_manager.search_pages_by_publication("Times")
pages = db_manager.search_pages_by_date("1900-01-01", "1900-12-31")
pages = db_manager.search_pages_by_status("completed")
pages = db_manager.search_pages_by_text("historical event")
```

#### Article Segments Methods

```python
# Add a new article segment
segment_id = db_manager.add_article_segment(
    page_id=page_id,
    segment_type="article",
    content="Article text goes here...",
    position_data='{"x": 100, "y": 100, "width": 300, "height": 500}',
    confidence=0.95,
    image_path="/path/to/segment.jpg"
)

# Get segment by ID
segment = db_manager.get_segment_by_id(segment_id)

# Get segments for a page
segments = db_manager.get_segments_for_page(page_id)

# Update segment
db_manager.update_segment(
    segment_id=segment_id,
    content="Updated content...",
    status="reviewed"
)
```

#### Newspaper Articles Methods

```python
# Add a newspaper article (composed of segments)
article_id = db_manager.add_newspaper_article(
    page_id=page_id,
    title="Important News",
    content="Full article content...",
    article_type="news",
    segment_ids='["segment1", "segment2"]',  # JSON string of segment IDs
    metadata={"author": "John Smith"}
)

# Get article by ID
article = db_manager.get_article_by_id(article_id)

# Get articles for a page
articles = db_manager.get_articles_for_page(page_id)
```

#### Processing Queue Methods

```python
# Add to processing queue
queue_id = db_manager.add_to_processing_queue(
    page_id="page123",
    operation="ocr",
    parameters='{"language": "eng"}',  # Optional JSON string of parameters
    priority=1  # Lower numbers = higher priority
)

# Get pending queue items
pending_items = db_manager.get_pending_processing_queue_items()

# Update queue item status
db_manager.update_processing_queue_item(
    item_id=queue_id,
    status="completed",
    result='{"success": true}',  # Optional result data
    last_error=""  # Optional error message
)
```

### FileManager

Handles file organization and storage for the repository system.

#### Initialization

```python
file_manager = FileManager(base_directory)
```

Parameters:
- `base_directory` (str): Base directory for all repository files

#### Methods

```python
# Get paths for different file types
original_dir = file_manager.get_original_directory("chroniclingamerica")
ocr_dir = file_manager.get_ocr_directory("text")
hocr_dir = file_manager.get_ocr_directory("hocr")
processed_dir = file_manager.get_processed_directory("chroniclingamerica")
article_clips_dir = file_manager.get_article_clips_directory()

# Save files
file_manager.save_file(source_path, dest_path)
file_manager.save_text_file(dest_path, text_content)

# Generate standardized paths
page_path = file_manager.generate_page_path(
    directory=original_dir,
    source_type="chroniclingamerica",
    date="1900-01-01",
    page_number=1,
    extension="jpg"
)

ocr_path = file_manager.generate_ocr_path(
    directory=ocr_dir,
    source_type="chroniclingamerica",
    date="1900-01-01",
    page_number=1,
    extension="txt"
)

segment_path = file_manager.generate_article_segment_path(
    directory=article_clips_dir,
    source_type="chroniclingamerica",
    date="1900-01-01",
    segment_id="segment123",
    extension="jpg"
)
```

### OCRProcessor

Performs OCR and layout analysis on newspaper pages.

#### Initialization

```python
ocr_processor = OCRProcessor(
    tesseract_path=None,  # Optional path to Tesseract executable
    languages=["eng"]  # Languages to use for OCR
)
```

#### Methods

```python
# Process a page with OCR
ocr_result = ocr_processor.process_page(
    image_path,
    languages=["eng"],  # Optional, overrides initialization languages
    config="--psm 1"  # Optional Tesseract configuration
)

# OCR result contains:
# - text: Extracted text content
# - hocr: HOCR XML content
# - hocr_path: Path to HOCR file (if saved)
# - confidence: Overall OCR confidence score

# Analyze layout from HOCR data
segments = ocr_processor.analyze_layout_from_hocr(
    hocr_path,
    image_path=None  # Optional, used to extract images for segments
)

# Analyze layout and extract segments in one step
segments = ocr_processor.analyze_layout_and_extract_segments(
    image_path,
    min_segment_size=100,  # Minimum segment size in pixels
    min_confidence=0.5  # Minimum confidence for segments
)

# Each segment contains:
# - segment_type: Type of segment (article, header, image, etc.)
# - position: Dictionary with x, y, width, height
# - text: Extracted text
# - confidence: Confidence score
# - image_path: Path to segment image (if saved)
```

### MainDBConnector

Facilitates integration with the main Nova database.

#### Initialization

```python
connector = MainDBConnector(
    repo_db_path,  # Path to repository database
    main_db_path  # Path to main Nova database
)
```

#### Methods

```python
# Import article segment as event
event_id = connector.import_segment_as_event(
    segment_id,
    title=None,  # Optional, extracted from segment if None
    date=None,  # Optional, extracted from parent page if None
    content=None,  # Optional, extracted from segment if None
    source_id=None  # Optional, extracted from parent page if None
)

# Find potential duplicates in main database
duplicates = connector.find_potential_duplicates(
    content,
    title=None,  # Optional
    date=None,  # Optional
    similarity_threshold=0.8  # Minimum similarity score (0-1)
)

# Batch import segments
results = connector.batch_import_segments(
    segment_ids,
    check_duplicates=True,  # Whether to check for duplicates
    create_links=True  # Whether to create bidirectional links
)

# Sync changes between databases
connector.sync_from_main_to_repo(event_id)
connector.sync_from_repo_to_main(segment_id)
```

### BackgroundProcessingService

Manages asynchronous processing tasks in a separate thread.

#### Initialization

```python
service = BackgroundProcessingService(
    db_path,  # Path to repository database
    base_directory,  # Base directory for file storage
    max_retries=3,  # Maximum number of retry attempts
    retry_delay=300,  # Delay in seconds before retrying failed tasks
    poll_interval=5,  # Interval in seconds to poll for new tasks
    max_concurrent_tasks=2  # Maximum number of tasks to process concurrently
)
```

#### Methods

```python
# Start the background service
service.start()

# Stop the background service
service.stop()

# Pause/resume the service
service.pause()
service.resume()

# Add a task to the processing queue
task_id = service.add_task(
    page_id="page123",
    operation="ocr",
    parameters={"language": "eng"},
    priority=1
)

# Get queue status
status = service.get_queue_status()
# Returns: running, paused, queue_size, in_progress, stats

# Get task status
task_status = service.get_task_status(task_id)

# Cancel a pending task
success = service.cancel_task(task_id)

# Register a progress callback function
service.register_progress_callback(callback_function)
```

### SearchEngine

Provides full-text search capabilities across both repositories.

#### Initialization

```python
search_engine = SearchEngine(
    index_path,  # Path to the search index
    newspaper_db_path,  # Path to newspaper repository database
    main_db_path  # Path to main Nova database
)
```

#### Methods

```python
# Initialize search options
from newspaper_repository.search_engine import SearchOptions, SearchSource

options = SearchOptions(
    query="historical event",
    source=SearchSource.ALL,  # ALL, MAIN, or NEWSPAPER
    limit=20,
    offset=0,
    min_score=0.0,
    fuzzy=True,
    fuzzy_threshold=70,  # Minimum fuzz ratio (0-100)
    facets=["source", "date", "type"],
    filters={"type": "newspaper_article"},
    date_start=date(1900, 1, 1),
    date_end=date(1910, 12, 31)
)

# Perform search
response = search_engine.search(options)

# The response contains:
# - query: Original query string
# - results: List of SearchResult objects
# - total_count: Total number of matching results
# - facets: Dictionary of facet name -> SearchFacet objects
# - execution_time_ms: Search execution time in milliseconds

# Reindex content
search_engine.reindex_newspaper_repository()
search_engine.reindex_main_database()
search_engine.reindex_all()
```

### ChroniclingAmericaClient

Client for interacting with the Library of Congress Chronicling America API.

#### Initialization

```python
from api.chronicling_america import ChroniclingAmericaClient

client = ChroniclingAmericaClient(
    output_directory="/path/to/downloads",
    request_delay=0.5  # Seconds between API requests
)
```

#### Methods

```python
# Search for newspapers
newspapers = client.search_newspapers(
    state="Washington",
    county=None,
    title=None,
    year=None
)

# Search for newspaper pages
pages, pagination = client.search_pages(
    keywords="gold rush",
    lccn=None,  # Library of Congress Control Number
    state="Washington",
    date_start="1900-01-01",
    date_end="1900-12-31",
    page=1,
    items_per_page=20
)

# Download page content
download_results = client.download_page_content(
    page_metadata,  # PageMetadata object from search results
    formats=["pdf", "jp2", "ocr", "json"],
    save_files=True
)

# Search and download in one operation
results = client.search_and_download(
    keywords="gold rush",
    lccn=None,
    state="Washington",
    date_start="1900-01-01",
    date_end="1900-12-31",
    max_pages=2,
    formats=["pdf", "ocr"]
)

# Integrate with repository
added_page_ids = client.integrate_with_repository(
    download_results,
    repository_manager  # Instance of RepositoryDatabaseManager
)
```

## Usage Examples

### Setting Up the Repository

```python
from newspaper_repository.repository_database import RepositoryDatabaseManager
from newspaper_repository.file_manager import FileManager
from newspaper_repository.background_service import BackgroundProcessingService
from newspaper_repository.search_engine import SearchEngine

# Paths
repo_dir = "/path/to/repository"
db_path = f"{repo_dir}/repository.db"
index_path = f"{repo_dir}/search_index.db"
main_db_path = "/path/to/nova.db"

# Initialize components
db_manager = RepositoryDatabaseManager(db_path)
file_manager = FileManager(repo_dir)
search_engine = SearchEngine(index_path, db_path, main_db_path)

# Start background processing service
service = BackgroundProcessingService(db_path, repo_dir)
service.start()

print("Repository system initialized and ready")
```

### Importing from ChroniclingAmerica API

```python
from api.chronicling_america import ChroniclingAmericaClient
from newspaper_repository.repository_database import RepositoryDatabaseManager

# Initialize components
client = ChroniclingAmericaClient(output_directory="/path/to/downloads")
db_manager = RepositoryDatabaseManager("/path/to/repository.db")

# Search for newspaper pages
pages, pagination = client.search_pages(
    keywords="gold rush",
    state="Washington",
    date_start="1900-01-01",
    date_end="1900-12-31"
)

print(f"Found {pagination['total_items']} matching pages")

# Download the first 10 pages (or fewer if less than 10 results)
download_count = min(10, len(pages))
batch = pages[:download_count]

results = client.batch_download_pages(
    batch,
    formats=["pdf", "ocr", "jp2"]
)

print(f"Downloaded {len(results)} pages")

# Import into repository
page_ids = client.integrate_with_repository(results, db_manager)

print(f"Imported {len(page_ids)} pages into repository")

# Queue pages for processing
for page_id in page_ids:
    db_manager.add_to_processing_queue(page_id, "segment")

print("Pages queued for processing")
```

### Using the Background Service for OCR Processing

```python
from newspaper_repository.repository_database import RepositoryDatabaseManager
from newspaper_repository.background_service import BackgroundProcessingService

# Initialize components
db_path = "/path/to/repository.db"
repo_dir = "/path/to/repository"

db_manager = RepositoryDatabaseManager(db_path)
service = BackgroundProcessingService(db_path, repo_dir)

# Define progress callback
def progress_callback(update):
    update_type = update["type"]
    data = update["data"]
    
    if update_type == "task_started":
        print(f"Started processing {data['page_id']} - {data['operation']}")
    elif update_type == "task_completed":
        print(f"Completed processing {data['page_id']} - {data['operation']}")
    elif update_type == "task_failed":
        print(f"Failed processing {data['page_id']} - {data['error']}")
    elif update_type == "task_progress":
        print(f"Progress: {int(data['progress']*100)}% - {data['message']}")

# Register callback
service.register_progress_callback(progress_callback)

# Start the service
service.start()

# Get pending OCR tasks
pending_tasks = db_manager.get_pending_processing_queue_items()
print(f"Found {len(pending_tasks)} pending tasks")

# Add a new OCR task
page_id = "page123"  # Replace with actual page ID
task_id = service.add_task(
    page_id=page_id,
    operation="ocr",
    parameters={"language": "eng"},
    priority=1
)

print(f"Added task {task_id} to queue")

# Check status periodically
import time
for _ in range(10):
    status = service.get_queue_status()
    print(f"Queue status: {status['queue_size']} pending, {status['in_progress']} in progress")
    time.sleep(5)

# Stop the service when done
service.stop()
print("Service stopped")
```

### Searching the Repository

```python
from newspaper_repository.search_engine import SearchEngine, SearchOptions, SearchSource
from datetime import date

# Initialize search engine
search_engine = SearchEngine(
    index_path="/path/to/search_index.db",
    newspaper_db_path="/path/to/repository.db",
    main_db_path="/path/to/nova.db"
)

# Basic search
options = SearchOptions(
    query="gold rush",
    source=SearchSource.ALL,
    limit=20,
    offset=0
)

response = search_engine.search(options)

print(f"Found {response.total_count} results in {response.execution_time_ms}ms")
for i, result in enumerate(response.results):
    print(f"{i+1}. {result.title} ({result.date}) - Score: {result.score:.2f}")
    print(f"   {result.highlights[0] if result.highlights else ''}")

# Advanced search with filters and facets
advanced_options = SearchOptions(
    query="president AND election",
    source=SearchSource.NEWSPAPER,
    limit=10,
    offset=0,
    fuzzy=True,
    fuzzy_threshold=80,
    facets=["source", "date", "type"],
    filters={"type": "newspaper_article"},
    date_start=date(1900, 1, 1),
    date_end=date(1910, 12, 31)
)

response = search_engine.search(advanced_options)

print(f"Found {response.total_count} results in {response.execution_time_ms}ms")

# Print facets
print("\nFacets:")
for facet_name, facet in response.facets.items():
    print(f"{facet_name}:")
    for value, count in facet.values.items():
        print(f"  {value}: {count}")
```

### Importing Articles to Main Database

```python
from newspaper_repository.repository_database import RepositoryDatabaseManager
from newspaper_repository.main_db_connector import MainDBConnector

# Initialize components
repo_db_path = "/path/to/repository.db"
main_db_path = "/path/to/nova.db"

db_manager = RepositoryDatabaseManager(repo_db_path)
connector = MainDBConnector(repo_db_path, main_db_path)

# Get article segments that mention a specific topic
segments = db_manager.search_segments_by_text("election")
print(f"Found {len(segments)} segments mentioning 'election'")

# Check for duplicates before importing
segment_id = segments[0]["segment_id"]
segment = db_manager.get_segment_by_id(segment_id)
page = db_manager.get_newspaper_page(segment["page_id"])

duplicates = connector.find_potential_duplicates(
    segment["content"],
    title=None,
    date=page["publication_date"]
)

if duplicates:
    print(f"Found {len(duplicates)} potential duplicates")
    for dup in duplicates:
        print(f"ID: {dup['id']}, Title: {dup['title']}, Score: {dup['score']}")
else:
    # Import segment as event
    event_id = connector.import_segment_as_event(segment_id)
    print(f"Imported as event ID: {event_id}")
```

### Using the Command-line Interface

```bash
# List all pages in the repository
python -m newspaper_repository.newspaper_cli list-pages

# Import a page from ChroniclingAmerica
python -m newspaper_repository.newspaper_cli import-chronicling --query="gold rush" --state="Washington" --date-start="1900-01-01" --date-end="1900-12-31" --limit=5

# Process a page with OCR
python -m newspaper_repository.newspaper_cli process-ocr --id=page123

# Extract article segments from a page
python -m newspaper_repository.newspaper_cli extract-segments --id=page123

# Search the repository
python -m newspaper_repository.newspaper_cli search --query="gold rush" --source=all --limit=20

# Import an article to the main database
python -m newspaper_repository.newspaper_cli import-to-main --id=segment123

# Start the background processing service
python -m newspaper_repository.newspaper_cli start-service

# Stop the background processing service
python -m newspaper_repository.newspaper_cli stop-service
```

## Integration with Nova

The newspaper repository system integrates with the main Nova database in several ways:

### Integration Points

1. **MainDBConnector**: The primary integration component that handles the transfer of data between the newspaper repository and the main Nova database.

2. **Data Mapping**: 
   - Article segments map to events in the main database
   - Newspaper pages map to sources
   - OCR text provides the content for events
   - Metadata is preserved and transferred

3. **Database Schema Compatibility**:
   - The MainDBConnector handles the translation between different schema structures
   - Identifiers from both systems are preserved to maintain linkage
   - Changes in either system can be synced to the other

4. **UI Integration**:
   - The repository tab in the Nova UI provides a seamless interface
   - Search results can include content from both systems
   - Events can be created from newspaper articles directly in the UI

### Data Flow

#### Repository to Nova

1. Article segments from the repository can be promoted to events in the main database:
   - Text content becomes the event description
   - Publication date becomes the event date
   - Newspaper title and metadata are added to the event source
   - Images are linked or copied to the main database

2. Newspaper pages become sources in the main database:
   - Publication information is preserved
   - Links to original files are maintained
   - OCR text is included in the source content

#### Nova to Repository

1. Changes to events in the main database can be synced back to source article segments:
   - Updated text and metadata flow back to the repository
   - Relationships between entities and events can enhance repository metadata
   - Links between articles on related topics can be established

### Technical Requirements

1. **Database Access**:
   - Both databases must be accessible from the same system
   - The MainDBConnector needs read/write permissions to both databases

2. **File System Access**:
   - Both systems need access to shared file storage
   - Image paths must be accessible from both contexts

3. **Security Considerations**:
   - Permission management between systems must be coordinated
   - Data integrity checks ensure consistent state between systems

4. **Performance Considerations**:
   - Large data transfers should be batched
   - Syncing operations should be scheduled during low-usage periods
   - Duplicate detection should use efficient algorithms

## Troubleshooting

### Database Issues

#### "no such table" Error

**Problem**: Attempting to access a table that doesn't exist.

**Solutions**:
- Ensure database initialization has been run
- Check for database schema changes between versions
- Verify database path is correct
- Run the database creation script again with `force=True` to rebuild missing tables:
  ```python
  db_manager = RepositoryDatabaseManager(db_path, force_create=True)
  ```

#### Foreign Key Constraint Failed

**Problem**: Attempting to add or update records with invalid foreign keys.

**Solutions**:
- Ensure referenced records exist before creating dependent records
- Check for cascading delete settings in schema
- Verify IDs are correctly formatted
- Use transactions to ensure data consistency:
  ```python
  db_manager.conn.execute("BEGIN TRANSACTION")
  try:
      # Perform operations
      db_manager.conn.execute("COMMIT")
  except Exception as e:
      db_manager.conn.execute("ROLLBACK")
      print(f"Transaction failed: {e}")
  ```

#### Database Locked

**Problem**: Multiple processes trying to write to the database simultaneously.

**Solutions**:
- Implement proper connection pooling
- Reduce concurrent write operations
- Set appropriate timeout values:
  ```python
  db_manager.conn.execute("PRAGMA busy_timeout = 30000")  # 30 seconds
  ```
- Consider using a more robust database system for high-concurrency environments

### OCR Issues

#### Poor OCR Quality

**Problem**: Text recognition is inaccurate or incomplete.

**Solutions**:
- Pre-process images to improve contrast and remove noise:
  ```python
  import cv2
  import numpy as np
  
  # Load image
  image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
  
  # Enhance contrast
  clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
  image = clahe.apply(image)
  
  # Denoise
  image = cv2.GaussianBlur(image, (3, 3), 0)
  
  # Binarize
  _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
  
  # Save or use for OCR
  cv2.imwrite(enhanced_path, image)
  ```
- Try different Tesseract configurations:
  ```python
  # For dense text with multiple columns
  ocr_text = pytesseract.image_to_string(image, config='--psm 3 --oem 1')
  
  # For a single column of text
  ocr_text = pytesseract.image_to_string(image, config='--psm 6 --oem 3')
  
  # For a single word
  ocr_text = pytesseract.image_to_string(image, config='--psm 10 --oem 3')
  ```
- Ensure correct language is set:
  ```python
  # For English
  ocr_text = pytesseract.image_to_string(image, lang='eng')
  
  # For multiple languages
  ocr_text = pytesseract.image_to_string(image, lang='eng+fra+deu')
  ```
- Increase image resolution (300+ DPI recommended):
  ```python
  from PIL import Image
  
  # Resize to higher resolution
  pil_image = Image.open(image_path)
  width, height = pil_image.size
  resized = pil_image.resize((width*2, height*2), Image.LANCZOS)
  resized.save(resized_path)
  ```

#### Tesseract Not Found

**Problem**: System can't locate Tesseract executable.

**Solutions**:
- Set the path explicitly:
  ```python
  import pytesseract
  
  # Windows
  pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
  
  # Linux/macOS
  pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'
  ```
- Add Tesseract to system PATH
- Check Tesseract installation:
  ```bash
  # Check version
  tesseract --version
  
  # List available languages
  tesseract --list-langs
  ```

### File Management Issues

#### File Not Found

**Problem**: System can't locate a file at the expected path.

**Solutions**:
- Use absolute paths instead of relative paths
- Verify file paths stored in the database are correct
- Check file system permissions
- Implement path validation:
  ```python
  import os
  
  def validate_path(path):
      if not os.path.exists(path):
          # Try to find the file elsewhere
          parent_dir = os.path.dirname(path)
          filename = os.path.basename(path)
          
          # Search in the parent directory
          if os.path.exists(parent_dir):
              for root, _, files in os.walk(parent_dir):
                  if filename in files:
                      return os.path.join(root, filename)
              
      return path if os.path.exists(path) else None
  ```

#### Insufficient Disk Space

**Problem**: Running out of disk space during image processing.

**Solutions**:
- Implement disk space checking before operations:
  ```python
  import shutil
  
  def check_disk_space(path, required_mb=100):
      """Check if enough disk space is available."""
      stats = shutil.disk_usage(path)
      available_mb = stats.free / (1024 * 1024)
      
      if available_mb < required_mb:
          print(f"Warning: Low disk space! {available_mb:.2f}MB available")
          return False
      return True
  ```
- Use compression for large files:
  ```python
  import gzip
  
  # Compress text files
  with open(original_path, 'r') as f_in:
      with gzip.open(compressed_path, 'wt') as f_out:
          f_out.write(f_in.read())
  ```
- Implement cleanup procedures for temporary files:
  ```python
  import tempfile
  import os
  import glob
  
  # Clean up temporary files older than 1 day
  temp_dir = tempfile.gettempdir()
  temp_files = glob.glob(os.path.join(temp_dir, "newspaper_repo_*"))
  
  for file in temp_files:
      file_age = time.time() - os.path.getmtime(file)
      if file_age > 86400:  # 24 hours
          try:
              os.remove(file)
              print(f"Removed old temp file: {file}")
          except Exception as e:
              print(f"Could not remove {file}: {e}")
  ```

### Search Engine Issues

#### Slow Search Performance

**Problem**: Searches take too long to complete.

**Solutions**:
- Optimize the search index:
  ```python
  search_engine.indexer.optimize_index()
  ```
- Use more specific queries to narrow results
- Implement query caching:
  ```python
  import functools
  
  # Cache frequent searches
  @functools.lru_cache(maxsize=100)
  def cached_search(query_string, source=None, limit=20):
      options = SearchOptions(query=query_string, source=source, limit=limit)
      return search_engine.search(options)
  ```
- Add appropriate indexes to the database:
  ```python
  db_manager.conn.execute("CREATE INDEX IF NOT EXISTS idx_content ON documents(content)")
  ```

#### No Results Found

**Problem**: Search queries return no results even when matching content exists.

**Solutions**:
- Enable fuzzy matching:
  ```python
  options = SearchOptions(query="historical", fuzzy=True, fuzzy_threshold=60)
  ```
- Check indexing status:
  ```python
  # Reindex specific content
  search_engine.indexer.index_newspaper_page(page_id, page_data)
  
  # Rebuild the entire index
  search_engine.reindex_all()
  ```
- Broaden search terms:
  ```python
  # Use OR instead of AND
  options = SearchOptions(query="historical OR newspapers")
  ```
- Check for stemming/normalization issues:
  ```python
  # Search for word variations
  options = SearchOptions(query="history historical historian")
  ```

### Background Service Issues

#### Tasks Stuck in Queue

**Problem**: Tasks remain in the queue and are not being processed.

**Solutions**:
- Check service status:
  ```python
  status = service.get_queue_status()
  print(f"Service running: {status['running']}")
  print(f"Service paused: {status['paused']}")
  ```
- Restart the service:
  ```python
  service.stop()
  service.start()
  ```
- Check for errors in running tasks:
  ```python
  # Reset stuck tasks back to pending
  db_manager.conn.execute("""
      UPDATE processing_queue 
      SET status = 'pending', last_error = 'Reset from stuck state'
      WHERE status = 'in_progress' AND started_at < datetime('now', '-1 hour')
  """)
  db_manager.conn.commit()
  ```
- Increase task timeout:
  ```python
  service.task_timeout = 7200  # 2 hours in seconds
  ```

#### High Failure Rate

**Problem**: Many tasks are failing and being retried repeatedly.

**Solutions**:
- Check error messages:
  ```python
  # Get failed tasks with errors
  cursor.execute("SELECT item_id, last_error FROM processing_queue WHERE status = 'failed'")
  errors = cursor.fetchall()
  for item_id, error in errors:
      print(f"Task {item_id} failed: {error}")
  ```
- Increase retry delay for resource issues:
  ```python
  service.retry_delay = 600  # 10 minutes
  ```
- Adjust max retries for different operations:
  ```python
  # More retries for external API calls
  if operation == "api_call":
      task.max_retries = 5
  else:
      task.max_retries = 3
  ```
- Implement specific error handling for common failures:
  ```python
  try:
      # Operation
  except requests.exceptions.ConnectionError:
      # Network issue, retry later
  except PermissionError:
      # Permission issue, notify admin
  except Exception as e:
      # General error
  ```

## Performance Optimization

### Database Optimization

1. **SQLite Optimizations**:

   ```python
   # Setup optimizations
   db_manager.conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
   db_manager.conn.execute("PRAGMA synchronous = NORMAL")  # Less durability, more speed
   db_manager.conn.execute("PRAGMA cache_size = 10000")  # Larger cache (in pages)
   db_manager.conn.execute("PRAGMA temp_store = MEMORY")  # Store temp tables in memory
   ```

2. **Indexing Key Fields**:

   ```python
   # Create indexes for frequently queried fields
   db_manager.conn.execute("CREATE INDEX IF NOT EXISTS idx_newspaper_pages_date ON newspaper_pages(publication_date)")
   db_manager.conn.execute("CREATE INDEX IF NOT EXISTS idx_newspaper_pages_status ON newspaper_pages(status)")
   db_manager.conn.execute("CREATE INDEX IF NOT EXISTS idx_article_segments_page_id ON article_segments(page_id)")
   db_manager.conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status)")
   db_manager.conn.commit()
   ```

3. **Batch Operations**:

   ```python
   # Use transactions for multiple operations
   db_manager.conn.execute("BEGIN TRANSACTION")
   try:
       for page in pages:
           # Multiple inserts or updates
           db_manager.add_newspaper_page(...)
       db_manager.conn.execute("COMMIT")
   except Exception as e:
       db_manager.conn.execute("ROLLBACK")
       print(f"Batch operation failed: {e}")
   ```

4. **Connection Pooling**:

   ```python
   # Simple connection pool
   class ConnectionPool:
       def __init__(self, db_path, max_connections=5):
           self.db_path = db_path
           self.connections = []
           self.max_connections = max_connections
           self.lock = threading.Lock()
       
       def get_connection(self):
           with self.lock:
               if not self.connections:
                   # Create new connection if pool is empty
                   conn = sqlite3.connect(self.db_path)
                   return conn
               return self.connections.pop()
       
       def release_connection(self, conn):
           with self.lock:
               if len(self.connections) < self.max_connections:
                   self.connections.append(conn)
               else:
                   conn.close()
   ```

### OCR Performance

1. **Image Preprocessing**:

   ```python
   # Optimize images before OCR
   def preprocess_for_ocr(image_path):
       # Load image
       image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
       
       # Check image resolution
       height, width = image.shape
       dpi = 300  # Target DPI
       
       # Resize if necessary
       if width < 2000 or height < 2000:
           scale = dpi / 72
           image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
       
       # Enhance contrast
       image = cv2.equalizeHist(image)
       
       # Denoise
       image = cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
       
       # Binarize
       _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
       
       # Save processed image
       processed_path = image_path.replace('.jpg', '_processed.jpg')
       cv2.imwrite(processed_path, image)
       
       return processed_path
   ```

2. **Parallel Processing**:

   ```python
   import concurrent.futures
   
   def process_pages_in_parallel(page_ids, max_workers=4):
       results = []
       
       with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
           # Submit processing tasks
           future_to_page = {
               executor.submit(ocr_processor.process_page, db_manager.get_page_by_id(page_id).image_path): page_id
               for page_id in page_ids
           }
           
           # Collect results as they complete
           for future in concurrent.futures.as_completed(future_to_page):
               page_id = future_to_page[future]
               try:
                   ocr_result = future.result()
                   results.append((page_id, ocr_result))
               except Exception as e:
                   print(f"Processing page {page_id} failed: {e}")
       
       return results
   ```

3. **Tesseract Optimizations**:

   ```python
   # Fast mode with limited accuracy (for initial processing)
   ocr_text = pytesseract.image_to_string(
       image, 
       config='--psm 3 --oem 1 -l eng --dpi 300'
   )
   
   # High accuracy mode (for important content)
   ocr_text = pytesseract.image_to_string(
       image, 
       config='--psm 3 --oem 3 -l eng --dpi 300'
   )
   ```

4. **Page Segmentation**:

   ```python
   # Split large pages into segments for parallel processing
   def split_page_for_processing(image_path, max_segments=4):
       image = cv2.imread(image_path)
       height, width = image.shape[:2]
       
       segments = []
       if height > width:  # Portrait
           segment_height = height // max_segments
           for i in range(max_segments):
               y_start = i * segment_height
               y_end = min((i + 1) * segment_height, height)
               segment = image[y_start:y_end, 0:width]
               
               # Save segment
               segment_path = f"{image_path}_segment_{i}.jpg"
               cv2.imwrite(segment_path, segment)
               segments.append(segment_path)
       else:  # Landscape
           segment_width = width // max_segments
           for i in range(max_segments):
               x_start = i * segment_width
               x_end = min((i + 1) * segment_width, width)
               segment = image[0:height, x_start:x_end]
               
               # Save segment
               segment_path = f"{image_path}_segment_{i}.jpg"
               cv2.imwrite(segment_path, segment)
               segments.append(segment_path)
       
       return segments
   ```

### Search Engine Optimization

1. **Incremental Indexing**:

   ```python
   # Only reindex changed content
   def incremental_reindex(last_reindex_time):
       # Get pages modified since last reindex
       db_manager.conn.execute("""
           SELECT page_id FROM newspaper_pages 
           WHERE modified_at > ?
       """, (last_reindex_time,))
       page_ids = [row[0] for row in cursor.fetchall()]
       
       # Reindex modified pages
       for page_id in page_ids:
           page_data = db_manager.get_newspaper_page(page_id)
           search_engine.indexer.index_newspaper_page(page_id, page_data)
       
       # Update last reindex time
       current_time = datetime.now().isoformat()
       return current_time
   ```

2. **Query Optimization**:

   ```python
   # Preprocess user queries
   def optimize_query(query_string):
       # Remove common words that aren't stop words but add noise
       noise_words = ["the", "a", "an", "in", "on", "at", "by", "to", "for"]
       words = query_string.split()
       filtered_words = [w for w in words if w.lower() not in noise_words]
       
       # Add synonyms for important terms
       synonyms = {
           "newspaper": ["paper", "gazette", "journal", "times", "post"],
           "president": ["executive", "chief", "commander"],
           "war": ["conflict", "battle", "fighting"]
       }
       
       expanded_words = []
       for word in filtered_words:
           expanded_words.append(word)
           if word.lower() in synonyms:
               expanded_words.append("OR")
               expanded_words.extend([f'"{s}"' for s in synonyms[word.lower()]])
       
       return " ".join(expanded_words)
   ```

3. **Caching**:

   ```python
   # Simple cache for search results
   class SearchCache:
       def __init__(self, max_size=100, expiry_seconds=3600):
           self.cache = {}
           self.max_size = max_size
           self.expiry_seconds = expiry_seconds
       
       def get(self, query_hash):
           if query_hash in self.cache:
               result, timestamp = self.cache[query_hash]
               # Check if cache entry is expired
               if (time.time() - timestamp) < self.expiry_seconds:
                   return result
               # Remove expired entry
               del self.cache[query_hash]
           return None
       
       def put(self, query_hash, result):
           # Evict old entries if cache is full
           if len(self.cache) >= self.max_size:
               oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
               del self.cache[oldest_key]
           
           self.cache[query_hash] = (result, time.time())
   ```

### File System Optimization

1. **File Organization**:

   ```python
   # Shard files across directories to avoid too many files in one directory
   def get_sharded_path(base_dir, identifier):
       # Use the first few characters of the ID hash for sharding
       id_hash = hashlib.md5(identifier.encode()).hexdigest()
       shard1, shard2 = id_hash[:2], id_hash[2:4]
       
       # Create the sharded directory path
       sharded_dir = os.path.join(base_dir, shard1, shard2)
       os.makedirs(sharded_dir, exist_ok=True)
       
       return os.path.join(sharded_dir, identifier)
   ```

2. **Compression**:

   ```python
   # Compress large text files
   import gzip
   import json
   
   def save_compressed_json(data, file_path):
       """Save JSON data with compression."""
       with gzip.open(file_path, 'wt', encoding='utf-8') as f:
           json.dump(data, f)
   
   def load_compressed_json(file_path):
       """Load compressed JSON data."""
       with gzip.open(file_path, 'rt', encoding='utf-8') as f:
           return json.load(f)
   ```

3. **Cleanup Procedures**:

   ```python
   # Clean up temporary and unused files
   def cleanup_orphaned_files(db_manager, file_manager):
       # Get all file paths in database
       db_paths = set()
       
       # Image paths from pages
       db_manager.conn.execute("SELECT image_path FROM newspaper_pages WHERE image_path IS NOT NULL")
       db_paths.update(row[0] for row in cursor.fetchall())
       
       # Image paths from segments
       db_manager.conn.execute("SELECT image_path FROM article_segments WHERE image_path IS NOT NULL")
       db_paths.update(row[0] for row in cursor.fetchall())
       
       # OCR paths
       db_manager.conn.execute("SELECT ocr_text_path, ocr_hocr_path FROM newspaper_pages WHERE ocr_text_path IS NOT NULL")
       for row in cursor.fetchall():
           db_paths.update([path for path in row if path])
       
       # Find all files in repository
       repo_files = set()
       for root, _, files in os.walk(file_manager.base_directory):
           for file in files:
               repo_files.add(os.path.join(root, file))
       
       # Find orphaned files (files that exist but aren't in the database)
       orphaned_files = repo_files - db_paths
       
       # Move to archive or delete
       archive_dir = os.path.join(file_manager.base_directory, "archived_files")
       os.makedirs(archive_dir, exist_ok=True)
       
       for file_path in orphaned_files:
           # Skip system files and directories
           if os.path.basename(file_path).startswith('.'):
               continue
               
           # Check file age
           file_age_days = (time.time() - os.path.getmtime(file_path)) / (24 * 3600)
           
           if file_age_days > 30:  # Older than 30 days
               try:
                   # Archive instead of delete
                   archive_path = os.path.join(
                       archive_dir, 
                       os.path.relpath(file_path, file_manager.base_directory)
                   )
                   os.makedirs(os.path.dirname(archive_path), exist_ok=True)
                   shutil.move(file_path, archive_path)
                   print(f"Archived orphaned file: {file_path}")
               except Exception as e:
                   print(f"Error archiving {file_path}: {e}")
   ```

### System Monitoring and Maintenance

1. **Performance Monitoring**:

   ```python
   # Monitor system performance
   def monitor_performance():
       start_time = time.time()
       total_pages = db_manager.count_pages()
       total_segments = db_manager.count_segments()
       
       # Database size
       db_size_mb = os.path.getsize(db_manager.db_path) / (1024 * 1024)
       
       # Check index fragmentation
       db_manager.conn.execute("PRAGMA integrity_check")
       integrity = cursor.fetchone()[0]
       
       # Check for long-running tasks
       db_manager.conn.execute("""
           SELECT COUNT(*) FROM processing_queue 
           WHERE status = 'in_progress' AND 
                 julianday('now') - julianday(started_at) > 0.0417  -- More than 1 hour
       """)
       stuck_tasks = cursor.fetchone()[0]
       
       return {
           "total_pages": total_pages,
           "total_segments": total_segments,
           "db_size_mb": db_size_mb,
           "integrity": integrity == "ok",
           "stuck_tasks": stuck_tasks,
           "check_time_ms": (time.time() - start_time) * 1000
       }
   ```

2. **Database Maintenance**:

   ```python
   # Perform routine database maintenance
   def maintain_database():
       # Analyze for query optimization
       db_manager.conn.execute("ANALYZE")
       
       # Vacuum to reclaim space and defragment
       db_manager.conn.execute("VACUUM")
       
       # Optimize indexes
       db_manager.conn.execute("REINDEX")
       
       # Integrity check
       db_manager.conn.execute("PRAGMA integrity_check")
       result = cursor.fetchone()[0]
       
       return result == "ok"
   ```

3. **Health Check API**:

   ```python
   # Health check endpoint for monitoring
   def health_check():
       try:
           # Check database connection
           db_manager.conn.execute("SELECT 1")
           db_ok = cursor.fetchone()[0] == 1
           
           # Check file system
           fs_ok = os.access(file_manager.base_directory, os.R_OK | os.W_OK)
           
           # Check search index
           index_ok = os.path.exists(search_engine.index_path)
           
           # Check background service
           service_status = service.get_queue_status()
           service_ok = service_status["running"]
           
           return {
               "status": "healthy" if (db_ok and fs_ok and index_ok and service_ok) else "degraded",
               "components": {
                   "database": "ok" if db_ok else "error",
                   "file_system": "ok" if fs_ok else "error",
                   "search_index": "ok" if index_ok else "error",
                   "background_service": "ok" if service_ok else "error"
               },
               "queue_size": service_status.get("queue_size", 0),
               "timestamp": datetime.now().isoformat()
           }
       except Exception as e:
           return {
               "status": "error",
               "error": str(e),
               "timestamp": datetime.now().isoformat()
           }
   ```

By following these optimization strategies, you can significantly improve the performance and reliability of the newspaper repository system, especially when dealing with large collections of historical newspapers.