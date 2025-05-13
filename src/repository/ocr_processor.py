#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCR processing pipeline for the Nova newspaper repository system.

This module implements a comprehensive OCR processing system for historical
newspaper images, with specialized components for layout analysis, article
segmentation, and text extraction. It handles the multi-column layout common
in newspapers and integrates with the repository for storage of processed content.
"""

import os
import cv2
import numpy as np
import pytesseract
import tempfile
import logging
import json
import re
import time
import threading
import queue
import uuid
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from .base_repository import (
    BaseRepository, RepositoryConfig, RepositoryError, RepositoryStatus,
    StorageError, InvalidPathError
)
from .database_manager import DatabaseManager
from .publication_repository import PublicationRepository


class OCRError(RepositoryError):
    """Base exception class for OCR-related errors."""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        super().__init__(message, error_code, details)


class ImageProcessingError(OCRError):
    """Exception raised when image processing fails."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "IMAGE_PROCESSING_ERROR", details)


class TesseractError(OCRError):
    """Exception raised when Tesseract OCR fails."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "TESSERACT_ERROR", details)


class SegmentationError(OCRError):
    """Exception raised when article segmentation fails."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "SEGMENTATION_ERROR", details)


class RegionType(Enum):
    """Types of detected regions in a newspaper page."""
    TITLE = "title"
    SUBTITLE = "subtitle"
    ARTICLE = "article"
    ADVERTISEMENT = "advertisement"
    IMAGE = "image"
    CAPTION = "caption"
    TABLE = "table"
    MASTHEAD = "masthead"
    PAGE_NUMBER = "page_number"
    DATE = "date"
    UNKNOWN = "unknown"


class ProcessingMode(Enum):
    """Processing modes for OCR with different quality/speed tradeoffs."""
    FAST = "fast"  # Quick processing with basic preprocessing
    STANDARD = "standard"  # Balanced processing with moderate enhancements
    QUALITY = "quality"  # Thorough processing with all enhancements
    ARCHIVAL = "archival"  # Maximum quality with advanced error correction


class ProcessingPriority(Enum):
    """Priority levels for the processing queue."""
    CRITICAL = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    BACKGROUND = 10


class ProcessingStatus(Enum):
    """Status values for processing operations."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class OCRConfig:
    """Configuration for OCR processing."""
    # Tesseract settings
    tesseract_path: Optional[str] = None  # Path to Tesseract executable, or None for default
    language: str = "eng"  # OCR language
    psm_mode: int = 4  # Page Segmentation Mode (4 for multi-column text)
    oem_mode: int = 3  # OCR Engine Mode (3 for LSTM neural network)
    
    # Image enhancement settings
    enhance_contrast: bool = True
    contrast_factor: float = 1.5
    enhance_brightness: bool = True
    brightness_factor: float = 1.2
    enhance_sharpness: bool = True
    sharpness_factor: float = 1.3
    denoise: bool = True
    deskew: bool = True
    
    # Layout analysis settings
    detect_columns: bool = True
    min_column_width_ratio: float = 0.05  # Minimum width as ratio of page width
    max_column_width_ratio: float = 0.4  # Maximum width as ratio of page width
    min_title_height_ratio: float = 0.02  # Minimum height for headlines
    detect_article_boundaries: bool = True
    
    # Text post-processing
    apply_error_correction: bool = True
    correct_common_ocr_errors: bool = True
    use_publication_dictionary: bool = False
    publication_dictionary_path: Optional[str] = None
    
    # Processing options
    timeout_seconds: int = 300  # Maximum processing time per page
    max_image_dimension: int = 4000  # Resize images larger than this
    processing_mode: ProcessingMode = ProcessingMode.STANDARD
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for saving."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'OCRConfig':
        """Create config from dictionary."""
        config = cls()
        for key, value in config_dict.items():
            if hasattr(config, key):
                # Convert string to enum if needed
                if key == "processing_mode" and isinstance(value, str):
                    value = ProcessingMode(value)
                setattr(config, key, value)
        return config
    
    def get_tesseract_config(self, hocr: bool = False) -> str:
        """Get Tesseract configuration string."""
        config = f"--psm {self.psm_mode} --oem {self.oem_mode}"
        
        if hocr:
            config += " hocr"
        
        return config


@dataclass
class TextRegion:
    """Represents a text region in a newspaper page."""
    x: int
    y: int
    width: int
    height: int
    region_type: RegionType = RegionType.UNKNOWN
    text: str = ""
    confidence: float = 0.0
    image_path: Optional[str] = None
    
    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Get bounding box as tuple (x, y, width, height)."""
        return (self.x, self.y, self.width, self.height)
    
    @property
    def area(self) -> int:
        """Calculate area of the region."""
        return self.width * self.height
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "region_type": self.region_type.value,
            "text": self.text,
            "confidence": self.confidence,
            "image_path": self.image_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextRegion':
        """Create from dictionary."""
        region_type = RegionType(data.get("region_type", RegionType.UNKNOWN.value))
        return cls(
            x=data["x"],
            y=data["y"],
            width=data["width"],
            height=data["height"],
            region_type=region_type,
            text=data.get("text", ""),
            confidence=data.get("confidence", 0.0),
            image_path=data.get("image_path")
        )


