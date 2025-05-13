#!/usr/bin/env python3
import re

# Path to the file
file_path = '/mnt/c/AI/Nova/src/services/import_service.py'

# Read the file content
with open(file_path, 'r') as f:
    content = f.read()

# Fix the duplicate method issue
# First, find the duplicate method definition
duplicate_pattern = r'def check_if_newspaper_page_exists\(self, lccn: str, issue_date: str, sequence: int\) -> Optional\[Dict\[str, Any\]\]:.*?return None\s+"""[^"]*?"""[^}]*?return None'
fixed_content = re.sub(duplicate_pattern, '', content, flags=re.DOTALL)

# Now modify the source_data creation to include ExternalURL
source_data_pattern = r'''                # Create a new source entry
                source_data = {
                    'SourceName': source_name,
                    'SourceType': source_type,
                    'Aliases': lccn,  # Store LCCN as alias for identification
                    'Publisher': '',
                    'Location': '',
                    'EstablishedDate': '',
                    'DiscontinuedDate': '',
                    'ImagePath': '',
                    'ReviewStatus': 'needs_review'
                }'''
source_data_fix = r'''                # Create a new source entry
                source_data = {
                    'SourceName': source_name,
                    'SourceType': source_type,
                    'Aliases': lccn,  # Store LCCN as alias for identification
                    'Publisher': '',
                    'Location': '',
                    'EstablishedDate': '',
                    'DiscontinuedDate': '',
                    'ImagePath': '',
                    'ReviewStatus': 'needs_review',
                    'ExternalURL': None  # Include the ExternalURL field
                }'''

fixed_content = re.sub(source_data_pattern, source_data_fix, fixed_content)

# Fix the fallback case too
fallback_pattern = r'''            # If an error occurs, fall back to creating a new source through the service
            return self.source_service.create_source\({
                'SourceName': source_name,
                'SourceType': source_type,
                'Aliases': lccn
            }\)'''
fallback_fix = r'''            # If an error occurs, fall back to creating a new source through the service
            return self.source_service.create_source({
                'SourceName': source_name,
                'SourceType': source_type,
                'Aliases': lccn,
                'ExternalURL': None  # Include the ExternalURL field
            })'''

fixed_content = re.sub(fallback_pattern, fallback_fix, fixed_content)

# Also fix the SQL INSERT to handle the ExternalURL field in the source_service.create_source
# Now improve the dialog to better show table differences
dialog_pattern = r'''            # Add more detailed dialog info to the download_completed method
dialog_pattern = r'            message \+= f"Successfully imported: {total_imported} items\\.\n"'
dialog_debug = r\'\'\'            message += f"Successfully imported: {total_imported} items.\n"
            message += f"  - Created {lccn_sources} source records in Sources table\n"
            message += f"  - Created {total_imported} page records in NewspaperPages table\n"\'\'\'

content = re.sub\(dialog_pattern, dialog_debug, content\)'''

dialog_fix = r'''            # Add more detailed dialog info to the download_completed method
            message += "Successfully imported newspaper pages:\n"
            message += f"  - Created {1 if total_imported > 0 else 0} newspaper source record in Sources table\n"
            message += f"  - Created {total_imported} newspaper page records in NewspaperPages table\n"
            message += f"  - Skipped {total_skipped} newspaper pages (already in database)\n"'''

fixed_content = re.sub(dialog_pattern, dialog_fix, fixed_content, flags=re.DOTALL)

# Write the updated file back
with open(file_path, 'w') as f:
    f.write(fixed_content)

print("Fixed duplicate method and ExternalURL handling in import_service.py")