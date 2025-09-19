"""
Test suite for UpsertDriveDocsToZep tool.
Tests Zep GraphRAG integration with document chunking and semantic indexing.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock environment and dependencies before importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'zep_python': MagicMock(),
    'zep_python.client': MagicMock(),
}):
    from unittest.mock import MagicMock
    mock_base_tool = MagicMock()
    mock_field = MagicMock()

    with patch('drive_agent.tools.upsert_drive_docs_to_zep.BaseTool', mock_base_tool):
        with patch('drive_agent.tools.upsert_drive_docs_to_zep.Field', mock_field):
            from drive_agent.tools.upsert_drive_docs_to_zep import UpsertDriveDocsToZep


class TestUpsertDriveDocsToZep(unittest.TestCase):
    """Test cases for UpsertDriveDocsToZep tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_documents = [
            {
                "file_id": "doc_001",
                "content": "This is a test document about business strategy. " * 50,  # 250+ chars
                "metadata": {
                    "name": "Strategy Document",
                    "mime_type": "application/pdf",
                    "size": 1024,
                    "modified_time": "2025-01-15T10:30:00Z"
                },
                "drive_info": {
                    "web_view_link": "https://drive.google.com/file/d/doc_001/view",
                    "parents": ["folder_123"]
                }
            },
            {
                "file_id": "doc_002",
                "content": "Short content",
                "metadata": {
                    "name": "Brief Note",
                    "mime_type": "text/plain",
                    "size": 128
                },
                "drive_info": {
                    "web_view_link": "https://drive.google.com/file/d/doc_002/view"
                }
            }
        ]

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_app_config')
    def test_successful_document_upsert(self, mock_load_config, mock_get_env, mock_load_env):
        """Test successful document upsert to Zep."""
        mock_get_env.return_value = "test_api_key"
        mock_load_config.return_value = {"drive_agent": {"zep": {"namespace": "test_namespace"}}}

        # Mock Zep client
        mock_zep_client = MagicMock()
        mock_collection = MagicMock()
        mock_zep_client.document.get_collection.return_value = mock_collection

        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient', return_value=mock_zep_client):
            tool = UpsertDriveDocsToZep(
                documents=self.sample_documents,
                namespace="test_namespace"
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["documents_processed"], 2)
        self.assertEqual(result["chunks_created"], 2)  # One chunk per document
        self.assertEqual(result["namespace"], "test_namespace")
        self.assertGreater(len(result["processing_summary"]), 0)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_chunking_large_document(self, mock_get_env, mock_load_env):
        """Test chunking of large documents."""
        mock_get_env.return_value = "test_api_key"

        # Create large document
        large_doc = {
            "file_id": "large_doc",
            "content": "A" * 10000,  # 10k characters
            "metadata": {"name": "Large Document"},
            "drive_info": {"web_view_link": "https://drive.google.com/file/d/large_doc/view"}
        }

        mock_zep_client = MagicMock()
        mock_collection = MagicMock()
        mock_zep_client.document.get_collection.return_value = mock_collection

        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient', return_value=mock_zep_client):
            tool = UpsertDriveDocsToZep(
                documents=[large_doc],
                chunk_size=2000
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["documents_processed"], 1)
        self.assertGreaterEqual(result["chunks_created"], 5)  # Should create multiple chunks

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_empty_documents_list(self, mock_get_env, mock_load_env):
        """Test handling of empty documents list."""
        mock_get_env.return_value = "test_api_key"

        tool = UpsertDriveDocsToZep(documents=[])
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["documents_processed"], 0)
        self.assertEqual(result["chunks_created"], 0)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_missing_zep_api_key(self, mock_get_env, mock_load_env):
        """Test handling of missing Zep API key."""
        mock_get_env.side_effect = Exception("ZEP_API_KEY not found")

        tool = UpsertDriveDocsToZep(documents=self.sample_documents)
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "environment_error")
        self.assertIn("ZEP_API_KEY not found", result["message"])

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_zep_client_connection_error(self, mock_get_env, mock_load_env):
        """Test handling of Zep client connection errors."""
        mock_get_env.return_value = "test_api_key"

        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient') as mock_zep_class:
            mock_zep_class.side_effect = Exception("Connection failed")

            tool = UpsertDriveDocsToZep(documents=self.sample_documents)
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "zep_connection_failed")
        self.assertIn("Failed to connect to Zep", result["message"])

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_app_config')
    def test_namespace_from_config(self, mock_load_config, mock_get_env, mock_load_env):
        """Test namespace retrieval from configuration when not provided."""
        mock_get_env.return_value = "test_api_key"
        mock_load_config.return_value = {
            "drive_agent": {"zep": {"namespace": "config_namespace"}}
        }

        mock_zep_client = MagicMock()
        mock_collection = MagicMock()
        mock_zep_client.document.get_collection.return_value = mock_collection

        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient', return_value=mock_zep_client):
            tool = UpsertDriveDocsToZep(documents=self.sample_documents)  # No namespace provided
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["namespace"], "config_namespace")

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_batch_processing(self, mock_get_env, mock_load_env):
        """Test batch processing of documents."""
        mock_get_env.return_value = "test_api_key"

        # Create 6 documents for batch testing
        documents = []
        for i in range(6):
            documents.append({
                "file_id": f"doc_{i:03d}",
                "content": f"Content for document {i}",
                "metadata": {"name": f"Document {i}"},
                "drive_info": {"web_view_link": f"https://drive.google.com/file/d/doc_{i:03d}/view"}
            })

        mock_zep_client = MagicMock()
        mock_collection = MagicMock()
        mock_zep_client.document.get_collection.return_value = mock_collection

        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient', return_value=mock_zep_client):
            tool = UpsertDriveDocsToZep(
                documents=documents,
                batch_size=3  # Process in batches of 3
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["documents_processed"], 6)
        self.assertGreaterEqual(result["batches_processed"], 2)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.load_environment')
    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_invalid_document_structure(self, mock_get_env, mock_load_env):
        """Test handling of documents with invalid structure."""
        mock_get_env.return_value = "test_api_key"

        invalid_docs = [
            {"file_id": "doc_001"},  # Missing content
            {"content": "Some content"},  # Missing file_id
            {}  # Empty document
        ]

        mock_zep_client = MagicMock()
        mock_collection = MagicMock()
        mock_zep_client.document.get_collection.return_value = mock_collection

        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient', return_value=mock_zep_client):
            tool = UpsertDriveDocsToZep(documents=invalid_docs)
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["documents_processed"], 0)
        self.assertGreater(len(result["errors"]), 0)


if __name__ == '__main__':
    unittest.main()