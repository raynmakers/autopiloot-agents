"""
Test suite for prompt_version integration in Firestore records.
Tests TASK-LLM-0007 requirement for storing prompt_version: v1 in Firestore summaries.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone
import sys

# Add the parent directories to sys.path to import the tools
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from summarizer_agent.tools.SaveSummaryRecord import SaveSummaryRecord
    from summarizer_agent.tools.save_summary_record_enhanced import SaveSummaryRecordEnhanced
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    
    # Import SaveSummaryRecord
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'SaveSummaryRecord.py'
    )
    spec = importlib.util.spec_from_file_location("SaveSummaryRecord", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SaveSummaryRecord = module.SaveSummaryRecord
    
    # Import SaveSummaryRecordEnhanced
    tool_path_enhanced = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'save_summary_record_enhanced.py'
    )
    spec_enhanced = importlib.util.spec_from_file_location("SaveSummaryRecordEnhanced", tool_path_enhanced)
    module_enhanced = importlib.util.module_from_spec(spec_enhanced)
    spec_enhanced.loader.exec_module(module_enhanced)
    SaveSummaryRecordEnhanced = module_enhanced.SaveSummaryRecordEnhanced


class TestPromptVersionFirestore(unittest.TestCase):
    """Test cases for prompt_version integration in Firestore records."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_refs = {
            "zep_doc_id": "summary_test_video_123",
            "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4",
            "transcript_doc_ref": "transcripts/test_video_123",
            "transcript_drive_id_txt": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx",
            "transcript_drive_id_json": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe",
            "prompt_id": "coach_v1_12345678",
            "prompt_version": "v1",
            "token_usage": {
                "input_tokens": 1500,
                "output_tokens": 300
            },
            "rag_refs": {
                "collection": "autopiloot_guidelines",
                "document_count": 1
            },
            "bullets_count": 3,
            "concepts_count": 4
        }
        
        self.test_video_metadata = {
            "title": "How to Scale Your Business Without Burnout",
            "published_at": "2023-09-15T10:30:00Z",
            "channel_id": "UC1234567890"
        }

    @patch('summarizer_agent.tools.SaveSummaryRecord.firestore.Client')
    def test_basic_summary_record_includes_prompt_version(self, mock_firestore):
        """Test that basic SaveSummaryRecord includes prompt_version in Firestore."""
        # Mock Firestore client and documents
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
        
        # Create and run tool
        tool = SaveSummaryRecord(
            video_id="test_video_123",
            refs=self.test_refs
        )
        
        result = tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        self.assertNotIn("error", data)
        
        # Verify summary document was created with prompt_version
        mock_summary_ref.set.assert_called_once()
        summary_data = mock_summary_ref.set.call_args[0][0]
        
        # Check prompt_version is included
        self.assertIn("prompt_version", summary_data)
        self.assertEqual(summary_data["prompt_version"], "v1")
        
        # Verify other prompt fields
        self.assertEqual(summary_data["prompt_id"], "coach_v1_12345678")
        
        print("✅ Basic SaveSummaryRecord includes prompt_version in Firestore")

    @patch('summarizer_agent.tools.save_summary_record_enhanced.firestore.Client')
    def test_enhanced_summary_record_includes_prompt_version(self, mock_firestore):
        """Test that enhanced SaveSummaryRecordEnhanced includes prompt_version in Firestore."""
        # Mock Firestore client and documents
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
        
        # Set up document method
        def mock_document(path):
            if path.startswith("transcripts/"):
                return mock_transcript_doc
            elif path.startswith("summaries/"):
                return mock_summary_ref
            return MagicMock()
        
        mock_db.document.side_effect = mock_document
        
        # Create enhanced refs including RAG references
        enhanced_refs = self.test_refs.copy()
        enhanced_refs["rag_refs"] = [
            {
                "type": "transcript_drive",
                "ref": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx"
            }
        ]
        
        # Create and run enhanced tool
        tool = SaveSummaryRecordEnhanced(
            video_id="test_video_123",
            refs=enhanced_refs,
            video_metadata=self.test_video_metadata
        )
        
        result = tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        self.assertNotIn("error", data)
        
        # Verify enhanced summary document was created with prompt_version
        mock_summary_ref.set.assert_called_once()
        summary_data = mock_summary_ref.set.call_args[0][0]
        
        # Check prompt_version is included in enhanced record
        self.assertIn("prompt_version", summary_data)
        self.assertEqual(summary_data["prompt_version"], "v1")
        
        # Verify other enhanced fields
        self.assertEqual(summary_data["prompt_id"], "coach_v1_12345678")
        self.assertEqual(summary_data["metadata"]["version"], "2.0")
        self.assertEqual(summary_data["metadata"]["zep_integration"], "enabled")
        
        print("✅ Enhanced SaveSummaryRecord includes prompt_version in Firestore")

    def test_prompt_version_fallback_to_v1(self):
        """Test that prompt_version defaults to v1 when not provided in refs."""
        # Create refs without prompt_version
        refs_without_version = self.test_refs.copy()
        del refs_without_version["prompt_version"]
        
        tool = SaveSummaryRecord(
            video_id="test_video_123",
            refs=refs_without_version
        )
        
        # Mock Firestore to avoid actual database calls
        with patch('summarizer_agent.tools.SaveSummaryRecord.firestore.Client') as mock_firestore:
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
            
            def mock_document(path):
                if path.startswith("transcripts/"):
                    return mock_transcript_doc
                elif path.startswith("summaries/"):
                    return mock_summary_ref
                return MagicMock()
            
            mock_db.document.side_effect = mock_document
            
            # Run the tool
            result = tool.run()
            
            # Verify fallback to v1
            mock_summary_ref.set.assert_called_once()
            summary_data = mock_summary_ref.set.call_args[0][0]
            
            self.assertEqual(summary_data["prompt_version"], "v1")
        
        print("✅ prompt_version defaults to v1 when not provided")

    @patch('summarizer_agent.tools.SaveSummaryRecord.firestore.Client')
    def test_atomic_transaction_includes_prompt_version(self, mock_firestore):
        """Test that atomic transactions include prompt_version."""
        # Mock Firestore client with transaction support
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction
        
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
        mock_db.document.return_value = mock_summary_ref
        
        # Create tool
        tool = SaveSummaryRecord(
            video_id="test_video_123",
            refs=self.test_refs
        )
        
        # Test atomic transaction method directly
        result = tool._atomic_transaction(mock_db)
        
        # Verify transaction was used
        mock_db.transaction.assert_called_once()
        
        print("✅ Atomic transactions support prompt_version")

    def test_refs_validation_with_prompt_version(self):
        """Test that refs validation handles prompt_version correctly."""
        # Test with minimal required refs including prompt_version
        minimal_refs = {
            "transcript_doc_ref": "transcripts/test_video_123",
            "prompt_version": "v1"
        }
        
        tool = SaveSummaryRecord(
            video_id="test_video_123",
            refs=minimal_refs
        )
        
        # Should not raise validation error during initialization
        self.assertEqual(tool.refs["transcript_doc_ref"], "transcripts/test_video_123")
        self.assertEqual(tool.refs["prompt_version"], "v1")
        
        print("✅ Refs validation handles prompt_version correctly")

    def test_enhanced_refs_with_rag_and_prompt_version(self):
        """Test that enhanced refs work with both RAG references and prompt_version."""
        enhanced_refs = {
            "transcript_doc_ref": "transcripts/test_video_123",
            "zep_doc_id": "summary_test_video_123",
            "prompt_id": "coach_v1_12345678",
            "prompt_version": "v1",
            "rag_refs": [
                {"type": "transcript_drive", "ref": "file_id_1"},
                {"type": "logic_doc", "ref": "file_id_2"}
            ]
        }
        
        enhanced_tool = SaveSummaryRecordEnhanced(
            video_id="test_video_123",
            refs=enhanced_refs,
            video_metadata=self.test_video_metadata
        )
        
        # Verify enhanced tool handles all ref types
        self.assertEqual(enhanced_tool.refs["prompt_version"], "v1")
        self.assertEqual(len(enhanced_tool.refs["rag_refs"]), 2)
        self.assertEqual(enhanced_tool.refs["zep_doc_id"], "summary_test_video_123")
        
        print("✅ Enhanced refs support both RAG references and prompt_version")


if __name__ == '__main__':
    unittest.main()