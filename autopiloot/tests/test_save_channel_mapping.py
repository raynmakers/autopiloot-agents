"""
Comprehensive tests for SaveChannelMapping tool.
Tests idempotent channel handle → channel_id mapping persistence to Firestore.
"""

import unittest
import json
import os
import sys
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

# Mock agency_swarm and pydantic before importing tool
mock_base_tool = MagicMock()
mock_field = MagicMock(return_value=lambda **kwargs: None)
sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['agency_swarm.tools'].BaseTool = mock_base_tool
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic'].Field = mock_field

# Import tool using direct file import for coverage
import importlib.util
tool_path = os.path.join(
    os.path.dirname(__file__),
    '..',
    'scraper_agent',
    'tools',
    'save_channel_mapping.py'
)
spec = importlib.util.spec_from_file_location("save_channel_mapping", tool_path)
module = importlib.util.module_from_spec(spec)

# Mock google.cloud.firestore before executing
mock_firestore = MagicMock()
mock_firestore.SERVER_TIMESTAMP = "SERVER_TIMESTAMP"
sys.modules['google.cloud.firestore'] = mock_firestore
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud'].firestore = mock_firestore

# Execute module
spec.loader.exec_module(module)
SaveChannelMapping = module.SaveChannelMapping


class TestSaveChannelMapping(unittest.TestCase):
    """Test SaveChannelMapping tool comprehensive functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'GCP_PROJECT_ID': 'test-project',
            'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/test-credentials.json'
        })
        self.env_patcher.start()

        # Mock file existence
        self.exists_patcher = patch('os.path.exists', return_value=True)
        self.exists_patcher.start()

        # Mock Firestore client
        self.mock_db = MagicMock()
        self.firestore_patcher = patch('google.cloud.firestore.Client', return_value=self.mock_db)
        self.firestore_patcher.start()

    def tearDown(self):
        """Clean up mocks."""
        self.env_patcher.stop()
        self.exists_patcher.stop()
        self.firestore_patcher.stop()

    def test_create_new_channel_mapping(self):
        """Test creating a new channel mapping with all fields."""
        # Mock Firestore document
        mock_doc = MagicMock()
        mock_doc.exists = False  # New document
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.set = MagicMock()

        tool = SaveChannelMapping(
            handle="AlexHormozi",
            channel_id="UC123",
            title="Alex Hormozi",
            custom_url="@AlexHormozi"
        )

        result = tool.run()
        data = json.loads(result)

        # Verify success response
        self.assertTrue(data.get('ok'))
        self.assertEqual(data['channel_id'], 'UC123')
        self.assertEqual(data['canonical_handle'], '@AlexHormozi')

        # Verify Firestore was called correctly
        self.mock_db.collection.assert_called_with('channels')
        self.mock_db.collection.return_value.document.assert_called_with('UC123')

        # Verify set was called with correct data
        set_call_args = self.mock_db.collection.return_value.document.return_value.set.call_args
        self.assertIsNotNone(set_call_args)
        create_data = set_call_args[0][0]

        self.assertEqual(create_data['channel_id'], 'UC123')
        self.assertEqual(create_data['canonical_handle'], '@AlexHormozi')
        self.assertEqual(create_data['handles'], ['@AlexHormozi'])
        self.assertEqual(create_data['title'], 'Alex Hormozi')
        self.assertEqual(create_data['custom_url'], '@AlexHormozi')
        self.assertIn('created_at', create_data)
        self.assertIn('updated_at', create_data)
        self.assertIn('last_resolved_at', create_data)

    def test_update_existing_channel_with_new_handle(self):
        """Test updating existing channel merges handles without duplicates."""
        # Mock existing document
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'channel_id': 'UC123',
            'canonical_handle': '@AlexHormozi',
            'handles': ['@AlexHormozi']
        }
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.update = MagicMock()

        tool = SaveChannelMapping(
            handle="@alexhormozi",  # Different case
            channel_id="UC123",
            title="Alex Hormozi Updated"
        )

        result = tool.run()
        data = json.loads(result)

        # Verify success
        self.assertTrue(data.get('ok'))

        # Verify update was called
        update_call_args = self.mock_db.collection.return_value.document.return_value.update.call_args
        self.assertIsNotNone(update_call_args)
        update_data = update_call_args[0][0]

        # Should NOT add duplicate (case-insensitive)
        self.assertEqual(update_data['handles'], ['@AlexHormozi'])
        self.assertEqual(update_data['canonical_handle'], '@alexhormozi')
        self.assertEqual(update_data['title'], 'Alex Hormozi Updated')
        self.assertIn('updated_at', update_data)

    def test_handle_normalization_without_at_prefix(self):
        """Test handle normalization adds @ prefix when missing."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.set = MagicMock()

        tool = SaveChannelMapping(
            handle="TestChannel",  # No @ prefix
            channel_id="UC456"
        )

        result = tool.run()
        data = json.loads(result)

        # Verify @ prefix was added
        self.assertEqual(data['canonical_handle'], '@TestChannel')

        # Verify Firestore data
        set_call_args = self.mock_db.collection.return_value.document.return_value.set.call_args
        create_data = set_call_args[0][0]
        self.assertEqual(create_data['canonical_handle'], '@TestChannel')
        self.assertEqual(create_data['handles'], ['@TestChannel'])

    def test_handle_normalization_preserves_at_prefix(self):
        """Test handle normalization preserves existing @ prefix."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.set = MagicMock()

        tool = SaveChannelMapping(
            handle="@TestChannel",  # With @ prefix
            channel_id="UC456"
        )

        result = tool.run()
        data = json.loads(result)

        # Verify @ prefix is preserved
        self.assertEqual(data['canonical_handle'], '@TestChannel')

    def test_merge_handles_case_insensitive_deduplication(self):
        """Test merging handles deduplicates case-insensitively."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'channel_id': 'UC123',
            'handles': ['@AlexHormozi', '@alexhormozi']  # Different cases
        }
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.update = MagicMock()

        tool = SaveChannelMapping(
            handle="@ALEXHORMOZI",  # All caps
            channel_id="UC123"
        )

        result = tool.run()

        # Verify no duplicate added
        update_call_args = self.mock_db.collection.return_value.document.return_value.update.call_args
        update_data = update_call_args[0][0]
        self.assertEqual(len(update_data['handles']), 2)  # No new handle added

    def test_merge_handles_adds_new_variant(self):
        """Test merging handles adds genuinely new variants."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'channel_id': 'UC123',
            'handles': ['@AlexHormozi']
        }
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.update = MagicMock()

        tool = SaveChannelMapping(
            handle="@Alex.Hormozi",  # Different handle
            channel_id="UC123"
        )

        result = tool.run()

        # Verify new handle was added
        update_call_args = self.mock_db.collection.return_value.document.return_value.update.call_args
        update_data = update_call_args[0][0]
        self.assertIn('@Alex.Hormozi', update_data['handles'])
        self.assertEqual(len(update_data['handles']), 2)

    def test_invalid_thumbnails_json_returns_error(self):
        """Test invalid thumbnails_json returns structured error."""
        tool = SaveChannelMapping(
            handle="@Test",
            channel_id="UC789",
            thumbnails_json="{invalid json"
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error response
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'invalid_thumbnails_json')
        self.assertIn('message', data)

    def test_valid_thumbnails_json_parsed(self):
        """Test valid thumbnails_json is parsed and stored."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.set = MagicMock()

        thumbnails_data = {"default": {"url": "https://example.com/thumb.jpg"}}
        tool = SaveChannelMapping(
            handle="@Test",
            channel_id="UC789",
            thumbnails_json=json.dumps(thumbnails_data)
        )

        result = tool.run()
        data = json.loads(result)

        # Verify success
        self.assertTrue(data.get('ok'))

        # Verify thumbnails were stored
        set_call_args = self.mock_db.collection.return_value.document.return_value.set.call_args
        create_data = set_call_args[0][0]
        self.assertEqual(create_data['thumbnails'], thumbnails_data)

    def test_firestore_initialization_error_missing_credentials(self):
        """Test error when service account credentials file is missing."""
        with patch('os.path.exists', return_value=False):
            tool = SaveChannelMapping(
                handle="@Test",
                channel_id="UC999"
            )

            result = tool.run()
            data = json.loads(result)

            # Verify error response
            self.assertIn('error', data)
            self.assertEqual(data['error'], 'save_failed')
            self.assertIn('message', data)

    def test_firestore_initialization_error_missing_env_vars(self):
        """Test error when required environment variables are missing."""
        with patch.dict('os.environ', {}, clear=True):
            tool = SaveChannelMapping(
                handle="@Test",
                channel_id="UC999"
            )

            result = tool.run()
            data = json.loads(result)

            # Verify error response
            self.assertIn('error', data)
            self.assertEqual(data['error'], 'save_failed')

    def test_empty_handle_validation(self):
        """Test validation rejects empty handle."""
        with self.assertRaises(Exception):  # Pydantic validation error
            SaveChannelMapping(
                handle="",
                channel_id="UC123"
            )

    def test_empty_channel_id_validation(self):
        """Test validation rejects empty channel_id."""
        with self.assertRaises(Exception):  # Pydantic validation error
            SaveChannelMapping(
                handle="@Test",
                channel_id=""
            )

    def test_whitespace_trimmed_from_inputs(self):
        """Test whitespace is trimmed from handle and channel_id."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.set = MagicMock()

        tool = SaveChannelMapping(
            handle="  @TestChannel  ",
            channel_id="  UC456  "
        )

        result = tool.run()
        data = json.loads(result)

        # Verify trimming
        self.assertEqual(data['channel_id'], 'UC456')
        self.assertEqual(data['canonical_handle'], '@TestChannel')

    def test_optional_fields_not_included_when_none(self):
        """Test optional fields are not included in Firestore when None."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.set = MagicMock()

        tool = SaveChannelMapping(
            handle="@Test",
            channel_id="UC789"
            # title, custom_url, thumbnails_json not provided
        )

        result = tool.run()

        # Verify Firestore data doesn't include optional fields
        set_call_args = self.mock_db.collection.return_value.document.return_value.set.call_args
        create_data = set_call_args[0][0]
        self.assertNotIn('title', create_data)
        self.assertNotIn('custom_url', create_data)
        self.assertNotIn('thumbnails', create_data)

    def test_last_resolved_at_iso_format(self):
        """Test last_resolved_at is in ISO 8601 format with Z."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        self.mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        self.mock_db.collection.return_value.document.return_value.set = MagicMock()

        tool = SaveChannelMapping(
            handle="@Test",
            channel_id="UC789"
        )

        result = tool.run()

        # Verify last_resolved_at format
        set_call_args = self.mock_db.collection.return_value.document.return_value.set.call_args
        create_data = set_call_args[0][0]
        last_resolved = create_data['last_resolved_at']

        # Verify ISO 8601 format with Z
        self.assertTrue(last_resolved.endswith('Z'))
        # Should be parseable as datetime
        datetime.fromisoformat(last_resolved.replace('Z', '+00:00'))


if __name__ == '__main__':
    unittest.main()
