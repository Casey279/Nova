#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Downloader module for the Nova newspaper repository system.

This module implements a comprehensive downloader system for retrieving historical
newspaper content from various sources and storing it in the repository structure.
It provides download queue management, progress tracking, and adaptive rate limiting
for efficient and reliable downloads.
"""

import os
import time
import json
import logging
import datetime
import random
import re
import uuid
import threading
import queue
import hashlib
import shutil
import requests
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Tuple, Any, Set, Callable
from urllib.parse import urljoin, urlparse
from pathlib import Path
from enum import Enum

from .base_repository import (
    BaseRepository, RepositoryConfig, RepositoryError, RepositoryStatus,
    StorageError, InvalidPathError
)
from .database_manager import DatabaseManager
from .publication_repository import PublicationRepository


class DownloadError(RepositoryError):
    """Base exception class for download-related errors."""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        super().__init__(message, error_code, details)


class NetworkError(DownloadError):
    """Exception raised when network operations fail."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "NETWORK_ERROR", details)


class RateLimitError(DownloadError):
    """Exception raised when rate limits are exceeded."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "RATE_LIMIT_ERROR", details)


class ValidationError(DownloadError):
    """Exception raised when downloaded content fails validation."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class DownloaderConfig:
    """Configuration for the downloader system."""
    
    def __init__(self):
        # Network settings
        self.request_timeout = 30  # seconds
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.default_request_delay = 3  # seconds between requests
        self.adaptive_rate_limiting = True
        self.rate_limit_window = 60  # seconds
        self.rate_limit_requests = 10  # max requests per window
        
        # Download settings
        self.max_concurrent_downloads = 2
        self.download_chunk_size = 8192  # bytes
        self.validate_downloads = True
        self.max_download_size = 1024 * 1024 * 100  # 100 MB max file size
        
        # Queue settings
        self.max_queue_size = 1000
        self.default_priority = 5  # 1 (highest) to 10 (lowest)
        
        # Storage settings
        self.temp_dir = "temp"
        self.download_dir = "downloads"
        
        # Source-specific settings
        self.chronicling_america_api_url = "https://chroniclingamerica.loc.gov"
        self.chronicling_america_max_pages = 20  # max pages to try per issue
        
        # User-Agent for API requests
        self.user_agent = "NovaNewspaperRepository/1.0 (nova-repository.org; research project)"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for saving."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'DownloaderConfig':
        """Create config from dictionary."""
        config = cls()
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config


class DownloadPriority(Enum):
    """Priority levels for download queue."""
    CRITICAL = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    BACKGROUND = 10


class DownloadStatus(Enum):
    """Status values for download operations."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    CANCELED = "canceled"
    SKIPPED = "skipped"  # For already downloaded content


@dataclass
class DownloadItem:
    """Represents a single item in the download queue."""
    url: str
    destination_path: str
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: DownloadPriority = DownloadPriority.NORMAL
    status: DownloadStatus = DownloadStatus.QUEUED
    attempts: int = 0
    max_retries: int = 3
    content_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    added_time: float = field(default_factory=time.time)
    started_time: Optional[float] = None
    completed_time: Optional[float] = None
    file_size: Optional[int] = None
    
    def __post_init__(self):
        """Initialize computed properties after instance creation."""
        # Convert priority to enum if needed
        if isinstance(self.priority, int):
            self.priority = DownloadPriority(self.priority)
        
        # Convert status to enum if needed
        if isinstance(self.status, str):
            self.status = DownloadStatus(self.status)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "destination_path": self.destination_path,
            "item_id": self.item_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "content_type": self.content_type,
            "metadata": self.metadata,
            "error_message": self.error_message,
            "added_time": self.added_time,
            "started_time": self.started_time,
            "completed_time": self.completed_time,
            "file_size": self.file_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DownloadItem':
        """Create from dictionary."""
        # Convert enum values from string/int
        priority = DownloadPriority(data.get("priority", DownloadPriority.NORMAL.value))
        status = DownloadStatus(data.get("status", DownloadStatus.QUEUED.value))
        
        return cls(
            url=data["url"],
            destination_path=data["destination_path"],
            item_id=data.get("item_id", str(uuid.uuid4())),
            priority=priority,
            status=status,
            attempts=data.get("attempts", 0),
            max_retries=data.get("max_retries", 3),
            content_type=data.get("content_type"),
            metadata=data.get("metadata", {}),
            error_message=data.get("error_message"),
            added_time=data.get("added_time", time.time()),
            started_time=data.get("started_time"),
            completed_time=data.get("completed_time"),
            file_size=data.get("file_size")
        )


@dataclass
class DownloadProgress:
    """Tracks the progress of a download operation."""
    item_id: str
    url: str
    destination_path: str
    total_size: Optional[int] = None
    downloaded_size: int = 0
    start_time: float = field(default_factory=time.time)
    last_update_time: float = field(default_factory=time.time)
    status: DownloadStatus = DownloadStatus.IN_PROGRESS
    error_message: Optional[str] = None
    
    @property
    def progress_percentage(self) -> Optional[float]:
        """Calculate progress percentage if total size is known."""
        if self.total_size and self.total_size > 0:
            return (self.downloaded_size / self.total_size) * 100
        return None
    
    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def download_speed(self) -> Optional[float]:
        """Calculate download speed in bytes per second."""
        if self.elapsed_time > 0:
            return self.downloaded_size / self.elapsed_time
        return None
    
    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Estimate time remaining in seconds."""
        if (self.total_size and self.downloaded_size > 0 and 
            self.elapsed_time > 0 and self.progress_percentage < 100):
            
            bytes_per_second = self.downloaded_size / self.elapsed_time
            bytes_remaining = self.total_size - self.downloaded_size
            
            if bytes_per_second > 0:
                return bytes_remaining / bytes_per_second
        
        return None
    
    def update(self, downloaded_size: int):
        """Update download progress."""
        self.downloaded_size = downloaded_size
        self.last_update_time = time.time()
    
    def complete(self):
        """Mark download as complete."""
        self.status = DownloadStatus.COMPLETED
        self.downloaded_size = self.total_size if self.total_size else self.downloaded_size
    
    def fail(self, error_message: str):
        """Mark download as failed."""
        self.status = DownloadStatus.FAILED
        self.error_message = error_message


