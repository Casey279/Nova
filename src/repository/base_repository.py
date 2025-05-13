#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base repository classes for the Nova newspaper repository system.

This module defines abstract interfaces and common functionality for all repository types
in the Nova system. It provides base classes that handle file system operations,
standardized error handling, and utility methods for path management and validation.
"""

import os
import logging
import time
import json
import shutil
import hashlib
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
import traceback


class RepositoryError(Exception):
    """Base exception class for all repository-related errors."""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class FileNotFoundError(RepositoryError):
    """Exception raised when a requested file is not found in the repository."""
    def __init__(self, file_path: str, details: Dict = None):
        message = f"File not found: {file_path}"
        super().__init__(message, "FILE_NOT_FOUND", details)


class InvalidPathError(RepositoryError):
    """Exception raised when a provided path is invalid or malformed."""
    def __init__(self, path: str, details: Dict = None):
        message = f"Invalid path: {path}"
        super().__init__(message, "INVALID_PATH", details)


class StorageError(RepositoryError):
    """Exception raised when storage operations fail."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "STORAGE_ERROR", details)


class DatabaseError(RepositoryError):
    """Exception raised for database-related errors."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "DATABASE_ERROR", details)


class PermissionError(RepositoryError):
    """Exception raised when there are insufficient permissions for an operation."""
    def __init__(self, path: str, operation: str, details: Dict = None):
        message = f"Permission denied: {operation} on {path}"
        super().__init__(message, "PERMISSION_ERROR", details)


class TransactionError(RepositoryError):
    """Exception raised when a transaction fails."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "TRANSACTION_ERROR", details)


class ConfigurationError(RepositoryError):
    """Exception raised when there is an issue with repository configuration."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "CONFIG_ERROR", details)


class RepositoryLogLevel(Enum):
    """Log levels for repository operations."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class RepositoryStatus(Enum):
    """Status values for repository operations."""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    IDLE = "idle"


class RepositoryMetrics:
    """Class for tracking performance metrics of repository operations."""
    
    def __init__(self):
        self.start_time = time.time()
        self.operation_times = {}
        self.operation_counts = {}
        self.errors = {}
        self.storage_usage = {
            "total_bytes": 0,
            "files_count": 0
        }
    
    def start_operation(self, operation_name: str) -> float:
        """Start timing an operation and return the start time."""
        start_time = time.time()
        if operation_name not in self.operation_counts:
            self.operation_counts[operation_name] = 0
            self.operation_times[operation_name] = 0
        return start_time
    
    def end_operation(self, operation_name: str, start_time: float) -> float:
        """End timing an operation and update metrics."""
        duration = time.time() - start_time
        self.operation_counts[operation_name] = self.operation_counts.get(operation_name, 0) + 1
        self.operation_times[operation_name] = self.operation_times.get(operation_name, 0) + duration
        return duration
    
    def record_error(self, operation_name: str, error_type: str) -> None:
        """Record an error for a given operation."""
        if operation_name not in self.errors:
            self.errors[operation_name] = {}
        self.errors[operation_name][error_type] = self.errors.get(operation_name, {}).get(error_type, 0) + 1
    
    def update_storage_usage(self, bytes_added: int = 0, files_added: int = 0) -> None:
        """Update storage usage metrics."""
        self.storage_usage["total_bytes"] += bytes_added
        self.storage_usage["files_count"] += files_added
    
    def get_metrics_report(self) -> Dict[str, Any]:
        """Get a report of all metrics."""
        total_time = time.time() - self.start_time
        return {
            "uptime_seconds": total_time,
            "operations": {
                name: {
                    "count": count,
                    "total_time": self.operation_times[name],
                    "avg_time": self.operation_times[name] / count if count > 0 else 0
                }
                for name, count in self.operation_counts.items()
            },
            "errors": self.errors,
            "storage_usage": self.storage_usage
        }
    
    def reset(self) -> None:
        """Reset all metrics except uptime."""
        self.operation_times = {}
        self.operation_counts = {}
        self.errors = {}
        self.storage_usage = {
            "total_bytes": 0,
            "files_count": 0
        }


