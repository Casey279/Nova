"""
Search Engine for the Newspaper Repository System.

This module provides advanced search capabilities for the newspaper repository,
including full-text search, faceted search, and entity-based search.
"""

import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('search_engine')


class SearchError(Exception):
    """Exception raised for search engine errors."""
    pass


class SearchEngine:
    """
    Search engine for the newspaper repository system.
    
    Provides advanced search capabilities for articles, publications, and entities.
    """
    
    def __init__(self, db_manager):
        """
        Initialize the search engine.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        
        # Ensure FTS tables are set up
        self._ensure_fts_tables()
    
    def _ensure_fts_tables(self) -> None:
        """Ensure FTS tables are set up for fulltext search."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if FTS tables exist
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='ArticlesFTS'"
                )
                if not cursor.fetchone():
                    # Create FTS table for Articles
                    cursor.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS ArticlesFTS USING fts5(
                            id,
                            title,
                            text,
                            content='Articles',
                            content_rowid='id',
                            tokenize='porter unicode61'
                        )
                        """
                    )
                    
                    # Create triggers to keep FTS table in sync
                    cursor.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS Articles_ai AFTER INSERT ON Articles
                        BEGIN
                            INSERT INTO ArticlesFTS(rowid, id, title, text)
                            VALUES (new.id, new.id, new.title, new.text);
                        END
                        """
                    )
                    
                    cursor.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS Articles_ad AFTER DELETE ON Articles
                        BEGIN
                            INSERT INTO ArticlesFTS(ArticlesFTS, rowid, id, title, text)
                            VALUES ('delete', old.id, old.id, old.title, old.text);
                        END
                        """
                    )
                    
                    cursor.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS Articles_au AFTER UPDATE ON Articles
                        BEGIN
                            INSERT INTO ArticlesFTS(ArticlesFTS, rowid, id, title, text)
                            VALUES ('delete', old.id, old.id, old.title, old.text);
                            INSERT INTO ArticlesFTS(rowid, id, title, text)
                            VALUES (new.id, new.id, new.title, new.text);
                        END
                        """
                    )
                    
                    # Populate FTS table with existing data
                    cursor.execute(
                        """
                        INSERT INTO ArticlesFTS(rowid, id, title, text)
                        SELECT id, id, title, text FROM Articles
                        WHERE text IS NOT NULL AND text != ''
                        """
                    )
                    
                    logger.info("Created FTS tables and triggers for fulltext search")
                
                # Check if entity FTS table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='EntitiesFTS'"
                )
                if not cursor.fetchone():
                    # Create FTS table for Entities
                    cursor.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS EntitiesFTS USING fts5(
                            id,
                            name,
                            description,
                            notes,
                            content='Entities',
                            content_rowid='id',
                            tokenize='porter unicode61'
                        )
                        """
                    )
                    
                    # Create triggers to keep FTS table in sync
                    cursor.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS Entities_ai AFTER INSERT ON Entities
                        BEGIN
                            INSERT INTO EntitiesFTS(rowid, id, name, description, notes)
                            VALUES (new.id, new.id, new.name, new.description, new.notes);
                        END
                        """
                    )
                    
                    cursor.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS Entities_ad AFTER DELETE ON Entities
                        BEGIN
                            INSERT INTO EntitiesFTS(EntitiesFTS, rowid, id, name, description, notes)
                            VALUES ('delete', old.id, old.id, old.name, old.description, old.notes);
                        END
                        """
                    )
                    
                    cursor.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS Entities_au AFTER UPDATE ON Entities
                        BEGIN
                            INSERT INTO EntitiesFTS(EntitiesFTS, rowid, id, name, description, notes)
                            VALUES ('delete', old.id, old.id, old.name, old.description, old.notes);
                            INSERT INTO EntitiesFTS(rowid, id, name, description, notes)
                            VALUES (new.id, new.id, new.name, new.description, new.notes);
                        END
                        """
                    )
                    
                    # Populate FTS table with existing data
                    cursor.execute(
                        """
                        INSERT INTO EntitiesFTS(rowid, id, name, description, notes)
                        SELECT id, id, name, description, notes FROM Entities
                        """
                    )
                    
                    logger.info("Created Entity FTS tables and triggers for fulltext search")
                
        except Exception as e:
            logger.error(f"Failed to ensure FTS tables: {str(e)}")
            raise SearchError(f"Failed to ensure FTS tables: {str(e)}")
    
    def rebuild_search_index(self) -> Dict:
        """
        Rebuild the search index.
        
        Returns:
            Dictionary with rebuild results
        """
        try:
            start_time = time.time()
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Rebuild ArticlesFTS
                cursor.execute("DELETE FROM ArticlesFTS")
                
                cursor.execute(
                    """
                    INSERT INTO ArticlesFTS(rowid, id, title, text)
                    SELECT id, id, title, text FROM Articles
                    WHERE text IS NOT NULL AND text != ''
                    """
                )
                articles_count = cursor.rowcount
                
                # Rebuild EntitiesFTS
                cursor.execute("DELETE FROM EntitiesFTS")
                
                cursor.execute(
                    """
                    INSERT INTO EntitiesFTS(rowid, id, name, description, notes)
                    SELECT id, id, name, description, notes FROM Entities
                    """
                )
                entities_count = cursor.rowcount
                
                # Optimize FTS tables
                cursor.execute("INSERT INTO ArticlesFTS(ArticlesFTS) VALUES('optimize')")
                cursor.execute("INSERT INTO EntitiesFTS(EntitiesFTS) VALUES('optimize')")
                
            execution_time = time.time() - start_time
            
            logger.info(
                f"Rebuilt search index in {execution_time:.2f} seconds "
                f"({articles_count} articles, {entities_count} entities)"
            )
            
            return {
                'articles': articles_count,
                'entities': entities_count,
                'execution_time': execution_time
            }
            
        except Exception as e:
            logger.error(f"Failed to rebuild search index: {str(e)}")
            raise SearchError(f"Failed to rebuild search index: {str(e)}")
    
    def search_articles(
        self,
        query: str,
        publication_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        region_id: Optional[int] = None,
        entity_id: Optional[int] = None,
        page_number: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = 'relevance',
        include_snippet: bool = True,
        snippet_size: int = 200
    ) -> List[Dict]:
        """
        Search for articles using full-text search.
        
        Args:
            query: Search query
            publication_id: Optional publication filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            region_id: Optional region filter
            entity_id: Optional entity filter
            page_number: Optional page number filter
            limit: Maximum number of results
            offset: Result offset for pagination
            sort_by: Sort order ('relevance', 'date_asc', 'date_desc')
            include_snippet: Whether to include a text snippet
            snippet_size: Size of text snippet in characters
            
        Returns:
            List of matching article dictionaries
        """
        try:
            # Clean and process the query
            processed_query = self._process_search_query(query)
            
            if not processed_query:
                raise SearchError("Invalid search query")
            
            # Build the query
            fts_query = f"""
                SELECT 
                    a.id, a.title, a.text, a.published_date, a.page_number,
                    i.date as issue_date, i.id as issue_id,
                    p.id as publication_id, p.title as publication_title,
                    r.name as region_name
            """
            
            # Add snippet if requested
            if include_snippet:
                fts_query += f"""
                    , highlight(ArticlesFTS, 0, '<mark>', '</mark>') as title_highlight,
                    highlight(ArticlesFTS, 2, '<mark>', '</mark>') as text_highlight,
                    snippet(ArticlesFTS, 2, '<mark>', '</mark>', '...', 5) as snippet
                """
            
            # Add base tables
            fts_query += f"""
                FROM ArticlesFTS
                JOIN Articles a ON ArticlesFTS.id = a.id
                JOIN Issues i ON a.issue_id = i.id
                JOIN Publications p ON i.publication_id = p.id
                LEFT JOIN Regions r ON p.region_id = r.id
            """
            
            # Add entity join if filtering by entity
            if entity_id:
                fts_query += f"""
                    JOIN EntityMentions em ON a.id = em.article_id
                """
            
            # Add WHERE clause
            where_clauses = [f"ArticlesFTS MATCH ?"]
            params = [processed_query]
            
            if publication_id:
                where_clauses.append("p.id = ?")
                params.append(publication_id)
            
            if start_date:
                where_clauses.append("i.date >= ?")
                params.append(start_date.strftime("%Y-%m-%d"))
            
            if end_date:
                where_clauses.append("i.date <= ?")
                params.append(end_date.strftime("%Y-%m-%d"))
            
            if region_id:
                where_clauses.append("p.region_id = ?")
                params.append(region_id)
            
            if entity_id:
                where_clauses.append("em.entity_id = ?")
                params.append(entity_id)
            
            if page_number:
                where_clauses.append("a.page_number = ?")
                params.append(page_number)
            
            fts_query += " WHERE " + " AND ".join(where_clauses)
            
            # Add sorting
            if sort_by == 'date_asc':
                fts_query += " ORDER BY i.date ASC, a.page_number ASC"
            elif sort_by == 'date_desc':
                fts_query += " ORDER BY i.date DESC, a.page_number ASC"
            else:  # Default to relevance
                fts_query += " ORDER BY rank"
            
            # Add pagination
            fts_query += " LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)
            
            # Execute query
            with self.db_manager.get_connection() as conn:
                conn.create_function("highlight", 3, self._highlight_match)
                conn.create_function("snippet", 5, self._create_snippet)
                
                cursor = conn.cursor()
                cursor.execute(fts_query, params)
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                articles = []
                for row in results:
                    article = dict(row)
                    
                    # Process snippet if included
                    if include_snippet and 'snippet' in article:
                        if not article['snippet']:
                            # Create a default snippet from the text
                            text = article['text']
                            if text and len(text) > snippet_size:
                                # Find the first match or use the beginning
                                match_pos = -1
                                for term in processed_query.split():
                                    if term.startswith('"') and term.endswith('"'):
                                        term = term[1:-1].lower()
                                    else:
                                        term = term.lower()
                                    
                                    pos = text.lower().find(term)
                                    if pos >= 0:
                                        match_pos = pos
                                        break
                                
                                if match_pos >= 0:
                                    start = max(0, match_pos - snippet_size // 2)
                                    end = min(len(text), start + snippet_size)
                                    snippet = text[start:end]
                                    
                                    if start > 0:
                                        snippet = "..." + snippet
                                    if end < len(text):
                                        snippet += "..."
                                else:
                                    # No match found, use beginning
                                    snippet = text[:snippet_size] + "..."
                                
                                article['snippet'] = snippet
                            else:
                                article['snippet'] = text
                    
                    articles.append(article)
                
                return articles
            
        except Exception as e:
            logger.error(f"Failed to search articles: {str(e)}")
            raise SearchError(f"Failed to search articles: {str(e)}")
    
    def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_article_count: bool = True
    ) -> List[Dict]:
        """
        Search for entities using full-text search.
        
        Args:
            query: Search query
            entity_type: Optional entity type filter
            limit: Maximum number of results
            offset: Result offset for pagination
            include_article_count: Whether to include article count
            
        Returns:
            List of matching entity dictionaries
        """
        try:
            # Clean and process the query
            processed_query = self._process_search_query(query)
            
            if not processed_query:
                raise SearchError("Invalid search query")
            
            # Build the query
            fts_query = f"""
                SELECT 
                    e.id, e.name, e.description, e.notes,
                    et.name as entity_type
            """
            
            # Add article count if requested
            if include_article_count:
                fts_query += f"""
                    , (SELECT COUNT(*) FROM EntityMentions em WHERE em.entity_id = e.id) as article_count
                """
            
            # Add base tables
            fts_query += f"""
                FROM EntitiesFTS
                JOIN Entities e ON EntitiesFTS.id = e.id
                JOIN EntityTypes et ON e.type_id = et.id
            """
            
            # Add WHERE clause
            where_clauses = [f"EntitiesFTS MATCH ?"]
            params = [processed_query]
            
            if entity_type:
                where_clauses.append("et.name = ?")
                params.append(entity_type)
            
            fts_query += " WHERE " + " AND ".join(where_clauses)
            
            # Add sorting by relevance
            fts_query += " ORDER BY rank"
            
            # Add pagination
            fts_query += " LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)
            
            # Execute query
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(fts_query, params)
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                entities = [dict(row) for row in results]
                
                return entities
            
        except Exception as e:
            logger.error(f"Failed to search entities: {str(e)}")
            raise SearchError(f"Failed to search entities: {str(e)}")
    
    def get_related_entities(
        self, 
        article_id: str,
        min_count: int = 1,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get entities related to an article.
        
        Args:
            article_id: Article ID
            min_count: Minimum mention count
            limit: Maximum number of results
            
        Returns:
            List of entity dictionaries with mention counts
        """
        try:
            query = f"""
                SELECT 
                    e.id, e.name, e.description, et.name as entity_type,
                    em.count, em.context
                FROM EntityMentions em
                JOIN Entities e ON em.entity_id = e.id
                JOIN EntityTypes et ON e.type_id = et.id
                WHERE em.article_id = ? AND em.count >= ?
                ORDER BY em.count DESC
                LIMIT ?
            """
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (article_id, min_count, limit))
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                entities = [dict(row) for row in results]
                
                return entities
            
        except Exception as e:
            logger.error(f"Failed to get related entities: {str(e)}")
            raise SearchError(f"Failed to get related entities: {str(e)}")
    
    def get_related_articles(
        self, 
        article_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get articles related to an article based on shared entities.
        
        Args:
            article_id: Article ID
            limit: Maximum number of results
            
        Returns:
            List of related article dictionaries
        """
        try:
            query = f"""
                SELECT 
                    a.id, a.title, a.published_date, a.page_number,
                    i.date as issue_date,
                    p.id as publication_id, p.title as publication_title,
                    COUNT(DISTINCT em2.entity_id) as shared_entities
                FROM Articles a
                JOIN Issues i ON a.issue_id = i.id
                JOIN Publications p ON i.publication_id = p.id
                JOIN EntityMentions em1 ON em1.article_id = ?
                JOIN EntityMentions em2 ON em2.entity_id = em1.entity_id AND em2.article_id = a.id
                WHERE a.id != ?
                GROUP BY a.id
                ORDER BY shared_entities DESC, i.date DESC
                LIMIT ?
            """
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (article_id, article_id, limit))
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                articles = [dict(row) for row in results]
                
                return articles
            
        except Exception as e:
            logger.error(f"Failed to get related articles: {str(e)}")
            raise SearchError(f"Failed to get related articles: {str(e)}")
    
    def get_entity_timeline(
        self, 
        entity_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get a timeline of articles mentioning an entity.
        
        Args:
            entity_id: Entity ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
            
        Returns:
            List of article dictionaries sorted by date
        """
        try:
            query = f"""
                SELECT 
                    a.id, a.title, a.page_number,
                    i.date as issue_date,
                    p.id as publication_id, p.title as publication_title,
                    em.count, em.context
                FROM EntityMentions em
                JOIN Articles a ON em.article_id = a.id
                JOIN Issues i ON a.issue_id = i.id
                JOIN Publications p ON i.publication_id = p.id
                WHERE em.entity_id = ?
            """
            
            params = [entity_id]
            
            if start_date:
                query += " AND i.date >= ?"
                params.append(start_date.strftime("%Y-%m-%d"))
            
            if end_date:
                query += " AND i.date <= ?"
                params.append(end_date.strftime("%Y-%m-%d"))
            
            query += " ORDER BY i.date ASC, a.page_number ASC LIMIT ?"
            params.append(limit)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                timeline = [dict(row) for row in results]
                
                return timeline
            
        except Exception as e:
            logger.error(f"Failed to get entity timeline: {str(e)}")
            raise SearchError(f"Failed to get entity timeline: {str(e)}")
    
    def get_entity_co_occurrences(
        self, 
        entity_id: int,
        min_count: int = 2,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get entities that co-occur with the given entity.
        
        Args:
            entity_id: Entity ID
            min_count: Minimum co-occurrence count
            limit: Maximum number of results
            
        Returns:
            List of entity dictionaries with co-occurrence counts
        """
        try:
            query = f"""
                SELECT 
                    e.id, e.name, e.description, et.name as entity_type,
                    COUNT(DISTINCT em2.article_id) as co_occurrence_count
                FROM Entities e
                JOIN EntityTypes et ON e.type_id = et.id
                JOIN EntityMentions em1 ON em1.entity_id = ?
                JOIN EntityMentions em2 ON em2.article_id = em1.article_id AND em2.entity_id = e.id
                WHERE e.id != ?
                GROUP BY e.id
                HAVING co_occurrence_count >= ?
                ORDER BY co_occurrence_count DESC
                LIMIT ?
            """
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (entity_id, entity_id, min_count, limit))
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                co_occurrences = [dict(row) for row in results]
                
                return co_occurrences
            
        except Exception as e:
            logger.error(f"Failed to get entity co-occurrences: {str(e)}")
            raise SearchError(f"Failed to get entity co-occurrences: {str(e)}")
    
    def get_trending_topics(
        self, 
        days: int = 30,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get trending topics based on entity mention frequency.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of results
            
        Returns:
            List of entity dictionaries with mention counts
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            query = f"""
                SELECT 
                    e.id, e.name, e.description, et.name as entity_type,
                    COUNT(em.id) as mention_count,
                    COUNT(DISTINCT em.article_id) as article_count
                FROM EntityMentions em
                JOIN Entities e ON em.entity_id = e.id
                JOIN EntityTypes et ON e.type_id = et.id
                JOIN Articles a ON em.article_id = a.id
                JOIN Issues i ON a.issue_id = i.id
                WHERE i.date >= ?
                GROUP BY e.id
                ORDER BY mention_count DESC
                LIMIT ?
            """
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (start_date.strftime("%Y-%m-%d"), limit))
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                trending = [dict(row) for row in results]
                
                return trending
            
        except Exception as e:
            logger.error(f"Failed to get trending topics: {str(e)}")
            raise SearchError(f"Failed to get trending topics: {str(e)}")
    
    def get_search_suggestions(
        self, 
        query: str,
        limit: int = 10
    ) -> List[str]:
        """
        Get search suggestions based on partial query.
        
        Args:
            query: Partial search query
            limit: Maximum number of suggestions
            
        Returns:
            List of search suggestions
        """
        try:
            if not query or len(query) < 2:
                return []
            
            # Clean the query
            clean_query = re.sub(r'[^\w\s]', '', query).strip().lower()
            
            if not clean_query:
                return []
            
            # Add wildcard for prefix search
            search_term = f"{clean_query}*"
            
            # Search in articles
            article_query = f"""
                SELECT DISTINCT term
                FROM (
                    SELECT title as term FROM Articles
                    WHERE title LIKE ?
                    UNION
                    SELECT DISTINCT e.name as term
                    FROM Entities e
                    JOIN EntityMentions em ON e.id = em.entity_id
                    WHERE e.name LIKE ?
                )
                ORDER BY length(term), term
                LIMIT ?
            """
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    article_query, 
                    (f"%{clean_query}%", f"%{clean_query}%", limit)
                )
                results = cursor.fetchall()
                
                # Extract suggestions
                suggestions = [row['term'] for row in results]
                
                return suggestions
            
        except Exception as e:
            logger.error(f"Failed to get search suggestions: {str(e)}")
            return []
    
    def _process_search_query(self, query: str) -> str:
        """
        Process and clean a search query for FTS.
        
        Args:
            query: Raw search query
            
        Returns:
            Processed query
        """
        if not query or not query.strip():
            return ""
        
        # Remove special characters but keep quotes for phrase searches
        query = query.strip()
        
        # Handle phrase searches (quoted terms)
        phrases = re.findall(r'"([^"]*)"', query)
        for phrase in phrases:
            if phrase:
                # Keep phrases as is
                continue
            else:
                # Remove empty quotes
                query = query.replace('""', '')
        
        # Process terms outside quotes
        parts = re.split(r'"[^"]*"', query)
        for i, part in enumerate(parts):
            if part:
                # Clean up terms
                parts[i] = re.sub(r'[^\w\s]', ' ', part)
                # Handle operators
                parts[i] = re.sub(r'\bAND\b', 'AND', parts[i], flags=re.IGNORECASE)
                parts[i] = re.sub(r'\bOR\b', 'OR', parts[i], flags=re.IGNORECASE)
                parts[i] = re.sub(r'\bNOT\b', 'NOT', parts[i], flags=re.IGNORECASE)
        
        # Reconstruct the query
        result = ""
        for i in range(max(len(parts), len(phrases) + 1)):
            if i < len(parts):
                result += parts[i]
            if i < len(phrases):
                result += f'"{phrases[i]}"'
        
        # Handle wildcards
        result = re.sub(r'\*+', '*', result)
        
        # Remove any remaining special characters that might break FTS
        result = re.sub(r'[^\w\s"*ANDORT]', ' ', result)
        
        # Normalize whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def _highlight_match(self, text: str, term: str, tag: str) -> str:
        """
        Highlight search term matches in text.
        
        Args:
            text: Text to search in
            term: Term to highlight
            tag: HTML tag to use
            
        Returns:
            Text with highlighted terms
        """
        if not text or not term:
            return text
        
        close_tag = tag.replace('<', '</')
        
        # Handle phrase searches
        if term.startswith('"') and term.endswith('"'):
            phrase = term[1:-1].lower()
            parts = text.split()
            result = []
            
            i = 0
            while i < len(parts):
                if i <= len(parts) - len(phrase.split()):
                    potential_match = ' '.join(parts[i:i+len(phrase.split())]).lower()
                    if potential_match == phrase:
                        result.append(f"{tag}{' '.join(parts[i:i+len(phrase.split())])}{close_tag}")
                        i += len(phrase.split())
                    else:
                        result.append(parts[i])
                        i += 1
                else:
                    result.append(parts[i])
                    i += 1
            
            return ' '.join(result)
        
        # Handle regular term searches
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        return pattern.sub(f"{tag}\\g<0>{close_tag}", text)
    
    def _create_snippet(self, text: str, column: str, open_tag: str, close_tag: str, ellipsis: str, max_tokens: int) -> str:
        """
        Create a snippet from text.
        
        Args:
            text: Text to create snippet from
            column: Column name
            open_tag: Opening highlight tag
            close_tag: Closing highlight tag
            ellipsis: Ellipsis string
            max_tokens: Maximum number of tokens
            
        Returns:
            Text snippet
        """
        if not text:
            return ""
        
        # Simple implementation - find first occurrence of a highlight tag
        start_idx = text.find(open_tag)
        
        if start_idx == -1:
            # No match found, return beginning of text
            return text[:200] + (ellipsis if len(text) > 200 else "")
        
        # Find a good starting point before the first match
        start = max(0, start_idx - 100)
        
        # Go back to start of word
        while start > 0 and text[start].isalnum():
            start -= 1
        
        # Find a good ending point
        end = min(len(text), start_idx + 300)
        
        # Go forward to end of word
        while end < len(text) and text[end].isalnum():
            end += 1
        
        snippet = text[start:end]
        
        # Add ellipsis if truncated
        if start > 0:
            snippet = ellipsis + snippet
        if end < len(text):
            snippet = snippet + ellipsis
        
        return snippet