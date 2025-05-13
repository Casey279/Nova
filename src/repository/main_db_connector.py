"""
Database Connector for connecting the newspaper repository with the main application database.

This module provides a bridge between the newspaper repository database and the main
Nova application database, allowing data to be synchronized between the two systems.
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('main_db_connector')


class DatabaseConnectorError(Exception):
    """Exception raised for database connector errors."""
    pass


class MainDatabaseConnector:
    """
    Connector for synchronizing data between the newspaper repository and main application database.
    """
    
    def __init__(
        self, 
        repo_db_path: str,
        main_db_path: str,
        auto_connect: bool = True
    ):
        """
        Initialize the database connector.
        
        Args:
            repo_db_path: Path to the newspaper repository database
            main_db_path: Path to the main application database
            auto_connect: If True, connect to databases immediately
        """
        self.repo_db_path = os.path.abspath(repo_db_path)
        self.main_db_path = os.path.abspath(main_db_path)
        self.repo_conn = None
        self.main_conn = None
        
        if auto_connect:
            self.connect()
    
    def connect(self) -> None:
        """
        Connect to both databases.
        
        Raises:
            DatabaseConnectorError: If connection fails
        """
        try:
            # Verify database files exist
            if not os.path.exists(self.repo_db_path):
                raise DatabaseConnectorError(f"Repository database not found: {self.repo_db_path}")
            
            if not os.path.exists(self.main_db_path):
                raise DatabaseConnectorError(f"Main database not found: {self.main_db_path}")
            
            # Connect to repository database
            self.repo_conn = sqlite3.connect(
                self.repo_db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self.repo_conn.row_factory = sqlite3.Row
            
            # Enable foreign keys
            self.repo_conn.execute("PRAGMA foreign_keys = ON")
            
            # Connect to main database
            self.main_conn = sqlite3.connect(
                self.main_db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self.main_conn.row_factory = sqlite3.Row
            
            # Enable foreign keys
            self.main_conn.execute("PRAGMA foreign_keys = ON")
            
            logger.info("Connected to repository and main databases")
            
        except Exception as e:
            if isinstance(e, DatabaseConnectorError):
                raise
            raise DatabaseConnectorError(f"Failed to connect to databases: {str(e)}")
    
    def close(self) -> None:
        """Close database connections."""
        if self.repo_conn:
            self.repo_conn.close()
            self.repo_conn = None
        
        if self.main_conn:
            self.main_conn.close()
            self.main_conn = None
        
        logger.info("Closed database connections")
    
    def __enter__(self):
        """Context manager entry."""
        if not self.repo_conn or not self.main_conn:
            self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def _ensure_connected(self) -> None:
        """Ensure database connections are established."""
        if not self.repo_conn or not self.main_conn:
            self.connect()
    
    def sync_sources(self) -> Tuple[int, int, int]:
        """
        Synchronize sources (publications) from repository to main database.
        
        Returns:
            Tuple of (added, updated, total) counts
        """
        self._ensure_connected()
        
        try:
            # Begin transaction
            with self.main_conn:
                main_cursor = self.main_conn.cursor()
                
                # Check if Sources table exists in main database
                main_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Sources'"
                )
                if not main_cursor.fetchone():
                    raise DatabaseConnectorError("Sources table not found in main database")
                
                # Get existing sources from main database
                main_cursor.execute("SELECT id, name, url FROM Sources")
                existing_sources = {row['name']: dict(row) for row in main_cursor.fetchall()}
                
                # Get publications from repository
                repo_cursor = self.repo_conn.cursor()
                repo_cursor.execute(
                    """
                    SELECT p.id, p.title, p.source, p.url, r.name as location
                    FROM Publications p
                    LEFT JOIN Regions r ON p.region_id = r.id
                    """
                )
                publications = repo_cursor.fetchall()
                
                added = 0
                updated = 0
                
                # Process each publication
                for pub in publications:
                    # Convert repository publication to main source format
                    source_name = pub['title']
                    source_url = pub['url'] or ''
                    source_description = f"Newspaper: {pub['title']}"
                    if pub['location']:
                        source_description += f" ({pub['location']})"
                    
                    # Check if source already exists
                    if source_name in existing_sources:
                        # Update if URL changed
                        if existing_sources[source_name]['url'] != source_url:
                            main_cursor.execute(
                                "UPDATE Sources SET url = ?, notes = ? WHERE id = ?",
                                (source_url, source_description, existing_sources[source_name]['id'])
                            )
                            updated += 1
                    else:
                        # Add new source
                        main_cursor.execute(
                            "INSERT INTO Sources (name, url, notes) VALUES (?, ?, ?)",
                            (source_name, source_url, source_description)
                        )
                        added += 1
                
                total = len(publications)
                logger.info(f"Synchronized sources: {added} added, {updated} updated, {total} total")
                return added, updated, total
                
        except Exception as e:
            if isinstance(e, DatabaseConnectorError):
                raise
            raise DatabaseConnectorError(f"Failed to synchronize sources: {str(e)}")
    
    def sync_articles_to_documents(
        self, 
        publication_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> Tuple[int, int, int]:
        """
        Synchronize articles from repository to documents in main database.
        
        Args:
            publication_id: Optional publication ID to filter by
            start_date: Optional start date to filter by
            end_date: Optional end date to filter by
            limit: Maximum number of articles to sync
            
        Returns:
            Tuple of (added, updated, total) counts
        """
        self._ensure_connected()
        
        try:
            # Begin transaction
            with self.main_conn:
                main_cursor = self.main_conn.cursor()
                
                # Check if Documents table exists in main database
                main_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Documents'"
                )
                if not main_cursor.fetchone():
                    raise DatabaseConnectorError("Documents table not found in main database")
                
                # Get mapping of source names to IDs in main database
                main_cursor.execute("SELECT id, name FROM Sources")
                source_map = {row['name']: row['id'] for row in main_cursor.fetchall()}
                
                # Prepare query for repository articles
                query = """
                    SELECT a.id, a.title, a.text, a.published_date, a.page_number,
                           i.date as issue_date, p.title as publication_title,
                           p.id as publication_id
                    FROM Articles a
                    JOIN Issues i ON a.issue_id = i.id
                    JOIN Publications p ON i.publication_id = p.id
                    WHERE a.text IS NOT NULL AND a.text != ''
                """
                params = []
                
                if publication_id:
                    query += " AND p.id = ?"
                    params.append(publication_id)
                
                if start_date:
                    query += " AND i.date >= ?"
                    params.append(start_date.strftime('%Y-%m-%d'))
                
                if end_date:
                    query += " AND i.date <= ?"
                    params.append(end_date.strftime('%Y-%m-%d'))
                
                query += " ORDER BY i.date DESC, a.page_number"
                if limit > 0:
                    query += f" LIMIT {limit}"
                
                # Get articles from repository
                repo_cursor = self.repo_conn.cursor()
                repo_cursor.execute(query, params)
                articles = repo_cursor.fetchall()
                
                # Get existing documents with repository_id
                main_cursor.execute(
                    """
                    SELECT id, repository_id, title, content, date_modified 
                    FROM Documents
                    WHERE repository_id IS NOT NULL
                    """
                )
                existing_docs = {row['repository_id']: dict(row) for row in main_cursor.fetchall()}
                
                added = 0
                updated = 0
                
                # Process each article
                for article in articles:
                    # Skip if publication not in source map
                    if article['publication_title'] not in source_map:
                        logger.warning(
                            f"Publication not found in Sources: {article['publication_title']}"
                        )
                        continue
                    
                    source_id = source_map[article['publication_title']]
                    repository_id = article['id']
                    
                    # Create document title
                    title = article['title'] or f"Article from {article['publication_title']}"
                    title += f" ({article['issue_date']}, Page {article['page_number']})"
                    
                    # Format document text
                    content = article['text']
                    
                    # Format metadata
                    metadata = {
                        "repository_type": "newspaper",
                        "publication_id": article['publication_id'],
                        "publication_title": article['publication_title'],
                        "issue_date": article['issue_date'],
                        "page_number": article['page_number']
                    }
                    
                    # Check if document already exists
                    if repository_id in existing_docs:
                        # Update document if content changed
                        if existing_docs[repository_id]['content'] != content:
                            main_cursor.execute(
                                """
                                UPDATE Documents 
                                SET title = ?, content = ?, source_id = ?, 
                                    date_modified = datetime('now'), metadata = ?
                                WHERE id = ?
                                """,
                                (
                                    title, 
                                    content, 
                                    source_id, 
                                    str(metadata), 
                                    existing_docs[repository_id]['id']
                                )
                            )
                            updated += 1
                    else:
                        # Add new document
                        main_cursor.execute(
                            """
                            INSERT INTO Documents 
                            (title, content, source_id, date_added, date_modified, 
                             repository_id, metadata)
                            VALUES (?, ?, ?, datetime('now'), datetime('now'), ?, ?)
                            """,
                            (title, content, source_id, repository_id, str(metadata))
                        )
                        added += 1
                
                total = len(articles)
                logger.info(
                    f"Synchronized articles to documents: {added} added, {updated} updated, {total} total"
                )
                return added, updated, total
                
        except Exception as e:
            if isinstance(e, DatabaseConnectorError):
                raise
            raise DatabaseConnectorError(f"Failed to synchronize articles to documents: {str(e)}")
    
    def import_entities_to_repository(self) -> Tuple[int, int, int]:
        """
        Import entities from main database to repository.
        
        Returns:
            Tuple of (added, updated, total) counts
        """
        self._ensure_connected()
        
        try:
            # Begin transaction
            with self.repo_conn:
                repo_cursor = self.repo_conn.cursor()
                
                # Check if Entities table exists in repository
                repo_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Entities'"
                )
                if not repo_cursor.fetchone():
                    raise DatabaseConnectorError("Entities table not found in repository database")
                
                # Get entity types from repository
                repo_cursor.execute("SELECT id, name FROM EntityTypes")
                entity_types = {row['name'].lower(): row['id'] for row in repo_cursor.fetchall()}
                
                # Ensure we have required entity types
                required_types = ['person', 'organization', 'location']
                for type_name in required_types:
                    if type_name not in entity_types:
                        # Add missing entity type
                        repo_cursor.execute(
                            "INSERT INTO EntityTypes (name) VALUES (?)",
                            (type_name,)
                        )
                        repo_cursor.execute(
                            "SELECT id FROM EntityTypes WHERE name = ?",
                            (type_name,)
                        )
                        entity_types[type_name] = repo_cursor.fetchone()['id']
                
                # Get existing entities from repository
                repo_cursor.execute("SELECT id, name, type_id FROM Entities")
                existing_entities = {row['name'].lower(): dict(row) for row in repo_cursor.fetchall()}
                
                # Get entities from main database
                main_cursor = self.main_conn.cursor()
                
                # Check if Characters and Entities tables exist
                tables_to_check = ['Characters', 'Entities']
                for table in tables_to_check:
                    main_cursor.execute(
                        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                    )
                    if not main_cursor.fetchone():
                        logger.warning(f"{table} table not found in main database")
                
                # Get characters (persons)
                main_cursor.execute(
                    """
                    SELECT id, name, description, notes 
                    FROM Characters
                    WHERE name IS NOT NULL AND name != ''
                    """
                )
                characters = main_cursor.fetchall()
                
                # Get other entities
                main_cursor.execute(
                    """
                    SELECT id, name, entity_type, description 
                    FROM Entities
                    WHERE name IS NOT NULL AND name != ''
                    """
                )
                entities = main_cursor.fetchall()
                
                added = 0
                updated = 0
                
                # Process characters (persons)
                for character in characters:
                    name = character['name']
                    description = character['description'] or ''
                    notes = character['notes'] or ''
                    
                    # Map to person entity type
                    type_id = entity_types['person']
                    
                    # Create or update entity
                    if name.lower() in existing_entities:
                        # Update entity
                        repo_cursor.execute(
                            """
                            UPDATE Entities 
                            SET type_id = ?, description = ?, notes = ?, 
                                main_db_id = ?, main_db_table = ?
                            WHERE id = ?
                            """,
                            (
                                type_id, 
                                description, 
                                notes, 
                                character['id'], 
                                'Characters',
                                existing_entities[name.lower()]['id']
                            )
                        )
                        updated += 1
                    else:
                        # Add new entity
                        repo_cursor.execute(
                            """
                            INSERT INTO Entities 
                            (name, type_id, description, notes, main_db_id, main_db_table)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (name, type_id, description, notes, character['id'], 'Characters')
                        )
                        added += 1
                
                # Process other entities
                for entity in entities:
                    name = entity['name']
                    description = entity['description'] or ''
                    entity_type = entity['entity_type'] or 'unknown'
                    
                    # Map entity type
                    if entity_type.lower() in entity_types:
                        type_id = entity_types[entity_type.lower()]
                    else:
                        # Use organization as default
                        type_id = entity_types['organization']
                    
                    # Create or update entity
                    if name.lower() in existing_entities:
                        # Update entity
                        repo_cursor.execute(
                            """
                            UPDATE Entities 
                            SET type_id = ?, description = ?, 
                                main_db_id = ?, main_db_table = ?
                            WHERE id = ?
                            """,
                            (
                                type_id, 
                                description, 
                                entity['id'], 
                                'Entities',
                                existing_entities[name.lower()]['id']
                            )
                        )
                        updated += 1
                    else:
                        # Add new entity
                        repo_cursor.execute(
                            """
                            INSERT INTO Entities 
                            (name, type_id, description, main_db_id, main_db_table)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (name, type_id, description, entity['id'], 'Entities')
                        )
                        added += 1
                
                total = len(characters) + len(entities)
                logger.info(f"Imported entities: {added} added, {updated} updated, {total} total")
                return added, updated, total
                
        except Exception as e:
            if isinstance(e, DatabaseConnectorError):
                raise
            raise DatabaseConnectorError(f"Failed to import entities: {str(e)}")
    
    def import_locations_to_repository(self) -> Tuple[int, int, int]:
        """
        Import locations from main database to repository regions.
        
        Returns:
            Tuple of (added, updated, total) counts
        """
        self._ensure_connected()
        
        try:
            # Begin transaction
            with self.repo_conn:
                repo_cursor = self.repo_conn.cursor()
                
                # Check if Regions table exists in repository
                repo_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Regions'"
                )
                if not repo_cursor.fetchone():
                    raise DatabaseConnectorError("Regions table not found in repository database")
                
                # Get region types from repository
                repo_cursor.execute("SELECT id, name FROM RegionTypes")
                region_types = {row['name'].lower(): row['id'] for row in repo_cursor.fetchall()}
                
                # Ensure we have required region types
                required_types = ['country', 'state', 'city', 'locality']
                for type_name in required_types:
                    if type_name not in region_types:
                        # Add missing region type
                        repo_cursor.execute(
                            "INSERT INTO RegionTypes (name) VALUES (?)",
                            (type_name,)
                        )
                        repo_cursor.execute(
                            "SELECT id FROM RegionTypes WHERE name = ?",
                            (type_name,)
                        )
                        region_types[type_name] = repo_cursor.fetchone()['id']
                
                # Get existing regions from repository
                repo_cursor.execute("SELECT id, name, type_id FROM Regions")
                existing_regions = {row['name'].lower(): dict(row) for row in repo_cursor.fetchall()}
                
                # Get locations from main database
                main_cursor = self.main_conn.cursor()
                
                # Check if Locations table exists
                main_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Locations'"
                )
                if not main_cursor.fetchone():
                    raise DatabaseConnectorError("Locations table not found in main database")
                
                # Get locations
                main_cursor.execute(
                    """
                    SELECT id, name, location_type, description, city, state, country 
                    FROM Locations
                    WHERE name IS NOT NULL AND name != ''
                    """
                )
                locations = main_cursor.fetchall()
                
                added = 0
                updated = 0
                
                # Process locations
                for location in locations:
                    name = location['name']
                    description = location['description'] or ''
                    location_type = location['location_type'] or 'locality'
                    
                    # Determine region type
                    if location_type.lower() in region_types:
                        type_id = region_types[location_type.lower()]
                    else:
                        # Use locality as default
                        type_id = region_types['locality']
                    
                    # Handle parent regions if available
                    parent_id = None
                    city = location['city']
                    state = location['state']
                    country = location['country']
                    
                    # Create parent regions if needed
                    if country and country.lower() not in existing_regions:
                        repo_cursor.execute(
                            """
                            INSERT INTO Regions 
                            (name, type_id, description)
                            VALUES (?, ?, ?)
                            """,
                            (country, region_types['country'], f"Country: {country}")
                        )
                        
                        # Get the ID of the inserted country
                        repo_cursor.execute(
                            "SELECT id FROM Regions WHERE name = ? AND type_id = ?",
                            (country, region_types['country'])
                        )
                        country_id = repo_cursor.fetchone()['id']
                        existing_regions[country.lower()] = {
                            'id': country_id, 
                            'type_id': region_types['country']
                        }
                        added += 1
                    elif country:
                        country_id = existing_regions[country.lower()]['id']
                    else:
                        country_id = None
                    
                    if state and country_id and state.lower() not in existing_regions:
                        repo_cursor.execute(
                            """
                            INSERT INTO Regions 
                            (name, type_id, description, parent_id)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                state, 
                                region_types['state'], 
                                f"State/Province: {state}, {country}", 
                                country_id
                            )
                        )
                        
                        # Get the ID of the inserted state
                        repo_cursor.execute(
                            "SELECT id FROM Regions WHERE name = ? AND type_id = ?",
                            (state, region_types['state'])
                        )
                        state_id = repo_cursor.fetchone()['id']
                        existing_regions[state.lower()] = {
                            'id': state_id, 
                            'type_id': region_types['state']
                        }
                        added += 1
                    elif state:
                        state_id = existing_regions[state.lower()]['id']
                    else:
                        state_id = None
                    
                    if city and state_id and city.lower() not in existing_regions:
                        repo_cursor.execute(
                            """
                            INSERT INTO Regions 
                            (name, type_id, description, parent_id)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                city, 
                                region_types['city'], 
                                f"City: {city}, {state}", 
                                state_id
                            )
                        )
                        
                        # Get the ID of the inserted city
                        repo_cursor.execute(
                            "SELECT id FROM Regions WHERE name = ? AND type_id = ?",
                            (city, region_types['city'])
                        )
                        city_id = repo_cursor.fetchone()['id']
                        existing_regions[city.lower()] = {
                            'id': city_id, 
                            'type_id': region_types['city']
                        }
                        added += 1
                    elif city:
                        city_id = existing_regions[city.lower()]['id']
                    else:
                        city_id = None
                    
                    # Set the parent ID based on available information
                    if city_id and type_id == region_types['locality']:
                        parent_id = city_id
                    elif state_id:
                        parent_id = state_id
                    elif country_id:
                        parent_id = country_id
                    
                    # Create or update region
                    if name.lower() in existing_regions:
                        # Update region
                        repo_cursor.execute(
                            """
                            UPDATE Regions 
                            SET type_id = ?, description = ?, parent_id = ?,
                                main_db_id = ?, main_db_table = ?
                            WHERE id = ?
                            """,
                            (
                                type_id, 
                                description, 
                                parent_id,
                                location['id'], 
                                'Locations',
                                existing_regions[name.lower()]['id']
                            )
                        )
                        updated += 1
                    else:
                        # Add new region
                        repo_cursor.execute(
                            """
                            INSERT INTO Regions 
                            (name, type_id, description, parent_id, main_db_id, main_db_table)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                name, 
                                type_id, 
                                description, 
                                parent_id,
                                location['id'], 
                                'Locations'
                            )
                        )
                        added += 1
                
                total = len(locations)
                logger.info(f"Imported locations: {added} added, {updated} updated, {total} total")
                return added, updated, total
                
        except Exception as e:
            if isinstance(e, DatabaseConnectorError):
                raise
            raise DatabaseConnectorError(f"Failed to import locations: {str(e)}")
    
    def export_entity_mentions(self) -> Tuple[int, int]:
        """
        Export entity mentions from repository to main database.
        
        Returns:
            Tuple of (added_mentions, added_relations) counts
        """
        self._ensure_connected()
        
        try:
            # Begin transaction
            with self.main_conn:
                main_cursor = self.main_conn.cursor()
                
                # Check if Documents, Characters, and CharacterMentions tables exist
                tables_to_check = ['Documents', 'Characters', 'CharacterMentions']
                for table in tables_to_check:
                    main_cursor.execute(
                        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                    )
                    if not main_cursor.fetchone():
                        raise DatabaseConnectorError(f"{table} table not found in main database")
                
                # Get entity mentions from repository
                repo_cursor = self.repo_conn.cursor()
                repo_cursor.execute(
                    """
                    SELECT em.id, em.entity_id, em.article_id, em.count, em.context,
                           e.name as entity_name, e.type_id, e.main_db_id, e.main_db_table,
                           a.text as article_text, a.title as article_title
                    FROM EntityMentions em
                    JOIN Entities e ON em.entity_id = e.id
                    JOIN Articles a ON em.article_id = a.id
                    WHERE e.main_db_id IS NOT NULL
                    """
                )
                mentions = repo_cursor.fetchall()
                
                # Get documents with repository_id
                main_cursor.execute(
                    "SELECT id, repository_id FROM Documents WHERE repository_id IS NOT NULL"
                )
                doc_map = {row['repository_id']: row['id'] for row in main_cursor.fetchall()}
                
                added_mentions = 0
                added_relations = 0
                
                # Process each mention
                for mention in mentions:
                    # Skip if article not mapped to document
                    if mention['article_id'] not in doc_map:
                        continue
                    
                    document_id = doc_map[mention['article_id']]
                    main_db_id = mention['main_db_id']
                    main_db_table = mention['main_db_table']
                    
                    # Handle based on entity type
                    if main_db_table == 'Characters':
                        # Add character mention
                        context = mention['context'] or ""
                        if not context and mention['article_text']:
                            # Create context from article text (excerpt around name)
                            text = mention['article_text']
                            name = mention['entity_name']
                            
                            # Find the first occurrence and create a context window
                            pos = text.lower().find(name.lower())
                            if pos >= 0:
                                start = max(0, pos - 100)
                                end = min(len(text), pos + len(name) + 100)
                                context = text[start:end]
                                
                                # Add ellipsis if truncated
                                if start > 0:
                                    context = "..." + context
                                if end < len(text):
                                    context += "..."
                            else:
                                # Use article title as context
                                context = mention['article_title'] or "Article mention"
                        
                        # Check if mention already exists
                        main_cursor.execute(
                            """
                            SELECT id FROM CharacterMentions
                            WHERE character_id = ? AND document_id = ?
                            """,
                            (main_db_id, document_id)
                        )
                        
                        if not main_cursor.fetchone():
                            # Add new mention
                            main_cursor.execute(
                                """
                                INSERT INTO CharacterMentions
                                (character_id, document_id, context, count)
                                VALUES (?, ?, ?, ?)
                                """,
                                (main_db_id, document_id, context, mention['count'] or 1)
                            )
                            added_mentions += 1
                    
                    elif main_db_table == 'Entities':
                        # Add document-entity relation
                        main_cursor.execute(
                            """
                            SELECT id FROM DocumentEntityRelations
                            WHERE document_id = ? AND entity_id = ?
                            """,
                            (document_id, main_db_id)
                        )
                        
                        if not main_cursor.fetchone():
                            # Add new relation
                            main_cursor.execute(
                                """
                                INSERT INTO DocumentEntityRelations
                                (document_id, entity_id)
                                VALUES (?, ?)
                                """,
                                (document_id, main_db_id)
                            )
                            added_relations += 1
                
                logger.info(
                    f"Exported entity mentions: {added_mentions} character mentions, "
                    f"{added_relations} entity relations"
                )
                return added_mentions, added_relations
                
        except Exception as e:
            if isinstance(e, DatabaseConnectorError):
                raise
            raise DatabaseConnectorError(f"Failed to export entity mentions: {str(e)}")