"""
Bulk Task Manager for the Newspaper Repository System.

This module provides functionality for creating and running bulk operations with the 
newspaper repository system, such as batch downloads, OCR processing, and database tasks.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bulk_task')


class TaskType(Enum):
    """Types of bulk tasks."""
    DOWNLOAD = "download"
    OCR = "ocr"
    ENTITY_EXTRACTION = "entity_extraction"
    IMPORT = "import"
    EXPORT = "export"
    MAINTENANCE = "maintenance"
    CUSTOM = "custom"


class TaskStatus(Enum):
    """Status values for bulk tasks."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class BulkTaskError(Exception):
    """Exception raised for bulk task errors."""
    pass


class BulkTask:
    """
    Bulk task for running large-scale operations.
    
    This class represents a bulk operation that can be executed with the repository system,
    such as batch downloads, OCR processing, or database maintenance.
    """
    
    def __init__(
        self,
        task_type: Union[str, TaskType],
        parameters: Dict[str, Any],
        task_id: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        Initialize a bulk task.
        
        Args:
            task_type: Type of task to execute
            parameters: Parameters for the task
            task_id: Optional task identifier (generated if not provided)
            description: Optional task description
        """
        # Set task type
        if isinstance(task_type, str):
            try:
                self.task_type = TaskType(task_type.lower())
            except ValueError:
                self.task_type = TaskType.CUSTOM
                self.custom_type = task_type
        else:
            self.task_type = task_type
            self.custom_type = None
        
        # Set task properties
        self.parameters = parameters or {}
        self.task_id = task_id or f"{self.task_type.value}_{int(time.time())}"
        self.description = description or f"Bulk {self.task_type.value} task"
        
        # Initialize task state
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.total_items = 0
        self.processed_items = 0
        self.success_items = 0
        self.failed_items = 0
        self.start_time = None
        self.end_time = None
        self.error = None
        self.results = {}
        
        # Validate parameters
        self._validate_parameters()
        
        logger.info(f"Initialized bulk task {self.task_id}: {self.description}")
    
    def _validate_parameters(self) -> None:
        """
        Validate task parameters.
        
        Raises:
            BulkTaskError: If parameters are invalid
        """
        if self.task_type == TaskType.DOWNLOAD:
            if 'source' not in self.parameters:
                raise BulkTaskError("Download task requires 'source' parameter")
        
        elif self.task_type == TaskType.OCR:
            pass  # No strict requirements
        
        elif self.task_type == TaskType.ENTITY_EXTRACTION:
            pass  # No strict requirements
        
        elif self.task_type == TaskType.IMPORT:
            if 'source_type' not in self.parameters:
                raise BulkTaskError("Import task requires 'source_type' parameter")
            
            if 'source_path' not in self.parameters:
                raise BulkTaskError("Import task requires 'source_path' parameter")
        
        elif self.task_type == TaskType.EXPORT:
            if 'output_format' not in self.parameters:
                raise BulkTaskError("Export task requires 'output_format' parameter")
            
            if 'output_path' not in self.parameters:
                raise BulkTaskError("Export task requires 'output_path' parameter")
        
        elif self.task_type == TaskType.MAINTENANCE:
            if 'operations' not in self.parameters:
                raise BulkTaskError("Maintenance task requires 'operations' parameter")
    
    def execute(self, **components) -> Dict:
        """
        Execute the bulk task.
        
        Args:
            **components: Repository components needed for execution
                (e.g., db_manager, download_manager, ocr_processor)
            
        Returns:
            Dictionary with task results
            
        Raises:
            BulkTaskError: If execution fails
        """
        try:
            # Update state
            self.status = TaskStatus.RUNNING
            self.start_time = datetime.now()
            self.progress = 0.0
            self.error = None
            
            logger.info(f"Executing bulk task {self.task_id}")
            
            # Execute based on task type
            if self.task_type == TaskType.DOWNLOAD:
                result = self._execute_download(**components)
            elif self.task_type == TaskType.OCR:
                result = self._execute_ocr(**components)
            elif self.task_type == TaskType.ENTITY_EXTRACTION:
                result = self._execute_entity_extraction(**components)
            elif self.task_type == TaskType.IMPORT:
                result = self._execute_import(**components)
            elif self.task_type == TaskType.EXPORT:
                result = self._execute_export(**components)
            elif self.task_type == TaskType.MAINTENANCE:
                result = self._execute_maintenance(**components)
            elif self.task_type == TaskType.CUSTOM:
                if 'execute_func' not in components:
                    raise BulkTaskError("Custom task requires 'execute_func' parameter")
                result = components['execute_func'](self, **components)
            else:
                raise BulkTaskError(f"Unsupported task type: {self.task_type}")
            
            # Update final state
            self.status = TaskStatus.COMPLETED
            self.end_time = datetime.now()
            self.progress = 100.0
            self.results = result
            
            logger.info(
                f"Completed bulk task {self.task_id}: processed {self.processed_items} items "
                f"({self.success_items} succeeded, {self.failed_items} failed)"
            )
            
            return result
            
        except Exception as e:
            # Update error state
            self.status = TaskStatus.FAILED
            self.end_time = datetime.now()
            self.error = str(e)
            
            logger.error(f"Failed bulk task {self.task_id}: {str(e)}")
            
            raise BulkTaskError(f"Failed to execute bulk task: {str(e)}")
    
    def _execute_download(self, **components) -> Dict:
        """
        Execute a download task.
        
        Args:
            **components: Repository components
            
        Returns:
            Dictionary with download results
        """
        if 'download_manager' not in components:
            raise BulkTaskError("Download task requires 'download_manager' component")
        
        download_manager = components['download_manager']
        
        # Get parameters
        source = self.parameters['source']
        publications = self.parameters.get('publications', [])
        if isinstance(publications, str):
            publications = [p.strip() for p in publications.split(',')]
        
        date_range = self.parameters.get('date_range', {})
        start_date = None
        end_date = None
        
        if isinstance(date_range, dict):
            start_date_str = date_range.get('start')
            end_date_str = date_range.get('end')
            
            if start_date_str:
                if start_date_str == 'latest_month':
                    start_date = (datetime.now() - timedelta(days=30)).date()
                else:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            
            if end_date_str:
                if end_date_str == 'today':
                    end_date = datetime.now().date()
                else:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        
        max_items = self.parameters.get('max_items', 0)
        location = self.parameters.get('location')
        max_concurrent = self.parameters.get('max_concurrent', 3)
        
        # Prepare download tasks
        tasks = []
        
        if not publications:
            # Single download task
            task_id = download_manager.add_task(
                downloader=source,
                start_date=start_date,
                end_date=end_date,
                location=location,
                max_items=max_items,
                priority=1
            )
            tasks.append(task_id)
        else:
            # Multiple download tasks (one per publication)
            for pub_id in publications:
                task_id = download_manager.add_task(
                    downloader=source,
                    publication_id=pub_id,
                    start_date=start_date,
                    end_date=end_date,
                    location=location,
                    max_items=max_items,
                    priority=1
                )
                tasks.append(task_id)
        
        self.total_items = len(tasks)
        
        # Start download manager and set worker count
        download_manager.max_workers = max_concurrent
        download_manager.start()
        
        try:
            # Monitor progress
            completed_tasks = 0
            
            while completed_tasks < len(tasks):
                completed_tasks = 0
                self.processed_items = 0
                self.success_items = 0
                self.failed_items = 0
                
                for task_id in tasks:
                    status = download_manager.get_task_status(task_id)
                    
                    if status.status in ('completed', 'failed'):
                        completed_tasks += 1
                        self.processed_items += status.items_processed
                        
                        if status.status == 'completed':
                            self.success_items += status.items_processed
                        else:
                            self.failed_items += 1
                
                # Update progress
                if tasks:
                    self.progress = (completed_tasks / len(tasks)) * 100
                
                # Sleep to avoid busy waiting
                if completed_tasks < len(tasks):
                    time.sleep(5)
            
            # Get final results
            results = {
                'total_tasks': len(tasks),
                'completed_tasks': completed_tasks,
                'downloaded_items': self.success_items,
                'failed_tasks': self.failed_items,
                'task_details': []
            }
            
            for task_id in tasks:
                status = download_manager.get_task_status(task_id)
                results['task_details'].append({
                    'task_id': task_id,
                    'status': status.status,
                    'items_processed': status.items_processed,
                    'error': status.error
                })
            
            return results
            
        finally:
            # Ensure download manager is stopped
            download_manager.stop()
    
    def _execute_ocr(self, **components) -> Dict:
        """
        Execute an OCR processing task.
        
        Args:
            **components: Repository components
            
        Returns:
            Dictionary with OCR processing results
        """
        if 'ocr_processor' not in components:
            raise BulkTaskError("OCR task requires 'ocr_processor' component")
        
        if 'publication_repo' not in components:
            raise BulkTaskError("OCR task requires 'publication_repo' component")
        
        ocr_processor = components['ocr_processor']
        publication_repo = components['publication_repo']
        
        # Get parameters
        publication_id = self.parameters.get('publication_id')
        date_range = self.parameters.get('date_range', {})
        reprocess = self.parameters.get('reprocess', False)
        max_concurrent = self.parameters.get('max_concurrent', 2)
        
        start_date = None
        end_date = None
        
        if isinstance(date_range, dict):
            start_date_str = date_range.get('start')
            end_date_str = date_range.get('end')
            
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        
        # Find issues that need processing
        issues = publication_repo.find_issues(
            publication_id=publication_id,
            issue_date=start_date,
            end_date=end_date,
            processed=not reprocess
        )
        
        if not issues:
            return {
                'status': 'no_issues_found',
                'publication_id': publication_id,
                'reprocess': reprocess
            }
        
        self.total_items = len(issues)
        
        # Create OCR tasks
        tasks = []
        
        for issue in issues:
            task_id = ocr_processor.add_task(
                publication_id=publication_id,
                issue_id=issue['id'],
                priority=1
            )
            tasks.append(task_id)
        
        # Configure and start OCR processor
        ocr_processor.max_workers = max_concurrent
        
        # Set OCR options if specified
        if 'ocr_engine' in self.parameters:
            ocr_processor.ocr_engine = self.parameters['ocr_engine']
        
        if 'segment_articles' in self.parameters:
            ocr_processor.segment_articles = self.parameters['segment_articles']
        
        ocr_processor.start()
        
        try:
            # Monitor progress
            completed_tasks = 0
            
            while completed_tasks < len(tasks):
                completed_tasks = 0
                self.processed_items = 0
                self.success_items = 0
                self.failed_items = 0
                
                for task_id in tasks:
                    status = ocr_processor.get_task_status(task_id)
                    
                    if status.status in ('completed', 'failed'):
                        completed_tasks += 1
                        self.processed_items += 1
                        
                        if status.status == 'completed':
                            self.success_items += 1
                        else:
                            self.failed_items += 1
                
                # Update progress
                if tasks:
                    self.progress = (completed_tasks / len(tasks)) * 100
                
                # Sleep to avoid busy waiting
                if completed_tasks < len(tasks):
                    time.sleep(5)
            
            # Get final results
            results = {
                'total_issues': len(tasks),
                'processed_issues': completed_tasks,
                'successful_issues': self.success_items,
                'failed_issues': self.failed_items,
                'publication_id': publication_id,
                'task_details': []
            }
            
            for task_id in tasks:
                status = ocr_processor.get_task_status(task_id)
                results['task_details'].append({
                    'task_id': task_id,
                    'status': status.status,
                    'pages_processed': status.items_processed,
                    'articles_extracted': status.articles_extracted,
                    'error': status.error
                })
            
            return results
            
        finally:
            # Ensure OCR processor is stopped
            ocr_processor.stop()
    
    def _execute_entity_extraction(self, **components) -> Dict:
        """
        Execute an entity extraction task.
        
        Args:
            **components: Repository components
            
        Returns:
            Dictionary with entity extraction results
        """
        if 'publication_repo' not in components:
            raise BulkTaskError("Entity extraction task requires 'publication_repo' component")
        
        if 'db_manager' not in components:
            raise BulkTaskError("Entity extraction task requires 'db_manager' component")
        
        publication_repo = components['publication_repo']
        db_manager = components['db_manager']
        
        # Get parameters
        publication_id = self.parameters.get('publication_id')
        date_range = self.parameters.get('date_range', {})
        min_confidence = self.parameters.get('min_confidence', 0.5)
        entity_types = self.parameters.get('entity_types', ['person', 'organization', 'location'])
        batch_size = self.parameters.get('batch_size', 100)
        
        start_date = None
        end_date = None
        
        if isinstance(date_range, dict):
            start_date_str = date_range.get('start')
            end_date_str = date_range.get('end')
            
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        
        # Find articles for entity extraction
        articles = publication_repo.find_articles(
            publication_id=publication_id,
            start_date=start_date,
            end_date=end_date,
            with_text=True,
            limit=0  # No limit
        )
        
        if not articles:
            return {
                'status': 'no_articles_found',
                'publication_id': publication_id
            }
        
        self.total_items = len(articles)
        
        # Process articles in batches
        total_entities = 0
        total_mentions = 0
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            
            # Process batch
            batch_entities, batch_mentions = publication_repo.extract_entities(
                articles=batch,
                min_confidence=min_confidence,
                entity_types=entity_types
            )
            
            total_entities += batch_entities
            total_mentions += batch_mentions
            
            # Update progress
            self.processed_items = min(i + batch_size, len(articles))
            self.success_items = self.processed_items
            self.progress = (self.processed_items / len(articles)) * 100
        
        # Get final results
        results = {
            'total_articles': len(articles),
            'processed_articles': self.processed_items,
            'extracted_entities': total_entities,
            'entity_mentions': total_mentions,
            'publication_id': publication_id
        }
        
        return results
    
    def _execute_import(self, **components) -> Dict:
        """
        Execute an import task.
        
        Args:
            **components: Repository components
            
        Returns:
            Dictionary with import results
        """
        if 'db_manager' not in components:
            raise BulkTaskError("Import task requires 'db_manager' component")
        
        db_manager = components['db_manager']
        
        # Get parameters
        source_type = self.parameters['source_type']
        source_path = self.parameters['source_path']
        mapping = self.parameters.get('mapping', {})
        batch_size = self.parameters.get('batch_size', 1000)
        
        # Check if source exists
        if not os.path.exists(source_path):
            raise BulkTaskError(f"Source path not found: {source_path}")
        
        # Process based on source type
        if source_type == 'csv':
            return self._import_from_csv(
                db_manager=db_manager,
                source_path=source_path,
                mapping=mapping,
                batch_size=batch_size
            )
        elif source_type == 'json':
            return self._import_from_json(
                db_manager=db_manager,
                source_path=source_path,
                mapping=mapping,
                batch_size=batch_size
            )
        elif source_type == 'sqlite':
            return self._import_from_sqlite(
                db_manager=db_manager,
                source_path=source_path,
                mapping=mapping,
                batch_size=batch_size
            )
        else:
            raise BulkTaskError(f"Unsupported import source type: {source_type}")
    
    def _import_from_csv(self, db_manager, source_path, mapping, batch_size) -> Dict:
        """Import data from CSV file."""
        import csv
        
        imported = 0
        errors = 0
        
        try:
            # Read CSV file
            with open(source_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Get total rows for progress
                rows = list(reader)
                self.total_items = len(rows)
                
                # Process in batches
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i+batch_size]
                    
                    # Map rows to database format
                    mapped_rows = []
                    
                    for row in batch:
                        mapped_row = {}
                        for target_field, source_field in mapping.items():
                            if source_field in row:
                                mapped_row[target_field] = row[source_field]
                        
                        if mapped_row:
                            mapped_rows.append(mapped_row)
                    
                    # Import batch
                    with db_manager.transaction() as tx:
                        for row in mapped_rows:
                            try:
                                if 'publication_id' in row and 'issue_date' in row:
                                    # Get or create publication
                                    publication = db_manager.get_publication(row['publication_id'])
                                    if not publication:
                                        db_manager.insert_publication({
                                            'id': row['publication_id'],
                                            'title': row.get('publication_title', row['publication_id'])
                                        })
                                    
                                    # Get or create issue
                                    issue_date = row['issue_date']
                                    issue = db_manager.get_issue(row['publication_id'], issue_date)
                                    if not issue:
                                        issue_id = db_manager.insert_issue({
                                            'publication_id': row['publication_id'],
                                            'date': issue_date
                                        })
                                    else:
                                        issue_id = issue['id']
                                    
                                    # Get or create page
                                    page_number = row.get('page_number', 1)
                                    page = db_manager.get_page(issue_id, page_number)
                                    if not page:
                                        page_id = db_manager.insert_page({
                                            'issue_id': issue_id,
                                            'page_number': page_number
                                        })
                                    else:
                                        page_id = page['id']
                                    
                                    # Add article
                                    if 'title' in row or 'text' in row:
                                        db_manager.insert_article({
                                            'issue_id': issue_id,
                                            'page_number': page_number,
                                            'title': row.get('title', ''),
                                            'text': row.get('text', '')
                                        })
                                        
                                        imported += 1
                            except Exception as e:
                                errors += 1
                                logger.error(f"Error importing row: {str(e)}")
                    
                    # Update progress
                    self.processed_items = min(i + batch_size, len(rows))
                    self.success_items = imported
                    self.failed_items = errors
                    self.progress = (self.processed_items / len(rows)) * 100
            
            return {
                'source_type': 'csv',
                'source_path': source_path,
                'total_rows': self.total_items,
                'imported': imported,
                'errors': errors
            }
            
        except Exception as e:
            raise BulkTaskError(f"Failed to import from CSV: {str(e)}")
    
    def _import_from_json(self, db_manager, source_path, mapping, batch_size) -> Dict:
        """Import data from JSON file."""
        imported = 0
        errors = 0
        
        try:
            # Read JSON file
            with open(source_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ensure data is a list
            if not isinstance(data, list):
                if isinstance(data, dict) and 'items' in data and isinstance(data['items'], list):
                    data = data['items']
                else:
                    raise BulkTaskError("JSON data must be a list or have an 'items' list property")
            
            self.total_items = len(data)
            
            # Process in batches
            for i in range(0, len(data), batch_size):
                batch = data[i:i+batch_size]
                
                # Map items to database format
                mapped_items = []
                
                for item in batch:
                    mapped_item = {}
                    for target_field, source_field in mapping.items():
                        if source_field in item:
                            mapped_item[target_field] = item[source_field]
                    
                    if mapped_item:
                        mapped_items.append(mapped_item)
                
                # Import batch
                with db_manager.transaction() as tx:
                    for item in mapped_items:
                        try:
                            if 'publication_id' in item and 'issue_date' in item:
                                # Get or create publication
                                publication = db_manager.get_publication(item['publication_id'])
                                if not publication:
                                    db_manager.insert_publication({
                                        'id': item['publication_id'],
                                        'title': item.get('publication_title', item['publication_id'])
                                    })
                                
                                # Get or create issue
                                issue_date = item['issue_date']
                                issue = db_manager.get_issue(item['publication_id'], issue_date)
                                if not issue:
                                    issue_id = db_manager.insert_issue({
                                        'publication_id': item['publication_id'],
                                        'date': issue_date
                                    })
                                else:
                                    issue_id = issue['id']
                                
                                # Get or create page
                                page_number = item.get('page_number', 1)
                                page = db_manager.get_page(issue_id, page_number)
                                if not page:
                                    page_id = db_manager.insert_page({
                                        'issue_id': issue_id,
                                        'page_number': page_number
                                    })
                                else:
                                    page_id = page['id']
                                
                                # Add article
                                if 'title' in item or 'text' in item:
                                    db_manager.insert_article({
                                        'issue_id': issue_id,
                                        'page_number': page_number,
                                        'title': item.get('title', ''),
                                        'text': item.get('text', '')
                                    })
                                    
                                    imported += 1
                        except Exception as e:
                            errors += 1
                            logger.error(f"Error importing item: {str(e)}")
                
                # Update progress
                self.processed_items = min(i + batch_size, len(data))
                self.success_items = imported
                self.failed_items = errors
                self.progress = (self.processed_items / len(data)) * 100
            
            return {
                'source_type': 'json',
                'source_path': source_path,
                'total_items': self.total_items,
                'imported': imported,
                'errors': errors
            }
            
        except Exception as e:
            raise BulkTaskError(f"Failed to import from JSON: {str(e)}")
    
    def _import_from_sqlite(self, db_manager, source_path, mapping, batch_size) -> Dict:
        """Import data from SQLite database."""
        import sqlite3
        
        imported = 0
        errors = 0
        
        try:
            # Connect to source database
            source_query = self.parameters.get('source_query', "SELECT * FROM publications")
            
            source_conn = sqlite3.connect(source_path)
            source_conn.row_factory = sqlite3.Row
            
            cursor = source_conn.cursor()
            cursor.execute(source_query)
            
            # Get total rows for progress
            rows = cursor.fetchall()
            self.total_items = len(rows)
            
            # Process in batches
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                
                # Map rows to database format
                mapped_rows = []
                
                for row in batch:
                    mapped_row = {}
                    for target_field, source_field in mapping.items():
                        if source_field in row.keys():
                            mapped_row[target_field] = row[source_field]
                    
                    if mapped_row:
                        mapped_rows.append(mapped_row)
                
                # Import batch
                with db_manager.transaction() as tx:
                    for row in mapped_rows:
                        try:
                            if 'publication_id' in row and 'issue_date' in row:
                                # Get or create publication
                                publication = db_manager.get_publication(row['publication_id'])
                                if not publication:
                                    db_manager.insert_publication({
                                        'id': row['publication_id'],
                                        'title': row.get('publication_title', row['publication_id'])
                                    })
                                
                                # Get or create issue
                                issue_date = row['issue_date']
                                issue = db_manager.get_issue(row['publication_id'], issue_date)
                                if not issue:
                                    issue_id = db_manager.insert_issue({
                                        'publication_id': row['publication_id'],
                                        'date': issue_date
                                    })
                                else:
                                    issue_id = issue['id']
                                
                                # Get or create page
                                page_number = row.get('page_number', 1)
                                page = db_manager.get_page(issue_id, page_number)
                                if not page:
                                    page_id = db_manager.insert_page({
                                        'issue_id': issue_id,
                                        'page_number': page_number
                                    })
                                else:
                                    page_id = page['id']
                                
                                # Add article
                                if 'title' in row or 'text' in row:
                                    db_manager.insert_article({
                                        'issue_id': issue_id,
                                        'page_number': page_number,
                                        'title': row.get('title', ''),
                                        'text': row.get('text', '')
                                    })
                                    
                                    imported += 1
                        except Exception as e:
                            errors += 1
                            logger.error(f"Error importing row: {str(e)}")
                
                # Update progress
                self.processed_items = min(i + batch_size, len(rows))
                self.success_items = imported
                self.failed_items = errors
                self.progress = (self.processed_items / len(rows)) * 100
            
            # Close connection
            source_conn.close()
            
            return {
                'source_type': 'sqlite',
                'source_path': source_path,
                'total_rows': self.total_items,
                'imported': imported,
                'errors': errors
            }
            
        except Exception as e:
            raise BulkTaskError(f"Failed to import from SQLite: {str(e)}")
    
    def _execute_export(self, **components) -> Dict:
        """
        Execute an export task.
        
        Args:
            **components: Repository components
            
        Returns:
            Dictionary with export results
        """
        if 'publication_repo' not in components:
            raise BulkTaskError("Export task requires 'publication_repo' component")
        
        publication_repo = components['publication_repo']
        
        # Get parameters
        output_format = self.parameters['output_format']
        output_path = self.parameters['output_path']
        publication_id = self.parameters.get('publication_id')
        date_range = self.parameters.get('date_range', {})
        include_fields = self.parameters.get('include_fields', [])
        batch_size = self.parameters.get('batch_size', 1000)
        
        start_date = None
        end_date = None
        
        if isinstance(date_range, dict):
            start_date_str = date_range.get('start')
            end_date_str = date_range.get('end')
            
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Find articles to export
        total_articles = publication_repo.count_articles(
            publication_id=publication_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if total_articles == 0:
            return {
                'status': 'no_articles_found',
                'publication_id': publication_id
            }
        
        self.total_items = total_articles
        
        # Determine export function based on format
        if output_format == 'json':
            export_func = self._export_to_json
        elif output_format == 'csv':
            export_func = self._export_to_csv
        elif output_format == 'txt':
            export_func = self._export_to_txt
        else:
            raise BulkTaskError(f"Unsupported export format: {output_format}")
        
        # Process in batches
        exported = 0
        errors = 0
        offset = 0
        
        while offset < total_articles:
            # Get batch of articles
            articles = publication_repo.find_articles(
                publication_id=publication_id,
                start_date=start_date,
                end_date=end_date,
                limit=batch_size,
                offset=offset
            )
            
            if not articles:
                break
            
            # Filter fields if specified
            if include_fields:
                filtered_articles = []
                for article in articles:
                    filtered = {field: article[field] for field in include_fields if field in article}
                    filtered_articles.append(filtered)
                articles = filtered_articles
            
            # Determine if this is the first batch
            is_first_batch = (offset == 0)
            
            # Export batch
            try:
                batch_exported = export_func(
                    articles=articles,
                    output_path=output_path,
                    is_first_batch=is_first_batch,
                    is_last_batch=(offset + len(articles) >= total_articles)
                )
                
                exported += batch_exported
            except Exception as e:
                errors += len(articles)
                logger.error(f"Error exporting batch: {str(e)}")
            
            # Update offset for next batch
            offset += len(articles)
            
            # Update progress
            self.processed_items = offset
            self.success_items = exported
            self.failed_items = errors
            self.progress = (offset / total_articles) * 100
        
        return {
            'output_format': output_format,
            'output_path': output_path,
            'total_articles': total_articles,
            'exported': exported,
            'errors': errors
        }
    
    def _export_to_json(self, articles, output_path, is_first_batch, is_last_batch) -> int:
        """Export articles to JSON file."""
        if is_first_batch:
            # For first batch, create file and write opening bracket
            mode = 'w'
            content = "[\n"
        else:
            # For subsequent batches, append to file
            mode = 'a'
            content = ""
        
        # Add articles as JSON objects
        for i, article in enumerate(articles):
            article_json = json.dumps(article, ensure_ascii=False, indent=2)
            
            if i > 0 or not is_first_batch:
                content += ",\n"
            
            content += article_json
        
        if is_last_batch:
            # For last batch, add closing bracket
            content += "\n]"
        
        # Write to file
        with open(output_path, mode, encoding='utf-8') as f:
            f.write(content)
        
        return len(articles)
    
    def _export_to_csv(self, articles, output_path, is_first_batch, is_last_batch) -> int:
        """Export articles to CSV file."""
        import csv
        
        if not articles:
            return 0
        
        # Determine fieldnames from first article
        fieldnames = list(articles[0].keys())
        
        if is_first_batch:
            # For first batch, create file and write header
            mode = 'w'
            include_header = True
        else:
            # For subsequent batches, append to file without header
            mode = 'a'
            include_header = False
        
        # Write to file
        with open(output_path, mode, encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if include_header:
                writer.writeheader()
            
            for article in articles:
                # Convert any non-string values to strings
                for key, value in article.items():
                    if isinstance(value, (dict, list)):
                        article[key] = json.dumps(value)
                
                writer.writerow(article)
        
        return len(articles)
    
    def _export_to_txt(self, articles, output_path, is_first_batch, is_last_batch) -> int:
        """Export articles to text file."""
        if is_first_batch:
            # For first batch, create file
            mode = 'w'
        else:
            # For subsequent batches, append to file
            mode = 'a'
        
        # Write to file
        with open(output_path, mode, encoding='utf-8') as f:
            for article in articles:
                f.write(f"ID: {article.get('id', 'unknown')}\n")
                f.write(f"Title: {article.get('title', 'Untitled')}\n")
                
                if 'publication_title' in article:
                    f.write(f"Publication: {article['publication_title']}\n")
                
                if 'issue_date' in article:
                    f.write(f"Date: {article['issue_date']}\n")
                
                if 'page_number' in article:
                    f.write(f"Page: {article['page_number']}\n")
                
                f.write("-" * 80 + "\n")
                
                if 'text' in article:
                    f.write(article['text'] + "\n\n")
                
                f.write("=" * 80 + "\n\n")
        
        return len(articles)
    
    def _execute_maintenance(self, **components) -> Dict:
        """
        Execute a maintenance task.
        
        Args:
            **components: Repository components
            
        Returns:
            Dictionary with maintenance results
        """
        if 'db_manager' not in components:
            raise BulkTaskError("Maintenance task requires 'db_manager' component")
        
        db_manager = components['db_manager']
        
        # Get parameters
        operations = self.parameters['operations']
        
        if not operations:
            return {'status': 'no_operations_specified'}
        
        if isinstance(operations, str):
            operations = [operations]
        
        # Set total operations
        self.total_items = len(operations)
        self.processed_items = 0
        
        results = {
            'completed_operations': [],
            'failed_operations': []
        }
        
        # Execute operations
        for operation in operations:
            try:
                if operation == 'vacuum':
                    db_manager.vacuum_database()
                    results['completed_operations'].append('vacuum')
                
                elif operation == 'analyze':
                    db_manager.analyze_database()
                    results['completed_operations'].append('analyze')
                
                elif operation == 'backup':
                    backup_path = self.parameters.get('backup_path')
                    if not backup_path:
                        backup_dir = os.path.dirname(db_manager.db_path)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
                    
                    db_manager.backup_database(backup_path)
                    results['backup_path'] = backup_path
                    results['completed_operations'].append('backup')
                
                elif operation == 'rebuild_index':
                    if 'search_engine' not in components:
                        raise BulkTaskError("rebuild_index operation requires 'search_engine' component")
                    
                    search_engine = components['search_engine']
                    index_result = search_engine.rebuild_search_index()
                    
                    results['index_result'] = index_result
                    results['completed_operations'].append('rebuild_index')
                
                elif operation == 'optimize':
                    db_manager.optimize_database()
                    results['completed_operations'].append('optimize')
                
                else:
                    logger.warning(f"Unknown maintenance operation: {operation}")
                    results['failed_operations'].append(operation)
                
                self.success_items += 1
            
            except Exception as e:
                logger.error(f"Error executing maintenance operation {operation}: {str(e)}")
                results['failed_operations'].append(operation)
                self.failed_items += 1
            
            # Update progress
            self.processed_items += 1
            self.progress = (self.processed_items / self.total_items) * 100
        
        return results
    
    def get_status(self) -> Dict:
        """
        Get the current status of the task.
        
        Returns:
            Dictionary with task status
        """
        return {
            'task_id': self.task_id,
            'description': self.description,
            'task_type': self.task_type.value,
            'status': self.status.value,
            'progress': self.progress,
            'total': self.total_items,
            'processed': self.processed_items,
            'completed': self.success_items,
            'failed': self.failed_items,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error': self.error,
            'results': self.results
        }
    
    def cancel(self) -> None:
        """Cancel the task if it's running."""
        if self.status == TaskStatus.RUNNING:
            self.status = TaskStatus.CANCELED
            self.end_time = datetime.now()
            logger.info(f"Canceled bulk task {self.task_id}")
    
    def to_dict(self) -> Dict:
        """
        Convert the task to a dictionary.
        
        Returns:
            Dictionary representation of the task
        """
        return {
            'task_id': self.task_id,
            'description': self.description,
            'task_type': self.task_type.value,
            'custom_type': self.custom_type,
            'parameters': self.parameters,
            'status': self.status.value,
            'progress': self.progress,
            'total_items': self.total_items,
            'processed_items': self.processed_items,
            'success_items': self.success_items,
            'failed_items': self.failed_items,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error': self.error,
            'results': self.results
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BulkTask':
        """
        Create a task from a dictionary.
        
        Args:
            data: Dictionary representation of the task
            
        Returns:
            BulkTask instance
        """
        task = cls(
            task_type=data['task_type'],
            parameters=data['parameters'],
            task_id=data['task_id'],
            description=data['description']
        )
        
        task.custom_type = data.get('custom_type')
        task.status = TaskStatus(data['status'])
        task.progress = data['progress']
        task.total_items = data['total_items']
        task.processed_items = data['processed_items']
        task.success_items = data['success_items']
        task.failed_items = data['failed_items']
        
        if data.get('start_time'):
            task.start_time = datetime.fromisoformat(data['start_time'])
        
        if data.get('end_time'):
            task.end_time = datetime.fromisoformat(data['end_time'])
        
        task.error = data.get('error')
        task.results = data.get('results', {})
        
        return task
    
    def save_to_file(self, file_path: str) -> None:
        """
        Save the task to a file.
        
        Args:
            file_path: Path to save the task
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'BulkTask':
        """
        Load a task from a file.
        
        Args:
            file_path: Path to the task file
            
        Returns:
            BulkTask instance
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls.from_dict(data)