# File: file_utils.py

import os
import shutil
import tempfile
from typing import List, Dict, Any, Tuple, Optional
import mimetypes
import hashlib

def get_file_extension(file_path: str) -> str:
    """
    Get the extension of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File extension (including the dot)
    """
    return os.path.splitext(file_path)[1].lower()

def get_file_name(file_path: str) -> str:
    """
    Get the name of a file without extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File name without extension
    """
    return os.path.splitext(os.path.basename(file_path))[0]

def get_mime_type(file_path: str) -> str:
    """
    Get the MIME type of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"

def is_text_file(file_path: str) -> bool:
    """
    Check if a file is a text file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file is a text file, False otherwise
    """
    mime_type = get_mime_type(file_path)
    return mime_type and mime_type.startswith('text/')

def is_image_file(file_path: str) -> bool:
    """
    Check if a file is an image file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file is an image file, False otherwise
    """
    mime_type = get_mime_type(file_path)
    return mime_type and mime_type.startswith('image/')

def is_document_file(file_path: str) -> bool:
    """
    Check if a file is a document file (PDF, DOC, DOCX, etc.).
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file is a document file, False otherwise
    """
    ext = get_file_extension(file_path).lower()
    document_extensions = ['.pdf', '.doc', '.docx', '.rtf', '.odt', '.txt']
    return ext in document_extensions

def create_temp_file(prefix: str = "temp", suffix: str = "") -> str:
    """
    Create a temporary file.
    
    Args:
        prefix: Prefix for the file name
        suffix: Suffix for the file name (extension)
        
    Returns:
        Path to the temporary file
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return path

def calculate_file_hash(file_path: str, algorithm: str = 'md5') -> str:
    """
    Calculate a hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use
        
    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()

def ensure_directory_exists(directory_path: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory
    """
    os.makedirs(directory_path, exist_ok=True)

def copy_file(source_path: str, dest_path: str) -> bool:
    """
    Copy a file from source to destination.
    
    Args:
        source_path: Path to the source file
        dest_path: Path to the destination file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        shutil.copy2(source_path, dest_path)
        return True
    except Exception:
        return False

def move_file(source_path: str, dest_path: str) -> bool:
    """
    Move a file from source to destination.
    
    Args:
        source_path: Path to the source file
        dest_path: Path to the destination file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        shutil.move(source_path, dest_path)
        return True
    except Exception:
        return False

def list_files_with_extension(directory_path: str, extension: str) -> List[str]:
    """
    List all files in a directory with a specific extension.
    
    Args:
        directory_path: Path to the directory
        extension: File extension to filter by
        
    Returns:
        List of file paths
    """
    if not extension.startswith('.'):
        extension = '.' + extension
    
    extension = extension.lower()
    
    files = []
    for file_name in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path) and file_name.lower().endswith(extension):
            files.append(file_path)
    
    return files

def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes
    """
    return os.path.getsize(file_path)

def format_file_size(size_bytes: int) -> str:
    """
    Format a file size in a human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted file size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    
    size_kb = size_bytes / 1024
    if size_kb < 1024:
        return f"{size_kb:.1f} KB"
    
    size_mb = size_kb / 1024
    if size_mb < 1024:
        return f"{size_mb:.1f} MB"
    
    size_gb = size_mb / 1024
    return f"{size_gb:.1f} GB"