class RateLimiter:
    """
    Implements adaptive rate limiting for downloads.
    
    This class tracks request timing and automatically adjusts delays
    based on response patterns to avoid hitting rate limits.
    """
    
    def __init__(self, window_size: float = 60.0, max_requests: int = 10,
                default_delay: float = 3.0, backend_limited: bool = True):
        """
        Initialize the rate limiter.
        
        Args:
            window_size: Time window in seconds for tracking requests
            max_requests: Maximum number of requests allowed in window
            default_delay: Default delay in seconds between requests
            backend_limited: Whether the backend has rate limits to respect
        """
        self.window_size = window_size
        self.max_requests = max_requests
        self.default_delay = default_delay
        self.backend_limited = backend_limited
        
        # Tracking variables
        self.request_times = []
        self.last_request_time = 0
        self.current_delay = default_delay
        self.consecutive_errors = 0
        self.consecutive_successes = 0
        
        # Lock for thread safety
        self.lock = threading.RLock()
    
    def wait_if_needed(self):
        """
        Wait to respect rate limits before making a request.
        
        Raises:
            RateLimitError: If rate limit is exceeded and we've hit our own buffer
        """
        with self.lock:
            now = time.time()
            
            # Clean up old request times
            self.request_times = [t for t in self.request_times 
                                if now - t <= self.window_size]
            
            # Check if we're exceeding our rate limit
            if len(self.request_times) >= self.max_requests:
                oldest = min(self.request_times)
                wait_time = self.window_size - (now - oldest)
                
                if wait_time > 0:
                    time.sleep(wait_time)
                    # Recursive call after waiting, returning to get fresh wait times
                    return self.wait_if_needed()
            
            # Check if we need to wait between requests
            if now - self.last_request_time < self.current_delay:
                wait_time = self.current_delay - (now - self.last_request_time)
                # Add some random jitter to avoid thundering herd
                jitter = random.uniform(0, 0.2 * wait_time)
                time.sleep(wait_time + jitter)
            
            # Update tracking
            self.request_times.append(time.time())
            self.last_request_time = time.time()
    
    def record_success(self):
        """Record a successful request."""
        with self.lock:
            self.consecutive_successes += 1
            self.consecutive_errors = 0
            
            # Gradually decrease delay after consecutive successes
            if self.consecutive_successes >= 5 and self.backend_limited:
                self.current_delay = max(self.default_delay, self.current_delay * 0.9)
    
    def record_error(self, is_rate_limit: bool = False):
        """
        Record an error response.
        
        Args:
            is_rate_limit: Whether the error was due to rate limiting
        """
        with self.lock:
            self.consecutive_errors += 1
            self.consecutive_successes = 0
            
            # Exponential backoff for rate limit errors
            if is_rate_limit:
                self.current_delay = min(60, self.current_delay * 2)
            # Linear backoff for other errors
            elif self.consecutive_errors > 1:
                self.current_delay = min(30, self.current_delay + 1)


