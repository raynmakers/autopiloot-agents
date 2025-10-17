"""
Test suite for drive_agent RAG wrapper (rag_index_document.py).

Tests wrapper initialization, document type inference, payload building,
core library delegation, and error handling for document indexing.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util


class TestRagIndexDocumentWrapper(unittest.TestCase):
    """Test suite for RagIndexDocument tool wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_agency_swarm = MagicMock()
        self.mock_base_tool = MagicMock()
        self.mock_agency_swarm.tools.BaseTool = self.mock_base_tool
        # Mock pydantic module
        self.mock_pydantic = MagicMock()
        sys.modules["pydantic"] = self.mock_pydantic

        sys.modules["agency_swarm"] = self.mock_agency_swarm
        sys.modules['agency_swarm.tools'] = self.mock_agency_swarm.tools

        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'drive_agent', 'tools', 'rag_index_document.py'
        )
        spec = importlib.util.spec_from_file_location("rag_index_document", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.RagIndexDocument = self.module.RagIndexDocument

    def tearDown(self):
        """Clean up after each test."""
        if "pydantic" in sys.modules:
            del sys.modules["pydantic"]
        if "agency_swarm" in sys.modules:
            del sys.modules['agency_swarm']
        if 'agency_swarm.tools' in sys.modules:
            del sys.modules['agency_swarm.tools']

    def test_init_with_required_fields(self):
        """Test initialization with only required fields."""
        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample document text."
        )

        self.assertEqual(tool.doc_id, "drive_file_123")
        self.assertEqual(tool.text, "Sample document text.")
        self.assertIsNone(tool.source_uri)
        self.assertIsNone(tool.mime_type)
        self.assertIsNone(tool.title)
        self.assertIsNone(tool.tags)

    @patch('core.rag.ingest_document.ingest')
    def test_run_success(self, mock_ingest):
        """Test successful document indexing."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "drive_file_123",
            "chunk_count": 3,
            "sinks": {
                "opensearch": {"status": "indexed"},
                "bigquery": {"status": "streamed"}
            },
            "message": "Ingested 3 document chunks"
        }

        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample document for testing."
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["document_id"], "drive_file_123")
        self.assertEqual(result["chunk_count"], 3)

    @patch('core.rag.ingest_document.ingest')
    def test_run_sets_source_to_drive(self, mock_ingest):
        """Test that source is always set to 'drive'."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "drive_file_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample document."
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["source"], "drive")

    def test_infer_document_type_pdf(self):
        """Test PDF document type inference."""
        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample text",
            mime_type="application/pdf"
        )

        doc_type = tool._infer_document_type()
        self.assertEqual(doc_type, "pdf")

    def test_infer_document_type_docx(self):
        """Test DOCX document type inference from MIME type."""
        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample text",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        doc_type = tool._infer_document_type()
        self.assertEqual(doc_type, "docx")

    def test_infer_document_type_from_title(self):
        """Test document type inference from title extension."""
        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample text",
            title="document.pdf"
        )

        doc_type = tool._infer_document_type()
        self.assertEqual(doc_type, "pdf")

    def test_infer_document_type_unknown(self):
        """Test unknown document type inference."""
        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample text"
        )

        doc_type = tool._infer_document_type()
        self.assertEqual(doc_type, "unknown")

    @patch('core.rag.ingest_document.ingest')
    def test_run_with_tags(self, mock_ingest):
        """Test run() passes tags to core library."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "drive_file_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample text",
            tags=["strategy", "q4-2025"]
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["tags"], ["strategy", "q4-2025"])

    @patch('core.rag.ingest_document.ingest')
    def test_run_error_handling(self, mock_ingest):
        """Test error handling when core library fails."""
        mock_ingest.side_effect = Exception("Connection failed")

        tool = self.RagIndexDocument(
            doc_id="drive_file_123",
            text="Sample text"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "error")
        self.assertIn("Connection failed", result["message"])


if __name__ == "__main__":
    unittest.main()
