#!/usr/bin/env python3
"""
Nova Database Schema Extractor

This script extracts the schema of the Nova database and outputs it in a structured format.
It provides information about tables, columns, data types, constraints, and relationships,
as well as sample queries showing how the database is used.

Features:
1. Connects to the Nova database and extracts table definitions
2. Lists all columns with their data types and constraints for each table
3. Identifies primary keys, foreign keys, and relationships between tables
4. Distinguishes between project-specific and application-level tables
5. Outputs the schema in a structured format (JSON and markdown)
6. Includes sample queries showing how Events, Characters, Locations, and Entities tables are used
7. Analyzes how project separation is handled in the database structure

Usage:
    python database_schema_extractor.py [--output OUTPUT_FILE] [--format {json,markdown}]

Arguments:
    --output OUTPUT_FILE    Output file path (default: schema_output.md or schema_output.json)
    --format {json,markdown}   Output format (default: markdown)

The script is non-destructive and read-only, focusing only on schema extraction.
"""

import sqlite3
import json
import argparse
import os
from pathlib import Path
import sys
from typing import Dict, List, Any, Tuple, Optional, Set


class DatabaseSchemaExtractor:
    """Extract and analyze the schema of the Nova database"""

    def __init__(self, db_path: str):
        """
        Initialize the schema extractor
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.schema = {
            "database_info": {
                "path": db_path,
                "size": 0
            },
            "tables": {},
            "relationships": [],
            "project_tables": [],
            "application_tables": [],
            "sample_queries": {},
            "analysis": {}
        }
        
    def connect(self):
        """Connect to the database"""
        try:
            # Get file size
            if os.path.exists(self.db_path):
                self.schema["database_info"]["size"] = os.path.getsize(self.db_path) / 1024 / 1024
            
            # Connect to database
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            print(f"Connected to database at {self.db_path}")
            return True
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return False
            
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            print("Database connection closed")
            
    def extract_schema(self):
        """Extract the complete database schema"""
        if not self.conn:
            if not self.connect():
                return False
                
        # Get list of all tables
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in self.cursor.fetchall()]
        
        # Process each table
        for table_name in tables:
            self._extract_table_schema(table_name)
            
        # Extract foreign key relationships
        self._extract_relationships()
        
        # Categorize tables
        self._categorize_tables()
        
        # Create sample queries
        self._create_sample_queries()
        
        # Analyze project structure
        self._analyze_project_structure()
        
        return True
            
    def _extract_table_schema(self, table_name: str):
        """
        Extract schema for a specific table
        
        Args:
            table_name: Name of the table to extract
        """
        # Get column information
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        columns = []
        primary_keys = []
        
        for row in self.cursor.fetchall():
            column = {
                "name": row["name"],
                "type": row["type"],
                "not_null": bool(row["notnull"]),
                "default_value": row["dflt_value"],
                "primary_key": bool(row["pk"])
            }
            columns.append(column)
            
            if column["primary_key"]:
                primary_keys.append(column["name"])
                
        # Get foreign key information
        self.cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        foreign_keys = []
        
        for row in self.cursor.fetchall():
            foreign_key = {
                "column": row["from"],
                "references_table": row["table"],
                "references_column": row["to"]
            }
            foreign_keys.append(foreign_key)
            
        # Get index information
        self.cursor.execute(f"PRAGMA index_list({table_name})")
        indexes = []
        
        for idx_row in self.cursor.fetchall():
            idx_name = idx_row["name"]
            self.cursor.execute(f"PRAGMA index_info({idx_name})")
            idx_columns = [row["name"] for row in self.cursor.fetchall()]
            
            indexes.append({
                "name": idx_name,
                "columns": idx_columns,
                "unique": bool(idx_row["unique"])
            })
            
        # Get a row count (approximate for large tables)
        try:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table_name} LIMIT 1000")
            row_count = self.cursor.fetchone()[0]
            row_count_note = "" if row_count < 1000 else "+"
        except sqlite3.Error:
            row_count = 0
            row_count_note = ""
            
        # Store table information
        self.schema["tables"][table_name] = {
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "row_count": f"{row_count}{row_count_note}"
        }
        
    def _extract_relationships(self):
        """Extract relationships between tables based on foreign keys"""
        relationships = []
        
        for table_name, table_info in self.schema["tables"].items():
            for fk in table_info["foreign_keys"]:
                relationship = {
                    "from_table": table_name,
                    "from_column": fk["column"],
                    "to_table": fk["references_table"],
                    "to_column": fk["references_column"],
                    "relationship_type": self._determine_relationship_type(table_name, fk["references_table"])
                }
                relationships.append(relationship)
                
        self.schema["relationships"] = relationships
        
    def _determine_relationship_type(self, table1: str, table2: str) -> str:
        """
        Determine the type of relationship between two tables
        
        Args:
            table1: First table name
            table2: Second table name
            
        Returns:
            Relationship type (one-to-one, one-to-many, many-to-many)
        """
        # Check if table1 is a junction table
        if table1.startswith("Event") and table1 != "Events" and table1 != "EventMetadata":
            return "many-to-many"
            
        # Default assumption for most relationships in the Nova database
        return "one-to-many"
        
    def _categorize_tables(self):
        """Categorize tables as project-specific or application-level"""
        project_tables = []
        application_tables = []
        
        for table_name in self.schema["tables"].keys():
            # Logic to categorize tables
            if table_name in ["Events", "Characters", "Locations", "Entities", "Sources"]:
                project_tables.append(table_name)
            elif table_name.startswith("Event") or table_name.endswith("Occupations"):
                project_tables.append(table_name)
            else:
                application_tables.append(table_name)
                
        self.schema["project_tables"] = sorted(project_tables)
        self.schema["application_tables"] = sorted(application_tables)
        
    def _create_sample_queries(self):
        """Create sample queries showing how tables are used"""
        self.schema["sample_queries"] = {
            "events": {
                "get_all_events": """
                    SELECT EventID, EventDate, PublicationDate, EventTitle, QualityScore 
                    FROM Events
                    ORDER BY PublicationDate DESC
                """,
                "get_event_by_id": """
                    SELECT EventDate, PublicationDate, EventTitle, EventText, SourceType, SourceName, QualityScore
                    FROM Events 
                    WHERE EventID = ?
                """,
                "get_event_associations": """
                    -- Characters associated with an event
                    SELECT Characters.DisplayName
                    FROM Characters
                    JOIN EventCharacters ON Characters.CharacterID = EventCharacters.CharacterID
                    WHERE EventCharacters.EventID = ?
                    
                    -- Locations associated with an event
                    SELECT Locations.LocationName
                    FROM Locations
                    JOIN EventLocations ON Locations.LocationID = EventLocations.LocationID
                    WHERE EventLocations.EventID = ?
                    
                    -- Entities associated with an event
                    SELECT Entities.Name
                    FROM Entities
                    JOIN EventEntities ON Entities.EntityID = EventEntities.EntityID
                    WHERE EventEntities.EventID = ?
                """
            },
            "characters": {
                "get_articles_by_character": """
                    SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                    FROM Events e
                    JOIN EventCharacters ec ON e.EventID = ec.EventID
                    WHERE ec.CharacterID = ? AND e.Status = 'active'
                    ORDER BY e.PublicationDate DESC
                """,
                "get_character_by_id": """
                    SELECT * FROM Characters WHERE CharacterID = ?
                """,
                "get_character_occupations": """
                    SELECT l.DisplayName as location_name, lo.RoleType, 
                        lo.StartDate, lo.EndDate
                    FROM LocationOccupations lo
                    JOIN Locations l ON lo.LocationID = l.LocationID
                    WHERE lo.CharacterID = ?
                    ORDER BY lo.StartDate
                """
            },
            "locations": {
                "get_articles_by_location": """
                    SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                    FROM Events e
                    JOIN EventLocations ec ON e.EventID = ec.EventID
                    WHERE ec.LocationID = ? AND e.Status = 'active'
                    ORDER BY e.PublicationDate DESC
                """,
                "get_location_occupants": """
                    SELECT c.DisplayName as character_name, lo.RoleType,
                        lo.StartDate, lo.EndDate
                    FROM LocationOccupations lo
                    JOIN Characters c ON lo.CharacterID = c.CharacterID
                    WHERE lo.LocationID = ?
                    ORDER BY lo.RoleType, lo.StartDate
                """
            },
            "entities": {
                "get_articles_by_entity": """
                    SELECT e.PublicationDate, e.EventTitle, e.EventID, e.EventText
                    FROM Events e
                    JOIN EventEntities ec ON e.EventID = ec.EventID
                    WHERE ec.EntityID = ? AND e.Status = 'active'
                    ORDER BY e.PublicationDate DESC
                """,
                "update_known_members": """
                    -- First get the entity name
                    SELECT DisplayName FROM Entities WHERE EntityID = ?
                    
                    -- Find all characters with this entity in their Affiliations
                    SELECT DisplayName FROM Characters WHERE Affiliations LIKE ?
                    
                    -- Update the KnownMembers field
                    UPDATE Entities SET KnownMembers = ? WHERE EntityID = ?
                """
            }
        }
        
    def _analyze_project_structure(self):
        """Analyze how project separation is handled in the database"""
        self.schema["analysis"] = {
            "project_separation": """
