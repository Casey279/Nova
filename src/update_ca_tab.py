#!/usr/bin/env python3
"""
Update script to replace the original Chronicling America tab with the improved version.

This script:
1. Makes a backup of the original chronicling_america_tab.py
2. Reads the improved version and updates the class name to match the original
3. Writes the modified content to the original file
4. Validates the changes

Run this script to update your installation with the improved tab.
"""

import os
import sys
import shutil
import datetime
import re

def main():
    """Main function to update the Chronicling America tab."""
    print("Updating Chronicling America tab to improved version...")

    # Get the directory paths
    src_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.join(src_dir, "ui")

    # Path to the original and improved files
    original_file = os.path.join(ui_dir, "chronicling_america_tab.py")
    improved_file = os.path.join(ui_dir, "chronicling_america_tab_improved.py")

    # Check if files exist
    if not os.path.exists(original_file):
        print(f"Error: Original file not found at {original_file}")
        return False

    if not os.path.exists(improved_file):
        print(f"Error: Improved file not found at {improved_file}")
        return False

    # Create a backup of the original file
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = f"{original_file}.bak.{timestamp}"

    try:
        # Make a backup
        shutil.copy2(original_file, backup_file)
        print(f"Created backup at {backup_file}")

        # Read the improved file
        with open(improved_file, 'r', encoding='utf-8') as f:
            improved_content = f.read()

        # Replace class name to match the original
        improved_content = improved_content.replace('ChroniclingAmericaTabImproved', 'ChroniclingAmericaTab')

        # Write the modified content to the original file
        with open(original_file, 'w', encoding='utf-8') as f:
            f.write(improved_content)

        print(f"Successfully updated {original_file} with improved version")

        # Verify the update
        if os.path.getsize(original_file) > 0:
            print("Update successful!")
            print("Key improvements:")
            print("1. Better HTML parsing for newspaper listings")
            print("2. Enhanced dropdown display format for newspapers")
            print("3. Improved error handling and logging")
            print("4. Better handling of HTML content")
            print("\nThe changes will take effect the next time you run main_ui.py")
            return True
        else:
            print("Error: Updated file appears to be empty")
            # Try to restore from backup
            shutil.copy2(backup_file, original_file)
            print(f"Restored original file from backup")
            return False

    except Exception as e:
        print(f"Error during update: {str(e)}")
        # Try to restore from backup if it exists
        if os.path.exists(backup_file):
            try:
                shutil.copy2(backup_file, original_file)
                print(f"Restored original file from backup")
            except Exception as restore_error:
                print(f"Error restoring backup: {str(restore_error)}")
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)