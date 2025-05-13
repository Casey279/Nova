#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for repository configuration component
"""

import os
import sys

# Add the parent directory to the path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PyQt5.QtWidgets import QApplication
    from ui.repository_config import RepositoryConfig
    
    def main():
        """Main entry point for testing the config dialog"""
        app = QApplication(sys.argv)
        config_dialog = RepositoryConfig()
        config_dialog.show()
        sys.exit(app.exec_())
    
    if __name__ == "__main__":
        main()
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure PyQt5 is installed and you're running from the correct environment.")