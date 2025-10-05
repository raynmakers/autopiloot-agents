"""
Comprehensive test suite for save_transcript_record.py targeting 100% coverage.
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone

# Mock external dependencies before imports
mock_modules = {
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'dotenv': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field
sys.modules['pydantic'].field_validator = lambda *args, **kwargs: lambda func: func

# Mock SERVER_TIMESTAMP
sys.modules['google.cloud.firestore'].SERVER_TIMESTAMP = 'SERVER_TIMESTAMP'
sys.modules['google.cloud.firestore'].ArrayUnion = lambda x: x

# Import the tool after mocking
from transcriber_agent.tools.save_transcript_record import SaveTranscriptRecord

# Patch SaveTranscriptRecord __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.video_id = kwargs.get('video_id')
    self.drive_ids = kwargs.get('drive_ids', {})
    self.transcript_digest = kwargs.get('transcript_digest')
    self.costs = kwargs.get('costs', {})

SaveTranscriptRecord.__init__ = patched_init


class TestSaveTranscriptRecord100Coverage(unittest.TestCase):
    """Test SaveTranscriptRecord to achieve 100% coverage."""

    @patch('transcriber_agent.tools.save_transcript_record.audit_logger')
    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project', 'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'})
    @patch('transcriber_agent.tools.save_transcript_record.service_account')
    @patch('transcriber_agent.tools.save_transcript_record.firestore')
    def test_successful_transcript_save(self, mock_firestore_module, mock_service_account, mock_audit):
        """Test successful transcript record save (lines 111-263)."""
        tool = SaveTranscriptRecord(
            video_id="test_video_123",
            drive_ids={"drive_id_txt": "txt_123", "drive_id_json": "json_123"},
            transcript_digest="abcd1234",
            costs={"transcription_usd": 0.5}
        )

        # Mock Firestore client and documents
        mock_db = MagicMock()
        mock_firestore_module.Client.return_value = mock_db

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            'status': 'transcription_queued',
            'title': 'Test Video',
            'channel_title': 'Test Channel',
            'published_at': '2025-01-01T00:00:00Z',
            'duration_sec': 300
        }

        mock_video_ref = MagicMock()
        mock_video_ref.get.return_value = mock_video_doc

        mock_transcript_ref = MagicMock()

        mock_db.collection.return_value.document.side_effect = lambda doc_id: mock_video_ref if 'videos' in str(mock_db.collection.call_args) else mock_transcript_ref

        # Mock transaction
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['video_status'], 'transcribed')
        self.assertEqual(data['video_id'], 'test_video_123')
        self.assertIn('transcript_doc_ref', data)
        self.assertIn('created_at', data)
        self.assertEqual(data['drive_ids'], {"drive_id_txt": "txt_123", "drive_id_json": "json_123"})

        # Verify audit logging
        mock_audit.log_transcript_created.assert_called_once()
        mock_audit.log_cost_updated.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_gcp_project_id(self):
        """Test error when GCP_PROJECT_ID is missing (lines 134-138)."""
        tool = SaveTranscriptRecord(
            video_id="test_video",
            drive_ids={"drive_id_txt": "txt", "drive_id_json": "json"},
            transcript_digest="abcd",
            costs={"transcription_usd": 0.5}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['error'], 'configuration_error')
        self.assertIn('GCP_PROJECT_ID', data['message'])

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'}, clear=True)
    def test_missing_service_account_path(self):
        """Test error when GOOGLE_APPLICATION_CREDENTIALS is missing (lines 140-144)."""
        tool = SaveTranscriptRecord(
            video_id="test_video",
            drive_ids={"drive_id_txt": "txt", "drive_id_json": "json"},
            transcript_digest="abcd",
            costs={"transcription_usd": 0.5}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['error'], 'configuration_error')
        self.assertIn('GOOGLE_APPLICATION_CREDENTIALS', data['message'])

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project', 'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'})
    @patch('transcriber_agent.tools.save_transcript_record.service_account')
    @patch('transcriber_agent.tools.save_transcript_record.firestore')
    def test_video_not_found(self, mock_firestore_module, mock_service_account):
        """Test error when video document doesn't exist (lines 159-164)."""
        tool = SaveTranscriptRecord(
            video_id="nonexistent_video",
            drive_ids={"drive_id_txt": "txt", "drive_id_json": "json"},
            transcript_digest="abcd",
            costs={"transcription_usd": 0.5}
        )

        mock_db = MagicMock()
        mock_firestore_module.Client.return_value = mock_db

        mock_video_doc = MagicMock()
        mock_video_doc.exists = False

        mock_video_ref = MagicMock()
        mock_video_ref.get.return_value = mock_video_doc

        mock_db.collection.return_value.document.return_value = mock_video_ref

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['error'], 'document_not_found')
        self.assertEqual(data['video_id'], 'nonexistent_video')

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project', 'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'})
    @patch('transcriber_agent.tools.save_transcript_record.service_account')
    @patch('transcriber_agent.tools.save_transcript_record.firestore')
    def test_invalid_video_status(self, mock_firestore_module, mock_service_account):
        """Test error when video has invalid status (lines 171-177)."""
        tool = SaveTranscriptRecord(
            video_id="test_video",
            drive_ids={"drive_id_txt": "txt", "drive_id_json": "json"},
            transcript_digest="abcd",
            costs={"transcription_usd": 0.5}
        )

        mock_db = MagicMock()
        mock_firestore_module.Client.return_value = mock_db

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'status': 'discovered'}

        mock_video_ref = MagicMock()
        mock_video_ref.get.return_value = mock_video_doc

        mock_db.collection.return_value.document.return_value = mock_video_ref

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['error'], 'invalid_status')
        self.assertEqual(data['current_status'], 'discovered')

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project', 'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'})
    @patch('transcriber_agent.tools.save_transcript_record.firestore')
    @patch('transcriber_agent.tools.save_transcript_record.service_account')
    def test_credentials_error(self, mock_service_account, mock_firestore_module):
        """Test firestore error handling (lines 271-276)."""
        tool = SaveTranscriptRecord(
            video_id="test_video",
            drive_ids={"drive_id_txt": "txt", "drive_id_json": "json"},
            transcript_digest="abcd",
            costs={"transcription_usd": 0.5}
        )

        # Mock credentials to succeed, but firestore to fail
        mock_db = MagicMock()
        mock_firestore_module.Client.return_value = mock_db
        mock_db.collection.side_effect = Exception("Firestore connection error")

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['error'], 'firestore_error')
        self.assertIn('Firestore connection error', data['message'])

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project', 'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'})
    @patch('transcriber_agent.tools.save_transcript_record.audit_logger')
    @patch('transcriber_agent.tools.save_transcript_record.service_account')
    @patch('transcriber_agent.tools.save_transcript_record.firestore')
    def test_processing_status_allowed(self, mock_firestore_module, mock_service_account, mock_audit):
        """Test that 'processing' status is allowed (line 170)."""
        tool = SaveTranscriptRecord(
            video_id="test_video",
            drive_ids={"drive_id_txt": "txt", "drive_id_json": "json"},
            transcript_digest="abcd",
            costs={"transcription_usd": 0.5}
        )

        mock_db = MagicMock()
        mock_firestore_module.Client.return_value = mock_db

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'status': 'processing', 'title': 'Test'}

        mock_video_ref = MagicMock()
        mock_video_ref.get.return_value = mock_video_doc

        mock_db.collection.return_value.document.side_effect = lambda doc_id: mock_video_ref

        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['video_status'], 'transcribed')


if __name__ == '__main__':
    unittest.main()
