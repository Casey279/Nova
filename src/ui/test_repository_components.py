#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for repository UI components

This script allows you to test the repository import and configuration
components individually or together.
"""

import os
import sys
import argparse
from PyQt5.QtWidgets import QApplication

# Add the parent directory to the path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import components
from ui.repository_import import RepositoryImport
from ui.repository_config import RepositoryConfig
from ui.repository_browser import RepositoryBrowser


def main():
    """Main entry point for the test script"""
    parser = argparse.ArgumentParser(description='Test repository UI components')
    parser.add_argument('--component', choices=['import', 'config', 'browser', 'all'], 
                      default='all', help='Component to test')
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    
    if args.component == 'import' or args.component == 'all':
        import_dialog = RepositoryImport()
        import_dialog.show()
        
    if args.component == 'config' or args.component == 'all':
        config_dialog = RepositoryConfig()
        config_dialog.show()
        
    if args.component == 'browser' or args.component == 'all':
        browser = RepositoryBrowser()
        browser.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()