The Nova database does not implement explicit project separation through schemas or prefixes. 
Instead, it uses a single database with all tables. Projects appear to be implicitly defined 
by the content of the Events, Characters, Locations, and Entities tables, possibly filtered 
by date ranges or other attributes.

The database follows a relational model with junction tables (EventCharacters, EventLocations, 
EventEntities) implementing many-to-many relationships between primary entities. This allows 
building complex narratives that span multiple entities.
""",
            "core_entities": """
The database is organized around these core entities:
1. Events - Newspaper articles or other historical events with dates and text content
2. Characters - Historical individuals with biographical information
3. Locations - Physical places with addresses and descriptions
4. Entities - Organizations or groups with establishment dates and affiliations
5. Sources - Newspapers or other publication sources of events

Each of these entities has relationships with the others, primarily through the Events table
which acts as a hub connecting Characters, Locations, and Entities together.
""",
            "temporal_model": """
The database includes various date fields (EventDate, PublicationDate, BirthDate, DeathDate, 
EstablishedDate, StartDate, EndDate) that enable temporal analysis and chronological ordering 
of records. This suggests the database is designed for historical research and narrative 
construction across time periods.

LocationOccupations is especially interesting as it tracks characters' relationships with
locations over time, including role types and date ranges, enabling temporal analysis of
character movements and occupations.
"""
        }
                
    def to_json(self) -> str:
        """
        Convert schema to JSON format
        
        Returns:
            JSON string representation of the schema
        """
        return json.dumps(self.schema, indent=2)
        
    def to_markdown(self) -> str:
        """
        Convert schema to Markdown format
        
        Returns:
            Markdown string representation of the schema
        """
        md = []
        
        # Database info
        md.append("# Nova Database Schema\n")
        db_info = self.schema["database_info"]
        md.append(f"**Database Path**: {db_info['path']}")
        md.append(f"**Size**: {db_info['size']:.2f} MB\n")
        
        # Table of contents
        md.append("## Table of Contents\n")
        md.append("1. [Tables](#tables)")
        for table_name in sorted(self.schema["tables"].keys()):
            md.append(f"   - [{table_name}](#{table_name.lower()})")
        md.append("2. [Relationships](#relationships)")
        md.append("3. [Sample Queries](#sample-queries)")
        md.append("4. [Database Analysis](#database-analysis)\n")
        
        # Tables
        md.append("## Tables\n")
        
        # Project tables first
        md.append("### Project Tables\n")
        for table_name in self.schema["project_tables"]:
            md.append(self._table_to_markdown(table_name))
            
        # Application tables
        if self.schema["application_tables"]:
            md.append("### Application Tables\n")
            for table_name in self.schema["application_tables"]:
                md.append(self._table_to_markdown(table_name))
        
        # Relationships
        md.append("## Relationships\n")
        md.append("| From Table | From Column | Relationship | To Table | To Column |")
        md.append("|------------|-------------|--------------|----------|-----------|")
        
        for rel in self.schema["relationships"]:
            rel_type = rel["relationship_type"]
            rel_symbol = "1:N" if rel_type == "one-to-many" else "M:N" if rel_type == "many-to-many" else "1:1"
            md.append(f"| {rel['from_table']} | {rel['from_column']} | {rel_symbol} | {rel['to_table']} | {rel['to_column']} |")
        
        md.append("")
        
        # Sample queries
        md.append("## Sample Queries\n")
        
        for entity, queries in self.schema["sample_queries"].items():
            md.append(f"### {entity.title()} Queries\n")
            
            for query_name, query_sql in queries.items():
                md.append(f"#### {query_name.replace('_', ' ').title()}")
                md.append("```sql")
                md.append(query_sql.strip())
                md.append("```\n")
        
        # Analysis
        md.append("## Database Analysis\n")
        
        for section, content in self.schema["analysis"].items():
            md.append(f"### {section.replace('_', ' ').title()}")
            md.append(content.strip())
            md.append("")
        
        return "\n".join(md)
    
    def _table_to_markdown(self, table_name: str) -> str:
        """
        Convert a table's schema to markdown format
        
        Args:
            table_name: Name of the table
            
        Returns:
            Markdown string for the table
        """
        md = []
        table_info = self.schema["tables"][table_name]
        
        md.append(f"### {table_name}")
        md.append(f"**Row count:** {table_info['row_count']}\n")
        
        # Primary key info
        if table_info["primary_keys"]:
            md.append(f"**Primary Key(s):** {', '.join(table_info['primary_keys'])}\n")
        
        # Columns
        md.append("| Column | Type | NOT NULL | Default | Primary Key |")
        md.append("|--------|------|----------|---------|-------------|")
        
        for col in table_info["columns"]:
            pk = "✓" if col["primary_key"] else ""
            not_null = "✓" if col["not_null"] else ""
            default = col["default_value"] if col["default_value"] is not None else ""
            md.append(f"| {col['name']} | {col['type']} | {not_null} | {default} | {pk} |")
        
        md.append("")
        
        # Foreign keys
        if table_info["foreign_keys"]:
            md.append("**Foreign Keys:**")
            for fk in table_info["foreign_keys"]:
                md.append(f"- {fk['column']} → {fk['references_table']}({fk['references_column']})")
            md.append("")
        
        # Indexes
        if table_info["indexes"]:
            md.append("**Indexes:**")
            for idx in table_info["indexes"]:
                unique = "UNIQUE " if idx["unique"] else ""
                md.append(f"- {unique}INDEX {idx['name']} ({', '.join(idx['columns'])})")
            md.append("")
            
        return "\n".join(md)
        
    def save_to_file(self, output_path: str, format: str = "markdown"):
        """
        Save the schema to a file
        
        Args:
            output_path: Path to save the output
            format: Format to use (json or markdown)
        """
        if format.lower() == "json":
            content = self.to_json()
        else:
            content = self.to_markdown()
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"Schema saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract and analyze Nova database schema")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown", 
                       help="Output format (default: markdown)")
    args = parser.parse_args()
    
    # Determine database path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "nova_database.db")
    
    if not os.path.exists(db_path):
        alt_path = "C:\\AI\\Nova\\src\\nova_database.db"
        if os.path.exists(alt_path):
            db_path = alt_path
        else:
            print(f"Error: Database not found at {db_path} or {alt_path}")
            print("Please specify the correct database path.")
            return 1
    
    # Determine output path
    if not args.output:
        ext = ".json" if args.format == "json" else ".md"
        args.output = os.path.join(script_dir, f"schema_output{ext}")
    
    # Extract schema
    extractor = DatabaseSchemaExtractor(db_path)
    if not extractor.extract_schema():
        return 1
        
    # Save to file
    extractor.save_to_file(args.output, args.format)
    
    # Clean up
    extractor.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())