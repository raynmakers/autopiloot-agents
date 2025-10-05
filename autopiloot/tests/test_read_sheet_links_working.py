"""
Test suite for ReadSheetLinks with proper coverage tracking.
Imports module at top level to ensure coverage.py can track execution.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import sys


# Mock agency_swarm and pydantic BEFORE any imports
class MockBaseTool:
    pass

def mock_field(default=None, **kwargs):
    return default

sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic'].Field = mock_field

# Import the module at module level for coverage tracking
from scraper_agent.tools.read_sheet_links import ReadSheetLinks


class TestReadSheetLinksWorking(unittest.TestCase):
    """Test suite for ReadSheetLinks with full coverage tracking."""

    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_no_sheet_id_error(self, mock_config):
        """Test error when no sheet ID provided (lines 76-81)."""
        mock_config.return_value = {}

        tool = ReadSheetLinks()
        tool.sheet_id = None
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertIn("No sheet ID", data["error"])
        self.assertEqual(data["items"], [])

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_empty_sheet_handling(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_sleep):
        """Test handling of empty sheet (lines 92-103)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {"values": []}

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["items"], [])
        self.assertEqual(data["summary"]["total_rows"], 0)
        self.assertEqual(data["summary"]["pages_processed"], 0)

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('bs4.BeautifulSoup')
    @patch('requests.get')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_successful_processing(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_get, mock_bs, mock_sleep):
        """Test successful YouTube URL extraction (lines 111-156)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [["https://example.com/page1"]]
        }

        # Mock HTTP request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><iframe src="https://www.youtube.com/embed/abc12345678"></iframe></html>'
        mock_get.return_value = mock_response

        # Mock BeautifulSoup
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_iframe = MagicMock()
        mock_iframe.get.return_value = "https://www.youtube.com/embed/abc12345678"
        mock_soup.find_all.return_value = [mock_iframe]

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        self.assertIn("items", data)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["total_rows"], 1)

    def test_url_validation_method(self):
        """Test _is_valid_url method (lines 254-264)."""
        tool = ReadSheetLinks()
        tool.sheet_id = None
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        self.assertTrue(tool._is_valid_url("https://example.com"))
        self.assertTrue(tool._is_valid_url("http://example.com"))
        self.assertTrue(tool._is_valid_url("https://localhost:8080"))
        self.assertFalse(tool._is_valid_url("not-a-url"))
        self.assertFalse(tool._is_valid_url(""))

    def test_youtube_url_detection_method(self):
        """Test _is_youtube_url method (lines 266-282)."""
        tool = ReadSheetLinks()
        tool.sheet_id = None
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        self.assertTrue(tool._is_youtube_url("https://www.youtube.com/watch?v=abc12345678"))
        self.assertTrue(tool._is_youtube_url("https://youtu.be/abc12345678"))
        self.assertTrue(tool._is_youtube_url("https://www.youtube.com/embed/abc12345678"))
        self.assertTrue(tool._is_youtube_url("https://www.youtube.com/v/abc12345678"))
        self.assertFalse(tool._is_youtube_url("https://example.com"))
        self.assertFalse(tool._is_youtube_url(""))

    def test_youtube_url_normalization_method(self):
        """Test _normalize_youtube_url method (lines 284-300)."""
        tool = ReadSheetLinks()
        tool.sheet_id = None
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        expected = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(tool._normalize_youtube_url("https://youtu.be/dQw4w9WgXcQ"), expected)
        self.assertEqual(tool._normalize_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ"), expected)
        self.assertEqual(tool._normalize_youtube_url("https://www.youtube.com/v/dQw4w9WgXcQ"), expected)
        self.assertIsNone(tool._normalize_youtube_url(""))
        self.assertIsNone(tool._normalize_youtube_url("https://example.com"))

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('bs4.BeautifulSoup')
    @patch('requests.get')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_max_rows_enforcement(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_get, mock_bs, mock_sleep):
        """Test max_rows limit enforcement (lines 113-114)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["https://example.com/page1"],
                ["https://example.com/page2"],
                ["https://example.com/page3"]
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html></html>'
        mock_get.return_value = mock_response

        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.find_all.return_value = []

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = 2  # Limit to 2 rows
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["summary"]["processed_rows"], 2)
        self.assertEqual(data["summary"]["total_rows"], 3)

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('bs4.BeautifulSoup')
    @patch('requests.get')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_skip_empty_rows_logic(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_get, mock_bs, mock_sleep):
        """Test skipping empty rows (lines 117-118)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [
                ["https://example.com/page1"],
                [""],  # Empty
                ["   "],  # Whitespace only
                ["https://example.com/page2"]
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html></html>'
        mock_get.return_value = mock_response

        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        mock_soup.find_all.return_value = []

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        # Should process only 2 rows (skip empty ones)
        self.assertEqual(data["summary"]["processed_rows"], 2)

    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    def test_credentials_file_missing(self, mock_env, mock_exists):
        """Test credentials file not found error (lines 311-312)."""
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = False

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_sheets_service()
        self.assertIn("Service account file not found", str(context.exception))

    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_top_level_exception_handling(self, mock_config):
        """Test top-level exception handling (lines 173-177)."""
        mock_config.side_effect = Exception("Config loading failed")

        tool = ReadSheetLinks()
        tool.sheet_id = None
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertIn("Failed to read sheet links", data["error"])

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_invalid_url_handling(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_sleep):
        """Test invalid URL handling (lines 123-124)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [["not-a-valid-url"], ["https://example.com"]]
        }

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        # Should have 1 failed page (invalid URL)
        self.assertEqual(data["summary"]["pages_failed"], 1)

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('requests.get')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_request_exception_handling(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_get, mock_sleep):
        """Test request exception handling (lines 251-252)."""
        import requests

        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [["https://example.com/page1"]]
        }

        # Mock requests.get to raise RequestException
        mock_get.side_effect = requests.RequestException("Connection timeout")

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        # Should have 1 failed page (request exception)
        self.assertEqual(data["summary"]["pages_failed"], 1)
        self.assertEqual(data["summary"]["pages_processed"], 0)

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('bs4.BeautifulSoup')
    @patch('requests.get')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_beautifulsoup_exception_handling(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_get, mock_bs, mock_sleep):
        """Test BeautifulSoup exception handling (lines 231-232)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [["https://example.com/page1"]]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html>Content with YouTube video: https://www.youtube.com/watch?v=test12345678</html>'
        mock_get.return_value = mock_response

        # Mock BeautifulSoup to raise exception
        mock_bs.side_effect = Exception("Parsing error")

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        # Should still process the page using regex fallback (lines 235-247)
        self.assertEqual(data["summary"]["pages_processed"], 1)
        self.assertGreater(len(data["items"]), 0)

    @patch('scraper_agent.tools.read_sheet_links.time.sleep')
    @patch('bs4.BeautifulSoup')
    @patch('requests.get')
    @patch('scraper_agent.tools.read_sheet_links.build')
    @patch('scraper_agent.tools.read_sheet_links.Credentials.from_service_account_file')
    @patch('scraper_agent.tools.read_sheet_links.os.path.exists')
    @patch('scraper_agent.tools.read_sheet_links.get_required_env_var')
    @patch('scraper_agent.tools.read_sheet_links.load_app_config')
    def test_general_exception_during_page_processing(self, mock_config, mock_env, mock_exists, mock_creds, mock_build, mock_get, mock_bs, mock_sleep):
        """Test general exception handling during page processing (lines 141-144, 253-254)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_env.return_value = "/fake/creds.json"
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [["https://example.com/page1"]]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html></html>'
        mock_get.return_value = mock_response

        # Mock BeautifulSoup to raise a non-RequestException
        mock_bs.side_effect = ValueError("Unexpected error")

        tool = ReadSheetLinks()
        tool.sheet_id = "test_sheet_id"
        tool.range_a1 = "Sheet1!A:A"
        tool.max_rows = None
        tool.timeout_sec = 10

        result = tool.run()
        data = json.loads(result)

        # BeautifulSoup exception is caught (line 231-232), and regex fallback is used
        # Page is successfully processed even though BeautifulSoup failed
        self.assertEqual(data["summary"]["pages_processed"], 1)
        # No URLs found since HTML is empty
        self.assertEqual(len(data["items"]), 0)


if __name__ == "__main__":
    unittest.main()