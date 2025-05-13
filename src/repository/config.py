"""
Configuration module for the Newspaper Repository system.

This module provides functionality for loading, validating, and managing
configuration settings for the newspaper repository components.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('config')


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


class Configuration:
    """Configuration manager for the newspaper repository system."""
    
    DEFAULT_CONFIG = {
        'database': {
            'path': os.path.join(os.path.dirname(__file__), 'newspaper_repository.db'),
            'pool_size': 5,
            'backup_directory': os.path.join(os.path.dirname(__file__), 'backups'),
            'enable_foreign_keys': True,
            'busy_timeout': 5000
        },
        'repository': {
            'base_path': os.path.join(os.path.dirname(__file__), 'repository'),
            'temp_path': os.path.join(os.path.dirname(__file__), 'temp'),
            'log_path': os.path.join(os.path.dirname(__file__), 'logs'),
            'max_file_size': 100 * 1024 * 1024  # 100 MB
        },
        'downloader': {
            'max_workers': 3,
            'retry_attempts': 3,
            'retry_delay': 5,
            'timeout': 30,
            'user_agent': 'Newspaper Repository Downloader/1.0'
        },
        'downloaders': {
            'chroniclingamerica': {
                'base_url': 'https://chroniclingamerica.loc.gov/api/',
                'rate_limit': 5,
                'batch_size': 10
            }
        },
        'ocr': {
            'max_workers': 2,
            'engine': 'tesseract',
            'tesseract_path': None,  # System default
            'use_gpu': False,
            'languages': ['eng'],
            'dpi': 300,
            'timeout': 300,  # 5 minutes per page
            'segment_articles': True
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration.
        
        Args:
            config_path: Optional path to a configuration file
        """
        self.config = self.DEFAULT_CONFIG.copy()
        
        if config_path:
            self.load_from_file(config_path)
        
        # Ensure critical directories exist
        self._ensure_directories()
    
    def load_from_file(self, config_path: str) -> None:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to the configuration file (json, yaml)
            
        Raises:
            ConfigError: If the file cannot be loaded or is invalid
        """
        try:
            config_path = os.path.abspath(config_path)
            if not os.path.exists(config_path):
                raise ConfigError(f"Configuration file not found: {config_path}")
            
            # Determine file type from extension
            _, ext = os.path.splitext(config_path)
            ext = ext.lower()
            
            if ext == '.json':
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
            elif ext in ('.yaml', '.yml'):
                try:
                    import yaml
                    with open(config_path, 'r', encoding='utf-8') as f:
                        user_config = yaml.safe_load(f)
                except ImportError:
                    raise ConfigError("YAML support requires PyYAML package. Install with 'pip install pyyaml'")
            else:
                raise ConfigError(f"Unsupported configuration file format: {ext}")
            
            # Update configuration with loaded values
            self._deep_update(self.config, user_config)
            logger.info(f"Loaded configuration from {config_path}")
            
        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"Failed to load configuration from {config_path}: {str(e)}")
    
    def _deep_update(self, target: Dict, source: Dict) -> Dict:
        """
        Recursively update a dictionary.
        
        Args:
            target: Target dictionary to update
            source: Source dictionary with new values
            
        Returns:
            Updated dictionary
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
        return target
    
    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        dirs_to_create = [
            self.config['repository']['base_path'],
            self.config['repository']['temp_path'],
            self.config['repository']['log_path'],
            self.config['database']['backup_directory']
        ]
        
        for dir_path in dirs_to_create:
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
                logger.debug(f"Ensured directory exists: {dir_path}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using a dot-notation path.
        
        Args:
            key_path: Dot-notation path to the configuration value (e.g., 'database.path')
            default: Default value to return if the key doesn't exist
            
        Returns:
            The configuration value or the default
        """
        keys = key_path.split('.')
        result = self.config
        
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return default
        
        return result
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set a configuration value using a dot-notation path.
        
        Args:
            key_path: Dot-notation path to the configuration value (e.g., 'database.path')
            value: The value to set
        """
        keys = key_path.split('.')
        target = self.config
        
        # Navigate to the innermost dictionary
        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]
        
        # Set the value
        target[keys[-1]] = value
    
    def save_to_file(self, config_path: str) -> None:
        """
        Save the current configuration to a file.
        
        Args:
            config_path: Path to save the configuration file
            
        Raises:
            ConfigError: If the file cannot be saved
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
            
            # Determine file type from extension
            _, ext = os.path.splitext(config_path)
            ext = ext.lower()
            
            if ext == '.json':
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            elif ext in ('.yaml', '.yml'):
                try:
                    import yaml
                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(self.config, f, default_flow_style=False)
                except ImportError:
                    raise ConfigError("YAML support requires PyYAML package. Install with 'pip install pyyaml'")
            else:
                raise ConfigError(f"Unsupported configuration file format: {ext}")
            
            logger.info(f"Saved configuration to {config_path}")
            
        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"Failed to save configuration to {config_path}: {str(e)}")
    
    def validate(self) -> bool:
        """
        Validate the configuration.
        
        Returns:
            True if the configuration is valid
            
        Raises:
            ConfigError: If the configuration is invalid
        """
        # Check database configuration
        db_path = self.get('database.path')
        if not db_path:
            raise ConfigError("Database path not specified")
        
        # Check repository paths
        base_path = self.get('repository.base_path')
        if not base_path:
            raise ConfigError("Repository base path not specified")
        
        # Check OCR configuration
        ocr_engine = self.get('ocr.engine')
        if ocr_engine == 'tesseract':
            # Check if tesseract is available
            import shutil
            tesseract_path = self.get('ocr.tesseract_path')
            if tesseract_path and not os.path.exists(tesseract_path):
                raise ConfigError(f"Specified tesseract path does not exist: {tesseract_path}")
            elif not tesseract_path and not shutil.which('tesseract'):
                raise ConfigError("Tesseract not found in PATH. Please install Tesseract or specify the path.")
        
        return True
    
    def as_dict(self) -> Dict:
        """
        Get the full configuration as a dictionary.
        
        Returns:
            Dictionary with all configuration values
        """
        return self.config.copy()


# Global configuration instance
_config_instance = None

def get_config(config_path: Optional[str] = None) -> Configuration:
    """
    Get the global configuration instance.
    
    Args:
        config_path: Optional path to a configuration file
        
    Returns:
        Configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Configuration(config_path)
    return _config_instance