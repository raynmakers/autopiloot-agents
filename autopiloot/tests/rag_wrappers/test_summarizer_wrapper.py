"""
Test suite for summarizer_agent RAG wrapper (rag_index_summary.py).

Tests wrapper initialization, payload building with summary-specific fields,
core library delegation, and error handling for summary indexing.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util


class TestRagIndexSummaryWrapper(unittest.TestCase):
    """Test suite for RagIndexSummary tool wrapper."""

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
            'summarizer_agent', 'tools', 'rag_index_summary.py'
        )
        spec = importlib.util.spec_from_file_location("rag_index_summary", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.RagIndexSummary = self.module.RagIndexSummary

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
        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary text."
        )

        self.assertEqual(tool.summary_id, "summary_123")
        self.assertEqual(tool.text, "Sample summary text.")
        self.assertIsNone(tool.video_id)
        self.assertIsNone(tool.title)
        self.assertIsNone(tool.tags)
        self.assertIsNone(tool.channel_id)
        self.assertIsNone(tool.published_at)

    @patch('core.rag.ingest_document.ingest')
    def test_run_success(self, mock_ingest):
        """Test successful summary indexing."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "summary_123",
            "chunk_count": 2,
            "sinks": {
                "opensearch": {"status": "indexed"},
                "bigquery": {"status": "streamed"},
                "zep": {"status": "upserted"}
            },
            "message": "Success"
        }

        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary for testing."
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary_id"], "summary_123")  # Renamed from document_id
        self.assertEqual(result["chunk_count"], 2)

    @patch('core.rag.ingest_document.ingest')
    def test_run_sets_document_type_and_source(self, mock_ingest):
        """Test that document_type is set to 'summary' and source to 'summarizer'."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "summary_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary"
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["document_type"], "summary")
        self.assertEqual(call_args["source"], "summarizer")

    @patch('core.rag.ingest_document.ingest')
    def test_run_with_video_id_linking(self, mock_ingest):
        """Test summary with video_id linking."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "summary_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary",
            video_id="video_abc123"
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["video_id"], "video_abc123")

    @patch('core.rag.ingest_document.ingest')
    def test_run_with_all_optional_fields(self, mock_ingest):
        """Test run() with all optional fields."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "summary_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary",
            video_id="video_abc123",
            title="Video Title",
            tags=["saas", "scaling"],
            channel_id="UC123",
            published_at="2025-10-08T12:00:00Z"
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["video_id"], "video_abc123")
        self.assertEqual(call_args["title"], "Video Title")
        self.assertEqual(call_args["tags"], ["saas", "scaling"])
        self.assertEqual(call_args["channel_id"], "UC123")
        self.assertEqual(call_args["published_at"], "2025-10-08T12:00:00Z")

    @patch('core.rag.ingest_document.ingest')
    def test_run_renames_document_id_to_summary_id(self, mock_ingest):
        """Test that document_id is renamed to summary_id in response."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "summary_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertIn("summary_id", result)
        self.assertEqual(result["summary_id"], "summary_123")
        self.assertNotIn("document_id", result)

    @patch('core.rag.ingest_document.ingest')
    def test_run_error_handling(self, mock_ingest):
        """Test error handling when core library fails."""
        mock_ingest.side_effect = Exception("Database connection failed")

        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "error")
        self.assertIn("Database connection failed", result["message"])
        self.assertEqual(result["summary_id"], "summary_123")

    @patch('core.rag.ingest_document.ingest')
    def test_run_partial_success(self, mock_ingest):
        """Test partial indexing scenario."""
        mock_ingest.return_value = {
            "status": "partial",
            "document_id": "summary_123",
            "chunk_count": 2,
            "sinks": {
                "opensearch": {"status": "indexed"},
                "bigquery": {"status": "error"}
            },
            "message": "Partial: BigQuery failed"
        }

        tool = self.RagIndexSummary(
            summary_id="summary_123",
            text="Sample summary"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "partial")
        self.assertIn("BigQuery", result["message"])


if __name__ == "__main__":
    unittest.main()
