"""
Background Service for automated newspaper repository tasks.

This module provides a background service that can run automated tasks related to
the newspaper repository system, such as scheduled downloads, OCR processing,
database maintenance, and synchronization with the main application.
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any, Callable

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import repository components
from repository.config import Configuration
from repository.database_manager import DatabaseManager
from repository.publication_repository import PublicationRepository
from repository.downloader import DownloadManager, ChroniclingAmericaDownloader
from repository.ocr_processor import OCRProcessor
from repository.main_db_connector import MainDatabaseConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'background_service.log'))
    ]
)
logger = logging.getLogger('background_service')


class ServiceError(Exception):
    """Exception raised for background service errors."""
    pass


class Task:
    """Background task definition."""
    
    def __init__(
        self,
        name: str,
        function: Callable,
        interval: int,
        args: Optional[List] = None,
        kwargs: Optional[Dict] = None,
        enabled: bool = True,
        last_run: Optional[datetime] = None
    ):
        """
        Initialize a background task.
        
        Args:
            name: Task name
            function: Function to execute
            interval: Interval in seconds between executions
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            enabled: Whether the task is enabled
            last_run: Last execution time
        """
        self.name = name
        self.function = function
        self.interval = interval
        self.args = args or []
        self.kwargs = kwargs or {}
        self.enabled = enabled
        self.last_run = last_run
        self.next_run = datetime.now() if last_run is None else last_run + timedelta(seconds=interval)
        self.running = False
        self.error = None
        self.result = None
    
    def should_run(self) -> bool:
        """Check if the task should run now."""
        return (
            self.enabled and 
            not self.running and 
            datetime.now() >= self.next_run
        )
    
    def execute(self) -> Any:
        """Execute the task and update its state."""
        if not self.enabled:
            return None
        
        self.running = True
        self.error = None
        self.result = None
        
        try:
            logger.info(f"Executing task: {self.name}")
            start_time = time.time()
            self.result = self.function(*self.args, **self.kwargs)
            execution_time = time.time() - start_time
            logger.info(f"Task {self.name} completed in {execution_time:.2f} seconds")
            
            return self.result
        except Exception as e:
            self.error = str(e)
            logger.error(f"Task {self.name} failed: {str(e)}")
            return None
        finally:
            self.running = False
            self.last_run = datetime.now()
            self.next_run = self.last_run + timedelta(seconds=self.interval)


class BackgroundService:
    """Background service for automated newspaper repository tasks."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the background service.
        
        Args:
            config_path: Optional path to configuration file
        """
        # Load configuration
        self.config = Configuration(config_path)
        
        # Initialize components
        self.db_manager = DatabaseManager(
            db_path=self.config.get('database.path'),
            enable_foreign_keys=True,
            pool_size=self.config.get('database.pool_size', 5)
        )
        
        self.publication_repo = PublicationRepository(
            config={
                'base_path': self.config.get('repository.base_path'),
                'temp_path': self.config.get('repository.temp_path'),
            },
            db_manager=self.db_manager
        )
        
        self.download_manager = DownloadManager(
            config={
                'base_path': self.config.get('repository.base_path'),
                'temp_path': self.config.get('repository.temp_path'),
            },
            max_workers=self.config.get('downloader.max_workers', 3),
            default_retry_attempts=self.config.get('downloader.retry_attempts', 3)
        )
        
        # Register downloaders
        self.download_manager.register_downloader(
            'chroniclingamerica',
            ChroniclingAmericaDownloader(
                api_key=self.config.get('downloaders.chroniclingamerica.api_key'),
                base_url=self.config.get('downloaders.chroniclingamerica.base_url'),
                rate_limit=self.config.get('downloaders.chroniclingamerica.rate_limit', 5)
            )
        )
        
        self.ocr_processor = OCRProcessor(
            config={
                'base_path': self.config.get('repository.base_path'),
                'temp_path': self.config.get('repository.temp_path'),
            },
            publication_repo=self.publication_repo,
            max_workers=self.config.get('ocr.max_workers', 2),
            use_gpu=self.config.get('ocr.use_gpu', False)
        )
        
        # Initialize main database connector if configured
        self.main_db_connector = None
        main_db_path = self.config.get('main_database.path')
        if main_db_path:
            self.main_db_connector = MainDatabaseConnector(
                repo_db_path=self.config.get('database.path'),
                main_db_path=main_db_path,
                auto_connect=False
            )
        
        # Initialize task registry
        self.tasks = {}
        self.running = False
        self.thread = None
        
        # Register default tasks
        self._register_default_tasks()
        
        logger.info("Background service initialized")
    
    def _register_default_tasks(self) -> None:
        """Register default background tasks."""
        # Database maintenance task
        self.register_task(
            name="database_maintenance",
            function=self._task_database_maintenance,
            interval=24 * 60 * 60,  # Daily
            enabled=True
        )
        
        # Process OCR queue task
        self.register_task(
            name="process_ocr_queue",
            function=self._task_process_ocr_queue,
            interval=60 * 60,  # Hourly
            enabled=True
        )
        
        # Download scheduled publications task
        self.register_task(
            name="download_scheduled_publications",
            function=self._task_download_scheduled_publications,
            interval=6 * 60 * 60,  # Every 6 hours
            enabled=True
        )
        
        # Sync with main database task (if configured)
        if self.main_db_connector:
            self.register_task(
                name="sync_with_main_database",
                function=self._task_sync_with_main_database,
                interval=12 * 60 * 60,  # Every 12 hours
                enabled=True
            )
    
    def register_task(
        self, 
        name: str, 
        function: Callable, 
        interval: int, 
        args: Optional[List] = None,
        kwargs: Optional[Dict] = None,
        enabled: bool = True
    ) -> None:
        """
        Register a new background task.
        
        Args:
            name: Task name
            function: Function to execute
            interval: Interval in seconds between executions
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            enabled: Whether the task is enabled
        """
        self.tasks[name] = Task(
            name=name,
            function=function,
            interval=interval,
            args=args,
            kwargs=kwargs,
            enabled=enabled
        )
        logger.info(f"Registered task: {name} (interval: {interval}s, enabled: {enabled})")
    
    def unregister_task(self, name: str) -> None:
        """
        Unregister a background task.
        
        Args:
            name: Task name
        """
        if name in self.tasks:
            del self.tasks[name]
            logger.info(f"Unregistered task: {name}")
    
    def enable_task(self, name: str) -> None:
        """
        Enable a background task.
        
        Args:
            name: Task name
        """
        if name in self.tasks:
            self.tasks[name].enabled = True
            logger.info(f"Enabled task: {name}")
    
    def disable_task(self, name: str) -> None:
        """
        Disable a background task.
        
        Args:
            name: Task name
        """
        if name in self.tasks:
            self.tasks[name].enabled = False
            logger.info(f"Disabled task: {name}")
    
    def set_task_interval(self, name: str, interval: int) -> None:
        """
        Set the interval for a background task.
        
        Args:
            name: Task name
            interval: Interval in seconds between executions
        """
        if name in self.tasks:
            self.tasks[name].interval = interval
            logger.info(f"Set interval for task {name}: {interval}s")
    
    def get_task_status(self, name: str) -> Optional[Dict]:
        """
        Get the status of a background task.
        
        Args:
            name: Task name
            
        Returns:
            Task status dictionary or None if not found
        """
        if name in self.tasks:
            task = self.tasks[name]
            return {
                'name': task.name,
                'enabled': task.enabled,
                'running': task.running,
                'interval': task.interval,
                'last_run': task.last_run,
                'next_run': task.next_run,
                'error': task.error
            }
        return None
    
    def get_all_task_status(self) -> Dict[str, Dict]:
        """
        Get the status of all background tasks.
        
        Returns:
            Dictionary of task status dictionaries
        """
        return {name: self.get_task_status(name) for name in self.tasks}
    
    def start(self) -> None:
        """
        Start the background service.
        
        Raises:
            ServiceError: If the service is already running
        """
        if self.running:
            raise ServiceError("Background service is already running")
        
        self.running = True
        self.thread = threading.Thread(target=self._run_service, daemon=True)
        self.thread.start()
        
        logger.info("Background service started")
    
    def stop(self) -> None:
        """
        Stop the background service.
        
        Raises:
            ServiceError: If the service is not running
        """
        if not self.running:
            raise ServiceError("Background service is not running")
        
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        
        logger.info("Background service stopped")
    
    def _run_service(self) -> None:
        """Run the background service loop."""
        try:
            while self.running:
                for name, task in self.tasks.items():
                    if task.should_run():
                        # Run task in a separate thread
                        threading.Thread(
                            target=task.execute,
                            name=f"task-{name}",
                            daemon=True
                        ).start()
                
                # Sleep to avoid busy waiting
                time.sleep(1)
        except Exception as e:
            logger.error(f"Background service error: {str(e)}")
            self.running = False
    
    def run_task_now(self, name: str) -> Any:
        """
        Run a specific task immediately and synchronously.
        
        Args:
            name: Task name
            
        Returns:
            Task result
            
        Raises:
            ServiceError: If the task is not found
        """
        if name not in self.tasks:
            raise ServiceError(f"Task not found: {name}")
        
        task = self.tasks[name]
        return task.execute()
    
    def _task_database_maintenance(self) -> Dict:
        """
        Perform database maintenance tasks.
        
        Returns:
            Dictionary with maintenance results
        """
        results = {}
        
        try:
            # Vacuum the database
            self.db_manager.vacuum_database()
            results['vacuum'] = True
            
            # Analyze database for query optimization
            self.db_manager.analyze_database()
            results['analyze'] = True
            
            # Create backup
            backup_dir = self.config.get('database.backup_directory')
            if backup_dir:
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d')
                backup_path = os.path.join(backup_dir, f"newspaper_repo_backup_{timestamp}.db")
                
                # Only create one backup per day
                if not os.path.exists(backup_path):
                    self.db_manager.backup_database(backup_path)
                    results['backup'] = backup_path
            
            return results
        except Exception as e:
            logger.error(f"Database maintenance task error: {str(e)}")
            return {'error': str(e)}
    
    def _task_process_ocr_queue(self) -> Dict:
        """
        Process items in the OCR queue.
        
        Returns:
            Dictionary with processing results
        """
        results = {'processed': 0, 'errors': 0}
        
        try:
            # Check if there are items in the queue
            queue_items = self.ocr_processor.get_queue_status()
            
            if not queue_items or queue_items.get('pending', 0) == 0:
                return results
            
            # Start OCR processing
            logger.info(f"Starting OCR processing for {queue_items.get('pending', 0)} items")
            self.ocr_processor.start()
            
            # Process for a maximum time or until queue is empty
            max_processing_time = self.config.get('ocr.background_processing_time', 30 * 60)  # 30 minutes
            start_time = time.time()
            
            while (time.time() - start_time < max_processing_time and 
                  self.ocr_processor.is_running() and
                  self.ocr_processor.get_queue_status().get('pending', 0) > 0):
                # Wait a bit
                time.sleep(10)
            
            # Stop OCR processor
            self.ocr_processor.stop()
            
            # Get final status
            final_status = self.ocr_processor.get_queue_status()
            results['processed'] = final_status.get('completed', 0) - queue_items.get('completed', 0)
            results['errors'] = final_status.get('failed', 0) - queue_items.get('failed', 0)
            
            logger.info(f"OCR processing completed: {results['processed']} processed, {results['errors']} errors")
            return results
        except Exception as e:
            logger.error(f"OCR processing task error: {str(e)}")
            return {'error': str(e), 'processed': 0, 'errors': 0}
    
    def _task_download_scheduled_publications(self) -> Dict:
        """
        Download scheduled publications.
        
        Returns:
            Dictionary with download results
        """
        results = {'downloaded': 0, 'errors': 0, 'publications': []}
        
        try:
            # Get publications with scheduled downloads
            scheduled = self.publication_repo.get_scheduled_downloads()
            
            if not scheduled:
                return results
            
            logger.info(f"Found {len(scheduled)} scheduled publication downloads")
            
            # Process each scheduled download
            for schedule in scheduled:
                pub_id = schedule.get('publication_id')
                source = schedule.get('source')
                frequency = schedule.get('frequency')
                last_download = schedule.get('last_download')
                params = schedule.get('parameters', {})
                
                # Skip if source is not registered
                if not self.download_manager.get_downloader(source):
                    logger.warning(f"Downloader not found for source: {source}")
                    continue
                
                # Check if download is due based on frequency
                should_download = False
                
                if frequency == 'daily':
                    should_download = (not last_download or 
                                     datetime.now() - last_download > timedelta(days=1))
                elif frequency == 'weekly':
                    should_download = (not last_download or 
                                     datetime.now() - last_download > timedelta(days=7))
                elif frequency == 'monthly':
                    should_download = (not last_download or 
                                     datetime.now() - last_download > timedelta(days=30))
                
                if not should_download:
                    continue
                
                # Create download task
                task_id = self.download_manager.add_task(
                    downloader=source,
                    publication_id=pub_id,
                    start_date=params.get('start_date'),
                    end_date=params.get('end_date'),
                    location=params.get('location'),
                    max_items=params.get('max_items', 10),
                    priority=1
                )
                
                logger.info(f"Created download task {task_id} for publication {pub_id}")
                results['publications'].append({
                    'publication_id': pub_id,
                    'task_id': task_id
                })
            
            # Start download manager if tasks were created
            if results['publications']:
                logger.info(f"Starting download for {len(results['publications'])} publications")
                self.download_manager.start()
                
                # Process for a maximum time
                max_processing_time = self.config.get('downloader.background_processing_time', 30 * 60)  # 30 minutes
                start_time = time.time()
                
                while (time.time() - start_time < max_processing_time and 
                      self.download_manager.is_running()):
                    # Wait a bit
                    time.sleep(10)
                
                # Stop download manager
                self.download_manager.stop()
                
                # Update results
                for pub in results['publications']:
                    task_status = self.download_manager.get_task_status(pub['task_id'])
                    pub['status'] = task_status.status
                    pub['downloaded'] = task_status.items_processed
                    pub['error'] = task_status.error
                    
                    if task_status.status == 'completed':
                        results['downloaded'] += task_status.items_processed
                    elif task_status.status == 'failed':
                        results['errors'] += 1
                    
                    # Update last download time
                    if task_status.status == 'completed':
                        self.publication_repo.update_download_schedule(
                            publication_id=pub['publication_id'],
                            last_download=datetime.now()
                        )
            
            logger.info(f"Download task completed: {results['downloaded']} items downloaded, {results['errors']} errors")
            return results
        except Exception as e:
            logger.error(f"Download task error: {str(e)}")
            return {'error': str(e), 'downloaded': 0, 'errors': 0, 'publications': []}
    
    def _task_sync_with_main_database(self) -> Dict:
        """
        Synchronize with the main application database.
        
        Returns:
            Dictionary with synchronization results
        """
        results = {}
        
        if not self.main_db_connector:
            return {'error': 'Main database connector not configured'}
        
        try:
            # Connect to databases
            self.main_db_connector.connect()
            
            # Sync entities from main database to repository
            entities_result = self.main_db_connector.import_entities_to_repository()
            results['entities_imported'] = {
                'added': entities_result[0],
                'updated': entities_result[1],
                'total': entities_result[2]
            }
            
            # Sync locations from main database to repository
            locations_result = self.main_db_connector.import_locations_to_repository()
            results['locations_imported'] = {
                'added': locations_result[0],
                'updated': locations_result[1],
                'total': locations_result[2]
            }
            
            # Sync sources from repository to main database
            sources_result = self.main_db_connector.sync_sources()
            results['sources_synced'] = {
                'added': sources_result[0],
                'updated': sources_result[1],
                'total': sources_result[2]
            }
            
            # Sync articles to documents
            articles_result = self.main_db_connector.sync_articles_to_documents(
                start_date=datetime.now() - timedelta(days=30),  # Last 30 days
                limit=500  # Limit to 500 articles per sync
            )
            results['articles_synced'] = {
                'added': articles_result[0],
                'updated': articles_result[1],
                'total': articles_result[2]
            }
            
            # Export entity mentions
            mentions_result = self.main_db_connector.export_entity_mentions()
            results['mentions_exported'] = {
                'character_mentions': mentions_result[0],
                'entity_relations': mentions_result[1]
            }
            
            # Close connections
            self.main_db_connector.close()
            
            logger.info(f"Database synchronization completed: {results}")
            return results
        except Exception as e:
            logger.error(f"Database synchronization task error: {str(e)}")
            if self.main_db_connector:
                self.main_db_connector.close()
            return {'error': str(e)}


def main():
    """Main entry point for running the background service."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Newspaper Repository Background Service')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                         help='Set the logging level')
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create service
    service = BackgroundService(config_path=args.config)
    
    # Handle signals for graceful shutdown
    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Start service
        service.start()
        logger.info("Background service is running")
        
        # If running as daemon, just wait
        if args.daemon:
            while True:
                time.sleep(60)
        else:
            # Interactive mode - allow simple commands
            print("Background service is running. Type 'status' to see task status, 'stop' to exit.")
            while service.running:
                cmd = input("> ").strip().lower()
                
                if cmd == 'stop' or cmd == 'exit' or cmd == 'quit':
                    service.stop()
                    break
                elif cmd == 'status':
                    status = service.get_all_task_status()
                    for name, task in status.items():
                        print(f"{name}:")
                        print(f"  Enabled: {task['enabled']}")
                        print(f"  Running: {task['running']}")
                        if task['last_run']:
                            print(f"  Last run: {task['last_run'].strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"  Next run: {task['next_run'].strftime('%Y-%m-%d %H:%M:%S')}")
                        if task['error']:
                            print(f"  Error: {task['error']}")
                        print()
                elif cmd.startswith('run '):
                    task_name = cmd[4:].strip()
                    if task_name in service.tasks:
                        print(f"Running task {task_name}...")
                        try:
                            result = service.run_task_now(task_name)
                            print(f"Task {task_name} completed.")
                            print(f"Result: {result}")
                        except Exception as e:
                            print(f"Task {task_name} failed: {str(e)}")
                    else:
                        print(f"Task {task_name} not found.")
                else:
                    print("Unknown command. Available commands: status, run <task_name>, stop")
    
    except Exception as e:
        logger.error(f"Error in background service: {str(e)}")
        service.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()