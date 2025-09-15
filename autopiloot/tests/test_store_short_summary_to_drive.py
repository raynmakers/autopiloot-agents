"""
Test suite for StoreShortSummaryToDrive tool.
Tests Google Drive integration, dual format storage, and file management.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from summarizer_agent.tools.store_short_summary_to_drive import StoreShortSummaryToDrive
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'store_short_summary_to_drive.py'
    )
    spec = importlib.util.spec_from_file_location("store_short_summary_to_drive", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    StoreShortSummaryToDrive = module.StoreShortSummaryToDrive


class TestStoreShortSummaryToDrive(unittest.TestCase):
    """Test cases for StoreShortSummaryToDrive tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_summary = {
            "bullets": [
                "Focus on understanding customer pain points before developing solutions",
                "Implement systematic sales processes with clear metrics and stages",
                "Build automated systems that can scale without constant manual intervention"
            ],
            "key_concepts": [
                "Customer acquisition cost optimization",
                "Systematic sales process design", 
                "Business automation and scaling",
                "Performance metrics tracking"
            ],
            "prompt_id": "coach_v1_12345678",
            "token_usage": {
                "input_tokens": 1500,
                "output_tokens": 300
            }
        }
        
        self.tool = StoreShortSummaryToDrive(
            video_id="test_video_123",
            short_summary=self.test_summary
        )

    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.load_app_config')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_drive_naming_format')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_required_env_var')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.os.path.exists')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.Credentials.from_service_account_file')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.build')
    def test_successful_drive_storage(self, mock_build, mock_credentials, mock_exists, mock_get_required, mock_naming_format, mock_config):
        """Test successful storage to Google Drive in both formats."""
        # Mock configuration
        mock_config.return_value = {"test": "config"}
        mock_naming_format.return_value = "{video_id}_{date}_{type}.{ext}"
        mock_get_required.side_effect = lambda key, desc: {
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json",
            "GOOGLE_DRIVE_FOLDER_ID_SUMMARIES": "fake_folder_id"
        }[key]
        mock_exists.return_value = True
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds
        
        # Mock Google Drive service
        mock_drive_service = MagicMock()
        mock_build.return_value = mock_drive_service
        
        # Mock file creation responses
        json_file_response = {'id': 'json_file_id_123'}
        markdown_file_response = {'id': 'markdown_file_id_123'}
        
        mock_drive_service.files().create().execute.side_effect = [json_file_response, markdown_file_response]
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertIn("short_drive_id", data)
        self.assertEqual(data["short_drive_id"], "json_file_id_123")
        
        # Verify Drive service was built correctly
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)
        
        # Verify two files were created (JSON and Markdown)
        self.assertEqual(mock_drive_service.files().create().execute.call_count, 2)

    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_required_env_var')
    def test_missing_credentials_path(self, mock_get_required):
        """Test handling when Google credentials path is missing."""
        mock_get_required.side_effect = Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is required")
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", data["error"])
        self.assertIsNone(data["short_drive_id"])

    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_required_env_var')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.os.path.exists')
    def test_credentials_file_not_found(self, mock_exists, mock_get_required):
        """Test handling when credentials file doesn't exist."""
        mock_get_required.side_effect = lambda key, desc: {
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json",
            "GOOGLE_DRIVE_FOLDER_ID_SUMMARIES": "fake_folder_id"
        }[key]
        mock_exists.return_value = False
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("Service account file not found", data["error"])
        self.assertIsNone(data["short_drive_id"])

    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.load_app_config')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_drive_naming_format')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_required_env_var')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.os.path.exists')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.Credentials.from_service_account_file')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.build')
    def test_drive_upload_failure(self, mock_build, mock_credentials, mock_exists, mock_get_required, mock_naming_format, mock_config):
        """Test handling of Google Drive upload failures."""
        # Mock configuration
        mock_config.return_value = {"test": "config"}
        mock_naming_format.return_value = "{video_id}_{date}_{type}.{ext}"
        mock_get_required.side_effect = lambda key, desc: {
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json",
            "GOOGLE_DRIVE_FOLDER_ID_SUMMARIES": "fake_folder_id"
        }[key]
        mock_exists.return_value = True
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds
        
        # Mock Google Drive service with upload failure
        mock_drive_service = MagicMock()
        mock_build.return_value = mock_drive_service
        mock_drive_service.files().create().execute.side_effect = Exception("Upload failed")
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("Upload failed", data["error"])
        self.assertIsNone(data["short_drive_id"])

    def test_create_json_content(self):
        """Test JSON content creation."""
        timestamp = datetime(2023, 9, 15, 10, 30, 0)
        json_content = self.tool._create_json_content(self.test_summary, timestamp)
        
        # Parse JSON content
        data = json.loads(json_content)
        
        self.assertEqual(data["video_id"], "test_video_123")
        self.assertEqual(len(data["bullets"]), 3)
        self.assertEqual(len(data["key_concepts"]), 4)
        self.assertEqual(data["prompt_id"], "coach_v1_12345678")
        self.assertIn("token_usage", data)
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["bullets_count"], 3)
        self.assertEqual(data["metadata"]["concepts_count"], 4)
        self.assertEqual(data["metadata"]["source"], "autopiloot_summarizer")

    def test_create_markdown_content(self):
        """Test Markdown content creation."""
        timestamp = datetime(2023, 9, 15, 10, 30, 0)
        markdown_content = self.tool._create_markdown_content(self.test_summary, timestamp)
        
        self.assertIn("# Video Summary: test_video_123", markdown_content)
        self.assertIn("**Generated:** 2023-09-15 10:30:00 UTC", markdown_content)
        self.assertIn("**Prompt ID:** coach_v1_12345678", markdown_content)
        self.assertIn("**Token Usage:** 1500 input, 300 output", markdown_content)
        self.assertIn("## Actionable Insights", markdown_content)
        self.assertIn("## Key Concepts", markdown_content)
        self.assertIn("Focus on understanding customer pain points", markdown_content)
        self.assertIn("Customer acquisition cost optimization", markdown_content)
        self.assertIn("Generated by Autopiloot Summarizer Agent", markdown_content)

    def test_format_filename(self):
        """Test filename formatting with naming convention."""
        naming_format = "{video_id}_{date}_{type}.{ext}"
        filename = self.tool._format_filename(naming_format, "test_video_123", "2023-09-15", "summary", "json")
        
        self.assertEqual(filename, "test_video_123_2023-09-15_summary.json")

    def test_empty_summary_content(self):
        """Test handling of empty summary content."""
        empty_summary = {
            "bullets": [],
            "key_concepts": [],
            "prompt_id": "test_prompt",
            "token_usage": {}
        }
        
        tool = StoreShortSummaryToDrive(
            video_id="test_video_123",
            short_summary=empty_summary
        )
        
        # Test JSON content
        timestamp = datetime.now()
        json_content = tool._create_json_content(empty_summary, timestamp)
        data = json.loads(json_content)
        
        self.assertEqual(len(data["bullets"]), 0)
        self.assertEqual(len(data["key_concepts"]), 0)
        self.assertEqual(data["metadata"]["bullets_count"], 0)
        self.assertEqual(data["metadata"]["concepts_count"], 0)
        
        # Test Markdown content
        markdown_content = tool._create_markdown_content(empty_summary, timestamp)
        self.assertIn("*No actionable insights generated*", markdown_content)
        self.assertIn("*No key concepts identified*", markdown_content)

    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.load_app_config')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_drive_naming_format')
    @patch('summarizer_agent.tools.StoreShortSummaryToDrive.get_required_env_var')
    def test_configuration_loading(self, mock_get_required, mock_naming_format, mock_config):
        """Test configuration loading functionality."""
        mock_config.return_value = {"llm": {"model": "gpt-4"}}
        mock_naming_format.return_value = "{video_id}_{date}_{type}.{ext}"
        mock_get_required.side_effect = Exception("GOOGLE_APPLICATION_CREDENTIALS environment variable is required")
        
        # Run the tool - it should fail at credential loading but still call config functions
        result = self.tool.run()
        
        # Parse result to verify it's an error response
        data = json.loads(result)
        self.assertIn("error", data)
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", data["error"])
        
        # Verify configuration was attempted to be loaded
        mock_config.assert_called_once()
        # Note: get_drive_naming_format might not be called if config loading fails early
        # So we don't assert on mock_naming_format

    def test_upload_to_drive_method(self):
        """Test the _upload_to_drive method functionality."""
        mock_drive_service = MagicMock()
        mock_files = MagicMock()
        mock_create = MagicMock()
        mock_execute = MagicMock()
        
        mock_drive_service.files.return_value = mock_files
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {'id': 'test_file_id_123'}
        
        result = self.tool._upload_to_drive(
            mock_drive_service,
            "test_folder_id",
            "test_file.json",
            '{"test": "content"}',
            "application/json"
        )
        
        self.assertEqual(result, "test_file_id_123")
        
        # Verify Drive API calls
        mock_files.create.assert_called_once()
        call_args = mock_files.create.call_args
        
        # Check file metadata - use call_args.kwargs for keyword arguments
        body = call_args.kwargs['body']
        self.assertEqual(body['name'], 'test_file.json')
        self.assertEqual(body['parents'], ['test_folder_id'])
        self.assertEqual(body['mimeType'], 'application/json')


if __name__ == '__main__':
    unittest.main()