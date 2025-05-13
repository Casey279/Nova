# Nova Historical Database

A comprehensive database system for historical research and documentation.

## Project Structure

- `src/` - Source code for the Nova application
  - `api/` - API clients for external services
  - `newspaper_repository/` - Module for managing newspaper content
  - `services/` - Core services for the application
  - `ui/` - User interface components
  - `utils/` - Utility functions and helpers

## Features

- Historical event management
- Character and entity tracking
- Location management
- Document intake and processing
- Newspaper repository for storing and analyzing historical newspapers
- External API integrations for research

## API Clients

The project includes API clients for various external services:

- **ChroniclingAmerica API** - Client for the Library of Congress Chronicling America API to search and download historical newspaper content. See `src/api/README.md` for details.

## Newspaper Repository

The newspaper repository provides functionality to:

- Store and organize newspaper content
- Perform OCR on newspaper pages
- Extract articles from pages
- Maintain a searchable repository
- Interface with the main Nova database

### Repository Components

- **Repository Browser**: Three-panel UI for navigating and viewing newspaper content
- **Repository Import**: Dialog for importing content from various sources
- **Repository Config**: Interface for configuring repository settings

### Testing the Repository Components

#### Windows

Run the batch file to test all components:
```
src\ui\test_repository_components.bat
```

Or run individual test scripts:
```
python src\ui\test_repository_import.py
python src\ui\test_repository_config.py
```

#### Linux/Mac

Run the shell script to test all components:
```
./src/ui/test_repository_components.sh
```

Or run individual test scripts:
```
python src/ui/test_repository_import.py
python src/ui/test_repository_config.py
```

See `src/newspaper_repository/README.md` for implementation details.

## Getting Started

1. Clone the repository
2. Install the required dependencies: `pip install -r requirements.txt`
3. Run the application: `python src/ui/main_ui.py`