"""
Test suite for ReadSheetLinks tool.
Tests reading page links from Google Sheets and extracting YouTube URLs from those pages.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
import sys
import requests

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from scraper_agent.tools.ReadSheetLinks import ReadSheetLinks
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'scraper_agent', 
        'tools', 
        'ReadSheetLinks.py'
    )
    spec = importlib.util.spec_from_file_location("ReadSheetLinks", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ReadSheetLinks = module.ReadSheetLinks


class TestReadSheetLinks(unittest.TestCase):
    """Test cases for ReadSheetLinks tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.tool = ReadSheetLinks()

    @patch('scraper_agent.tools.ReadSheetLinks.load_app_config')
    @patch('scraper_agent.tools.ReadSheetLinks.get_required_env_var')
    @patch('scraper_agent.tools.ReadSheetLinks.build')
    @patch('scraper_agent.tools.ReadSheetLinks.requests.get')
    @patch('scraper_agent.tools.ReadSheetLinks.os.path.exists')
    @patch('scraper_agent.tools.ReadSheetLinks.Credentials.from_service_account_file')
    def test_run_with_page_containing_youtube_urls(self, mock_credentials, mock_exists, mock_requests, mock_build, mock_get_required_env_var, mock_config):
        """Test successful extraction of YouTube URLs from web pages."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        mock_exists.return_value = True
        mock_credentials.return_value = MagicMock()
        
        # Mock Google Sheets API response with page URLs
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_response = {
            'values': [
                ['https://example.com/blog-post-1'],
                ['https://example.com/blog-post-2']
            ]
        }
        mock_service.spreadsheets().values().get().execute.return_value = mock_response
        
        # Mock HTTP responses with embedded YouTube URLs
        mock_html_1 = '''
        <html>
        <body>
            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>
            <a href="https://youtu.be/jNQXAC9IVRw">Video Link</a>
        </body>
        </html>
        '''
        
        mock_html_2 = '''
        <html>
        <body>
            <p>Check out this video: https://www.youtube.com/watch?v=9bZkp7q19f0</p>
            <meta property="og:video" content="https://www.youtube.com/watch?v=ScMzIvxBSi4" />
        </body>
        </html>
        '''
        
        # Mock requests.get to return different HTML for different URLs
        def mock_get(url, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            if 'blog-post-1' in url:
                mock_response.text = mock_html_1
            elif 'blog-post-2' in url:
                mock_response.text = mock_html_2
            else:
                mock_response.text = "<html></html>"
            return mock_response
        
        mock_requests.side_effect = mock_get
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        # Should find YouTube URLs from both pages
        self.assertNotIn("error", data)
        self.assertIn("items", data)
        self.assertGreater(len(data["items"]), 0)
        
        # Check that items have both source_page_url and video_url
        for item in data["items"]:
            self.assertIn("source_page_url", item)
            self.assertIn("video_url", item)
            self.assertTrue(item["source_page_url"].startswith("https://example.com/blog-post"))
            self.assertTrue("youtube.com/watch?v=" in item["video_url"])
        
        # Check summary
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["pages_processed"], 2)
        self.assertGreater(data["summary"]["youtube_urls_found"], 0)

    @patch('scraper_agent.tools.ReadSheetLinks.load_app_config')
    @patch('scraper_agent.tools.ReadSheetLinks.get_required_env_var')
    @patch('scraper_agent.tools.ReadSheetLinks.build')
    @patch('scraper_agent.tools.ReadSheetLinks.os.path.exists')
    @patch('scraper_agent.tools.ReadSheetLinks.Credentials.from_service_account_file')
    def test_run_with_empty_sheet(self, mock_credentials, mock_exists, mock_build, mock_get_required_env_var, mock_config):
        """Test handling of empty Google Sheet."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        mock_exists.return_value = True
        mock_credentials.return_value = MagicMock()
        
        # Mock Google Sheets API response with no values
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {'values': []}
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertEqual(len(data["items"]), 0)
        self.assertEqual(data["summary"]["total_rows"], 0)
        self.assertEqual(data["summary"]["pages_processed"], 0)
        self.assertEqual(data["summary"]["youtube_urls_found"], 0)

    @patch('scraper_agent.tools.ReadSheetLinks.load_app_config')
    def test_run_with_no_sheet_id_configured(self, mock_config):
        """Test handling when no sheet ID is configured."""
        # Mock configuration without sheet ID
        mock_config.return_value = {}
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("No sheet ID provided", data["error"])
        self.assertEqual(len(data["items"]), 0)

    @patch('scraper_agent.tools.ReadSheetLinks.load_app_config')
    @patch('scraper_agent.tools.ReadSheetLinks.get_required_env_var')
    @patch('scraper_agent.tools.ReadSheetLinks.build')
    @patch('scraper_agent.tools.ReadSheetLinks.requests.get')
    @patch('scraper_agent.tools.ReadSheetLinks.os.path.exists')
    @patch('scraper_agent.tools.ReadSheetLinks.Credentials.from_service_account_file')
    def test_run_with_invalid_page_urls(self, mock_credentials, mock_exists, mock_requests, mock_build, mock_get_required_env_var, mock_config):
        """Test handling of invalid page URLs in sheet."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        mock_exists.return_value = True
        mock_credentials.return_value = MagicMock()
        
        # Mock Google Sheets API response with invalid URLs
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_response = {
            'values': [
                ['not-a-valid-url'],
                ['https://valid-url.com/page']
            ]
        }
        mock_service.spreadsheets().values().get().execute.return_value = mock_response
        
        # Mock HTTP response for valid URL (no YouTube content)
        mock_html = '<html><body>No YouTube content here</body></html>'
        mock_http_response = Mock()
        mock_http_response.raise_for_status = Mock()
        mock_http_response.text = mock_html
        mock_requests.return_value = mock_http_response
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertIn("summary", data)
        # Should process 1 valid page (invalid URL should be skipped)
        self.assertEqual(data["summary"]["pages_processed"], 1)
        self.assertEqual(data["summary"]["pages_failed"], 1)

    @patch('scraper_agent.tools.ReadSheetLinks.load_app_config')
    @patch('scraper_agent.tools.ReadSheetLinks.get_required_env_var')  
    @patch('scraper_agent.tools.ReadSheetLinks.build')
    @patch('scraper_agent.tools.ReadSheetLinks.requests.get')
    @patch('scraper_agent.tools.ReadSheetLinks.os.path.exists')
    @patch('scraper_agent.tools.ReadSheetLinks.Credentials.from_service_account_file')
    def test_run_with_request_failures(self, mock_credentials, mock_exists, mock_requests, mock_build, mock_get_required_env_var, mock_config):
        """Test handling of HTTP request failures."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        mock_exists.return_value = True
        mock_credentials.return_value = MagicMock()
        
        # Mock Google Sheets API response
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_response = {
            'values': [
                ['https://failing-url.com/page']
            ]
        }
        mock_service.spreadsheets().values().get().execute.return_value = mock_response
        
        # Mock HTTP request failure
        mock_requests.side_effect = requests.RequestException("Connection failed")
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["pages_processed"], 0)
        self.assertEqual(data["summary"]["pages_failed"], 1)

    def test_normalize_youtube_url(self):
        """Test YouTube URL normalization functionality."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("invalid-url", None),
            ("", None),
            (None, None)
        ]
        
        for input_url, expected in test_cases:
            with self.subTest(input_url=input_url):
                result = self.tool._normalize_youtube_url(input_url)
                self.assertEqual(result, expected)

    def test_is_youtube_url(self):
        """Test YouTube URL detection functionality."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "http://youtube.com/watch?v=dQw4w9WgXcQ",
            "youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        
        invalid_urls = [
            "https://example.com",
            "https://vimeo.com/123456",
            "not-a-url",
            "",
            None
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(self.tool._is_youtube_url(url))
        
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.tool._is_youtube_url(url))

    def test_is_valid_url(self):
        """Test URL validation functionality."""
        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "https://sub.domain.com:8080/path?param=value",
            "http://localhost:3000",
            "https://192.168.1.1"
        ]
        
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "just-text",
            "",
            "https://",
            "http://"
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(self.tool._is_valid_url(url))
        
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.tool._is_valid_url(url))


if __name__ == '__main__':
    unittest.main()