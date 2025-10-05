"""
Comprehensive test suite for SaveSummaryRecordEnhanced tool - targeting 100% coverage.
Tests all paths including Zep integration, RAG references, and enhanced metadata.
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

# Mock external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
}

# Apply mocks
# First set up the mocks in sys.modules (without context manager to keep them persistent)
sys.modules.update(mock_modules)
# Mock BaseTool and Field
class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    return kwargs.get('default', None)

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'].Field = mock_field

# Mock audit_logger module
mock_audit_logger = MagicMock()
sys.modules['audit_logger'] = mock_audit_logger

# Import using direct file import to avoid module import errors
import importlib.util
tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'summarizer_agent', 'tools', 'save_summary_record_enhanced.py')
spec = importlib.util.spec_from_file_location("save_summary_record_enhanced", tool_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Register the module so patches can find it
sys.modules['save_summary_record_enhanced'] = module
SaveSummaryRecordEnhanced = module.SaveSummaryRecordEnhanced


class TestSaveSummaryRecordEnhanced100Coverage(unittest.TestCase):
    """Comprehensive test suite for SaveSummaryRecordEnhanced achieving 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_video_id = "test_video_123"
        self.test_refs = {
            "zep_doc_id": "summary_test_video_123",
            "zep_collection": "autopiloot_guidelines",
            "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4",
            "transcript_doc_ref": "transcripts/test_video_123",
            "transcript_drive_id_txt": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx",
            "transcript_drive_id_json": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe",
            "prompt_id": "coach_v1_12345678",
            "token_usage": {
                "input_tokens": 1500,
                "output_tokens": 300
            },
            "rag_refs": [
                {"type": "transcript_drive", "ref": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx"},
                {"type": "logic_doc", "ref": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe"}
            ],
            "tags": ["coaching", "business", "automation"],
            "bullets_count": 3,
            "concepts_count": 4
        }
        self.test_video_metadata = {
            "title": "How to Scale Your Business",
            "published_at": "2023-09-15T10:30:00Z",
            "channel_id": "UC1234567890"
        }

    @patch('save_summary_record_enhanced.firestore')
    @patch('save_summary_record_enhanced.audit_logger')
    def test_successful_enhanced_summary_save(self, mock_audit, mock_firestore):
        """Test successful enhanced summary creation with Zep integration (lines 62-91)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True

        # Mock video exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'status': 'transcribed'}

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            elif 'videos' in doc_ref:
                mock_ref.get.return_value = mock_video_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify result structure
        self.assertEqual(data['summary_doc_ref'], f"summaries/{self.test_video_id}")
        self.assertEqual(data['zep_doc_id'], self.test_refs['zep_doc_id'])
        self.assertEqual(data['rag_refs_count'], 2)
        self.assertEqual(data['status'], 'completed')

        # Verify audit log was called
        mock_audit.log_summary_created.assert_called_once()

    @patch('save_summary_record_enhanced.firestore')
    def test_missing_required_references(self, mock_firestore):
        """Test validation of required references (lines 109-120)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Create refs missing required fields
        invalid_refs = {
            "short_drive_id": "123",
            # Missing: transcript_doc_ref, zep_doc_id
        }

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=invalid_refs,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Should return error
        self.assertIn('error', data)
        self.assertIn('required', data['error'].lower())

    @patch('save_summary_record_enhanced.firestore')
    def test_transcript_does_not_exist(self, mock_firestore):
        """Test error when transcript doesn't exist (lines 122-141)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript does NOT exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False

        mock_db.document.return_value.get.return_value = mock_transcript_doc

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Should return error
        self.assertIn('error', data)

    @patch('save_summary_record_enhanced.firestore')
    def test_firestore_initialization_failure(self, mock_firestore):
        """Test Firestore client initialization failure (lines 100-107)."""
        # Mock Firestore client initialization failure
        mock_firestore.Client.side_effect = Exception("Connection failed")

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Should return error
        self.assertIn('error', data)
        self.assertIn('Failed to save enhanced summary record', data['error'])

    @patch('save_summary_record_enhanced.firestore')
    @patch('save_summary_record_enhanced.audit_logger')
    def test_enhanced_summary_document_structure(self, mock_audit, mock_firestore):
        """Test enhanced summary document has all required fields (lines 143-205)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript and video exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'status': 'transcribed'}

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            elif 'summaries' in doc_ref:
                pass  # Summary ref for creation
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        # Capture set call
        mock_summary_ref = MagicMock()
        mock_db.document.return_value = mock_summary_ref

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

        tool.run()

        # Verify set was called
        mock_summary_ref.set.assert_called()
        call_args = mock_summary_ref.set.call_args[0][0]

        # Verify enhanced fields
        self.assertEqual(call_args['video_id'], self.test_video_id)
        self.assertEqual(call_args['zep_doc_id'], self.test_refs['zep_doc_id'])
        self.assertEqual(call_args['zep_collection'], 'autopiloot_guidelines')
        self.assertEqual(len(call_args['rag_refs']), 2)
        self.assertEqual(call_args['status'], 'completed')
        self.assertEqual(call_args['metadata']['version'], '2.0')
        self.assertEqual(call_args['metadata']['zep_integration'], 'enabled')

    @patch('save_summary_record_enhanced.firestore')
    @patch('save_summary_record_enhanced.audit_logger')
    def test_video_status_update_with_zep(self, mock_audit, mock_firestore):
        """Test video status update includes Zep references (lines 207-244)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True

        # Mock video exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'status': 'transcribed'}

        mock_video_ref = MagicMock()

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value = mock_video_ref
        mock_video_ref.get.return_value = mock_video_doc

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

        tool.run()

        # Verify video update was called with Zep fields
        mock_video_ref.update.assert_called_once()
        call_args = mock_video_ref.update.call_args[0][0]

        self.assertEqual(call_args['status'], 'summarized')
        self.assertEqual(call_args['zep_doc_id'], self.test_refs['zep_doc_id'])
        self.assertEqual(call_args['zep_collection'], 'autopiloot_guidelines')
        self.assertEqual(len(call_args['rag_refs']), 2)

    @patch('save_summary_record_enhanced.firestore')
    def test_video_does_not_exist_for_status_update(self, mock_firestore):
        """Test error when video doesn't exist for status update (lines 218-222)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True

        # Mock video does NOT exist
        mock_video_doc = MagicMock()
        mock_video_doc.exists = False

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Should return error
        self.assertIn('error', data)

    @patch('save_summary_record_enhanced.firestore')
    @patch('save_summary_record_enhanced.audit_logger')
    def test_video_wrong_status_warning(self, mock_audit, mock_firestore):
        """Test warning when video has unexpected status (lines 224-228)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True

        # Mock video with wrong status
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'status': 'discovered'}  # Wrong status

        mock_video_ref = MagicMock()

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value = mock_video_ref
        mock_video_ref.get.return_value = mock_video_doc

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

        # Should still complete despite warning
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'completed')

    @patch('save_summary_record_enhanced.firestore')
    @patch('save_summary_record_enhanced.audit_logger')
    def test_empty_rag_refs(self, mock_audit, mock_firestore):
        """Test tool handles empty rag_refs gracefully."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript and video exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'status': 'transcribed'}

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        # Create refs with empty rag_refs
        refs_no_rag = self.test_refs.copy()
        refs_no_rag['rag_refs'] = []

        tool = SaveSummaryRecordEnhanced(
            video_id=self.test_video_id,
            refs=refs_no_rag,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['rag_refs_count'], 0)
        self.assertEqual(data['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