class DownloadQueue:
    """
    Manages a prioritized queue of download items.
    
    This class handles adding, retrieving, and updating items in the 
    download queue with proper thread safety and priority ordering.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize the download queue.
        
        Args:
            max_size: Maximum queue size
        """
        self.max_size = max_size
        self.queue = queue.PriorityQueue(maxsize=max_size)
        self.items = {}  # Dictionary mapping item_id to DownloadItem
        self.lock = threading.RLock()
    
    def add_item(self, item: DownloadItem) -> bool:
        """
        Add an item to the download queue.
        
        Args:
            item: Download item to add
        
        Returns:
            True if item was added, False if queue is full
        
        Raises:
            ValueError: If an item with the same ID already exists
        """
        with self.lock:
            if item.item_id in self.items:
                raise ValueError(f"Item with ID {item.item_id} already exists in queue")
            
            try:
                # Add item to priority queue using a tuple for ordering
                # (priority value, timestamp, item_id)
                # This ensures consistent ordering even for same-priority items
                self.queue.put_nowait((
                    item.priority.value,
                    item.added_time,
                    item.item_id
                ))
                self.items[item.item_id] = item
                return True
            except queue.Full:
                return False
    
    def get_next_item(self) -> Optional[DownloadItem]:
        """
        Get the next item from the queue based on priority.
        
        Returns:
            Next download item or None if queue is empty
        """
        try:
            # Get next item from priority queue (non-blocking)
            _, _, item_id = self.queue.get_nowait()
            with self.lock:
                item = self.items.get(item_id)
                if item and item.status == DownloadStatus.QUEUED:
                    # Update status
                    item.status = DownloadStatus.IN_PROGRESS
                    item.started_time = time.time()
                    return item
                # If item was canceled or already processed, skip it
                self.queue.task_done()
                return self.get_next_item()
        except queue.Empty:
            return None
    
    def update_item(self, item_id: str, **kwargs) -> bool:
        """
        Update an item in the queue.
        
        Args:
            item_id: ID of the item to update
            **kwargs: Fields to update
        
        Returns:
            True if item was updated, False if not found
        """
        with self.lock:
            if item_id not in self.items:
                return False
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(self.items[item_id], key):
                    setattr(self.items[item_id], key, value)
            
            return True
    
    def complete_item(self, item_id: str, file_size: Optional[int] = None) -> bool:
        """
        Mark an item as completed.
        
        Args:
            item_id: ID of the item to mark as completed
            file_size: Size of the downloaded file in bytes
        
        Returns:
            True if item was marked as completed, False if not found
        """
        with self.lock:
            if item_id not in self.items:
                return False
            
            item = self.items[item_id]
            item.status = DownloadStatus.COMPLETED
            item.completed_time = time.time()
            if file_size is not None:
                item.file_size = file_size
            
            self.queue.task_done()
            return True
    
    def fail_item(self, item_id: str, error_message: str) -> bool:
        """
        Mark an item as failed.
        
        Args:
            item_id: ID of the item to mark as failed
            error_message: Error message to store
        
        Returns:
            True if item was marked as failed, False if not found
        """
        with self.lock:
            if item_id not in self.items:
                return False
            
            item = self.items[item_id]
            item.attempts += 1
            
            if item.attempts >= item.max_retries:
                item.status = DownloadStatus.FAILED
                item.error_message = error_message
                item.completed_time = time.time()
                self.queue.task_done()
            else:
                # Put back in queue for retry
                item.status = DownloadStatus.QUEUED
                # Increase priority slightly for retries (but not too much)
                new_priority_value = max(item.priority.value - 1, 1)
                new_priority = DownloadPriority(new_priority_value)
                item.priority = new_priority
                
                # Add back to queue
                try:
                    self.queue.put_nowait((
                        item.priority.value,
                        time.time(),  # Use current time for re-queuing
                        item.item_id
                    ))
                except queue.Full:
                    # If queue is full, mark as failed
                    item.status = DownloadStatus.FAILED
                    item.error_message = f"{error_message} (Queue full, cannot retry)"
                    item.completed_time = time.time()
                    self.queue.task_done()
            
            return True
    
    def cancel_item(self, item_id: str) -> bool:
        """
        Cancel a queued item.
        
        Args:
            item_id: ID of the item to cancel
        
        Returns:
            True if item was canceled, False if not found or not cancellable
        """
        with self.lock:
            if item_id not in self.items:
                return False
            
            item = self.items[item_id]
            if item.status not in [DownloadStatus.QUEUED, DownloadStatus.RATE_LIMITED]:
                # Can only cancel queued or rate-limited items
                return False
            
            item.status = DownloadStatus.CANCELED
            item.completed_time = time.time()
            # Note: We can't remove it from the priority queue, but we'll skip it when retrieved
            
            return True
    
    def get_item(self, item_id: str) -> Optional[DownloadItem]:
        """
        Get an item by ID.
        
        Args:
            item_id: ID of the item to get
        
        Returns:
            Download item or None if not found
        """
        with self.lock:
            return self.items.get(item_id)
    
    def get_all_items(self) -> List[DownloadItem]:
        """
        Get all items in the queue.
        
        Returns:
            List of all download items
        """
        with self.lock:
            return list(self.items.values())
    
    def get_queue_stats(self) -> Dict[str, int]:
        """
        Get statistics about the queue.
        
        Returns:
            Dictionary with queue statistics
        """
        with self.lock:
            status_counts = {}
            for status in DownloadStatus:
                status_counts[status.value] = sum(
                    1 for item in self.items.values() if item.status == status
                )
            
            return {
                "total": len(self.items),
                "queued": status_counts[DownloadStatus.QUEUED.value],
                "in_progress": status_counts[DownloadStatus.IN_PROGRESS.value],
                "completed": status_counts[DownloadStatus.COMPLETED.value],
                "failed": status_counts[DownloadStatus.FAILED.value],
                "rate_limited": status_counts[DownloadStatus.RATE_LIMITED.value],
                "canceled": status_counts[DownloadStatus.CANCELED.value],
                "skipped": status_counts[DownloadStatus.SKIPPED.value]
            }
    
    def clear_completed_and_failed(self) -> int:
        """
        Remove completed and failed items from the queue.
        
        Returns:
            Number of items removed
        """
        with self.lock:
            to_remove = []
            
            for item_id, item in self.items.items():
                if item.status in [
                    DownloadStatus.COMPLETED, 
                    DownloadStatus.FAILED,
                    DownloadStatus.CANCELED,
                    DownloadStatus.SKIPPED
                ]:
                    to_remove.append(item_id)
            
            for item_id in to_remove:
                del self.items[item_id]
            
            return len(to_remove)
    
    def size(self) -> int:
        """Get the number of items in the queue."""
        return len(self.items)
    
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self.size() == 0
    
    def save_to_file(self, file_path: str) -> bool:
        """
        Save the queue state to a file.
        
        Args:
            file_path: Path to save the queue state to
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                # Convert items to serializable form
                items_dict = {
                    item_id: item.to_dict()
                    for item_id, item in self.items.items()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(items_dict, f, indent=2)
                
                return True
        except Exception as e:
            logging.error(f"Error saving queue state: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'DownloadQueue':
        """
        Load queue state from a file.
        
        Args:
            file_path: Path to load the queue state from
        
        Returns:
            Loaded download queue
        
        Raises:
            FileNotFoundError: If the file does not exist
        """
        queue = cls()
        
        try:
            with open(file_path, 'r') as f:
                items_dict = json.load(f)
            
            for item_id, item_data in items_dict.items():
                # Skip completed or failed items
                status = DownloadStatus(item_data.get("status", DownloadStatus.QUEUED.value))
                if status in [
                    DownloadStatus.COMPLETED, 
                    DownloadStatus.FAILED,
                    DownloadStatus.CANCELED,
                    DownloadStatus.SKIPPED
                ]:
                    continue
                
                # Reset in_progress to queued for restoring
                if status == DownloadStatus.IN_PROGRESS:
                    item_data["status"] = DownloadStatus.QUEUED.value
                
                # Create download item
                item = DownloadItem.from_dict(item_data)
                
                # Add to queue
                queue.add_item(item)
        except FileNotFoundError:
            raise
        except Exception as e:
            logging.error(f"Error loading queue state: {e}")
        
        return queue


class HttpClient:
    """
    HTTP client with rate limiting and retry logic.
    
    This class handles making HTTP requests with appropriate rate limiting,
    retries, and error handling for robust downloads.
    """
    
    def __init__(self, config: DownloaderConfig):
        """
        Initialize the HTTP client.
        
        Args:
            config: Downloader configuration
        """
        self.config = config
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml,*/*"
        })
        
        # Create rate limiter
        self.rate_limiter = RateLimiter(
            window_size=config.rate_limit_window,
            max_requests=config.rate_limit_requests,
            default_delay=config.default_request_delay,
            backend_limited=config.adaptive_rate_limiting
        )
    
    def make_request(self, url: str, method: str = "GET", 
                    headers: Optional[Dict[str, str]] = None,
                    params: Optional[Dict[str, str]] = None,
                    data: Optional[Dict[str, Any]] = None,
                    stream: bool = False,
                    timeout: Optional[float] = None,
                    retry_count: Optional[int] = None) -> Optional[requests.Response]:
        """
        Make an HTTP request with rate limiting and retry logic.
        
        Args:
            url: URL to request
            method: HTTP method (GET, HEAD, etc.)
            headers: Additional headers to include
            params: URL parameters
            data: Request body data for POST/PUT
            stream: Whether to stream the response
            timeout: Request timeout in seconds
            retry_count: Number of retries (uses config default if None)
        
        Returns:
            Response object or None on failure
        
        Raises:
            NetworkError: If the request fails after all retries
            RateLimitError: If rate limiting is detected
        """
        # Use config defaults if not specified
        if timeout is None:
            timeout = self.config.request_timeout
        
        if retry_count is None:
            retry_count = self.config.max_retries
        
        # Wait for rate limiting if needed
        try:
            self.rate_limiter.wait_if_needed()
        except RateLimitError as e:
            raise e
        
        # Try the request with retries
        for attempt in range(retry_count + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    stream=stream,
                    timeout=timeout
                )
                
                # For 404 errors, we can just return None immediately - no need to retry
                if response.status_code == 404:
                    return None
                
                # Return response if successful
                if response.status_code == 200:
                    self.rate_limiter.record_success()
                    return response
                
                # Handle specific error codes
                if response.status_code in (429, 503, 504, 502):
                    # Rate limit or server busy
                    self.rate_limiter.record_error(is_rate_limit=True)
                    
                    # If it's not our last attempt, wait and try again
                    if attempt < retry_count:
                        backoff = min(2 ** attempt * 5 + random.uniform(0, 3), 60)
                        logging.warning(
                            f"Request failed with status {response.status_code}, "
                            f"retrying in {backoff:.2f} seconds (attempt {attempt+1}/{retry_count})"
                        )
                        time.sleep(backoff)
                        continue
                    else:
                        raise RateLimitError(
                            f"Rate limit exceeded after {retry_count} retries: {url}",
                            {"status_code": response.status_code}
                        )
                
                # Other error codes
                self.rate_limiter.record_error()
                if attempt < retry_count:
                    backoff = min(2 ** attempt * 2 + random.uniform(0, 1), 30)
                    logging.warning(
                        f"Request failed with status {response.status_code}, "
                        f"retrying in {backoff:.2f} seconds (attempt {attempt+1}/{retry_count})"
                    )
                    time.sleep(backoff)
                    continue
                else:
                    raise NetworkError(
                        f"Request failed with status {response.status_code}: {url}",
                        {"status_code": response.status_code}
                    )
            
            except (requests.RequestException, ConnectionError, TimeoutError) as e:
                self.rate_limiter.record_error()
                
                if attempt < retry_count:
                    backoff = min(2 ** attempt * 2 + random.uniform(0, 1), 30)
                    logging.warning(
                        f"Request error: {str(e)}, retrying in {backoff:.2f} seconds "
                        f"(attempt {attempt+1}/{retry_count})"
                    )
                    time.sleep(backoff)
                else:
                    raise NetworkError(
                        f"Request failed after {retry_count} retries: {url}",
                        {"error": str(e)}
                    )
        
        # This should never be reached, but just in case
        raise NetworkError(f"Request failed: {url}")
    
    def download_file(self, url: str, destination_path: str,
                     headers: Optional[Dict[str, str]] = None,
                     progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
                     resume: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Download a file with progress tracking and resuming.
        
        Args:
            url: URL to download
            destination_path: Path to save the file to
            headers: Additional headers to include
            progress_callback: Callback function for progress updates
            resume: Whether to resume partial downloads
        
        Returns:
            Tuple of (success, error_message)
        """
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        # Check if file already exists
        existing_size = 0
        if os.path.exists(destination_path):
            existing_size = os.path.getsize(destination_path)
            if existing_size > 0 and not resume:
                # File exists and we're not resuming
                return True, None
        
        # Create progress tracker
        progress = DownloadProgress(
            item_id=str(uuid.uuid4()),
            url=url,
            destination_path=destination_path
        )
        
        # Set up headers for resume if needed
        request_headers = headers.copy() if headers else {}
        if existing_size > 0 and resume:
            request_headers["Range"] = f"bytes={existing_size}-"
            progress.downloaded_size = existing_size
        
        try:
            # Make request
            response = self.make_request(
                url=url,
                headers=request_headers,
                stream=True
            )
            
            if not response:
                error_msg = "File not found"
                if progress_callback:
                    progress.fail(error_msg)
                    progress_callback(progress)
                return False, error_msg
            
            # Get total size
            if "Content-Length" in response.headers:
                content_length = int(response.headers["Content-Length"])
                if existing_size > 0 and resume:
                    # For resumed downloads, content-length is remaining size
                    progress.total_size = existing_size + content_length
                else:
                    progress.total_size = content_length
            
            # Check if size exceeds max download size
            if progress.total_size and progress.total_size > self.config.max_download_size:
                error_msg = f"File size ({progress.total_size} bytes) exceeds maximum allowed size"
                if progress_callback:
                    progress.fail(error_msg)
                    progress_callback(progress)
                return False, error_msg
            
            # Open file for writing
            mode = "ab" if existing_size > 0 and resume else "wb"
            with open(destination_path, mode) as f:
                # Download file in chunks
                for chunk in response.iter_content(chunk_size=self.config.download_chunk_size):
                    if chunk:
                        f.write(chunk)
                        progress.update(progress.downloaded_size + len(chunk))
                        
                        # Call progress callback
                        if progress_callback:
                            progress_callback(progress)
            
            # Mark as complete
            progress.complete()
            if progress_callback:
                progress_callback(progress)
            
            # Validate download if configured
            if self.config.validate_downloads:
                valid, error = self._validate_download(destination_path)
                if not valid:
                    return False, error
            
            return True, None
        
        except NetworkError as e:
            error_msg = f"Network error: {str(e)}"
            if progress_callback:
                progress.fail(error_msg)
                progress_callback(progress)
            return False, error_msg
        
        except RateLimitError as e:
            error_msg = f"Rate limit error: {str(e)}"
            if progress_callback:
                progress.fail(error_msg)
                progress_callback(progress)
            return False, error_msg
        
        except Exception as e:
            error_msg = f"Error downloading file: {str(e)}"
            if progress_callback:
                progress.fail(error_msg)
                progress_callback(progress)
            return False, error_msg
    
    def _validate_download(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a downloaded file.
        
        Args:
            file_path: Path to the file to validate
        
        Returns:
            Tuple of (valid, error_message)
        """
        # Basic validation - check file exists and is not empty
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "File is empty"
        
        # Try to open the file to make sure it's not corrupted
        try:
            with open(file_path, "rb") as f:
                # Read a small chunk to check
                f.read(1024)
            return True, None
        except Exception as e:
            return False, f"File is corrupted: {str(e)}"


class DownloadWorker(threading.Thread):
    """
    Worker thread for processing downloads from the queue.
    
    This class handles fetching items from the download queue and
    downloading them with appropriate error handling and progress tracking.
    """
    
    def __init__(self, queue: DownloadQueue, http_client: HttpClient,
                 worker_id: int, stop_event: threading.Event,
                 progress_callback: Optional[Callable[[DownloadItem, DownloadProgress], None]] = None):
        """
        Initialize the download worker.
        
        Args:
            queue: Download queue to process
            http_client: HTTP client for making requests
            worker_id: ID of this worker
            stop_event: Event to signal worker to stop
            progress_callback: Callback function for progress updates
        """
        super().__init__(name=f"DownloadWorker-{worker_id}")
        self.queue = queue
        self.http_client = http_client
        self.worker_id = worker_id
        self.stop_event = stop_event
        self.progress_callback = progress_callback
        self.daemon = True  # Allow process to exit even if thread is running
    
    def run(self):
        """Main worker thread loop."""
        logging.info(f"Download worker {self.worker_id} started")
        
        while not self.stop_event.is_set():
            # Get next item from queue
            item = self.queue.get_next_item()
            if not item:
                # No items in queue, sleep and check again
                time.sleep(1)
                continue
            
            logging.info(f"Worker {self.worker_id} processing item {item.item_id}: {item.url}")
            
            # Download file
            progress = DownloadProgress(
                item_id=item.item_id,
                url=item.url,
                destination_path=item.destination_path
            )
            
            try:
                success, error = self.http_client.download_file(
                    url=item.url,
                    destination_path=item.destination_path,
                    progress_callback=lambda p: self._handle_progress(item, p)
                )
                
                if success:
                    # Mark item as completed
                    file_size = os.path.getsize(item.destination_path) if os.path.exists(item.destination_path) else None
                    self.queue.complete_item(item.item_id, file_size)
                    logging.info(f"Worker {self.worker_id} completed item {item.item_id}")
                else:
                    # Mark item as failed
                    self.queue.fail_item(item.item_id, error or "Unknown error")
                    logging.warning(f"Worker {self.worker_id} failed item {item.item_id}: {error}")
            
            except Exception as e:
                # Handle unexpected errors
                error_msg = f"Unexpected error: {str(e)}"
                self.queue.fail_item(item.item_id, error_msg)
                logging.error(f"Worker {self.worker_id} error processing item {item.item_id}: {error_msg}")
        
        logging.info(f"Download worker {self.worker_id} stopped")
    
    def _handle_progress(self, item: DownloadItem, progress: DownloadProgress):
        """
        Handle progress updates.
        
        Args:
            item: Download item being processed
            progress: Download progress information
        """
        if self.progress_callback:
            self.progress_callback(item, progress)


class ChroniclingAmericaDownloader:
    """
    Specialized downloader for ChroniclingAmerica API.
    
    Implements functionality for downloading newspaper content from the
    Library of Congress Chronicling America API.
    """
    
    def __init__(self, config: DownloaderConfig, http_client: HttpClient, 
                 publication_repo: PublicationRepository):
        """
        Initialize the ChroniclingAmerica downloader.
        
        Args:
            config: Downloader configuration
            http_client: HTTP client for making requests
            publication_repo: Publication repository for storing metadata
        """
        self.config = config
        self.http_client = http_client
        self.publication_repo = publication_repo
        self.api_url = config.chronicling_america_api_url
        self.max_pages = config.chronicling_america_max_pages
    
    def check_newspaper_availability(self, lccn: str) -> Optional[Dict[str, Any]]:
        """
        Check if a newspaper is available in the ChroniclingAmerica API.
        
        Args:
            lccn: Library of Congress Control Number
        
        Returns:
            Newspaper metadata or None if not found
        """
        url = f"{self.api_url}/lccn/{lccn}.json"
        
        try:
            response = self.http_client.make_request(url)
            if not response:
                return None
            
            return response.json()
        
        except Exception as e:
            logging.error(f"Error checking newspaper availability: {str(e)}")
            return None
    
    def search_newspapers(self, state: Optional[str] = None, title: Optional[str] = None,
                         year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for newspapers in the ChroniclingAmerica API.
        
        Args:
            state: State to filter by
            title: Title to search for
            year: Year to filter by
        
        Returns:
            List of matching newspapers
        """
        url = f"{self.api_url}/newspapers.json"
        
        params = {}
        if state:
            params["state"] = state
        if title:
            params["terms"] = title
        if year:
            params["year"] = str(year)
        
        try:
            response = self.http_client.make_request(url, params=params)
            if not response:
                return []
            
            data = response.json()
            return data.get("newspapers", [])
        
        except Exception as e:
            logging.error(f"Error searching newspapers: {str(e)}")
            return []
    
    def queue_newspaper_issue(self, queue: DownloadQueue, lccn: str, date: str, 
                            edition: str = "1", output_dir: Optional[str] = None,
                            formats: List[str] = ["jp2", "pdf", "ocr"],
                            priority: DownloadPriority = DownloadPriority.NORMAL) -> List[str]:
        """
        Queue downloads for a newspaper issue.
        
        Args:
            queue: Download queue to add items to
            lccn: Library of Congress Control Number
            date: Date in YYYY-MM-DD format
            edition: Edition number
            output_dir: Output directory (defaults to config)
            formats: List of formats to download
            priority: Download priority
        
        Returns:
            List of queued item IDs
        """
        item_ids = []
        
        # Ensure output directory
        if not output_dir:
            output_dir = os.path.join(self.config.download_dir, lccn.replace("/", "_"), date)
        
        # First, check if issue exists by querying the first page
        base_url = f"{self.api_url}/lccn/{lccn}/{date}/ed-{edition}"
        
        try:
            # Check if first page exists
            check_url = f"{base_url}/seq-1.jp2"
            response = self.http_client.make_request(check_url, method="HEAD")
            
            if not response:
                logging.warning(f"No issue found for {lccn} on {date}")
                return []
            
            # Get newspaper metadata
            metadata = self.check_newspaper_availability(lccn)
            if metadata:
                # Create or get publication
                title = metadata.get("name", lccn)
                place = metadata.get("place_of_publication", "")
                
                # Extract state from place of publication
                state = None
                if place and "," in place:
                    parts = place.split(",")
                    if len(parts) >= 2:
                        state = parts[1].strip()
                
                # Build region data
                region_data = {
                    "country": "United States",
                }
                
                if state:
                    region_data["state"] = state
                
                # Get or create publication
                publication = self.publication_repo.find_publication_by_name(title)
                if not publication:
                    publication_id = self.publication_repo.add_publication(
                        name=title,
                        publication_type_id=self.publication_repo.PUBLICATION_TYPE_NEWSPAPER,
                        region_data=region_data,
                        start_date=metadata.get("start_year"),
                        end_date=metadata.get("end_year"),
                        publisher=metadata.get("publisher"),
                        lccn=lccn
                    )
                else:
                    publication_id = publication["publication_id"]
                
                # Create issue
                issue = self.publication_repo.find_issue(publication_id, date)
                if not issue:
                    issue_id = self.publication_repo.add_issue(
                        publication_id=publication_id,
                        publication_date=date,
                        edition=edition
                    )
                else:
                    issue_id = issue["issue_id"]
            
            # Queue downloads for all available pages
            for page_num in range(1, self.max_pages + 1):
                page_base_url = f"{base_url}/seq-{page_num}"
                
                # Check if this page exists
                check_url = f"{page_base_url}.jp2"
                page_response = self.http_client.make_request(check_url, method="HEAD")
                
                if not page_response:
                    # No more pages
                    break
                
                # Queue downloads for each format
                for fmt in formats:
                    if fmt == "jp2":
                        url = f"{page_base_url}.jp2"
                        output_path = os.path.join(output_dir, f"page_{page_num:04d}.jp2")
                    elif fmt == "pdf":
                        url = f"{page_base_url}.pdf"
                        output_path = os.path.join(output_dir, f"page_{page_num:04d}.pdf")
                    elif fmt == "ocr":
                        url = f"{page_base_url}/ocr.txt"
                        output_path = os.path.join(output_dir, f"page_{page_num:04d}_ocr.txt")
                    else:
                        continue
                    
                    # Create download item
                    item = DownloadItem(
                        url=url,
                        destination_path=output_path,
                        priority=priority,
                        metadata={
                            "lccn": lccn,
                            "date": date,
                            "edition": edition,
                            "page": page_num,
                            "format": fmt,
                            "publication_id": publication_id if 'publication_id' in locals() else None,
                            "issue_id": issue_id if 'issue_id' in locals() else None
                        }
                    )
                    
                    # Add to queue
                    if queue.add_item(item):
                        item_ids.append(item.item_id)
                        
                        # Add page to database if it's a JP2 format (primary image)
                        if fmt == "jp2" and 'issue_id' in locals():
                            self.publication_repo.add_page(
                                issue_id=issue_id,
                                page_number=page_num,
                                image_path=output_path,
                                image_format="jp2"
                            )
            
            return item_ids
        
        except Exception as e:
            logging.error(f"Error queuing newspaper issue: {str(e)}")
            return []
    
    def queue_newspaper_batch(self, queue: DownloadQueue, lccn: str, 
                            start_date: str, end_date: str,
                            output_dir: Optional[str] = None,
                            formats: List[str] = ["jp2", "pdf", "ocr"],
                            priority: DownloadPriority = DownloadPriority.NORMAL) -> Dict[str, List[str]]:
        """
        Queue downloads for a range of dates.
        
        Args:
            queue: Download queue to add items to
            lccn: Library of Congress Control Number
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            output_dir: Output directory (defaults to config)
            formats: List of formats to download
            priority: Download priority
        
        Returns:
            Dictionary mapping dates to lists of queued item IDs
        """
        results = {}
        
        # Parse dates
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        
        # Generate dates
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            
            # Queue issue for this date
            item_ids = self.queue_newspaper_issue(
                queue=queue,
                lccn=lccn,
                date=date_str,
                output_dir=output_dir,
                formats=formats,
                priority=priority
            )
            
            if item_ids:
                results[date_str] = item_ids
            
            # Move to next day
            current += datetime.timedelta(days=1)
        
        return results
    
    def queue_newspaper_dates(self, queue: DownloadQueue, lccn: str, 
                            dates: List[str], output_dir: Optional[str] = None,
                            formats: List[str] = ["jp2", "pdf", "ocr"],
                            priority: DownloadPriority = DownloadPriority.NORMAL) -> Dict[str, List[str]]:
        """
        Queue downloads for specific dates.
        
        Args:
            queue: Download queue to add items to
            lccn: Library of Congress Control Number
            dates: List of dates in YYYY-MM-DD format
            output_dir: Output directory (defaults to config)
            formats: List of formats to download
            priority: Download priority
        
        Returns:
            Dictionary mapping dates to lists of queued item IDs
        """
        results = {}
        
        for date_str in dates:
            # Queue issue for this date
            item_ids = self.queue_newspaper_issue(
                queue=queue,
                lccn=lccn,
                date=date_str,
                output_dir=output_dir,
                formats=formats,
                priority=priority
            )
            
            if item_ids:
                results[date_str] = item_ids
        
        return results


class DownloaderManager:
    """
    Central manager for the download system.
    
    This class coordinates download workers, queues, and specialized downloaders
    to provide a unified interface for downloading content.
    """
    
    def __init__(self, db_manager: DatabaseManager, 
                 publication_repo: PublicationRepository,
                 config: Optional[DownloaderConfig] = None):
        """
        Initialize the downloader manager.
        
        Args:
            db_manager: Database manager
            publication_repo: Publication repository
            config: Downloader configuration (uses defaults if None)
        """
        self.db_manager = db_manager
        self.publication_repo = publication_repo
        self.config = config or DownloaderConfig()
        
        # Create download directory
        base_path = self.db_manager.config.base_path
        self.download_dir = os.path.join(base_path, self.config.download_dir)
        self.temp_dir = os.path.join(base_path, self.config.temp_dir)
        
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Create queue file path
        self.queue_file = os.path.join(self.temp_dir, "download_queue.json")
        
        # Create download queue
        self.queue = self._load_queue()
        
        # Create HTTP client
        self.http_client = HttpClient(self.config)
        
        # Create specialized downloaders
        self.ca_downloader = ChroniclingAmericaDownloader(
            config=self.config,
            http_client=self.http_client,
            publication_repo=self.publication_repo
        )
        
        # Worker management
        self.workers = []
        self.stop_event = threading.Event()
        self.progress_callbacks = []
        
        # Download tracking
        self.active_downloads = {}  # item_id -> DownloadProgress
        self.download_lock = threading.RLock()
        
        # Start workers
        self.start_workers()
    
    def _load_queue(self) -> DownloadQueue:
        """
        Load download queue from file if available.
        
        Returns:
            Download queue
        """
        try:
            return DownloadQueue.load_from_file(self.queue_file)
        except FileNotFoundError:
            return DownloadQueue(max_size=self.config.max_queue_size)
        except Exception as e:
            logging.error(f"Error loading download queue: {str(e)}")
            return DownloadQueue(max_size=self.config.max_queue_size)
    
    def save_queue(self) -> bool:
        """
        Save download queue to file.
        
        Returns:
            True if successful, False otherwise
        """
        return self.queue.save_to_file(self.queue_file)
    
    def start_workers(self, num_workers: Optional[int] = None) -> None:
        """
        Start download worker threads.
        
        Args:
            num_workers: Number of workers to start (uses config default if None)
        """
        # Use config default if not specified
        if num_workers is None:
            num_workers = self.config.max_concurrent_downloads
        
        # Stop existing workers if any
        self.stop_workers()
        
        # Reset stop event
        self.stop_event.clear()
        
        # Create workers
        self.workers = []
        for i in range(num_workers):
            worker = DownloadWorker(
                queue=self.queue,
                http_client=self.http_client,
                worker_id=i,
                stop_event=self.stop_event,
                progress_callback=self._handle_progress
            )
            worker.start()
            self.workers.append(worker)
        
        logging.info(f"Started {len(self.workers)} download workers")
    
    def stop_workers(self) -> None:
        """Stop all download worker threads."""
        if self.workers:
            # Set stop event to signal workers to stop
            self.stop_event.set()
            
            # Wait for workers to finish
            for worker in self.workers:
                worker.join(timeout=2)
            
            self.workers = []
            logging.info("All download workers stopped")
    
    def add_progress_callback(self, callback: Callable[[DownloadItem, DownloadProgress], None]) -> None:
        """
        Add a callback for download progress updates.
        
        Args:
            callback: Callback function
        """
        self.progress_callbacks.append(callback)
    
    def _handle_progress(self, item: DownloadItem, progress: DownloadProgress) -> None:
        """
        Handle progress updates from workers.
        
        Args:
            item: Download item being processed
            progress: Download progress information
        """
        with self.download_lock:
            # Update active downloads tracking
            self.active_downloads[item.item_id] = progress
            
            # Call registered callbacks
            for callback in self.progress_callbacks:
                try:
                    callback(item, progress)
                except Exception as e:
                    logging.error(f"Error in progress callback: {str(e)}")
    
    def queue_url(self, url: str, destination_path: Optional[str] = None,
                 priority: DownloadPriority = DownloadPriority.NORMAL,
                 metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Queue a URL for download.
        
        Args:
            url: URL to download
            destination_path: Path to save the file to (uses auto-generated path if None)
            priority: Download priority
            metadata: Additional metadata
        
        Returns:
            Download item ID or None if queue is full
        """
        # Generate destination path if not provided
        if not destination_path:
            # Parse URL for filename
            url_path = urlparse(url).path
            filename = os.path.basename(url_path) or "download.bin"
            
            # Create destination path in download directory
            destination_path = os.path.join(
                self.download_dir,
                "direct",
                datetime.datetime.now().strftime("%Y%m%d"),
                filename
            )
        
        # Create download item
        item = DownloadItem(
            url=url,
            destination_path=destination_path,
            priority=priority,
            metadata=metadata or {}
        )
        
        # Add to queue
        if self.queue.add_item(item):
            # Save queue state
            self.save_queue()
            return item.item_id
        
        return None
    
    def queue_chronicling_america_issue(self, lccn: str, date: str, 
                                      formats: List[str] = ["jp2", "pdf", "ocr"],
                                      priority: DownloadPriority = DownloadPriority.NORMAL) -> List[str]:
        """
        Queue downloads for a ChroniclingAmerica newspaper issue.
        
        Args:
            lccn: Library of Congress Control Number
            date: Date in YYYY-MM-DD format
            formats: List of formats to download
            priority: Download priority
        
        Returns:
            List of queued item IDs
        """
        # Create output directory
        output_dir = os.path.join(
            self.download_dir,
            "chroniclingamerica",
            lccn.replace("/", "_"),
            date.replace("-", "")
        )
        
        # Queue downloads
        item_ids = self.ca_downloader.queue_newspaper_issue(
            queue=self.queue,
            lccn=lccn,
            date=date,
            output_dir=output_dir,
            formats=formats,
            priority=priority
        )
        
        # Save queue state
        if item_ids:
            self.save_queue()
        
        return item_ids
    
    def queue_chronicling_america_batch(self, lccn: str, start_date: str, end_date: str,
                                      formats: List[str] = ["jp2", "pdf", "ocr"],
                                      priority: DownloadPriority = DownloadPriority.NORMAL) -> Dict[str, List[str]]:
        """
        Queue downloads for a range of ChroniclingAmerica newspaper issues.
        
        Args:
            lccn: Library of Congress Control Number
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            formats: List of formats to download
            priority: Download priority
        
        Returns:
            Dictionary mapping dates to lists of queued item IDs
        """
        # Create output directory
        output_dir = os.path.join(
            self.download_dir,
            "chroniclingamerica",
            lccn.replace("/", "_")
        )
        
        # Queue downloads
        results = self.ca_downloader.queue_newspaper_batch(
            queue=self.queue,
            lccn=lccn,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            formats=formats,
            priority=priority
        )
        
        # Save queue state
        if results:
            self.save_queue()
        
        return results
    
    def cancel_download(self, item_id: str) -> bool:
        """
        Cancel a queued download.
        
        Args:
            item_id: Download item ID
        
        Returns:
            True if canceled, False otherwise
        """
        result = self.queue.cancel_item(item_id)
        
        # Save queue state
        if result:
            self.save_queue()
        
        return result
    
    def get_download_status(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a download.
        
        Args:
            item_id: Download item ID
        
        Returns:
            Dictionary with download status or None if not found
        """
        item = self.queue.get_item(item_id)
        if not item:
            return None
        
        # Check for active download progress
        progress = None
        with self.download_lock:
            if item_id in self.active_downloads:
                progress = self.active_downloads[item_id]
        
        # Build status dictionary
        status = {
            "item_id": item.item_id,
            "url": item.url,
            "destination_path": item.destination_path,
            "status": item.status.value,
            "attempts": item.attempts,
            "added_time": item.added_time,
            "started_time": item.started_time,
            "completed_time": item.completed_time,
            "error_message": item.error_message,
            "file_size": item.file_size
        }
        
        # Add progress information if available
        if progress:
            status.update({
                "downloaded_size": progress.downloaded_size,
                "total_size": progress.total_size,
                "progress_percentage": progress.progress_percentage,
                "download_speed": progress.download_speed,
                "elapsed_time": progress.elapsed_time,
                "estimated_time_remaining": progress.estimated_time_remaining
            })
        
        return status
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get status of the download queue.
        
        Returns:
            Dictionary with queue status
        """
        stats = self.queue.get_queue_stats()
        
        # Add worker status
        stats["workers"] = {
            "total": len(self.workers),
            "active": sum(1 for w in self.workers if w.is_alive())
        }
        
        # Add active downloads
        with self.download_lock:
            active_count = sum(1 for p in self.active_downloads.values() 
                            if p.status == DownloadStatus.IN_PROGRESS)
            stats["active_downloads"] = active_count
        
        return stats
    
    def clear_completed_downloads(self) -> int:
        """
        Remove completed and failed downloads from the queue.
        
        Returns:
            Number of items removed
        """
        count = self.queue.clear_completed_and_failed()
        
        # Save queue state
        if count > 0:
            self.save_queue()
        
        return count
    
    def search_chronicling_america(self, state: Optional[str] = None, 
                                 title: Optional[str] = None,
                                 year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for newspapers in ChroniclingAmerica.
        
        Args:
            state: State to filter by
            title: Title to search for
            year: Year to filter by
        
        Returns:
            List of matching newspapers
        """
        return self.ca_downloader.search_newspapers(state, title, year)
    
    def shutdown(self) -> None:
        """Shutdown the downloader manager."""
        # Stop workers
        self.stop_workers()
        
        # Save queue state
        self.save_queue()
        
        logging.info("Downloader manager shutdown complete")
    
    def process_downloaded_files(self) -> Dict[str, int]:
        """
        Process downloaded files and update database.
        
        Returns:
            Dictionary with counts of processed items
        """
        stats = {
            "pages_processed": 0,
            "ocr_files_processed": 0,
            "errors": 0
        }
        
        # Get completed downloads
        completed_items = [
            item for item in self.queue.get_all_items()
            if item.status == DownloadStatus.COMPLETED
        ]
        
        for item in completed_items:
            try:
                # Skip if file doesn't exist
                if not os.path.isfile(item.destination_path):
                    continue
                
                # Process based on metadata
                metadata = item.metadata
                if not metadata:
                    continue
                
                # If we have issue_id and page number, update page record
                issue_id = metadata.get("issue_id")
                page_num = metadata.get("page")
                fmt = metadata.get("format")
                
                if issue_id and page_num and fmt:
                    # Find page
                    page = self.publication_repo.find_page(issue_id, page_num)
                    if page:
                        if fmt == "jp2":
                            # Update page image
                            self.publication_repo.update_page(
                                page["page_id"],
                                image_path=item.destination_path,
                                image_format="jp2"
                            )
                            stats["pages_processed"] += 1
                        
                        elif fmt == "ocr":
                            # Update page OCR status
                            self.publication_repo.update_page(
                                page["page_id"],
                                ocr_status="completed",
                                ocr_processed_at=datetime.datetime.now().isoformat(),
                                has_text_content=True
                            )
                            stats["ocr_files_processed"] += 1
            
            except Exception as e:
                logging.error(f"Error processing downloaded file: {str(e)}")
                stats["errors"] += 1
        
        return stats