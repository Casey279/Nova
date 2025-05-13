#!/usr/bin/env python3
"""
Newspaper Repository CLI - Command Line Interface for the Newspaper Repository System

This module provides a unified interface for interacting with the newspaper repository
components, allowing users to download, process, and query newspaper content.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import repository components
from repository.base_repository import RepositoryConfig, RepositoryError
from repository.database_manager import DatabaseManager
from repository.publication_repository import PublicationRepository
from repository.downloader import DownloadManager, ChroniclingAmericaDownloader
from repository.ocr_processor import OCRProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'newspaper_cli.log'))
    ]
)
logger = logging.getLogger('newspaper_cli')


class NewspaperCLI:
    """Command Line Interface for managing the newspaper repository."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the CLI with repository components.
        
        Args:
            config_path: Optional path to a configuration file
        """
        # Initialize configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        try:
            self.db_manager = DatabaseManager(
                db_path=self.config['database']['path'],
                enable_foreign_keys=True,
                pool_size=self.config['database'].get('pool_size', 5)
            )
            
            self.publication_repo = PublicationRepository(
                config=RepositoryConfig(
                    base_path=self.config['repository']['base_path'],
                    temp_path=self.config['repository']['temp_path']
                ),
                db_manager=self.db_manager
            )
            
            self.download_manager = DownloadManager(
                config=RepositoryConfig(
                    base_path=self.config['repository']['base_path'],
                    temp_path=self.config['repository']['temp_path']
                ),
                max_workers=self.config['downloader'].get('max_workers', 3),
                default_retry_attempts=self.config['downloader'].get('retry_attempts', 3)
            )
            
            # Register downloaders
            self.download_manager.register_downloader(
                'chroniclingamerica',
                ChroniclingAmericaDownloader(
                    api_key=self.config['downloaders']['chroniclingamerica'].get('api_key'),
                    base_url=self.config['downloaders']['chroniclingamerica'].get('base_url'),
                    rate_limit=self.config['downloaders']['chroniclingamerica'].get('rate_limit', 5)
                )
            )
            
            self.ocr_processor = OCRProcessor(
                config=RepositoryConfig(
                    base_path=self.config['repository']['base_path'],
                    temp_path=self.config['repository']['temp_path']
                ),
                publication_repo=self.publication_repo,
                max_workers=self.config['ocr'].get('max_workers', 2),
                use_gpu=self.config['ocr'].get('use_gpu', False)
            )
            
            logger.info("Newspaper CLI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Newspaper CLI: {str(e)}")
            raise
    
    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """
        Load configuration from file or use default values.
        
        Args:
            config_path: Path to configuration file (JSON or YAML)
            
        Returns:
            Configuration dictionary
        """
        # Default configuration
        default_config = {
            'database': {
                'path': os.path.join(os.path.dirname(__file__), 'newspaper_repository.db'),
                'pool_size': 5,
                'backup_directory': os.path.join(os.path.dirname(__file__), 'backups')
            },
            'repository': {
                'base_path': os.path.join(os.path.dirname(__file__), 'repository'),
                'temp_path': os.path.join(os.path.dirname(__file__), 'temp')
            },
            'downloader': {
                'max_workers': 3,
                'retry_attempts': 3
            },
            'downloaders': {
                'chroniclingamerica': {
                    'base_url': 'https://chroniclingamerica.loc.gov/api/',
                    'rate_limit': 5
                }
            },
            'ocr': {
                'max_workers': 2,
                'use_gpu': False,
                'engine': 'tesseract'
            }
        }
        
        if config_path:
            try:
                import json
                import yaml
                
                ext = os.path.splitext(config_path)[1].lower()
                with open(config_path, 'r') as f:
                    if ext == '.json':
                        user_config = json.load(f)
                    elif ext in ('.yaml', '.yml'):
                        user_config = yaml.safe_load(f)
                    else:
                        logger.warning(f"Unsupported config file extension: {ext}. Using default config.")
                        return default_config
                
                # Merge configurations (simple recursive update)
                self._deep_update(default_config, user_config)
                logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Failed to load config from {config_path}: {str(e)}")
                logger.warning("Using default configuration")
        
        return default_config
    
    def _deep_update(self, target: Dict, source: Dict) -> Dict:
        """
        Recursively update a dictionary.
        
        Args:
            target: Target dictionary to update
            source: Source dictionary with new values
            
        Returns:
            Updated dictionary
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value
        return target
    
    def setup_database(self, force_reset: bool = False) -> None:
        """
        Set up the database schema.
        
        Args:
            force_reset: If True, drop all tables and recreate them
        """
        try:
            if force_reset:
                logger.warning("Resetting database - all data will be lost")
                self.db_manager.reset_database()
            
            self.db_manager.initialize_database()
            logger.info("Database setup complete")
        except Exception as e:
            logger.error(f"Failed to set up database: {str(e)}")
            raise
    
    def download_publication(
        self, 
        source: str,
        publication_id: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        location: Optional[str] = None,
        max_items: Optional[int] = None
    ) -> None:
        """
        Download publication issues.
        
        Args:
            source: Source name (e.g., 'chroniclingamerica')
            publication_id: Publication identifier
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            location: Optional location filter
            max_items: Maximum number of items to download
        """
        try:
            # Parse dates if provided
            parsed_start_date = None
            parsed_end_date = None
            
            if start_date:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            
            if end_date:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # Get the appropriate downloader
            downloader = self.download_manager.get_downloader(source)
            if not downloader:
                raise ValueError(f"Downloader not found for source: {source}")
            
            # Create download task
            task_id = self.download_manager.add_task(
                downloader=source,
                publication_id=publication_id,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                location=location,
                max_items=max_items,
                priority=1
            )
            
            logger.info(f"Download task created with ID: {task_id}")
            logger.info("Starting download manager")
            
            # Start the download manager and wait for completion
            self.download_manager.start()
            self.download_manager.wait_for_completion()
            
            # Check task status
            task_status = self.download_manager.get_task_status(task_id)
            if task_status.status == 'completed':
                logger.info(f"Download completed successfully. Downloaded {task_status.items_processed} items.")
            else:
                logger.warning(f"Download task ended with status: {task_status.status}")
                if task_status.error:
                    logger.error(f"Error: {task_status.error}")
        
        except Exception as e:
            logger.error(f"Failed to download publication: {str(e)}")
            raise
    
    def process_publication(
        self,
        publication_id: str,
        issue_date: Optional[str] = None,
        reprocess: bool = False
    ) -> None:
        """
        Process downloaded publication issues with OCR.
        
        Args:
            publication_id: Publication identifier
            issue_date: Optional specific issue date to process (YYYY-MM-DD)
            reprocess: If True, reprocess already processed items
        """
        try:
            # Find downloaded issues that need processing
            issues = self.publication_repo.find_issues(
                publication_id=publication_id,
                issue_date=datetime.strptime(issue_date, "%Y-%m-%d").date() if issue_date else None,
                processed=not reprocess
            )
            
            if not issues:
                logger.warning(f"No {'unprocessed ' if not reprocess else ''}issues found for publication: {publication_id}")
                return
            
            logger.info(f"Found {len(issues)} issues to process")
            
            # Create OCR tasks for each issue
            for issue in issues:
                task_id = self.ocr_processor.add_task(
                    publication_id=publication_id,
                    issue_id=issue['id'],
                    priority=1
                )
                logger.info(f"Created OCR task {task_id} for issue {issue['id']}")
            
            # Start OCR processing and wait for completion
            logger.info("Starting OCR processing")
            self.ocr_processor.start()
            self.ocr_processor.wait_for_completion()
            
            logger.info("OCR processing completed")
            
        except Exception as e:
            logger.error(f"Failed to process publication: {str(e)}")
            raise
    
    def search_articles(
        self, 
        query: str,
        publication_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict]:
        """
        Search for articles in the repository.
        
        Args:
            query: Search query
            publication_id: Optional publication filter
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            location: Optional location filter
            limit: Maximum number of results
            offset: Result offset for pagination
            
        Returns:
            List of matching article dictionaries
        """
        try:
            # Parse dates if provided
            parsed_start_date = None
            parsed_end_date = None
            
            if start_date:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            
            if end_date:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # Perform search
            results = self.publication_repo.search_articles(
                query=query,
                publication_id=publication_id,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                location=location,
                limit=limit,
                offset=offset
            )
            
            logger.info(f"Search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search articles: {str(e)}")
            raise
    
    def list_publications(
        self,
        location: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        List publications in the repository.
        
        Args:
            location: Optional location filter
            source: Optional source filter
            limit: Maximum number of results
            offset: Result offset for pagination
            
        Returns:
            List of publication dictionaries
        """
        try:
            publications = self.publication_repo.find_publications(
                location=location,
                source=source,
                limit=limit,
                offset=offset
            )
            
            logger.info(f"Found {len(publications)} publications")
            return publications
            
        except Exception as e:
            logger.error(f"Failed to list publications: {str(e)}")
            raise
    
    def get_publication_statistics(self, publication_id: Optional[str] = None) -> Dict:
        """
        Get statistics for publications in the repository.
        
        Args:
            publication_id: Optional specific publication to get statistics for
            
        Returns:
            Dictionary of statistics
        """
        try:
            stats = self.publication_repo.get_statistics(publication_id=publication_id)
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get publication statistics: {str(e)}")
            raise
    
    def export_articles(
        self,
        output_path: str,
        publication_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = 'json'
    ) -> str:
        """
        Export articles to a file.
        
        Args:
            output_path: Path to output file or directory
            publication_id: Optional publication filter
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            format: Export format ('json', 'csv', 'txt')
            
        Returns:
            Path to the exported file
        """
        try:
            # Parse dates if provided
            parsed_start_date = None
            parsed_end_date = None
            
            if start_date:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            
            if end_date:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            # Check if output_path is a directory
            if os.path.isdir(output_path):
                filename = f"articles_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
                output_path = os.path.join(output_path, filename)
            
            # Get articles
            articles = self.publication_repo.find_articles(
                publication_id=publication_id,
                start_date=parsed_start_date,
                end_date=parsed_end_date
            )
            
            if not articles:
                logger.warning("No articles found matching criteria")
                return None
            
            # Export based on format
            if format == 'json':
                import json
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(articles, f, ensure_ascii=False, indent=2)
            
            elif format == 'csv':
                import csv
                # Flatten the structure for CSV
                flattened = []
                for article in articles:
                    flat_article = {
                        'id': article.get('id'),
                        'title': article.get('title'),
                        'publication_id': article.get('publication_id'),
                        'issue_date': article.get('issue_date'),
                        'page_number': article.get('page_number'),
                        'text': article.get('text', '').replace('\n', ' ')[:1000],  # Truncate text for CSV
                        'word_count': len(article.get('text', '').split())
                    }
                    flattened.append(flat_article)
                
                with open(output_path, 'w', encoding='utf-8', newline='') as f:
                    if flattened:
                        writer = csv.DictWriter(f, fieldnames=flattened[0].keys())
                        writer.writeheader()
                        writer.writerows(flattened)
            
            elif format == 'txt':
                with open(output_path, 'w', encoding='utf-8') as f:
                    for article in articles:
                        f.write(f"ID: {article.get('id')}\n")
                        f.write(f"Title: {article.get('title')}\n")
                        f.write(f"Publication: {article.get('publication_id')}\n")
                        f.write(f"Date: {article.get('issue_date')}\n")
                        f.write(f"Page: {article.get('page_number')}\n")
                        f.write("-" * 80 + "\n")
                        f.write(article.get('text', '') + "\n\n")
                        f.write("=" * 80 + "\n\n")
            
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            logger.info(f"Exported {len(articles)} articles to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to export articles: {str(e)}")
            raise
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Optional path for the backup file
            
        Returns:
            Path to the backup file
        """
        try:
            if not backup_path:
                backup_dir = self.config['database'].get('backup_directory', 
                                                        os.path.join(os.path.dirname(__file__), 'backups'))
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = os.path.join(backup_dir, f"newspaper_repo_backup_{timestamp}.db")
            
            self.db_manager.backup_database(backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to backup database: {str(e)}")
            raise


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description='Newspaper Repository CLI')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Set up the database')
    setup_parser.add_argument('--reset', action='store_true', help='Reset the database (CAUTION: all data will be lost)')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download publications')
    download_parser.add_argument('--source', required=True, help='Source to download from (e.g., chroniclingamerica)')
    download_parser.add_argument('--publication', required=True, help='Publication identifier')
    download_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    download_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    download_parser.add_argument('--location', help='Location filter')
    download_parser.add_argument('--max-items', type=int, help='Maximum number of items to download')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process publications with OCR')
    process_parser.add_argument('--publication', required=True, help='Publication identifier')
    process_parser.add_argument('--issue-date', help='Specific issue date to process (YYYY-MM-DD)')
    process_parser.add_argument('--reprocess', action='store_true', help='Reprocess already processed items')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for articles')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--publication', help='Publication filter')
    search_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    search_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    search_parser.add_argument('--location', help='Location filter')
    search_parser.add_argument('--limit', type=int, default=10, help='Maximum number of results')
    search_parser.add_argument('--offset', type=int, default=0, help='Result offset for pagination')
    
    # List publications command
    list_parser = subparsers.add_parser('list', help='List publications')
    list_parser.add_argument('--location', help='Location filter')
    list_parser.add_argument('--source', help='Source filter')
    list_parser.add_argument('--limit', type=int, default=50, help='Maximum number of results')
    list_parser.add_argument('--offset', type=int, default=0, help='Result offset for pagination')
    
    # Statistics command
    stats_parser = subparsers.add_parser('stats', help='Get publication statistics')
    stats_parser.add_argument('--publication', help='Publication identifier')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export articles')
    export_parser.add_argument('--output', required=True, help='Output file or directory')
    export_parser.add_argument('--publication', help='Publication filter')
    export_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    export_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    export_parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json', help='Export format')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup the database')
    backup_parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create CLI instance
    try:
        cli = NewspaperCLI(config_path=args.config)
        
        # Execute command
        if args.command == 'setup':
            cli.setup_database(force_reset=args.reset)
            print("Database setup complete")
        
        elif args.command == 'download':
            cli.download_publication(
                source=args.source,
                publication_id=args.publication,
                start_date=args.start_date,
                end_date=args.end_date,
                location=args.location,
                max_items=args.max_items
            )
            print("Download complete")
        
        elif args.command == 'process':
            cli.process_publication(
                publication_id=args.publication,
                issue_date=args.issue_date,
                reprocess=args.reprocess
            )
            print("Processing complete")
        
        elif args.command == 'search':
            results = cli.search_articles(
                query=args.query,
                publication_id=args.publication,
                start_date=args.start_date,
                end_date=args.end_date,
                location=args.location,
                limit=args.limit,
                offset=args.offset
            )
            
            print(f"Found {len(results)} results:")
            for i, article in enumerate(results, 1):
                print(f"{i}. {article.get('title', 'Untitled')} - "
                      f"{article.get('publication_id')} "
                      f"({article.get('issue_date')}), "
                      f"Page {article.get('page_number')}")
                if 'text' in article:
                    preview = article['text'].replace('\n', ' ')[:100]
                    print(f"   {preview}...")
                print()
        
        elif args.command == 'list':
            publications = cli.list_publications(
                location=args.location,
                source=args.source,
                limit=args.limit,
                offset=args.offset
            )
            
            print(f"Found {len(publications)} publications:")
            for i, pub in enumerate(publications, 1):
                print(f"{i}. {pub.get('title', 'Untitled')} "
                      f"({pub.get('id')}) - "
                      f"{pub.get('location', 'Unknown location')}")
                if 'date_range' in pub:
                    print(f"   {pub['date_range'].get('start')} to {pub['date_range'].get('end')}")
                print()
        
        elif args.command == 'stats':
            stats = cli.get_publication_statistics(publication_id=args.publication)
            
            print("Publication Statistics:")
            print("-" * 50)
            
            if 'publications' in stats:
                print(f"Total Publications: {stats['publications']['count']}")
            
            if 'issues' in stats:
                print(f"Total Issues: {stats['issues']['count']}")
                print(f"Date Range: {stats['issues'].get('start_date')} to {stats['issues'].get('end_date')}")
            
            if 'pages' in stats:
                print(f"Total Pages: {stats['pages']['count']}")
                print(f"Processed Pages: {stats['pages'].get('processed', 0)} "
                      f"({stats['pages'].get('processed_percentage', 0):.1f}%)")
            
            if 'articles' in stats:
                print(f"Total Articles: {stats['articles']['count']}")
                if 'word_count' in stats['articles']:
                    print(f"Total Words: {stats['articles']['word_count']:,}")
                    print(f"Average Words per Article: {stats['articles'].get('avg_word_count', 0):.1f}")
        
        elif args.command == 'export':
            output_path = cli.export_articles(
                output_path=args.output,
                publication_id=args.publication,
                start_date=args.start_date,
                end_date=args.end_date,
                format=args.format
            )
            
            if output_path:
                print(f"Exported articles to {output_path}")
            else:
                print("No articles found matching criteria")
        
        elif args.command == 'backup':
            backup_path = cli.backup_database(backup_path=args.output)
            print(f"Database backed up to {backup_path}")
        
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"Error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()