"""
Tests for the ChroniclingAmerica API client.

This module provides tests for the ChroniclingAmerica API client.
"""

import unittest
import os
import tempfile
import shutil
from datetime import date
from unittest.mock import Mock, patch

from chronicling_america import (
    ChroniclingAmericaClient,
    NewspaperMetadata, 
    PageMetadata
)

class TestChroniclingAmericaClient(unittest.TestCase):
    """Test cases for the ChroniclingAmerica API client."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for test downloads
        self.temp_dir = tempfile.mkdtemp()
        self.client = ChroniclingAmericaClient(output_directory=self.temp_dir)
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
    
    @patch('chronicling_america.requests.get')
    def test_search_newspapers(self, mock_get):
        """Test searching for newspapers."""
        # Mock the API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'newspapers': [
                {
                    'lccn': 'sn86069873',
                    'title': 'New York Tribune',
                    'place_of_publication': 'New York, N.Y.',
                    'start_year': 1841,
                    'end_year': 1924,
                    'url': 'https://chroniclingamerica.loc.gov/lccn/sn86069873/',
                    'publisher': 'Tribune Association',
                    'language': ['English']
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Call the method
        results = self.client.search_newspapers(state='New York')
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].lccn, 'sn86069873')
        self.assertEqual(results[0].title, 'New York Tribune')
        self.assertEqual(results[0].start_year, 1841)
        self.assertEqual(results[0].end_year, 1924)
    
    @patch('chronicling_america.requests.get')
    def test_search_pages(self, mock_get):
        """Test searching for newspaper pages."""
        # Mock the API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'totalItems': 100,
            'items': [
                {
                    'lccn': 'sn86069873',
                    'date': '1900-01-01',
                    'edition': None,
                    'sequence': 1,
                    'url': 'https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1/',
                    'jp2_url': 'https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1.jp2',
                    'pdf_url': 'https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1.pdf',
                    'ocr_url': 'https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1/ocr.txt',
                    'title': 'New York Tribune',
                    'page_number': '1'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Call the method
        pages, pagination = self.client.search_pages(
            keywords='lincoln',
            date_start='1900-01-01',
            date_end='1900-01-31'
        )
        
        # Verify results
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].lccn, 'sn86069873')
        self.assertEqual(pages[0].issue_date, date(1900, 1, 1))
        self.assertEqual(pages[0].sequence, 1)
        self.assertEqual(pagination['total_items'], 100)
    
    @patch('chronicling_america.requests.get')
    @patch('chronicling_america.ChroniclingAmericaClient._download_file')
    def test_download_page_content(self, mock_download, mock_get):
        """Test downloading page content."""
        # Mock the download function
        mock_download.side_effect = lambda url, output_path, save_file: output_path if save_file else None
        
        # Create a test page metadata object
        page = PageMetadata(
            lccn='sn86069873',
            issue_date=date(1900, 1, 1),
            edition=None,
            sequence=1,
            url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1/',
            jp2_url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1.jp2',
            pdf_url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1.pdf',
            ocr_url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1/ocr.txt',
            title='New York Tribune'
        )
        
        # Call the method
        result = self.client.download_page_content(page, formats=['pdf', 'jp2'])
        
        # Verify results
        self.assertIn('pdf', result)
        self.assertIn('jp2', result)
        self.assertIn(self.temp_dir, result['pdf'])
        self.assertIn(self.temp_dir, result['jp2'])
        self.assertTrue(result['pdf'].endswith('.pdf'))
        self.assertTrue(result['jp2'].endswith('.jp2'))
    
    @patch('chronicling_america.ChroniclingAmericaClient.search_pages')
    @patch('chronicling_america.ChroniclingAmericaClient.batch_download_pages')
    def test_search_and_download(self, mock_batch_download, mock_search):
        """Test searching and downloading in one operation."""
        # Mock the search function
        page = PageMetadata(
            lccn='sn86069873',
            issue_date=date(1900, 1, 1),
            edition=None,
            sequence=1,
            url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1/',
            jp2_url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1.jp2',
            pdf_url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1.pdf',
            ocr_url='https://chroniclingamerica.loc.gov/lccn/sn86069873/1900-01-01/ed-1/seq-1/ocr.txt',
            title='New York Tribune'
        )
        mock_search.return_value = ([page], {'total_items': 1, 'total_pages': 1, 'current_page': 1})
        
        # Mock the batch download function
        mock_batch_download.return_value = [
            {
                'pdf': os.path.join(self.temp_dir, 'pdf', 'sn86069873_19000101_seq1.pdf'),
                'jp2': os.path.join(self.temp_dir, 'jp2', 'sn86069873_19000101_seq1.jp2'),
                'metadata': {
                    'lccn': 'sn86069873',
                    'issue_date': '1900-01-01',
                    'sequence': 1,
                    'title': 'New York Tribune'
                }
            }
        ]
        
        # Call the method
        results = self.client.search_and_download(
            keywords='lincoln',
            date_start='1900-01-01',
            date_end='1900-01-31',
            formats=['pdf', 'jp2']
        )
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertIn('pdf', results[0])
        self.assertIn('jp2', results[0])
        self.assertIn('metadata', results[0])
    
    def test_integrate_with_repository(self):
        """Test integration with the newspaper repository."""
        # Create a mock repository manager
        mock_repo = Mock()
        mock_repo.add_newspaper_page.return_value = 'page_123'
        
        # Create test download results
        download_results = [
            {
                'pdf': os.path.join(self.temp_dir, 'pdf', 'sn86069873_19000101_seq1.pdf'),
                'ocr': os.path.join(self.temp_dir, 'ocr', 'sn86069873_19000101_seq1.txt'),
                'json': os.path.join(self.temp_dir, 'json', 'sn86069873_19000101_seq1.json'),
                'metadata': {
                    'lccn': 'sn86069873',
                    'issue_date': '1900-01-01',
                    'sequence': 1,
                    'title': 'New York Tribune'
                }
            }
        ]
        
        # Create a JSON file to test parsing
        os.makedirs(os.path.dirname(download_results[0]['json']), exist_ok=True)
        with open(download_results[0]['json'], 'w') as f:
            f.write('{"title": {"name": "New York Tribune"}, "date_issued": "1900-01-01", "publisher": "Tribune Association", "place_of_publication": [{"name": "New York, N.Y."}]}')
        
        # Call the method
        results = self.client.integrate_with_repository(download_results, mock_repo)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], 'page_123')
        mock_repo.add_newspaper_page.assert_called_once()


if __name__ == '__main__':
    unittest.main()