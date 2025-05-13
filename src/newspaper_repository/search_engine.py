"""
Newspaper Repository Search Engine

This module provides a search engine for the newspaper repository that:
1. Provides full-text search across both repositories (main database and newspaper repository)
2. Implements fuzzy matching for better results
3. Supports advanced query syntax (AND, OR, NOT)
4. Ranks results by relevance
5. Includes faceted search options (by date, source, etc.)
6. Integrates with both the repository and main database
"""

import os
import json
import re
import sqlite3
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from datetime import datetime, date
import logging
from collections import Counter, defaultdict
import math
from functools import lru_cache
from enum import Enum
import difflib
from dataclasses import dataclass, field

# For fuzzy matching
from fuzzywuzzy import fuzz, process

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchSource(Enum):
    """Enum for possible search sources."""
    ALL = "all"  # Search in both repositories
    MAIN = "main"  # Search only in main database
    NEWSPAPER = "newspaper"  # Search only in newspaper repository


class SearchResultType(Enum):
    """Enum for possible search result types."""
    NEWSPAPER_PAGE = "newspaper_page"
    NEWSPAPER_ARTICLE = "newspaper_article"
    ARTICLE_SEGMENT = "article_segment"
    SOURCE = "source"  # From main database
    EVENT = "event"  # From main database


@dataclass
class SearchResult:
    """Data class for search results."""
    id: str
    title: str
    content: str
    result_type: SearchResultType
    source: SearchSource
    date: Optional[date] = None
    score: float = 0.0
    highlights: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert search result to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "result_type": self.result_type.value,
            "source": self.source.value,
            "date": self.date.isoformat() if self.date else None,
            "score": self.score,
            "highlights": self.highlights,
            "metadata": self.metadata,
            "url": self.url
        }


@dataclass
class SearchFacet:
    """Data class for search facets."""
    name: str
    values: Dict[str, int]  # Value -> Count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert facet to dictionary."""
        return {
            "name": self.name,
            "values": self.values
        }


@dataclass
class SearchOptions:
    """Data class for search options."""
    query: str
    source: SearchSource = SearchSource.ALL
    limit: int = 100
    offset: int = 0
    min_score: float = 0.0
    fuzzy: bool = True
    fuzzy_threshold: int = 70  # Minimum fuzz ratio to match (0-100)
    facets: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    date_start: Optional[date] = None
    date_end: Optional[date] = None