class RepositoryConfig:
    """Configuration class for repository settings."""
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        # Default configuration values
        self.base_path = os.path.abspath("./repository")
        self.database_path = os.path.join(self.base_path, "repository.db")
        self.log_level = RepositoryLogLevel.INFO
        self.log_file = os.path.join(self.base_path, "repository.log")
        self.max_file_size = 1024 * 1024 * 100  # 100 MB
        self.supported_image_formats = ["jp2", "jpg", "png", "tif", "tiff"]
        self.temp_dir = os.path.join(self.base_path, "temp")
        self.backup_dir = os.path.join(self.base_path, "backups")
        self.use_transactions = True
        self.enable_metrics = True
        self.file_chunk_size = 1024 * 1024  # 1 MB chunks for file operations
        self.enable_file_validation = True
        self.max_retry_attempts = 3
        self.retry_delay_seconds = 2
        
        # Override defaults with provided configuration
        if config_dict:
            self.update_from_dict(config_dict)
    
    def update_from_dict(self, config_dict: Dict[str, Any]) -> None:
        """Update configuration from a dictionary."""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logging.warning(f"Unknown configuration parameter: {key}")
    
    def update_from_file(self, file_path: str) -> None:
        """Load configuration from a JSON file."""
        try:
            with open(file_path, 'r') as f:
                config_dict = json.load(f)
                self.update_from_dict(config_dict)
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration from {file_path}: {str(e)}")
    
    def save_to_file(self, file_path: str) -> None:
        """Save configuration to a JSON file."""
        # Convert enum values to strings for serialization
        config_dict = {
            key: value.name if isinstance(value, Enum) else value
            for key, value in self.__dict__.items()
        }
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(config_dict, f, indent=4)
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration to {file_path}: {str(e)}")
    
    def validate(self) -> List[str]:
        """Validate the configuration settings and return a list of warnings."""
        warnings = []
        
        # Check if directories exist or can be created
        for path_attr in ['base_path', 'temp_dir', 'backup_dir']:
            path = getattr(self, path_attr)
            if not os.path.exists(path):
                try:
                    os.makedirs(path, exist_ok=True)
                except Exception:
                    warnings.append(f"Could not create {path_attr} directory: {path}")
        
        # Check if database directory is writable
        db_dir = os.path.dirname(self.database_path)
        if not os.access(db_dir, os.W_OK):
            warnings.append(f"Database directory is not writable: {db_dir}")
        
        # Check log file path
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                warnings.append(f"Could not create log directory: {log_dir}")
        
        return warnings


class PathManager:
    """Utility class for path management and validation."""
    
    def __init__(self, base_path: str):
        self.base_path = os.path.abspath(base_path)
    
    def validate_path(self, path: str) -> bool:
        """Validate that a path is safe and within the base path."""
        if not path:
            return False
        
        # Convert to absolute path
        abs_path = os.path.abspath(path)
        
        # Check if path is within base_path
        return abs_path.startswith(self.base_path)
    
    def ensure_path(self, path: str) -> str:
        """Ensure a path exists and is valid, creating directories as needed."""
        if not self.validate_path(path):
            raise InvalidPathError(path)
        
        directory = path if os.path.isdir(path) else os.path.dirname(path)
        
        try:
            os.makedirs(directory, exist_ok=True)
            return path
        except Exception as e:
            raise StorageError(f"Failed to create directory: {directory}", {"error": str(e)})
    
    def get_relative_path(self, full_path: str) -> str:
        """Get path relative to base path."""
        if not self.validate_path(full_path):
            raise InvalidPathError(full_path)
        
        return os.path.relpath(full_path, self.base_path)
    
    def get_full_path(self, relative_path: str) -> str:
        """Convert relative path to full path."""
        full_path = os.path.join(self.base_path, relative_path)
        
        if not self.validate_path(full_path):
            raise InvalidPathError(full_path)
        
        return full_path
    
    def generate_path_hash(self, identifier: str, extension: str = None) -> str:
        """Generate a path with hash-based sharding to avoid too many files in one directory."""
        # Create a hash of the identifier
        id_hash = hashlib.md5(identifier.encode()).hexdigest()
        
        # Use first few characters for sharding
        shard1, shard2 = id_hash[:2], id_hash[2:4]
        sharded_path = os.path.join(self.base_path, shard1, shard2, id_hash)
        
        # Add extension if provided
        if extension:
            if not extension.startswith('.'):
                extension = f".{extension}"
            sharded_path += extension
        
        return sharded_path
    
    def file_exists(self, path: str) -> bool:
        """Check if a file exists and is within the base path."""
        if not self.validate_path(path):
            raise InvalidPathError(path)
        
        return os.path.isfile(path)


