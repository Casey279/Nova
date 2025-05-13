# API Clients for Nova Historical Database

This directory contains API clients for various external services used by the Nova Historical Database project.

## ImprovedChroniclingAmerica API Client

The `ImprovedChroniclingAmericaClient` in `chronicling_america_improved.py` provides enhanced search capabilities for the Library of Congress Chronicling America API, with a focus on accurate date filtering.

### Key Features

- **Multiple Search Strategies**: Uses several search approaches in sequence, prioritizing the most accurate ones:
  1. Web UI date format (MM/DD/YYYY) - matches the web UI's search format
  2. Direct URL construction - tries specific issue URLs
  3. Year + month as text - fallback approach
  4. Year-only search - last resort

- **Accurate Date Filtering**: Properly filters results to ensure they fall within the requested date range.

- **Pagination Support**: Can retrieve multiple pages of results for more comprehensive searches.

- **Robust Error Handling**: Includes retries, backoff, and comprehensive error reporting.

- **Special Newspaper Handling**: Includes special cases for newspapers like the Seattle Post-Intelligencer (which didn't publish on Mondays).

### Usage Example

```python
from api.chronicling_america_improved import ImprovedChroniclingAmericaClient

# Create client with output directory for downloads
client = ImprovedChroniclingAmericaClient("/path/to/downloads")

# Search for pages from Seattle Post-Intelligencer in April 1891
pages, pagination = client.search_pages(
    lccn="sn83045604",  # Seattle Post-Intelligencer
    date_start="1891-04-01",
    date_end="1891-04-30",
    max_pages=2  # Retrieve up to 2 pages of results (typically 20 items per page)
)

# Display pagination info
print(f"Found {len(pages)} pages out of {pagination['total_items']} total")
print(f"Page {pagination['current_page']} of {pagination['total_pages']}")

# Download content from the first page
if pages:
    result = client.download_page_content(
        pages[0],
        formats=["jp2", "pdf", "ocr"],  # Formats to download
        save_files=True  # Save to disk
    )
    print(f"Downloaded files: {list(result.keys())}")
```

### Implementation Details

The key innovation in this client is using the web UI's date format and query parameters to ensure accurate date filtering. By using the format `MM/DD/YYYY` with the correct `searchType` and `dateFilterType` parameters, we can accurately retrieve all pages from a specific date range.

```python
# Format as MM/DD/YYYY exactly as the web UI does
params['date1'] = date_obj.strftime("%m/%d/%Y")
params['date2'] = date_obj.strftime("%m/%d/%Y")
params['searchType'] = 'advanced'
params['dateFilterType'] = 'range'
```

This matches the parameter format used by the Chronicling America web interface, which returns more accurate results than the standard API parameters.

## Original ChroniclingAmerica API Client

The original ChroniclingAmerica API client also provides integration with the Library of Congress Chronicling America API to search and download historical newspaper content.

### Features

- Search for newspaper content by date, publication, location, and keywords
- Download newspaper pages in various formats (JP2, PDF, etc.)
- Extract metadata from API responses
- Support batch operations for downloading multiple pages
- Integration with the newspaper repository system
- Error handling and rate limiting

### Usage

Here's a simple example of how to use the client:

```python
from api.chronicling_america import ChroniclingAmericaClient

# Create a client instance
client = ChroniclingAmericaClient(output_directory="/path/to/downloads")

# Search for newspapers
newspapers = client.search_newspapers(state="Washington")

# Search for pages with specific criteria
pages, pagination = client.search_pages(
    keywords="gold rush",
    state="Washington",
    date_start="1900-01-01",
    date_end="1900-12-31"
)

# Download content for a specific page
if pages:
    download_results = client.download_page_content(
        pages[0],
        formats=["pdf", "jp2", "ocr"]
    )

# Search and download in one operation
results = client.search_and_download(
    keywords="railway accident",
    state="Washington",
    date_start="1900-01-01",
    date_end="1900-12-31",
    max_pages=2,
    formats=["pdf", "ocr"]
)

# Integrate with the newspaper repository
from newspaper_repository.repository_database import RepositoryDatabaseManager

repo_manager = RepositoryDatabaseManager("repository.db")
client.integrate_with_repository(results, repo_manager)
```

For more detailed examples, see the `examples` directory.

### Running Tests

To run the tests for the ChroniclingAmerica API client:

```bash
cd /path/to/Nova
python -m unittest src/api/test_chronicling_america.py
```