"""
Test suite for SaveSummaryRecordEnhanced tool.
Tests enhanced Firestore integration with Zep references and RAG linkage.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from summarizer_agent.tools.SaveSummaryRecordEnhanced import SaveSummaryRecordEnhanced
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'SaveSummaryRecordEnhanced.py'
    )
    spec = importlib.util.spec_from_file_location("SaveSummaryRecordEnhanced", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SaveSummaryRecordEnhanced = module.SaveSummaryRecordEnhanced


class TestSaveSummaryRecordEnhanced(unittest.TestCase):
    """Test cases for SaveSummaryRecordEnhanced tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
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
                {
                    "type": "transcript_drive",
                    "ref": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx"
                },
                {
                    "type": "logic_doc",
                    "ref": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe"
                }
            ],
            "tags": ["coaching", "business", "automation"],
            "bullets_count": 3,
            "concepts_count": 4
        }
        
        self.test_video_metadata = {
            "title": "How to Scale Your Business Without Burnout",
            "published_at": "2023-09-15T10:30:00Z",
            "channel_id": "UC1234567890"
        }
        
        self.tool = SaveSummaryRecordEnhanced(
            video_id="test_video_123",
            refs=self.test_refs,
            video_metadata=self.test_video_metadata
        )

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_successful_enhanced_summary_record_creation(self, mock_firestore):
        """Test successful enhanced summary record creation with Zep references."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock transcript document exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_db.document.return_value.get.return_value = mock_transcript_doc
        
        # Mock video document
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {"status": "transcribed"}
        
        # Mock collection and document references
        mock_video_collection = MagicMock()
        mock_video_ref = MagicMock()
        mock_summary_ref = MagicMock()
        
        mock_db.collection.return_value = mock_video_collection
        mock_video_collection.document.return_value = mock_video_ref
        mock_video_ref.get.return_value = mock_video_doc
        
        # Set up document method to return different refs for different paths
        def mock_document(path):
            if path.startswith("transcripts/"):
                return mock_transcript_doc
            elif path.startswith("summaries/"):
                return mock_summary_ref
            return MagicMock()
        
        mock_db.document.side_effect = mock_document
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertIn("summary_doc_ref", data)
        self.assertEqual(data["summary_doc_ref"], "summaries/test_video_123")
        self.assertEqual(data["zep_doc_id"], "summary_test_video_123")
        self.assertEqual(data["rag_refs_count"], 2)
        self.assertEqual(data["status"], "completed")
        
        # Verify enhanced summary document was created
        mock_summary_ref.set.assert_called_once()
        summary_data = mock_summary_ref.set.call_args[0][0]
        
        # Check core references
        self.assertEqual(summary_data["video_id"], "test_video_123")
        self.assertEqual(summary_data["transcript_doc_ref"], "transcripts/test_video_123")
        self.assertEqual(summary_data["short_drive_id"], "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4")
        
        # Check enhanced Zep references
        self.assertEqual(summary_data["zep_doc_id"], "summary_test_video_123")
        self.assertEqual(summary_data["zep_collection"], "autopiloot_guidelines")
        self.assertEqual(len(summary_data["rag_refs"]), 2)
        
        # Check video metadata
        self.assertEqual(summary_data["title"], "How to Scale Your Business Without Burnout")
        self.assertEqual(summary_data["published_at"], "2023-09-15T10:30:00Z")
        self.assertEqual(summary_data["channel_id"], "UC1234567890")
        self.assertEqual(len(summary_data["tags"]), 3)
        
        # Check enhanced metadata
        self.assertEqual(summary_data["metadata"]["version"], "2.0")
        self.assertEqual(summary_data["metadata"]["rag_refs_count"], 2)
        self.assertEqual(summary_data["metadata"]["zep_integration"], "enabled")
        
        # Verify video status was updated with Zep references
        mock_video_ref.update.assert_called_once()
        video_update = mock_video_ref.update.call_args[0][0]
        
        self.assertEqual(video_update["status"], "summarized")
        self.assertEqual(video_update["summary_doc_ref"], "summaries/test_video_123")
        self.assertEqual(video_update["zep_doc_id"], "summary_test_video_123")
        self.assertEqual(video_update["zep_collection"], "autopiloot_guidelines")
        self.assertEqual(len(video_update["rag_refs"]), 2)

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_missing_required_references(self, mock_firestore):
        """Test handling when required Zep references are missing."""
        # Create tool with missing zep_doc_id
        invalid_refs = self.test_refs.copy()
        del invalid_refs["zep_doc_id"]
        
        tool = SaveSummaryRecordEnhanced(
            video_id="test_video_123",
            refs=invalid_refs,
            video_metadata=self.test_video_metadata
        )
        
        # Run the tool
        result = tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("zep_doc_id is required", data["error"])
        self.assertIsNone(data["summary_doc_ref"])

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_missing_transcript_doc_ref(self, mock_firestore):
        """Test handling when transcript_doc_ref is missing."""
        # Create tool with missing transcript_doc_ref
        invalid_refs = self.test_refs.copy()
        del invalid_refs["transcript_doc_ref"]
        
        tool = SaveSummaryRecordEnhanced(
            video_id="test_video_123",
            refs=invalid_refs,
            video_metadata=self.test_video_metadata
        )
        
        # Run the tool
        result = tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("transcript_doc_ref is required", data["error"])
        self.assertIsNone(data["summary_doc_ref"])

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_transcript_document_not_exists(self, mock_firestore):
        """Test handling when referenced transcript document doesn't exist."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock transcript document doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False
        mock_db.document.return_value.get.return_value = mock_transcript_doc
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("Transcript document transcripts/test_video_123 does not exist", data["error"])
        self.assertIsNone(data["summary_doc_ref"])

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_video_document_not_exists(self, mock_firestore):
        """Test handling when video document doesn't exist."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock transcript document exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        
        # Mock video document doesn't exist
        mock_video_doc = MagicMock()
        mock_video_doc.exists = False
        
        # Mock collection and document references
        mock_video_collection = MagicMock()
        mock_video_ref = MagicMock()
        mock_summary_ref = MagicMock()
        
        mock_db.collection.return_value = mock_video_collection
        mock_video_collection.document.return_value = mock_video_ref
        mock_video_ref.get.return_value = mock_video_doc
        
        # Set up document method
        def mock_document(path):
            if path.startswith("transcripts/"):
                return mock_transcript_doc
            elif path.startswith("summaries/"):
                return mock_summary_ref
            return MagicMock()
        
        mock_db.document.side_effect = mock_document
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("Video document test_video_123 does not exist", data["error"])
        self.assertIsNone(data["summary_doc_ref"])

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_firestore_operation_failure(self, mock_firestore):
        """Test handling of Firestore operation failures."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock transcript document exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_db.document.return_value.get.return_value = mock_transcript_doc
        
        # Mock video document exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {"status": "transcribed"}
        
        mock_video_collection = MagicMock()
        mock_video_ref = MagicMock()
        mock_summary_ref = MagicMock()
        
        mock_db.collection.return_value = mock_video_collection
        mock_video_collection.document.return_value = mock_video_ref
        mock_video_ref.get.return_value = mock_video_doc
        
        # Mock summary creation failure
        mock_summary_ref.set.side_effect = Exception("Firestore write failed")
        
        def mock_document(path):
            if path.startswith("transcripts/"):
                return mock_transcript_doc
            elif path.startswith("summaries/"):
                return mock_summary_ref
            return MagicMock()
        
        mock_db.document.side_effect = mock_document
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("Firestore write failed", data["error"])
        self.assertIsNone(data["summary_doc_ref"])

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_video_status_warning(self, mock_firestore):
        """Test warning when video has unexpected status."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock transcript document exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_db.document.return_value.get.return_value = mock_transcript_doc
        
        # Mock video document with unexpected status
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {"status": "discovered"}  # Unexpected status
        
        mock_video_collection = MagicMock()
        mock_video_ref = MagicMock()
        mock_summary_ref = MagicMock()
        
        mock_db.collection.return_value = mock_video_collection
        mock_video_collection.document.return_value = mock_video_ref
        mock_video_ref.get.return_value = mock_video_doc
        
        def mock_document(path):
            if path.startswith("transcripts/"):
                return mock_transcript_doc
            elif path.startswith("summaries/"):
                return mock_summary_ref
            return MagicMock()
        
        mock_db.document.side_effect = mock_document
        
        # Capture stdout to check for warning
        with patch('builtins.print') as mock_print:
            result = self.tool.run()
            
            # Check that warning was printed
            mock_print.assert_called()
            warning_call = mock_print.call_args[0][0]
            self.assertIn("Warning: Video test_video_123 has status 'discovered'", warning_call)
        
        # Parse and validate result (should still succeed)
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertEqual(data["summary_doc_ref"], "summaries/test_video_123")

    def test_rag_refs_validation(self):
        """Test RAG references validation and handling."""
        # Test with various rag_refs formats
        test_refs = self.test_refs.copy()
        test_refs["rag_refs"] = [
            {"type": "transcript_drive", "ref": "file_id_1"},
            {"type": "logic_doc", "ref": "file_id_2"},
            {"type": "other", "ref": "file_id_3"}
        ]
        
        tool = SaveSummaryRecordEnhanced(
            video_id="test_video_123",
            refs=test_refs,
            video_metadata=self.test_video_metadata
        )
        
        # Should not raise validation error during initialization
        self.assertEqual(len(tool.refs["rag_refs"]), 3)
        self.assertEqual(tool.refs["rag_refs"][0]["type"], "transcript_drive")

    def test_empty_rag_refs_handling(self):
        """Test handling of empty RAG references."""
        test_refs = self.test_refs.copy()
        test_refs["rag_refs"] = []
        
        tool = SaveSummaryRecordEnhanced(
            video_id="test_video_123",
            refs=test_refs,
            video_metadata=self.test_video_metadata
        )
        
        # Should handle empty rag_refs gracefully
        self.assertEqual(len(tool.refs["rag_refs"]), 0)

    @patch('summarizer_agent.tools.SaveSummaryRecordEnhanced.firestore.Client')
    def test_timestamp_format(self, mock_firestore):
        """Test that timestamps are created in correct UTC ISO format."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock all required documents
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {"status": "transcribed"}
        
        mock_video_collection = MagicMock()
        mock_video_ref = MagicMock()
        mock_summary_ref = MagicMock()
        
        mock_db.collection.return_value = mock_video_collection
        mock_video_collection.document.return_value = mock_video_ref
        mock_video_ref.get.return_value = mock_video_doc
        
        def mock_document(path):
            if path.startswith("transcripts/"):
                return mock_transcript_doc
            elif path.startswith("summaries/"):
                return mock_summary_ref
            return MagicMock()
        
        mock_db.document.side_effect = mock_document
        
        # Run the tool
        result = self.tool.run()
        
        # Verify timestamp format in summary creation
        mock_summary_ref.set.assert_called_once()
        summary_data = mock_summary_ref.set.call_args[0][0]
        
        # Check timestamp format (ISO 8601 with timezone)
        created_at = summary_data["created_at"]
        updated_at = summary_data["updated_at"]
        
        # Should be valid ISO format strings
        datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        
        # Should be UTC timestamps
        self.assertTrue(created_at.endswith('Z') or '+00:00' in created_at)
        self.assertTrue(updated_at.endswith('Z') or '+00:00' in updated_at)


if __name__ == '__main__':
    unittest.main()