class FileManager:
    """Handles file storage and retrieval with error handling and validation."""
    
    def __init__(self, path_manager: PathManager, config: RepositoryConfig):
        self.path_manager = path_manager
        self.config = config
        self.metrics = RepositoryMetrics() if config.enable_metrics else None
    
    def save_file(self, source_path: str, destination_path: str, validate: bool = None) -> str:
        """
        Save a file to the repository.
        
        Args:
            source_path: Path to the source file
            destination_path: Destination path in the repository
            validate: Whether to validate the file (uses config default if None)
        
        Returns:
            The path to the saved file
        """
        validate = self.config.enable_file_validation if validate is None else validate
        start_time = self.metrics.start_operation("save_file") if self.metrics else 0
        
        try:
            # Validate paths
            if not os.path.isfile(source_path):
                raise FileNotFoundError(source_path)
            
            if not self.path_manager.validate_path(destination_path):
                raise InvalidPathError(destination_path)
            
            # Ensure directory exists
            dest_dir = os.path.dirname(destination_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, destination_path)
            
            # Validate if requested
            if validate:
                self._validate_file_copy(source_path, destination_path)
            
            # Update metrics
            if self.metrics:
                file_size = os.path.getsize(destination_path)
                self.metrics.update_storage_usage(bytes_added=file_size, files_added=1)
                self.metrics.end_operation("save_file", start_time)
            
            return destination_path
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("save_file", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to save file: {str(e)}",
                    {"source": source_path, "destination": destination_path}
                ) from e
    
    def save_bytes(self, data: bytes, destination_path: str) -> str:
        """
        Save binary data to a file.
        
        Args:
            data: Binary data to save
            destination_path: Destination path in the repository
        
        Returns:
            The path to the saved file
        """
        start_time = self.metrics.start_operation("save_bytes") if self.metrics else 0
        
        try:
            # Validate path
            if not self.path_manager.validate_path(destination_path):
                raise InvalidPathError(destination_path)
            
            # Ensure directory exists
            dest_dir = os.path.dirname(destination_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Write data
            with open(destination_path, 'wb') as f:
                f.write(data)
            
            # Update metrics
            if self.metrics:
                self.metrics.update_storage_usage(bytes_added=len(data), files_added=1)
                self.metrics.end_operation("save_bytes", start_time)
            
            return destination_path
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("save_bytes", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to save bytes: {str(e)}",
                    {"destination": destination_path}
                ) from e
    
    def save_text(self, text: str, destination_path: str, encoding: str = 'utf-8') -> str:
        """
        Save text to a file.
        
        Args:
            text: Text to save
            destination_path: Destination path in the repository
            encoding: Text encoding (default: utf-8)
        
        Returns:
            The path to the saved file
        """
        start_time = self.metrics.start_operation("save_text") if self.metrics else 0
        
        try:
            # Validate path
            if not self.path_manager.validate_path(destination_path):
                raise InvalidPathError(destination_path)
            
            # Ensure directory exists
            dest_dir = os.path.dirname(destination_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Write text
            with open(destination_path, 'w', encoding=encoding) as f:
                f.write(text)
            
            # Update metrics
            if self.metrics:
                file_size = os.path.getsize(destination_path)
                self.metrics.update_storage_usage(bytes_added=file_size, files_added=1)
                self.metrics.end_operation("save_text", start_time)
            
            return destination_path
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("save_text", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to save text: {str(e)}",
                    {"destination": destination_path}
                ) from e
    
    def read_file(self, file_path: str, binary: bool = False) -> Union[str, bytes]:
        """
        Read a file from the repository.
        
        Args:
            file_path: Path to the file
            binary: Whether to read in binary mode
        
        Returns:
            File contents as string or bytes
        """
        start_time = self.metrics.start_operation("read_file") if self.metrics else 0
        
        try:
            # Validate path
            if not self.path_manager.validate_path(file_path):
                raise InvalidPathError(file_path)
            
            # Check if file exists
            if not os.path.isfile(file_path):
                raise FileNotFoundError(file_path)
            
            # Read file
            mode = 'rb' if binary else 'r'
            encoding = None if binary else 'utf-8'
            
            with open(file_path, mode, encoding=encoding) as f:
                content = f.read()
            
            if self.metrics:
                self.metrics.end_operation("read_file", start_time)
            
            return content
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("read_file", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to read file: {str(e)}",
                    {"file_path": file_path}
                ) from e
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from the repository.
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if file was deleted, False if it didn't exist
        """
        start_time = self.metrics.start_operation("delete_file") if self.metrics else 0
        
        try:
            # Validate path
            if not self.path_manager.validate_path(file_path):
                raise InvalidPathError(file_path)
            
            # Check if file exists
            if not os.path.isfile(file_path):
                if self.metrics:
                    self.metrics.end_operation("delete_file", start_time)
                return False
            
            # Get file size for metrics
            file_size = os.path.getsize(file_path) if self.metrics else 0
            
            # Delete file
            os.remove(file_path)
            
            # Update metrics
            if self.metrics:
                self.metrics.update_storage_usage(bytes_added=-file_size, files_added=-1)
                self.metrics.end_operation("delete_file", start_time)
            
            return True
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("delete_file", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to delete file: {str(e)}",
                    {"file_path": file_path}
                ) from e
    
    def copy_file(self, source_path: str, destination_path: str) -> str:
        """
        Copy a file within the repository.
        
        Args:
            source_path: Source path in the repository
            destination_path: Destination path in the repository
        
        Returns:
            The destination path
        """
        start_time = self.metrics.start_operation("copy_file") if self.metrics else 0
        
        try:
            # Validate paths
            if not self.path_manager.validate_path(source_path):
                raise InvalidPathError(source_path)
            
            if not self.path_manager.validate_path(destination_path):
                raise InvalidPathError(destination_path)
            
            # Check if source file exists
            if not os.path.isfile(source_path):
                raise FileNotFoundError(source_path)
            
            # Ensure destination directory exists
            dest_dir = os.path.dirname(destination_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, destination_path)
            
            # Update metrics
            if self.metrics:
                file_size = os.path.getsize(destination_path)
                self.metrics.update_storage_usage(bytes_added=file_size, files_added=1)
                self.metrics.end_operation("copy_file", start_time)
            
            return destination_path
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("copy_file", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to copy file: {str(e)}",
                    {"source": source_path, "destination": destination_path}
                ) from e
    
    def move_file(self, source_path: str, destination_path: str) -> str:
        """
        Move a file within the repository.
        
        Args:
            source_path: Source path in the repository
            destination_path: Destination path in the repository
        
        Returns:
            The destination path
        """
        start_time = self.metrics.start_operation("move_file") if self.metrics else 0
        
        try:
            # Validate paths
            if not self.path_manager.validate_path(source_path):
                raise InvalidPathError(source_path)
            
            if not self.path_manager.validate_path(destination_path):
                raise InvalidPathError(destination_path)
            
            # Check if source file exists
            if not os.path.isfile(source_path):
                raise FileNotFoundError(source_path)
            
            # Ensure destination directory exists
            dest_dir = os.path.dirname(destination_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Move file
            shutil.move(source_path, destination_path)
            
            if self.metrics:
                self.metrics.end_operation("move_file", start_time)
            
            return destination_path
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("move_file", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to move file: {str(e)}",
                    {"source": source_path, "destination": destination_path}
                ) from e
    
    def list_files(self, directory_path: str, pattern: str = None) -> List[str]:
        """
        List files in a directory within the repository.
        
        Args:
            directory_path: Directory path in the repository
            pattern: Optional glob pattern to filter files
        
        Returns:
            List of file paths
        """
        start_time = self.metrics.start_operation("list_files") if self.metrics else 0
        
        try:
            # Validate path
            if not self.path_manager.validate_path(directory_path):
                raise InvalidPathError(directory_path)
            
            # Check if directory exists
            if not os.path.isdir(directory_path):
                if self.metrics:
                    self.metrics.end_operation("list_files", start_time)
                return []
            
            # List files
            if pattern:
                import glob
                files = glob.glob(os.path.join(directory_path, pattern))
            else:
                files = [
                    os.path.join(directory_path, f)
                    for f in os.listdir(directory_path)
                    if os.path.isfile(os.path.join(directory_path, f))
                ]
            
            if self.metrics:
                self.metrics.end_operation("list_files", start_time)
            
            return files
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("list_files", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to list files: {str(e)}",
                    {"directory_path": directory_path, "pattern": pattern}
                ) from e
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get information about a file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            Dictionary with file information
        """
        start_time = self.metrics.start_operation("get_file_info") if self.metrics else 0
        
        try:
            # Validate path
            if not self.path_manager.validate_path(file_path):
                raise InvalidPathError(file_path)
            
            # Check if file exists
            if not os.path.isfile(file_path):
                raise FileNotFoundError(file_path)
            
            # Get file information
            stat_info = os.stat(file_path)
            file_info = {
                "path": file_path,
                "size": stat_info.st_size,
                "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
                "extension": os.path.splitext(file_path)[1].lower()[1:],
                "filename": os.path.basename(file_path)
            }
            
            if self.metrics:
                self.metrics.end_operation("get_file_info", start_time)
            
            return file_info
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("get_file_info", type(e).__name__)
            
            if isinstance(e, RepositoryError):
                raise
            else:
                raise StorageError(
                    f"Failed to get file info: {str(e)}",
                    {"file_path": file_path}
                ) from e
    
    def _validate_file_copy(self, source_path: str, destination_path: str) -> bool:
        """
        Validate that a file was copied correctly by comparing file sizes and checksums.
        
        Args:
            source_path: Path to the source file
            destination_path: Path to the destination file
        
        Returns:
            True if validation passes
        
        Raises:
            StorageError: If validation fails
        """
        # Check if files exist
        if not os.path.isfile(source_path):
            raise FileNotFoundError(source_path)
        
        if not os.path.isfile(destination_path):
            raise FileNotFoundError(destination_path)
        
        # Compare file sizes
        source_size = os.path.getsize(source_path)
        dest_size = os.path.getsize(destination_path)
        
        if source_size != dest_size:
            raise StorageError(
                "File size mismatch during validation",
                {"source_size": source_size, "dest_size": dest_size}
            )
        
        # For small files, compare checksums
        if source_size < 100 * 1024 * 1024:  # Less than 100 MB
            source_hash = self._calculate_file_hash(source_path)
            dest_hash = self._calculate_file_hash(destination_path)
            
            if source_hash != dest_hash:
                raise StorageError(
                    "File checksum mismatch during validation",
                    {"source_hash": source_hash, "dest_hash": dest_hash}
                )
        
        return True
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(self.config.file_chunk_size), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()


class BaseRepository(ABC):
    """Abstract base class for all repository implementations."""
    
    def __init__(self, config: RepositoryConfig):
        """
        Initialize the repository with the given configuration.
        
        Args:
            config: Repository configuration
        """
        self.config = config
        
        # Configure logging
        log_dir = os.path.dirname(config.log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            filename=config.log_file,
            level=config.log_level.value,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize path and file managers
        self.path_manager = PathManager(config.base_path)
        self.file_manager = FileManager(self.path_manager, config)
        
        # Initialize metrics
        self.metrics = RepositoryMetrics() if config.enable_metrics else None
        
        # Status tracking
        self._status = RepositoryStatus.INITIALIZING
        self._last_error = None
        
        self.logger.info(f"Repository initialized at {config.base_path}")
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get the current repository status."""
        status_info = {
            "status": self._status.value,
            "base_path": self.config.base_path,
            "last_error": self._last_error,
            "initialized_at": self.metrics.start_time if self.metrics else None
        }
        
        if self.metrics:
            status_info["metrics"] = self.metrics.get_metrics_report()
        
        return status_info
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the repository.
        
        Returns:
            True if initialization was successful
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the repository, releasing any resources."""
        pass
    
    def _set_status(self, status: RepositoryStatus, error: Exception = None) -> None:
        """Update repository status."""
        self._status = status
        
        if error:
            self._last_error = {
                "error_type": type(error).__name__,
                "message": str(error),
                "timestamp": datetime.now().isoformat(),
                "traceback": traceback.format_exc()
            }
            
            self.logger.error(f"Repository error: {str(error)}")
            
            if self.metrics:
                self.metrics.record_error("repository", type(error).__name__)
        else:
            self._last_error = None
    
    def with_transaction(self, func, *args, **kwargs):
        """
        Execute a function within a transaction context if supported.
        
        This is a helper method that child classes should override if they support transactions.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
        
        Returns:
            The result of the function
        """
        if not self.config.use_transactions:
            return func(*args, **kwargs)
        
        # Default implementation (no transaction support)
        self.logger.warning("Transactions not supported by this repository")
        return func(*args, **kwargs)
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get information about repository storage usage.
        
        Returns:
            Dictionary with storage information
        """
        base_path = self.config.base_path
        try:
            total_size = 0
            file_count = 0
            
            for dirpath, _, filenames in os.walk(base_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1
            
            # Get disk usage information
            if hasattr(shutil, 'disk_usage'):  # Python 3.3+
                disk_info = shutil.disk_usage(base_path)
                free_space = disk_info.free
                total_space = disk_info.total
            else:
                free_space = None
                total_space = None
            
            return {
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": file_count,
                "free_space_bytes": free_space,
                "free_space_mb": free_space / (1024 * 1024) if free_space else None,
                "total_space_bytes": total_space,
                "total_space_mb": total_space / (1024 * 1024) if total_space else None,
                "base_path": base_path
            }
        
        except Exception as e:
            self.logger.error(f"Error getting storage info: {str(e)}")
            return {
                "error": str(e),
                "base_path": base_path
            }
    
    def backup(self, backup_name: str = None) -> str:
        """
        Create a backup of the repository.
        
        Args:
            backup_name: Optional name for the backup (defaults to timestamp)
        
        Returns:
            Path to the backup file
        """
        start_time = self.metrics.start_operation("backup") if self.metrics else 0
        
        try:
            # Default backup name to timestamp if not provided
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"repository_backup_{timestamp}"
            
            # Add .zip extension if not present
            if not backup_name.endswith(".zip"):
                backup_name += ".zip"
            
            # Create backup directory if it doesn't exist
            backup_dir = self.config.backup_dir
            os.makedirs(backup_dir, exist_ok=True)
            
            # Full path to backup file
            backup_path = os.path.join(backup_dir, backup_name)
            
            # Create temp directory for database backup
            temp_dir = os.path.join(self.config.temp_dir, f"backup_{int(time.time())}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Hook for repository implementation to backup database
            db_backup_path = self._backup_database(temp_dir)
            
            # Create zip archive
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add database backup if created
                if db_backup_path and os.path.exists(db_backup_path):
                    zipf.write(
                        db_backup_path,
                        os.path.basename(db_backup_path)
                    )
                
                # Add configuration
                config_path = os.path.join(temp_dir, "repository_config.json")
                self.config.save_to_file(config_path)
                zipf.write(config_path, os.path.basename(config_path))
                
                # Optionally add additional files (implement in subclasses)
                self._add_files_to_backup(zipf, temp_dir)
            
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            self.logger.info(f"Repository backup created at {backup_path}")
            
            if self.metrics:
                self.metrics.end_operation("backup", start_time)
            
            return backup_path
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("backup", type(e).__name__)
            
            self.logger.error(f"Backup failed: {str(e)}")
            self._set_status(RepositoryStatus.ERROR, e)
            
            raise StorageError(f"Failed to create backup: {str(e)}") from e
    
    def _backup_database(self, temp_dir: str) -> Optional[str]:
        """
        Create a backup of the repository database.
        
        Args:
            temp_dir: Temporary directory to store the backup
        
        Returns:
            Path to the database backup file, or None if not applicable
        """
        # Default implementation does nothing
        # Subclasses should override this method if they use a database
        return None
    
    def _add_files_to_backup(self, zipf: 'zipfile.ZipFile', temp_dir: str) -> None:
        """
        Add additional files to the backup archive.
        
        Args:
            zipf: ZipFile object to add files to
            temp_dir: Temporary directory to prepare files
        """
        # Default implementation does nothing
        # Subclasses should override this method to add repository-specific files
        pass
    
    def restore(self, backup_path: str) -> bool:
        """
        Restore the repository from a backup.
        
        Args:
            backup_path: Path to the backup file
        
        Returns:
            True if restore was successful
        """
        start_time = self.metrics.start_operation("restore") if self.metrics else 0
        
        try:
            # Validate backup file
            if not os.path.isfile(backup_path):
                raise FileNotFoundError(backup_path)
            
            if not zipfile.is_zipfile(backup_path):
                raise StorageError(f"Invalid backup file: {backup_path}")
            
            # Create temp directory for extraction
            temp_dir = os.path.join(self.config.temp_dir, f"restore_{int(time.time())}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Extract backup
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(temp_dir)
            
            # Look for configuration file
            config_path = os.path.join(temp_dir, "repository_config.json")
            if os.path.isfile(config_path):
                # Load configuration but don't override base_path
                old_base_path = self.config.base_path
                self.config.update_from_file(config_path)
                self.config.base_path = old_base_path
            
            # Hook for repository implementation to restore database
            db_restored = self._restore_database(temp_dir)
            
            # Hook for repository implementation to restore additional files
            files_restored = self._restore_files(temp_dir)
            
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            self.logger.info(f"Repository restored from {backup_path}")
            
            if self.metrics:
                self.metrics.end_operation("restore", start_time)
            
            return db_restored and files_restored
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("restore", type(e).__name__)
            
            self.logger.error(f"Restore failed: {str(e)}")
            self._set_status(RepositoryStatus.ERROR, e)
            
            raise StorageError(f"Failed to restore from backup: {str(e)}") from e
    
    def _restore_database(self, temp_dir: str) -> bool:
        """
        Restore the repository database from a backup.
        
        Args:
            temp_dir: Temporary directory with extracted backup files
        
        Returns:
            True if database restore was successful
        """
        # Default implementation does nothing
        # Subclasses should override this method if they use a database
        return True
    
    def _restore_files(self, temp_dir: str) -> bool:
        """
        Restore additional files from a backup.
        
        Args:
            temp_dir: Temporary directory with extracted backup files
        
        Returns:
            True if file restore was successful
        """
        # Default implementation does nothing
        # Subclasses should override this method to restore repository-specific files
        return True
    
    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the repository.
        
        Returns:
            Dictionary with verification results
        """
        start_time = self.metrics.start_operation("verify_integrity") if self.metrics else 0
        
        try:
            results = {
                "success": True,
                "errors": [],
                "warnings": [],
                "checks": {}
            }
            
            # Check if repository directory exists
            if not os.path.isdir(self.config.base_path):
                results["errors"].append(f"Repository directory not found: {self.config.base_path}")
                results["success"] = False
            
            # Check if database file exists
            db_path = self.config.database_path
            if not os.path.isfile(db_path):
                results["errors"].append(f"Database file not found: {db_path}")
                results["success"] = False
            
            # Check if required directories exist
            required_dirs = [
                self.config.temp_dir,
                self.config.backup_dir
            ]
            
            for dir_path in required_dirs:
                if not os.path.isdir(dir_path):
                    # Try to create the directory
                    try:
                        os.makedirs(dir_path, exist_ok=True)
                        results["warnings"].append(f"Created missing directory: {dir_path}")
                    except Exception as e:
                        results["errors"].append(f"Failed to create directory {dir_path}: {str(e)}")
                        results["success"] = False
            
            # Check if database is readable and valid
            db_check = self._verify_database_integrity()
            results["checks"]["database"] = db_check
            
            if not db_check.get("success", False):
                results["errors"].extend(db_check.get("errors", []))
                results["success"] = False
            
            # Check if file system is accessible
            fs_check = self._verify_filesystem_integrity()
            results["checks"]["filesystem"] = fs_check
            
            if not fs_check.get("success", False):
                results["errors"].extend(fs_check.get("errors", []))
                results["success"] = False
            
            if self.metrics:
                self.metrics.end_operation("verify_integrity", start_time)
            
            return results
        
        except Exception as e:
            if self.metrics:
                self.metrics.record_error("verify_integrity", type(e).__name__)
            
            self.logger.error(f"Integrity verification failed: {str(e)}")
            self._set_status(RepositoryStatus.ERROR, e)
            
            return {
                "success": False,
                "errors": [f"Verification failed: {str(e)}"],
                "warnings": [],
                "checks": {}
            }
    
    def _verify_database_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the repository database.
        
        Returns:
            Dictionary with verification results
        """
        # Default implementation does a basic check
        # Subclasses should override this method for more thorough database checks
        db_path = self.config.database_path
        
        results = {
            "success": True,
            "errors": [],
            "warnings": []
        }
        
        # Check if database file exists
        if not os.path.isfile(db_path):
            results["errors"].append(f"Database file not found: {db_path}")
            results["success"] = False
            return results
        
        # Check if database file is readable
        try:
            with open(db_path, 'rb') as f:
                # Read first few bytes
                f.read(10)
        except Exception as e:
            results["errors"].append(f"Database file not readable: {str(e)}")
            results["success"] = False
        
        return results
    
    def _verify_filesystem_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the repository file system.
        
        Returns:
            Dictionary with verification results
        """
        results = {
            "success": True,
            "errors": [],
            "warnings": []
        }
        
        # Check if repository directory exists and is readable/writable
        base_path = self.config.base_path
        
        if not os.path.isdir(base_path):
            results["errors"].append(f"Repository directory not found: {base_path}")
            results["success"] = False
            return results
        
        # Check read permission
        if not os.access(base_path, os.R_OK):
            results["errors"].append(f"Repository directory not readable: {base_path}")
            results["success"] = False
        
        # Check write permission
        if not os.access(base_path, os.W_OK):
            results["errors"].append(f"Repository directory not writable: {base_path}")
            results["success"] = False
        
        # Check for free space
        try:
            if hasattr(shutil, 'disk_usage'):  # Python 3.3+
                disk_info = shutil.disk_usage(base_path)
                free_space_mb = disk_info.free / (1024 * 1024)
                
                if free_space_mb < 100:  # Less than 100 MB
                    results["warnings"].append(f"Low disk space: {free_space_mb:.1f} MB free")
                    
                    if free_space_mb < 10:  # Less than 10 MB
                        results["errors"].append(f"Critical low disk space: {free_space_mb:.1f} MB free")
                        results["success"] = False
        except Exception as e:
            results["warnings"].append(f"Could not check disk space: {str(e)}")
        
        return results