"""
Bulk Processing Task Module

This module extends the background processing service with support for bulk operations.
It provides classes and utilities for efficiently handling batches of related tasks,
prioritizing bulk operations, tracking progress across multiple items, and implementing
pause/resume functionality specifically for bulk tasks.

Features:
- BulkProcessingTask class for representing a group of related tasks
- Batch prioritization in the task queue
- Progress tracking across multiple related tasks
- Detailed status reporting for bulk operations
- Automatic retry mechanisms for failed operations
- Pause/resume functionality specifically for bulk tasks
"""

import os
import time
import threading
import json
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from enum import Enum

# Import dynamically to avoid circular imports
import sys
if 'newspaper_repository.background_service' in sys.modules:
    from newspaper_repository.background_service import ProcessingTask, BackgroundProcessingService
elif 'background_service' in sys.modules:
    from background_service import ProcessingTask, BackgroundProcessingService
else:
    # Placeholder definitions for type checking
    class BackgroundProcessingService:
        pass

    class ProcessingTask:
        pass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BulkOperationType(Enum):
    """Types of bulk operations that can be performed."""
    DOWNLOAD = "download"
    OCR = "ocr"
    SEGMENT = "segment"
    ARTICLE_EXTRACTION = "extract_articles"
    IMPORT = "import"
    EXPORT = "export"
    INDEX = "index"


