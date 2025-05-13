"""
Entity Processor for the Newspaper Repository System.

This module analyzes OCR'd newspaper article text to detect, process, and manage entities
such as people, organizations, locations, and other named entities. It implements various
detection strategies, historical content specialization, and entity relationship tracking.
"""

import collections
import datetime
import difflib
import json
import logging
import os
import re
import sqlite3
import threading
import time
import unicodedata
from enum import Enum
from dataclasses import dataclass
from queue import PriorityQueue, Empty
from typing import Dict, List, Optional, Set, Tuple, Union, Any, Callable

try:
    import spacy
    from spacy.tokens import Doc, Span
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('entity_processor')


class EntityType(Enum):
    """Types of entities that can be detected."""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    EVENT = "event"
    MISC = "misc"


class DetectionMethod(Enum):
    """Methods used to detect entities."""
    NER = "named_entity_recognition"
    RULE_BASED = "rule_based_patterns"
    DICTIONARY = "dictionary_lookup"
    CONTEXT = "context_based"
    HISTORICAL = "historical_patterns"
    USER = "user_defined"


class ConfidenceLevel(Enum):
    """Confidence levels for entity detection."""
    VERY_LOW = 0.2  # Speculative detection
    LOW = 0.4       # Pattern matched but not verified
    MEDIUM = 0.6    # Good pattern match or weak NER
    HIGH = 0.8      # Strong NER or dictionary match
    VERY_HIGH = 1.0 # Multiple methods agree or human verified


@dataclass
class EntityMention:
    """
    Represents an entity mention within an article.
    
    Stores information about an entity detected in text, including position,
    confidence level, and detection method.
    """
    entity_id: Optional[int]  # ID in the entities table
    entity_type: EntityType   # Type of entity
    name: str                 # Detected name
    normalized_name: str      # Normalized version of the name
    article_id: str           # Article where entity was mentioned
    start_pos: int            # Start position in text
    end_pos: int              # End position in text
    context: str              # Surrounding text context
    confidence: float         # Detection confidence (0.0-1.0)
    method: DetectionMethod   # Method used to detect
    attributes: Dict[str, Any] = None  # Additional attributes
    mention_id: Optional[int] = None   # Database ID once stored
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}
        
        # Ensure normalized name exists
        if not self.normalized_name:
            self.normalized_name = normalize_entity_name(self.name, self.entity_type)
    
    def overlaps_with(self, other: 'EntityMention') -> bool:
        """Check if this mention overlaps with another in text position."""
        return (
            self.article_id == other.article_id and
            max(0, min(self.end_pos, other.end_pos) - max(self.start_pos, other.start_pos)) > 0
        )
    
    def similarity_to(self, other: 'EntityMention') -> float:
        """Calculate similarity to another entity mention."""
        name_similarity = difflib.SequenceMatcher(
            None, self.normalized_name, other.normalized_name
        ).ratio()
        
        type_match = 1.0 if self.entity_type == other.entity_type else 0.0
        
        # Weight: 70% name similarity, 30% type match
        return 0.7 * name_similarity + 0.3 * type_match


class EntityRelationType(Enum):
    """Types of relationships between entities."""
    SAME_ARTICLE = "same_article"  # Entities mentioned in the same article
    CO_LOCATED = "co_located"      # Located in the same place
    FAMILY = "family"              # Family relationship
    BUSINESS = "business"          # Business relationship
    POLITICAL = "political"        # Political relationship
    TEMPORAL = "temporal"          # Temporal relationship
    MEMBER_OF = "member_of"        # Membership relationship
    LOCATED_IN = "located_in"      # Location hierarchy relationship
    ASSOCIATED = "associated"      # Generic association


@dataclass
class EntityRelation:
    """
    Represents a relationship between two entities.
    
    Stores information about how entities are related, including the relationship
    type, confidence, and evidence sources.
    """
    entity1_id: int              # ID of first entity
    entity2_id: int              # ID of second entity
    relation_type: EntityRelationType  # Type of relationship
    confidence: float            # Confidence in relationship (0.0-1.0)
    evidence: List[str]          # Articles or other evidence sources
    attributes: Dict[str, Any]   # Additional attributes
    relation_id: Optional[int] = None  # Database ID once stored


class EntityProcessorError(Exception):
    """Exception raised for entity processor errors."""
    pass


