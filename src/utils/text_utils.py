# File: text_utils.py

import re
from typing import List, Dict, Any, Tuple, Set, Optional
import string

def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and normalizing line breaks.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Replace multiple line breaks with double line breaks
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Trim leading/trailing whitespace
    text = text.strip()
    
    return text

def extract_sentences(text: str) -> List[str]:
    """
    Extract sentences from text.
    
    Args:
        text: Text to extract sentences from
        
    Returns:
        List of sentences
    """
    # Simple sentence extraction using regex
    # This is a basic implementation and might not handle all cases correctly
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Filter out empty sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return sentences

def find_exact_matches(text: str, search_term: str) -> List[Tuple[int, int]]:
    """
    Find exact matches of a search term in text.
    
    Args:
        text: Text to search in
        search_term: Term to search for
        
    Returns:
        List of tuples with (start, end) positions
    """
    matches = []
    for match in re.finditer(re.escape(search_term), text, re.IGNORECASE):
        matches.append(match.span())
    
    return matches

def find_fuzzy_matches(text: str, search_term: str, threshold: float = 0.8) -> List[Tuple[int, int, float]]:
    """
    Find fuzzy matches of a search term in text.
    
    Args:
        text: Text to search in
        search_term: Term to search for
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        List of tuples with (start, end, score) positions
    """
    # This would implement fuzzy matching logic
    # For now, we return an empty list as a placeholder
    return []

def extract_context(text: str, start: int, end: int, context_size: int = 50) -> str:
    """
    Extract context around a match.
    
    Args:
        text: Text to extract context from
        start: Start position of the match
        end: End position of the match
        context_size: Number of characters to include before and after
        
    Returns:
        Context string
    """
    context_start = max(0, start - context_size)
    context_end = min(len(text), end + context_size)
    
    prefix = "..." if context_start > 0 else ""
    suffix = "..." if context_end < len(text) else ""
    
    return prefix + text[context_start:context_end] + suffix

def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    # Simple Jaccard similarity implementation
    # Convert texts to sets of words
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # Calculate Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 0.0
    
    return intersection / union

def is_similar_name(name1: str, name2: str, threshold: float = 0.7) -> bool:
    """
    Check if two names are similar.
    
    Args:
        name1: First name
        name2: Second name
        threshold: Similarity threshold
        
    Returns:
        True if names are similar, False otherwise
    """
    # Clean and normalize names
    name1 = name1.lower().strip()
    name2 = name2.lower().strip()
    
    # Check for exact match
    if name1 == name2:
        return True
    
    # Check if one is contained in the other
    if name1 in name2 or name2 in name1:
        return True
    
    # Check for initials match
    if is_initials_match(name1, name2):
        return True
    
    # Calculate similarity
    similarity = calculate_similarity(name1, name2)
    
    return similarity >= threshold

def is_initials_match(name1: str, name2: str) -> bool:
    """
    Check if one name is initials of the other.
    
    Args:
        name1: First name
        name2: Second name
        
    Returns:
        True if one name is initials of the other, False otherwise
    """
    name1_parts = name1.split()
    name2_parts = name2.split()
    
    # If one name has only one part, it can't be initials
    if len(name1_parts) <= 1 or len(name2_parts) <= 1:
        return False
    
    # Get initials of both names
    initials1 = ''.join(part[0] for part in name1_parts if part)
    initials2 = ''.join(part[0] for part in name2_parts if part)
    
    # Check if initials match the first letter of the first part of the other name
    return (initials1 and initials1.lower() == name2_parts[0][0].lower()) or \
           (initials2 and initials2.lower() == name1_parts[0][0].lower())