class BulkTaskStatus(Enum):
    """Status of a bulk task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


class BulkProcessingTask:
    """
    Represents a bulk task that consists of multiple related processing tasks.
    This allows for better tracking and management of batches of operations.
    """
    
    def __init__(self, 
                 bulk_id: str, 
                 operation_type: BulkOperationType,
                 description: str,
                 parameters: Optional[Dict[str, Any]] = None,
                 priority: int = 1):
        """
        Initialize a bulk processing task.
        
        Args:
            bulk_id: Unique identifier for the bulk task
            operation_type: Type of bulk operation
            description: Human-readable description of the bulk task
            parameters: Additional parameters for the bulk operation
            priority: Priority of the bulk task (lower numbers = higher priority)
        """
        self.bulk_id = bulk_id
        self.operation_type = operation_type
        self.description = description
        self.parameters = parameters or {}
        self.priority = priority
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.status = BulkTaskStatus.PENDING
        
        # Task tracking
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.in_progress_tasks = 0
        self.pending_tasks = 0
        self.task_ids = set()  # All task IDs in this bulk operation
        self.failed_task_ids = set()  # Task IDs that failed
        
        # Pause/resume tracking
        self.is_paused = False
        self.pause_requested = False
        
        # Detailed status information
        self.status_messages = []
        self.last_error = ""
        self.last_update_time = datetime.now()
        
        # Performance metrics
        self.start_time = None
        self.end_time = None
        self.processing_time = 0
        self.estimated_time_remaining = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bulk task to dictionary for storage."""
        return {
            "bulk_id": self.bulk_id,
            "operation_type": self.operation_type.value,
            "description": self.description,
            "parameters": self.parameters,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "in_progress_tasks": self.in_progress_tasks,
            "pending_tasks": self.pending_tasks,
            "is_paused": self.is_paused,
            "task_ids": list(self.task_ids),
            "failed_task_ids": list(self.failed_task_ids),
            "last_error": self.last_error,
            "last_update_time": self.last_update_time.isoformat() if self.last_update_time else None,
            "processing_time": self.processing_time,
            "estimated_time_remaining": self.estimated_time_remaining,
            "status_messages": self.status_messages[-10:] if self.status_messages else []  # Store last 10 messages only
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BulkProcessingTask':
        """Create bulk task from dictionary."""
        # Convert operation_type string to enum
        try:
            operation_type = BulkOperationType(data["operation_type"])
        except ValueError:
            # Default to DOWNLOAD if the operation type is not recognized
            operation_type = BulkOperationType.DOWNLOAD
            logger.warning(f"Unknown operation type: {data['operation_type']}, defaulting to DOWNLOAD")
        
        # Create the task with basic properties
        bulk_task = cls(
            bulk_id=data["bulk_id"],
            operation_type=operation_type,
            description=data["description"],
            parameters=data.get("parameters", {}),
            priority=data.get("priority", 1)
        )
        
        # Parse dates
        if data.get("created_at"):
            bulk_task.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            bulk_task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            bulk_task.completed_at = datetime.fromisoformat(data["completed_at"])
        if data.get("last_update_time"):
            bulk_task.last_update_time = datetime.fromisoformat(data["last_update_time"])
        
        # Set status
        try:
            bulk_task.status = BulkTaskStatus(data.get("status", "pending"))
        except ValueError:
            bulk_task.status = BulkTaskStatus.PENDING
            logger.warning(f"Unknown status: {data.get('status')}, defaulting to PENDING")
        
        # Set task counters
        bulk_task.total_tasks = data.get("total_tasks", 0)
        bulk_task.completed_tasks = data.get("completed_tasks", 0)
        bulk_task.failed_tasks = data.get("failed_tasks", 0)
        bulk_task.in_progress_tasks = data.get("in_progress_tasks", 0)
        bulk_task.pending_tasks = data.get("pending_tasks", 0)
        
        # Set task IDs
        bulk_task.task_ids = set(data.get("task_ids", []))
        bulk_task.failed_task_ids = set(data.get("failed_task_ids", []))
        
        # Set other properties
        bulk_task.is_paused = data.get("is_paused", False)
        bulk_task.last_error = data.get("last_error", "")
        bulk_task.processing_time = data.get("processing_time", 0)
        bulk_task.estimated_time_remaining = data.get("estimated_time_remaining")
        bulk_task.status_messages = data.get("status_messages", [])
        
        return bulk_task
    
    def add_task(self, task_id: str) -> None:
        """
        Add a task to this bulk operation.
        
        Args:
            task_id: ID of the task to add
        """
        self.task_ids.add(task_id)
        self.total_tasks = len(self.task_ids)
        self.pending_tasks += 1
    
    def remove_task(self, task_id: str) -> None:
        """
        Remove a task from this bulk operation.
        
        Args:
            task_id: ID of the task to remove
        """
        if task_id in self.task_ids:
            self.task_ids.remove(task_id)
            self.total_tasks = len(self.task_ids)
            
            # Adjust counters based on task status in failed_task_ids
            if task_id in self.failed_task_ids:
                self.failed_task_ids.remove(task_id)
                self.failed_tasks -= 1
            else:
                # Assume it was pending if not failed
                self.pending_tasks -= 1
    
    def update_task_status(self, task_id: str, status: str) -> None:
        """
        Update the status of a task in this bulk operation.
        
        Args:
            task_id: ID of the task to update
            status: New status of the task
        """
        if task_id not in self.task_ids:
            # Task not part of this bulk operation
            return
        
        # Update counters based on status transition
        if status == "in_progress":
            self.pending_tasks -= 1
            self.in_progress_tasks += 1
        elif status == "completed":
            if task_id in self.failed_task_ids:
                self.failed_task_ids.remove(task_id)
                self.failed_tasks -= 1
            self.in_progress_tasks -= 1
            self.completed_tasks += 1
        elif status == "failed":
            self.in_progress_tasks -= 1
            self.failed_tasks += 1
            self.failed_task_ids.add(task_id)
        
        # Update bulk task status
        self._update_bulk_status()
        self.last_update_time = datetime.now()
        
        # Update processing time and estimate remaining time
        self._update_time_estimates()
    
    def _update_bulk_status(self) -> None:
        """Update the overall status of the bulk task based on its subtasks."""
        if self.total_tasks == 0:
            self.status = BulkTaskStatus.PENDING
            return
        
        if self.is_paused:
            self.status = BulkTaskStatus.PAUSED
            return
        
        if self.completed_tasks + self.failed_tasks == self.total_tasks:
            # All tasks have been processed
            if self.failed_tasks == 0:
                self.status = BulkTaskStatus.COMPLETED
                self.completed_at = datetime.now()
            elif self.completed_tasks == 0:
                self.status = BulkTaskStatus.FAILED
                self.completed_at = datetime.now()
            else:
                self.status = BulkTaskStatus.PARTIALLY_COMPLETED
                self.completed_at = datetime.now()
        elif self.in_progress_tasks > 0 or self.completed_tasks > 0 or self.failed_tasks > 0:
            self.status = BulkTaskStatus.IN_PROGRESS
            if self.started_at is None:
                self.started_at = datetime.now()
                self.start_time = datetime.now()
        else:
            self.status = BulkTaskStatus.PENDING
    
    def _update_time_estimates(self) -> None:
        """Update processing time and estimate remaining time."""
        if self.start_time is None:
            return
        
        now = datetime.now()
        
        # Calculate total processing time so far
        if self.status in [BulkTaskStatus.COMPLETED, BulkTaskStatus.FAILED, BulkTaskStatus.PARTIALLY_COMPLETED]:
            if self.end_time is None:
                self.end_time = now
            self.processing_time = (self.end_time - self.start_time).total_seconds()
        else:
            self.processing_time = (now - self.start_time).total_seconds()
        
        # Estimate remaining time
        completed_count = self.completed_tasks + self.failed_tasks
        if completed_count > 0 and self.total_tasks > completed_count:
            # Average time per task
            avg_time_per_task = self.processing_time / completed_count
            
            # Remaining tasks
            remaining_tasks = self.total_tasks - completed_count
            
            # Estimated time remaining
            self.estimated_time_remaining = avg_time_per_task * remaining_tasks
        else:
            self.estimated_time_remaining = None
    
    def pause(self) -> None:
        """Pause the bulk task."""
        self.is_paused = True
        self.pause_requested = True
        self.status = BulkTaskStatus.PAUSED
        self.add_status_message("Bulk task paused")
    
    def resume(self) -> None:
        """Resume the bulk task."""
        self.is_paused = False
        self.pause_requested = False
        self._update_bulk_status()
        self.add_status_message("Bulk task resumed")
    
    def add_status_message(self, message: str) -> None:
        """
        Add a status message to the bulk task.
        
        Args:
            message: Status message to add
        """
        # Add timestamp to message
        timestamped_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self.status_messages.append(timestamped_message)
        self.last_update_time = datetime.now()
        
        # Keep only the last 100 messages
        if len(self.status_messages) > 100:
            self.status_messages = self.status_messages[-100:]
    
    def get_progress(self) -> float:
        """
        Get the current progress as a percentage.
        
        Returns:
            Progress as a float between 0 and 1
        """
        if self.total_tasks == 0:
            return 0.0
        
        return (self.completed_tasks + self.failed_tasks) / self.total_tasks
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the bulk task status.
        
        Returns:
            Dictionary with status summary
        """
        return {
            "bulk_id": self.bulk_id,
            "description": self.description,
            "status": self.status.value,
            "progress": self.get_progress(),
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "in_progress_tasks": self.in_progress_tasks,
            "pending_tasks": self.pending_tasks,
            "is_paused": self.is_paused,
            "processing_time": self.processing_time,
            "estimated_time_remaining": self.estimated_time_remaining,
            "last_error": self.last_error,
            "last_update": self.last_update_time.isoformat() if self.last_update_time else None
        }


class BulkTaskManager:
    """
    Manager for handling bulk tasks in the background service.
    
    This class extends the background service with functionality for bulk operations,
    providing features like bulk task creation, status tracking, and pause/resume.
    """
    
    def __init__(self, background_service: BackgroundProcessingService):
        """
        Initialize the bulk task manager.
        
        Args:
            background_service: The background processing service to extend
        """
        self.background_service = background_service
        self.bulk_tasks = {}  # Dictionary of bulk_id -> BulkProcessingTask
        self.task_to_bulk_map = {}  # Dictionary of task_id -> bulk_id
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Database manager for persistence
        self.db_manager = background_service.db_manager
        
        # Initialize from database
        self._load_bulk_tasks_from_database()
    
    def create_bulk_task(self, 
                        operation_type: BulkOperationType,
                        description: str,
                        parameters: Optional[Dict[str, Any]] = None,
                        priority: int = 1) -> str:
        """
        Create a new bulk task.
        
        Args:
            operation_type: Type of bulk operation
            description: Human-readable description of the bulk task
            parameters: Additional parameters for the bulk operation
            priority: Priority of the bulk task (lower numbers = higher priority)
            
        Returns:
            Bulk task ID
        """
        with self.lock:
            # Generate a unique bulk ID
            bulk_id = f"bulk_{operation_type.value}_{int(datetime.now().timestamp())}"
            
            # Create the bulk task
            bulk_task = BulkProcessingTask(
                bulk_id=bulk_id,
                operation_type=operation_type,
                description=description,
                parameters=parameters,
                priority=priority
            )
            
            # Add to our tracking dictionary
            self.bulk_tasks[bulk_id] = bulk_task
            
            # Add to database
            self._save_bulk_task_to_database(bulk_task)
            
            # Log creation
            logger.info(f"Created bulk task: {bulk_id} - {description} ({operation_type.value})")
            bulk_task.add_status_message(f"Bulk task created: {description}")
            
            # Notify progress listeners if available
            if hasattr(self.background_service, 'notify_progress'):
                self.background_service.notify_progress("bulk_task_created", {
                    "bulk_id": bulk_id,
                    "operation_type": operation_type.value,
                    "description": description,
                    "priority": priority
                })
            
            return bulk_id
    
    def add_task_to_bulk(self, 
                        bulk_id: str, 
                        page_id: str, 
                        operation: str, 
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
        with self.lock:
            # Check if bulk task exists
            if bulk_id not in self.bulk_tasks:
                logger.error(f"Bulk task {bulk_id} not found")
                return None
            
            bulk_task = self.bulk_tasks[bulk_id]
            
            # Add task to background service with bulk task's priority
            task_id = self.background_service.add_task(
                page_id=page_id,
                operation=operation,
                parameters=parameters,
                priority=bulk_task.priority
            )
            
            if not task_id:
                logger.error(f"Failed to add task to background service: {page_id} - {operation}")
                return None
            
            # Associate task with bulk task
            bulk_task.add_task(task_id)
            self.task_to_bulk_map[task_id] = bulk_id
            
            # Update bulk task in database
            self._save_bulk_task_to_database(bulk_task)
            
            # Log addition
            bulk_task.add_status_message(f"Added task: {page_id} - {operation}")
            
            # Notify progress listeners if available
            if hasattr(self.background_service, 'notify_progress'):
                self.background_service.notify_progress("bulk_task_updated", {
                    "bulk_id": bulk_id,
                    "task_id": task_id,
                    "total_tasks": bulk_task.total_tasks,
                    "pending_tasks": bulk_task.pending_tasks
                })
            
            return task_id
    
    def add_tasks_to_bulk(self, 
                        bulk_id: str, 
                        tasks: List[Tuple[str, str, Dict[str, Any]]]) -> List[str]:
        """
        Add multiple tasks to a bulk operation.
        
        Args:
            bulk_id: ID of the bulk task to add to
            tasks: List of tuples (page_id, operation, parameters)
            
        Returns:
            List of task IDs
        """
        task_ids = []
        
        with self.lock:
            # Check if bulk task exists
            if bulk_id not in self.bulk_tasks:
                logger.error(f"Bulk task {bulk_id} not found")
                return []
            
            bulk_task = self.bulk_tasks[bulk_id]
            
            # Add all tasks to the bulk task
            for page_id, operation, parameters in tasks:
                task_id = self.background_service.add_task(
                    page_id=page_id,
                    operation=operation,
                    parameters=parameters,
                    priority=bulk_task.priority
                )
                
                if task_id:
                    # Associate task with bulk task
                    bulk_task.add_task(task_id)
                    self.task_to_bulk_map[task_id] = bulk_id
                    task_ids.append(task_id)
            
            # Update bulk task in database
            self._save_bulk_task_to_database(bulk_task)
            
            # Log addition
            bulk_task.add_status_message(f"Added {len(task_ids)} tasks in batch")
            
            # Notify progress listeners if available
            if hasattr(self.background_service, 'notify_progress'):
                self.background_service.notify_progress("bulk_task_updated", {
                    "bulk_id": bulk_id,
                    "total_tasks": bulk_task.total_tasks,
                    "pending_tasks": bulk_task.pending_tasks,
                    "added_tasks": len(task_ids)
                })
            
            return task_ids
    
    def get_bulk_task(self, bulk_id: str) -> Optional[BulkProcessingTask]:
        """
        Get a bulk task by ID.
        
        Args:
            bulk_id: ID of the bulk task
            
        Returns:
            BulkProcessingTask object or None if not found
        """
        with self.lock:
            return self.bulk_tasks.get(bulk_id)
    
    def get_all_bulk_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all bulk tasks.
        
        Returns:
            List of bulk task summaries
        """
        with self.lock:
            return [task.get_status_summary() for task in self.bulk_tasks.values()]
    
    def pause_bulk_task(self, bulk_id: str) -> bool:
        """
        Pause a bulk task.
        
        This will prevent new tasks from starting but won't interrupt tasks in progress.
        
        Args:
            bulk_id: ID of the bulk task to pause
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            if bulk_id not in self.bulk_tasks:
                logger.error(f"Bulk task {bulk_id} not found")
                return False
            
            bulk_task = self.bulk_tasks[bulk_id]
            
            # Already paused?
            if bulk_task.is_paused:
                return True
            
            # Set pause flag
            bulk_task.pause()
            
            # Update in database
            self._save_bulk_task_to_database(bulk_task)
            
            # Notify progress listeners if available
            if hasattr(self.background_service, 'notify_progress'):
                self.background_service.notify_progress("bulk_task_paused", {
                    "bulk_id": bulk_id,
                    "status": bulk_task.status.value
                })
            
            return True
    
    def resume_bulk_task(self, bulk_id: str) -> bool:
        """
        Resume a paused bulk task.
        
        Args:
            bulk_id: ID of the bulk task to resume
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            if bulk_id not in self.bulk_tasks:
                logger.error(f"Bulk task {bulk_id} not found")
                return False
            
            bulk_task = self.bulk_tasks[bulk_id]
            
            # Not paused?
            if not bulk_task.is_paused:
                return True
            
            # Resume the task
            bulk_task.resume()
            
            # Update in database
            self._save_bulk_task_to_database(bulk_task)
            
            # Notify progress listeners if available
            if hasattr(self.background_service, 'notify_progress'):
                self.background_service.notify_progress("bulk_task_resumed", {
                    "bulk_id": bulk_id,
                    "status": bulk_task.status.value
                })
            
            return True
    
    def cancel_bulk_task(self, bulk_id: str) -> bool:
        """
        Cancel a bulk task.
        
        This will cancel all pending tasks and mark the bulk task as failed.
        
        Args:
            bulk_id: ID of the bulk task to cancel
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            if bulk_id not in self.bulk_tasks:
                logger.error(f"Bulk task {bulk_id} not found")
                return False
            
            bulk_task = self.bulk_tasks[bulk_id]
            
            # Cancel all pending tasks
            cancelled_count = 0
            for task_id in bulk_task.task_ids:
                if self.background_service.cancel_task(task_id):
                    cancelled_count += 1
            
            # Mark as failed
            bulk_task.status = BulkTaskStatus.FAILED
            bulk_task.completed_at = datetime.now()
            bulk_task.end_time = datetime.now()
            bulk_task.add_status_message(f"Bulk task cancelled, {cancelled_count} pending tasks cancelled")
            
            # Update in database
            self._save_bulk_task_to_database(bulk_task)
            
            # Notify progress listeners if available
            if hasattr(self.background_service, 'notify_progress'):
                self.background_service.notify_progress("bulk_task_cancelled", {
                    "bulk_id": bulk_id,
                    "cancelled_tasks": cancelled_count,
                    "status": bulk_task.status.value
                })
            
            return True
    
    def update_task_status(self, task_id: str, status: str, error: str = "") -> None:
        """
        Update the status of a task in a bulk operation.
        
        Args:
            task_id: ID of the task to update
            status: New status of the task
            error: Error message if the task failed
        """
        with self.lock:
            # Check if task is part of a bulk task
            if task_id not in self.task_to_bulk_map:
                return
            
            bulk_id = self.task_to_bulk_map[task_id]
            
            if bulk_id not in self.bulk_tasks:
                # Inconsistent state, remove from map
                del self.task_to_bulk_map[task_id]
                return
            
            bulk_task = self.bulk_tasks[bulk_id]
            
            # Update task status in bulk task
            bulk_task.update_task_status(task_id, status)
            
            # Update error message if provided
            if status == "failed" and error:
                bulk_task.last_error = error
                bulk_task.add_status_message(f"Task {task_id} failed: {error}")
            elif status == "completed":
                bulk_task.add_status_message(f"Task {task_id} completed successfully")
            
            # Update in database
            self._save_bulk_task_to_database(bulk_task)
            
            # Notify progress listeners if available
            if hasattr(self.background_service, 'notify_progress'):
                self.background_service.notify_progress("bulk_task_progress", {
                    "bulk_id": bulk_id,
                    "task_id": task_id,
                    "status": bulk_task.status.value,
                    "progress": bulk_task.get_progress(),
                    "completed_tasks": bulk_task.completed_tasks,
                    "failed_tasks": bulk_task.failed_tasks,
                    "total_tasks": bulk_task.total_tasks
                })
    
    def retry_failed_tasks(self, bulk_id: str) -> int:
        """
        Retry all failed tasks in a bulk operation.
        
        Args:
            bulk_id: ID of the bulk task
            
        Returns:
            Number of tasks requeued for retry
        """
        with self.lock:
            if bulk_id not in self.bulk_tasks:
                logger.error(f"Bulk task {bulk_id} not found")
                return 0
            
            bulk_task = self.bulk_tasks[bulk_id]
            
            # Get list of failed tasks
            failed_tasks = list(bulk_task.failed_task_ids)
            retry_count = 0
            
            # Retry each failed task
            for task_id in failed_tasks:
                # Parse page_id and operation from task_id
                if "_" in task_id:
                    page_id, operation = task_id.rsplit("_", 1)
                    
                    # Get original parameters from database
                    task_data = self.background_service.db_manager.get_processing_queue_item(task_id)
                    
                    if task_data:
                        parameters = json.loads(task_data.get("parameters", "{}")) if task_data.get("parameters") else {}
                        
                        # Cancel the old task explicitly to be safe
                        self.background_service.cancel_task(task_id)
                        
                        # Add as a new task
                        new_task_id = self.background_service.add_task(
                            page_id=page_id,
                            operation=operation,
                            parameters=parameters,
                            priority=bulk_task.priority
                        )
                        
                        if new_task_id:
                            # Update bulk task tracking
                            bulk_task.failed_task_ids.remove(task_id)
                            bulk_task.failed_tasks -= 1
                            bulk_task.add_task(new_task_id)
                            self.task_to_bulk_map[new_task_id] = bulk_id
                            
                            # Remove old task_id from task_to_bulk_map
                            if task_id in self.task_to_bulk_map:
                                del self.task_to_bulk_map[task_id]
                            
                            retry_count += 1
            
            if retry_count > 0:
                bulk_task.add_status_message(f"Retrying {retry_count} failed tasks")
                
                # If we were in failed or partially completed state, update status
                if bulk_task.status in [BulkTaskStatus.FAILED, BulkTaskStatus.PARTIALLY_COMPLETED]:
                    bulk_task._update_bulk_status()
                
                # Update in database
                self._save_bulk_task_to_database(bulk_task)
                
                # Notify progress listeners if available
                if hasattr(self.background_service, 'notify_progress'):
                    self.background_service.notify_progress("bulk_task_retrying", {
                        "bulk_id": bulk_id,
                        "retried_tasks": retry_count,
                        "status": bulk_task.status.value
                    })
            
            return retry_count
    
    def clean_up_completed_tasks(self, age_days: int = 7) -> int:
        """
        Clean up completed bulk tasks older than the specified age.
        
        Args:
            age_days: Age in days after which completed tasks should be removed
            
        Returns:
            Number of tasks removed
        """
        with self.lock:
            cutoff_date = datetime.now() - timedelta(days=age_days)
            tasks_to_remove = []
            
            for bulk_id, bulk_task in self.bulk_tasks.items():
                if bulk_task.status in [BulkTaskStatus.COMPLETED, BulkTaskStatus.FAILED, BulkTaskStatus.PARTIALLY_COMPLETED]:
                    if bulk_task.completed_at and bulk_task.completed_at < cutoff_date:
                        tasks_to_remove.append(bulk_id)
            
            # Remove the tasks
            for bulk_id in tasks_to_remove:
                # Remove task-to-bulk mappings
                for task_id in self.bulk_tasks[bulk_id].task_ids:
                    if task_id in self.task_to_bulk_map:
                        del self.task_to_bulk_map[task_id]
                
                # Remove from dictionary
                del self.bulk_tasks[bulk_id]
                
                # Remove from database
                self._delete_bulk_task_from_database(bulk_id)
            
            return len(tasks_to_remove)
    
    def _load_bulk_tasks_from_database(self) -> None:
        """Load bulk tasks from the database."""
        try:
            # Check if the bulk_processing_tasks table exists, create if not
            if not self._ensure_bulk_tasks_table_exists():
                logger.info("Created bulk_processing_tasks table")
            
            # Get all bulk tasks from database - use execute_query method which is likely to exist
            query = "SELECT * FROM bulk_processing_tasks"
            try:
                # Try various method names that might exist
                if hasattr(self.db_manager, 'execute_query'):
                    bulk_data = self.db_manager.execute_query(query)
                elif hasattr(self.db_manager, '_execute_query'):
                    bulk_data = self.db_manager._execute_query(query)
                elif hasattr(self.db_manager, 'query'):
                    bulk_data = self.db_manager.query(query)
                else:
                    logger.warning("No query method found on database manager")
                    bulk_data = []
            except Exception as e:
                logger.error(f"Failed to execute query: {e}")
                bulk_data = []
            
            for row in bulk_data:
                try:
                    # Parse JSON data
                    task_dict = json.loads(row["task_data"])
                    
                    # Create bulk task object
                    bulk_task = BulkProcessingTask.from_dict(task_dict)
                    
                    # Add to tracking dictionaries
                    self.bulk_tasks[bulk_task.bulk_id] = bulk_task
                    
                    # Update task-to-bulk mappings
                    for task_id in bulk_task.task_ids:
                        self.task_to_bulk_map[task_id] = bulk_task.bulk_id
                        
                except Exception as e:
                    logger.error(f"Error loading bulk task: {e}")
                    continue
            
            logger.info(f"Loaded {len(self.bulk_tasks)} bulk tasks from database")
            
        except Exception as e:
            logger.error(f"Error loading bulk tasks from database: {e}")
    
    def _ensure_bulk_tasks_table_exists(self) -> bool:
        """
        Ensure the bulk_processing_tasks table exists in the database.
        
        Returns:
            True if table already existed, False if it was created
        """
        # Check if table exists
        query = """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='bulk_processing_tasks'
        """

        try:
            # Try various method names that might exist
            if hasattr(self.db_manager, 'execute_query'):
                result = self.db_manager.execute_query(query)
            elif hasattr(self.db_manager, '_execute_query'):
                result = self.db_manager._execute_query(query)
            elif hasattr(self.db_manager, 'query'):
                result = self.db_manager.query(query)
            else:
                logger.warning("No query method found on database manager")
                result = []
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            result = []

        if result:
            return True

        # Create table if it doesn't exist
        create_table_query = """
        CREATE TABLE bulk_processing_tasks (
            bulk_id TEXT PRIMARY KEY,
            created_at TEXT,
            updated_at TEXT,
            task_data TEXT
        )
        """

        try:
            # Try various method names that might exist
            if hasattr(self.db_manager, 'execute_query'):
                self.db_manager.execute_query(create_table_query)
            elif hasattr(self.db_manager, '_execute_query'):
                self.db_manager._execute_query(create_table_query)
            elif hasattr(self.db_manager, 'query'):
                self.db_manager.query(create_table_query)
            elif hasattr(self.db_manager, 'execute'):
                self.db_manager.execute(create_table_query)
            else:
                logger.warning("No query method found on database manager to create table")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
        return False
    
    def _save_bulk_task_to_database(self, bulk_task: BulkProcessingTask) -> None:
        """
        Save a bulk task to the database.
        
        Args:
            bulk_task: Bulk task to save
        """
        try:
            # Ensure table exists
            self._ensure_bulk_tasks_table_exists()
            
            # Convert task to JSON
            task_data = json.dumps(bulk_task.to_dict())
            
            # Check if task already exists
            query = "SELECT bulk_id FROM bulk_processing_tasks WHERE bulk_id = ?"

            try:
                # Try various method names that might exist
                if hasattr(self.db_manager, 'execute_query'):
                    existing = self.db_manager.execute_query(query, (bulk_task.bulk_id,))
                elif hasattr(self.db_manager, '_execute_query'):
                    existing = self.db_manager._execute_query(query, (bulk_task.bulk_id,))
                elif hasattr(self.db_manager, 'query'):
                    existing = self.db_manager.query(query, (bulk_task.bulk_id,))
                else:
                    logger.warning("No query method found on database manager")
                    existing = []
            except Exception as e:
                logger.error(f"Failed to query existing bulk task: {e}")
                existing = []
            
            if existing:
                # Update existing task
                update_query = """
                UPDATE bulk_processing_tasks
                SET updated_at = ?, task_data = ?
                WHERE bulk_id = ?
                """
                try:
                    # Try various method names that might exist
                    if hasattr(self.db_manager, 'execute_query'):
                        self.db_manager.execute_query(update_query,
                            (datetime.now().isoformat(), task_data, bulk_task.bulk_id))
                    elif hasattr(self.db_manager, '_execute_query'):
                        self.db_manager._execute_query(update_query,
                            (datetime.now().isoformat(), task_data, bulk_task.bulk_id))
                    elif hasattr(self.db_manager, 'query'):
                        self.db_manager.query(update_query,
                            (datetime.now().isoformat(), task_data, bulk_task.bulk_id))
                    elif hasattr(self.db_manager, 'execute'):
                        self.db_manager.execute(update_query,
                            (datetime.now().isoformat(), task_data, bulk_task.bulk_id))
                    else:
                        logger.warning("No query method found on database manager to update task")
                except Exception as e:
                    logger.error(f"Failed to update bulk task: {e}")
            else:
                # Insert new task
                insert_query = """
                INSERT INTO bulk_processing_tasks (bulk_id, created_at, updated_at, task_data)
                VALUES (?, ?, ?, ?)
                """
                try:
                    # Try various method names that might exist
                    if hasattr(self.db_manager, 'execute_query'):
                        self.db_manager.execute_query(insert_query,
                            (bulk_task.bulk_id, datetime.now().isoformat(), datetime.now().isoformat(), task_data))
                    elif hasattr(self.db_manager, '_execute_query'):
                        self.db_manager._execute_query(insert_query,
                            (bulk_task.bulk_id, datetime.now().isoformat(), datetime.now().isoformat(), task_data))
                    elif hasattr(self.db_manager, 'query'):
                        self.db_manager.query(insert_query,
                            (bulk_task.bulk_id, datetime.now().isoformat(), datetime.now().isoformat(), task_data))
                    elif hasattr(self.db_manager, 'execute'):
                        self.db_manager.execute(insert_query,
                            (bulk_task.bulk_id, datetime.now().isoformat(), datetime.now().isoformat(), task_data))
                    else:
                        logger.warning("No query method found on database manager to insert task")
                except Exception as e:
                    logger.error(f"Failed to insert bulk task: {e}")
                
        except Exception as e:
            logger.error(f"Error saving bulk task to database: {e}")
    
    def _delete_bulk_task_from_database(self, bulk_id: str) -> None:
        """
        Delete a bulk task from the database.
        
        Args:
            bulk_id: ID of the bulk task to delete
        """
        try:
            query = "DELETE FROM bulk_processing_tasks WHERE bulk_id = ?"
            # Try various method names that might exist
            if hasattr(self.db_manager, 'execute_query'):
                self.db_manager.execute_query(query, (bulk_id,))
            elif hasattr(self.db_manager, '_execute_query'):
                self.db_manager._execute_query(query, (bulk_id,))
            elif hasattr(self.db_manager, 'query'):
                self.db_manager.query(query, (bulk_id,))
            elif hasattr(self.db_manager, 'execute'):
                self.db_manager.execute(query, (bulk_id,))
            else:
                logger.warning("No query method found on database manager to delete task")
        except Exception as e:
            logger.error(f"Error deleting bulk task from database: {e}")
    
    def hook_into_background_service(self) -> None:
        """
        Hook into the background service to intercept task status updates.
        This allows the bulk task manager to update the status of bulk tasks
        when their component tasks are updated.
        """
        # Store original notify_progress function
        original_notify_progress = self.background_service.notify_progress
        
        # Define intercept function
        def intercept_notify_progress(update_type: str, data: Dict[str, Any]) -> None:
            # Check if this is a task status update
            if update_type in ["task_started", "task_completed", "task_failed"]:
                task_id = data.get("task_id", "")
                
                # Update bulk task status if applicable
                if task_id in self.task_to_bulk_map:
                    if update_type == "task_started":
                        self.update_task_status(task_id, "in_progress")
                    elif update_type == "task_completed":
                        self.update_task_status(task_id, "completed")
                    elif update_type == "task_failed":
                        self.update_task_status(task_id, "failed", data.get("error", ""))
            
            # Call original function
            original_notify_progress(update_type, data)
        
        # Replace notify_progress with our intercept function
        self.background_service.notify_progress = intercept_notify_progress
        
        logger.info("Hooked bulk task manager into background service")