@dataclass
class SearchResponse:
    """Data class for search responses."""
    query: str
    results: List[SearchResult]
    total_count: int
    facets: Dict[str, SearchFacet] = field(default_factory=dict)
    execution_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert search response to dictionary."""
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "facets": {k: v.to_dict() for k, v in self.facets.items()},
            "execution_time_ms": self.execution_time_ms
        }


class QueryParser:
    """
    Parser for advanced search queries.
    
    Supports:
    - AND, OR, NOT operators (uppercase)
    - Phrase search with quotes: "exact phrase"
    - Parentheses for grouping
    - Field-specific search with colon: title:term
    """
    
    def __init__(self):
        """Initialize the query parser."""
        # Define tokens for lexing
        self.AND = 'AND'
        self.OR = 'OR'
        self.NOT = 'NOT'
        self.LPAREN = '('
        self.RPAREN = ')'
        self.QUOTE = '"'
        self.COLON = ':'
        
        # Compiled regex patterns
        self.token_pattern = re.compile(
            r'"[^"]*"|\(|\)|AND|OR|NOT|[a-zA-Z0-9_]+:[a-zA-Z0-9_]+|[a-zA-Z0-9_]+'
        )
    
    def tokenize(self, query: str) -> List[str]:
        """
        Convert query string into tokens.
        
        Args:
            query: Query string
            
        Returns:
            List of tokens
        """
        return self.token_pattern.findall(query)
    
    def parse(self, query: str) -> Dict[str, Any]:
        """
        Parse query into structured representation for search.
        
        Args:
            query: Query string
            
        Returns:
            Structured query dictionary
        """
        tokens = self.tokenize(query)
        
        # Parse tokens into structured query
        parsed_query = self._parse_tokens(tokens)
        
        return parsed_query
    
    def _parse_tokens(self, tokens: List[str]) -> Dict[str, Any]:
        """
        Parse list of tokens into structured query.
        
        Args:
            tokens: List of tokens
            
        Returns:
            Structured query dictionary
        """
        if not tokens:
            return {"type": "match_none"}
        
        # Handle single token case
        if len(tokens) == 1:
            return self._parse_single_token(tokens[0])
        
        # Find all field-specific searches (field:value)
        field_queries = []
        remaining_tokens = []
        
        for token in tokens:
            if ':' in token and not token.startswith('"'):
                field, value = token.split(':', 1)
                field_queries.append({
                    "type": "field_match",
                    "field": field,
                    "value": value
                })
            else:
                remaining_tokens.append(token)
        
        # Process operators (AND, OR, NOT)
        operator_queries = []
        i = 0
        
        while i < len(remaining_tokens):
            token = remaining_tokens[i]
            
            if token == self.AND and i > 0 and i < len(remaining_tokens) - 1:
                # AND operator: both terms must match
                left = remaining_tokens[i-1]
                right = remaining_tokens[i+1]
                
                operator_queries.append({
                    "type": "and",
                    "left": self._parse_single_token(left),
                    "right": self._parse_single_token(right)
                })
                
                i += 2  # Skip the processed tokens
                
            elif token == self.OR and i > 0 and i < len(remaining_tokens) - 1:
                # OR operator: either term can match
                left = remaining_tokens[i-1]
                right = remaining_tokens[i+1]
                
                operator_queries.append({
                    "type": "or",
                    "left": self._parse_single_token(left),
                    "right": self._parse_single_token(right)
                })
                
                i += 2  # Skip the processed tokens
                
            elif token == self.NOT and i < len(remaining_tokens) - 1:
                # NOT operator: term must not match
                right = remaining_tokens[i+1]
                
                operator_queries.append({
                    "type": "not",
                    "query": self._parse_single_token(right)
                })
                
                i += 2  # Skip the processed tokens
                
            else:
                # Regular term
                if token not in [self.AND, self.OR, self.NOT]:
                    term_query = self._parse_single_token(token)
                    operator_queries.append(term_query)
                
                i += 1
        
        # Combine all queries
        all_queries = field_queries + operator_queries
        
        if not all_queries:
            return {"type": "match_none"}
        elif len(all_queries) == 1:
            return all_queries[0]
        else:
            return {
                "type": "and",
                "queries": all_queries
            }
    
    def _parse_single_token(self, token: str) -> Dict[str, Any]:
        """
        Parse a single token into a query component.
        
        Args:
            token: Token string
            
        Returns:
            Query component dictionary
        """
        if token.startswith('"') and token.endswith('"'):
            # Phrase search
            phrase = token[1:-1]
            return {
                "type": "phrase",
                "text": phrase
            }
        elif ':' in token:
            # Field-specific search
            field, value = token.split(':', 1)
            return {
                "type": "field_match",
                "field": field,
                "value": value
            }
        else:
            # Term search
            return {
                "type": "term",
                "text": token
            }


class Indexer:
    """
    Indexer for building and updating the search index.
    
    This class handles the creation and maintenance of the search index
    for both the newspaper repository and main database.
    """
    
    def __init__(self, index_path: str):
        """
        Initialize the indexer.
        
        Args:
            index_path: Path to store the index
        """
        self.index_path = index_path
        self.stopwords = self._load_stopwords()
        
        # Ensure index directory exists
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        
        # Initialize index database if it doesn't exist
        self._init_index_db()
    
    def _load_stopwords(self) -> Set[str]:
        """
        Load list of stopwords (common words to exclude from indexing).
        
        Returns:
            Set of stopwords
        """
        # Common English stopwords
        return {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
            "to", "was", "were", "will", "with"
        }
    
    def _init_index_db(self) -> None:
        """Initialize the index database schema if it doesn't exist."""
        conn = sqlite3.connect(self.index_path)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT,
            content TEXT,
            date TEXT,
            metadata TEXT,
            last_indexed TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS terms (
            term TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            field TEXT NOT NULL,
            frequency INTEGER NOT NULL,
            positions TEXT,
            PRIMARY KEY (term, doc_id, field),
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        )
        ''')
        
        # Create indices for faster lookup
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(date)')
        
        conn.commit()
        conn.close()
    
    def index_newspaper_page(self, page_id: str, page_data: Dict[str, Any]) -> None:
        """
        Index a newspaper page.
        
        Args:
            page_id: ID of the page
            page_data: Page data dictionary
        """
        # Extract relevant fields
        doc_id = f"newspaper_page_{page_id}"
        source = SearchSource.NEWSPAPER.value
        doc_type = SearchResultType.NEWSPAPER_PAGE.value
        
        title = page_data.get("publication_name", "")
        if page_data.get("page_number"):
            title += f" - Page {page_data['page_number']}"
        
        content = page_data.get("ocr_text", "")
        
        # Parse date
        date_str = page_data.get("publication_date")
        date_indexed = None
        if date_str:
            try:
                date_obj = datetime.fromisoformat(date_str).date()
                date_indexed = date_obj.isoformat()
            except (ValueError, TypeError):
                pass
        
        # Metadata
        metadata = page_data.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        
        # Add specific fields to metadata
        metadata.update({
            "publication_name": page_data.get("publication_name", ""),
            "page_number": page_data.get("page_number", ""),
            "source_id": page_data.get("source_id", ""),
            "source_type": page_data.get("source_type", "")
        })
        
        # Index the document
        self._index_document(
            doc_id=doc_id,
            source=source,
            doc_type=doc_type,
            title=title,
            content=content,
            date=date_indexed,
            metadata=metadata
        )
    
    def index_article_segment(self, segment_id: str, segment_data: Dict[str, Any], 
                              page_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Index an article segment.
        
        Args:
            segment_id: ID of the segment
            segment_data: Segment data dictionary
            page_data: Optional parent page data
        """
        # Extract relevant fields
        doc_id = f"article_segment_{segment_id}"
        source = SearchSource.NEWSPAPER.value
        doc_type = SearchResultType.ARTICLE_SEGMENT.value
        
        # Generate title from segment type and first few words
        segment_type = segment_data.get("segment_type", "segment")
        content = segment_data.get("content", "")
        
        title_words = content.split()[:10]
        title = f"{segment_type.capitalize()}: {' '.join(title_words)}..."
        
        # Parse date from parent page
        date_indexed = None
        if page_data and page_data.get("publication_date"):
            try:
                date_str = page_data["publication_date"]
                date_obj = datetime.fromisoformat(date_str).date()
                date_indexed = date_obj.isoformat()
            except (ValueError, TypeError):
                pass
        
        # Metadata
        metadata = {
            "segment_type": segment_type,
            "page_id": segment_data.get("page_id", ""),
            "confidence": segment_data.get("confidence", 0),
        }
        
        # Add page metadata if available
        if page_data:
            metadata.update({
                "publication_name": page_data.get("publication_name", ""),
                "page_number": page_data.get("page_number", ""),
                "source_id": page_data.get("source_id", ""),
                "source_type": page_data.get("source_type", "")
            })
        
        # Get position data if available
        position_data = segment_data.get("position_data", "{}")
        if isinstance(position_data, str):
            try:
                position_dict = json.loads(position_data)
                metadata["position"] = position_dict
            except json.JSONDecodeError:
                pass
        
        # Index the document
        self._index_document(
            doc_id=doc_id,
            source=source,
            doc_type=doc_type,
            title=title,
            content=content,
            date=date_indexed,
            metadata=metadata
        )
    
    def index_newspaper_article(self, article_id: str, article_data: Dict[str, Any],
                              page_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Index a newspaper article.
        
        Args:
            article_id: ID of the article
            article_data: Article data dictionary
            page_data: Optional parent page data
        """
        # Extract relevant fields
        doc_id = f"newspaper_article_{article_id}"
        source = SearchSource.NEWSPAPER.value
        doc_type = SearchResultType.NEWSPAPER_ARTICLE.value
        
        title = article_data.get("title", "Untitled Article")
        content = article_data.get("content", "")
        
        # Parse date from parent page
        date_indexed = None
        if page_data and page_data.get("publication_date"):
            try:
                date_str = page_data["publication_date"]
                date_obj = datetime.fromisoformat(date_str).date()
                date_indexed = date_obj.isoformat()
            except (ValueError, TypeError):
                pass
        
        # Metadata
        metadata = {
            "article_type": article_data.get("article_type", ""),
            "page_id": article_data.get("page_id", "")
        }
        
        # Add page metadata if available
        if page_data:
            metadata.update({
                "publication_name": page_data.get("publication_name", ""),
                "page_number": page_data.get("page_number", ""),
                "source_id": page_data.get("source_id", ""),
                "source_type": page_data.get("source_type", "")
            })
        
        # Parse segment IDs if available
        segment_ids = article_data.get("segment_ids", "[]")
        if isinstance(segment_ids, str):
            try:
                segments = json.loads(segment_ids)
                metadata["segments"] = segments
            except json.JSONDecodeError:
                pass
        
        # Index the document
        self._index_document(
            doc_id=doc_id,
            source=source,
            doc_type=doc_type,
            title=title,
            content=content,
            date=date_indexed,
            metadata=metadata
        )
    
    def index_main_source(self, source_id: str, source_data: Dict[str, Any]) -> None:
        """
        Index a source from the main database.
        
        Args:
            source_id: ID of the source
            source_data: Source data dictionary
        """
        # Extract relevant fields
        doc_id = f"main_source_{source_id}"
        source = SearchSource.MAIN.value
        doc_type = SearchResultType.SOURCE.value
        
        title = source_data.get("title", "Untitled Source")
        content = source_data.get("content", "")
        
        # Parse date
        date_indexed = None
        date_str = source_data.get("publication_date")
        if date_str:
            try:
                date_obj = datetime.fromisoformat(date_str).date()
                date_indexed = date_obj.isoformat()
            except (ValueError, TypeError):
                pass
        
        # Metadata
        metadata = {
            "author": source_data.get("author", ""),
            "source_type": source_data.get("source_type", ""),
            "url": source_data.get("url", "")
        }
        
        # Index the document
        self._index_document(
            doc_id=doc_id,
            source=source,
            doc_type=doc_type,
            title=title,
            content=content,
            date=date_indexed,
            metadata=metadata
        )
    
    def index_main_event(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Index an event from the main database.
        
        Args:
            event_id: ID of the event
            event_data: Event data dictionary
        """
        # Extract relevant fields
        doc_id = f"main_event_{event_id}"
        source = SearchSource.MAIN.value
        doc_type = SearchResultType.EVENT.value
        
        title = event_data.get("name", "Untitled Event")
        content = event_data.get("description", "")
        
        # Parse date
        date_indexed = None
        date_str = event_data.get("date")
        if date_str:
            try:
                date_obj = datetime.fromisoformat(date_str).date()
                date_indexed = date_obj.isoformat()
            except (ValueError, TypeError):
                pass
        
        # Metadata
        metadata = {
            "location": event_data.get("location", ""),
            "event_type": event_data.get("event_type", ""),
            "tags": event_data.get("tags", [])
        }
        
        # Index the document
        self._index_document(
            doc_id=doc_id,
            source=source,
            doc_type=doc_type,
            title=title,
            content=content,
            date=date_indexed,
            metadata=metadata
        )
    
    def delete_document(self, doc_id: str) -> None:
        """
        Delete a document from the index.
        
        Args:
            doc_id: Document ID to delete
        """
        conn = sqlite3.connect(self.index_path)
        cursor = conn.cursor()
        
        # Delete the document and its terms
        cursor.execute('DELETE FROM documents WHERE doc_id = ?', (doc_id,))
        cursor.execute('DELETE FROM terms WHERE doc_id = ?', (doc_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted document from index: {doc_id}")
    
    def _index_document(self, doc_id: str, source: str, doc_type: str, title: str, 
                       content: str, date: Optional[str] = None, 
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Index a document by adding it to the search index.
        
        Args:
            doc_id: Unique document ID
            source: Source of the document
            doc_type: Type of document
            title: Document title
            content: Document content
            date: Document date (ISO format)
            metadata: Additional metadata
        """
        conn = sqlite3.connect(self.index_path)
        cursor = conn.cursor()
        
        # Check if document already exists
        cursor.execute('SELECT doc_id FROM documents WHERE doc_id = ?', (doc_id,))
        exists = cursor.fetchone() is not None
        
        # Convert metadata to JSON string
        metadata_json = json.dumps(metadata or {})
        current_time = datetime.now().isoformat()
        
        if exists:
            # Update existing document
            cursor.execute('''
            UPDATE documents
            SET source = ?, type = ?, title = ?, content = ?, date = ?, metadata = ?, last_indexed = ?
            WHERE doc_id = ?
            ''', (source, doc_type, title, content, date, metadata_json, current_time, doc_id))
            
            # Delete existing terms for this document
            cursor.execute('DELETE FROM terms WHERE doc_id = ?', (doc_id,))
        else:
            # Insert new document
            cursor.execute('''
            INSERT INTO documents (doc_id, source, type, title, content, date, metadata, last_indexed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, source, doc_type, title, content, date, metadata_json, current_time))
        
        # Index terms in title
        if title:
            self._index_field(cursor, doc_id, "title", title)
        
        # Index terms in content
        if content:
            self._index_field(cursor, doc_id, "content", content)
        
        # Index selected metadata fields
        if metadata:
            for field, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    field_name = f"metadata.{field}"
                    self._index_field(cursor, doc_id, field_name, str(value))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Indexed document: {doc_id}")
    
    def _index_field(self, cursor: sqlite3.Cursor, doc_id: str, field: str, text: str) -> None:
        """
        Index terms in a field of a document.
        
        Args:
            cursor: Database cursor
            doc_id: Document ID
            field: Field name
            text: Field text
        """
        # Tokenize text
        terms_with_positions = self._tokenize(text)
        
        # Group by term
        term_frequencies = Counter(term for term, _ in terms_with_positions)
        
        # Group positions by term
        term_positions = defaultdict(list)
        for term, position in terms_with_positions:
            term_positions[term].append(position)
        
        # Insert terms into index
        for term, frequency in term_frequencies.items():
            positions_json = json.dumps(term_positions[term])
            
            cursor.execute('''
            INSERT INTO terms (term, doc_id, field, frequency, positions)
            VALUES (?, ?, ?, ?, ?)
            ''', (term, doc_id, field, frequency, positions_json))
    
    def _tokenize(self, text: str) -> List[Tuple[str, int]]:
        """
        Tokenize text into terms with positions.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of (term, position) tuples
        """
        # Convert to lowercase
        text = text.lower()
        
        # Replace common punctuation with spaces
        text = re.sub(r'[.,;:!?()[\]{}"\'-]', ' ', text)
        
        # Split into words
        words = text.split()
        
        # Filter out stopwords and apply stemming
        terms_with_positions = []
        position = 0
        
        for word in words:
            # Skip stopwords and very short words
            if word in self.stopwords or len(word) < 2:
                continue
            
            # Apply simple stemming (just a placeholder, use a proper stemmer in production)
            term = self._simple_stem(word)
            
            terms_with_positions.append((term, position))
            position += 1
        
        return terms_with_positions
    
    def _simple_stem(self, word: str) -> str:
        """
        Apply simple stemming to a word.
        
        Args:
            word: Word to stem
            
        Returns:
            Stemmed word
        """
        # This is a very simple stemmer, consider using a proper one like Porter in production
        if word.endswith('ing'):
            return word[:-3]
        elif word.endswith('ed'):
            return word[:-2]
        elif word.endswith('s'):
            return word[:-1]
        return word
    
    def optimize_index(self) -> None:
        """Optimize the index for faster searches."""
        conn = sqlite3.connect(self.index_path)
        cursor = conn.cursor()
        
        # Analyze tables for better query planning
        cursor.execute('ANALYZE')
        
        # Vacuum database to reclaim space
        cursor.execute('VACUUM')
        
        conn.commit()
        conn.close()
        
        logger.info("Optimized search index")


