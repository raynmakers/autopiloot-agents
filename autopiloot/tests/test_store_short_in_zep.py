"""
Test suite for StoreShortInZep tool.
Tests Zep GraphRAG integration, document storage, and metadata handling.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from summarizer_agent.tools.store_short_in_zep import StoreShortInZep
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'store_short_in_zep.py'
    )
    spec = importlib.util.spec_from_file_location("store_short_in_zep", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    StoreShortInZep = module.StoreShortInZep


class TestStoreShortInZep(unittest.TestCase):
    """Test cases for StoreShortInZep tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_summary = {
            "bullets": [
                "Focus on customer acquisition through targeted marketing",
                "Implement systematic sales processes for consistency",
                "Build automated systems that scale without manual intervention"
            ],
            "key_concepts": [
                "Customer Acquisition Cost (CAC) optimization",
                "Sales process systematization",
                "Business automation frameworks"
            ],
            "prompt_id": "coach_v1_12345678",
            "token_usage": {
                "input_tokens": 1500,
                "output_tokens": 300
            }
        }
        
        self.tool = StoreShortInZep(
            video_id="test_video_123",
            bullets=self.test_summary["bullets"],
            key_concepts=self.test_summary["key_concepts"]
        )

    @patch('summarizer_agent.tools.StoreShortInZep.get_required_env_var')
    @patch('summarizer_agent.tools.StoreShortInZep.get_optional_env_var')
    @patch('builtins.__import__')
    def test_successful_zep_storage(self, mock_import, mock_get_optional, mock_get_required):
        """Test successful storage in Zep collection."""
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
        
        # Verify Zep client was called correctly
        mock_zep_client_class.assert_called_once_with(
            api_key="test-zep-api-key",
            base_url="https://api.getzep.com"
        )
        
        # Verify document was created with correct content
        mock_document_class.assert_called_once()
        call_args = mock_document_class.call_args
        self.assertIn("ACTIONABLE INSIGHTS:", call_args.kwargs["content"])
        self.assertIn("KEY CONCEPTS:", call_args.kwargs["content"])
        
        # Verify metadata
        metadata = call_args.kwargs["metadata"]
        self.assertEqual(metadata["video_id"], "test_video_123")
        self.assertEqual(metadata["content_type"], "coaching_summary")
        self.assertEqual(metadata["bullets_count"], 3)
        self.assertEqual(metadata["concepts_count"], 3)

    @patch('summarizer_agent.tools.StoreShortInZep.get_required_env_var')
    @patch('summarizer_agent.tools.StoreShortInZep.get_optional_env_var')
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

    @patch('summarizer_agent.tools.StoreShortInZep.get_required_env_var')
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

    @patch('summarizer_agent.tools.StoreShortInZep.get_required_env_var')
    @patch('summarizer_agent.tools.StoreShortInZep.get_optional_env_var')
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

    @patch('summarizer_agent.tools.StoreShortInZep.get_required_env_var')
    @patch('summarizer_agent.tools.StoreShortInZep.get_optional_env_var')
    @patch('builtins.__import__')
    def test_zep_storage_failure(self, mock_import, mock_get_optional, mock_get_required):
        """Test handling of Zep storage failures."""
        # Mock environment variables
        mock_get_required.return_value = "test-zep-api-key"
        mock_get_optional.return_value = "autopiloot_guidelines"
        
        # Mock Zep SDK
        mock_zep_module = MagicMock()
        mock_zep_client_class = MagicMock()
        mock_document_class = MagicMock()
        
        mock_zep_module.ZepClient = mock_zep_client_class
        mock_zep_module.Document = mock_document_class
        
        def mock_import_side_effect(name, *args, **kwargs):
            if name == 'zep_python':
                return mock_zep_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_side_effect
        
        # Mock Zep client with storage failure
        mock_zep_client = MagicMock()
        mock_zep_client_class.return_value = mock_zep_client
        mock_zep_client.document.get_collection.return_value = MagicMock()
        mock_zep_client.document.add_document.side_effect = Exception("Storage failed")
        
        mock_document = MagicMock()
        mock_document.document_id = "summary_test_video_123"
        mock_document_class.return_value = mock_document
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("Storage failed", data["error"])
        self.assertIsNone(data["zep_doc_id"])

    def test_format_content_for_zep(self):
        """Test content formatting for Zep storage."""
        content = self.tool._format_content_for_zep(self.test_summary)
        
        self.assertIn("ACTIONABLE INSIGHTS:", content)
        self.assertIn("KEY CONCEPTS:", content)
        self.assertIn("Focus on customer acquisition", content)
        self.assertIn("Customer Acquisition Cost", content)

    def test_build_zep_metadata(self):
        """Test metadata building for Zep document."""
        metadata = self.tool._build_zep_metadata("test_video_123", self.test_summary)
        
        self.assertEqual(metadata["video_id"], "test_video_123")
        self.assertEqual(metadata["content_type"], "coaching_summary")
        self.assertEqual(metadata["bullets_count"], 3)
        self.assertEqual(metadata["concepts_count"], 3)
        self.assertEqual(metadata["prompt_id"], "coach_v1_12345678")
        self.assertEqual(metadata["source"], "autopiloot_summarizer")
        self.assertEqual(metadata["collection"], "autopiloot_guidelines")

    def test_empty_summary_handling(self):
        """Test handling of empty summary data."""
        empty_summary = {
            "bullets": [],
            "key_concepts": [],
            "prompt_id": "test_prompt",
            "token_usage": {}
        }
        
        tool = StoreShortInZep(
            video_id="test_video_123",
            short_summary=empty_summary
        )
        
        content = tool._format_content_for_zep(empty_summary)
        metadata = tool._build_zep_metadata("test_video_123", empty_summary)
        
        # For empty summaries, content will be empty since no bullets or concepts
        self.assertEqual(content, "")
        self.assertEqual(metadata["bullets_count"], 0)
        self.assertEqual(metadata["concepts_count"], 0)


if __name__ == '__main__':
    unittest.main()