"""
Background Processing Service

This module provides a background processing service for the newspaper repository.
The service runs in a separate thread and processes items from the queue in the background.
It updates the status of items as they are processed, handles failures gracefully with retries,
provides progress updates to the UI via PyQt signals, and can be paused, resumed, and stopped by the user.

Features:
- Multithreaded processing of OCR and article extraction tasks
- Prioritized task queue with automatic retries for failed tasks
- Real-time progress updates via PyQt signals
- Detailed error reporting and logging
- UI components for controlling the service
- Task cancellation and pause/resume capabilities
- Support for bulk operations with prioritization and tracking
- Batch processing for improved efficiency
- Detailed status reporting for bulk operations
"""

import os
import time
import threading
import queue
import logging
import traceback
import sys
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from datetime import datetime, timedelta
import json

# Import PyQt for signals
try:
    from PyQt5.QtCore import QObject, pyqtSignal
    PYQT_AVAILABLE = True
except ImportError:
    # Fallback for non-GUI environments
    PYQT_AVAILABLE = False
    # Create dummy QObject and pyqtSignal for non-GUI usage
    class QObject:
        pass
    def pyqtSignal(*args, **kwargs):
        return None

# Use absolute imports since the module might be run directly
try:
    # First try relative imports when used as a package
    from .repository_database import RepositoryDatabaseManager
    from .ocr_processor import OCRProcessor, ArticleSegment
    from .file_manager import FileManager
except ImportError:
    # Fall back to absolute imports when run directly
    from repository_database import RepositoryDatabaseManager
    from ocr_processor import OCRProcessor, ArticleSegment
    from file_manager import FileManager

# Helper function for safe imports
def _safe_import(relative_path, fallback_path):
    """
    Try to import a module using relative import first, then absolute import.

    Args:
        relative_path: The relative import path (e.g., '.module')
        fallback_path: The absolute import path (e.g., 'module')

    Returns:
        The imported module or None if both imports fail
    """
    try:
        # Try relative import first
        module_name = relative_path.lstrip('.')
        if relative_path.startswith('.'):
            # This is a relative import
            try:
                exec(f"from {relative_path} import {module_name}")
                return locals()[module_name]
            except (ImportError, KeyError):
                pass

        # Fall back to absolute import
        exec(f"import {fallback_path}")
        parts = fallback_path.split('.')
        module = locals()[parts[0]]
        for part in parts[1:]:
            module = getattr(module, part)
        return module
    except (ImportError, KeyError, AttributeError):
        return None