@dataclass
class Article:
    """Represents an extracted article from a newspaper page."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    content: str = ""
    regions: List[TextRegion] = field(default_factory=list)
    confidence: float = 0.0
    article_type: str = "news"
    start_page: Optional[int] = None
    continued_pages: List[int] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "content": self.content,
            "regions": [r.to_dict() for r in self.regions],
            "confidence": self.confidence,
            "article_type": self.article_type,
            "start_page": self.start_page,
            "continued_pages": self.continued_pages
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Article':
        """Create from dictionary."""
        regions = [TextRegion.from_dict(r) for r in data.get("regions", [])]
        return cls(
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            content=data.get("content", ""),
            regions=regions,
            confidence=data.get("confidence", 0.0),
            article_type=data.get("article_type", "news"),
            start_page=data.get("start_page"),
            continued_pages=data.get("continued_pages", [])
        )


@dataclass
class ProcessingItem:
    """Represents a single item in the OCR processing queue."""
    page_id: int
    image_path: str
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: ProcessingPriority = ProcessingPriority.NORMAL
    status: ProcessingStatus = ProcessingStatus.QUEUED
    config: Optional[OCRConfig] = None
    issue_id: Optional[int] = None
    page_number: Optional[int] = None
    publication_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    added_time: float = field(default_factory=time.time)
    started_time: Optional[float] = None
    completed_time: Optional[float] = None
    
    def __post_init__(self):
        """Initialize computed properties after instance creation."""
        # Convert priority to enum if needed
        if isinstance(self.priority, int):
            self.priority = ProcessingPriority(self.priority)
        
        # Convert status to enum if needed
        if isinstance(self.status, str):
            self.status = ProcessingStatus(self.status)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "page_id": self.page_id,
            "image_path": self.image_path,
            "item_id": self.item_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "config": self.config.to_dict() if self.config else None,
            "issue_id": self.issue_id,
            "page_number": self.page_number,
            "publication_id": self.publication_id,
            "metadata": self.metadata,
            "error_message": self.error_message,
            "added_time": self.added_time,
            "started_time": self.started_time,
            "completed_time": self.completed_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingItem':
        """Create from dictionary."""
        # Convert enum values from string/int
        priority = ProcessingPriority(data.get("priority", ProcessingPriority.NORMAL.value))
        status = ProcessingStatus(data.get("status", ProcessingStatus.QUEUED.value))
        
        # Convert config
        config = None
        if data.get("config"):
            config = OCRConfig.from_dict(data["config"])
        
        return cls(
            page_id=data["page_id"],
            image_path=data["image_path"],
            item_id=data.get("item_id", str(uuid.uuid4())),
            priority=priority,
            status=status,
            config=config,
            issue_id=data.get("issue_id"),
            page_number=data.get("page_number"),
            publication_id=data.get("publication_id"),
            metadata=data.get("metadata", {}),
            error_message=data.get("error_message"),
            added_time=data.get("added_time", time.time()),
            started_time=data.get("started_time"),
            completed_time=data.get("completed_time")
        )


@dataclass
class ProcessingResult:
    """Result of OCR processing."""
    item_id: str
    page_id: int
    success: bool
    ocr_text: Optional[str] = None
    hocr_text: Optional[str] = None
    regions: List[TextRegion] = field(default_factory=list)
    articles: List[Article] = field(default_factory=list)
    confidence: float = 0.0
    processing_time: float = 0.0
    error_message: Optional[str] = None
    output_files: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "item_id": self.item_id,
            "page_id": self.page_id,
            "success": self.success,
            "ocr_text": self.ocr_text,
            "hocr_text": self.hocr_text,
            "regions": [r.to_dict() for r in self.regions],
            "articles": [a.to_dict() for a in self.articles],
            "confidence": self.confidence,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "output_files": self.output_files
        }


class ProcessingQueue:
    """
    Manages a prioritized queue of OCR processing items.
    
    This class handles adding, retrieving, and updating items in the
    processing queue with proper thread safety and priority ordering.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize the processing queue.
        
        Args:
            max_size: Maximum queue size
        """
        self.max_size = max_size
        self.queue = queue.PriorityQueue(maxsize=max_size)
        self.items = {}  # Dictionary mapping item_id to ProcessingItem
        self.lock = threading.RLock()
    
    def add_item(self, item: ProcessingItem) -> bool:
        """
        Add an item to the processing queue.
        
        Args:
            item: Processing item to add
        
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
    
    def get_next_item(self) -> Optional[ProcessingItem]:
        """
        Get the next item from the queue based on priority.
        
        Returns:
            Next processing item or None if queue is empty
        """
        try:
            # Get next item from priority queue (non-blocking)
            _, _, item_id = self.queue.get_nowait()
            with self.lock:
                item = self.items.get(item_id)
                if item and item.status == ProcessingStatus.QUEUED:
                    # Update status
                    item.status = ProcessingStatus.IN_PROGRESS
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
    
    def complete_item(self, item_id: str) -> bool:
        """
        Mark an item as completed.
        
        Args:
            item_id: ID of the item to mark as completed
        
        Returns:
            True if item was marked as completed, False if not found
        """
        with self.lock:
            if item_id not in self.items:
                return False
            
            item = self.items[item_id]
            item.status = ProcessingStatus.COMPLETED
            item.completed_time = time.time()
            
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
            item.status = ProcessingStatus.FAILED
            item.error_message = error_message
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
            if item.status != ProcessingStatus.QUEUED:
                # Can only cancel queued items
                return False
            
            item.status = ProcessingStatus.CANCELED
            item.completed_time = time.time()
            # Note: We can't remove it from the priority queue, but we'll skip it when retrieved
            
            return True
    
    def get_item(self, item_id: str) -> Optional[ProcessingItem]:
        """
        Get an item by ID.
        
        Args:
            item_id: ID of the item to get
        
        Returns:
            Processing item or None if not found
        """
        with self.lock:
            return self.items.get(item_id)
    
    def get_all_items(self) -> List[ProcessingItem]:
        """
        Get all items in the queue.
        
        Returns:
            List of all processing items
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
            for status in ProcessingStatus:
                status_counts[status.value] = sum(
                    1 for item in self.items.values() if item.status == status
                )
            
            return {
                "total": len(self.items),
                "queued": status_counts[ProcessingStatus.QUEUED.value],
                "in_progress": status_counts[ProcessingStatus.IN_PROGRESS.value],
                "completed": status_counts[ProcessingStatus.COMPLETED.value],
                "failed": status_counts[ProcessingStatus.FAILED.value],
                "canceled": status_counts[ProcessingStatus.CANCELED.value]
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
                    ProcessingStatus.COMPLETED, 
                    ProcessingStatus.FAILED,
                    ProcessingStatus.CANCELED
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
    def load_from_file(cls, file_path: str) -> 'ProcessingQueue':
        """
        Load queue state from a file.
        
        Args:
            file_path: Path to load the queue state from
        
        Returns:
            Loaded processing queue
        
        Raises:
            FileNotFoundError: If the file does not exist
        """
        queue = cls()
        
        try:
            with open(file_path, 'r') as f:
                items_dict = json.load(f)
            
            for item_id, item_data in items_dict.items():
                # Skip completed or failed items
                status = ProcessingStatus(item_data.get("status", ProcessingStatus.QUEUED.value))
                if status in [
                    ProcessingStatus.COMPLETED, 
                    ProcessingStatus.FAILED,
                    ProcessingStatus.CANCELED
                ]:
                    continue
                
                # Reset in_progress to queued for restoring
                if status == ProcessingStatus.IN_PROGRESS:
                    item_data["status"] = ProcessingStatus.QUEUED.value
                
                # Create processing item
                item = ProcessingItem.from_dict(item_data)
                
                # Add to queue
                queue.add_item(item)
        except FileNotFoundError:
            raise
        except Exception as e:
            logging.error(f"Error loading queue state: {e}")
        
        return queue


class ProcessingWorker(threading.Thread):
    """
    Worker thread for processing items from the OCR queue.
    
    This class handles fetching items from the processing queue and
    running OCR on them with appropriate error handling.
    """
    
    def __init__(self, queue: ProcessingQueue, processor: 'OCRProcessor',
                 worker_id: int, stop_event: threading.Event,
                 result_callback: Optional[Callable[[ProcessingResult], None]] = None):
        """
        Initialize the processing worker.
        
        Args:
            queue: Processing queue to fetch items from
            processor: OCR processor for processing items
            worker_id: ID of this worker
            stop_event: Event to signal worker to stop
            result_callback: Callback function for processing results
        """
        super().__init__(name=f"OCRWorker-{worker_id}")
        self.queue = queue
        self.processor = processor
        self.worker_id = worker_id
        self.stop_event = stop_event
        self.result_callback = result_callback
        self.daemon = True  # Allow process to exit even if thread is running
    
    def run(self):
        """Main worker thread loop."""
        logging.info(f"OCR worker {self.worker_id} started")
        
        while not self.stop_event.is_set():
            # Get next item from queue
            item = self.queue.get_next_item()
            if not item:
                # No items in queue, sleep and check again
                time.sleep(1)
                continue
            
            logging.info(f"Worker {self.worker_id} processing item {item.item_id}: Page {item.page_id}")
            
            try:
                # Start timer
                start_time = time.time()
                
                # Process the image
                ocr_text, hocr_text, regions, articles = self.processor.process_image(
                    image_path=item.image_path,
                    config=item.config
                )
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Calculate overall confidence
                if regions:
                    confidence = sum(r.confidence for r in regions) / len(regions)
                else:
                    confidence = 0.0
                
                # Create result object
                result = ProcessingResult(
                    item_id=item.item_id,
                    page_id=item.page_id,
                    success=True,
                    ocr_text=ocr_text,
                    hocr_text=hocr_text,
                    regions=regions,
                    articles=articles,
                    confidence=confidence,
                    processing_time=processing_time
                )
                
                # Mark item as completed
                self.queue.complete_item(item.item_id)
                
                # Call result callback
                if self.result_callback:
                    self.result_callback(result)
                
                logging.info(
                    f"Worker {self.worker_id} completed item {item.item_id} "
                    f"in {processing_time:.2f}s: {len(regions)} regions, "
                    f"{len(articles)} articles"
                )
            
            except Exception as e:
                # Mark item as failed
                self.queue.fail_item(item.item_id, str(e))
                
                # Create error result
                result = ProcessingResult(
                    item_id=item.item_id,
                    page_id=item.page_id,
                    success=False,
                    error_message=str(e)
                )
                
                # Call result callback
                if self.result_callback:
                    self.result_callback(result)
                
                logging.error(f"Worker {self.worker_id} failed to process item {item.item_id}: {str(e)}")
        
        logging.info(f"OCR worker {self.worker_id} stopped")


class OCRProcessor:
    """
    Implements the OCR processing pipeline for newspaper images.
    
    This class provides methods for image preprocessing, OCR, layout analysis,
    and article segmentation specialized for historical newspapers.
    """
    
    def __init__(self, db_manager: DatabaseManager, publication_repo: PublicationRepository,
                 config: Optional[OCRConfig] = None):
        """
        Initialize the OCR processor.
        
        Args:
            db_manager: Database manager
            publication_repo: Publication repository
            config: OCR configuration (uses defaults if None)
        """
        self.db_manager = db_manager
        self.publication_repo = publication_repo
        self.config = config or OCRConfig()
        
        # Set up Tesseract path if provided
        if self.config.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_path
        
        # Validate Tesseract installation
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            raise TesseractError(f"Failed to initialize Tesseract: {str(e)}")
        
        # Create output directories
        base_path = self.db_manager.config.base_path
        output_dir = os.path.join(base_path, "ocr_output")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        self.text_dir = self.output_dir / "text"
        self.hocr_dir = self.output_dir / "hocr"
        self.regions_dir = self.output_dir / "regions"
        self.articles_dir = self.output_dir / "articles"
        
        for directory in [self.text_dir, self.hocr_dir, self.regions_dir, self.articles_dir]:
            directory.mkdir(exist_ok=True)
        
        # Create dictionary of common OCR errors for correction
        self.ocr_corrections = self._init_ocr_corrections()
        
        # Keep track of supported publication dictionaries
        self.publication_dictionaries = {}
        
        # Initialize processing queue and workers
        self.queue = ProcessingQueue()
        self.stop_event = threading.Event()
        self.workers = []
        self.max_workers = 2  # Default number of workers
    
    def _init_ocr_corrections(self) -> Dict[str, str]:
        """Initialize dictionary of common OCR errors and their corrections."""
        return {
            # Common OCR errors in historical newspapers
            "tbe": "the",
            "tbat": "that",
            "tbe": "the",
            "bave": "have",
            "witb": "with",
            "tbis": "this",
            "tban": "than",
            "tbese": "these",
            "tbose": "those",
            "tben": "then",
            "tbere": "there",
            "tbeir": "their",
            "tbey": "they",
            "bere": "here",
            "bim": "him",
            "ber": "her",
            "wbere": "where",
            "wben": "when",
            "wbich": "which",
            "wbo": "who",
            "wbat": "what",
            "wby": "why",
            "bave": "have",
            "bas": "has",
            "bad": "had",
            "tbrough": "through",
            "tbought": "thought",
            "tbousand": "thousand",
            "tbree": "three",
            "tbe": "the",
            "Tbe": "The",
            ",,": ",",
            "..": ".",
            "''": "\"",
            "``": "\"",
            # Date-related corrections
            "Januarv": "January",
            "Januaiy": "January",
            "Februarv": "February",
            "Februaiy": "February",
            "Apiil": "April",
            "Julv": "July",
            "Augnst": "August",
            "Septeniber": "September",
            "0ctober": "October",
            "Noveraber": "November",
            "Decernber": "December",
        }
    
    def start_workers(self, num_workers: int = 2) -> None:
        """
        Start OCR worker threads.
        
        Args:
            num_workers: Number of worker threads to start
        """
        # Stop existing workers if any
        self.stop_workers()
        
        # Reset stop event
        self.stop_event.clear()
        
        # Save number of workers
        self.max_workers = num_workers
        
        # Create workers
        self.workers = []
        for i in range(num_workers):
            worker = ProcessingWorker(
                queue=self.queue,
                processor=self,
                worker_id=i,
                stop_event=self.stop_event,
                result_callback=self._handle_result
            )
            worker.start()
            self.workers.append(worker)
        
        logging.info(f"Started {len(self.workers)} OCR workers")
    
    def stop_workers(self) -> None:
        """Stop all OCR worker threads."""
        if self.workers:
            # Set stop event to signal workers to stop
            self.stop_event.set()
            
            # Wait for workers to finish
            for worker in self.workers:
                worker.join(timeout=2)
            
            self.workers = []
            logging.info("All OCR workers stopped")
    
    def queue_page(self, page_id: int, image_path: str, config: Optional[OCRConfig] = None,
                  issue_id: Optional[int] = None, page_number: Optional[int] = None,
                  publication_id: Optional[int] = None, priority: ProcessingPriority = ProcessingPriority.NORMAL,
                  metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Queue a page for OCR processing.
        
        Args:
            page_id: ID of the page in the database
            image_path: Path to the page image
            config: OCR configuration (uses default if None)
            issue_id: ID of the issue this page belongs to
            page_number: Page number within the issue
            publication_id: ID of the publication
            priority: Processing priority
            metadata: Additional metadata
        
        Returns:
            ID of the queued item
        
        Raises:
            ValueError: If the image file does not exist
            ProcessingQueueFullError: If the queue is full
        """
        # Check if image exists
        if not os.path.isfile(image_path):
            raise ValueError(f"Image file not found: {image_path}")
        
        # Create processing item
        item = ProcessingItem(
            page_id=page_id,
            image_path=image_path,
            config=config or self.config,
            issue_id=issue_id,
            page_number=page_number,
            publication_id=publication_id,
            priority=priority,
            metadata=metadata or {}
        )
        
        # Add to queue
        if not self.queue.add_item(item):
            raise OCRError("Processing queue is full")
        
        # Start workers if not running
        if not self.workers:
            self.start_workers(self.max_workers)
        
        return item.item_id
    
    def get_processing_status(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a processing item.
        
        Args:
            item_id: ID of the processing item
        
        Returns:
            Dictionary with status information or None if not found
        """
        item = self.queue.get_item(item_id)
        if not item:
            return None
        
        return {
            "item_id": item.item_id,
            "page_id": item.page_id,
            "status": item.status.value,
            "added_time": item.added_time,
            "started_time": item.started_time,
            "completed_time": item.completed_time,
            "error_message": item.error_message
        }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get the status of the processing queue.
        
        Returns:
            Dictionary with queue statistics and worker status
        """
        stats = self.queue.get_queue_stats()
        
        # Add worker status
        stats["workers"] = {
            "total": len(self.workers),
            "active": sum(1 for w in self.workers if w.is_alive())
        }
        
        return stats
    
    def cancel_processing(self, item_id: str) -> bool:
        """
        Cancel a queued processing item.
        
        Args:
            item_id: ID of the processing item to cancel
        
        Returns:
            True if the item was canceled, False if not found or not cancellable
        """
        return self.queue.cancel_item(item_id)
    
    def process_image(self, image_path: str, config: Optional[OCRConfig] = None,
                     output_dir: Optional[str] = None) -> Tuple[str, str, List[TextRegion], List[Article]]:
        """
        Process a newspaper image through the OCR pipeline.
        
        Args:
            image_path: Path to the image file
            config: OCR configuration (uses default if None)
            output_dir: Directory to save output files (uses default if None)
        
        Returns:
            Tuple of (ocr_text, hocr_text, regions, articles)
        
        Raises:
            ImageProcessingError: If image processing fails
            TesseractError: If OCR fails
            SegmentationError: If article segmentation fails
        """
        # Use default config if not provided
        if not config:
            config = self.config
        
        try:
            # Load and preprocess image
            preprocessed_image = self._preprocess_image(image_path, config)
            
            # Run Tesseract OCR
            ocr_text = pytesseract.image_to_string(
                preprocessed_image,
                lang=config.language,
                config=config.get_tesseract_config()
            )
            
            # Run Tesseract with HOCR output
            hocr_text = pytesseract.image_to_string(
                preprocessed_image,
                lang=config.language,
                config=config.get_tesseract_config(hocr=True)
            )
            
            # Generate output directories if provided
            if output_dir:
                output_base = Path(output_dir)
            else:
                # Use default output directories
                image_name = os.path.splitext(os.path.basename(image_path))[0]
                output_base = self.output_dir / image_name
                output_base.mkdir(exist_ok=True)
            
            # Save OCR text
            text_path = output_base / "text.txt"
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(ocr_text)
            
            # Save HOCR text
            hocr_path = output_base / "hocr.html"
            with open(hocr_path, 'w', encoding='utf-8') as f:
                f.write(hocr_text)
            
            # Perform layout analysis to identify text regions
            regions = self._analyze_layout_from_hocr(hocr_text, image_path, config)
            
            # Save regions to file
            regions_path = output_base / "regions.json"
            with open(regions_path, 'w', encoding='utf-8') as f:
                json.dump([r.to_dict() for r in regions], f, indent=2)
            
            # Extract articles from regions
            articles = self._segment_articles(regions, config)
            
            # Save articles to file
            articles_path = output_base / "articles.json"
            with open(articles_path, 'w', encoding='utf-8') as f:
                json.dump([a.to_dict() for a in articles], f, indent=2)
            
            # Apply post-processing to OCR text
            if config.apply_error_correction:
                ocr_text = self._post_process_text(ocr_text, config)
            
            return ocr_text, hocr_text, regions, articles
        
        except Exception as e:
            if isinstance(e, (ImageProcessingError, TesseractError, SegmentationError)):
                raise
            
            # Wrap in appropriate exception type
            error_msg = f"Failed to process image: {str(e)}"
            if "image" in str(e).lower():
                raise ImageProcessingError(error_msg)
            elif "tesseract" in str(e).lower():
                raise TesseractError(error_msg)
            else:
                raise OCRError(error_msg)
    
    def _handle_result(self, result: ProcessingResult) -> None:
        """
        Handle the result of OCR processing.
        
        Args:
            result: Processing result
        """
        if not result.success:
            logging.error(f"Processing failed for item {result.item_id}: {result.error_message}")
            return
        
        try:
            # Save OCR results to database
            # Update page record
            self.publication_repo.update_page(
                result.page_id,
                ocr_status="completed",
                ocr_processed_at=datetime.now().isoformat(),
                ocr_engine="tesseract",
                ocr_confidence=result.confidence,
                has_text_content=True
            )
            
            # Save page regions
            for region in result.regions:
                self.publication_repo.add_page_region(
                    page_id=result.page_id,
                    region_type=region.region_type.value,
                    x=region.x,
                    y=region.y,
                    width=region.width,
                    height=region.height,
                    ocr_text=region.text,
                    confidence=region.confidence,
                    image_path=region.image_path
                )
            
            # Get page info for article creation
            page = self.publication_repo.get_page(result.page_id)
            if not page:
                return
            
            # Save articles
            for article in result.articles:
                # Create article
                article_id = self.publication_repo.db_manager.add_article(
                    issue_id=page["issue_id"],
                    title=article.title,
                    full_text=article.content,
                    article_type=article.article_type,
                    start_page=page["page_number"]
                )
                
                # Update regions with article ID
                for region in article.regions:
                    # Find the corresponding page region
                    # We're using the coordinates to match
                    self.db_manager.execute_query("""
                        UPDATE PageRegions
                        SET article_id = ?
                        WHERE page_id = ? AND x = ? AND y = ? AND width = ? AND height = ?
                    """, (
                        article_id,
                        result.page_id,
                        region.x,
                        region.y,
                        region.width,
                        region.height
                    ))
            
            # Update page to show article segmentation is done
            if result.articles:
                self.publication_repo.update_page(
                    result.page_id,
                    has_article_segmentation=True
                )
        
        except Exception as e:
            logging.error(f"Error saving processing results: {str(e)}")
    
    def _preprocess_image(self, image_path: str, config: OCRConfig) -> np.ndarray:
        """
        Preprocess an image for OCR.
        
        Args:
            image_path: Path to the image
            config: OCR configuration
        
        Returns:
            Preprocessed image as NumPy array
        
        Raises:
            ImageProcessingError: If preprocessing fails
        """
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ImageProcessingError(f"Failed to read image: {image_path}")
            
            # Check dimensions and resize if needed
            height, width = image.shape[:2]
            if max(height, width) > config.max_image_dimension:
                # Calculate new dimensions
                if width > height:
                    new_width = config.max_image_dimension
                    new_height = int(height * new_width / width)
                else:
                    new_height = config.max_image_dimension
                    new_width = int(width * new_height / height)
                
                # Resize image
                image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply different preprocessing based on mode
            if config.processing_mode == ProcessingMode.FAST:
                # Fast mode - minimal preprocessing
                return gray
            
            # Apply denoising if configured
            if config.denoise:
                # Non-local means denoising
                gray = cv2.fastNlMeansDenoising(gray, None, h=10, searchWindowSize=21, templateWindowSize=7)
            
            # Convert to PIL for enhancements
            pil_image = Image.fromarray(gray)
            
            # Apply enhancements based on config
            if config.enhance_contrast:
                enhancer = ImageEnhance.Contrast(pil_image)
                pil_image = enhancer.enhance(config.contrast_factor)
            
            if config.enhance_brightness:
                enhancer = ImageEnhance.Brightness(pil_image)
                pil_image = enhancer.enhance(config.brightness_factor)
            
            if config.enhance_sharpness:
                enhancer = ImageEnhance.Sharpness(pil_image)
                pil_image = enhancer.enhance(config.sharpness_factor)
            
            # Convert back to OpenCV format
            enhanced = np.array(pil_image)
            
            # Deskew if configured
            if config.deskew:
                # Calculate skew angle
                enhanced = self._deskew_image(enhanced)
            
            # Apply additional processing for quality modes
            if config.processing_mode in [ProcessingMode.QUALITY, ProcessingMode.ARCHIVAL]:
                # Apply adaptive thresholding for better text extraction
                enhanced = cv2.adaptiveThreshold(
                    enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 11, 2
                )
                
                # Apply morphological operations to clean up the image
                kernel = np.ones((1, 1), np.uint8)
                enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
            
            return enhanced
        
        except Exception as e:
            if isinstance(e, ImageProcessingError):
                raise
            raise ImageProcessingError(f"Image preprocessing failed: {str(e)}")
    
    def _deskew_image(self, image: np.ndarray) -> np.ndarray:
        """
        Deskew an image to straighten text lines.
        
        Args:
            image: Image as NumPy array
        
        Returns:
            Deskewed image as NumPy array
        """
        # Find all non-zero points
        coords = np.column_stack(np.where(image > 0))
        if len(coords) == 0:
            return image
        
        # Get rotated rectangle
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        
        # Determine angle to rotate (the angle is between -90 and 0 in OpenCV)
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Only correct if angle is significant
        if abs(angle) < 0.5:
            return image
        
        # Get rotation matrix
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Apply rotation
        rotated = cv2.warpAffine(
            image, M, (w, h), 
            flags=cv2.INTER_CUBIC, 
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return rotated
    
    def _analyze_layout_from_hocr(self, hocr_text: str, image_path: str, 
                                 config: OCRConfig) -> List[TextRegion]:
        """
        Analyze document layout from HOCR data to identify text regions.
        
        Args:
            hocr_text: HOCR text from Tesseract
            image_path: Path to the original image
            config: OCR configuration
        
        Returns:
            List of identified text regions
        
        Raises:
            SegmentationError: If layout analysis fails
        """
        try:
            # Parse HOCR with BeautifulSoup
            soup = BeautifulSoup(hocr_text, 'html.parser')
            
            # Get image dimensions for percentage calculations
            image = cv2.imread(image_path)
            if image is None:
                raise SegmentationError(f"Failed to load image for layout analysis: {image_path}")
            
            img_height, img_width = image.shape[:2]
            
            # Find all text areas (ocr_carea)
            text_areas = soup.find_all('div', class_='ocr_carea')
            
            # If no text areas found, try to use paragraphs
            if not text_areas:
                text_areas = soup.find_all('p', class_='ocr_par')
            
            # If still no areas found, use lines
            if not text_areas:
                text_areas = soup.find_all('span', class_='ocr_line')
            
            regions = []
            
            # Process each text area
            for area in text_areas:
                # Extract bbox coordinates
                bbox_str = area.get('title', '')
                if not bbox_str.startswith('bbox'):
                    continue
                
                # Parse bounding box
                # Format: bbox x1 y1 x2 y2
                try:
                    bbox_parts = bbox_str.split(' ')
                    x1 = int(bbox_parts[1])
                    y1 = int(bbox_parts[2])
                    x2 = int(bbox_parts[3])
                    y2 = int(bbox_parts[4])
                except (IndexError, ValueError):
                    continue
                
                # Calculate width and height
                width = x2 - x1
                height = y2 - y1
                
                # Skip very small areas (likely noise)
                if width < 10 or height < 10:
                    continue
                
                # Extract text content
                text = area.get_text().strip()
                if not text:
                    continue
                
                # Determine region type
                region_type = self._determine_region_type(
                    text, x1, y1, width, height, img_width, img_height, config
                )
                
                # Extract confidence from HOCR
                confidence = 0.0
                word_nodes = area.find_all('span', class_='ocrx_word')
                if word_nodes:
                    # Calculate average confidence
                    total_conf = 0
                    word_count = 0
                    for word in word_nodes:
                        word_title = word.get('title', '')
                        if 'x_wconf' in word_title:
                            try:
                                conf_str = word_title.split('x_wconf ')[1]
                                conf_value = float(conf_str)
                                total_conf += conf_value
                                word_count += 1
                            except (IndexError, ValueError):
                                continue
                    
                    if word_count > 0:
                        confidence = total_conf / (word_count * 100)  # Normalize to 0-1
                
                # Create region
                region = TextRegion(
                    x=x1,
                    y=y1,
                    width=width,
                    height=height,
                    region_type=region_type,
                    text=text,
                    confidence=confidence
                )
                
                regions.append(region)
            
            # Handle empty results
            if not regions:
                raise SegmentationError(f"No text regions found in image: {image_path}")
            
            # Sort regions by position (top to bottom, left to right)
            regions.sort(key=lambda r: (r.y, r.x))
            
            return regions
        
        except Exception as e:
            if isinstance(e, SegmentationError):
                raise
            raise SegmentationError(f"Layout analysis failed: {str(e)}")
    
    def _determine_region_type(self, text: str, x: int, y: int, width: int, height: int,
                              img_width: int, img_height: int, config: OCRConfig) -> RegionType:
        """
        Determine the type of text region based on content and position.
        
        Args:
            text: Text content of the region
            x, y, width, height: Region coordinates
            img_width, img_height: Image dimensions
            config: OCR configuration
        
        Returns:
            Region type
        """
        # Calculate relative position and size
        rel_y = y / img_height
        rel_height = height / img_height
        rel_width = width / img_width
        
        # Check if it's a masthead (top of page, large font)
        if rel_y < 0.1 and rel_height > config.min_title_height_ratio * 1.5:
            return RegionType.MASTHEAD
        
        # Check if it's a page number (very small, usually at top or bottom)
        if (rel_height < 0.02 and len(text) < 10 and 
            text.strip().isdigit() and rel_width < 0.1):
            return RegionType.PAGE_NUMBER
        
        # Check if it's a date (small, at top, contains date-related words)
        date_words = ["January", "February", "March", "April", "May", "June", "July", 
                      "August", "September", "October", "November", "December",
                      "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if (rel_y < 0.15 and rel_height < 0.03 and 
            any(word in text for word in date_words)):
            return RegionType.DATE
        
        # Check if it's a title (large font, at start of article)
        if rel_height > config.min_title_height_ratio:
            # Check for all caps, which is common for headlines
            if text.isupper() or len(text.split()) < 10:
                return RegionType.TITLE
        
        # Check if it's a subtitle (medium font, follows title)
        if rel_height > config.min_title_height_ratio * 0.7:
            if not text.isupper() and len(text.split()) < 15:
                return RegionType.SUBTITLE
        
        # Check if it's an advertisement
        ad_indicators = ["ADVERTISEMENT", "ADVERTISE", "FOR SALE", "WANTED", "PRICES"]
        if any(indicator in text.upper() for indicator in ad_indicators):
            return RegionType.ADVERTISEMENT
        
        # Check if it's a caption
        if rel_height < 0.03 and rel_width < 0.3:
            return RegionType.CAPTION
        
        # Default to article for most content
        return RegionType.ARTICLE
    
    def _segment_articles(self, regions: List[TextRegion], config: OCRConfig) -> List[Article]:
        """
        Segment text regions into coherent articles.
        
        Args:
            regions: List of text regions
            config: OCR configuration
        
        Returns:
            List of extracted articles
        
        Raises:
            SegmentationError: If article segmentation fails
        """
        try:
            articles = []
            current_article = None
            current_regions = []
            
            # Filter out non-article regions
            filtered_regions = [r for r in regions if r.region_type not in 
                               [RegionType.MASTHEAD, RegionType.PAGE_NUMBER]]
            
            if not filtered_regions:
                return []
            
            # Group regions into articles
            for region in filtered_regions:
                # Start a new article when we encounter a title
                if region.region_type == RegionType.TITLE:
                    # Save current article if there is one
                    if current_article and current_regions:
                        article = self._create_article(current_article, current_regions)
                        articles.append(article)
                    
                    # Start a new article
                    current_article = region
                    current_regions = [region]
                
                # Add to current article
                elif current_article:
                    current_regions.append(region)
                
                # Handle case where the first region is not a title
                elif not current_article:
                    # Start article without a proper title
                    current_article = region
                    current_regions = [region]
            
            # Add the last article
            if current_article and current_regions:
                article = self._create_article(current_article, current_regions)
                articles.append(article)
            
            # Fall back to basic grouping if no articles were created
            if not articles and filtered_regions:
                # Group regions by position, assuming articles are laid out in columns
                self._group_regions_into_articles(filtered_regions, articles, config)
            
            return articles
        
        except Exception as e:
            raise SegmentationError(f"Article segmentation failed: {str(e)}")
    
    def _create_article(self, title_region: TextRegion, regions: List[TextRegion]) -> Article:
        """
        Create an article from a title region and a list of text regions.
        
        Args:
            title_region: Title region
            regions: List of text regions belonging to the article
        
        Returns:
            Created article
        """
        # Extract title and subtitle
        title = title_region.text
        subtitle = None
        
        # Look for subtitle
        subtitle_regions = [r for r in regions if r.region_type == RegionType.SUBTITLE]
        if subtitle_regions:
            subtitle = subtitle_regions[0].text
        
        # Get article content by combining all regions
        article_regions = [r for r in regions if r.region_type == RegionType.ARTICLE]
        content = "\n\n".join(r.text for r in article_regions)
        
        # Calculate average confidence
        confidence = 0.0
        if regions:
            confidence = sum(r.confidence for r in regions) / len(regions)
        
        # Determine article type
        article_type = "news"
        ad_regions = [r for r in regions if r.region_type == RegionType.ADVERTISEMENT]
        if ad_regions:
            article_type = "advertisement"
        
        # Create article
        article = Article(
            title=title,
            subtitle=subtitle,
            content=content,
            regions=regions,
            confidence=confidence,
            article_type=article_type
        )
        
        return article
    
    def _group_regions_into_articles(self, regions: List[TextRegion], 
                                    articles: List[Article], config: OCRConfig) -> None:
        """
        Group regions into articles based on position and layout.
        
        Args:
            regions: List of text regions
            articles: List to append created articles to
            config: OCR configuration
        """
        if not regions:
            return
        
        # Sort regions by column then by y-coordinate
        # Assume columns are spaced horizontally
        column_threshold = min(r.width for r in regions) * 0.8
        
        # Group regions into columns
        columns = []
        current_column = []
        
        # Sort by x-coordinate first to get the regions in column order
        sorted_by_x = sorted(regions, key=lambda r: r.x)
        
        # Initialize with the first region
        current_x = sorted_by_x[0].x
        current_column.append(sorted_by_x[0])
        
        # Group regions into columns
        for region in sorted_by_x[1:]:
            # If this region is in a new column
            if abs(region.x - current_x) > column_threshold:
                # Save current column
                if current_column:
                    columns.append(current_column)
                
                # Start a new column
                current_x = region.x
                current_column = [region]
            else:
                # Add to current column
                current_column.append(region)
        
        # Add the last column
        if current_column:
            columns.append(current_column)
        
        # Sort regions within each column by y-coordinate
        for i, column in enumerate(columns):
            columns[i] = sorted(column, key=lambda r: r.y)
        
        # Create an article for each column
        for column in columns:
            if not column:
                continue
            
            # Find a title or use the first region
            title_regions = [r for r in column if r.region_type == RegionType.TITLE]
            title_region = title_regions[0] if title_regions else column[0]
            
            # Create article
            article = self._create_article(title_region, column)
            articles.append(article)
    
    def _post_process_text(self, text: str, config: OCRConfig) -> str:
        """
        Apply post-processing to OCR text to correct common errors.
        
        Args:
            text: OCR text to process
            config: OCR configuration
        
        Returns:
            Processed text
        """
        # Return original if no processing is needed
        if not config.correct_common_ocr_errors:
            return text
        
        processed_text = text
        
        # Apply common OCR error corrections
        for error, correction in self.ocr_corrections.items():
            processed_text = re.sub(r'\b' + re.escape(error) + r'\b', correction, processed_text)
        
        # Apply publication-specific dictionary if configured
        if config.use_publication_dictionary and config.publication_dictionary_path:
            publication_dict = self._get_publication_dictionary(config.publication_dictionary_path)
            if publication_dict:
                for error, correction in publication_dict.items():
                    processed_text = re.sub(r'\b' + re.escape(error) + r'\b', correction, processed_text)
        
        # Fix broken lines
        processed_text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', processed_text)
        
        # Fix spacing after periods
        processed_text = re.sub(r'\.(\w)', r'. \1', processed_text)
        
        # Fix multiple spaces
        processed_text = re.sub(r' +', ' ', processed_text)
        
        # Fix multiple line breaks
        processed_text = re.sub(r'\n{3,}', '\n\n', processed_text)
        
        return processed_text
    
    def _get_publication_dictionary(self, path: str) -> Dict[str, str]:
        """
        Load a publication-specific dictionary for OCR correction.
        
        Args:
            path: Path to the dictionary file
        
        Returns:
            Dictionary of corrections
        """
        # Check cache first
        if path in self.publication_dictionaries:
            return self.publication_dictionaries[path]
        
        # Load dictionary
        try:
            with open(path, 'r', encoding='utf-8') as f:
                dictionary = json.load(f)
            
            # Cache for future use
            self.publication_dictionaries[path] = dictionary
            return dictionary
        except Exception as e:
            logging.error(f"Failed to load publication dictionary: {str(e)}")
            return {}


class OCRManager:
    """
    Central manager for the OCR processing system.
    
    This class coordinates the OCR processor, processing queue, and database
    integration, providing a unified interface for OCR operations.
    """
    
    def __init__(self, db_manager: DatabaseManager, publication_repo: PublicationRepository,
                 config: Optional[OCRConfig] = None):
        """
        Initialize the OCR manager.
        
        Args:
            db_manager: Database manager
            publication_repo: Publication repository
            config: OCR configuration (uses defaults if None)
        """
        self.db_manager = db_manager
        self.publication_repo = publication_repo
        self.config = config or OCRConfig()
        
        # Create OCR processor
        self.processor = OCRProcessor(db_manager, publication_repo, config)
        
        # Create output directories
        base_path = self.db_manager.config.base_path
        self.temp_dir = os.path.join(base_path, "temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Create queue file path
        self.queue_file = os.path.join(self.temp_dir, "ocr_queue.json")
        
        # Load queue from file if available
        self.processor.queue = self._load_queue()
        
        # Start workers
        self.processor.start_workers(2)  # Default to 2 workers
    
    def _load_queue(self) -> ProcessingQueue:
        """
        Load processing queue from file if available.
        
        Returns:
            Processing queue
        """
        try:
            return ProcessingQueue.load_from_file(self.queue_file)
        except FileNotFoundError:
            return ProcessingQueue()
        except Exception as e:
            logging.error(f"Error loading processing queue: {str(e)}")
            return ProcessingQueue()
    
    def save_queue(self) -> bool:
        """
        Save processing queue to file.
        
        Returns:
            True if successful, False otherwise
        """
        return self.processor.queue.save_to_file(self.queue_file)
    
    def process_page(self, page_id: int, config: Optional[OCRConfig] = None,
                    priority: ProcessingPriority = ProcessingPriority.NORMAL) -> Optional[str]:
        """
        Queue a page for OCR processing.
        
        Args:
            page_id: ID of the page to process
            config: OCR configuration (uses default if None)
            priority: Processing priority
        
        Returns:
            ID of the queued item or None if the page was not found
        """
        # Get page information
        page = self.publication_repo.get_page(page_id)
        if not page:
            return None
        
        # Check if image path is set
        if not page.get("image_path"):
            raise ValueError(f"Page {page_id} has no image path")
        
        # Queue for processing
        return self.processor.queue_page(
            page_id=page_id,
            image_path=page["image_path"],
            config=config,
            issue_id=page.get("issue_id"),
            page_number=page.get("page_number"),
            publication_id=page.get("publication_id"),
            priority=priority
        )
    
    def process_issue(self, issue_id: int, config: Optional[OCRConfig] = None,
                     priority: ProcessingPriority = ProcessingPriority.NORMAL) -> List[str]:
        """
        Queue all pages in an issue for OCR processing.
        
        Args:
            issue_id: ID of the issue to process
            config: OCR configuration (uses default if None)
            priority: Processing priority
        
        Returns:
            List of queued item IDs
        """
        # Get all pages for the issue
        pages = self.publication_repo.search_pages(issue_id=issue_id)
        
        # Queue each page
        item_ids = []
        for page in pages:
            if page.get("image_path"):
                try:
                    item_id = self.process_page(page["page_id"], config, priority)
                    if item_id:
                        item_ids.append(item_id)
                except Exception as e:
                    logging.error(f"Error queuing page {page['page_id']}: {str(e)}")
        
        # Save queue state
        self.save_queue()
        
        return item_ids
    
    def process_publication(self, publication_id: int, start_date: Optional[str] = None,
                          end_date: Optional[str] = None, config: Optional[OCRConfig] = None,
                          priority: ProcessingPriority = ProcessingPriority.NORMAL) -> List[str]:
        """
        Queue all pages in a publication for OCR processing.
        
        Args:
            publication_id: ID of the publication to process
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            config: OCR configuration (uses default if None)
            priority: Processing priority
        
        Returns:
            List of queued item IDs
        """
        # Get all issues for the publication
        issues = self.publication_repo.search_issues(
            publication_id=publication_id,
            start_date=start_date,
            end_date=end_date,
            has_pages=True
        )
        
        # Queue each issue
        item_ids = []
        for issue in issues:
            issue_items = self.process_issue(issue["issue_id"], config, priority)
            item_ids.extend(issue_items)
        
        # Save queue state
        self.save_queue()
        
        return item_ids
    
    def get_processing_status(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a processing item.
        
        Args:
            item_id: ID of the processing item
        
        Returns:
            Dictionary with status information or None if not found
        """
        return self.processor.get_processing_status(item_id)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get the status of the processing queue.
        
        Returns:
            Dictionary with queue statistics and worker status
        """
        return self.processor.get_queue_status()
    
    def cancel_processing(self, item_id: str) -> bool:
        """
        Cancel a queued processing item.
        
        Args:
            item_id: ID of the processing item to cancel
        
        Returns:
            True if the item was canceled, False if not found or not cancellable
        """
        result = self.processor.cancel_processing(item_id)
        self.save_queue()
        return result
    
    def shutdown(self) -> None:
        """Shutdown the OCR manager."""
        # Stop workers
        self.processor.stop_workers()
        
        # Save queue state
        self.save_queue()
        
        logging.info("OCR manager shutdown complete")