#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Publication repository module for the Nova newspaper repository system.

This module implements a specialized repository for managing publications, issues,
and pages within the newspaper repository. It provides methods for adding, updating,
and searching publications with proper geographic hierarchy, as well as managing
publication metadata, issues, and pages.
"""

import os
import re
import json
import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, Iterator, Set
import unicodedata

from .base_repository import (
    BaseRepository, RepositoryConfig, RepositoryError, 
    DatabaseError, StorageError, RepositoryStatus
)
from .database_manager import DatabaseManager


class PublicationError(RepositoryError):
    """Base exception class for publication-related errors."""
    def __init__(self, message: str, error_code: str = None, details: Dict = None):
        super().__init__(message, error_code, details)


class PublicationNotFoundError(PublicationError):
    """Exception raised when a publication is not found."""
    def __init__(self, name: str, details: Dict = None):
        message = f"Publication not found: {name}"
        super().__init__(message, "PUBLICATION_NOT_FOUND", details)


class IssueNotFoundError(PublicationError):
    """Exception raised when an issue is not found."""
    def __init__(self, publication_name: str, date_str: str, details: Dict = None):
        message = f"Issue not found: {publication_name} on {date_str}"
        super().__init__(message, "ISSUE_NOT_FOUND", details)


class PageNotFoundError(PublicationError):
    """Exception raised when a page is not found."""
    def __init__(self, issue_id: int, page_number: int, details: Dict = None):
        message = f"Page not found: Issue {issue_id}, Page {page_number}"
        super().__init__(message, "PAGE_NOT_FOUND", details)


class InvalidPublicationDataError(PublicationError):
    """Exception raised when publication data is invalid."""
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "INVALID_PUBLICATION_DATA", details)


class DuplicatePublicationError(PublicationError):
    """Exception raised when a duplicate publication is detected."""
    def __init__(self, name: str, details: Dict = None):
        message = f"Duplicate publication: {name}"
        super().__init__(message, "DUPLICATE_PUBLICATION", details)


class PublicationRepository:
    """Repository for managing publications, issues, and pages."""
    
    # Publication type constants
    PUBLICATION_TYPE_NEWSPAPER = 1
    PUBLICATION_TYPE_MAGAZINE = 2
    PUBLICATION_TYPE_BOOK = 3
    PUBLICATION_TYPE_NEWSLETTER = 4
    PUBLICATION_TYPE_PAMPHLET = 5
    
    # Region type constants
    REGION_TYPE_COUNTRY = 1
    REGION_TYPE_STATE = 2
    REGION_TYPE_COUNTY = 3
    REGION_TYPE_CITY = 4
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the publication repository.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Cache for frequently accessed data
        self._region_cache = {}
        self._publication_cache = {}
        
        # Initialize with default publication types if needed
        self._ensure_publication_types()
        
        # Initialize with default region types if needed
        self._ensure_region_types()
    
    def _ensure_publication_types(self) -> None:
        """Ensure default publication types exist in the database."""
        types = [
            (self.PUBLICATION_TYPE_NEWSPAPER, "Newspaper", "Daily or weekly newspaper"),
            (self.PUBLICATION_TYPE_MAGAZINE, "Magazine", "Periodical magazine or journal"),
            (self.PUBLICATION_TYPE_BOOK, "Book", "Book or monograph"),
            (self.PUBLICATION_TYPE_NEWSLETTER, "Newsletter", "Organizational newsletter"),
            (self.PUBLICATION_TYPE_PAMPHLET, "Pamphlet", "Pamphlet or leaflet")
        ]
        
        for type_id, name, description in types:
            result = self.db_manager.execute_query_fetchone(
                "SELECT publication_type_id FROM PublicationTypes WHERE publication_type_id = ?",
                (type_id,)
            )
            
            if not result:
                with self.db_manager.transaction() as conn:
                    conn.execute(
                        "INSERT INTO PublicationTypes (publication_type_id, name, description) VALUES (?, ?, ?)",
                        (type_id, name, description)
                    )
    
    def _ensure_region_types(self) -> None:
        """Ensure default region types exist in the database."""
        types = [
            (self.REGION_TYPE_COUNTRY, "Country", "Nation or sovereign state", 1),
            (self.REGION_TYPE_STATE, "State/Province", "State, province, or major administrative division", 2),
            (self.REGION_TYPE_COUNTY, "County", "County or equivalent administrative division", 3),
            (self.REGION_TYPE_CITY, "City/Town", "City, town, or other municipality", 4)
        ]
        
        for type_id, name, description, level in types:
            result = self.db_manager.execute_query_fetchone(
                "SELECT region_type_id FROM RegionTypes WHERE region_type_id = ?",
                (type_id,)
            )
            
            if not result:
                with self.db_manager.transaction() as conn:
                    conn.execute(
                        "INSERT INTO RegionTypes (region_type_id, name, description, hierarchy_level) VALUES (?, ?, ?, ?)",
                        (type_id, name, description, level)
                    )
    
    def add_publication(self, name: str, publication_type_id: int, 
                       region_data: Dict[str, str], start_date: Optional[str] = None,
                       end_date: Optional[str] = None, publisher: Optional[str] = None,
                       frequency: Optional[str] = None, language: Optional[str] = None,
                       lccn: Optional[str] = None, nova_source_id: Optional[int] = None,
                       alternate_names: Optional[List[str]] = None) -> int:
        """
        Add a new publication with geographic hierarchy.
        
        Args:
            name: Publication name
            publication_type_id: Publication type ID
            region_data: Dictionary with country, state, county, and city information
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            publisher: Publisher name
            frequency: Publication frequency (daily, weekly, etc.)
            language: Publication language
            lccn: Library of Congress Control Number
            nova_source_id: ID in the Nova Sources table
            alternate_names: List of alternate names/aliases
        
        Returns:
            ID of the new publication
        
        Raises:
            DuplicatePublicationError: If publication already exists
            InvalidPublicationDataError: If required data is missing or invalid
        """
        # Validate inputs
        if not name or not name.strip():
            raise InvalidPublicationDataError("Publication name is required")
        
        # Normalize publication name
        name = self._normalize_publication_name(name)
        
        # Check if publication already exists
        existing = self.find_publication_by_name(name)
        if existing:
            raise DuplicatePublicationError(name, {"publication_id": existing["publication_id"]})
        
        # Get or create the region hierarchy
        region_id = self._get_or_create_region_hierarchy(region_data)
        
        # Format alternate names for storage
        alternate_names_str = None
        if alternate_names:
            alternate_names_str = "; ".join(alternate_names)
        
        # Create canonical name
        canonical_name = self._generate_canonical_name(name, region_data)
        
        try:
            # Insert the publication
            with self.db_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO Publications (
                        name, publication_type_id, region_id, publisher,
                        start_date, end_date, frequency, language, lccn,
                        nova_source_id, canonical_name, alternate_names
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, publication_type_id, region_id, publisher,
                    start_date, end_date, frequency, language, lccn,
                    nova_source_id, canonical_name, alternate_names_str
                ))
                
                publication_id = conn.cursor.lastrowid
                
                self.logger.info(f"Added publication: {name} (ID: {publication_id})")
                return publication_id
        
        except DatabaseError as e:
            self.logger.error(f"Failed to add publication {name}: {str(e)}")
            raise PublicationError(f"Failed to add publication: {str(e)}")
    
    def update_publication(self, publication_id: int, 
                          name: Optional[str] = None,
                          publication_type_id: Optional[int] = None,
                          region_data: Optional[Dict[str, str]] = None,
                          **kwargs) -> bool:
        """
        Update an existing publication.
        
        Args:
            publication_id: Publication ID
            name: New publication name
            publication_type_id: New publication type ID
            region_data: New region data
            **kwargs: Additional fields to update
        
        Returns:
            True if update was successful
        
        Raises:
            PublicationNotFoundError: If publication not found
            InvalidPublicationDataError: If data is invalid
        """
        # Check if publication exists
        publication = self.get_publication(publication_id)
        if not publication:
            raise PublicationNotFoundError(f"ID: {publication_id}")
        
        # Prepare update fields
        update_fields = {}
        
        # Update name if provided
        if name:
            name = self._normalize_publication_name(name)
            update_fields["name"] = name
        
        # Update region if provided
        if region_data:
            region_id = self._get_or_create_region_hierarchy(region_data)
            update_fields["region_id"] = region_id
        
        # Update publication type if provided
        if publication_type_id:
            update_fields["publication_type_id"] = publication_type_id
        
        # Add any additional fields from kwargs
        valid_fields = [
            "publisher", "start_date", "end_date", "frequency", 
            "language", "lccn", "nova_source_id", "alternate_names",
            "issn", "oclc", "notes"
        ]
        
        for field, value in kwargs.items():
            if field in valid_fields:
                update_fields[field] = value
        
        # Update canonical name if name or region changed
        if "name" in update_fields or "region_id" in update_fields:
            new_name = update_fields.get("name", publication["name"])
            
            if "region_id" in update_fields:
                # Get region data for the new region
                region = self.get_region(update_fields["region_id"])
                region_data = {
                    "country": region.get("country"),
                    "state": region.get("state"),
                    "county": region.get("county"),
                    "city": region.get("city")
                }
            else:
                # Use existing region data
                region_data = {
                    "country": publication.get("country"),
                    "state": publication.get("state"),
                    "county": publication.get("county"),
                    "city": publication.get("city")
                }
            
            update_fields["canonical_name"] = self._generate_canonical_name(new_name, region_data)
        
        # Add updated_at timestamp
        update_fields["updated_at"] = datetime.now().isoformat()
        
        if not update_fields:
            return True  # Nothing to update
        
        try:
            # Build update query
            set_clause = ", ".join([f"{field} = ?" for field in update_fields])
            values = list(update_fields.values())
            values.append(publication_id)
            
            # Execute update
            with self.db_manager.transaction() as conn:
                conn.execute(
                    f"UPDATE Publications SET {set_clause} WHERE publication_id = ?",
                    values
                )
                
                self.logger.info(f"Updated publication ID {publication_id}")
                
                # Clear publication from cache
                if publication_id in self._publication_cache:
                    del self._publication_cache[publication_id]
                
                return True
        
        except DatabaseError as e:
            self.logger.error(f"Failed to update publication {publication_id}: {str(e)}")
            raise PublicationError(f"Failed to update publication: {str(e)}")
    
    def get_publication(self, publication_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a publication by ID with full details.
        
        Args:
            publication_id: Publication ID
        
        Returns:
            Publication details or None if not found
        """
        # Check cache first
        if publication_id in self._publication_cache:
            return self._publication_cache[publication_id].copy()
        
        try:
            # Get publication details
            result = self.db_manager.execute_query_fetchone("""
                SELECT p.*, pt.name as publication_type_name
                FROM Publications p
                JOIN PublicationTypes pt ON p.publication_type_id = pt.publication_type_id
                WHERE p.publication_id = ?
            """, (publication_id,))
            
            if not result:
                return None
            
            publication = dict(result)
            
            # Get region information
            region_id = publication.get("region_id")
            if region_id:
                region = self.get_region(region_id)
                if region:
                    publication.update({
                        "country": region.get("country"),
                        "state": region.get("state"),
                        "county": region.get("county"),
                        "city": region.get("city")
                    })
            
            # Get issue count
            issue_count = self.db_manager.execute_query_fetchone(
                "SELECT COUNT(*) FROM Issues WHERE publication_id = ?",
                (publication_id,)
            )
            
            if issue_count:
                publication["issue_count"] = issue_count[0]
            
            # Parse alternate names
            if publication.get("alternate_names"):
                publication["alternate_names_list"] = [
                    name.strip() for name in publication["alternate_names"].split(";")
                ]
            else:
                publication["alternate_names_list"] = []
            
            # Cache the result
            self._publication_cache[publication_id] = publication.copy()
            
            return publication
        
        except DatabaseError as e:
            self.logger.error(f"Failed to get publication {publication_id}: {str(e)}")
            return None
    
    def find_publication_by_name(self, name: str, 
                               region_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Find a publication by name, checking both exact name and aliases.
        
        Args:
            name: Publication name to find
            region_id: Optional region ID for disambiguation
        
        Returns:
            Publication details or None if not found
        """
        try:
            # Normalize name for search
            name = self._normalize_publication_name(name)
            
            # First check exact name match
            query = """
                SELECT publication_id 
                FROM Publications
                WHERE name = ?
            """
            params = [name]
            
            if region_id is not None:
                query += " AND region_id = ?"
                params.append(region_id)
            
            result = self.db_manager.execute_query_fetchone(query, params)
            
            if result:
                return self.get_publication(result[0])
            
            # Next check alternate names
            query = """
                SELECT publication_id 
                FROM Publications
                WHERE alternate_names LIKE ?
            """
            params = [f"%{name}%"]
            
            if region_id is not None:
                query += " AND region_id = ?"
                params.append(region_id)
            
            result = self.db_manager.execute_query_fetchone(query, params)
            
            if result:
                return self.get_publication(result[0])
            
            # Finally check for similarity with fuzzy matching
            # This is an expensive operation, so do it last
            similar_pubs = self._find_similar_publications(name)
            
            if similar_pubs and region_id is not None:
                # Filter by region if provided
                similar_pubs = [pub for pub in similar_pubs if pub.get("region_id") == region_id]
            
            return similar_pubs[0] if similar_pubs else None
        
        except DatabaseError as e:
            self.logger.error(f"Failed to find publication by name {name}: {str(e)}")
            return None
    
    def add_issue(self, publication_id: int, publication_date: str,
                 volume: Optional[str] = None, issue_number: Optional[str] = None,
                 edition: Optional[str] = None, page_count: Optional[int] = None,
                 special_issue: bool = False, notes: Optional[str] = None) -> int:
        """
        Add a new issue for a publication.
        
        Args:
            publication_id: Publication ID
            publication_date: Publication date (YYYY-MM-DD)
            volume: Volume information
            issue_number: Issue number
            edition: Edition information (morning, evening, etc.)
            page_count: Number of pages
            special_issue: Whether this is a special issue
            notes: Additional notes
        
        Returns:
            ID of the new issue
        
        Raises:
            PublicationNotFoundError: If publication not found
            InvalidPublicationDataError: If data is invalid
        """
        # Validate publication date
        if not publication_date or not self._validate_date_format(publication_date):
            raise InvalidPublicationDataError(
                f"Invalid publication date: {publication_date}. Expected format: YYYY-MM-DD"
            )
        
        # Check if publication exists
        publication = self.get_publication(publication_id)
        if not publication:
            raise PublicationNotFoundError(f"ID: {publication_id}")
        
        # Check if issue already exists
        existing = self.find_issue(publication_id, publication_date, edition)
        if existing:
            # Return the ID of the existing issue
            return existing["issue_id"]
        
        try:
            # Insert the issue
            with self.db_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO Issues (
                        publication_id, publication_date, volume, issue_number,
                        edition, page_count, special_issue, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    publication_id, publication_date, volume, issue_number,
                    edition, page_count, 1 if special_issue else 0, notes
                ))
                
                issue_id = conn.cursor.lastrowid
                
                self.logger.info(
                    f"Added issue: {publication['name']} on {publication_date} "
                    f"(ID: {issue_id})"
                )
                
                return issue_id
        
        except DatabaseError as e:
            self.logger.error(f"Failed to add issue for publication {publication_id}: {str(e)}")
            raise PublicationError(f"Failed to add issue: {str(e)}")
    
    def update_issue(self, issue_id: int, **kwargs) -> bool:
        """
        Update an existing issue.
        
        Args:
            issue_id: Issue ID
            **kwargs: Fields to update
        
        Returns:
            True if update was successful
        
        Raises:
            IssueNotFoundError: If issue not found
        """
        # Check if issue exists
        issue = self.get_issue(issue_id)
        if not issue:
            raise IssueNotFoundError("Unknown", "Unknown", {"issue_id": issue_id})
        
        # Prepare update fields
        update_fields = {}
        
        valid_fields = [
            "publication_date", "volume", "issue_number", "edition",
            "page_count", "special_issue", "notes"
        ]
        
        for field, value in kwargs.items():
            if field in valid_fields:
                # Special handling for boolean fields
                if field == "special_issue":
                    update_fields[field] = 1 if value else 0
                else:
                    update_fields[field] = value
        
        # Validate publication date if provided
        if "publication_date" in update_fields:
            if not self._validate_date_format(update_fields["publication_date"]):
                raise InvalidPublicationDataError(
                    f"Invalid publication date: {update_fields['publication_date']}. "
                    f"Expected format: YYYY-MM-DD"
                )
        
        # Add updated_at timestamp
        update_fields["updated_at"] = datetime.now().isoformat()
        
        if not update_fields:
            return True  # Nothing to update
        
        try:
            # Build update query
            set_clause = ", ".join([f"{field} = ?" for field in update_fields])
            values = list(update_fields.values())
            values.append(issue_id)
            
            # Execute update
            with self.db_manager.transaction() as conn:
                conn.execute(
                    f"UPDATE Issues SET {set_clause} WHERE issue_id = ?",
                    values
                )
                
                self.logger.info(f"Updated issue ID {issue_id}")
                return True
        
        except DatabaseError as e:
            self.logger.error(f"Failed to update issue {issue_id}: {str(e)}")
            raise PublicationError(f"Failed to update issue: {str(e)}")
    
    def get_issue(self, issue_id: int) -> Optional[Dict[str, Any]]:
        """
        Get an issue by ID with publication details.
        
        Args:
            issue_id: Issue ID
        
        Returns:
            Issue details or None if not found
        """
        try:
            result = self.db_manager.execute_query_fetchone("""
                SELECT i.*, p.name as publication_name, p.publication_id
                FROM Issues i
                JOIN Publications p ON i.publication_id = p.publication_id
                WHERE i.issue_id = ?
            """, (issue_id,))
            
            if not result:
                return None
            
            issue = dict(result)
            
            # Convert special_issue to boolean
            issue["special_issue"] = bool(issue.get("special_issue"))
            
            # Get page count
            page_count = self.db_manager.execute_query_fetchone(
                "SELECT COUNT(*) FROM Pages WHERE issue_id = ?",
                (issue_id,)
            )
            
            if page_count:
                if issue.get("page_count") is None or issue.get("page_count") == 0:
                    issue["page_count"] = page_count[0]
                issue["available_pages"] = page_count[0]
            
            return issue
        
        except DatabaseError as e:
            self.logger.error(f"Failed to get issue {issue_id}: {str(e)}")
            return None
    
    def find_issue(self, publication_id: int, publication_date: str, 
                  edition: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find an issue by publication ID, date, and optional edition.
        
        Args:
            publication_id: Publication ID
            publication_date: Publication date (YYYY-MM-DD)
            edition: Optional edition information
        
        Returns:
            Issue details or None if not found
        """
        try:
            query = """
                SELECT issue_id 
                FROM Issues
                WHERE publication_id = ? AND publication_date = ?
            """
            params = [publication_id, publication_date]
            
            if edition:
                query += " AND edition = ?"
                params.append(edition)
            
            result = self.db_manager.execute_query_fetchone(query, params)
            
            if result:
                return self.get_issue(result[0])
            
            return None
        
        except DatabaseError as e:
            self.logger.error(
                f"Failed to find issue for publication {publication_id} on {publication_date}: {str(e)}"
            )
            return None
    
    def add_page(self, issue_id: int, page_number: int, image_path: Optional[str] = None,
                image_format: Optional[str] = None, width: Optional[int] = None,
                height: Optional[int] = None, dpi: Optional[int] = None) -> int:
        """
        Add a new page to an issue.
        
        Args:
            issue_id: Issue ID
            page_number: Page number
            image_path: Path to the page image
            image_format: Image format (jp2, jpg, tiff, etc.)
            width: Image width in pixels
            height: Image height in pixels
            dpi: Image resolution in DPI
        
        Returns:
            ID of the new page
        
        Raises:
            IssueNotFoundError: If issue not found
            InvalidPublicationDataError: If data is invalid
        """
        # Check if issue exists
        issue = self.get_issue(issue_id)
        if not issue:
            raise IssueNotFoundError("Unknown", "Unknown", {"issue_id": issue_id})
        
        # Validate page number
        if page_number < 1:
            raise InvalidPublicationDataError("Page number must be greater than 0")
        
        # Check if page already exists
        existing = self.find_page(issue_id, page_number)
        if existing:
            # If page exists but image path is being updated, update it
            if image_path and existing.get("image_path") != image_path:
                self.update_page(
                    existing["page_id"],
                    image_path=image_path,
                    image_format=image_format,
                    width=width,
                    height=height,
                    dpi=dpi
                )
            # Return the ID of the existing page
            return existing["page_id"]
        
        try:
            # Insert the page
            with self.db_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO Pages (
                        issue_id, page_number, image_path, image_format,
                        width, height, dpi
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    issue_id, page_number, image_path, image_format,
                    width, height, dpi
                ))
                
                page_id = conn.cursor.lastrowid
                
                self.logger.info(
                    f"Added page: {issue['publication_name']} on {issue['publication_date']}, "
                    f"Page {page_number} (ID: {page_id})"
                )
                
                # Update issue page count if needed
                if issue["page_count"] is None or page_number > issue["page_count"]:
                    self.update_issue(issue_id, page_count=max(page_number, issue.get("page_count", 0) or 0))
                
                return page_id
        
        except DatabaseError as e:
            self.logger.error(f"Failed to add page for issue {issue_id}: {str(e)}")
            raise PublicationError(f"Failed to add page: {str(e)}")
    
    def update_page(self, page_id: int, **kwargs) -> bool:
        """
        Update an existing page.
        
        Args:
            page_id: Page ID
            **kwargs: Fields to update
        
        Returns:
            True if update was successful
        
        Raises:
            PageNotFoundError: If page not found
        """
        # Check if page exists
        page = self.get_page(page_id)
        if not page:
            raise PageNotFoundError(0, 0, {"page_id": page_id})
        
        # Prepare update fields
        update_fields = {}
        
        valid_fields = [
            "image_path", "image_format", "width", "height", "dpi",
            "ocr_status", "ocr_processed_at", "ocr_engine", "ocr_confidence",
            "has_text_content", "has_article_segmentation", "notes", "source_url"
        ]
        
        for field, value in kwargs.items():
            if field in valid_fields:
                # Special handling for boolean fields
                if field in ["has_text_content", "has_article_segmentation"]:
                    update_fields[field] = 1 if value else 0
                else:
                    update_fields[field] = value
        
        # Add updated_at timestamp
        update_fields["updated_at"] = datetime.now().isoformat()
        
        if not update_fields:
            return True  # Nothing to update
        
        try:
            # Build update query
            set_clause = ", ".join([f"{field} = ?" for field in update_fields])
            values = list(update_fields.values())
            values.append(page_id)
            
            # Execute update
            with self.db_manager.transaction() as conn:
                conn.execute(
                    f"UPDATE Pages SET {set_clause} WHERE page_id = ?",
                    values
                )
                
                self.logger.info(f"Updated page ID {page_id}")
                return True
        
        except DatabaseError as e:
            self.logger.error(f"Failed to update page {page_id}: {str(e)}")
            raise PublicationError(f"Failed to update page: {str(e)}")
    
    def get_page(self, page_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a page by ID with issue and publication details.
        
        Args:
            page_id: Page ID
        
        Returns:
            Page details or None if not found
        """
        try:
            result = self.db_manager.execute_query_fetchone("""
                SELECT pg.*, i.publication_date, i.issue_id, i.publication_id,
                       p.name as publication_name
                FROM Pages pg
                JOIN Issues i ON pg.issue_id = i.issue_id
                JOIN Publications p ON i.publication_id = p.publication_id
                WHERE pg.page_id = ?
            """, (page_id,))
            
            if not result:
                return None
            
            page = dict(result)
            
            # Convert boolean fields
            page["has_text_content"] = bool(page.get("has_text_content"))
            page["has_article_segmentation"] = bool(page.get("has_article_segmentation"))
            
            # Get region count
            region_count = self.db_manager.execute_query_fetchone(
                "SELECT COUNT(*) FROM PageRegions WHERE page_id = ?",
                (page_id,)
            )
            
            if region_count:
                page["region_count"] = region_count[0]
            
            return page
        
        except DatabaseError as e:
            self.logger.error(f"Failed to get page {page_id}: {str(e)}")
            return None
    
    def find_page(self, issue_id: int, page_number: int) -> Optional[Dict[str, Any]]:
        """
        Find a page by issue ID and page number.
        
        Args:
            issue_id: Issue ID
            page_number: Page number
        
        Returns:
            Page details or None if not found
        """
        try:
            result = self.db_manager.execute_query_fetchone("""
                SELECT page_id 
                FROM Pages
                WHERE issue_id = ? AND page_number = ?
            """, (issue_id, page_number))
            
            if result:
                return self.get_page(result[0])
            
            return None
        
        except DatabaseError as e:
            self.logger.error(
                f"Failed to find page for issue {issue_id}, page {page_number}: {str(e)}"
            )
            return None
    
    def get_region(self, region_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a region by ID with hierarchical information.
        
        Args:
            region_id: Region ID
        
        Returns:
            Region details or None if not found
        """
        # Check cache first
        if region_id in self._region_cache:
            return self._region_cache[region_id].copy()
        
        try:
            # Get the region
            region = self.db_manager.execute_query_fetchone("""
                SELECT r.*, rt.name as region_type_name
                FROM Regions r
                JOIN RegionTypes rt ON r.region_type_id = rt.region_type_id
                WHERE r.region_id = ?
            """, (region_id,))
            
            if not region:
                return None
            
            region_dict = dict(region)
            
            # Get parent regions for hierarchy
            country = None
            state = None
            county = None
            city = None
            
            # Determine region type and set appropriate field
            region_type_id = region_dict.get("region_type_id")
            
            if region_type_id == self.REGION_TYPE_CITY:
                city = region_dict.get("name")
                parent_id = region_dict.get("parent_region_id")
                
                if parent_id:
                    parent = self.get_region(parent_id)
                    if parent:
                        county = parent.get("name")
                        state = parent.get("state")
                        country = parent.get("country")
            
            elif region_type_id == self.REGION_TYPE_COUNTY:
                county = region_dict.get("name")
                parent_id = region_dict.get("parent_region_id")
                
                if parent_id:
                    parent = self.get_region(parent_id)
                    if parent:
                        state = parent.get("name")
                        country = parent.get("country")
            
            elif region_type_id == self.REGION_TYPE_STATE:
                state = region_dict.get("name")
                parent_id = region_dict.get("parent_region_id")
                
                if parent_id:
                    parent = self.get_region(parent_id)
                    if parent:
                        country = parent.get("name")
            
            elif region_type_id == self.REGION_TYPE_COUNTRY:
                country = region_dict.get("name")
            
            # Add hierarchy information to region
            region_dict.update({
                "country": country,
                "state": state,
                "county": county,
                "city": city
            })
            
            # Cache the result
            self._region_cache[region_id] = region_dict.copy()
            
            return region_dict
        
        except DatabaseError as e:
            self.logger.error(f"Failed to get region {region_id}: {str(e)}")
            return None
    
    def search_publications(self, name: Optional[str] = None, 
                           region_id: Optional[int] = None,
                           publication_type_id: Optional[int] = None,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search for publications by various criteria.
        
        Args:
            name: Publication name (partial match)
            region_id: Region ID
            publication_type_id: Publication type ID
            start_date: Publication must have started on or after this date
            end_date: Publication must have ended on or before this date
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            List of matching publications
        """
        try:
            query = """
                SELECT p.*, pt.name as publication_type_name,
                       r.name as region_name
                FROM Publications p
                JOIN PublicationTypes pt ON p.publication_type_id = pt.publication_type_id
                JOIN Regions r ON p.region_id = r.region_id
                WHERE 1=1
            """
            params = []
            
            if name:
                # Search in both name and alternate names
                query += " AND (p.name LIKE ? OR p.alternate_names LIKE ?)"
                params.extend([f"%{name}%", f"%{name}%"])
            
            if region_id:
                query += " AND p.region_id = ?"
                params.append(region_id)
            
            if publication_type_id:
                query += " AND p.publication_type_id = ?"
                params.append(publication_type_id)
            
            if start_date:
                query += " AND (p.end_date IS NULL OR p.end_date >= ?)"
                params.append(start_date)
            
            if end_date:
                query += " AND (p.start_date IS NULL OR p.start_date <= ?)"
                params.append(end_date)
            
            query += " ORDER BY p.name LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            results = self.db_manager.execute_query_fetchall(query, params)
            
            publications = []
            for row in results:
                pub = dict(row)
                
                # Get region information
                region_id = pub.get("region_id")
                if region_id:
                    region = self.get_region(region_id)
                    if region:
                        pub.update({
                            "country": region.get("country"),
                            "state": region.get("state"),
                            "county": region.get("county"),
                            "city": region.get("city")
                        })
                
                # Parse alternate names
                if pub.get("alternate_names"):
                    pub["alternate_names_list"] = [
                        name.strip() for name in pub["alternate_names"].split(";")
                    ]
                else:
                    pub["alternate_names_list"] = []
                
                publications.append(pub)
            
            return publications
        
        except DatabaseError as e:
            self.logger.error(f"Failed to search publications: {str(e)}")
            return []
    
    def search_issues(self, publication_id: Optional[int] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     has_pages: Optional[bool] = None,
                     limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search for issues by various criteria.
        
        Args:
            publication_id: Publication ID
            start_date: Issue must be published on or after this date
            end_date: Issue must be published on or before this date
            has_pages: Filter by whether the issue has pages
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            List of matching issues
        """
        try:
            query = """
                SELECT i.*, p.name as publication_name
                FROM Issues i
                JOIN Publications p ON i.publication_id = p.publication_id
                WHERE 1=1
            """
            params = []
            
            if publication_id:
                query += " AND i.publication_id = ?"
                params.append(publication_id)
            
            if start_date:
                query += " AND i.publication_date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND i.publication_date <= ?"
                params.append(end_date)
            
            if has_pages is not None:
                if has_pages:
                    query += """ AND EXISTS (
                        SELECT 1 FROM Pages pg WHERE pg.issue_id = i.issue_id
                    )"""
                else:
                    query += """ AND NOT EXISTS (
                        SELECT 1 FROM Pages pg WHERE pg.issue_id = i.issue_id
                    )"""
            
            query += " ORDER BY i.publication_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            results = self.db_manager.execute_query_fetchall(query, params)
            
            issues = []
            for row in results:
                issue = dict(row)
                
                # Convert special_issue to boolean
                issue["special_issue"] = bool(issue.get("special_issue"))
                
                # Get page count
                page_count = self.db_manager.execute_query_fetchone(
                    "SELECT COUNT(*) FROM Pages WHERE issue_id = ?",
                    (issue["issue_id"],)
                )
                
                if page_count:
                    issue["available_pages"] = page_count[0]
                
                issues.append(issue)
            
            return issues
        
        except DatabaseError as e:
            self.logger.error(f"Failed to search issues: {str(e)}")
            return []
    
    def search_pages(self, issue_id: Optional[int] = None,
                    publication_id: Optional[int] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    ocr_status: Optional[str] = None,
                    has_text_content: Optional[bool] = None,
                    has_article_segmentation: Optional[bool] = None,
                    limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search for pages by various criteria.
        
        Args:
            issue_id: Issue ID
            publication_id: Publication ID
            start_date: Page must be from an issue published on or after this date
            end_date: Page must be from an issue published on or before this date
            ocr_status: OCR status filter
            has_text_content: Filter by whether the page has text content
            has_article_segmentation: Filter by whether the page has article segmentation
            limit: Maximum number of results
            offset: Offset for pagination
        
        Returns:
            List of matching pages
        """
        try:
            query = """
                SELECT pg.*, i.publication_date, i.issue_id, i.publication_id,
                       p.name as publication_name
                FROM Pages pg
                JOIN Issues i ON pg.issue_id = i.issue_id
                JOIN Publications p ON i.publication_id = p.publication_id
                WHERE 1=1
            """
            params = []
            
            if issue_id:
                query += " AND pg.issue_id = ?"
                params.append(issue_id)
            
            if publication_id:
                query += " AND i.publication_id = ?"
                params.append(publication_id)
            
            if start_date:
                query += " AND i.publication_date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND i.publication_date <= ?"
                params.append(end_date)
            
            if ocr_status:
                query += " AND pg.ocr_status = ?"
                params.append(ocr_status)
            
            if has_text_content is not None:
                query += " AND pg.has_text_content = ?"
                params.append(1 if has_text_content else 0)
            
            if has_article_segmentation is not None:
                query += " AND pg.has_article_segmentation = ?"
                params.append(1 if has_article_segmentation else 0)
            
            query += " ORDER BY i.publication_date DESC, pg.page_number LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            results = self.db_manager.execute_query_fetchall(query, params)
            
            pages = []
            for row in results:
                page = dict(row)
                
                # Convert boolean fields
                page["has_text_content"] = bool(page.get("has_text_content"))
                page["has_article_segmentation"] = bool(page.get("has_article_segmentation"))
                
                pages.append(page)
            
            return pages
        
        except DatabaseError as e:
            self.logger.error(f"Failed to search pages: {str(e)}")
            return []
    
    def add_page_region(self, page_id: int, region_type: str, 
                       x: int, y: int, width: int, height: int,
                       ocr_text: Optional[str] = None, 
                       confidence: Optional[float] = None,
                       article_id: Optional[int] = None,
                       image_path: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add a new region to a page.
        
        Args:
            page_id: Page ID
            region_type: Region type ('article', 'advertisement', 'image', etc.)
            x: X coordinate
            y: Y coordinate
            width: Width
            height: Height
            ocr_text: OCR text content
            confidence: OCR confidence
            article_id: Associated article ID
            image_path: Path to region image
            metadata: Additional metadata
        
        Returns:
            ID of the new region
        
        Raises:
            PageNotFoundError: If page not found
            InvalidPublicationDataError: If data is invalid
        """
        # Check if page exists
        page = self.get_page(page_id)
        if not page:
            raise PageNotFoundError(0, 0, {"page_id": page_id})
        
        # Validate position data
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise InvalidPublicationDataError("Invalid position data")
        
        # Convert metadata to JSON if provided
        metadata_json = None
        if metadata:
            metadata_json = json.dumps(metadata)
        
        try:
            # Insert the region
            with self.db_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO PageRegions (
                        page_id, region_type, x, y, width, height,
                        ocr_text, confidence, article_id, image_path, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    page_id, region_type, x, y, width, height,
                    ocr_text, confidence, article_id, image_path, metadata_json
                ))
                
                region_id = conn.cursor.lastrowid
                
                self.logger.info(
                    f"Added page region: {page['publication_name']} on {page['publication_date']}, "
                    f"Page {page['page_number']} (Region ID: {region_id})"
                )
                
                # Update page has_article_segmentation flag if this is an article region
                if region_type.lower() == 'article' and not page.get("has_article_segmentation"):
                    self.update_page(page_id, has_article_segmentation=True)
                
                # Update page has_text_content flag if this region has OCR text
                if ocr_text and not page.get("has_text_content"):
                    self.update_page(page_id, has_text_content=True)
                
                return region_id
        
        except DatabaseError as e:
            self.logger.error(f"Failed to add page region for page {page_id}: {str(e)}")
            raise PublicationError(f"Failed to add page region: {str(e)}")
    
    def get_publication_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about publications in the repository.
        
        Returns:
            Dictionary with various statistics
        """
        try:
            stats = {
                "total_publications": 0,
                "total_issues": 0,
                "total_pages": 0,
                "total_regions": 0,
                "by_publication_type": {},
                "by_country": {},
                "by_decade": {},
                "ocr_statistics": {
                    "completed": 0,
                    "pending": 0,
                    "error": 0
                }
            }
            
            # Get total publications
            result = self.db_manager.execute_query_fetchone(
                "SELECT COUNT(*) FROM Publications"
            )
            if result:
                stats["total_publications"] = result[0]
            
            # Get total issues
            result = self.db_manager.execute_query_fetchone(
                "SELECT COUNT(*) FROM Issues"
            )
            if result:
                stats["total_issues"] = result[0]
            
            # Get total pages
            result = self.db_manager.execute_query_fetchone(
                "SELECT COUNT(*) FROM Pages"
            )
            if result:
                stats["total_pages"] = result[0]
            
            # Get total regions
            result = self.db_manager.execute_query_fetchone(
                "SELECT COUNT(*) FROM PageRegions"
            )
            if result:
                stats["total_regions"] = result[0]
            
            # Get statistics by publication type
            results = self.db_manager.execute_query_fetchall("""
                SELECT pt.name, COUNT(p.publication_id) as count
                FROM Publications p
                JOIN PublicationTypes pt ON p.publication_type_id = pt.publication_type_id
                GROUP BY pt.name
            """)
            
            for row in results:
                stats["by_publication_type"][row[0]] = row[1]
            
            # Get statistics by country
            # This is more complex due to the region hierarchy
            results = self.db_manager.execute_query_fetchall("""
                SELECT r_country.name as country, COUNT(p.publication_id) as count
                FROM Publications p
                JOIN Regions r ON p.region_id = r.region_id
                JOIN Regions r_state ON r.parent_region_id = r_state.region_id
                JOIN Regions r_country ON r_state.parent_region_id = r_country.region_id
                WHERE r.region_type_id = ? AND r_state.region_type_id = ? AND r_country.region_type_id = ?
                GROUP BY r_country.name
                
                UNION
                
                SELECT r_country.name as country, COUNT(p.publication_id) as count
                FROM Publications p
                JOIN Regions r ON p.region_id = r.region_id
                JOIN Regions r_country ON r.parent_region_id = r_country.region_id
                WHERE r.region_type_id = ? AND r_country.region_type_id = ?
                GROUP BY r_country.name
                
                UNION
                
                SELECT r.name as country, COUNT(p.publication_id) as count
                FROM Publications p
                JOIN Regions r ON p.region_id = r.region_id
                WHERE r.region_type_id = ?
                GROUP BY r.name
            """, (
                self.REGION_TYPE_CITY, self.REGION_TYPE_STATE, self.REGION_TYPE_COUNTRY,
                self.REGION_TYPE_STATE, self.REGION_TYPE_COUNTRY,
                self.REGION_TYPE_COUNTRY
            ))
            
            for row in results:
                if row[0] in stats["by_country"]:
                    stats["by_country"][row[0]] += row[1]
                else:
                    stats["by_country"][row[0]] = row[1]
            
            # Get statistics by decade
            results = self.db_manager.execute_query_fetchall("""
                SELECT 
                    SUBSTR(i.publication_date, 1, 3) || '0s' as decade,
                    COUNT(DISTINCT i.issue_id) as issues,
                    COUNT(DISTINCT pg.page_id) as pages
                FROM Issues i
                LEFT JOIN Pages pg ON i.issue_id = pg.issue_id
                GROUP BY decade
                ORDER BY decade
            """)
            
            for row in results:
                stats["by_decade"][row[0]] = {
                    "issues": row[1],
                    "pages": row[2]
                }
            
            # Get OCR statistics
            results = self.db_manager.execute_query_fetchall("""
                SELECT ocr_status, COUNT(*) as count
                FROM Pages
                GROUP BY ocr_status
            """)
            
            for row in results:
                status = row[0] or "pending"
                if status in stats["ocr_statistics"]:
                    stats["ocr_statistics"][status] = row[1]
            
            return stats
        
        except DatabaseError as e:
            self.logger.error(f"Failed to get publication statistics: {str(e)}")
            return {
                "error": str(e),
                "total_publications": 0,
                "total_issues": 0,
                "total_pages": 0
            }
    
    def import_publication_from_nova_source(self, nova_source_id: int, 
                                          publication_type_id: Optional[int] = None,
                                          region_data: Optional[Dict[str, str]] = None) -> int:
        """
        Import a publication from a Nova source.
        
        Args:
            nova_source_id: Nova source ID
            publication_type_id: Publication type ID (default: Newspaper)
            region_data: Region data (default: extracted from source)
        
        Returns:
            ID of the imported publication
        
        Raises:
            PublicationError: If import fails
        """
        try:
            # First check if publication already exists with this nova_source_id
            result = self.db_manager.execute_query_fetchone("""
                SELECT publication_id FROM Publications
                WHERE nova_source_id = ?
            """, (nova_source_id,))
            
            if result:
                return result[0]
            
            # Get the Nova source
            source = self._get_nova_source(nova_source_id)
            
            if not source:
                raise PublicationError(f"Nova source not found: {nova_source_id}")
            
            # Extract source details
            name = source.get("SourceName")
            publisher = source.get("Publisher")
            
            # Set default publication type if not provided
            if publication_type_id is None:
                # Default to Newspaper
                publication_type_id = self.PUBLICATION_TYPE_NEWSPAPER
            
            # Extract or use provided region data
            if region_data is None:
                region_data = {}
                
                # Try to extract region from source location
                location = source.get("Location")
                if location:
                    # Simple parsing - assumes format like "City, State, Country"
                    parts = [part.strip() for part in location.split(",")]
                    
                    if len(parts) >= 3:
                        region_data["country"] = parts[2]
                        region_data["state"] = parts[1]
                        region_data["city"] = parts[0]
                    elif len(parts) == 2:
                        region_data["country"] = "United States"  # Default assumption
                        region_data["state"] = parts[1]
                        region_data["city"] = parts[0]
                    elif len(parts) == 1:
                        region_data["city"] = parts[0]
            
            # Create region if needed
            region_id = self._get_or_create_region_hierarchy(region_data)
            
            # Extract date ranges if available
            start_date = source.get("EstablishedDate")
            end_date = source.get("DiscontinuedDate")
            
            # Extract alternate names if available
            alternate_names = None
            if source.get("Aliases"):
                alternate_names = [name.strip() for name in source.get("Aliases").split(";")]
            
            # Create the publication
            publication_id = self.add_publication(
                name=name,
                publication_type_id=publication_type_id,
                region_data=region_data,
                start_date=start_date,
                end_date=end_date,
                publisher=publisher,
                nova_source_id=nova_source_id,
                alternate_names=alternate_names
            )
            
            self.logger.info(f"Imported publication from Nova source {nova_source_id}: {name}")
            
            return publication_id
        
        except (DatabaseError, PublicationError) as e:
            self.logger.error(f"Failed to import publication from Nova source {nova_source_id}: {str(e)}")
            raise PublicationError(f"Failed to import publication: {str(e)}")
    
    def get_or_create_publication_for_file(self, file_path: str, 
                                          file_pattern: Optional[str] = None,
                                          default_region: Optional[Dict[str, str]] = None,
                                          default_type_id: int = 1) -> int:
        """
        Extract publication info from a file path and get or create the publication.
        
        Args:
            file_path: Path to the file
            file_pattern: Regular expression pattern for parsing file path
            default_region: Default region data if not in filename
            default_type_id: Default publication type ID
        
        Returns:
            ID of the existing or new publication
        
        Raises:
            PublicationError: If publication cannot be created
        """
        try:
            # Extract publication metadata from filename
            metadata = self._extract_metadata_from_filename(file_path, file_pattern)
            
            if not metadata.get("publication_name"):
                raise InvalidPublicationDataError("Could not extract publication name from file path")
            
            # Look for existing publication
            publication = self.find_publication_by_name(metadata.get("publication_name"))
            
            if publication:
                return publication["publication_id"]
            
            # Prepare region data
            region_data = default_region or {}
            
            # Add any region info from filename
            for region_type in ["country", "state", "county", "city"]:
                if metadata.get(region_type):
                    region_data[region_type] = metadata.get(region_type)
            
            # If no region data provided or extracted, use default
            if not region_data:
                region_data = {"country": "United States"}
            
            # Create new publication
            return self.add_publication(
                name=metadata.get("publication_name"),
                publication_type_id=default_type_id,
                region_data=region_data,
                start_date=metadata.get("start_date"),
                end_date=metadata.get("end_date")
            )
        
        except (PublicationError, InvalidPublicationDataError) as e:
            self.logger.error(f"Failed to get or create publication for file {file_path}: {str(e)}")
            raise PublicationError(f"Failed to process publication: {str(e)}")
    
    def bulk_update_publications(self, updates: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Bulk update multiple publications.
        
        Args:
            updates: List of dictionaries with publication_id and fields to update
        
        Returns:
            Dictionary with counts of successes and failures
        """
        results = {"success": 0, "failure": 0}
        
        for update in updates:
            publication_id = update.get("publication_id")
            if not publication_id:
                results["failure"] += 1
                continue
            
            try:
                # Remove publication_id from update data
                update_data = {k: v for k, v in update.items() if k != "publication_id"}
                
                # Update the publication
                self.update_publication(publication_id, **update_data)
                results["success"] += 1
            
            except Exception as e:
                self.logger.error(f"Failed to update publication {publication_id}: {str(e)}")
                results["failure"] += 1
        
        return results
    
    # Helper methods
    
    def _get_nova_source(self, source_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a source from the Nova database.
        
        Args:
            source_id: Nova source ID
        
        Returns:
            Source data or None if not found
        """
        # Implement this to connect to the Nova database
        # This is a simplified example
        try:
            # Assuming the Nova database table is accessible
            result = self.db_manager.execute_query_fetchone("""
                SELECT * FROM Sources
                WHERE SourceID = ?
            """, (source_id,))
            
            return dict(result) if result else None
        
        except Exception as e:
            self.logger.error(f"Failed to get Nova source {source_id}: {str(e)}")
            return None
    
    def _get_or_create_region_hierarchy(self, region_data: Dict[str, str]) -> int:
        """
        Get or create a region hierarchy from region data.
        
        Args:
            region_data: Dictionary with country, state, county, and city information
        
        Returns:
            ID of the region
        
        Raises:
            InvalidPublicationDataError: If region data is insufficient
        """
        country = region_data.get("country")
        state = region_data.get("state")
        county = region_data.get("county")
        city = region_data.get("city")
        
        # We need at least one region identifier
        if not any([country, state, county, city]):
            raise InvalidPublicationDataError("Insufficient region data provided")
        
        # Start with the highest level (country) and work down
        country_id = None
        state_id = None
        county_id = None
        city_id = None
        
        # Create or get country
        if country:
            country_id = self.db_manager.get_or_create_region(
                name=country,
                region_type_id=self.REGION_TYPE_COUNTRY
            )
        
        # Create or get state
        if state:
            state_id = self.db_manager.get_or_create_region(
                name=state,
                region_type_id=self.REGION_TYPE_STATE,
                parent_region_id=country_id
            )
        
        # Create or get county
        if county:
            county_id = self.db_manager.get_or_create_region(
                name=county,
                region_type_id=self.REGION_TYPE_COUNTY,
                parent_region_id=state_id
            )
        
        # Create or get city
        if city:
            city_id = self.db_manager.get_or_create_region(
                name=city,
                region_type_id=self.REGION_TYPE_CITY,
                parent_region_id=county_id or state_id
            )
        
        # Return the most specific region ID
        return city_id or county_id or state_id or country_id
    
    def _normalize_publication_name(self, name: str) -> str:
        """
        Normalize a publication name for consistent storage and comparison.
        
        Args:
            name: Publication name
        
        Returns:
            Normalized name
        """
        if not name:
            return ""
        
        # Clean white space
        name = name.strip()
        
        # Remove common prefixes like "The "
        if name.lower().startswith("the "):
            name = name[4:]
        
        # Normalize case (title case)
        name = name.title()
        
        # Normalize Unicode characters
        name = unicodedata.normalize('NFKC', name)
        
        # Normalize special cases
        special_cases = {
            "Post Intelligencer": "Post-Intelligencer",
            "Post-intel": "Post-Intelligencer",
            "Pi": "Post-Intelligencer",
            "New York Times": "The New York Times",
            "Nyt": "The New York Times",
            "Wash Post": "The Washington Post",
            "Wapo": "The Washington Post"
        }
        
        for case, replacement in special_cases.items():
            if name.lower() == case.lower():
                return replacement
        
        return name
    
    def _generate_canonical_name(self, name: str, region_data: Dict[str, str]) -> str:
        """
        Generate a canonical name combining publication name and location.
        
        Args:
            name: Publication name
            region_data: Region data
        
        Returns:
            Canonical name
        """
        # Start with the normalized name
        canonical_name = self._normalize_publication_name(name)
        
        # Add location information
        location_parts = []
        
        # Try to use the most specific location available
        if region_data.get("city"):
            location_parts.append(region_data.get("city"))
        elif region_data.get("county"):
            location_parts.append(region_data.get("county"))
        
        # Add state if available
        if region_data.get("state"):
            location_parts.append(region_data.get("state"))
        
        # Create location string
        if location_parts:
            location_str = ", ".join(location_parts)
            canonical_name = f"{canonical_name} ({location_str})"
        
        return canonical_name
    
    def _validate_date_format(self, date_str: str) -> bool:
        """
        Validate that a date string is in YYYY-MM-DD format.
        
        Args:
            date_str: Date string to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not date_str:
            return False
        
        try:
            # Check format
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                return False
            
            # Parse date to check validity
            year, month, day = map(int, date_str.split("-"))
            date(year, month, day)
            
            return True
        
        except ValueError:
            return False
    
    def _extract_metadata_from_filename(self, file_path: str, 
                                      file_pattern: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract publication metadata from a filename.
        
        Args:
            file_path: Path to the file
            file_pattern: Regular expression pattern for parsing
        
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}
        
        # Get filename without path and extension
        filename = os.path.basename(file_path)
        filename_no_ext = os.path.splitext(filename)[0]
        
        # Default pattern - tries to extract publication name and date
        default_pattern = r'(?:(\d{4})-(\d{2})-(\d{2})[-_])?(.+?)(?:[-_](\d{4})-(\d{2})-(\d{2}))?'
        
        pattern = file_pattern or default_pattern
        
        # Try to match the pattern
        match = re.match(pattern, filename_no_ext)
        
        if match:
            # With default pattern, groups are:
            # 1-3: Year, month, day (optional)
            # 4: Publication name
            # 5-7: Year, month, day (optional)
            groups = match.groups()
            
            if file_pattern:
                # Custom pattern - just return the groups
                return {"match_groups": groups}
            
            # Process default pattern
            if groups[0] and groups[1] and groups[2]:
                # First date pattern matched
                metadata["publication_date"] = f"{groups[0]}-{groups[1]}-{groups[2]}"
            
            publication_name = groups[3]
            if publication_name:
                metadata["publication_name"] = publication_name.replace("_", " ")
            
            if groups[4] and groups[5] and groups[6]:
                # Second date pattern matched
                if "publication_date" not in metadata:
                    metadata["publication_date"] = f"{groups[4]}-{groups[5]}-{groups[6]}"
                else:
                    # If we already have a publication date, this might be a date range
                    metadata["end_date"] = f"{groups[4]}-{groups[5]}-{groups[6]}"
                    metadata["start_date"] = metadata["publication_date"]
        else:
            # No match - use the filename as the publication name
            metadata["publication_name"] = filename_no_ext.replace("_", " ")
        
        return metadata
    
    def _find_similar_publications(self, name: str, 
                                 threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Find publications with similar names using fuzzy matching.
        
        Args:
            name: Publication name to find
            threshold: Similarity threshold (0-1)
        
        Returns:
            List of similar publications
        """
        try:
            # Get all publications
            publications = self.db_manager.execute_query_fetchall("""
                SELECT publication_id, name, region_id
                FROM Publications
            """)
            
            if not publications:
                return []
            
            # Normalize input name
            normalized_name = self._normalize_publication_name(name)
            
            # Use difflib for fuzzy matching
            import difflib
            similar_publications = []
            
            for pub in publications:
                # Calculate similarity
                similarity = difflib.SequenceMatcher(
                    None, normalized_name.lower(), pub[1].lower()
                ).ratio()
                
                if similarity >= threshold:
                    similar_publications.append({
                        "publication_id": pub[0],
                        "name": pub[1],
                        "region_id": pub[2],
                        "similarity": similarity
                    })
            
            # Sort by similarity (highest first)
            similar_publications.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Get full details for top matches
            return [self.get_publication(pub["publication_id"]) for pub in similar_publications[:5]]
        
        except Exception as e:
            self.logger.error(f"Failed to find similar publications for {name}: {str(e)}")
            return []
    
    def generate_storage_path(self, publication_name: str, publication_date: str,
                            page_number: int, file_format: str = "jp2",
                            base_path: Optional[str] = None) -> str:
        """
        Generate a standardized storage path for a page image.
        
        Args:
            publication_name: Publication name
            publication_date: Publication date (YYYY-MM-DD)
            page_number: Page number
            file_format: File format (jp2, jpg, etc.)
            base_path: Base storage path (default: from config)
        
        Returns:
            Full storage path
        """
        # Validate inputs
        if not publication_name or not publication_date or page_number < 1:
            raise InvalidPublicationDataError("Invalid inputs for storage path generation")
        
        # Normalize publication name for folder name
        folder_name = self._normalize_for_filesystem(publication_name)
        
        # Parse publication date
        try:
            year, month, day = publication_date.split("-")
        except ValueError:
            raise InvalidPublicationDataError(f"Invalid publication date: {publication_date}")
        
        # Generate path components
        date_path = f"{year}/{month}/{day}"
        
        # Ensure base path
        if not base_path:
            base_path = self.db_manager.config.base_path
        
        # Build the full path
        full_path = os.path.join(
            base_path, "publications", folder_name, date_path,
            f"page_{page_number:04d}.{file_format}"
        )
        
        return full_path
    
    def _normalize_for_filesystem(self, text: str) -> str:
        """
        Normalize text for use in file system paths.
        
        Args:
            text: Text to normalize
        
        Returns:
            Normalized text safe for file system
        """
        # Remove invalid characters
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        
        # Replace spaces and other characters with underscores
        text = re.sub(r'[\s-]+', '_', text)
        
        # Ensure it doesn't start with a dot or end with a space
        text = text.strip('. ')
        
        # Convert to lowercase for consistency
        text = text.lower()
        
        return text