# Import for delayed access to avoid circular imports
BulkTaskManager = None

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessingTask:
    """Represents a task to be processed by the background service."""
    
    def __init__(self, page_id: str, operation: str, parameters: Optional[Dict[str, Any]] = None,
                retries: int = 0, last_error: str = "", priority: int = 1):
        """
        Initialize a processing task.
        
        Args:
            page_id: ID of the newspaper page to process
            operation: Operation to perform (e.g., 'ocr', 'segment', 'extract_articles')
            parameters: Additional parameters for the operation
            retries: Number of retry attempts already made
            last_error: Last error message if the task failed previously
            priority: Priority of the task (lower numbers = higher priority)
        """
        self.page_id = page_id
        self.operation = operation
        self.parameters = parameters or {}
        self.retries = retries
        self.last_error = last_error
        self.priority = priority
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.status = "pending"  # pending, in_progress, completed, failed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for storage."""
        return {
            "page_id": self.page_id,
            "operation": self.operation,
            "parameters": self.parameters,
            "retries": self.retries,
            "last_error": self.last_error,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingTask':
        """Create task from dictionary."""
        task = cls(
            page_id=data["page_id"],
            operation=data["operation"],
            parameters=data.get("parameters", {}),
            retries=data.get("retries", 0),
            last_error=data.get("last_error", ""),
            priority=data.get("priority", 1)
        )
        
        # Parse dates
        if data.get("created_at"):
            task.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            task.completed_at = datetime.fromisoformat(data["completed_at"])
        
        task.status = data.get("status", "pending")
        return task


class BackgroundServiceSignals(QObject):
    """Signals for the background processing service."""
    
    # Service status signals
    started = pyqtSignal()
    stopped = pyqtSignal(dict)  # Stats summary
    paused = pyqtSignal()
    resumed = pyqtSignal()
    
    # Task status signals
    task_started = pyqtSignal(str, object)  # task_id, task
    task_completed = pyqtSignal(str, object, dict)  # task_id, task, result
    task_failed = pyqtSignal(str, object, str)  # task_id, task, error_message
    task_progress = pyqtSignal(str, object, float, str)  # task_id, task, progress, message
    
    # Queue signals
    task_added = pyqtSignal(str, object)  # task_id, task
    task_retry = pyqtSignal(str, object, int)  # task_id, task, retry_count
    queue_updated = pyqtSignal(int)  # queue size
    
    # Status update signal
    status_update = pyqtSignal(dict)  # Status dictionary


class BackgroundProcessingService(QObject if PYQT_AVAILABLE else object):
    """
    Service for processing newspaper pages in the background.
    
    This service runs in a separate thread and processes items from the queue in the
    background. It can be paused, resumed, and stopped by the user. It provides
    real-time progress updates via PyQt signals when available.
    
    Enhanced with bulk operation support for better handling of large batches of tasks.
    """
    
    def __init__(self, db_path: str, base_directory: str, 
                max_retries: int = 3,
                retry_delay: int = 300,
                poll_interval: int = 5,
                max_concurrent_tasks: int = 1,
                batch_size: int = 10):
        """
        Initialize the background processing service.
        
        Args:
            db_path: Path to the repository database
            base_directory: Base directory for file storage
            max_retries: Maximum number of retry attempts for failed tasks
            retry_delay: Delay in seconds before retrying a failed task
            poll_interval: Interval in seconds to poll for new tasks
            max_concurrent_tasks: Maximum number of tasks to process concurrently
            batch_size: Number of tasks to process in a batch (for bulk operations)
        """
        # Initialize QObject if PyQt is available
        if PYQT_AVAILABLE:
            super().__init__()
        
        self.db_path = db_path
        self.base_directory = base_directory
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.poll_interval = poll_interval
        self.max_concurrent_tasks = max_concurrent_tasks
        self.batch_size = batch_size
        
        # Initialize components
        self.db_manager = RepositoryDatabaseManager(db_path)
        self.file_manager = FileManager(base_directory)
        self.ocr_processor = OCRProcessor()
        
        # Task queues
        self.task_queue = queue.PriorityQueue()
        self.in_progress_tasks = {}
        
        # Bulk operation support
        self.bulk_task_manager = None  # Will be initialized later to avoid circular imports
        self.bulk_tasks_paused = set()  # Set of bulk_ids that are paused
        
        # Batch processing support
        self.batch_mode = False  # Whether to process tasks in batches
        self.current_batch = []  # List of tasks in the current batch
        
        # Service control
        self.running = False
        self.paused = False
        self.processing_thread = None
        self.lock = threading.Lock()
        
        # Initialize signals if PyQt is available
        if PYQT_AVAILABLE:
            self.signals = BackgroundServiceSignals()
        else:
            self.signals = None
        
        # Progress callbacks (for non-PyQt usage)
        self.progress_callbacks = []
        
        # Statistics
        self.stats = {
            "tasks_processed": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "tasks_cancelled": 0,
            "batches_processed": 0,
            "bulk_operations_completed": 0,
            "start_time": None,
            "total_processing_time": 0
        }
        
        # Create log directory
        self.log_dir = os.path.join(self.base_directory, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Task cancellation set
        self.cancelled_tasks = set()
        
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
    
    def _init_bulk_task_manager(self) -> None:
        """Initialize the bulk task manager if it's not already initialized."""
        if self.bulk_task_manager is None:
            # Import here to avoid circular imports - global declaration needs to be at top
            global BulkTaskManager
            if BulkTaskManager is None:
                # Try direct imports instead of the helper function
                try:
                    # First try relative import
                    from .bulk_task import BulkTaskManager as BTM
                    BulkTaskManager = BTM
                except ImportError:
                    # Then try absolute import
                    try:
                        from bulk_task import BulkTaskManager as BTM
                        BulkTaskManager = BTM
                    except ImportError:
                        logging.error("Could not import BulkTaskManager")
                        return

            # Only create manager if import was successful
            if BulkTaskManager is not None:
                try:
                    self.bulk_task_manager = BulkTaskManager(self)
                    # Hook into background service if the method exists
                    if hasattr(self.bulk_task_manager, 'hook_into_background_service'):
                        self.bulk_task_manager.hook_into_background_service()
                except Exception as e:
                    import logging
                    logging.error(f"Error initializing BulkTaskManager: {e}")
                    self.bulk_task_manager = None
            else:
                import logging
                logging.error("Failed to import BulkTaskManager. Bulk operations will not be available.")
            
            logger.info("Initialized bulk task manager")
    
    def enable_batch_mode(self, enabled: bool = True) -> None:
        """
        Enable or disable batch processing mode.
        
        In batch mode, tasks are processed in batches rather than one at a time.
        This can be more efficient for bulk operations.
        
        Args:
            enabled: Whether to enable batch mode
        """
        with self.lock:
            self.batch_mode = enabled
            logger.info(f"Batch processing mode {'enabled' if enabled else 'disabled'}")
    
    def register_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback for progress updates.
        
        Args:
            callback: Function to call with progress updates
        """
        self.progress_callbacks.append(callback)
    
    def unregister_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Unregister a progress callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)
    
    def notify_progress(self, update_type: str, data: Dict[str, Any]) -> None:
        """
        Notify all registered callbacks of progress updates and emit signals.
        
        Args:
            update_type: Type of update (e.g., 'task_started', 'task_completed', 'task_failed')
            data: Update data
        """
        update = {
            "type": update_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        # Log the update
        self._log_progress_update(update_type, data)
        
        # Call callbacks for non-PyQt usage
        for callback in self.progress_callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
        
        # Emit signals if PyQt is available
        if PYQT_AVAILABLE and self.signals:
            try:
                # Emit appropriate signal based on update type
                if update_type == "service_started":
                    self.signals.started.emit()
                    self.signals.status_update.emit(data)
                    self.signals.queue_updated.emit(data.get("queue_size", 0))
                
                elif update_type == "service_stopped":
                    self.signals.stopped.emit(data.get("stats", {}))
                    self.signals.status_update.emit(data)
                
                elif update_type == "service_paused":
                    self.signals.paused.emit()
                    self.signals.status_update.emit(data)
                
                elif update_type == "service_resumed":
                    self.signals.resumed.emit()
                    self.signals.status_update.emit(data)
                
                elif update_type == "task_started":
                    task_id = data.get("task_id", "")
                    task = self.in_progress_tasks.get(task_id)
                    if task:
                        self.signals.task_started.emit(task_id, task)
                    self.signals.status_update.emit(data)
                
                elif update_type == "task_completed":
                    task_id = data.get("task_id", "")
                    task = self.in_progress_tasks.get(task_id)
                    result = data.get("result", {})
                    if task:
                        self.signals.task_completed.emit(task_id, task, result)
                    self.signals.status_update.emit(data)
                
                elif update_type == "task_failed":
                    task_id = data.get("task_id", "")
                    task = self.in_progress_tasks.get(task_id)
                    error = data.get("error", "Unknown error")
                    if task:
                        self.signals.task_failed.emit(task_id, task, error)
                    self.signals.status_update.emit(data)
                
                elif update_type == "task_progress":
                    task_id = data.get("page_id", "") + "_" + data.get("operation", "")
                    task = self.in_progress_tasks.get(task_id)
                    progress = data.get("progress", 0.0)
                    message = data.get("message", "")
                    if task:
                        self.signals.task_progress.emit(task_id, task, progress, message)
                    self.signals.status_update.emit(data)
                
                elif update_type == "task_added":
                    task_id = data.get("task_id", "")
                    page_id = data.get("page_id", "")
                    operation = data.get("operation", "")
                    priority = data.get("priority", 1)
                    
                    # Create a task object for the signal
                    task = ProcessingTask(
                        page_id=page_id,
                        operation=operation,
                        priority=priority
                    )
                    
                    self.signals.task_added.emit(task_id, task)
                    self.signals.queue_updated.emit(data.get("queue_size", 0))
                    self.signals.status_update.emit(data)
                
                elif update_type == "task_retry_scheduled":
                    task_id = data.get("task_id", "")
                    task = ProcessingTask(
                        page_id=data.get("page_id", ""),
                        operation=data.get("operation", ""),
                        retries=data.get("retries", 0),
                        last_error=data.get("error", ""),
                        priority=data.get("priority", 1)
                    )
                    
                    self.signals.task_retry.emit(task_id, task, data.get("retries", 0))
                    self.signals.status_update.emit(data)
                
            except Exception as e:
                logger.error(f"Error emitting signal for {update_type}: {e}")
                logger.error(traceback.format_exc())
    
    def _log_progress_update(self, update_type: str, data: Dict[str, Any]) -> None:
        """
        Log progress updates to a file.
        
        Args:
            update_type: Type of update
            data: Update data
        """
        try:
            # Create a log filename based on date
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = os.path.join(self.log_dir, f"processing_log_{today}.jsonl")
            
            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": update_type,
                "data": data
            }
            
            # Append to log file
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            logger.error(f"Error logging progress update: {e}")
            # Don't raise - this is a non-critical error
    
    def start(self) -> None:
        """Start the background processing service."""
        with self.lock:
            if self.running:
                logger.warning("Background service is already running")
                return
            
            self.running = True
            self.paused = False
            self.stats["start_time"] = datetime.now()
            
            # Load tasks from database
            self._load_tasks_from_database()
            
            # Start processing thread
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True  # Make thread a daemon so it exits when the main program exits
            )
            self.processing_thread.start()
            
            logger.info("Background processing service started")
            self.notify_progress("service_started", {
                "queue_size": self.task_queue.qsize(),
                "stats": self.stats
            })
    
    def stop(self) -> None:
        """Stop the background processing service."""
        with self.lock:
            if not self.running:
                logger.warning("Background service is not running")
                return
            
            logger.info("Stopping background processing service...")
            self.running = False
            
            # Wait for the processing thread to finish
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(timeout=5.0)
            
            # Save in-progress tasks back to the database
            self._save_in_progress_tasks()
            
            logger.info("Background processing service stopped")
            self.notify_progress("service_stopped", {
                "stats": self.stats
            })
    
    def pause(self) -> None:
        """Pause the background processing service."""
        with self.lock:
            if not self.running:
                logger.warning("Background service is not running")
                return
            
            if self.paused:
                logger.warning("Background service is already paused")
                return
            
            self.paused = True
            logger.info("Background processing service paused")
            self.notify_progress("service_paused", {
                "queue_size": self.task_queue.qsize(),
                "in_progress": len(self.in_progress_tasks),
                "stats": self.stats
            })
    
    def resume(self) -> None:
        """Resume the background processing service."""
        with self.lock:
            if not self.running:
                logger.warning("Background service is not running")
                return
            
            if not self.paused:
                logger.warning("Background service is not paused")
                return
            
            self.paused = False
            logger.info("Background processing service resumed")
            self.notify_progress("service_resumed", {
                "queue_size": self.task_queue.qsize(),
                "stats": self.stats
            })
    
    def add_task(self, page_id: str, operation: str, 
                parameters: Optional[Dict[str, Any]] = None,
                priority: int = 1,
                bulk_id: str = None) -> str:
        """
        Add a task to the processing queue.
        
        Args:
            page_id: ID of the newspaper page to process
            operation: Operation to perform
            parameters: Additional parameters for the operation
            priority: Priority of the task (lower numbers = higher priority)
            bulk_id: ID of the bulk task this task belongs to (if any)
            
        Returns:
            Task ID
        """
        # Make sure parameters is a dictionary
        if parameters is None:
            parameters = {}
        
        # If this is part of a bulk operation, store the bulk_id in parameters
        if bulk_id:
            parameters["bulk_id"] = bulk_id
        
        task = ProcessingTask(
            page_id=page_id,
            operation=operation,
            parameters=parameters,
            priority=priority
        )
        
        # Generate task ID
        task_id = f"{page_id}_{operation}"
        
        # Check if task is already in cancelled set
        if task_id in self.cancelled_tasks:
            logger.info(f"Task {task_id} was previously cancelled, removing from cancelled set")
            self.cancelled_tasks.remove(task_id)
        
        # Add to database
        db_task_id = self.db_manager.add_to_processing_queue(
            page_id=page_id,
            operation=operation,
            parameters=json.dumps(parameters) if parameters else None,
            priority=priority
        )
        
        if not db_task_id:
            logger.error(f"Failed to add task to database: {page_id} - {operation}")
            return None
        
        # Add to memory queue if service is running
        if self.running:
            self.task_queue.put((priority, task))
            logger.info(f"Task added to queue: {page_id} - {operation} (priority {priority})")
            
            # Log detailed information
            self._log_task_details(task_id, "added", {
                "page_id": page_id,
                "operation": operation,
                "parameters": parameters,
                "priority": priority,
                "bulk_id": bulk_id
            })
            
            # Include bulk_id in progress notification if available
            progress_data = {
                "task_id": task_id,
                "page_id": page_id,
                "operation": operation,
                "priority": priority,
                "queue_size": self.task_queue.qsize()
            }
            
            if bulk_id:
                progress_data["bulk_id"] = bulk_id
            
            self.notify_progress("task_added", progress_data)
        
        return task_id
    
    def add_bulk_tasks(self, tasks: List[Tuple[str, str, Dict[str, Any], int]], 
                      bulk_id: str = None) -> List[str]:
        """
        Add multiple tasks to the processing queue as part of a bulk operation.
        
        Args:
            tasks: List of tuples (page_id, operation, parameters, priority)
            bulk_id: ID of the bulk task these tasks belong to (if any)
            
        Returns:
            List of task IDs
        """
        task_ids = []
        
        with self.lock:
            # First, add all tasks to the database
            for page_id, operation, parameters, priority in tasks:
                task_id = self.add_task(
                    page_id=page_id,
                    operation=operation,
                    parameters=parameters,
                    priority=priority,
                    bulk_id=bulk_id
                )
                
                if task_id:
                    task_ids.append(task_id)
            
            # Log the bulk addition
            logger.info(f"Added {len(task_ids)} tasks to queue as part of bulk operation")
            
            # Notify progress listeners if available
            if bulk_id:
                self.notify_progress("bulk_tasks_added", {
                    "bulk_id": bulk_id,
                    "task_count": len(task_ids),
                    "queue_size": self.task_queue.qsize()
                })
            
            return task_ids
        
    def _log_task_details(self, task_id: str, action: str, details: Dict[str, Any]) -> None:
        """
        Log detailed information about a task.
        
        Args:
            task_id: Task ID
            action: Action being performed (e.g., "added", "completed", "failed")
            details: Task details
        """
        try:
            # Create a log filename for tasks
            log_file = os.path.join(self.log_dir, "task_details.jsonl")
            
            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "task_id": task_id,
                "action": action,
                "details": details
            }
            
            # Append to log file
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            logger.error(f"Error logging task details: {e}")
            # Don't raise - this is a non-critical error
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get the current status of the processing queue.
        
        Returns:
            Dictionary with queue status information
        """
        with self.lock:
            return {
                "running": self.running,
                "paused": self.paused,
                "queue_size": self.task_queue.qsize(),
                "in_progress": len(self.in_progress_tasks),
                "stats": self.stats
            }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a specific task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Dictionary with task status information
        """
        return self.db_manager.get_processing_queue_item(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task (pending or in-progress).
        
        Args:
            task_id: Task ID
            
        Returns:
            True if task was canceled, False otherwise
        """
        cancelled = False
        
        with self.lock:
            # Check if the task is in-progress
            if task_id in self.in_progress_tasks:
                # We can't stop an in-progress task immediately, but we can mark it
                # as cancelled so it doesn't retry on failure
                logger.info(f"Marking in-progress task {task_id} for cancellation")
                self.cancelled_tasks.add(task_id)
                cancelled = True
            
            # Try to remove from the queue if it's pending
            else:
                # First check in the database
                if self.db_manager.remove_from_processing_queue(task_id):
                    logger.info(f"Task {task_id} removed from database")
                    cancelled = True
                
                # Mark as cancelled in case it's added again in the future
                self.cancelled_tasks.add(task_id)
                
                # Try to remove from the task queue
                # Note: This is an expensive O(n) operation for PriorityQueue
                # but it's the only way to remove a task from the queue
                if self.running:
                    try:
                        # Extract all items into a temporary list
                        temp_items = []
                        while not self.task_queue.empty():
                            priority, task = self.task_queue.get()
                            current_task_id = f"{task.page_id}_{task.operation}"
                            if current_task_id != task_id:
                                temp_items.append((priority, task))
                        
                        # Put back everything except the task to cancel
                        for item in temp_items:
                            self.task_queue.put(item)
                        
                        # If we had fewer items than expected, it was probably in the queue
                        if len(temp_items) < self.task_queue.qsize() + 1:
                            cancelled = True
                    
                    except Exception as e:
                        logger.error(f"Error removing task {task_id} from queue: {e}")
                        # Put back all items to restore the queue
                        for item in temp_items:
                            self.task_queue.put(item)
        
        if cancelled:
            # Update statistics
            self.stats["tasks_cancelled"] += 1
            
            # Log the cancellation
            self._log_task_details(task_id, "cancelled", {
                "timestamp": datetime.now().isoformat()
            })
            
            # Notify listeners
            self.notify_progress("task_cancelled", {
                "task_id": task_id,
                "queue_size": self.task_queue.qsize() if self.running else 0
            })
            
            return True
        
        return False
    
    def _load_tasks_from_database(self) -> None:
        """Load pending tasks from the database into the memory queue."""
        pending_tasks = self.db_manager.get_pending_processing_queue_items()
        
        for task_data in pending_tasks:
            task = ProcessingTask(
                page_id=task_data["page_id"],
                operation=task_data["operation"],
                parameters=json.loads(task_data["parameters"]) if task_data["parameters"] else {},
                retries=task_data["retries"],
                last_error=task_data["last_error"],
                priority=task_data["priority"]
            )
            
            # Add to queue
            self.task_queue.put((task.priority, task))
        
        logger.info(f"Loaded {len(pending_tasks)} pending tasks from database")
    
    def _save_in_progress_tasks(self) -> None:
        """Save in-progress tasks back to the database."""
        for task_id, task in self.in_progress_tasks.items():
            # Update task status in database
            self.db_manager.update_processing_queue_item(
                item_id=task_id,
                status="pending",  # Reset to pending
                last_error="Task interrupted when service stopped"
            )
        
        logger.info(f"Saved {len(self.in_progress_tasks)} in-progress tasks back to database")
        self.in_progress_tasks.clear()
    
    def _processing_loop(self) -> None:
        """Main processing loop for the background service."""
        while self.running:
            try:
                # Check if paused
                if self.paused:
                    time.sleep(1)
                    continue
                
                # Check if we can process more tasks
                if len(self.in_progress_tasks) >= self.max_concurrent_tasks:
                    time.sleep(1)
                    continue
                
                # Determine whether to use batch mode
                if self.batch_mode and len(self.in_progress_tasks) == 0:
                    # Try to process a batch of tasks
                    self._process_task_batch()
                else:
                    # Process a single task
                    self._process_next_task()
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                logger.error(traceback.format_exc())
                time.sleep(5)  # Avoid tight loop in case of repeated errors
    
    def _process_next_task(self) -> None:
        """Process the next task from the queue."""
        try:
            # Get next task from queue
            priority, task = self.task_queue.get(block=True, timeout=self.poll_interval)
            task_id = f"{task.page_id}_{task.operation}"
            
            # Check if this task is part of a paused bulk operation
            bulk_id = task.parameters.get("bulk_id")
            if bulk_id and bulk_id in self.bulk_tasks_paused:
                # Put the task back in the queue and skip it
                self.task_queue.put((priority, task))
                logger.debug(f"Skipping task {task_id} as it belongs to paused bulk operation {bulk_id}")
                return
            
            # Mark task as in-progress
            self.in_progress_tasks[task_id] = task
            task.started_at = datetime.now()
            task.status = "in_progress"
            
            # Update database
            self.db_manager.update_processing_queue_item(
                item_id=task_id,
                status="in_progress",
                started_at=task.started_at.isoformat()
            )
            
            logger.info(f"Processing task: {task.page_id} - {task.operation}")
            progress_data = {
                "task_id": task_id,
                "page_id": task.page_id,
                "operation": task.operation
            }
            
            # Include bulk_id in progress notification if available
            if bulk_id:
                progress_data["bulk_id"] = bulk_id
            
            self.notify_progress("task_started", progress_data)
            
            # Process task in a separate thread to avoid blocking
            processing_thread = threading.Thread(
                target=self._process_task,
                args=(task_id, task),
                daemon=True
            )
            processing_thread.start()
            
        except queue.Empty:
            # No tasks in queue, check database for new tasks
            self._check_database_for_new_tasks()
    
    def _process_task_batch(self) -> None:
        """Process a batch of tasks from the queue."""
        batch = []
        batch_by_bulk = {}  # Group tasks by bulk_id for better reporting
        
        try:
            # Try to collect a batch of tasks
            for _ in range(self.batch_size):
                try:
                    priority, task = self.task_queue.get(block=False)
                    task_id = f"{task.page_id}_{task.operation}"
                    
                    # Check if this task is part of a paused bulk operation
                    bulk_id = task.parameters.get("bulk_id")
                    if bulk_id and bulk_id in self.bulk_tasks_paused:
                        # Put the task back in the queue and skip it
                        self.task_queue.put((priority, task))
                        continue
                    
                    # Add to batch
                    batch.append((task_id, task))
                    
                    # Group by bulk_id if available
                    if bulk_id:
                        if bulk_id not in batch_by_bulk:
                            batch_by_bulk[bulk_id] = []
                        batch_by_bulk[bulk_id].append(task_id)
                    
                except queue.Empty:
                    # No more tasks available
                    break
            
            if not batch:
                # No tasks found, check database
                self._check_database_for_new_tasks()
                return
            
            logger.info(f"Processing batch of {len(batch)} tasks")
            
            # Mark all tasks as in-progress
            with self.lock:
                for task_id, task in batch:
                    self.in_progress_tasks[task_id] = task
                    task.started_at = datetime.now()
                    task.status = "in_progress"
                    
                    # Update database
                    self.db_manager.update_processing_queue_item(
                        item_id=task_id,
                        status="in_progress",
                        started_at=task.started_at.isoformat()
                    )
            
            # Notify about batch start
            self.notify_progress("batch_started", {
                "batch_size": len(batch),
                "bulk_operations": list(batch_by_bulk.keys())
            })
            
            # Process each task in the batch with its own thread
            threads = []
            for task_id, task in batch:
                # Notify task started
                progress_data = {
                    "task_id": task_id,
                    "page_id": task.page_id,
                    "operation": task.operation,
                    "batch": True
                }
                
                # Include bulk_id if available
                bulk_id = task.parameters.get("bulk_id")
                if bulk_id:
                    progress_data["bulk_id"] = bulk_id
                
                self.notify_progress("task_started", progress_data)
                
                # Start processing thread
                thread = threading.Thread(
                    target=self._process_task,
                    args=(task_id, task),
                    daemon=True
                )
                thread.start()
                threads.append(thread)
            
            # Optional: Wait for all threads to complete if you want batch completion notification
            # This would make the main loop wait, so we'll leave it commented out
            # for thread in threads:
            #     thread.join()
            
            # Update batch statistics
            self.stats["batches_processed"] += 1
            
        except Exception as e:
            logger.error(f"Error processing task batch: {e}")
            logger.error(traceback.format_exc())
    
    def _check_database_for_new_tasks(self) -> None:
        """Check database for new tasks and add them to the queue."""
        try:
            pending_tasks = self.db_manager.get_pending_processing_queue_items()
            
            for task_data in pending_tasks:
                task_id = f"{task_data['page_id']}_{task_data['operation']}"
                
                # Skip if already in queue or in progress
                if task_id in self.in_progress_tasks:
                    continue
                
                # Check if already in queue (more complex)
                skip = False
                for _, existing_task in list(self.task_queue.queue):
                    if existing_task.page_id == task_data["page_id"] and existing_task.operation == task_data["operation"]:
                        skip = True
                        break
                
                if skip:
                    continue
                
                # Create task and add to queue
                task = ProcessingTask(
                    page_id=task_data["page_id"],
                    operation=task_data["operation"],
                    parameters=json.loads(task_data["parameters"]) if task_data["parameters"] else {},
                    retries=task_data["retries"],
                    last_error=task_data["last_error"],
                    priority=task_data["priority"]
                )
                
                self.task_queue.put((task.priority, task))
                logger.info(f"Added new task from database: {task.page_id} - {task.operation}")
        
        except Exception as e:
            logger.error(f"Error checking database for new tasks: {e}")
    
    def _process_task(self, task_id: str, task: ProcessingTask) -> None:
        """
        Process a task and update its status.
        
        Args:
            task_id: Task ID
            task: Task to process
        """
        success = False
        error_message = ""
        result = None
        
        # Check if task is part of a bulk operation
        bulk_id = task.parameters.get("bulk_id")
        
        # If part of a bulk operation, check if it's paused
        if bulk_id and bulk_id in self.bulk_tasks_paused:
            # Put the task back in the queue and return
            logger.info(f"Skipping task {task_id} as it belongs to paused bulk operation {bulk_id}")
            with self.lock:
                if task_id in self.in_progress_tasks:
                    del self.in_progress_tasks[task_id]
                self.task_queue.put((task.priority, task))
                
                # Update database status back to pending
                self.db_manager.update_processing_queue_item(
                    item_id=task_id,
                    status="pending"
                )
            return
        
        try:
            # Process based on operation
            if task.operation == "ocr":
                result = self._process_ocr_task(task)
            elif task.operation == "segment":
                result = self._process_segment_task(task)
            elif task.operation == "extract_articles":
                result = self._process_extract_articles_task(task)
            else:
                raise ValueError(f"Unknown operation: {task.operation}")
            
            success = True
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error processing task {task_id}: {e}")
            logger.error(traceback.format_exc())
        
        # Update task status
        with self.lock:
            # Remove from in-progress tasks
            if task_id in self.in_progress_tasks:
                del self.in_progress_tasks[task_id]
            
            # Update statistics
            self.stats["tasks_processed"] += 1
            
            if success:
                # Task completed successfully
                task.status = "completed"
                task.completed_at = datetime.now()
                self.stats["tasks_succeeded"] += 1
                
                # Update database
                self.db_manager.update_processing_queue_item(
                    item_id=task_id,
                    status="completed",
                    completed_at=task.completed_at.isoformat(),
                    result=json.dumps(result) if result else None
                )
                
                logger.info(f"Task completed successfully: {task_id}")
                
                # Prepare notification data
                notify_data = {
                    "task_id": task_id,
                    "page_id": task.page_id,
                    "operation": task.operation,
                    "processing_time": (task.completed_at - task.started_at).total_seconds(),
                    "result": result
                }
                
                # Include bulk_id if available
                if bulk_id:
                    notify_data["bulk_id"] = bulk_id
                
                self.notify_progress("task_completed", notify_data)
                
                # Update bulk task status if applicable
                if bulk_id and self.bulk_task_manager:
                    self.bulk_task_manager.update_task_status(task_id, "completed")
                
            else:
                # Task failed
                task.last_error = error_message
                task.retries += 1
                
                if task.retries >= self.max_retries:
                    # Max retries reached, mark as failed
                    task.status = "failed"
                    task.completed_at = datetime.now()
                    self.stats["tasks_failed"] += 1
                    
                    # Update database
                    self.db_manager.update_processing_queue_item(
                        item_id=task_id,
                        status="failed",
                        completed_at=task.completed_at.isoformat(),
                        last_error=error_message
                    )
                    
                    logger.error(f"Task failed after {task.retries} retries: {task_id}")
                    
                    # Prepare notification data
                    notify_data = {
                        "task_id": task_id,
                        "page_id": task.page_id,
                        "operation": task.operation,
                        "retries": task.retries,
                        "error": error_message
                    }
                    
                    # Include bulk_id if available
                    if bulk_id:
                        notify_data["bulk_id"] = bulk_id
                    
                    self.notify_progress("task_failed", notify_data)
                    
                    # Update bulk task status if applicable
                    if bulk_id and self.bulk_task_manager:
                        self.bulk_task_manager.update_task_status(task_id, "failed", error_message)
                    
                else:
                    # Retry task
                    task.status = "pending"
                    self.stats["tasks_retried"] += 1
                    
                    # Update database
                    self.db_manager.update_processing_queue_item(
                        item_id=task_id,
                        status="pending",
                        retries=task.retries,
                        last_error=error_message
                    )
                    
                    # Add back to queue with delay and increased priority
                    retry_task = ProcessingTask(
                        page_id=task.page_id,
                        operation=task.operation,
                        parameters=task.parameters,
                        retries=task.retries,
                        last_error=error_message,
                        priority=task.priority + 1  # Lower priority for retries
                    )
                    
                    # Schedule retry after delay
                    retry_thread = threading.Thread(
                        target=self._schedule_retry,
                        args=(retry_task,),
                        daemon=True
                    )
                    retry_thread.start()
                    
                    logger.info(f"Task scheduled for retry: {task_id} (attempt {task.retries}/{self.max_retries})")
                    
                    # Prepare notification data
                    notify_data = {
                        "task_id": task_id,
                        "page_id": task.page_id,
                        "operation": task.operation,
                        "retries": task.retries,
                        "max_retries": self.max_retries,
                        "error": error_message,
                        "retry_delay": self.retry_delay
                    }
                    
                    # Include bulk_id if available
                    if bulk_id:
                        notify_data["bulk_id"] = bulk_id
                    
                    self.notify_progress("task_retry_scheduled", notify_data)
    
    def _schedule_retry(self, task: ProcessingTask) -> None:
        """
        Schedule a task for retry after delay.
        
        Args:
            task: Task to retry
        """
        # Sleep for retry delay
        time.sleep(self.retry_delay)
        
        # Add back to queue
        with self.lock:
            if self.running:
                self.task_queue.put((task.priority, task))
                logger.info(f"Task added back to queue for retry: {task.page_id} - {task.operation}")
    
    def _process_ocr_task(self, task: ProcessingTask) -> Dict[str, Any]:
        """
        Process an OCR task.
        
        Args:
            task: Task to process
            
        Returns:
            Result dictionary
        """
        # Get page information from database
        page_data = self.db_manager.get_newspaper_page(task.page_id)
        if not page_data:
            raise ValueError(f"Page {task.page_id} not found in database")
        
        # Get image path
        image_path = page_data.get("image_path")
        if not image_path or not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")
        
        # Progress update
        self.notify_progress("task_progress", {
            "page_id": task.page_id,
            "operation": task.operation,
            "progress": 0.1,
            "message": "Starting OCR processing"
        })
        
        # Process OCR
        ocr_result = self.ocr_processor.process_page(image_path)
        
        # Progress update
        self.notify_progress("task_progress", {
            "page_id": task.page_id,
            "operation": task.operation,
            "progress": 0.8,
            "message": "OCR processing completed, saving results"
        })
        
        # Update page with OCR text and HOCR paths
        self.db_manager.update_newspaper_page(
            page_id=task.page_id,
            ocr_text=ocr_result.text,
            ocr_hocr_path=ocr_result.hocr_path
        )
        
        return {
            "ocr_text_length": len(ocr_result.text),
            "hocr_path": ocr_result.hocr_path
        }
    
    def _process_segment_task(self, task: ProcessingTask) -> Dict[str, Any]:
        """
        Process a page segmentation task.
        
        Args:
            task: Task to process
            
        Returns:
            Result dictionary
        """
        # Get page information from database
        page_data = self.db_manager.get_newspaper_page(task.page_id)
        if not page_data:
            raise ValueError(f"Page {task.page_id} not found in database")
        
        # Get required paths
        image_path = page_data.get("image_path")
        ocr_hocr_path = page_data.get("ocr_hocr_path")
        
        if not image_path or not os.path.exists(image_path):
            raise ValueError(f"Image file not found: {image_path}")
        
        if not ocr_hocr_path or not os.path.exists(ocr_hocr_path):
            raise ValueError(f"HOCR file not found: {ocr_hocr_path}")
        
        # Progress update
        self.notify_progress("task_progress", {
            "page_id": task.page_id,
            "operation": task.operation,
            "progress": 0.1,
            "message": "Starting page segmentation"
        })
        
        # Perform layout analysis
        segments = self.ocr_processor.analyze_layout_from_hocr(
            hocr_path=ocr_hocr_path,
            image_path=image_path
        )
        
        # Progress update
        self.notify_progress("task_progress", {
            "page_id": task.page_id,
            "operation": task.operation,
            "progress": 0.5,
            "message": f"Identified {len(segments)} segments, saving to database"
        })
        
        # Save segments to database
        segment_ids = []
        for i, segment in enumerate(segments):
            # Progress update for long operations
            if i % 5 == 0:
                progress = 0.5 + (i / len(segments) * 0.5)
                self.notify_progress("task_progress", {
                    "page_id": task.page_id,
                    "operation": task.operation,
                    "progress": progress,
                    "message": f"Saving segment {i+1}/{len(segments)}"
                })
            
            segment_id = self.db_manager.add_article_segment(
                page_id=task.page_id,
                segment_type=segment.segment_type,
                content=segment.text,
                position_data=json.dumps(segment.position),
                confidence=segment.confidence,
                image_path=segment.image_path
            )
            segment_ids.append(segment_id)
        
        return {
            "segments_count": len(segments),
            "segment_ids": segment_ids
        }
    
    def _process_extract_articles_task(self, task: ProcessingTask) -> Dict[str, Any]:
        """
        Process an article extraction task.
        
        Args:
            task: Task to process
            
        Returns:
            Result dictionary
        """
        # Get page information from database
        page_data = self.db_manager.get_newspaper_page(task.page_id)
        if not page_data:
            raise ValueError(f"Page {task.page_id} not found in database")
        
        # Get segments for the page
        segments = self.db_manager.get_segments_for_page(task.page_id)
        
        if not segments:
            raise ValueError(f"No segments found for page {task.page_id}")
        
        # Progress update
        self.notify_progress("task_progress", {
            "page_id": task.page_id,
            "operation": task.operation,
            "progress": 0.1,
            "message": f"Extracting articles from {len(segments)} segments"
        })
        
        # Group segments into articles based on proximity and content
        # This is a simplified version - a real implementation would need more sophisticated logic
        articles = []
        current_article = []
        current_type = None
        
        for i, segment in enumerate(segments):
            # For simplicity, group by segment type
            if current_type is None:
                current_type = segment["segment_type"]
                current_article.append(segment)
            elif segment["segment_type"] == current_type:
                current_article.append(segment)
            else:
                # New segment type, save the current article and start a new one
                if current_article:
                    articles.append(current_article)
                current_article = [segment]
                current_type = segment["segment_type"]
            
            # Progress update
            if i % 10 == 0:
                progress = 0.1 + (i / len(segments) * 0.5)
                self.notify_progress("task_progress", {
                    "page_id": task.page_id,
                    "operation": task.operation,
                    "progress": progress,
                    "message": f"Processing segment {i+1}/{len(segments)}"
                })
        
        # Add the last article if there's one in progress
        if current_article:
            articles.append(current_article)
        
        # Progress update
        self.notify_progress("task_progress", {
            "page_id": task.page_id,
            "operation": task.operation,
            "progress": 0.7,
            "message": f"Identified {len(articles)} potential articles, saving to database"
        })
        
        # Save articles to database
        article_ids = []
        for i, article_segments in enumerate(articles):
            # Extract article metadata
            segment_ids = [s["segment_id"] for s in article_segments]
            article_text = "\n\n".join([s["content"] for s in article_segments])
            article_type = article_segments[0]["segment_type"]
            
            # Create a title from the first few words
            title_words = article_text.split()[:10]
            title = " ".join(title_words) + "..."
            
            # Progress update
            if i % 5 == 0:
                progress = 0.7 + (i / len(articles) * 0.3)
                self.notify_progress("task_progress", {
                    "page_id": task.page_id,
                    "operation": task.operation,
                    "progress": progress,
                    "message": f"Saving article {i+1}/{len(articles)}"
                })
            
            # Save article
            article_id = self.db_manager.add_newspaper_article(
                page_id=task.page_id,
                title=title,
                content=article_text,
                article_type=article_type,
                segment_ids=json.dumps(segment_ids),
                metadata=json.dumps({
                    "segments_count": len(article_segments),
                    "length": len(article_text)
                })
            )
            article_ids.append(article_id)
        
        return {
            "articles_count": len(articles),
            "article_ids": article_ids
        }


    # Bulk operation methods
    
    def create_bulk_task(self, operation_type: str, description: str, 
                         parameters: Optional[Dict[str, Any]] = None,
                         priority: int = 1) -> str:
        """
        Create a new bulk task.
        
        Args:
            operation_type: Type of bulk operation (e.g., 'download', 'ocr')
            description: Human-readable description of the task
            parameters: Additional parameters for the bulk operation
            priority: Priority of the bulk task (lower numbers = higher priority)
            
        Returns:
            Bulk task ID
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        # Use the bulk task manager to create the task
        from .bulk_task import BulkOperationType
        try:
            # Convert string to enum
            op_type = BulkOperationType(operation_type)
        except ValueError:
            # Default to DOWNLOAD if unknown
            logger.warning(f"Unknown operation type: {operation_type}, defaulting to DOWNLOAD")
            op_type = BulkOperationType.DOWNLOAD
        
        return self.bulk_task_manager.create_bulk_task(
            operation_type=op_type,
            description=description,
            parameters=parameters,
            priority=priority
        )
    
    def add_task_to_bulk(self, bulk_id: str, page_id: str, operation: str, 
                         parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a task to a bulk operation.
        
        Args:
            bulk_id: ID of the bulk task to add to
            page_id: ID of the newspaper page to process
            operation: Operation to perform
            parameters: Additional parameters for the operation
            
        Returns:
            Task ID
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        return self.bulk_task_manager.add_task_to_bulk(
            bulk_id=bulk_id,
            page_id=page_id,
            operation=operation,
            parameters=parameters
        )
    
    def add_tasks_to_bulk(self, bulk_id: str, 
                          tasks: List[Tuple[str, str, Dict[str, Any]]]) -> List[str]:
        """
        Add multiple tasks to a bulk operation.
        
        Args:
            bulk_id: ID of the bulk task to add to
            tasks: List of tuples (page_id, operation, parameters)
            
        Returns:
            List of task IDs
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        return self.bulk_task_manager.add_tasks_to_bulk(
            bulk_id=bulk_id,
            tasks=tasks
        )
    
    def get_bulk_task(self, bulk_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a bulk task status.
        
        Args:
            bulk_id: ID of the bulk task
            
        Returns:
            Dictionary with bulk task status or None if not found
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        bulk_task = self.bulk_task_manager.get_bulk_task(bulk_id)
        if bulk_task:
            return bulk_task.get_status_summary()
        return None
    
    def get_all_bulk_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all bulk tasks.
        
        Returns:
            List of bulk task summaries
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        return self.bulk_task_manager.get_all_bulk_tasks()
    
    def pause_bulk_task(self, bulk_id: str) -> bool:
        """
        Pause a bulk task.
        
        Args:
            bulk_id: ID of the bulk task to pause
            
        Returns:
            True if successful, False otherwise
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        # Add to paused set
        with self.lock:
            self.bulk_tasks_paused.add(bulk_id)
        
        # Pause the task in the manager
        return self.bulk_task_manager.pause_bulk_task(bulk_id)
    
    def resume_bulk_task(self, bulk_id: str) -> bool:
        """
        Resume a paused bulk task.
        
        Args:
            bulk_id: ID of the bulk task to resume
            
        Returns:
            True if successful, False otherwise
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        # Remove from paused set
        with self.lock:
            if bulk_id in self.bulk_tasks_paused:
                self.bulk_tasks_paused.remove(bulk_id)
        
        # Resume the task in the manager
        return self.bulk_task_manager.resume_bulk_task(bulk_id)
    
    def cancel_bulk_task(self, bulk_id: str) -> bool:
        """
        Cancel a bulk task.
        
        Args:
            bulk_id: ID of the bulk task to cancel
            
        Returns:
            True if successful, False otherwise
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        # Remove from paused set
        with self.lock:
            if bulk_id in self.bulk_tasks_paused:
                self.bulk_tasks_paused.remove(bulk_id)
        
        # Cancel the task in the manager
        return self.bulk_task_manager.cancel_bulk_task(bulk_id)
    
    def retry_failed_bulk_tasks(self, bulk_id: str) -> int:
        """
        Retry all failed tasks in a bulk operation.
        
        Args:
            bulk_id: ID of the bulk task
            
        Returns:
            Number of tasks requeued for retry
        """
        # Initialize bulk task manager if needed
        self._init_bulk_task_manager()
        
        return self.bulk_task_manager.retry_failed_tasks(bulk_id)


class BackgroundServiceManager:
    """
    Manager for the background processing service.
    
    This class provides a singleton-like interface to the background service
    to ensure only one instance is running at a time.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls, db_path: str = None, base_directory: str = None,
                    max_concurrent_tasks: int = 1, batch_size: int = 10) -> BackgroundProcessingService:
        """
        Get the singleton instance of the background service.
        
        Args:
            db_path: Path to the repository database
            base_directory: Base directory for file storage
            max_concurrent_tasks: Maximum number of tasks to process concurrently
            batch_size: Number of tasks to process in a batch
            
        Returns:
            BackgroundProcessingService instance
        """
        if cls._instance is None:
            if db_path is None or base_directory is None:
                raise ValueError("db_path and base_directory must be specified when creating the service")
            
            cls._instance = BackgroundProcessingService(
                db_path=db_path, 
                base_directory=base_directory,
                max_concurrent_tasks=max_concurrent_tasks,
                batch_size=batch_size
            )
            
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance."""
        if cls._instance:
            if cls._instance.running:
                cls._instance.stop()
            cls._instance = None


# UI Integration Helper Functions

def create_service_control_widget(parent, service: BackgroundProcessingService, include_bulk_controls: bool = True):
    """
    Create a widget for controlling the background service.
    
    Args:
        parent: Parent widget
        service: BackgroundProcessingService instance
        include_bulk_controls: Whether to include controls for bulk operations
        
    Returns:
        QWidget with service controls
    """
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QLabel, QProgressBar, QGroupBox)
    from PyQt5.QtCore import QTimer
    
    control_widget = QWidget(parent)
    layout = QVBoxLayout(control_widget)
    
    # Status section
    status_group = QGroupBox("Processing Service Status")
    status_layout = QVBoxLayout()
    
    status_label = QLabel("Service is not running")
    queue_label = QLabel("Queue: 0 tasks")
    progress_label = QLabel("Processing: 0 tasks")
    stats_label = QLabel("Processed: 0 | Succeeded: 0 | Failed: 0 | Retried: 0")
    
    status_layout.addWidget(status_label)
    status_layout.addWidget(queue_label)
    status_layout.addWidget(progress_label)
    status_layout.addWidget(stats_label)
    
    status_group.setLayout(status_layout)
    layout.addWidget(status_group)
    
    # Control buttons
    button_layout = QHBoxLayout()
    
    start_button = QPushButton("Start Service")
    stop_button = QPushButton("Stop Service")
    pause_button = QPushButton("Pause Service")
    resume_button = QPushButton("Resume Service")
    
    # Disable buttons initially
    stop_button.setEnabled(False)
    pause_button.setEnabled(False)
    resume_button.setEnabled(False)
    
    button_layout.addWidget(start_button)
    button_layout.addWidget(stop_button)
    button_layout.addWidget(pause_button)
    button_layout.addWidget(resume_button)
    
    layout.addLayout(button_layout)
    
    # Current task progress
    progress_group = QGroupBox("Current Task Progress")
    progress_layout = QVBoxLayout()
    
    task_label = QLabel("No task in progress")
    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)
    
    progress_layout.addWidget(task_label)
    progress_layout.addWidget(progress_bar)
    
    progress_group.setLayout(progress_layout)
    layout.addWidget(progress_group)
    
    # Batch processing controls
    batch_group = QGroupBox("Batch Processing")
    batch_layout = QHBoxLayout()
    
    batch_mode_button = QPushButton("Enable Batch Mode")
    batch_mode_button.setCheckable(True)
    batch_mode_button.toggled.connect(lambda checked: toggle_batch_mode(checked))
    
    batch_layout.addWidget(batch_mode_button)
    batch_group.setLayout(batch_layout)
    layout.addWidget(batch_group)
    
    # Bulk operation controls (optional)
    bulk_widget = None
    if include_bulk_controls:
        from PyQt5.QtWidgets import (QTableWidget, QTableWidgetItem, QComboBox, 
                                    QHeaderView, QAbstractItemView)
        
        bulk_group = QGroupBox("Bulk Operations")
        bulk_layout = QVBoxLayout()
        
        # Table for listing bulk tasks
        bulk_table = QTableWidget()
        bulk_table.setColumnCount(7)
        bulk_table.setHorizontalHeaderLabels([
            "ID", "Description", "Status", "Progress", 
            "Tasks", "Started", "Actions"
        ])
        bulk_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        bulk_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        bulk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Task buttons
        refresh_button = QPushButton("Refresh List")
        refresh_button.clicked.connect(lambda: refresh_bulk_tasks())
        
        bulk_layout.addWidget(bulk_table)
        bulk_layout.addWidget(refresh_button)
        
        bulk_group.setLayout(bulk_layout)
        layout.addWidget(bulk_group)
        
        bulk_widget = {
            "table": bulk_table,
            "refresh_button": refresh_button
        }
    
    # Connect button actions
    start_button.clicked.connect(lambda: start_service())
    stop_button.clicked.connect(lambda: stop_service())
    pause_button.clicked.connect(lambda: pause_service())
    resume_button.clicked.connect(lambda: resume_service())
    
    # Status update timer
    update_timer = QTimer(control_widget)
    update_timer.timeout.connect(lambda: update_status())
    update_timer.start(1000)  # Update every second
    
    # Progress callback
    def progress_callback(update):
        update_type = update["type"]
        data = update["data"]
        
        if update_type == "task_progress":
            task_label.setText(f"Processing: {data['page_id']} - {data['operation']}")
            task_label.setToolTip(data.get('message', ''))
            progress_bar.setValue(int(data['progress'] * 100))
        elif update_type in ["task_started", "task_completed", "task_failed"]:
            update_status()  # Refresh status immediately
        elif update_type in ["bulk_task_created", "bulk_task_updated", "bulk_task_progress", 
                             "bulk_task_paused", "bulk_task_resumed", "bulk_task_cancelled"]:
            # If bulk controls are enabled, refresh the bulk tasks table
            if bulk_widget:
                refresh_bulk_tasks()
        elif update_type == "batch_started":
            # Update batch processing status
            if "batch_size" in data:
                task_label.setText(f"Processing batch of {data['batch_size']} tasks")
    
    # Register callback with service
    service.register_progress_callback(progress_callback)
    
    # Helper function for batch mode
    def toggle_batch_mode(enabled):
        service.enable_batch_mode(enabled)
        batch_mode_button.setText("Disable Batch Mode" if enabled else "Enable Batch Mode")
    
    # Helper function for refreshing bulk tasks
    def refresh_bulk_tasks():
        if not bulk_widget:
            return
            
        # Get all bulk tasks
        bulk_tasks = service.get_all_bulk_tasks()
        
        # Update table
        table = bulk_widget["table"]
        table.setRowCount(0)  # Clear table
        
        for row, task in enumerate(bulk_tasks):
            table.insertRow(row)
            
            # ID column
            id_item = QTableWidgetItem(task["bulk_id"])
            table.setItem(row, 0, id_item)
            
            # Description column
            desc_item = QTableWidgetItem(task["description"])
            table.setItem(row, 1, desc_item)
            
            # Status column
            status_item = QTableWidgetItem(task["status"])
            table.setItem(row, 2, status_item)
            
            # Progress column - use a progress bar
            progress_cell = QWidget()
            progress_layout = QHBoxLayout(progress_cell)
            progress_layout.setContentsMargins(2, 2, 2, 2)
            
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(int(task["progress"] * 100))
            progress_layout.addWidget(progress)
            
            table.setCellWidget(row, 3, progress_cell)
            
            # Tasks column
            tasks_text = f"{task['completed_tasks']}/{task['total_tasks']} ({task['failed_tasks']} failed)"
            tasks_item = QTableWidgetItem(tasks_text)
            table.setItem(row, 4, tasks_item)
            
            # Started column
            started = "Not started"
            if task.get("last_update"):
                from datetime import datetime
                try:
                    start_time = datetime.fromisoformat(task["last_update"])
                    started = start_time.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    started = "Error parsing time"
            
            started_item = QTableWidgetItem(started)
            table.setItem(row, 5, started_item)
            
            # Actions column - add buttons
            actions_cell = QWidget()
            actions_layout = QHBoxLayout(actions_cell)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            # Different buttons depending on status
            if task["status"] == "paused":
                resume_btn = QPushButton("Resume")
                resume_btn.clicked.connect(lambda checked, id=task["bulk_id"]: service.resume_bulk_task(id))
                actions_layout.addWidget(resume_btn)
            elif task["status"] in ["pending", "in_progress"]:
                pause_btn = QPushButton("Pause")
                pause_btn.clicked.connect(lambda checked, id=task["bulk_id"]: service.pause_bulk_task(id))
                actions_layout.addWidget(pause_btn)
            
            # Cancel button for active tasks
            if task["status"] in ["pending", "in_progress", "paused"]:
                cancel_btn = QPushButton("Cancel")
                cancel_btn.clicked.connect(lambda checked, id=task["bulk_id"]: service.cancel_bulk_task(id))
                actions_layout.addWidget(cancel_btn)
            
            # Retry button for failed or partially completed tasks
            if task["status"] in ["failed", "partially_completed"]:
                retry_btn = QPushButton("Retry Failed")
                retry_btn.clicked.connect(lambda checked, id=task["bulk_id"]: service.retry_failed_bulk_tasks(id))
                actions_layout.addWidget(retry_btn)
            
            table.setCellWidget(row, 6, actions_cell)
    
    # Initial refresh of bulk tasks
    if bulk_widget:
        refresh_bulk_tasks()
    
    # Helper functions for button actions
    def start_service():
        service.start()
        start_button.setEnabled(False)
        stop_button.setEnabled(True)
        pause_button.setEnabled(True)
        resume_button.setEnabled(False)
        update_status()
    
    def stop_service():
        service.stop()
        start_button.setEnabled(True)
        stop_button.setEnabled(False)
        pause_button.setEnabled(False)
        resume_button.setEnabled(False)
        update_status()
    
    def pause_service():
        service.pause()
        pause_button.setEnabled(False)
        resume_button.setEnabled(True)
        update_status()
    
    def resume_service():
        service.resume()
        pause_button.setEnabled(True)
        resume_button.setEnabled(False)
        update_status()
    
    def update_status():
        status = service.get_queue_status()
        
        if status['running']:
            if status['paused']:
                status_label.setText("Service is paused")
            else:
                status_label.setText("Service is running")
        else:
            status_label.setText("Service is stopped")
            task_label.setText("No task in progress")
            progress_bar.setValue(0)
        
        queue_label.setText(f"Queue: {status['queue_size']} tasks")
        progress_label.setText(f"Processing: {status['in_progress']} tasks")
        
        stats = status['stats']
        stats_text = (f"Processed: {stats['tasks_processed']} | "
                    f"Succeeded: {stats['tasks_succeeded']} | "
                    f"Failed: {stats['tasks_failed']} | "
                    f"Retried: {stats['tasks_retried']}")
        stats_label.setText(stats_text)
    
    # Initial status update
    update_status()
    
    return control_widget