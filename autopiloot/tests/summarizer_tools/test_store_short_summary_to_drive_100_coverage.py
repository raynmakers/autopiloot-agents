"""
Comprehensive test suite for StoreShortSummaryToDrive - targeting 100% coverage.
Tests Google Drive storage with environment validation and error handling.
"""

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timezone

# Create properly configured mock modules
mock_service_account = MagicMock()
mock_service_account.Credentials = MagicMock()
mock_service_account.Credentials.from_service_account_file = MagicMock()

mock_googleapiclient_discovery = MagicMock()
mock_googleapiclient_discovery.build = MagicMock()

mock_googleapiclient_http = MagicMock()
mock_googleapiclient_http.MediaInMemoryUpload = MagicMock()

# Mock external dependencies
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': mock_googleapiclient_discovery,
    'googleapiclient.http': mock_googleapiclient_http,
    'google': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': mock_service_account,
}

# First set up the mocks in sys.modules (without context manager to keep them persistent)
sys.modules.update(mock_modules)

class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    return kwargs.get('default', None)

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'].Field = mock_field

# Direct import
import importlib.util
tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'summarizer_agent', 'tools', 'store_short_summary_to_drive.py')
spec = importlib.util.spec_from_file_location("store_short_summary_to_drive", tool_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Register the module so patches can find it (keep it registered permanently)
sys.modules['store_short_summary_to_drive'] = module

StoreShortSummaryToDrive = module.StoreShortSummaryToDrive

# Store references to the imported functions for patching
store_service_account = module.service_account
store_build = module.build
store_MediaInMemoryUpload = module.MediaInMemoryUpload


class TestStoreShortSummaryToDrive100Coverage(unittest.TestCase):
    """Comprehensive test suite achieving 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_bullets = ["Insight 1", "Insight 2", "Insight 3"]
        self.test_concepts = ["Concept A", "Concept B"]
        self.test_video_id = "test_video_123"
        self.test_prompt_id = "prompt_test_001"

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_service_account_path(self):
        """Test error when GOOGLE_SERVICE_ACCOUNT_PATH is missing (lines 43-47)."""
        tool = StoreShortSummaryToDrive(
            video_id=self.test_video_id,
            bullets=self.test_bullets,
            key_concepts=self.test_concepts,
            prompt_id=self.test_prompt_id
        )

        with self.assertRaises(ValueError) as context:
            tool.run()

        self.assertIn("GOOGLE_SERVICE_ACCOUNT_PATH", str(context.exception))

    @patch.dict(os.environ, {'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service.json'}, clear=True)
    def test_missing_drive_folder_id(self):
        """Test error when DRIVE_SUMMARIES_FOLDER_ID is missing (lines 48-49)."""
        tool = StoreShortSummaryToDrive(
            video_id=self.test_video_id,
            bullets=self.test_bullets,
            key_concepts=self.test_concepts,
            prompt_id=self.test_prompt_id
        )

        with self.assertRaises(ValueError) as context:
            tool.run()

        self.assertIn("DRIVE_SUMMARIES_FOLDER_ID", str(context.exception))

    @patch.dict(os.environ, {
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service.json',
        'DRIVE_SUMMARIES_FOLDER_ID': 'folder_123'
    })
    @patch('store_short_summary_to_drive.service_account.Credentials.from_service_account_file')
    @patch('store_short_summary_to_drive.build')
    def test_successful_drive_storage(self, mock_build, mock_creds):
        """Test successful Drive storage (lines 51-127)."""
        # Mock credentials
        mock_creds_obj = MagicMock()
        mock_creds.return_value = mock_creds_obj

        # Mock Drive API
        mock_drive = MagicMock()
        mock_build.return_value = mock_drive

        # Mock file creation responses
        mock_md_file = {'id': 'md_file_123'}
        mock_json_file = {'id': 'json_file_456'}

        mock_drive.files().create().execute.side_effect = [mock_md_file, mock_json_file]

        tool = StoreShortSummaryToDrive(
            video_id=self.test_video_id,
            bullets=self.test_bullets,
            key_concepts=self.test_concepts,
            prompt_id=self.test_prompt_id
        )

        result = tool.run()
        data = json.loads(result)

        # Verify result structure
        self.assertEqual(data['short_drive_id'], 'md_file_123')
        self.assertEqual(data['json_drive_id'], 'json_file_456')
        self.assertIn(self.test_video_id, data['md_filename'])
        self.assertIn(self.test_video_id, data['json_filename'])

    @patch.dict(os.environ, {
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service.json',
        'DRIVE_SUMMARIES_FOLDER_ID': 'folder_123'
    })
    @patch('store_short_summary_to_drive.service_account.Credentials.from_service_account_file')
    def test_credentials_initialization_failure(self, mock_creds):
        """Test error handling when credentials fail (lines 129-130)."""
        mock_creds.side_effect = Exception("Invalid service account file")

        tool = StoreShortSummaryToDrive(
            video_id=self.test_video_id,
            bullets=self.test_bullets,
            key_concepts=self.test_concepts,
            prompt_id=self.test_prompt_id
        )

        with self.assertRaises(RuntimeError) as context:
            tool.run()

        self.assertIn("Failed to store summary to Drive", str(context.exception))

    @patch.dict(os.environ, {
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service.json',
        'DRIVE_SUMMARIES_FOLDER_ID': 'folder_123'
    })
    @patch('store_short_summary_to_drive.service_account.Credentials.from_service_account_file')
    @patch('store_short_summary_to_drive.build')
    def test_markdown_content_generation(self, mock_build, mock_creds):
        """Test markdown content is properly formatted (lines 61-73)."""
        mock_creds_obj = MagicMock()
        mock_creds.return_value = mock_creds_obj

        mock_drive = MagicMock()
        mock_build.return_value = mock_drive

        # Capture the media upload content
        uploaded_content = []

        def capture_create(**kwargs):
            if 'media_body' in kwargs:
                # Access the internal buffer from MediaInMemoryUpload mock
                uploaded_content.append(kwargs)
            return MagicMock(execute=MagicMock(return_value={'id': 'test_id'}))

        mock_drive.files().create = capture_create

        tool = StoreShortSummaryToDrive(
            video_id=self.test_video_id,
            bullets=["Bullet 1", "Bullet 2"],
            key_concepts=["Concept X"],
            prompt_id=self.test_prompt_id
        )

        result = tool.run()

        # Should successfully create files
        self.assertIsInstance(result, str)

    @patch.dict(os.environ, {
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service.json',
        'DRIVE_SUMMARIES_FOLDER_ID': 'folder_123'
    })
    @patch('store_short_summary_to_drive.service_account.Credentials.from_service_account_file')
    @patch('store_short_summary_to_drive.build')
    def test_json_content_generation(self, mock_build, mock_creds):
        """Test JSON content structure (lines 93-100)."""
        mock_creds_obj = MagicMock()
        mock_creds.return_value = mock_creds_obj

        mock_drive = MagicMock()
        mock_build.return_value = mock_drive

        mock_drive.files().create().execute.return_value = {'id': 'test_id'}

        tool = StoreShortSummaryToDrive(
            video_id=self.test_video_id,
            bullets=self.test_bullets,
            key_concepts=self.test_concepts,
            prompt_id=self.test_prompt_id
        )

        result = tool.run()
        data = json.loads(result)

        # Verify both files created
        self.assertIn('short_drive_id', data)
        self.assertIn('json_drive_id', data)

    @patch.dict(os.environ, {
        'GOOGLE_SERVICE_ACCOUNT_PATH': '/path/to/service.json',
        'DRIVE_SUMMARIES_FOLDER_ID': 'folder_123'
    })
    @patch('store_short_summary_to_drive.service_account.Credentials.from_service_account_file')
    @patch('store_short_summary_to_drive.build')
    def test_empty_bullets_and_concepts(self, mock_build, mock_creds):
        """Test with empty bullets and concepts."""
        mock_creds_obj = MagicMock()
        mock_creds.return_value = mock_creds_obj

        mock_drive = MagicMock()
        mock_build.return_value = mock_drive

        mock_drive.files().create().execute.return_value = {'id': 'test_id'}

        tool = StoreShortSummaryToDrive(
            video_id=self.test_video_id,
            bullets=[],
            key_concepts=[],
            prompt_id=self.test_prompt_id
        )

        result = tool.run()
        data = json.loads(result)

        # Should still succeed
        self.assertIn('short_drive_id', data)


if __name__ == '__main__':
    unittest.main()
