#!/usr/bin/env python3
"""
Entity Processor for the Newspaper Repository System

This module provides comprehensive entity processing capabilities for historical newspaper articles,
including detection, normalization, relationship analysis, and database integration.

The processor supports multiple detection strategies and is designed to handle the nuances of
historical content, such as name variants, titles, and antiquated language patterns.
"""

import re
import json
import logging
import sqlite3
import spacy
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Set, Optional, Any, Union
from datetime import datetime
from tqdm import tqdm
from pathlib import Path
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("entity_processor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EntityProcessor")

# Load spaCy model - use a model suitable for historical text if available
try:
    nlp = spacy.load("en_core_web_lg")
    logger.info("Loaded spaCy model: en_core_web_lg")
except OSError:
    try:
        nlp = spacy.load("en_core_web_md")
        logger.info("Loaded spaCy model: en_core_web_md")
    except OSError:
        nlp = spacy.load("en_core_web_sm")
        logger.info("Loaded spaCy model: en_core_web_sm")


class EntityProcessor:
    """
    A comprehensive entity processing system for historical newspaper articles.
    
    This class provides capabilities for entity detection, normalization, relationship analysis,
    and database integration, with special handling for historical content.
    """
    
    # Entity types 
    PERSON = "PERSON"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    MISC = "MISC"
    DATE = "DATE"
    EVENT = "EVENT"
    
    def __init__(self, db_path: str, dictionaries_path: Optional[str] = None):
        """
        Initialize the EntityProcessor with database connection and optional dictionaries.
        
        Args:
            db_path: Path to the SQLite database
            dictionaries_path: Optional path to dictionaries directory containing entity lists
        """
        self.db_path = db_path
        self.conn = self._create_connection()
        
        # Entity dictionaries for lookup-based detection
        self.dictionaries = {
            self.PERSON: set(),
            self.LOCATION: set(),
            self.ORGANIZATION: set(),
        }
        
        # Historical title patterns for persons
        self.person_titles = {
            "mr", "mrs", "miss", "ms", "dr", "prof", "rev", "hon", 
            "sir", "madam", "lady", "lord", "duke", "duchess", "earl",
            "sheriff", "officer", "captain", "col", "gen", "lt", "sgt",
            "judge", "justice", "councilman", "alderman", "mayor",
            "governor", "president", "senator", "representative",
            "secretary", "commissioner", "superintendent", "chief",
        }
        
        # Load entity dictionaries if provided
        if dictionaries_path:
            self._load_dictionaries(dictionaries_path)
        
        # Load entities from database to enhance dictionaries
        self._load_entities_from_db()
        
        # Detection results cache
        self.detection_cache = {}
        
        # Relationship patterns (simplified for demonstration)
        self.relationship_patterns = [
            (r'(\w+\s+\w+)\s+and\s+(\w+\s+\w+)', 'associated_with'),
            (r'(\w+\s+\w+)\s+of\s+(\w+\s+\w+)', 'member_of'),
            (r'(\w+\s+\w+),\s+(\w+)\s+of\s+(\w+\s+\w+)', 'position_at'),
        ]
        
        logger.info(f"EntityProcessor initialized with database at {db_path}")

    def _create_connection(self) -> sqlite3.Connection:
        """Create a database connection."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def _load_dictionaries(self, dictionaries_path: str) -> None:
        """
        Load entity dictionaries from files.
        
        Args:
            dictionaries_path: Path to the dictionaries directory
        """
        dictionary_files = {
            self.PERSON: "persons.txt",
            self.LOCATION: "locations.txt",
            self.ORGANIZATION: "organizations.txt",
        }
        
        for entity_type, filename in dictionary_files.items():
            file_path = os.path.join(dictionaries_path, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        entries = [line.strip().lower() for line in f if line.strip()]
                        self.dictionaries[entity_type].update(entries)
                    logger.info(f"Loaded {len(entries)} entries for {entity_type} dictionary")
                except Exception as e:
                    logger.error(f"Error loading dictionary {filename}: {e}")
            else:
                logger.warning(f"Dictionary file not found: {file_path}")

    def _load_entities_from_db(self) -> None:
        """Load existing entities from database to enhance dictionaries."""
        try:
            # Load persons from characters table
            cursor = self.conn.cursor()
            
            # Load persons (assuming there's a characters or persons table)
            try:
                cursor.execute("SELECT name FROM characters")
                for (name,) in cursor.fetchall():
                    if name and len(name.strip()) > 0:
                        self.dictionaries[self.PERSON].add(name.lower())
            except sqlite3.Error as e:
                logger.warning(f"Could not load persons from database: {e}")
            
            # Load locations
            try:
                cursor.execute("SELECT name FROM locations")
                for (name,) in cursor.fetchall():
                    if name and len(name.strip()) > 0:
                        self.dictionaries[self.LOCATION].add(name.lower())
            except sqlite3.Error as e:
                logger.warning(f"Could not load locations from database: {e}")
            
            # Load organizations (entities table or dedicated organizations table)
            try:
                cursor.execute("SELECT name FROM entities WHERE type = 'organization'")
                for (name,) in cursor.fetchall():
                    if name and len(name.strip()) > 0:
                        self.dictionaries[self.ORGANIZATION].add(name.lower())
            except sqlite3.Error as e:
                logger.warning(f"Could not load organizations from database: {e}")
            
            logger.info(f"Loaded {len(self.dictionaries[self.PERSON])} persons, "
                       f"{len(self.dictionaries[self.LOCATION])} locations, "
                       f"{len(self.dictionaries[self.ORGANIZATION])} organizations from database")
                
        except Exception as e:
            logger.error(f"Error loading entities from database: {e}")

    def detect_entities(self, text: str, strategies: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect entities in text using multiple strategies.
        
        Args:
            text: The text to analyze
            strategies: List of strategies to use ("spacy", "rules", "dictionary", "all")
                        Default is ["all"] which uses all available strategies
        
        Returns:
            Dictionary of entities by type with details including confidence scores
        """
        if not text:
            return {
                self.PERSON: [],
                self.LOCATION: [],
                self.ORGANIZATION: [],
                self.MISC: []
            }
        
        # Cache results to avoid reprocessing the same text
        cache_key = hash(text)
        if cache_key in self.detection_cache:
            return self.detection_cache[cache_key]
        
        if strategies is None or "all" in strategies:
            strategies = ["spacy", "rules", "dictionary"]
        
        # Combined results from all strategies
        all_entities = {
            self.PERSON: [],
            self.LOCATION: [],
            self.ORGANIZATION: [],
            self.MISC: []
        }
        
        # Detect with each strategy
        if "spacy" in strategies:
            spacy_entities = self._detect_with_spacy(text)
            self._merge_entity_results(all_entities, spacy_entities)
            
        if "rules" in strategies:
            rule_entities = self._detect_with_rules(text)
            self._merge_entity_results(all_entities, rule_entities)
            
        if "dictionary" in strategies:
            dict_entities = self._detect_with_dictionary(text)
            self._merge_entity_results(all_entities, dict_entities)
        
        # Deduplicate and normalize
        for entity_type in all_entities:
            all_entities[entity_type] = self._deduplicate_entities(all_entities[entity_type])
        
        # Cache the results
        self.detection_cache[cache_key] = all_entities
        
        return all_entities

    def _merge_entity_results(self, all_entities: Dict[str, List], new_entities: Dict[str, List]) -> None:
        """Merge new entities into the combined results."""
        for entity_type, entities in new_entities.items():
            all_entities[entity_type].extend(entities)

    def _detect_with_spacy(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect entities using spaCy's NER.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary of entities by type
        """
        results = {
            self.PERSON: [],
            self.LOCATION: [],
            self.ORGANIZATION: [],
            self.MISC: []
        }
        
        try:
            doc = nlp(text)
            
            for ent in doc.ents:
                entity_detail = {
                    "text": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "strategy": "spacy",
                    "confidence": 0.75,  # Default confidence for spaCy
                    "metadata": {"spacy_label": ent.label_}
                }
                
                # Map spaCy entity types to our types
                if ent.label_ == "PERSON":
                    results[self.PERSON].append(entity_detail)
                elif ent.label_ in ["GPE", "LOC", "FAC"]:
                    results[self.LOCATION].append(entity_detail)
                elif ent.label_ == "ORG":
                    results[self.ORGANIZATION].append(entity_detail)
                else:
                    entity_detail["metadata"]["entity_type"] = ent.label_
                    results[self.MISC].append(entity_detail)
                    
        except Exception as e:
            logger.error(f"Error detecting entities with spaCy: {e}")
            
        return results

    def _detect_with_rules(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect entities using rule-based patterns, especially effective for historical texts.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary of entities by type
        """
        results = {
            self.PERSON: [],
            self.LOCATION: [],
            self.ORGANIZATION: [],
            self.MISC: []
        }
        
        try:
            # Person patterns with titles (historical context)
            # Example: Mr. John Smith, Rev. William Brown
            title_pattern = "|".join(self.person_titles)
            person_pattern = fr'\b({title_pattern})\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
            for match in re.finditer(person_pattern, text, re.IGNORECASE):
                title, name = match.groups()
                entity_detail = {
                    "text": f"{title} {name}",
                    "start": match.start(),
                    "end": match.end(),
                    "strategy": "rules",
                    "confidence": 0.8,
                    "metadata": {"title": title, "name": name}
                }
                results[self.PERSON].append(entity_detail)
            
            # Organization patterns (simplified)
            # Example: First National Bank, Department of Agriculture
            org_patterns = [
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Company|Corporation|Inc|Ltd|Bank|Society|Association|Department|Bureau|Agency|Office)\b',
                r'\b(?:The\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Times|Gazette|Herald|Journal|Post|Intelligencer|Chronicle|Tribune)\b'
            ]
            
            for pattern in org_patterns:
                for match in re.finditer(pattern, text):
                    entity_detail = {
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "strategy": "rules",
                        "confidence": 0.7,
                        "metadata": {"pattern": pattern}
                    }
                    results[self.ORGANIZATION].append(entity_detail)
                    
            # Location patterns (simplified)
            # Example: City of Seattle, town of Portland
            loc_patterns = [
                r'\b(?:city|town|village|county|state|territory|district|province)\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
                r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:County|State|Territory)\b'
            ]
            
            for pattern in loc_patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    entity_detail = {
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "strategy": "rules",
                        "confidence": 0.75,
                        "metadata": {"pattern": pattern}
                    }
                    results[self.LOCATION].append(entity_detail)
            
        except Exception as e:
            logger.error(f"Error detecting entities with rules: {e}")
            
        return results

    def _detect_with_dictionary(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect entities using dictionary lookup.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary of entities by type
        """
        results = {
            self.PERSON: [],
            self.LOCATION: [],
            self.ORGANIZATION: [],
            self.MISC: []
        }
        
        try:
            # Simple dictionary lookup for each entity type
            for entity_type, entity_set in self.dictionaries.items():
                if not entity_set:
                    continue
                    
                # Create regex pattern from dictionary entries
                # Sort by length (longest first) to prioritize longer matches
                entries = sorted(entity_set, key=len, reverse=True)
                
                # Process entries in smaller chunks to avoid regex catastrophic backtracking
                chunk_size = 500
                for i in range(0, len(entries), chunk_size):
                    chunk = entries[i:i+chunk_size]
                    pattern = '|'.join(re.escape(entry) for entry in chunk if len(entry) > 2)
                    if not pattern:
                        continue
                    
                    for match in re.finditer(fr'\b({pattern})\b', text.lower()):
                        # Find the original case in the text
                        original_case = text[match.start():match.end()]
                        entity_detail = {
                            "text": original_case,
                            "start": match.start(),
                            "end": match.end(),
                            "strategy": "dictionary",
                            "confidence": 0.85,  # Dictionary matches are generally reliable
                            "metadata": {"dict_match": True}
                        }
                        
                        if entity_type == self.PERSON:
                            results[self.PERSON].append(entity_detail)
                        elif entity_type == self.LOCATION:
                            results[self.LOCATION].append(entity_detail)
                        elif entity_type == self.ORGANIZATION:
                            results[self.ORGANIZATION].append(entity_detail)
            
        except Exception as e:
            logger.error(f"Error detecting entities with dictionary: {e}")
            
        return results

    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate entities based on text and position, merging metadata and adjusting confidence.
        
        Args:
            entities: List of entity dictionaries
            
        Returns:
            Deduplicated list of entities
        """
        if not entities:
            return []
            
        # Sort by start position
        sorted_entities = sorted(entities, key=lambda x: x["start"])
        deduped = []
        
        i = 0
        while i < len(sorted_entities):
            current = sorted_entities[i]
            
            # Check for overlapping entities
            j = i + 1
            overlaps = []
            while j < len(sorted_entities) and sorted_entities[j]["start"] <= current["end"]:
                if self._entities_overlap(current, sorted_entities[j]):
                    overlaps.append(sorted_entities[j])
                j += 1
                
            if overlaps:
                # Merge overlapping entities
                merged = self._merge_overlapping_entities(current, overlaps)
                deduped.append(merged)
                i = j  # Skip the overlapped entities
            else:
                deduped.append(current)
                i += 1
                
        return deduped

    def _entities_overlap(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """Check if two entities overlap in text."""
        return (entity1["start"] <= entity2["start"] < entity1["end"] or
                entity2["start"] <= entity1["start"] < entity2["end"])

    def _merge_overlapping_entities(self, entity: Dict[str, Any], overlaps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge overlapping entities, combining their metadata and adjusting confidence.
        
        Args:
            entity: The base entity
            overlaps: List of overlapping entities
            
        Returns:
            Merged entity
        """
        # Start with the base entity
        merged = entity.copy()
        
        # Track strategies and confidences
        strategies = [entity["strategy"]]
        confidences = [entity["confidence"]]
        
        # Combine metadata
        merged_metadata = entity.get("metadata", {}).copy()
        
        # Process overlaps
        for overlap in overlaps:
            strategies.append(overlap["strategy"])
            confidences.append(overlap["confidence"])
            
            # Merge metadata
            overlap_metadata = overlap.get("metadata", {})
            for key, value in overlap_metadata.items():
                if key in merged_metadata:
                    if isinstance(merged_metadata[key], list):
                        if value not in merged_metadata[key]:
                            merged_metadata[key].append(value)
                    else:
                        merged_metadata[key] = [merged_metadata[key], value]
                else:
                    merged_metadata[key] = value
        
        # Update the merged entity
        merged["strategy"] = "+".join(sorted(set(strategies)))
        merged["confidence"] = min(1.0, sum(confidences) / len(confidences) + 0.05)  # Slight boost for multiple detections
        merged["metadata"] = merged_metadata
        
        return merged

    def normalize_entity(self, entity_text: str, entity_type: str) -> str:
        """
        Normalize entity names to a standard form.
        
        Args:
            entity_text: The entity text to normalize
            entity_type: The type of entity
            
        Returns:
            Normalized entity text
        """
        if not entity_text:
            return ""
            
        normalized = entity_text.strip()
        
        if entity_type == self.PERSON:
            # Handle person titles
            for title in self.person_titles:
                if normalized.lower().startswith(f"{title}.") or normalized.lower().startswith(f"{title} "):
                    pattern = fr"^{title}\.?\s+"
                    normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
                    break
                    
            # Handle name suffixes (Jr., Sr., etc.)
            normalized = re.sub(r'(\s+(?:Jr|Sr|III|IV|V|I|II)\.?)$', '', normalized, flags=re.IGNORECASE)
            
            # Normalize capitalization
            parts = normalized.split()
            normalized = " ".join([p.capitalize() for p in parts])
            
        elif entity_type in [self.LOCATION, self.ORGANIZATION]:
            # For locations and organizations, preserve original capitalization
            # but remove leading "The" or "the"
            normalized = re.sub(r'^the\s+', '', normalized, flags=re.IGNORECASE)
            
        return normalized

    def find_entity_relationships(self, text: str, entities: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Detect relationships between entities in text.
        
        Args:
            text: The text to analyze
            entities: Dictionary of detected entities by type
            
        Returns:
            List of relationship dictionaries
        """
        relationships = []
        
        # Flatten entities for simpler processing
        flat_entities = []
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                flat_entity = entity.copy()
                flat_entity["type"] = entity_type
                flat_entities.append(flat_entity)
        
        # Sort entities by position in text
        flat_entities.sort(key=lambda e: e["start"])
        
        # Find entities that are close to each other
        for i, entity1 in enumerate(flat_entities):
            for j in range(i+1, min(i+5, len(flat_entities))):  # Look at the next few entities
                entity2 = flat_entities[j]
                
                # Check if entities are within a reasonable distance
                if 0 < entity2["start"] - entity1["end"] < 50:  # Within 50 characters
                    # Extract the text between them
                    between_text = text[entity1["end"]:entity2["start"]]
                    
                    # Check against relationship patterns
                    for pattern, rel_type in self.relationship_patterns:
                        if re.search(pattern, between_text):
                            relationships.append({
                                "entity1": entity1["text"],
                                "entity1_type": entity1["type"],
                                "entity2": entity2["text"],
                                "entity2_type": entity2["type"],
                                "relationship": rel_type,
                                "confidence": 0.7,
                                "context": text[max(0, entity1["start"]-20):min(len(text), entity2["end"]+20)]
                            })
                            break
                    
                    # Infer relationships based on entity types
                    self._infer_relationships(relationships, entity1, entity2, between_text)
        
        return relationships

    def _infer_relationships(self, relationships: List[Dict[str, Any]], 
                            entity1: Dict[str, Any], 
                            entity2: Dict[str, Any], 
                            between_text: str) -> None:
        """
        Infer relationships based on entity types and connecting text.
        
        Args:
            relationships: List to add relationships to
            entity1: First entity
            entity2: Second entity
            between_text: Text between the entities
        """
        # Person-Organization relationship
        if (entity1["type"] == self.PERSON and entity2["type"] == self.ORGANIZATION and
            re.search(r'(?:of|at|with|from)', between_text)):
            relationships.append({
                "entity1": entity1["text"],
                "entity1_type": entity1["type"],
                "entity2": entity2["text"],
                "entity2_type": entity2["type"],
                "relationship": "affiliated_with",
                "confidence": 0.65,
                "evidence": between_text.strip()
            })
        
        # Person-Location relationship
        elif (entity1["type"] == self.PERSON and entity2["type"] == self.LOCATION and
             re.search(r'(?:of|from|in|at|to|visited)', between_text)):
            relationships.append({
                "entity1": entity1["text"],
                "entity1_type": entity1["type"],
                "entity2": entity2["text"],
                "entity2_type": entity2["type"],
                "relationship": "located_at",
                "confidence": 0.65,
                "evidence": between_text.strip()
            })
        
        # Person-Person relationship
        elif (entity1["type"] == self.PERSON and entity2["type"] == self.PERSON and
             re.search(r'(?:and|with|brother|sister|father|mother|wife|husband|married|cousin)', between_text)):
            relationships.append({
                "entity1": entity1["text"],
                "entity1_type": entity1["type"],
                "entity2": entity2["text"],
                "entity2_type": entity2["type"],
                "relationship": "associated_with",
                "confidence": 0.6,
                "evidence": between_text.strip()
            })

    def batch_process(self, texts: List[Tuple[str, str]], strategies: Optional[List[str]] = None) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Process multiple texts in batch.
        
        Args:
            texts: List of (text_id, text) tuples to process
            strategies: List of detection strategies to use
            
        Returns:
            Dictionary of results by text_id
        """
        results = {}
        
        for text_id, text in tqdm(texts, desc="Processing texts"):
            if not text:
                results[text_id] = {
                    "entities": {
                        self.PERSON: [],
                        self.LOCATION: [],
                        self.ORGANIZATION: [],
                        self.MISC: []
                    },
                    "relationships": []
                }
                continue
                
            # Detect entities
            entities = self.detect_entities(text, strategies)
            
            # Find relationships
            relationships = self.find_entity_relationships(text, entities)
            
            results[text_id] = {
                "entities": entities,
                "relationships": relationships
            }
            
        return results

    def save_to_database(self, text_id: str, entities: Dict[str, List[Dict[str, Any]]], 
                         relationships: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Save detected entities and relationships to the database.
        
        Args:
            text_id: ID of the text being processed (e.g., document_id)
            entities: Dictionary of entities by type
            relationships: Optional list of relationships
            
        Returns:
            Success status (True/False)
        """
        if not entities:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # Begin transaction
            self.conn.execute("BEGIN TRANSACTION")
            
            # Insert entities
            for entity_type, entity_list in entities.items():
                for entity in entity_list:
                    normalized_text = self.normalize_entity(entity["text"], entity_type)
                    
                    # Map entity types to database tables
                    if entity_type == self.PERSON:
                        table = "characters"
                    elif entity_type == self.LOCATION:
                        table = "locations"
                    elif entity_type == self.ORGANIZATION:
                        table = "entities"
                        entity_type_field = "organization"
                    else:
                        # Skip miscellaneous entities or handle as needed
                        continue
                    
                    # Check if entity already exists
                    if entity_type == self.ORGANIZATION:
                        cursor.execute(f"SELECT id FROM {table} WHERE name = ? AND type = ?", 
                                      (normalized_text, entity_type_field))
                    else:
                        cursor.execute(f"SELECT id FROM {table} WHERE name = ?", (normalized_text,))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        entity_id = result[0]
                    else:
                        # Insert new entity
                        if entity_type == self.ORGANIZATION:
                            cursor.execute(
                                f"INSERT INTO {table} (name, type, confidence, detection_method, created_at) "
                                f"VALUES (?, ?, ?, ?, ?)",
                                (normalized_text, entity_type_field, entity["confidence"], 
                                entity["strategy"], datetime.now())
                            )
                        else:
                            cursor.execute(
                                f"INSERT INTO {table} (name, confidence, detection_method, created_at) "
                                f"VALUES (?, ?, ?, ?)",
                                (normalized_text, entity["confidence"], entity["strategy"], datetime.now())
                            )
                        entity_id = cursor.lastrowid
                    
                    # Link entity to document
                    try:
                        cursor.execute(
                            f"INSERT INTO document_{table} (document_id, {table[:-1]}_id, context, start_pos, end_pos) "
                            f"VALUES (?, ?, ?, ?, ?)",
                            (text_id, entity_id, 
                             entity.get("context", text_id), 
                             entity.get("start", 0), 
                             entity.get("end", 0))
                        )
                    except sqlite3.Error as e:
                        # The linking table might have a different structure
                        logger.warning(f"Could not link entity to document: {e}")
            
            # Insert relationships if provided
            if relationships:
                for rel in relationships:
                    try:
                        cursor.execute(
                            "INSERT INTO entity_relationships "
                            "(entity1_id, entity1_type, entity2_id, entity2_type, relationship_type, "
                            "confidence, evidence, document_id) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                self._get_entity_id(rel["entity1"], rel["entity1_type"]),
                                rel["entity1_type"],
                                self._get_entity_id(rel["entity2"], rel["entity2_type"]),
                                rel["entity2_type"],
                                rel["relationship"],
                                rel.get("confidence", 0.5),
                                rel.get("evidence", ""),
                                text_id
                            )
                        )
                    except sqlite3.Error as e:
                        logger.warning(f"Could not insert relationship: {e}")
            
            # Commit transaction
            self.conn.execute("COMMIT")
            return True
            
        except sqlite3.Error as e:
            # Rollback on error
            self.conn.execute("ROLLBACK")
            logger.error(f"Database error: {e}")
            return False

    def _get_entity_id(self, entity_name: str, entity_type: str) -> Optional[int]:
        """Get entity ID from database by name and type."""
        try:
            cursor = self.conn.cursor()
            
            normalized_name = self.normalize_entity(entity_name, entity_type)
            
            if entity_type == self.PERSON:
                table = "characters"
                cursor.execute(f"SELECT id FROM {table} WHERE name = ?", (normalized_name,))
            elif entity_type == self.LOCATION:
                table = "locations"
                cursor.execute(f"SELECT id FROM {table} WHERE name = ?", (normalized_name,))
            elif entity_type == self.ORGANIZATION:
                table = "entities"
                cursor.execute(f"SELECT id FROM {table} WHERE name = ? AND type = 'organization'", 
                              (normalized_name,))
            else:
                return None
                
            result = cursor.fetchone()
            return result[0] if result else None
            
        except sqlite3.Error as e:
            logger.error(f"Error getting entity ID: {e}")
            return None

    def add_feedback(self, entity_id: int, entity_type: str, feedback_type: str, 
                   corrected_value: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        """
        Add user feedback for entity correction.
        
        Args:
            entity_id: ID of the entity
            entity_type: Type of entity
            feedback_type: Type of feedback (e.g., "incorrect", "incomplete", "duplicate")
            corrected_value: Optional corrected value
            user_id: Optional ID of the user providing feedback
            
        Returns:
            Success status (True/False)
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute(
                "INSERT INTO entity_feedback "
                "(entity_id, entity_type, feedback_type, corrected_value, user_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entity_id, entity_type, feedback_type, corrected_value, user_id, datetime.now())
            )
            
            self.conn.commit()
            
            # If feedback is correction, update entity if confidence is high enough
            if feedback_type == "correction" and corrected_value:
                self._apply_correction(entity_id, entity_type, corrected_value)
                
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error adding feedback: {e}")
            return False

    def _apply_correction(self, entity_id: int, entity_type: str, corrected_value: str) -> None:
        """Apply a correction to an entity in the database."""
        try:
            cursor = self.conn.cursor()
            
            if entity_type == self.PERSON:
                table = "characters"
            elif entity_type == self.LOCATION:
                table = "locations"
            elif entity_type == self.ORGANIZATION:
                table = "entities"
            else:
                return
                
            cursor.execute(
                f"UPDATE {table} SET name = ?, last_corrected = ? WHERE id = ?",
                (corrected_value, datetime.now(), entity_id)
            )
            
            self.conn.commit()
            logger.info(f"Applied correction to {entity_type} entity {entity_id}: {corrected_value}")
            
        except sqlite3.Error as e:
            logger.error(f"Error applying correction: {e}")

    def get_confidence_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics on entity detection confidence.
        
        Returns:
            Dictionary of confidence statistics by entity type
        """
        stats = {}
        
        for entity_type in [self.PERSON, self.LOCATION, self.ORGANIZATION]:
            if entity_type == self.PERSON:
                table = "characters"
            elif entity_type == self.LOCATION:
                table = "locations"
            elif entity_type == self.ORGANIZATION:
                table = "entities"
                where_clause = "WHERE type = 'organization'"
            else:
                continue
                
            try:
                cursor = self.conn.cursor()
                
                if entity_type == self.ORGANIZATION:
                    cursor.execute(f"SELECT AVG(confidence), MIN(confidence), MAX(confidence) FROM {table} {where_clause}")
                else:
                    cursor.execute(f"SELECT AVG(confidence), MIN(confidence), MAX(confidence) FROM {table}")
                    
                avg, min_conf, max_conf = cursor.fetchone()
                
                stats[entity_type] = {
                    "avg": avg or 0,
                    "min": min_conf or 0,
                    "max": max_conf or 0
                }
                
            except sqlite3.Error as e:
                logger.error(f"Error getting confidence stats: {e}")
                stats[entity_type] = {"avg": 0, "min": 0, "max": 0}
                
        return stats

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()


# Command-line functionality for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process entities in text.")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--dictionaries", help="Path to dictionaries directory")
    parser.add_argument("--text", help="Text to process")
    parser.add_argument("--file", help="File containing text to process")
    parser.add_argument("--batch", help="Directory of text files to process in batch")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    processor = EntityProcessor(args.db, args.dictionaries)
    
    if args.text:
        entities = processor.detect_entities(args.text)
        relationships = processor.find_entity_relationships(args.text, entities)
        
        print("Detected Entities:")
        for entity_type, entity_list in entities.items():
            print(f"\n{entity_type}:")
            for entity in entity_list:
                print(f"  - {entity['text']} (Confidence: {entity['confidence']:.2f}, Strategy: {entity['strategy']})")
        
        print("\nRelationships:")
        for rel in relationships:
            print(f"  - {rel['entity1']} ({rel['entity1_type']}) {rel['relationship']} {rel['entity2']} ({rel['entity2_type']})")
            print(f"    Evidence: {rel.get('evidence', 'N/A')}")
    
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        entities = processor.detect_entities(text)
        relationships = processor.find_entity_relationships(text, entities)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump({
                    "entities": entities,
                    "relationships": relationships
                }, f, indent=2)
        else:
            print("Detected Entities:")
            for entity_type, entity_list in entities.items():
                print(f"\n{entity_type}:")
                for entity in entity_list:
                    print(f"  - {entity['text']} (Confidence: {entity['confidence']:.2f}, Strategy: {entity['strategy']})")
            
            print("\nRelationships:")
            for rel in relationships:
                print(f"  - {rel['entity1']} ({rel['entity1_type']}) {rel['relationship']} {rel['entity2']} ({rel['entity2_type']})")
    
    elif args.batch:
        import glob
        
        files = glob.glob(os.path.join(args.batch, "*.txt"))
        texts = []
        
        for file_path in files:
            file_id = os.path.basename(file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            texts.append((file_id, text))
        
        results = processor.batch_process(texts)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
        else:
            print(f"Processed {len(results)} files")
    
    processor.close()