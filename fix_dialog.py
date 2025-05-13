#!/usr/bin/env python3
import re

# Path to the file
file_path = '/mnt/c/AI/Nova/src/services/import_service.py'

# Read the file content
with open(file_path, 'r') as f:
    content = f.read()

# Find the download_completed method and fix the dialog message
dialog_pattern = r'''            # Show result message
            message = f"Operation completed\.\n\n"

            if self\.import_check\.isChecked\(\):
                message \+= f"Downloaded: {total_downloaded} items\.\n"
                message \+= f"Successfully imported: {total_imported} items\.\n"
                message \+= f"Skipped \(already in database\): {total_skipped} items\.\n"
                message \+= f"Failed imports: {len\(failed\)} items\.\n\n"'''

dialog_fix = r'''            # Show result message
            message = f"Operation completed.\n\n"

            if self.import_check.isChecked():
                message += "Newspaper Pages:\n"
                message += f"- Downloaded: {total_downloaded} pages\n"
                message += f"- Created {1 if total_imported > 0 else 0} newspaper source record in Sources table\n"
                message += f"- Created {total_imported} newspaper page records in NewspaperPages table\n"
                message += f"- Skipped {total_skipped} pages (already in database)\n"
                message += f"- Failed imports: {len(failed)} pages\n\n"'''

fixed_content = re.sub(dialog_pattern, dialog_fix, content)

# Write the updated file back
with open(file_path, 'w') as f:
    f.write(fixed_content)

print("Fixed dialog message in download_completed method")