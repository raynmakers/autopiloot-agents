"""
Test suite for UpsertSummaryToZep tool.
Tests comprehensive Zep GraphRAG integration, extended metadata, and RAG references.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from summarizer_agent.tools.UpsertSummaryToZep import UpsertSummaryToZep
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'UpsertSummaryToZep.py'
    )
    spec = importlib.util.spec_from_file_location("UpsertSummaryToZep", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    UpsertSummaryToZep = module.UpsertSummaryToZep


class TestUpsertSummaryToZep(unittest.TestCase):
    """Test cases for UpsertSummaryToZep tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_summary = {
            "bullets": [
                "Focus on systematic customer acquisition through targeted marketing channels",
                "Implement automated sales processes with clear metrics and conversion tracking",
                "Build scalable business systems that operate without constant manual intervention"
            ],
            "key_concepts": [
                "Customer Acquisition Cost (CAC) optimization strategies",
                "Sales funnel systematization and automation",
                "Business process automation frameworks",
                "Performance metrics and KPI tracking systems"
            ],
            "prompt_id": "coach_v1_12345678",
            "token_usage": {
                "input_tokens": 1500,
                "output_tokens": 300
            }
        }
        
        self.test_video_metadata = {
            "title": "How to Scale Your Business Without Burnout",
            "published_at": "2023-09-15T10:30:00Z",
            "channel_id": "UC1234567890"
        }
        
        self.test_rag_refs = [
            {
                "type": "transcript_drive",
                "ref": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx"
            },
            {
                "type": "logic_doc",
                "ref": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe"
            }
        ]
        
        self.tool = UpsertSummaryToZep(
            video_id="test_video_123",
            short_summary=self.test_summary,
            video_metadata=self.test_video_metadata,
            transcript_doc_ref="transcripts/test_video_123",
            rag_refs=self.test_rag_refs,
            tags=["coaching", "business", "automation", "scaling"]
        )

    @patch('summarizer_agent.tools.UpsertSummaryToZep.get_required_env_var')
    @patch('summarizer_agent.tools.UpsertSummaryToZep.get_optional_env_var')
    @patch('builtins.__import__')
    def test_successful_zep_upsert(self, mock_import, mock_get_optional, mock_get_required):
        """Test successful upsert to Zep collection with comprehensive metadata."""
        # Mock environment variables
        mock_get_required.return_value = "test-zep-api-key"
        mock_get_optional.side_effect = lambda key, default="": {
            "ZEP_COLLECTION": "autopiloot_guidelines",
            "ZEP_BASE_URL": "https://api.getzep.com"
        }.get(key, default)
        
        # Mock Zep SDK
        mock_zep_module = MagicMock()
        mock_zep_client_class = MagicMock()
        mock_document_class = MagicMock()
        mock_create_collection_request = MagicMock()
        
        mock_zep_module.ZepClient = mock_zep_client_class
        mock_zep_module.Document = mock_document_class
        mock_zep_module.CreateCollectionRequest = mock_create_collection_request
        
        def mock_import_side_effect(name, *args, **kwargs):
            if name == 'zep_python':
                return mock_zep_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_side_effect
        
        # Mock Zep client and operations
        mock_zep_client = MagicMock()
        mock_zep_client_class.return_value = mock_zep_client
        
        mock_collection = MagicMock()
        mock_zep_client.document.get_collection.return_value = mock_collection
        
        mock_document = MagicMock()
        mock_document.document_id = "summary_test_video_123"
        mock_document_class.return_value = mock_document
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertIn("zep_doc_id", data)
        self.assertEqual(data["zep_doc_id"], "summary_test_video_123")
        self.assertEqual(data["collection"], "autopiloot_guidelines")
        self.assertEqual(len(data["rag_refs"]), 2)
        
        # Verify Zep client was called correctly
        mock_zep_client_class.assert_called_once_with(
            api_key="test-zep-api-key",
            base_url="https://api.getzep.com"
        )
        
        # Verify document was created with correct content and metadata
        mock_document_class.assert_called_once()
        call_args = mock_document_class.call_args
        
        # Check content formatting
        content = call_args.kwargs["content"]
        self.assertIn("ACTIONABLE INSIGHTS:", content)
        self.assertIn("KEY CONCEPTS:", content)
        self.assertIn("COACHING SUMMARY", content)
        
        # Check comprehensive metadata
        metadata = call_args.kwargs["metadata"]
        self.assertEqual(metadata["video_id"], "test_video_123")
        self.assertEqual(metadata["title"], "How to Scale Your Business Without Burnout")
        self.assertEqual(metadata["published_at"], "2023-09-15T10:30:00Z")
        self.assertEqual(metadata["channel_id"], "UC1234567890")
        self.assertEqual(metadata["transcript_doc_ref"], "transcripts/test_video_123")
        self.assertEqual(len(metadata["tags"]), 4)
        self.assertEqual(len(metadata["rag_refs"]), 2)
        self.assertEqual(metadata["content_type"], "coaching_summary")

    @patch('summarizer_agent.tools.UpsertSummaryToZep.get_required_env_var')
    @patch('summarizer_agent.tools.UpsertSummaryToZep.get_optional_env_var')
    @patch('builtins.__import__')
    def test_zep_collection_creation(self, mock_import, mock_get_optional, mock_get_required):
        """Test automatic collection creation when collection doesn't exist."""
        # Mock environment variables
        mock_get_required.return_value = "test-zep-api-key"
        mock_get_optional.side_effect = lambda key, default="": "autopiloot_guidelines" if key == "ZEP_COLLECTION" else default
        
        # Mock Zep SDK
        mock_zep_module = MagicMock()
        mock_zep_client_class = MagicMock()
        mock_document_class = MagicMock()
        mock_create_collection_request = MagicMock()
        
        mock_zep_module.ZepClient = mock_zep_client_class
        mock_zep_module.Document = mock_document_class
        mock_zep_module.CreateCollectionRequest = mock_create_collection_request
        
        def mock_import_side_effect(name, *args, **kwargs):
            if name == 'zep_python':
                return mock_zep_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_side_effect
        
        # Mock Zep client
        mock_zep_client = MagicMock()
        mock_zep_client_class.return_value = mock_zep_client
        
        # Mock collection not existing initially
        mock_zep_client.document.get_collection.side_effect = Exception("Collection not found")
        mock_new_collection = MagicMock()
        mock_zep_client.document.add_collection.return_value = mock_new_collection
        
        mock_document = MagicMock()
        mock_document.document_id = "summary_test_video_123"
        mock_document_class.return_value = mock_document
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertIn("zep_doc_id", data)
        
        # Verify collection creation was attempted
        mock_create_collection_request.assert_called_once_with(
            name="autopiloot_guidelines",
            description="Autopiloot coaching guidelines and actionable insights from video summaries"
        )
        mock_zep_client.document.add_collection.assert_called_once()

    @patch('summarizer_agent.tools.UpsertSummaryToZep.get_required_env_var')
    def test_missing_zep_credentials(self, mock_get_required):
        """Test handling when Zep API key is missing."""
        # Mock missing API key
        mock_get_required.side_effect = Exception("ZEP_API_KEY environment variable is required")
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("ZEP_API_KEY", data["error"])
        self.assertIsNone(data["zep_doc_id"])

    @patch('summarizer_agent.tools.UpsertSummaryToZep.get_required_env_var')
    @patch('summarizer_agent.tools.UpsertSummaryToZep.get_optional_env_var')
    def test_zep_package_missing(self, mock_get_optional, mock_get_required):
        """Test handling when zep-python package is not installed."""
        # Mock environment variables
        mock_get_required.return_value = "test-zep-api-key"
        mock_get_optional.return_value = "autopiloot_guidelines"
        
        # Mock ImportError for zep-python
        with patch('builtins.__import__', side_effect=ImportError("No module named 'zep_python'")):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("zep-python package not available", data["error"])
        self.assertIsNone(data["zep_doc_id"])

    def test_format_content_for_zep(self):
        """Test content formatting for Zep GraphRAG storage."""
        content = self.tool._format_content_for_zep(self.test_summary)
        
        self.assertIn("ACTIONABLE INSIGHTS:", content)
        self.assertIn("KEY CONCEPTS:", content)
        self.assertIn("COACHING SUMMARY", content)
        self.assertIn("Focus on systematic customer acquisition", content)
        self.assertIn("Customer Acquisition Cost", content)
        self.assertIn("actionable business insights", content)

    def test_build_zep_metadata(self):
        """Test comprehensive metadata building for Zep document."""
        metadata = self.tool._build_zep_metadata(
            "test_video_123", 
            self.test_summary,
            self.test_video_metadata,
            "transcripts/test_video_123",
            self.test_rag_refs,
            ["coaching", "business"]
        )
        
        self.assertEqual(metadata["video_id"], "test_video_123")
        self.assertEqual(metadata["title"], "How to Scale Your Business Without Burnout")
        self.assertEqual(metadata["published_at"], "2023-09-15T10:30:00Z")
        self.assertEqual(metadata["channel_id"], "UC1234567890")
        self.assertEqual(metadata["transcript_doc_ref"], "transcripts/test_video_123")
        self.assertEqual(len(metadata["tags"]), 2)
        self.assertEqual(len(metadata["rag_refs"]), 2)
        self.assertEqual(metadata["content_type"], "coaching_summary")
        self.assertEqual(metadata["bullets_count"], 3)
        self.assertEqual(metadata["concepts_count"], 4)
        self.assertEqual(metadata["source"], "autopiloot_summarizer")

    def test_rag_refs_formatting(self):
        """Test RAG references formatting and validation."""
        # Test with various rag_refs formats
        test_rag_refs = [
            {"type": "transcript_drive", "ref": "file_id_1"},
            {"type": "logic_doc", "ref": "file_id_2"},
            {"type": "other", "ref": "file_id_3"},
            {"ref": "file_id_4"}  # Missing type should default to "other"
        ]
        
        metadata = self.tool._build_zep_metadata(
            "test_video_123",
            self.test_summary,
            self.test_video_metadata,
            "transcripts/test_video_123",
            test_rag_refs,
            []
        )
        
        rag_refs = metadata["rag_refs"]
        self.assertEqual(len(rag_refs), 4)
        self.assertEqual(rag_refs[0]["type"], "transcript_drive")
        self.assertEqual(rag_refs[0]["ref"], "file_id_1")
        self.assertEqual(rag_refs[3]["type"], "other")  # Default type

    def test_empty_summary_handling(self):
        """Test handling of empty summary data."""
        empty_summary = {
            "bullets": [],
            "key_concepts": [],
            "prompt_id": "test_prompt",
            "token_usage": {}
        }
        
        tool = UpsertSummaryToZep(
            video_id="test_video_123",
            short_summary=empty_summary,
            video_metadata=self.test_video_metadata,
            transcript_doc_ref="transcripts/test_video_123",
            rag_refs=[],
            tags=[]
        )
        
        content = tool._format_content_for_zep(empty_summary)
        metadata = tool._build_zep_metadata(
            "test_video_123",
            empty_summary,
            self.test_video_metadata,
            "transcripts/test_video_123",
            [],
            []
        )
        
        # Content should still have coaching context even if empty
        self.assertIn("COACHING SUMMARY", content)
        self.assertEqual(metadata["bullets_count"], 0)
        self.assertEqual(metadata["concepts_count"], 0)
        self.assertEqual(len(metadata["rag_refs"]), 0)


if __name__ == '__main__':
    unittest.main()