class SearchEngine:
    """
    Search engine for the newspaper repository.
    
    This class provides search functionality across both the newspaper repository
    and the main database, with support for fuzzy matching, advanced query syntax,
    and faceted search.
    """
    
    def __init__(self, index_path: str, newspaper_db_path: str, main_db_path: str):
        """
        Initialize the search engine.
        
        Args:
            index_path: Path to the search index
            newspaper_db_path: Path to the newspaper repository database
            main_db_path: Path to the main database
        """
        self.index_path = index_path
        self.newspaper_db_path = newspaper_db_path
        self.main_db_path = main_db_path
        
        # Initialize components
        self.indexer = Indexer(index_path)
        self.query_parser = QueryParser()
        
        # Calculate total document count for IDF calculations
        self.total_documents = self._count_total_documents()
    
    def _count_total_documents(self) -> int:
        """
        Count the total number of documents in the index.
        
        Returns:
            Total document count
        """
        try:
            conn = sqlite3.connect(self.index_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM documents')
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            return 0
    
    def search(self, options: SearchOptions) -> SearchResponse:
        """
        Search the repository based on the provided options.
        
        Args:
            options: Search options
            
        Returns:
            Search response
        """
        start_time = datetime.now()
        
        # Parse query
        parsed_query = self.query_parser.parse(options.query)
        
        # Execute search
        results, total_count = self._execute_search(parsed_query, options)
        
        # Generate facets if requested
        facets = {}
        if options.facets:
            facets = self._generate_facets(results, options.facets)
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        response = SearchResponse(
            query=options.query,
            results=results,
            total_count=total_count,
            facets=facets,
            execution_time_ms=int(execution_time)
        )
        
        return response
    
    def _execute_search(self, parsed_query: Dict[str, Any], options: SearchOptions) -> Tuple[List[SearchResult], int]:
        """
        Execute a search query against the index.
        
        Args:
            parsed_query: Parsed query
            options: Search options
            
        Returns:
            Tuple of (results, total_count)
        """
        conn = sqlite3.connect(self.index_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()
        
        # Build SQL query
        select_clause = 'SELECT d.doc_id, d.source, d.type, d.title, d.content, d.date, d.metadata'
        from_clause = 'FROM documents d'
        where_clause = []
        params = []
        
        # Filter by source
        if options.source != SearchSource.ALL:
            where_clause.append('d.source = ?')
            params.append(options.source.value)
        
        # Filter by date range
        if options.date_start:
            where_clause.append('d.date >= ?')
            params.append(options.date_start.isoformat())
        
        if options.date_end:
            where_clause.append('d.date <= ?')
            params.append(options.date_end.isoformat())
        
        # Apply custom filters
        for field, value in options.filters.items():
            if field == 'type':
                where_clause.append('d.type = ?')
                params.append(value)
            elif field.startswith('metadata.'):
                metadata_field = field[9:]  # Remove 'metadata.' prefix
                # JSON path filtering (simplified approach)
                where_clause.append(f"JSON_EXTRACT(d.metadata, '$.{metadata_field}') = ?")
                params.append(value)
            else:
                # Other fields
                where_clause.append(f'd.{field} = ?')
                params.append(value)
        
        # Build the complete WHERE clause
        where_str = ' WHERE ' + ' AND '.join(where_clause) if where_clause else ''
        
        # Get matching documents
        matching_docs = self._find_matching_documents(cursor, parsed_query, options)
        
        if not matching_docs:
            conn.close()
            return [], 0
        
        # Add matching documents to WHERE clause
        if where_clause:
            where_str += f" AND d.doc_id IN ({','.join(['?'] * len(matching_docs))})"
        else:
            where_str = f" WHERE d.doc_id IN ({','.join(['?'] * len(matching_docs))})"
        
        params.extend(list(matching_docs.keys()))
        
        # Final SQL query
        sql = f"{select_clause} {from_clause}{where_str} ORDER BY ? LIMIT ? OFFSET ?"
        params.extend(['score DESC', options.limit, options.offset])
        
        # Execute query
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Convert rows to SearchResult objects
        results = []
        for row in rows:
            doc_id = row['doc_id']
            doc_score = matching_docs.get(doc_id, {}).get('score', 0)
            
            # Skip results below minimum score
            if doc_score < options.min_score:
                continue
            
            # Parse metadata
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
            
            # Parse date
            date_obj = None
            if row['date']:
                try:
                    date_obj = datetime.fromisoformat(row['date']).date()
                except (ValueError, TypeError):
                    pass
            
            # Get highlights
            highlights = matching_docs.get(doc_id, {}).get('highlights', [])
            
            # Create result
            result = SearchResult(
                id=doc_id,
                title=row['title'],
                content=self._truncate_content(row['content'], 200),
                result_type=SearchResultType(row['type']),
                source=SearchSource(row['source']),
                date=date_obj,
                score=doc_score,
                highlights=highlights,
                metadata=metadata
            )
            
            results.append(result)
        
        # Get total count
        total_sql = f"SELECT COUNT(*) FROM documents d{where_str}"
        cursor.execute(total_sql, params[:-3])  # Remove ORDER BY, LIMIT, OFFSET params
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        return results, total_count
    
    def _find_matching_documents(self, cursor: sqlite3.Cursor, parsed_query: Dict[str, Any], 
                                options: SearchOptions) -> Dict[str, Dict[str, Any]]:
        """
        Find documents matching the parsed query.
        
        Args:
            cursor: Database cursor
            parsed_query: Parsed query
            options: Search options
            
        Returns:
            Dictionary of matching documents with scores and highlights
        """
        if parsed_query.get('type') == 'match_none':
            return {}
        
        # Handle different query types
        if parsed_query.get('type') == 'term':
            return self._find_term_matches(cursor, parsed_query['text'], options)
        elif parsed_query.get('type') == 'phrase':
            return self._find_phrase_matches(cursor, parsed_query['text'], options)
        elif parsed_query.get('type') == 'field_match':
            return self._find_field_matches(cursor, parsed_query['field'], parsed_query['value'], options)
        elif parsed_query.get('type') == 'and':
            if 'left' in parsed_query and 'right' in parsed_query:
                # Binary AND
                left_matches = self._find_matching_documents(cursor, parsed_query['left'], options)
                right_matches = self._find_matching_documents(cursor, parsed_query['right'], options)
                
                # Find intersection and combine scores
                result = {}
                for doc_id in set(left_matches.keys()) & set(right_matches.keys()):
                    result[doc_id] = {
                        'score': left_matches[doc_id]['score'] + right_matches[doc_id]['score'],
                        'highlights': left_matches[doc_id]['highlights'] + right_matches[doc_id]['highlights']
                    }
                return result
            elif 'queries' in parsed_query:
                # Multiple AND
                if not parsed_query['queries']:
                    return {}
                
                results = [self._find_matching_documents(cursor, q, options) for q in parsed_query['queries']]
                
                # Find intersection of all queries
                common_docs = set.intersection(*[set(r.keys()) for r in results]) if results else set()
                
                # Combine scores and highlights
                result = {}
                for doc_id in common_docs:
                    score = sum(r[doc_id]['score'] for r in results)
                    highlights = sum([r[doc_id]['highlights'] for r in results], [])
                    result[doc_id] = {'score': score, 'highlights': highlights}
                
                return result
        elif parsed_query.get('type') == 'or':
            if 'left' in parsed_query and 'right' in parsed_query:
                # Binary OR
                left_matches = self._find_matching_documents(cursor, parsed_query['left'], options)
                right_matches = self._find_matching_documents(cursor, parsed_query['right'], options)
                
                # Combine results
                result = left_matches.copy()
                for doc_id, doc_data in right_matches.items():
                    if doc_id in result:
                        result[doc_id]['score'] += doc_data['score']
                        result[doc_id]['highlights'].extend(doc_data['highlights'])
                    else:
                        result[doc_id] = doc_data
                
                return result
            elif 'queries' in parsed_query:
                # Multiple OR
                if not parsed_query['queries']:
                    return {}
                
                result = {}
                for q in parsed_query['queries']:
                    matches = self._find_matching_documents(cursor, q, options)
                    for doc_id, doc_data in matches.items():
                        if doc_id in result:
                            result[doc_id]['score'] += doc_data['score']
                            result[doc_id]['highlights'].extend(doc_data['highlights'])
                        else:
                            result[doc_id] = doc_data
                
                return result
        elif parsed_query.get('type') == 'not':
            # NOT query
            all_docs = self._get_all_docs(cursor, options)
            exclude_docs = self._find_matching_documents(cursor, parsed_query['query'], options)
            
            # Remove excluded docs
            for doc_id in exclude_docs:
                if doc_id in all_docs:
                    del all_docs[doc_id]
            
            return all_docs
        
        return {}
    
    def _find_term_matches(self, cursor: sqlite3.Cursor, term: str, 
                          options: SearchOptions) -> Dict[str, Dict[str, Any]]:
        """
        Find documents matching a term query.
        
        Args:
            cursor: Database cursor
            term: Search term
            options: Search options
            
        Returns:
            Dictionary of matching documents with scores and highlights
        """
        # Normalize term (same processing as in the indexer)
        term = term.lower()
        term = self.indexer._simple_stem(term)
        
        # Initialize result
        matching_docs = {}
        
        # Search for exact matches
        sql = '''
        SELECT t.doc_id, t.field, t.frequency, d.content, d.title
        FROM terms t
        JOIN documents d ON t.doc_id = d.doc_id
        WHERE t.term = ?
        '''
        
        # Filter by source if specified
        params = [term]
        if options.source != SearchSource.ALL:
            sql += ' AND d.source = ?'
            params.append(options.source.value)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Process exact matches
        for row in rows:
            doc_id = row['doc_id']
            field = row['field']
            frequency = row['frequency']
            
            # Calculate TF-IDF score
            score = self._calculate_tfidf(term, frequency, field)
            
            # Generate highlight
            content = row['content'] if row['content'] else ''
            title = row['title'] if row['title'] else ''
            highlight = self._generate_highlight(term, content)
            
            # Add to results
            if doc_id not in matching_docs:
                matching_docs[doc_id] = {'score': score, 'highlights': [highlight] if highlight else []}
            else:
                matching_docs[doc_id]['score'] += score
                if highlight:
                    matching_docs[doc_id]['highlights'].append(highlight)
        
        # If fuzzy matching is enabled and no exact matches, try fuzzy matches
        if options.fuzzy and not matching_docs:
            fuzzy_matches = self._find_fuzzy_matches(cursor, term, options)
            matching_docs.update(fuzzy_matches)
        
        return matching_docs
    
    def _find_phrase_matches(self, cursor: sqlite3.Cursor, phrase: str, 
                           options: SearchOptions) -> Dict[str, Dict[str, Any]]:
        """
        Find documents matching a phrase query.
        
        Args:
            cursor: Database cursor
            phrase: Search phrase
            options: Search options
            
        Returns:
            Dictionary of matching documents with scores and highlights
        """
        # Split phrase into terms
        terms = phrase.lower().split()
        if not terms:
            return {}
        
        # Search for the first term to narrow down candidates
        first_term = self.indexer._simple_stem(terms[0])
        candidates = self._find_term_matches(cursor, first_term, options)
        
        # If no matches for first term, no matches for the phrase
        if not candidates:
            return {}
        
        # For each candidate document, check if it contains the full phrase
        matching_docs = {}
        
        for doc_id, doc_data in candidates.items():
            # Get document content
            cursor.execute('SELECT content FROM documents WHERE doc_id = ?', (doc_id,))
            row = cursor.fetchone()
            if not row or not row['content']:
                continue
            
            content = row['content'].lower()
            
            # Check if the full phrase is in the content
            if phrase.lower() in content:
                # Calculate score (higher for phrases)
                score = doc_data['score'] * len(terms)  # Boost for phrases
                
                # Generate highlight
                highlight = self._generate_highlight(phrase, content)
                
                matching_docs[doc_id] = {
                    'score': score,
                    'highlights': [highlight] if highlight else []
                }
        
        return matching_docs
    
    def _find_field_matches(self, cursor: sqlite3.Cursor, field: str, value: str,
                          options: SearchOptions) -> Dict[str, Dict[str, Any]]:
        """
        Find documents matching a field-specific query.
        
        Args:
            cursor: Database cursor
            field: Field name
            value: Field value
            options: Search options
            
        Returns:
            Dictionary of matching documents with scores and highlights
        """
        # Normalize value
        value = value.lower()
        value = self.indexer._simple_stem(value)
        
        # Initialize result
        matching_docs = {}
        
        # Search for exact field matches
        sql = '''
        SELECT t.doc_id, t.frequency, d.content, d.title
        FROM terms t
        JOIN documents d ON t.doc_id = d.doc_id
        WHERE t.term = ? AND t.field = ?
        '''
        
        # Adjust field name if it's a special case
        db_field = field
        if field in ['title', 'content']:
            db_field = field
        else:
            # Assume it's a metadata field
            db_field = f"metadata.{field}"
        
        # Filter by source if specified
        params = [value, db_field]
        if options.source != SearchSource.ALL:
            sql += ' AND d.source = ?'
            params.append(options.source.value)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Process matches
        for row in rows:
            doc_id = row['doc_id']
            frequency = row['frequency']
            
            # Calculate TF-IDF score with field boost
            score = self._calculate_tfidf(value, frequency, db_field)
            
            # Field-specific boosts
            if db_field == 'title':
                score *= 2.0  # Title matches are more important
            elif db_field.startswith('metadata.'):
                score *= 1.5  # Metadata matches get a boost
            
            # Generate highlight from appropriate content
            content = row['content'] if row['content'] else ''
            title = row['title'] if row['title'] else ''
            
            if db_field == 'title':
                highlight = self._generate_highlight(value, title)
            else:
                highlight = self._generate_highlight(value, content)
            
            # Add to results
            if doc_id not in matching_docs:
                matching_docs[doc_id] = {'score': score, 'highlights': [highlight] if highlight else []}
            else:
                matching_docs[doc_id]['score'] += score
                if highlight and highlight not in matching_docs[doc_id]['highlights']:
                    matching_docs[doc_id]['highlights'].append(highlight)
        
        return matching_docs
    
    def _find_fuzzy_matches(self, cursor: sqlite3.Cursor, term: str, 
                           options: SearchOptions) -> Dict[str, Dict[str, Any]]:
        """
        Find documents with fuzzy matching of the term.
        
        Args:
            cursor: Database cursor
            term: Search term
            options: Search options
            
        Returns:
            Dictionary of matching documents with scores and highlights
        """
        # Get all terms from the index
        sql = 'SELECT DISTINCT term FROM terms'
        cursor.execute(sql)
        all_terms = [row['term'] for row in cursor.fetchall()]
        
        # Find similar terms using fuzzywuzzy
        matches = process.extractBests(
            term, 
            all_terms, 
            scorer=fuzz.token_sort_ratio, 
            score_cutoff=options.fuzzy_threshold,
            limit=10
        )
        
        # Initialize result
        matching_docs = {}
        
        # Search for each similar term
        for similar_term, similarity in matches:
            # Skip the exact term (already handled by exact matching)
            if similar_term == term:
                continue
            
            # Adjust similarity to be between 0 and 1
            similarity_factor = similarity / 100.0
            
            # Find documents with this term
            sql = '''
            SELECT t.doc_id, t.field, t.frequency, d.content, d.title
            FROM terms t
            JOIN documents d ON t.doc_id = d.doc_id
            WHERE t.term = ?
            '''
            
            # Filter by source if specified
            params = [similar_term]
            if options.source != SearchSource.ALL:
                sql += ' AND d.source = ?'
                params.append(options.source.value)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # Process matches
            for row in rows:
                doc_id = row['doc_id']
                field = row['field']
                frequency = row['frequency']
                
                # Calculate TF-IDF score, adjusted by similarity
                score = self._calculate_tfidf(similar_term, frequency, field) * similarity_factor
                
                # Generate highlight
                content = row['content'] if row['content'] else ''
                highlight = self._generate_highlight(similar_term, content)
                if highlight:
                    highlight = f"Fuzzy match '{similar_term}' ({similarity}%): {highlight}"
                
                # Add to results
                if doc_id not in matching_docs:
                    matching_docs[doc_id] = {'score': score, 'highlights': [highlight] if highlight else []}
                else:
                    matching_docs[doc_id]['score'] += score
                    if highlight:
                        matching_docs[doc_id]['highlights'].append(highlight)
        
        return matching_docs
    
    def _get_all_docs(self, cursor: sqlite3.Cursor, options: SearchOptions) -> Dict[str, Dict[str, Any]]:
        """
        Get all documents in the index.
        
        Args:
            cursor: Database cursor
            options: Search options
            
        Returns:
            Dictionary of all documents with minimal scores
        """
        sql = 'SELECT doc_id FROM documents'
        params = []
        
        # Filter by source if specified
        if options.source != SearchSource.ALL:
            sql += ' WHERE source = ?'
            params.append(options.source.value)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Create minimal document data
        result = {}
        for row in rows:
            doc_id = row['doc_id']
            result[doc_id] = {'score': 0.1, 'highlights': []}
        
        return result
    
    def _calculate_tfidf(self, term: str, term_frequency: int, field: str) -> float:
        """
        Calculate TF-IDF score for a term in a document.
        
        Args:
            term: Term
            term_frequency: Term frequency in document
            field: Field name
            
        Returns:
            TF-IDF score
        """
        # Term frequency component
        tf = 1 + math.log(term_frequency) if term_frequency > 0 else 0
        
        # Inverse document frequency component
        idf = self._get_idf(term)
        
        # Field boost
        field_boost = 1.0
        if field == 'title':
            field_boost = 2.0
        elif field.startswith('metadata.'):
            field_boost = 1.5
        
        return tf * idf * field_boost
    
    @lru_cache(maxsize=1000)
    def _get_idf(self, term: str) -> float:
        """
        Get inverse document frequency for a term.
        
        Args:
            term: Term to get IDF for
            
        Returns:
            IDF value
        """
        try:
            conn = sqlite3.connect(self.index_path)
            cursor = conn.cursor()
            
            # Count documents containing the term
            cursor.execute(
                'SELECT COUNT(DISTINCT doc_id) FROM terms WHERE term = ?',
                (term,)
            )
            doc_count = cursor.fetchone()[0]
            
            conn.close()
            
            # Calculate IDF
            if doc_count == 0:
                return 0
            
            return math.log(self.total_documents / doc_count)
            
        except Exception as e:
            logger.error(f"Error calculating IDF: {e}")
            return 0
    
    def _generate_highlight(self, term: str, content: str, context_size: int = 40) -> Optional[str]:
        """
        Generate a highlighted snippet containing the search term.
        
        Args:
            term: Search term
            content: Document content
            context_size: Number of characters of context on each side
            
        Returns:
            Highlighted snippet or None if term not found
        """
        if not content:
            return None
        
        # Find term position (case-insensitive)
        content_lower = content.lower()
        term_lower = term.lower()
        
        term_pos = content_lower.find(term_lower)
        if term_pos == -1:
            # Try fuzzy matching if exact match not found
            matches = difflib.get_close_matches(term_lower, content_lower.split(), n=1, cutoff=0.8)
            if matches:
                match = matches[0]
                term_pos = content_lower.find(match)
        
        if term_pos == -1:
            return None
        
        # Extract context
        start = max(0, term_pos - context_size)
        end = min(len(content), term_pos + len(term) + context_size)
        
        # Create snippet
        snippet = content[start:end]
        
        # Add ellipsis if we truncated the text
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def _truncate_content(self, content: str, max_length: int = 200) -> str:
        """
        Truncate content to the specified maximum length.
        
        Args:
            content: Content to truncate
            max_length: Maximum length
            
        Returns:
            Truncated content
        """
        if not content:
            return ""
        
        if len(content) <= max_length:
            return content
        
        # Truncate at word boundary
        truncated = content[:max_length]
        last_space = truncated.rfind(' ')
        
        if last_space > 0:
            truncated = truncated[:last_space]
        
        return truncated + "..."
    
    def _generate_facets(self, results: List[SearchResult], facet_fields: List[str]) -> Dict[str, SearchFacet]:
        """
        Generate facets from search results.
        
        Args:
            results: Search results
            facet_fields: List of fields to generate facets for
            
        Returns:
            Dictionary of facets
        """
        facets = {}
        
        for field in facet_fields:
            values_count = defaultdict(int)
            
            for result in results:
                if field == 'type':
                    values_count[result.result_type.value] += 1
                elif field == 'source':
                    values_count[result.source.value] += 1
                elif field == 'date' and result.date:
                    # Group by year
                    year = result.date.year
                    values_count[str(year)] += 1
                elif field.startswith('metadata.') and field[9:] in result.metadata:
                    # Metadata field
                    field_name = field[9:]
                    value = result.metadata[field_name]
                    
                    # Convert to string for consistency
                    if isinstance(value, (list, dict)):
                        continue  # Skip complex values
                    
                    str_value = str(value)
                    values_count[str_value] += 1
            
            # Create facet
            facets[field] = SearchFacet(
                name=field,
                values=dict(values_count)
            )
        
        return facets
    
    def reindex_newspaper_repository(self) -> None:
        """Reindex all content from the newspaper repository."""
        try:
            # Connect to newspaper repository database
            conn = sqlite3.connect(self.newspaper_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all newspaper pages
            cursor.execute('SELECT * FROM newspaper_pages')
            pages = cursor.fetchall()
            
            # Index pages
            for page in pages:
                page_id = page['page_id']
                page_data = dict(page)
                self.indexer.index_newspaper_page(page_id, page_data)
                
                # Get segments for this page
                cursor.execute('SELECT * FROM article_segments WHERE page_id = ?', (page_id,))
                segments = cursor.fetchall()
                
                # Index segments
                for segment in segments:
                    segment_id = segment['segment_id']
                    segment_data = dict(segment)
                    self.indexer.index_article_segment(segment_id, segment_data, page_data)
            
            # Get newspaper articles
            cursor.execute('SELECT * FROM newspaper_articles')
            articles = cursor.fetchall()
            
            # Index articles
            for article in articles:
                article_id = article['article_id']
                article_data = dict(article)
                
                # Get parent page data
                page_id = article_data.get('page_id')
                page_data = None
                
                if page_id:
                    cursor.execute('SELECT * FROM newspaper_pages WHERE page_id = ?', (page_id,))
                    page_row = cursor.fetchone()
                    if page_row:
                        page_data = dict(page_row)
                
                self.indexer.index_newspaper_article(article_id, article_data, page_data)
            
            conn.close()
            
            logger.info("Reindexed newspaper repository")
            
        except Exception as e:
            logger.error(f"Error reindexing newspaper repository: {e}")
            raise
    
    def reindex_main_database(self) -> None:
        """Reindex all content from the main database."""
        try:
            # Connect to main database
            conn = sqlite3.connect(self.main_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all sources from main database
            cursor.execute('SELECT * FROM sources')
            sources = cursor.fetchall()
            
            # Index sources
            for source in sources:
                source_id = source['source_id']
                source_data = dict(source)
                self.indexer.index_main_source(source_id, source_data)
            
            # Get all events from main database
            cursor.execute('SELECT * FROM events')
            events = cursor.fetchall()
            
            # Index events
            for event in events:
                event_id = event['event_id']
                event_data = dict(event)
                self.indexer.index_main_event(event_id, event_data)
            
            conn.close()
            
            logger.info("Reindexed main database")
            
        except Exception as e:
            logger.error(f"Error reindexing main database: {e}")
            raise
    
    def reindex_all(self) -> None:
        """Reindex all content from both repositories."""
        # Reindex newspaper repository
        self.reindex_newspaper_repository()
        
        # Reindex main database
        self.reindex_main_database()
        
        # Optimize index
        self.indexer.optimize_index()
        
        # Update total document count
        self.total_documents = self._count_total_documents()
        
        logger.info(f"Reindexed all content, total documents: {self.total_documents}")


# UI Integration Helper Functions

def create_search_widget(parent):
    """
    Create a widget for searching the repository.
    
    Args:
        parent: Parent widget
        
    Returns:
        QWidget with search controls
    """
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QLabel, QLineEdit, QComboBox, QCheckBox, 
                                QGridLayout, QGroupBox, QTextEdit, QListWidget,
                                QListWidgetItem, QDateEdit, QSplitter, QScrollArea)
    from PyQt5.QtCore import Qt, QDate
    
    search_widget = QWidget(parent)
    main_layout = QVBoxLayout(search_widget)
    
    # Search box
    search_layout = QHBoxLayout()
    search_layout.addWidget(QLabel("Search:"))
    
    search_box = QLineEdit()
    search_box.setPlaceholderText("Enter search terms (supports AND, OR, NOT, \"phrases\", field:value)")
    search_layout.addWidget(search_box)
    
    search_button = QPushButton("Search")
    search_layout.addWidget(search_button)
    
    main_layout.addLayout(search_layout)
    
    # Options
    options_group = QGroupBox("Search Options")
    options_layout = QGridLayout()
    
    # Source selection
    source_label = QLabel("Search in:")
    source_combo = QComboBox()
    source_combo.addItems(["All Repositories", "Newspaper Repository", "Main Database"])
    
    # Date range
    date_label = QLabel("Date range:")
    date_start = QDateEdit()
    date_start.setDate(QDate(1800, 1, 1))
    date_start.setCalendarPopup(True)
    date_end = QDateEdit()
    date_end.setDate(QDate.currentDate())
    date_end.setCalendarPopup(True)
    
    # Fuzzy matching
    fuzzy_check = QCheckBox("Enable fuzzy matching")
    fuzzy_check.setChecked(True)
    
    # Add to layout
    options_layout.addWidget(source_label, 0, 0)
    options_layout.addWidget(source_combo, 0, 1)
    options_layout.addWidget(date_label, 1, 0)
    
    date_layout = QHBoxLayout()
    date_layout.addWidget(date_start)
    date_layout.addWidget(QLabel("to"))
    date_layout.addWidget(date_end)
    
    options_layout.addLayout(date_layout, 1, 1)
    options_layout.addWidget(fuzzy_check, 2, 0, 1, 2)
    
    options_group.setLayout(options_layout)
    main_layout.addWidget(options_group)
    
    # Results and facets in a splitter
    splitter = QSplitter(Qt.Horizontal)
    
    # Facets panel
    facets_widget = QWidget()
    facets_layout = QVBoxLayout(facets_widget)
    facets_layout.addWidget(QLabel("<b>Filters</b>"))
    
    facets_list = QListWidget()
    facets_layout.addWidget(facets_list)
    
    # Results panel
    results_widget = QWidget()
    results_layout = QVBoxLayout(results_widget)
    
    results_header = QHBoxLayout()
    results_count = QLabel("0 results")
    results_header.addWidget(results_count)
    results_header.addStretch()
    
    results_layout.addLayout(results_header)
    
    results_list = QListWidget()
    results_layout.addWidget(results_list)
    
    # Preview panel
    preview_widget = QWidget()
    preview_layout = QVBoxLayout(preview_widget)
    preview_layout.addWidget(QLabel("<b>Document Preview</b>"))
    
    preview_text = QTextEdit()
    preview_text.setReadOnly(True)
    preview_layout.addWidget(preview_text)
    
    # Add widgets to splitter
    splitter.addWidget(facets_widget)
    
    # Results and preview in a vertical splitter
    results_splitter = QSplitter(Qt.Vertical)
    results_splitter.addWidget(results_widget)
    results_splitter.addWidget(preview_widget)
    results_splitter.setSizes([500, 300])
    
    splitter.addWidget(results_splitter)
    
    # Set sizes (30% for facets, 70% for results)
    splitter.setSizes([300, 700])
    
    main_layout.addWidget(splitter)
    
    return search_widget