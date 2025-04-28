# File: config_service.py

import json
import os
from typing import Any, Dict, Optional

class ConfigService:
    """
    Service for handling application configuration settings.
    Provides methods for loading and saving configuration.
    """
    
    DEFAULT_CONFIG = {
        "database": {
            "path": "nova_database.db"
        },
        "ui": {
            "font_size": 10,
            "theme": "default",
            "window_size": [1024, 768]
        },
        "ocr": {
            "enhanced_mode": True,
            "tesseract_path": "",
            "ai_assist": False
        },
        "paths": {
            "default_import_dir": "",
            "default_export_dir": ""
        }
    }
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the config service.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or create default if not exists.
        
        Returns:
            Dictionary containing configuration settings
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                # Merge with default config to ensure all fields exist
                return self._merge_config(self.DEFAULT_CONFIG, config)
            except (json.JSONDecodeError, IOError):
                # If file is invalid, use default config
                return dict(self.DEFAULT_CONFIG)
        else:
            # Create default config file
            self.save_config(self.DEFAULT_CONFIG)
            return dict(self.DEFAULT_CONFIG)
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Dictionary containing configuration settings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            self.config = config
            return True
        except IOError:
            return False
    
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration setting.
        
        Args:
            section: Configuration section
            key: Setting key
            default: Default value if setting not found
            
        Returns:
            Setting value or default
        """
        if section in self.config and key in self.config[section]:
            return self.config[section][key]
        return default
    
    def set_setting(self, section: str, key: str, value: Any) -> bool:
        """
        Set a specific configuration setting.
        
        Args:
            section: Configuration section
            key: Setting key
            value: Setting value
            
        Returns:
            True if successful, False otherwise
        """
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][key] = value
        return self.save_config(self.config)
    
    def _merge_config(self, default_config: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge user config with default config to ensure all necessary keys exist.
        
        Args:
            default_config: Default configuration dictionary
            user_config: User configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        result = dict(default_config)
        
        for section, section_data in user_config.items():
            if section in result and isinstance(section_data, dict):
                # Merge section data
                for key, value in section_data.items():
                    result[section][key] = value
            else:
                # Add new section
                result[section] = section_data
        
        return result