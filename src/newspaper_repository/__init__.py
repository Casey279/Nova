"""
Newspaper Repository Package

This package provides functionality for storing, organizing, and processing newspaper content.
It includes tools for OCR, article extraction, searching, and managing a repository of historical newspapers.
"""

# Import main components to make them available at the package level
try:
    from .repository_database import RepositoryDatabaseManager
    from .ocr_processor import OCRProcessor, ArticleSegment
    from .file_manager import FileManager
    from .background_service import BackgroundProcessingService, create_service_control_widget
    from .bulk_task import BulkTaskManager
    from .main_db_connector import MainDBConnector
except ImportError:
    # When imported as a standalone module, relative imports may fail
    import sys
    import os
    
    # Add the current directory to sys.path if needed
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    
    # Try absolute imports
    try:
        from repository_database import RepositoryDatabaseManager
        from ocr_processor import OCRProcessor, ArticleSegment
        from file_manager import FileManager
        from background_service import BackgroundProcessingService, create_service_control_widget
        from bulk_task import BulkTaskManager
        from main_db_connector import MainDBConnector
    except ImportError:
        # It's okay if some imports fail, as they might be imported individually later
        pass