#!/usr/bin/env python3
import os
import re

# Path to the file
file_path = '/mnt/c/AI/Nova/src/services/import_service.py'

# Read the file content
with open(file_path, 'r') as f:
    content = f.read()

# First, add debug logging to check_if_newspaper_page_exists
check_if_newspaper_page_exists_pattern = r'def check_if_newspaper_page_exists\(self, lccn: str, issue_date: str, sequence: int\) -> Optional\[Dict\[str, Any\]\]:'
check_if_newspaper_page_exists_debug = r'''def check_if_newspaper_page_exists(self, lccn: str, issue_date: str, sequence: int) -> Optional[Dict[str, Any]]:
        """
        Check if a newspaper page already exists in the NewspaperPages table.

        Args:
            lccn: LCCN identifier
            issue_date: Issue date
            sequence: Page sequence number

        Returns:
            Page data as a dictionary if found, None otherwise
        """
        print(f"DEBUG: check_if_newspaper_page_exists called with lccn={lccn}, issue_date={issue_date}, sequence={sequence}")
        try:
            # Connect to the database
            conn, cursor = self.connect()
            
            # First check if the table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='NewspaperPages'")
            table_exists = cursor.fetchone() is not None
            if not table_exists:
                print("DEBUG: NewspaperPages table does not exist!")
                conn.close()
                return None

            # Check for an exact match in the NewspaperPages table by LCCN + issue_date + sequence
            cursor.execute("""
                SELECT PageID, SourceID, LCCN, IssueDate, Sequence, ImagePath
                FROM NewspaperPages
                WHERE LCCN = ? AND IssueDate = ? AND Sequence = ?
            """, (lccn, issue_date, sequence))
            
            result = cursor.fetchone()

            if result:
                # Found an exact match
                print(f"DEBUG: Found exact match in NewspaperPages: LCCN={lccn}, issue_date={issue_date}, sequence={sequence}")
                conn.close()
                return {
                    'page_id': result[0],
                    'source_id': result[1],
                    'lccn': result[2],
                    'issue_date': result[3],
                    'sequence': result[4],
                    'image_path': result[5]
                }
            else:
                print(f"DEBUG: No match found in NewspaperPages for LCCN={lccn}, issue_date={issue_date}, sequence={sequence}")
            
            conn.close()
            return None
        except Exception as e:
            print(f"Error checking if newspaper page exists: {str(e)}")
            return None'''

content = re.sub(check_if_newspaper_page_exists_pattern, check_if_newspaper_page_exists_debug, content)

# Second, add debug logging to add_newspaper_page
add_newspaper_page_pattern = r'def add_newspaper_page\(self, source_id: int, lccn: str, issue_date: str, sequence: int,'
add_newspaper_page_debug = r'''def add_newspaper_page(self, source_id: int, lccn: str, issue_date: str, sequence: int,'''

content = re.sub(add_newspaper_page_pattern, add_newspaper_page_debug, content)

# Add debug to beginning of add_newspaper_page method
add_debug_pattern = r'def add_newspaper_page.*?\n        try:'
add_debug_replace = r'''def add_newspaper_page(self, source_id: int, lccn: str, issue_date: str, sequence: int,
                           page_title: str, image_path: str = None, ocr_path: str = None,
                           pdf_path: str = None, json_path: str = None, external_url: str = None) -> int:
        """
        Add a new newspaper page to the NewspaperPages table.

        Args:
            source_id: ID of the source in the Sources table
            lccn: LCCN identifier
            issue_date: Issue date
            sequence: Page sequence number
            page_title: Title of the page
            image_path: Path to the image file (optional)
            ocr_path: Path to the OCR file (optional)
            pdf_path: Path to the PDF file (optional)
            json_path: Path to the JSON metadata file (optional)
            external_url: External URL to the page (optional)

        Returns:
            ID of the new page
        """
        print(f"DEBUG: add_newspaper_page called with source_id={source_id}, lccn={lccn}, issue_date={issue_date}, sequence={sequence}")
        print(f"DEBUG: file paths - image_path={image_path}, ocr_path={ocr_path}, pdf_path={pdf_path}, json_path={json_path}")
        try:'''

content = re.sub(add_debug_pattern, add_debug_replace, content, flags=re.DOTALL)

# Add debug to the actual page addition code
page_addition_pattern = r'            # Add the newspaper page to the NewspaperPages table\n            page_id = self\.add_newspaper_page\('
page_addition_debug = r'''            # Add the newspaper page to the NewspaperPages table
            print(f"DEBUG: Calling add_newspaper_page with source_id={source_id}, lccn={page.lccn}, issue_date={page.issue_date}, sequence={page.sequence}")
            page_id = self.add_newspaper_page('''

content = re.sub(page_addition_pattern, page_addition_debug, content)

# Add more debug for the cursor.execute part
cursor_execute_pattern = r'            # Insert the page\n            cursor\.execute\('
cursor_execute_debug = r'''            # Insert the page
            print(f"DEBUG: About to execute INSERT into NewspaperPages")
            cursor.execute('''

content = re.sub(cursor_execute_pattern, cursor_execute_debug, content)

# Add more debug for the return path
commit_pattern = r'            # Commit the changes\n            conn\.commit\(\)'
commit_debug = r'''            # Commit the changes
            print(f"DEBUG: About to commit NewspaperPages insert")
            conn.commit()
            print(f"DEBUG: Commit successful!")'''

content = re.sub(commit_pattern, commit_debug, content)

# Add more detailed dialog info to the download_completed method
dialog_pattern = r'            message \+= f"Successfully imported: {total_imported} items\\.\n"'
dialog_debug = r'''            message += f"Successfully imported: {total_imported} items.\n"
            message += f"  - Created {lccn_sources} source records in Sources table\n"
            message += f"  - Created {total_imported} page records in NewspaperPages table\n"'''

content = re.sub(dialog_pattern, dialog_debug, content)

# Fix the unique identifier for sources search in get_or_create_source_by_lccn
lccn_query_pattern = r'            # Try to find the source by LCCN in the Aliases field\n            cursor\.execute\(\"""'
lccn_query_debug = r'''            # Try to find the source by LCCN in the Aliases field
            print(f"DEBUG: Searching for source with exact LCCN={lccn}")
            cursor.execute("""'''

content = re.sub(lccn_query_pattern, lccn_query_debug, content)

# Change the LIKE query to an exact match
like_pattern = r'                WHERE Aliases LIKE \?\n            """, \(f"%{lccn}%",\)\)'
exact_match = r'''                WHERE Aliases = ?
            """, (lccn,))'''

content = re.sub(like_pattern, exact_match, content)

# Write the updated file back
with open(file_path, 'w') as f:
    f.write(content)

print("Debug logging added to import_service.py")