"""
Test suite for ReadSheetLinksSimple tool.
Tests YouTube URL extraction from Google Sheets functionality.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scraper', 'tools'))

try:
    from scraper.tools.ReadSheetLinksSimple import ReadSheetLinksSimple
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'scraper', 
        'tools', 
        'ReadSheetLinksSimple.py'
    )
    spec = importlib.util.spec_from_file_location("ReadSheetLinksSimple", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ReadSheetLinksSimple = module.ReadSheetLinksSimple


class TestReadSheetLinksSimple(unittest.TestCase):
    """Test cases for ReadSheetLinksSimple tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.tool = ReadSheetLinksSimple()

    @patch('scraper.tools.ReadSheetLinksSimple.load_app_config')
    @patch('scraper.tools.ReadSheetLinksSimple.get_required_var')
    @patch('scraper.tools.ReadSheetLinksSimple.build')
    def test_run_with_valid_youtube_urls(self, mock_build, mock_get_required_var, mock_config):
        """Test successful extraction of YouTube URLs from sheet."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API response
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_values = [
            ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            ["https://youtu.be/jNQXAC9IVRw"],
            ["https://www.youtube.com/embed/M7lc1UVf-VE"],
            ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],  # Duplicate
            ["invalid-url"],  # Invalid URL
            [""],  # Empty row
        ]
        
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': mock_values
        }
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('items', data)
        self.assertIn('summary', data)
        
        # Should have 3 unique valid URLs
        self.assertEqual(len(data['items']), 3)
        
        # Check that URLs are properly formatted
        expected_urls = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw", 
            "https://www.youtube.com/watch?v=M7lc1UVf-VE"
        }
        
        actual_urls = {item['video_url'] for item in data['items']}
        self.assertEqual(actual_urls, expected_urls)
        
        # Check summary
        self.assertEqual(data['summary']['total_rows'], 6)
        self.assertEqual(data['summary']['valid_urls'], 3)
        self.assertEqual(data['summary']['invalid_urls'], 1)

    @patch('scraper.tools.ReadSheetLinksSimple.load_app_config')
    def test_run_without_sheet_id(self, mock_config):
        """Test behavior when no sheet ID is configured."""
        mock_config.return_value = {}
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('items', data)
        self.assertEqual(len(data['items']), 0)

    @patch('scraper.tools.ReadSheetLinksSimple.load_app_config')
    @patch('scraper.tools.ReadSheetLinksSimple.get_required_var')
    @patch('scraper.tools.ReadSheetLinksSimple.build')
    def test_run_with_empty_sheet(self, mock_build, mock_get_required_var, mock_config):
        """Test behavior with empty sheet."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_var.return_value = "/fake/credentials.json"
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {'values': []}
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('items', data)
        self.assertIn('summary', data)
        self.assertEqual(len(data['items']), 0)
        self.assertEqual(data['summary']['total_rows'], 0)

    @patch('scraper.tools.ReadSheetLinksSimple.load_app_config')
    @patch('scraper.tools.ReadSheetLinksSimple.get_required_var')
    @patch('scraper.tools.ReadSheetLinksSimple.build')
    def test_run_with_max_rows_limit(self, mock_build, mock_get_required_var, mock_config):
        """Test max_rows limiting functionality."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_var.return_value = "/fake/credentials.json"
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # More URLs than max_rows limit
        mock_values = [
            ["https://www.youtube.com/watch?v=url1"],
            ["https://www.youtube.com/watch?v=url2"],
            ["https://www.youtube.com/watch?v=url3"],
            ["https://www.youtube.com/watch?v=url4"],
            ["https://www.youtube.com/watch?v=url5"],
        ]
        
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': mock_values
        }
        
        # Test with max_rows=3
        tool_with_limit = ReadSheetLinksSimple(max_rows=3)
        result = tool_with_limit.run()
        data = json.loads(result)
        
        # Should only process first 3 rows
        self.assertEqual(len(data['items']), 3)
        self.assertEqual(data['summary']['processed_rows'], 3)

    def test_is_youtube_url_validation(self):
        """Test YouTube URL validation patterns."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/v/dQw4w9WgXcQ",
            "youtube.com/watch?v=dQw4w9WgXcQ",
            "youtu.be/dQw4w9WgXcQ",
        ]
        
        invalid_urls = [
            "https://www.google.com",
            "not a url",
            "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw",
            "https://www.youtube.com/playlist?list=PLcMHoF3b5hEh",
            "",
        ]
        
        for url in valid_urls:
            self.assertTrue(self.tool._is_youtube_url(url), f"Should be valid: {url}")
            
        for url in invalid_urls:
            self.assertFalse(self.tool._is_youtube_url(url), f"Should be invalid: {url}")

    def test_normalize_youtube_url(self):
        """Test YouTube URL normalization to standard format."""
        test_cases = [
            ("https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ]
        
        for input_url, expected_output in test_cases:
            normalized = self.tool._normalize_youtube_url(input_url)
            self.assertEqual(normalized, expected_output, 
                           f"Failed to normalize {input_url} -> {expected_output}, got {normalized}")

    @patch('scraper.tools.ReadSheetLinksSimple.load_app_config')
    @patch('scraper.tools.ReadSheetLinksSimple.get_required_var')
    @patch('scraper.tools.ReadSheetLinksSimple.build')
    def test_error_handling(self, mock_build, mock_get_required_var, mock_config):
        """Test error handling in the tool."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_var.return_value = "/fake/credentials.json"
        
        # Mock an exception in the Sheets API call
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.side_effect = Exception("API Error")
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('API Error', data['error'])
        self.assertIn('items', data)
        self.assertEqual(len(data['items']), 0)

    def test_custom_parameters(self):
        """Test tool with custom parameters."""
        tool = ReadSheetLinksSimple(
            sheet_id="custom_sheet_id",
            range_a1="Sheet2!B:B",
            max_rows=10
        )
        
        self.assertEqual(tool.sheet_id, "custom_sheet_id")
        self.assertEqual(tool.range_a1, "Sheet2!B:B")
        self.assertEqual(tool.max_rows, 10)

    @patch('scraper.tools.ReadSheetLinksSimple.load_app_config')
    @patch('scraper.tools.ReadSheetLinksSimple.get_required_var')
    @patch('scraper.tools.ReadSheetLinksSimple.build')
    def test_deduplication(self, mock_build, mock_get_required_var, mock_config):
        """Test URL deduplication functionality."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_var.return_value = "/fake/credentials.json"
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Multiple duplicate URLs in different formats
        mock_values = [
            ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            ["https://youtu.be/dQw4w9WgXcQ"],  # Same video, different format
            ["https://www.youtube.com/embed/dQw4w9WgXcQ"],  # Same video, embed format
            ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s"],  # Same video with timestamp
        ]
        
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': mock_values
        }
        
        result = self.tool.run()
        data = json.loads(result)
        
        # Should deduplicate to single URL
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['video_url'], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")


if __name__ == '__main__':
    unittest.main(verbosity=2)