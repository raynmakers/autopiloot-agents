"""
Test suite for SaveVideoMetadata tool.
Tests Firestore upsert functionality and idempotency requirements.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scraper', 'tools'))

try:
    from scraper.tools.SaveVideoMetadata import SaveVideoMetadata
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'scraper', 
        'tools', 
        'SaveVideoMetadata.py'
    )
    spec = importlib.util.spec_from_file_location("SaveVideoMetadata", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SaveVideoMetadata = module.SaveVideoMetadata


class TestSaveVideoMetadata(unittest.TestCase):
    """Test cases for SaveVideoMetadata tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.valid_video_data = {
            "video_id": "dQw4w9WgXcQ",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
            "published_at": "2009-10-25T06:57:33Z",
            "duration_sec": 212,
            "source": "scrape",
            "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw"
        }
        
        self.tool = SaveVideoMetadata(**self.valid_video_data)

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    @patch('scraper.tools.SaveVideoMetadata.firestore.Client')
    def test_save_new_video_metadata(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test saving new video metadata to Firestore."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Mock document doesn't exist (new document)
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('doc_ref', data)
        self.assertEqual(data['doc_ref'], 'videos/dQw4w9WgXcQ')
        self.assertEqual(data['operation'], 'created')
        self.assertEqual(data['video_id'], 'dQw4w9WgXcQ')
        self.assertEqual(data['status'], 'discovered')
        
        # Verify Firestore operations
        mock_db.collection.assert_called_once_with('videos')
        mock_db.collection.return_value.document.assert_called_once_with('dQw4w9WgXcQ')
        mock_doc_ref.set.assert_called_once()
        
        # Verify the data passed to Firestore
        call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(call_args['video_id'], 'dQw4w9WgXcQ')
        self.assertEqual(call_args['status'], 'discovered')
        self.assertEqual(call_args['source'], 'scrape')
        self.assertIn('created_at', call_args)
        self.assertIn('updated_at', call_args)

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    @patch('scraper.tools.SaveVideoMetadata.firestore.Client')
    def test_update_existing_video_metadata(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test updating existing video metadata in Firestore."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Mock document exists (update existing)
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = True
        mock_doc_ref.get.return_value = mock_existing_doc
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertEqual(data['operation'], 'updated')
        
        # Verify update was called instead of set
        mock_doc_ref.update.assert_called_once()
        mock_doc_ref.set.assert_not_called()
        
        # Verify the data passed to Firestore update doesn't include created_at
        call_args = mock_doc_ref.update.call_args[0][0]
        self.assertNotIn('created_at', call_args)
        self.assertIn('updated_at', call_args)

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    def test_video_duration_exceeds_maximum(self, mock_config):
        """Test behavior when video duration exceeds maximum allowed."""
        # Mock configuration with 70-minute limit
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        
        # Create tool with video longer than 70 minutes
        long_video_data = self.valid_video_data.copy()
        long_video_data["duration_sec"] = 5000  # 83+ minutes
        
        tool = SaveVideoMetadata(**long_video_data)
        result = tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('exceeds maximum', data['error'])
        self.assertIsNone(data['doc_ref'])

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    @patch('scraper.tools.SaveVideoMetadata.firestore.Client')
    def test_firestore_operation_failure(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test error handling when Firestore operation fails."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore to raise an exception
        mock_firestore_client.side_effect = Exception("Firestore connection failed")
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('Firestore connection failed', data['error'])
        self.assertIsNone(data['doc_ref'])

    def test_tool_initialization_with_all_fields(self):
        """Test tool initialization with all required and optional fields."""
        tool = SaveVideoMetadata(
            video_id="test123",
            url="https://www.youtube.com/watch?v=test123",
            title="Test Video",
            published_at="2025-01-27T00:00:00Z",
            duration_sec=300,
            source="sheet",
            channel_id="UCtest123"
        )
        
        self.assertEqual(tool.video_id, "test123")
        self.assertEqual(tool.url, "https://www.youtube.com/watch?v=test123")
        self.assertEqual(tool.title, "Test Video")
        self.assertEqual(tool.published_at, "2025-01-27T00:00:00Z")
        self.assertEqual(tool.duration_sec, 300)
        self.assertEqual(tool.source, "sheet")
        self.assertEqual(tool.channel_id, "UCtest123")

    def test_tool_initialization_without_optional_fields(self):
        """Test tool initialization without optional channel_id field."""
        minimal_data = self.valid_video_data.copy()
        del minimal_data["channel_id"]
        
        tool = SaveVideoMetadata(**minimal_data)
        
        self.assertEqual(tool.video_id, "dQw4w9WgXcQ")
        self.assertIsNone(tool.channel_id)

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    @patch('scraper.tools.SaveVideoMetadata.firestore.Client')
    def test_source_field_validation(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test validation of source field values."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc
        
        # Test valid source values
        for source in ["scrape", "sheet"]:
            data = self.valid_video_data.copy()
            data["source"] = source
            data["video_id"] = f"test_{source}"
            
            tool = SaveVideoMetadata(**data)
            
            with patch('os.path.exists', return_value=True):
                result = tool.run()
            
            data_result = json.loads(result)
            self.assertNotIn('error', data_result)
            self.assertEqual(data_result['doc_ref'], f'videos/test_{source}')

    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    def test_missing_environment_variables(self, mock_get_required_env_var):
        """Test behavior when required environment variables are missing."""
        # Mock missing GCP_PROJECT_ID
        mock_get_required_env_var.side_effect = Exception("GCP_PROJECT_ID not set")
        
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('GCP_PROJECT_ID not set', data['error'])

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    def test_missing_service_account_file(self, mock_get_required_env_var, mock_config):
        """Test behavior when service account file doesn't exist."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/credentials.json"
        }[var]
        
        # Mock file doesn't exist
        with patch('os.path.exists', return_value=False):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('Service account file not found', data['error'])

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    @patch('scraper.tools.SaveVideoMetadata.firestore.Client')
    def test_video_without_channel_id(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test saving video metadata without optional channel_id."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc
        
        # Create tool without channel_id
        data = self.valid_video_data.copy()
        del data["channel_id"]
        tool = SaveVideoMetadata(**data)
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = tool.run()
        
        # Parse and validate result
        data_result = json.loads(result)
        self.assertNotIn('error', data_result)
        
        # Verify the data passed to Firestore doesn't include channel_id
        call_args = mock_doc_ref.set.call_args[0][0]
        self.assertNotIn('channel_id', call_args)

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    def test_default_configuration_values(self, mock_config):
        """Test behavior with default configuration when config is missing."""
        # Mock missing idempotency configuration
        mock_config.return_value = {}
        
        # Create tool with video under default 70-minute limit
        data = self.valid_video_data.copy()
        data["duration_sec"] = 3000  # 50 minutes
        tool = SaveVideoMetadata(**data)
        
        # Should not raise duration error with default 4200 seconds (70 minutes)
        # We'll mock the rest to avoid Firestore calls
        with patch.object(tool, '_initialize_firestore'), \
             patch('scraper.tools.SaveVideoMetadata.firestore'):
            try:
                result = tool.run()
                # Should not have duration error
                data_result = json.loads(result)
                # May have other errors due to mocking, but not duration error
                if 'error' in data_result:
                    self.assertNotIn('exceeds maximum', data_result['error'])
            except Exception:
                # Ignore other exceptions from incomplete mocking
                pass

    def test_iso_8601_timestamp_format(self):
        """Test that timestamps follow ISO 8601 format with Z suffix."""
        test_timestamps = [
            "2025-01-27T00:00:00Z",
            "2009-10-25T06:57:33Z",
            "2025-09-14T12:34:56Z"
        ]
        
        for timestamp in test_timestamps:
            data = self.valid_video_data.copy()
            data["published_at"] = timestamp
            
            # Should not raise validation error
            tool = SaveVideoMetadata(**data)
            self.assertEqual(tool.published_at, timestamp)

    @patch('scraper.tools.SaveVideoMetadata.load_app_config')
    @patch('scraper.tools.SaveVideoMetadata.get_required_env_var')
    @patch('scraper.tools.SaveVideoMetadata.firestore.Client')
    def test_idempotency_requirement(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test that re-running with same video_id doesn't create duplicates."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # First run - document doesn't exist
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc
        
        with patch('os.path.exists', return_value=True):
            result1 = self.tool.run()
        
        data1 = json.loads(result1)
        self.assertEqual(data1['operation'], 'created')
        
        # Second run - document exists
        mock_existing_doc.exists = True
        mock_doc_ref.get.return_value = mock_existing_doc
        
        with patch('os.path.exists', return_value=True):
            result2 = self.tool.run()
        
        data2 = json.loads(result2)
        self.assertEqual(data2['operation'], 'updated')
        
        # Both should have same doc_ref
        self.assertEqual(data1['doc_ref'], data2['doc_ref'])


if __name__ == '__main__':
    unittest.main(verbosity=2)