class EntityProcessor:
    """
    Processes entities in newspaper articles.
    
    This class is responsible for detecting, normalizing, and managing entities
    in OCR'd newspaper text. It implements multiple detection strategies, with
    special handling for historical content.
    """
    
    def __init__(
        self,
        db_manager,
        config: Dict[str, Any] = None,
        use_spacy: bool = True,
        max_workers: int = 2
    ):
        """
        Initialize the entity processor.
        
        Args:
            db_manager: Database manager instance
            config: Configuration dictionary
            use_spacy: Whether to use spaCy for NER (if available)
            max_workers: Maximum number of worker threads
        """
        self.db_manager = db_manager
        self.config = config or {}
        self.max_workers = max_workers
        
        # Set up NLP
        self.nlp = None
        if use_spacy and SPACY_AVAILABLE:
            try:
                # Use a small model by default for speed
                model_name = self.config.get('spacy_model', 'en_core_web_sm')
                self.nlp = spacy.load(model_name)
                logger.info(f"Loaded spaCy model: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to load spaCy model: {str(e)}")
        
        # Initialize dictionary resources
        self.dictionaries = self._load_dictionaries()
        
        # Initialize rule patterns
        self.patterns = self._load_patterns()
        
        # Initialize title and honorific data
        self.titles = self._load_titles()
        
        # Initialize historical name variants
        self.name_variants = self._load_name_variants()
        
        # Initialize processing queue and workers
        self.task_queue = PriorityQueue()
        self.workers = []
        self.running = False
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.lock = threading.Lock()
        
        logger.info("Entity processor initialized")
    
    def _load_dictionaries(self) -> Dict[EntityType, Dict[str, Any]]:
        """
        Load entity dictionaries from files or default values.
        
        Returns:
            Dictionary of entity dictionaries by type
        """
        dictionaries = {}
        
        # Load people dictionary
        people_path = self.config.get('people_dictionary_path')
        if people_path and os.path.exists(people_path):
            try:
                with open(people_path, 'r', encoding='utf-8') as f:
                    dictionaries[EntityType.PERSON] = {
                        normalize_entity_name(name, EntityType.PERSON): value
                        for name, value in json.load(f).items()
                    }
                logger.info(f"Loaded people dictionary from {people_path}")
            except Exception as e:
                logger.error(f"Failed to load people dictionary: {str(e)}")
                dictionaries[EntityType.PERSON] = {}
        else:
            dictionaries[EntityType.PERSON] = {}
        
        # Load organizations dictionary
        orgs_path = self.config.get('organizations_dictionary_path')
        if orgs_path and os.path.exists(orgs_path):
            try:
                with open(orgs_path, 'r', encoding='utf-8') as f:
                    dictionaries[EntityType.ORGANIZATION] = {
                        normalize_entity_name(name, EntityType.ORGANIZATION): value
                        for name, value in json.load(f).items()
                    }
                logger.info(f"Loaded organizations dictionary from {orgs_path}")
            except Exception as e:
                logger.error(f"Failed to load organizations dictionary: {str(e)}")
                dictionaries[EntityType.ORGANIZATION] = {}
        else:
            dictionaries[EntityType.ORGANIZATION] = {}
        
        # Load locations dictionary
        locations_path = self.config.get('locations_dictionary_path')
        if locations_path and os.path.exists(locations_path):
            try:
                with open(locations_path, 'r', encoding='utf-8') as f:
                    dictionaries[EntityType.LOCATION] = {
                        normalize_entity_name(name, EntityType.LOCATION): value
                        for name, value in json.load(f).items()
                    }
                logger.info(f"Loaded locations dictionary from {locations_path}")
            except Exception as e:
                logger.error(f"Failed to load locations dictionary: {str(e)}")
                dictionaries[EntityType.LOCATION] = {}
        else:
            dictionaries[EntityType.LOCATION] = {}
        
        return dictionaries
    
    def _load_patterns(self) -> Dict[EntityType, List[Dict[str, Any]]]:
        """
        Load entity detection patterns from files or default values.
        
        Returns:
            Dictionary of patterns by entity type
        """
        patterns = {}
        
        # Default person patterns
        patterns[EntityType.PERSON] = [
            {
                'pattern': r'\b(Mr\.|Mrs\.|Miss|Dr\.|Rev\.|Hon\.|Prof\.|Sir|Lady)\s+([A-Z][a-z]+(\s+[A-Z][a-z]+)?)',
                'confidence': 0.8,
                'group': 0
            },
            {
                'pattern': r'\b([A-Z][a-z]+)\s+([A-Z]\.)\s+([A-Z][a-z]+)',  # First M. Last
                'confidence': 0.7,
                'group': 0
            },
            {
                'pattern': r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)(?:,\s+(Esq\.|Jr\.|Sr\.|III|IV|MD|PhD))?',  # First Last
                'confidence': 0.6,
                'group': 0
            }
        ]
        
        # Default organization patterns
        patterns[EntityType.ORGANIZATION] = [
            {
                'pattern': r'\b(The\s+)?([A-Z][a-z]+(\s+[A-Z][a-z]+)*)\s+(Company|Corporation|Inc\.|Ltd\.|Co\.|Association|Society|Committee|Commission|Bureau)',
                'confidence': 0.8,
                'group': 0
            },
            {
                'pattern': r'\b(The\s+)?([A-Z][a-z]+(\s+[A-Z][a-z]+)*)\s+(Bank|Trust|Hospital|School|College|University|Institute|Department|Ministry)',
                'confidence': 0.8,
                'group': 0
            },
            {
                'pattern': r'\b(The\s+)?([A-Z][a-z]+(\s+and\s+|\s+&\s+)[A-Z][a-z]+)',  # Name and Name or Name & Name
                'confidence': 0.6,
                'group': 0
            }
        ]
        
        # Default location patterns
        patterns[EntityType.LOCATION] = [
            {
                'pattern': r'\b(city\s+of|town\s+of)\s+([A-Z][a-z]+(\s+[A-Z][a-z]+)*)',
                'confidence': 0.8,
                'group': 2
            },
            {
                'pattern': r'\b(in|at|near|from)\s+([A-Z][a-z]+(\s+[A-Z][a-z]+)*?)(?:,\s+([A-Z][a-z]+|[A-Z]{2}))?(?=[\.,\s]|$)',
                'confidence': 0.6,
                'group': 2
            },
            {
                'pattern': r'\b([A-Z][a-z]+(\s+[A-Z][a-z]+)*?)\s+(Street|Avenue|Road|Lane|Boulevard|Square|Park|Bridge)',
                'confidence': 0.7,
                'group': 0
            }
        ]
        
        # Load custom patterns if available
        patterns_path = self.config.get('patterns_path')
        if patterns_path and os.path.exists(patterns_path):
            try:
                with open(patterns_path, 'r', encoding='utf-8') as f:
                    custom_patterns = json.load(f)
                
                # Merge custom patterns with defaults
                for entity_type_str, type_patterns in custom_patterns.items():
                    try:
                        entity_type = EntityType(entity_type_str)
                        if entity_type not in patterns:
                            patterns[entity_type] = []
                        
                        patterns[entity_type].extend(type_patterns)
                        logger.info(f"Added {len(type_patterns)} custom patterns for {entity_type.value}")
                    except ValueError:
                        logger.warning(f"Unknown entity type in patterns: {entity_type_str}")
                
                logger.info(f"Loaded custom patterns from {patterns_path}")
            except Exception as e:
                logger.error(f"Failed to load custom patterns: {str(e)}")
        
        return patterns
    
    def _load_titles(self) -> Dict[str, Dict[str, Any]]:
        """
        Load historical titles and honorifics data.
        
        Returns:
            Dictionary of title information
        """
        # Default titles with gender and role information
        titles = {
            "mr": {"gender": "male", "role": "civilian", "prefix": True},
            "mrs": {"gender": "female", "role": "civilian", "marital_status": "married", "prefix": True},
            "miss": {"gender": "female", "role": "civilian", "marital_status": "unmarried", "prefix": True},
            "ms": {"gender": "female", "role": "civilian", "prefix": True},
            "dr": {"gender": None, "role": "professional", "prefix": True},
            "prof": {"gender": None, "role": "academic", "prefix": True},
            "rev": {"gender": None, "role": "religious", "prefix": True},
            "hon": {"gender": None, "role": "political", "prefix": True},
            "sir": {"gender": "male", "role": "nobility", "prefix": True},
            "lady": {"gender": "female", "role": "nobility", "prefix": True},
            "col": {"gender": "male", "role": "military", "prefix": True},
            "gen": {"gender": "male", "role": "military", "prefix": True},
            "capt": {"gender": "male", "role": "military", "prefix": True},
            "maj": {"gender": "male", "role": "military", "prefix": True},
            "lt": {"gender": "male", "role": "military", "prefix": True},
            "cmdr": {"gender": "male", "role": "military", "prefix": True},
            "sgt": {"gender": "male", "role": "military", "prefix": True},
            "gov": {"gender": None, "role": "political", "prefix": True},
            "sen": {"gender": None, "role": "political", "prefix": True},
            "rep": {"gender": None, "role": "political", "prefix": True},
            "president": {"gender": None, "role": "political", "prefix": False},
            "mayor": {"gender": None, "role": "political", "prefix": False},
            "judge": {"gender": None, "role": "legal", "prefix": False},
            "sheriff": {"gender": None, "role": "law_enforcement", "prefix": False},
            "chief": {"gender": None, "role": "leadership", "prefix": False},
            "esq": {"gender": "male", "role": "legal", "prefix": False, "suffix": True},
            "jr": {"gender": None, "role": None, "prefix": False, "suffix": True},
            "sr": {"gender": None, "role": None, "prefix": False, "suffix": True},
            "phd": {"gender": None, "role": "academic", "prefix": False, "suffix": True},
            "md": {"gender": None, "role": "medical", "prefix": False, "suffix": True},
        }
        
        # Load custom titles if available
        titles_path = self.config.get('titles_path')
        if titles_path and os.path.exists(titles_path):
            try:
                with open(titles_path, 'r', encoding='utf-8') as f:
                    custom_titles = json.load(f)
                
                # Merge custom titles with defaults
                titles.update(custom_titles)
                logger.info(f"Loaded custom titles from {titles_path}")
            except Exception as e:
                logger.error(f"Failed to load custom titles: {str(e)}")
        
        return titles
    
    def _load_name_variants(self) -> Dict[str, List[str]]:
        """
        Load historical name variants and spellings.
        
        Returns:
            Dictionary of name variants
        """
        # Default common name variants
        variants = {
            "william": ["will", "willy", "bill", "billy"],
            "robert": ["rob", "robby", "bob", "bobby"],
            "james": ["jim", "jimmy", "jamie"],
            "john": ["johnny", "jack", "jock"],
            "thomas": ["tom", "tommy"],
            "richard": ["rick", "ricky", "dick", "dickie"],
            "charles": ["charlie", "chuck"],
            "henry": ["harry", "hank"],
            "joseph": ["joe", "joey"],
            "edward": ["ed", "eddie", "ned", "teddy"],
            "margaret": ["maggie", "meg", "peggy"],
            "elizabeth": ["eliza", "liz", "lizzie", "beth", "betsy", "betty"],
            "catherine": ["katherine", "katharine", "kathryn", "kate", "katie", "kathy"],
            "dorothy": ["dot", "dotty", "dottie"],
            "frances": ["fanny", "frannie"],
            "sarah": ["sally", "sadie"],
            "mary": ["molly", "polly", "mae", "may"],
            "anna": ["ann", "anne", "annie", "nancy"],
            "rebecca": ["becky"],
            "susan": ["sue", "susie", "sukey"],
        }
        
        # Load custom variants if available
        variants_path = self.config.get('name_variants_path')
        if variants_path and os.path.exists(variants_path):
            try:
                with open(variants_path, 'r', encoding='utf-8') as f:
                    custom_variants = json.load(f)
                
                # Merge custom variants with defaults
                for name, name_variants in custom_variants.items():
                    if name in variants:
                        variants[name].extend(name_variants)
                    else:
                        variants[name] = name_variants
                
                logger.info(f"Loaded custom name variants from {variants_path}")
            except Exception as e:
                logger.error(f"Failed to load custom name variants: {str(e)}")
        
        return variants
    
    def start(self) -> None:
        """Start the entity processor workers."""
        if self.running:
            return
        
        self.running = True
        
        # Clear any existing workers
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1)
        
        self.workers = []
        
        # Create and start worker threads
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_thread,
                name=f"entity-worker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {len(self.workers)} entity processor workers")
    
    def stop(self) -> None:
        """Stop the entity processor workers."""
        if not self.running:
            return
        
        self.running = False
        
        # Wait for workers to terminate
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers = []
        logger.info("Stopped entity processor workers")
    
    def _worker_thread(self) -> None:
        """Worker thread function for processing tasks."""
        while self.running:
            try:
                # Get task from queue (with timeout to check running flag)
                try:
                    priority, task_id, func, args, kwargs = self.task_queue.get(timeout=1)
                except Empty:
                    continue
                
                # Execute task
                try:
                    func(*args, **kwargs)
                    with self.lock:
                        self.tasks_completed += 1
                except Exception as e:
                    logger.error(f"Error in entity processing task {task_id}: {str(e)}")
                    with self.lock:
                        self.tasks_failed += 1
                finally:
                    self.task_queue.task_done()
            
            except Exception as e:
                logger.error(f"Error in entity processor worker: {str(e)}")
    
    def add_task(
        self,
        task_function: Callable,
        *args,
        priority: int = 1,
        task_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Add a task to the processing queue.
        
        Args:
            task_function: Function to execute
            *args: Arguments for the function
            priority: Task priority (lower is higher priority)
            task_id: Optional task identifier
            **kwargs: Keyword arguments for the function
            
        Returns:
            Task identifier
        """
        if task_id is None:
            task_id = f"task-{int(time.time())}-{id(task_function)}"
        
        self.task_queue.put((priority, task_id, task_function, args, kwargs))
        return task_id
    
    def process_article(
        self,
        article_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        min_confidence: float = 0.5,
        priority: int = 1
    ) -> str:
        """
        Process an article to detect and extract entities.
        
        Args:
            article_id: Article identifier
            text: Article text
            metadata: Optional article metadata
            min_confidence: Minimum confidence for entity mentions
            priority: Task priority
            
        Returns:
            Task identifier
        """
        return self.add_task(
            self._process_article_task,
            article_id,
            text,
            metadata,
            min_confidence,
            priority=priority
        )
    
    def _process_article_task(
        self,
        article_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Task function for processing an article.
        
        Args:
            article_id: Article identifier
            text: Article text
            metadata: Optional article metadata
            min_confidence: Minimum confidence threshold
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        metadata = metadata or {}
        
        try:
            # Detect entities using all available methods
            raw_mentions = []
            
            # 1. NER-based detection
            if self.nlp:
                ner_mentions = self._detect_entities_ner(article_id, text)
                raw_mentions.extend(ner_mentions)
            
            # 2. Rule-based detection
            rule_mentions = self._detect_entities_rule_based(article_id, text)
            raw_mentions.extend(rule_mentions)
            
            # 3. Dictionary-based detection
            dict_mentions = self._detect_entities_dictionary(article_id, text)
            raw_mentions.extend(dict_mentions)
            
            # 4. Historical pattern detection
            hist_mentions = self._detect_entities_historical(article_id, text, metadata)
            raw_mentions.extend(hist_mentions)
            
            # Filter for minimum confidence and resolve overlaps
            all_mentions = self._resolve_entity_overlaps(raw_mentions, min_confidence)
            
            # Store entities and mentions in database
            stored_mentions = self._store_entity_mentions(all_mentions)
            
            # Detect and store entity relationships
            relationships = self._detect_entity_relationships(stored_mentions)
            stored_relationships = self._store_entity_relationships(relationships)
            
            # Calculate statistics
            mention_counts = collections.Counter(
                mention.entity_type.value for mention in stored_mentions
            )
            
            processing_time = time.time() - start_time
            
            # Build response
            result = {
                'article_id': article_id,
                'entities_detected': len(stored_mentions),
                'relationships_detected': len(stored_relationships),
                'processing_time': processing_time,
                'entity_counts': dict(mention_counts)
            }
            
            logger.info(
                f"Processed article {article_id}: {len(stored_mentions)} entities, "
                f"{len(stored_relationships)} relationships in {processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process article {article_id}: {str(e)}")
            raise EntityProcessorError(f"Failed to process article: {str(e)}")
    
    def _detect_entities_ner(
        self,
        article_id: str,
        text: str
    ) -> List[EntityMention]:
        """
        Detect entities using Named Entity Recognition (spaCy).
        
        Args:
            article_id: Article identifier
            text: Article text
            
        Returns:
            List of detected entity mentions
        """
        if not self.nlp:
            return []
        
        mentions = []
        
        try:
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Convert spaCy entities to EntityMention objects
            for ent in doc.ents:
                # Map spaCy entity types to our types
                if ent.label_ in ('PERSON', 'PER'):
                    entity_type = EntityType.PERSON
                    confidence = 0.8
                elif ent.label_ in ('ORG', 'ORGANIZATION'):
                    entity_type = EntityType.ORGANIZATION
                    confidence = 0.7
                elif ent.label_ in ('GPE', 'LOC', 'LOCATION', 'FAC'):
                    entity_type = EntityType.LOCATION
                    confidence = 0.7
                elif ent.label_ in ('DATE', 'TIME'):
                    entity_type = EntityType.DATE
                    confidence = 0.9
                elif ent.label_ in ('EVENT'):
                    entity_type = EntityType.EVENT
                    confidence = 0.7
                else:
                    entity_type = EntityType.MISC
                    confidence = 0.6
                
                # Get context (window around entity)
                context_start = max(0, ent.start_char - 50)
                context_end = min(len(text), ent.end_char + 50)
                context = text[context_start:context_end]
                
                # Create entity mention
                mention = EntityMention(
                    entity_id=None,
                    entity_type=entity_type,
                    name=ent.text,
                    normalized_name=normalize_entity_name(ent.text, entity_type),
                    article_id=article_id,
                    start_pos=ent.start_char,
                    end_pos=ent.end_char,
                    context=context,
                    confidence=confidence,
                    method=DetectionMethod.NER,
                    attributes={"spacy_label": ent.label_}
                )
                
                mentions.append(mention)
            
            return mentions
            
        except Exception as e:
            logger.error(f"Error in NER entity detection: {str(e)}")
            return []
    
    def _detect_entities_rule_based(
        self,
        article_id: str,
        text: str
    ) -> List[EntityMention]:
        """
        Detect entities using rule-based patterns.
        
        Args:
            article_id: Article identifier
            text: Article text
            
        Returns:
            List of detected entity mentions
        """
        mentions = []
        
        try:
            # Process each entity type with its patterns
            for entity_type, patterns in self.patterns.items():
                for pattern_info in patterns:
                    pattern = pattern_info['pattern']
                    confidence = pattern_info['confidence']
                    group = pattern_info.get('group', 0)
                    
                    # Find all matches
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        # Get the matched text (either whole match or specific group)
                        if group == 0 or group >= len(match.groups()):
                            matched_text = match.group(0)
                            start_pos = match.start(0)
                            end_pos = match.end(0)
                        else:
                            matched_text = match.group(group)
                            start_pos = match.start(group)
                            end_pos = match.end(group)
                        
                        # Skip if the match is empty
                        if not matched_text or not matched_text.strip():
                            continue
                        
                        # Get context (window around entity)
                        context_start = max(0, start_pos - 50)
                        context_end = min(len(text), end_pos + 50)
                        context = text[context_start:context_end]
                        
                        # Create entity mention
                        mention = EntityMention(
                            entity_id=None,
                            entity_type=entity_type,
                            name=matched_text,
                            normalized_name=normalize_entity_name(matched_text, entity_type),
                            article_id=article_id,
                            start_pos=start_pos,
                            end_pos=end_pos,
                            context=context,
                            confidence=confidence,
                            method=DetectionMethod.RULE_BASED,
                            attributes={"pattern": pattern}
                        )
                        
                        mentions.append(mention)
            
            return mentions
            
        except Exception as e:
            logger.error(f"Error in rule-based entity detection: {str(e)}")
            return []
    
    def _detect_entities_dictionary(
        self,
        article_id: str,
        text: str
    ) -> List[EntityMention]:
        """
        Detect entities using dictionary lookup.
        
        Args:
            article_id: Article identifier
            text: Article text
            
        Returns:
            List of detected entity mentions
        """
        mentions = []
        
        try:
            # Process text for each entity type
            for entity_type, dictionary in self.dictionaries.items():
                # Skip empty dictionaries
                if not dictionary:
                    continue
                
                # Sort dictionary entries by length (descending) to match longest first
                sorted_entries = sorted(dictionary.keys(), key=len, reverse=True)
                
                for entry in sorted_entries:
                    # Find all occurrences of the entry
                    entry_pattern = r'\b' + re.escape(entry) + r'\b'
                    for match in re.finditer(entry_pattern, text, re.IGNORECASE):
                        start_pos = match.start()
                        end_pos = match.end()
                        matched_text = match.group()
                        
                        # Get context (window around entity)
                        context_start = max(0, start_pos - 50)
                        context_end = min(len(text), end_pos + 50)
                        context = text[context_start:context_end]
                        
                        # Get attributes from dictionary
                        attributes = dictionary[entry].copy() if isinstance(dictionary[entry], dict) else {}
                        attributes["dictionary"] = True
                        
                        # Create entity mention
                        mention = EntityMention(
                            entity_id=attributes.get("entity_id"),
                            entity_type=entity_type,
                            name=matched_text,
                            normalized_name=entry,  # Use dictionary key as normalized name
                            article_id=article_id,
                            start_pos=start_pos,
                            end_pos=end_pos,
                            context=context,
                            confidence=0.9,  # High confidence for dictionary matches
                            method=DetectionMethod.DICTIONARY,
                            attributes=attributes
                        )
                        
                        mentions.append(mention)
            
            return mentions
            
        except Exception as e:
            logger.error(f"Error in dictionary entity detection: {str(e)}")
            return []
    
    def _detect_entities_historical(
        self,
        article_id: str,
        text: str,
        metadata: Dict[str, Any]
    ) -> List[EntityMention]:
        """
        Detect entities using historical patterns and context.
        
        Args:
            article_id: Article identifier
            text: Article text
            metadata: Article metadata
            
        Returns:
            List of detected entity mentions
        """
        mentions = []
        
        try:
            # Get publication date if available
            pub_date = None
            if metadata and 'date' in metadata:
                pub_date = metadata['date']
                if isinstance(pub_date, str):
                    try:
                        pub_date = datetime.datetime.strptime(pub_date, '%Y-%m-%d').date()
                    except ValueError:
                        pub_date = None
            
            # 1. Detect formal historical person references
            # Example: "Mr. John Smith, Esq., of Boston"
            formal_pattern = r'\b((?:Mr|Mrs|Miss|Dr|Rev|Hon|Prof|Sir|Lady|Col|Gen|Capt|Maj|Lt)\.?\s+)([A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z]+)+)(?:,\s+(Esq\.|Jr\.|Sr\.|III|IV|MD|PhD))?(?:\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*))?'
            
            for match in re.finditer(formal_pattern, text):
                title = match.group(1).strip() if match.group(1) else ""
                name = match.group(2).strip()
                suffix = match.group(3).strip() if match.group(3) else ""
                location = match.group(4).strip() if match.group(4) else ""
                
                full_name = name
                if suffix:
                    full_name += f", {suffix}"
                
                start_pos = match.start()
                end_pos = match.end()
                
                # Get context
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), end_pos + 50)
                context = text[context_start:context_end]
                
                # Determine attributes based on title
                attributes = {"historical": True}
                if title:
                    title_key = title.lower().rstrip('.')
                    if title_key in self.titles:
                        attributes.update(self.titles[title_key])
                
                if location:
                    attributes["associated_location"] = location
                
                # Create entity mention
                mention = EntityMention(
                    entity_id=None,
                    entity_type=EntityType.PERSON,
                    name=full_name,
                    normalized_name=normalize_entity_name(full_name, EntityType.PERSON),
                    article_id=article_id,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    context=context,
                    confidence=0.85,  # High confidence for formal historical references
                    method=DetectionMethod.HISTORICAL,
                    attributes=attributes
                )
                
                mentions.append(mention)
                
                # Also add location as a separate entity if found
                if location:
                    location_mention = EntityMention(
                        entity_id=None,
                        entity_type=EntityType.LOCATION,
                        name=location,
                        normalized_name=normalize_entity_name(location, EntityType.LOCATION),
                        article_id=article_id,
                        start_pos=match.start(4),
                        end_pos=match.end(4),
                        context=context,
                        confidence=0.7,
                        method=DetectionMethod.HISTORICAL,
                        attributes={"from_person_reference": True}
                    )
                    
                    mentions.append(location_mention)
            
            # 2. Detect historical organizational references
            # Example: "The New York and Erie Railroad Company"
            org_pattern = r'\b(The\s+)?([A-Z][a-z]+(?:[ \-][A-Z][a-z]+)*)(?:\s+and\s+|\s+&\s+)([A-Z][a-z]+(?:[ \-][A-Z][a-z]+)*)(?:\s+(Railroad|Railway|Telegraph|Manufacturing|Banking|Insurance|Publishing|Mercantile))?(?:\s+(Company|Corporation|Co\.|Inc\.|Ltd\.|Association|Society))?'
            
            for match in re.finditer(org_pattern, text):
                has_article = bool(match.group(1))
                first_name = match.group(2).strip() if match.group(2) else ""
                second_name = match.group(3).strip() if match.group(3) else ""
                industry = match.group(4).strip() if match.group(4) else ""
                org_type = match.group(5).strip() if match.group(5) else ""
                
                # Skip if likely not an organization
                if not (has_article or industry or org_type):
                    continue
                
                # Construct full name
                org_name = ""
                if has_article:
                    org_name += "The "
                
                org_name += f"{first_name} and {second_name}"
                
                if industry:
                    org_name += f" {industry}"
                if org_type:
                    org_name += f" {org_type}"
                
                start_pos = match.start()
                end_pos = match.end()
                
                # Get context
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), end_pos + 50)
                context = text[context_start:context_end]
                
                attributes = {
                    "historical": True,
                    "first_name": first_name,
                    "second_name": second_name
                }
                
                if industry:
                    attributes["industry"] = industry
                if org_type:
                    attributes["organization_type"] = org_type
                
                # Create entity mention
                mention = EntityMention(
                    entity_id=None,
                    entity_type=EntityType.ORGANIZATION,
                    name=org_name,
                    normalized_name=normalize_entity_name(org_name, EntityType.ORGANIZATION),
                    article_id=article_id,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    context=context,
                    confidence=0.75,
                    method=DetectionMethod.HISTORICAL,
                    attributes=attributes
                )
                
                mentions.append(mention)
            
            # 3. Detect historical location patterns with contemporary names
            # Example: "in the city of New Amsterdam (now New York)"
            location_pattern = r'\b((?:city|town|village|borough|district|county|parish|province|state|territory|colony)\s+of\s+)([A-Z][a-z]+(?:[ \-][A-Z][a-z]+)*)(?:\s+\((?:now|formerly)\s+([A-Z][a-z]+(?:[ \-][A-Z][a-z]+)*)\))?'
            
            for match in re.finditer(location_pattern, text):
                location_type = match.group(1).strip() if match.group(1) else ""
                location_name = match.group(2).strip()
                alternate_name = match.group(3).strip() if match.group(3) else ""
                
                start_pos = match.start()
                end_pos = match.end()
                
                # Get context
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), end_pos + 50)
                context = text[context_start:context_end]
                
                attributes = {
                    "historical": True,
                    "location_type": location_type
                }
                
                if alternate_name:
                    attributes["alternate_name"] = alternate_name
                
                # Create entity mention for main location
                mention = EntityMention(
                    entity_id=None,
                    entity_type=EntityType.LOCATION,
                    name=location_name,
                    normalized_name=normalize_entity_name(location_name, EntityType.LOCATION),
                    article_id=article_id,
                    start_pos=match.start(2),
                    end_pos=match.end(2),
                    context=context,
                    confidence=0.8,
                    method=DetectionMethod.HISTORICAL,
                    attributes=attributes
                )
                
                mentions.append(mention)
                
                # Add alternate name as a related location if present
                if alternate_name:
                    alt_mention = EntityMention(
                        entity_id=None,
                        entity_type=EntityType.LOCATION,
                        name=alternate_name,
                        normalized_name=normalize_entity_name(alternate_name, EntityType.LOCATION),
                        article_id=article_id,
                        start_pos=match.start(3),
                        end_pos=match.end(3),
                        context=context,
                        confidence=0.75,
                        method=DetectionMethod.HISTORICAL,
                        attributes={
                            "historical": True,
                            "location_type": location_type,
                            "related_to": location_name
                        }
                    )
                    
                    mentions.append(alt_mention)
            
            return mentions
            
        except Exception as e:
            logger.error(f"Error in historical entity detection: {str(e)}")
            return []
    
    def _resolve_entity_overlaps(
        self,
        mentions: List[EntityMention],
        min_confidence: float = 0.5
    ) -> List[EntityMention]:
        """
        Resolve overlapping entity mentions and filter by confidence.
        
        Args:
            mentions: List of entity mentions
            min_confidence: Minimum confidence threshold
            
        Returns:
            Filtered and de-duplicated entity mentions
        """
        # Filter by minimum confidence
        filtered_mentions = [m for m in mentions if m.confidence >= min_confidence]
        
        # If no mentions left, return empty list
        if not filtered_mentions:
            return []
        
        # Sort by confidence (descending)
        sorted_mentions = sorted(
            filtered_mentions, key=lambda m: m.confidence, reverse=True
        )
        
        # Group by article ID
        mentions_by_article = {}
        for mention in sorted_mentions:
            if mention.article_id not in mentions_by_article:
                mentions_by_article[mention.article_id] = []
            mentions_by_article[mention.article_id].append(mention)
        
        # Process each article's mentions separately
        resolved_mentions = []
        
        for article_id, article_mentions in mentions_by_article.items():
            # Sort mentions by position
            position_sorted = sorted(
                article_mentions, key=lambda m: (m.start_pos, -m.end_pos)
            )
            
            # Resolve overlaps
            non_overlapping = []
            for mention in position_sorted:
                # Check if this mention overlaps with any accepted mention
                overlaps = False
                for accepted in non_overlapping:
                    if mention.overlaps_with(accepted):
                        # If this mention is very similar to the accepted one, skip it
                        if mention.similarity_to(accepted) > 0.8:
                            overlaps = True
                            break
                        
                        # If this mention has higher confidence, replace the accepted one
                        if mention.confidence > accepted.confidence + 0.2:
                            non_overlapping.remove(accepted)
                        else:
                            overlaps = True
                            break
                
                if not overlaps:
                    non_overlapping.append(mention)
            
            resolved_mentions.extend(non_overlapping)
        
        return resolved_mentions
    
    def _store_entity_mentions(
        self,
        mentions: List[EntityMention]
    ) -> List[EntityMention]:
        """
        Store entity mentions in the database.
        
        Args:
            mentions: List of entity mentions
            
        Returns:
            List of stored entity mentions with updated IDs
        """
        if not mentions:
            return []
        
        stored_mentions = []
        
        try:
            with self.db_manager.transaction() as tx:
                for mention in mentions:
                    # First, check if entity already exists or create new one
                    if mention.entity_id is None:
                        # Try to find existing entity by normalized name
                        entity = self.db_manager.get_entity_by_name(
                            mention.normalized_name, str(mention.entity_type.value)
                        )
                        
                        if entity:
                            mention.entity_id = entity['id']
                        else:
                            # Create new entity
                            entity_data = {
                                'name': mention.name,
                                'normalized_name': mention.normalized_name,
                                'type': str(mention.entity_type.value),
                                'attributes': json.dumps(mention.attributes or {})
                            }
                            
                            mention.entity_id = self.db_manager.insert_entity(entity_data)
                    
                    # Now store the mention
                    mention_data = {
                        'entity_id': mention.entity_id,
                        'article_id': mention.article_id,
                        'start_pos': mention.start_pos,
                        'end_pos': mention.end_pos,
                        'context': mention.context,
                        'confidence': mention.confidence,
                        'method': str(mention.method.value),
                        'attributes': json.dumps(mention.attributes or {})
                    }
                    
                    mention.mention_id = self.db_manager.insert_entity_mention(mention_data)
                    stored_mentions.append(mention)
            
            return stored_mentions
            
        except Exception as e:
            logger.error(f"Failed to store entity mentions: {str(e)}")
            return []
    
    def _detect_entity_relationships(
        self,
        mentions: List[EntityMention]
    ) -> List[EntityRelation]:
        """
        Detect relationships between entities.
        
        Args:
            mentions: List of entity mentions
            
        Returns:
            List of detected entity relationships
        """
        if not mentions:
            return []
        
        relationships = []
        
        try:
            # Group mentions by article
            mentions_by_article = {}
            for mention in mentions:
                if mention.article_id not in mentions_by_article:
                    mentions_by_article[mention.article_id] = []
                mentions_by_article[mention.article_id].append(mention)
            
            # Process each article
            for article_id, article_mentions in mentions_by_article.items():
                # 1. Co-occurrence in same article
                for i, mention1 in enumerate(article_mentions):
                    for mention2 in article_mentions[i+1:]:
                        # Skip if same entity
                        if mention1.entity_id == mention2.entity_id:
                            continue
                        
                        # Create basic co-occurrence relationship
                        relation = EntityRelation(
                            entity1_id=mention1.entity_id,
                            entity2_id=mention2.entity_id,
                            relation_type=EntityRelationType.SAME_ARTICLE,
                            confidence=0.7,
                            evidence=[article_id],
                            attributes={
                                "article_id": article_id,
                                "character_distance": abs(
                                    (mention1.start_pos + mention1.end_pos) / 2 - 
                                    (mention2.start_pos + mention2.end_pos) / 2
                                )
                            }
                        )
                        
                        # Add specific relationship types based on entity types
                        if (mention1.entity_type == EntityType.PERSON and 
                            mention2.entity_type == EntityType.ORGANIZATION):
                            # Check for membership indicators
                            context1 = mention1.context.lower()
                            context2 = mention2.context.lower()
                            combined_context = f"{context1} {context2}"
                            
                            membership_indicators = [
                                "member of", "belongs to", "joined", "part of",
                                "works for", "employed by", "president of", "secretary of",
                                "chairman of", "director of", "officer of", "founder of"
                            ]
                            
                            for indicator in membership_indicators:
                                if indicator in combined_context:
                                    relation.relation_type = EntityRelationType.MEMBER_OF
                                    relation.confidence = 0.8
                                    relation.attributes["indicator"] = indicator
                                    break
                        
                        elif (mention1.entity_type == EntityType.PERSON and 
                              mention2.entity_type == EntityType.PERSON):
                            # Check for family relationship indicators
                            context1 = mention1.context.lower()
                            context2 = mention2.context.lower()
                            combined_context = f"{context1} {context2}"
                            
                            family_indicators = [
                                "father", "mother", "son", "daughter", "brother", "sister",
                                "husband", "wife", "spouse", "uncle", "aunt", "cousin",
                                "grandfather", "grandmother", "grandson", "granddaughter",
                                "nephew", "niece", "family", "relative", "married"
                            ]
                            
                            for indicator in family_indicators:
                                if indicator in combined_context:
                                    relation.relation_type = EntityRelationType.FAMILY
                                    relation.confidence = 0.75
                                    relation.attributes["indicator"] = indicator
                                    break
                        
                        elif (mention1.entity_type == EntityType.LOCATION and 
                              mention2.entity_type == EntityType.LOCATION):
                            # Check for location hierarchy indicators
                            context1 = mention1.context.lower()
                            context2 = mention2.context.lower()
                            combined_context = f"{context1} {context2}"
                            
                            location_indicators = [
                                "in", "near", "located in", "part of", "district of",
                                "county", "state", "province", "region", "territory"
                            ]
                            
                            for indicator in location_indicators:
                                if indicator in combined_context:
                                    relation.relation_type = EntityRelationType.LOCATED_IN
                                    relation.confidence = 0.7
                                    relation.attributes["indicator"] = indicator
                                    break
                        
                        relationships.append(relation)
                
                # 2. Proximity-based relationships (entities mentioned close together)
                sorted_mentions = sorted(article_mentions, key=lambda m: m.start_pos)
                
                for i, mention1 in enumerate(sorted_mentions[:-1]):
                    mention2 = sorted_mentions[i+1]
                    
                    # Skip if same entity
                    if mention1.entity_id == mention2.entity_id:
                        continue
                    
                    # Check if mentions are close to each other (within 100 chars)
                    if mention2.start_pos - mention1.end_pos < 100:
                        # Check context between mentions for relationship indicators
                        between_text = article_mentions[0].context[
                            mention1.end_pos - article_mentions[0].start_pos:
                            mention2.start_pos - article_mentions[0].start_pos
                        ].lower()
                        
                        relation_type = EntityRelationType.ASSOCIATED
                        confidence = 0.6
                        indicator = None
                        
                        # Business relationship indicators
                        business_indicators = [
                            "partner", "business", "company", "firm", "enterprise",
                            "corporation", "association", "contract", "agreement"
                        ]
                        
                        # Political relationship indicators
                        political_indicators = [
                            "politician", "elected", "appointed", "nomination", "campaign",
                            "government", "administration", "party", "delegate", "representative"
                        ]
                        
                        for bi in business_indicators:
                            if bi in between_text:
                                relation_type = EntityRelationType.BUSINESS
                                confidence = 0.7
                                indicator = bi
                                break
                        
                        if not indicator:
                            for pi in political_indicators:
                                if pi in between_text:
                                    relation_type = EntityRelationType.POLITICAL
                                    confidence = 0.7
                                    indicator = pi
                                    break
                        
                        relation = EntityRelation(
                            entity1_id=mention1.entity_id,
                            entity2_id=mention2.entity_id,
                            relation_type=relation_type,
                            confidence=confidence,
                            evidence=[article_id],
                            attributes={
                                "article_id": article_id,
                                "proximity": mention2.start_pos - mention1.end_pos
                            }
                        )
                        
                        if indicator:
                            relation.attributes["indicator"] = indicator
                        
                        relationships.append(relation)
            
            return relationships
            
        except Exception as e:
            logger.error(f"Failed to detect entity relationships: {str(e)}")
            return []
    
    def _store_entity_relationships(
        self,
        relationships: List[EntityRelation]
    ) -> List[EntityRelation]:
        """
        Store entity relationships in the database.
        
        Args:
            relationships: List of entity relationships
            
        Returns:
            List of stored entity relationships with updated IDs
        """
        if not relationships:
            return []
        
        stored_relationships = []
        
        try:
            with self.db_manager.transaction() as tx:
                for relation in relationships:
                    # Check if relationship already exists
                    existing = self.db_manager.get_entity_relation(
                        relation.entity1_id, 
                        relation.entity2_id,
                        str(relation.relation_type.value)
                    )
                    
                    if existing:
                        # Update existing relationship
                        relation_id = existing['id']
                        
                        # Merge evidence and update confidence
                        evidence = set(existing.get('evidence', []))
                        evidence.update(relation.evidence)
                        
                        # Update confidence based on evidence count
                        confidence = min(1.0, relation.confidence + (len(evidence) - 1) * 0.1)
                        
                        # Update attributes
                        attributes = existing.get('attributes', {})
                        if isinstance(attributes, str):
                            try:
                                attributes = json.loads(attributes)
                            except:
                                attributes = {}
                        
                        for key, value in relation.attributes.items():
                            attributes[key] = value
                        
                        # Update in database
                        self.db_manager.update_entity_relation(
                            relation_id,
                            {
                                'confidence': confidence,
                                'evidence': json.dumps(list(evidence)),
                                'attributes': json.dumps(attributes)
                            }
                        )
                        
                        relation.relation_id = relation_id
                        relation.confidence = confidence
                        relation.evidence = list(evidence)
                        relation.attributes = attributes
                        
                    else:
                        # Create new relationship
                        relation_data = {
                            'entity1_id': relation.entity1_id,
                            'entity2_id': relation.entity2_id,
                            'relation_type': str(relation.relation_type.value),
                            'confidence': relation.confidence,
                            'evidence': json.dumps(relation.evidence),
                            'attributes': json.dumps(relation.attributes)
                        }
                        
                        relation.relation_id = self.db_manager.insert_entity_relation(relation_data)
                    
                    stored_relationships.append(relation)
            
            return stored_relationships
            
        except Exception as e:
            logger.error(f"Failed to store entity relationships: {str(e)}")
            return []
    
    def process_articles_batch(
        self,
        articles: List[Dict[str, Any]],
        min_confidence: float = 0.5,
        priority: int = 1
    ) -> str:
        """
        Process a batch of articles.
        
        Args:
            articles: List of article dictionaries with 'id' and 'text' keys
            min_confidence: Minimum confidence threshold
            priority: Task priority
            
        Returns:
            Task identifier
        """
        return self.add_task(
            self._process_articles_batch_task,
            articles,
            min_confidence,
            priority=priority
        )
    
    def _process_articles_batch_task(
        self,
        articles: List[Dict[str, Any]],
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Task function for processing a batch of articles.
        
        Args:
            articles: List of article dictionaries with 'id' and 'text' keys
            min_confidence: Minimum confidence threshold
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        
        try:
            results = {}
            total_entities = 0
            total_relationships = 0
            
            # Process each article
            for article in articles:
                article_id = article['id']
                text = article['text']
                metadata = article.get('metadata', {})
                
                # Process the article
                result = self._process_article_task(
                    article_id, text, metadata, min_confidence
                )
                
                results[article_id] = result
                total_entities += result['entities_detected']
                total_relationships += result['relationships_detected']
            
            processing_time = time.time() - start_time
            
            # Build response
            result = {
                'articles_processed': len(articles),
                'total_entities': total_entities,
                'total_relationships': total_relationships,
                'processing_time': processing_time,
                'article_results': results
            }
            
            logger.info(
                f"Processed batch of {len(articles)} articles: {total_entities} entities, "
                f"{total_relationships} relationships in {processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process articles batch: {str(e)}")
            raise EntityProcessorError(f"Failed to process articles batch: {str(e)}")
    
    def update_entity(
        self,
        entity_id: int,
        updates: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an entity with corrected information.
        
        Args:
            entity_id: Entity ID
            updates: Dictionary of updates
            user_id: Optional ID of the user making the correction
            
        Returns:
            Updated entity dictionary
        """
        try:
            # Record correction for feedback
            if user_id:
                feedback = {
                    'entity_id': entity_id,
                    'user_id': user_id,
                    'timestamp': datetime.datetime.now().isoformat(),
                    'updates': updates
                }
                
                self.db_manager.insert_entity_feedback(feedback)
            
            # Update entity in database
            self.db_manager.update_entity(entity_id, updates)
            
            # Get updated entity
            entity = self.db_manager.get_entity(entity_id)
            
            if not entity:
                raise EntityProcessorError(f"Entity not found after update: {entity_id}")
            
            return entity
            
        except Exception as e:
            logger.error(f"Failed to update entity {entity_id}: {str(e)}")
            raise EntityProcessorError(f"Failed to update entity: {str(e)}")
    
    def merge_entities(
        self,
        primary_id: int,
        secondary_ids: List[int],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Merge multiple entities into one.
        
        Args:
            primary_id: ID of the primary entity to keep
            secondary_ids: IDs of secondary entities to merge
            user_id: Optional ID of the user performing the merge
            
        Returns:
            Dictionary with merge results
        """
        try:
            # Record merge for feedback
            if user_id:
                feedback = {
                    'entity_id': primary_id,
                    'user_id': user_id,
                    'timestamp': datetime.datetime.now().isoformat(),
                    'action': 'merge',
                    'details': {
                        'merged_ids': secondary_ids
                    }
                }
                
                self.db_manager.insert_entity_feedback(feedback)
            
            # Get all entities
            primary = self.db_manager.get_entity(primary_id)
            if not primary:
                raise EntityProcessorError(f"Primary entity not found: {primary_id}")
            
            secondaries = [
                self.db_manager.get_entity(sec_id) for sec_id in secondary_ids
            ]
            secondaries = [s for s in secondaries if s]  # Filter out None values
            
            if not secondaries:
                raise EntityProcessorError("No valid secondary entities found")
            
            # Verify entity types match
            for secondary in secondaries:
                if secondary['type'] != primary['type']:
                    raise EntityProcessorError(
                        f"Entity type mismatch: {primary['type']} vs {secondary['type']}"
                    )
            
            # Collect all mentions and relationships
            with self.db_manager.transaction() as tx:
                # Update all mentions to point to primary entity
                for secondary in secondaries:
                    self.db_manager.update_entity_mentions_entity(
                        old_entity_id=secondary['id'],
                        new_entity_id=primary_id
                    )
                    
                    # Update all relationships
                    self.db_manager.update_entity_relations_entity(
                        old_entity_id=secondary['id'],
                        new_entity_id=primary_id
                    )
                    
                    # Mark secondary as merged
                    self.db_manager.update_entity(
                        secondary['id'],
                        {
                            'merged_into': primary_id,
                            'attributes': json.dumps({
                                'merged': True,
                                'merged_timestamp': datetime.datetime.now().isoformat(),
                                'merged_by': user_id
                            })
                        }
                    )
            
            # Get updated primary entity
            updated_primary = self.db_manager.get_entity(primary_id)
            
            # Get updated mention count
            mention_count = self.db_manager.count_entity_mentions(primary_id)
            
            return {
                'entity': updated_primary,
                'merged_count': len(secondaries),
                'mention_count': mention_count,
                'merged_ids': [s['id'] for s in secondaries]
            }
            
        except Exception as e:
            logger.error(f"Failed to merge entities: {str(e)}")
            raise EntityProcessorError(f"Failed to merge entities: {str(e)}")
    
    def get_entity_statistics(
        self,
        entity_type: Optional[str] = None,
        min_mentions: int = 1,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get statistics about the most significant entities.
        
        Args:
            entity_type: Optional entity type filter
            min_mentions: Minimum number of mentions
            limit: Maximum number of entities to return
            
        Returns:
            Dictionary with entity statistics
        """
        try:
            # Convert string entity type to enum if needed
            entity_type_enum = None
            if entity_type:
                try:
                    entity_type_enum = EntityType(entity_type)
                    entity_type = entity_type_enum.value
                except ValueError:
                    pass
            
            # Get entity counts
            entity_counts = self.db_manager.get_entity_mention_counts(
                entity_type=entity_type,
                min_mentions=min_mentions,
                limit=limit
            )
            
            # Get total counts by type
            type_counts = self.db_manager.get_entity_type_counts()
            
            # Process results
            entities = []
            for entity in entity_counts:
                entity_data = {
                    'id': entity['id'],
                    'name': entity['name'],
                    'normalized_name': entity['normalized_name'],
                    'type': entity['type'],
                    'mention_count': entity['mention_count'],
                    'article_count': entity['article_count']
                }
                
                # Add relationship count if available
                relation_count = self.db_manager.count_entity_relations(entity['id'])
                entity_data['relation_count'] = relation_count
                
                entities.append(entity_data)
            
            return {
                'entities': entities,
                'type_counts': type_counts,
                'total_entities': sum(tc['count'] for tc in type_counts),
                'params': {
                    'entity_type': entity_type,
                    'min_mentions': min_mentions,
                    'limit': limit
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get entity statistics: {str(e)}")
            raise EntityProcessorError(f"Failed to get entity statistics: {str(e)}")
    
    def find_similar_entities(
        self,
        entity_id: int,
        threshold: float = 0.7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find entities similar to the given entity.
        
        Args:
            entity_id: Entity ID to find similar entities for
            threshold: Similarity threshold (0.0-1.0)
            limit: Maximum number of similar entities to return
            
        Returns:
            List of similar entity dictionaries with similarity scores
        """
        try:
            # Get the entity
            entity = self.db_manager.get_entity(entity_id)
            if not entity:
                raise EntityProcessorError(f"Entity not found: {entity_id}")
            
            # Get all entities of the same type
            entities = self.db_manager.get_entities_by_type(entity['type'])
            
            # Calculate similarity scores
            similar = []
            for other in entities:
                # Skip if same entity
                if other['id'] == entity_id:
                    continue
                
                # Calculate name similarity
                name_similarity = difflib.SequenceMatcher(
                    None, 
                    entity['normalized_name'],
                    other['normalized_name']
                ).ratio()
                
                # Only include if above threshold
                if name_similarity >= threshold:
                    similar.append({
                        'entity': other,
                        'similarity': name_similarity
                    })
            
            # Sort by similarity (descending) and limit
            similar.sort(key=lambda x: x['similarity'], reverse=True)
            
            return similar[:limit]
            
        except Exception as e:
            logger.error(f"Failed to find similar entities: {str(e)}")
            raise EntityProcessorError(f"Failed to find similar entities: {str(e)}")
    
    def get_queue_status(self) -> Dict[str, int]:
        """
        Get the status of the processing queue.
        
        Returns:
            Dictionary with queue status
        """
        return {
            'pending': self.task_queue.qsize(),
            'completed': self.tasks_completed,
            'failed': self.tasks_failed
        }
    
    def is_running(self) -> bool:
        """
        Check if the processor is running.
        
        Returns:
            True if processor is running, False otherwise
        """
        return self.running and any(w.is_alive() for w in self.workers)
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all tasks to complete.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            True if all tasks completed, False if timeout occurred
        """
        start_time = time.time()
        
        while self.running and self.task_queue.qsize() > 0:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                return False
            
            # Wait a bit
            time.sleep(0.5)
        
        return self.task_queue.qsize() == 0


def normalize_entity_name(name: str, entity_type: EntityType) -> str:
    """
    Normalize an entity name for consistent matching.
    
    Args:
        name: Entity name
        entity_type: Type of entity
        
    Returns:
        Normalized name
    """
    if not name:
        return ""
    
    # Convert to lowercase
    normalized = name.lower()
    
    # Remove leading/trailing whitespace
    normalized = normalized.strip()
    
    # Handle entity-specific normalization
    if entity_type == EntityType.PERSON:
        # Remove titles and honorifics
        prefixes = [
            "mr.", "mrs.", "miss", "ms.", "dr.", "prof.", "professor", "rev.",
            "honorable", "hon.", "sir", "lady", "lord", "colonel", "col.",
            "general", "gen.", "captain", "capt.", "major", "maj.", "lieutenant", "lt."
        ]
        
        suffixes = [
            "jr.", "sr.", "esq.", "ph.d.", "md", "m.d.", "dds", "esquire",
            "the third", "the fourth", "iii", "iv", "junior", "senior"
        ]
        
        # Process prefixes
        for prefix in prefixes:
            if normalized.startswith(prefix + " "):
                normalized = normalized[len(prefix):].strip()
            elif normalized.startswith(prefix + "."):
                normalized = normalized[len(prefix)+1:].strip()
        
        # Process suffixes
        for suffix in suffixes:
            if normalized.endswith(", " + suffix):
                normalized = normalized[:-(len(suffix)+2)].strip()
            elif normalized.endswith(" " + suffix):
                normalized = normalized[:-(len(suffix)+1)].strip()
        
        # Remove middle initials (e.g., "John Q. Public" -> "john public")
        # Find patterns like "word initial. word" and convert to "word word"
        normalized = re.sub(r'(\w+)\s+[a-z]\.\s+(\w+)', r'\1 \2', normalized)
        
    elif entity_type == EntityType.ORGANIZATION:
        # Remove common organization type words
        org_types = [
            "company", "corporation", "incorporated", "inc", "inc.", "limited", "ltd",
            "ltd.", "association", "committee", "society", "co.", "co", "corp.", "corp",
            "llc", "llp", "lp", "plc", "foundation", "trust", "group"
        ]
        
        # Remove "the" from beginning
        if normalized.startswith("the "):
            normalized = normalized[4:]
        
        # Remove organization type from end
        for org_type in org_types:
            if normalized.endswith(" " + org_type):
                normalized = normalized[:-(len(org_type)+1)].strip()
            elif normalized.endswith(", " + org_type):
                normalized = normalized[:-(len(org_type)+2)].strip()
        
        # Normalize "and" and "&"
        normalized = normalized.replace(" and ", " & ")
        
    elif entity_type == EntityType.LOCATION:
        # Remove common location type words
        location_types = [
            "city", "town", "village", "borough", "county", "parish", "district",
            "state", "province", "territory", "country", "region", "area"
        ]
        
        # Remove location type from beginning
        for loc_type in location_types:
            if normalized.startswith(loc_type + " of "):
                normalized = normalized[len(loc_type)+4:].strip()
    
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Remove punctuation
    normalized = re.sub(r'[^\w\s&]', '', normalized)
    
    # Normalize unicode characters
    normalized = unicodedata.normalize('NFKD', normalized)
    normalized = ''.join([c for c in normalized if not unicodedata.combining(c)])
    
    return normalized.strip()