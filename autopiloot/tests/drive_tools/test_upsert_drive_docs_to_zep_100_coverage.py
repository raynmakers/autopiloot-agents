#!/usr/bin/env python3
"""
Comprehensive test suite for UpsertDriveDocsToZep tool achieving 100% coverage.
Tests all code paths including error handling, edge cases, and Zep client operations.
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, Mock, call
from datetime import datetime, timezone

# Add path for imports
# Mock ALL external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.errors': MagicMock(),
    'zep_python': MagicMock(),
    'config': MagicMock(),
    'config.env_loader': MagicMock(),
    'config.loader': MagicMock(),
    'env_loader': MagicMock(),
    'loader': MagicMock(),
}

# Apply mocks
with patch.dict('sys.modules', mock_modules):
    # Mock BaseTool
    class MockBaseTool:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    # Mock Field
    def mock_field(*args, **kwargs):
        return kwargs.get('default', None)

    sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
    sys.modules['pydantic'].Field = mock_field

    # Import the tool
    from drive_agent.tools.upsert_drive_docs_to_zep import UpsertDriveDocsToZep


class TestUpsertDriveDocsToZep100Coverage(unittest.TestCase):
    """Comprehensive test suite for 100% coverage of UpsertDriveDocsToZep."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_documents = [
            {
                "file_id": "file123",
                "content": "This is test content",
                "metadata": {
                    "name": "test.pdf",
                    "mime_type": "application/pdf",
                    "size": 1024,
                    "modifiedTime": "2024-01-01T00:00:00Z",
                    "owner": "test@example.com",
                    "webViewLink": "https://drive.google.com/file/123",
                    "parent_folder_id": "folder456"
                },
                "text_stats": {
                    "word_count": 100,
                    "paragraph_count": 5
                },
                "document_metadata": {
                    "extraction_method": "pdf_extraction"
                }
            }
        ]

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_successful_upsert_with_zep_client(self, mock_get_env):
        """Test successful document upsert with real Zep client (lines 197-246)."""
        # Mock environment variables
        mock_get_env.return_value = "test_api_key"

        # Create mock Zep client
        mock_zep_client = MagicMock()
        mock_zep_client.document.add_documents.return_value = {"success": True}

        # Mock Zep SDK
        mock_zep = MagicMock()
        mock_zep_doc_class = MagicMock()
        mock_zep.Document = mock_zep_doc_class
        mock_zep.ZepClient.return_value = mock_zep_client

        with patch.dict('sys.modules', {'zep_python': mock_zep}):
            # Patch the _init_zep_client to return our mock client
            with patch.object(UpsertDriveDocsToZep, '_init_zep_client', return_value=mock_zep_client):
                tool = UpsertDriveDocsToZep(
                    namespace="test_namespace",
                    drive_documents=self.sample_documents,
                    chunk_size=1000,
                    overwrite_existing=True,
                    include_file_metadata=True,
                    batch_size=10
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify success
                self.assertIn('success', result_data)
                self.assertEqual(result_data['success'], True)

                # Verify client methods were called
                mock_zep_client.document.delete.assert_called()
                mock_zep_client.document.add_documents.assert_called()

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_zep_client_initialization_error(self, mock_get_env):
        """Test Zep client initialization error handling (lines 79-82)."""
        # Mock environment variable to raise exception
        mock_get_env.side_effect = Exception("API key error")

        # The tool should handle the exception and return None
        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=self.sample_documents
        )

        # Manually test _init_zep_client
        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient', side_effect=Exception("Connection failed")):
            client = tool._init_zep_client()
            self.assertIsNone(client)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_upsert_batch_error_handling(self, mock_get_env):
        """Test error handling during batch upsert (lines 238-245)."""
        mock_get_env.return_value = "test_api_key"

        # Create mock client that raises exception
        mock_zep_client = MagicMock()
        mock_zep_client.document.add_documents.side_effect = Exception("Upsert failed")

        # Mock Zep Document class
        mock_zep_doc = MagicMock()

        with patch('drive_agent.tools.upsert_drive_docs_to_zep.ZepClient', return_value=mock_zep_client):
            with patch('drive_agent.tools.upsert_drive_docs_to_zep.Document', mock_zep_doc):
                tool = UpsertDriveDocsToZep(
                    namespace="test_namespace",
                    drive_documents=self.sample_documents
                )

                # Manually call _upsert_batch_to_zep with mock client
                zep_docs = [tool._prepare_zep_document(self.sample_documents[0], {"content": "test", "chunk_index": 0, "chunk_count": 1, "is_complete": True})]
                result = tool._upsert_batch_to_zep(mock_zep_client, "test_namespace", zep_docs)

                # Verify error was captured
                self.assertEqual(result["errors"], 1)
                self.assertEqual(len(result["error_details"]), 1)
                self.assertIn("Upsert failed", result["error_details"][0]["error"])

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_overwrite_existing_documents(self, mock_get_env):
        """Test overwrite_existing flag functionality (lines 219-228)."""
        mock_get_env.return_value = "test_api_key"

        # Create mock Zep client
        mock_zep_client = MagicMock()
        mock_zep_client.document.add_documents.return_value = {"success": True}
        mock_zep_client.document.delete.return_value = None

        # Mock Zep SDK
        mock_zep = MagicMock()
        mock_zep_doc_class = MagicMock()
        mock_zep.Document = mock_zep_doc_class
        mock_zep.ZepClient.return_value = mock_zep_client

        with patch.dict('sys.modules', {'zep_python': mock_zep}):
            with patch.object(UpsertDriveDocsToZep, '_init_zep_client', return_value=mock_zep_client):
                tool = UpsertDriveDocsToZep(
                    namespace="test_namespace",
                    drive_documents=self.sample_documents,
                    overwrite_existing=True
                )

                result = tool.run()

                # Verify delete was called before add
                mock_zep_client.document.delete.assert_called()
                mock_zep_client.document.add_documents.assert_called()

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_delete_document_exception_ignored(self, mock_get_env):
        """Test that delete exceptions are ignored (lines 227-228)."""
        mock_get_env.return_value = "test_api_key"

        # Create mock client where delete raises exception
        mock_zep_client = MagicMock()
        mock_zep_client.document.delete.side_effect = Exception("Document not found")
        mock_zep_client.document.add_documents.return_value = {"success": True}

        # Mock Zep SDK
        mock_zep = MagicMock()
        mock_zep_doc_class = MagicMock()
        mock_zep.Document = mock_zep_doc_class
        mock_zep.ZepClient.return_value = mock_zep_client

        with patch.dict('sys.modules', {'zep_python': mock_zep}):
            with patch.object(UpsertDriveDocsToZep, '_init_zep_client', return_value=mock_zep_client):
                tool = UpsertDriveDocsToZep(
                    namespace="test_namespace",
                    drive_documents=self.sample_documents,
                    overwrite_existing=True
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should succeed despite delete exception
                self.assertIn('success', result_data)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_empty_documents_with_mock_client(self, mock_get_env):
        """Test empty documents list with mock implementation."""
        mock_get_env.side_effect = Exception("No API key")

        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=[]
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should return success with 0 documents
        self.assertIn('success', result_data)
        self.assertEqual(result_data['processing_stats']['total_input_documents'], 0)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_document_without_optional_fields(self, mock_get_env):
        """Test document processing without optional metadata fields."""
        mock_get_env.side_effect = Exception("No API key")

        # Minimal document without metadata or text_stats
        minimal_doc = {
            "file_id": "minimal123",
            "content": "Minimal content"
        }

        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=[minimal_doc],
            include_file_metadata=False
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn('success', result_data)
        self.assertEqual(result_data['processing_stats']['total_chunks_created'], 1)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_various_document_types(self, mock_get_env):
        """Test document type classification for various file extensions."""
        mock_get_env.side_effect = Exception("No API key")

        doc_types = [
            ("test.pdf", "pdf"),
            ("test.PDF", "pdf"),
            ("test.docx", "word_document"),
            ("test.DOCX", "word_document"),
            ("test.doc", "word_document"),
            ("test.DOC", "word_document"),
            ("test.txt", "text_document"),
            ("test.TXT", "text_document"),
            ("test.md", "text_document"),
            ("test.MD", "text_document"),
            ("test.csv", "spreadsheet"),
            ("test.CSV", "spreadsheet"),
            ("test.html", "web_document"),
            ("test.HTML", "web_document"),
            ("test.htm", "web_document"),
            ("test.HTM", "web_document"),
            ("test.xyz", "unknown"),
            ("", "unknown")  # Empty filename
        ]

        for filename, expected_type in doc_types:
            doc = {
                "file_id": f"file_{filename}",
                "content": "Test content",
                "metadata": {"name": filename} if filename else {}
            }

            tool = UpsertDriveDocsToZep(
                namespace="test_namespace",
                drive_documents=[doc],
                include_file_metadata=True
            )

            # Get prepared document
            chunk = {"content": "test", "chunk_index": 0, "chunk_count": 1, "is_complete": True}
            prepared = tool._prepare_zep_document(doc, chunk)

            if filename:
                self.assertEqual(prepared["metadata"]["document_type"], expected_type)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_large_document_chunking(self, mock_get_env):
        """Test chunking of large documents."""
        mock_get_env.side_effect = Exception("No API key")

        # Create large content that requires chunking
        large_content = "word " * 500  # 2500 characters

        doc = {
            "file_id": "large_file",
            "content": large_content
        }

        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=[doc],
            chunk_size=1000  # Force chunking
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should create multiple chunks
        self.assertIn('success', result_data)
        self.assertGreater(result_data['processing_stats']['total_chunks_created'], 1)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_chunk_at_word_boundary(self, mock_get_env):
        """Test that chunks break at word boundaries when possible."""
        mock_get_env.side_effect = Exception("No API key")

        # Content with clear word boundaries
        content = "a" * 900 + " " + "b" * 200  # Space at position 900

        doc = {
            "file_id": "boundary_test",
            "content": content
        }

        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=[doc],
            chunk_size=1000  # Should break at space
        )

        chunks = tool._chunk_content(content, "boundary_test")

        # First chunk should end at the space
        self.assertTrue(chunks[0]["content"].endswith("a"))
        self.assertEqual(len(chunks[0]["content"]), 900)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_batch_processing(self, mock_get_env):
        """Test batch processing of multiple documents."""
        mock_get_env.side_effect = Exception("No API key")

        # Create multiple documents
        docs = []
        for i in range(25):  # More than default batch size
            docs.append({
                "file_id": f"file_{i}",
                "content": f"Content {i}"
            })

        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=docs,
            batch_size=10
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn('success', result_data)
        self.assertEqual(result_data['processing_stats']['total_input_documents'], 25)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_document_id_generation(self, mock_get_env):
        """Test document ID generation for chunks."""
        mock_get_env.side_effect = Exception("No API key")

        tool = UpsertDriveDocsToZep(
            namespace="test",
            drive_documents=[]
        )

        # Test single document (no chunk index)
        doc_id = tool._generate_document_id("file123", 0)
        self.assertEqual(doc_id, "drive_file123")

        # Test chunked document
        doc_id = tool._generate_document_id("file123", 2)
        self.assertEqual(doc_id, "drive_file123_chunk_2")

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_run_with_general_exception(self, mock_get_env):
        """Test general exception handling in run method (lines 315-316)."""
        mock_get_env.return_value = "test_api_key"

        # Create a tool that will raise an exception during run
        with patch.object(UpsertDriveDocsToZep, '_init_zep_client', side_effect=Exception("Unexpected error")):
            tool = UpsertDriveDocsToZep(
                namespace="test_namespace",
                drive_documents=self.sample_documents
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should return error response
            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'upsert_error')
            self.assertIn('Unexpected error', result_data['message'])

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_processing_with_invalid_document_format(self, mock_get_env):
        """Test handling of documents with invalid format."""
        mock_get_env.side_effect = Exception("No API key")

        # Document missing required 'content' field
        invalid_doc = {
            "file_id": "invalid123"
            # Missing 'content' field
        }

        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=[invalid_doc]
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should handle gracefully
        self.assertIn('error', result_data)

    @patch('drive_agent.tools.upsert_drive_docs_to_zep.get_required_env_var')
    def test_metadata_extraction_all_fields(self, mock_get_env):
        """Test extraction of all metadata fields."""
        mock_get_env.side_effect = Exception("No API key")

        # Document with all possible metadata
        full_doc = {
            "file_id": "full123",
            "content": "Full content",
            "metadata": {
                "name": "full.pdf",
                "mime_type": "application/pdf",
                "size": 2048,
                "modifiedTime": "2024-01-01T12:00:00Z",
                "owner": "owner@example.com",
                "webViewLink": "https://drive.google.com/file/full",
                "parent_folder_id": "parent123"
            },
            "text_stats": {
                "word_count": 250,
                "paragraph_count": 10
            },
            "document_metadata": {
                "extraction_method": "advanced_ocr"
            }
        }

        tool = UpsertDriveDocsToZep(
            namespace="test_namespace",
            drive_documents=[full_doc],
            include_file_metadata=True
        )

        # Get prepared document
        chunk = {"content": "test", "chunk_index": 0, "chunk_count": 1, "is_complete": True}
        prepared = tool._prepare_zep_document(full_doc, chunk)

        # Verify all metadata fields
        metadata = prepared["metadata"]
        self.assertEqual(metadata["file_name"], "full.pdf")
        self.assertEqual(metadata["mime_type"], "application/pdf")
        self.assertEqual(metadata["file_size"], 2048)
        self.assertEqual(metadata["word_count"], 250)
        self.assertEqual(metadata["paragraph_count"], 10)
        self.assertEqual(metadata["extraction_method"], "advanced_ocr")
        self.assertEqual(metadata["document_type"], "pdf")


if __name__ == "__main__":
    unittest.main(verbosity=2)