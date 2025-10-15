"""
Test suite for transcriber_agent RAG wrapper (rag_index_transcript.py).

Tests wrapper initialization, payload building, core library delegation,
and error handling paths for transcript indexing.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util

# Add project root to path

class TestRagIndexTranscriptWrapper(unittest.TestCase):
    """Test suite for RagIndexTranscript tool wrapper."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Mock pydantic module
        self.mock_pydantic = MagicMock()
        sys.modules['pydantic'] = self.mock_pydantic

        # Mock agency_swarm module
        self.mock_agency_swarm = MagicMock()
        self.mock_base_tool = MagicMock()
        self.mock_agency_swarm.tools.BaseTool = self.mock_base_tool
        sys.modules['agency_swarm'] = self.mock_agency_swarm
        sys.modules['agency_swarm.tools'] = self.mock_agency_swarm.tools

        # Import tool using direct file import to ensure coverage measurement
        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'transcriber_agent', 'tools', 'rag_index_transcript.py'
        )
        spec = importlib.util.spec_from_file_location("rag_index_transcript", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.RagIndexTranscript = self.module.RagIndexTranscript

    def tearDown(self):
        """Clean up after each test."""
        if 'pydantic' in sys.modules:
            del sys.modules['pydantic']
        if 'agency_swarm' in sys.modules:
            del sys.modules['agency_swarm']
        if 'agency_swarm.tools' in sys.modules:
            del sys.modules['agency_swarm.tools']

    def test_init_with_required_fields(self):
        """Test initialization with only required fields."""
        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Sample transcript text for testing.",
            channel_id="UC_TestChannel"
        )

        self.assertEqual(tool.video_id, "test_video_123")
        self.assertEqual(tool.transcript_text, "Sample transcript text for testing.")
        self.assertEqual(tool.channel_id, "UC_TestChannel")
        self.assertIsNone(tool.title)
        self.assertIsNone(tool.published_at)
        self.assertIsNone(tool.duration_sec)

    def test_init_with_all_fields(self):
        """Test initialization with all optional fields."""
        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Full transcript text.",
            channel_id="UC_TestChannel",
            title="Test Video Title",
            channel_handle="@TestChannel",
            published_at="2025-10-08T12:00:00Z",
            duration_sec=1200
        )

        self.assertEqual(tool.video_id, "test_video_123")
        self.assertEqual(tool.title, "Test Video Title")
        self.assertEqual(tool.channel_handle, "@TestChannel")
        self.assertEqual(tool.published_at, "2025-10-08T12:00:00Z")
        self.assertEqual(tool.duration_sec, 1200)

    @patch('core.rag.ingest_transcript.ingest')
    def test_run_success(self, mock_ingest):
        """Test successful transcript indexing."""
        # Mock successful ingest response
        mock_ingest.return_value = {
            "status": "success",
            "video_id": "test_video_123",
            "chunk_count": 5,
            "sinks": {
                "opensearch": {"status": "indexed", "indexed_count": 5},
                "bigquery": {"status": "streamed", "row_count": 5},
                "zep": {"status": "upserted", "upserted_count": 5}
            },
            "message": "Ingested 5 chunks to RAG sinks (status: success)"
        }

        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Sample transcript for success test.",
            channel_id="UC_TestChannel"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        # Verify ingest was called with correct payload
        mock_ingest.assert_called_once()
        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["video_id"], "test_video_123")
        self.assertEqual(call_args["transcript_text"], "Sample transcript for success test.")
        self.assertEqual(call_args["channel_id"], "UC_TestChannel")

        # Verify result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["video_id"], "test_video_123")
        self.assertEqual(result["chunk_count"], 5)
        self.assertIn("sinks", result)

    @patch('core.rag.ingest_transcript.ingest')
    def test_run_with_optional_fields(self, mock_ingest):
        """Test run() passes optional fields to core library."""
        mock_ingest.return_value = {
            "status": "success",
            "video_id": "test_video_123",
            "chunk_count": 3,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Sample transcript.",
            channel_id="UC_TestChannel",
            title="Test Video",
            channel_handle="@TestChannel",
            published_at="2025-10-08T12:00:00Z",
            duration_sec=1200
        )

        tool.run()

        # Verify all optional fields were passed
        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["title"], "Test Video")
        self.assertEqual(call_args["channel_handle"], "@TestChannel")
        self.assertEqual(call_args["published_at"], "2025-10-08T12:00:00Z")
        self.assertEqual(call_args["duration_sec"], 1200)

    @patch('core.rag.ingest_transcript.ingest')
    def test_run_partial_success(self, mock_ingest):
        """Test partial indexing (some sinks fail)."""
        mock_ingest.return_value = {
            "status": "partial",
            "video_id": "test_video_123",
            "chunk_count": 5,
            "sinks": {
                "opensearch": {"status": "indexed", "indexed_count": 5},
                "bigquery": {"status": "error", "message": "BigQuery unavailable"},
                "zep": {"status": "upserted", "upserted_count": 5}
            },
            "message": "Partial ingestion: BigQuery failed"
        }

        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Sample transcript.",
            channel_id="UC_TestChannel"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "partial")
        self.assertIn("BigQuery", result["message"])

    @patch('core.rag.ingest_transcript.ingest')
    def test_run_core_library_error(self, mock_ingest):
        """Test error handling when core library raises exception."""
        mock_ingest.side_effect = Exception("Core library connection failed")

        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Sample transcript.",
            channel_id="UC_TestChannel"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["video_id"], "test_video_123")
        self.assertIn("Core library connection failed", result["message"])

    @patch('core.rag.ingest_transcript.ingest')
    def test_run_core_library_returns_error_status(self, mock_ingest):
        """Test handling of error status from core library."""
        mock_ingest.return_value = {
            "status": "error",
            "message": "Missing required fields: video_id, transcript_text, channel_id"
        }

        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Sample transcript.",
            channel_id="UC_TestChannel"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "error")
        self.assertIn("Missing required fields", result["message"])

    @patch('core.rag.ingest_transcript.ingest')
    def test_run_returns_json_string(self, mock_ingest):
        """Test that run() returns a JSON string, not a dict."""
        mock_ingest.return_value = {
            "status": "success",
            "video_id": "test_video_123",
            "chunk_count": 2,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text="Sample transcript.",
            channel_id="UC_TestChannel"
        )

        result = tool.run()

        # Verify it's a string
        self.assertIsInstance(result, str)

        # Verify it's valid JSON
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "success")

    def test_payload_omits_none_values(self):
        """Test that optional fields with None values are omitted from payload."""
        with patch('core.rag.ingest_transcript.ingest') as mock_ingest:
            mock_ingest.return_value = {
                "status": "success",
                "video_id": "test_video_123",
                "chunk_count": 1,
                "sinks": {},
                "message": "Success"
            }

            tool = self.RagIndexTranscript(
                video_id="test_video_123",
                transcript_text="Sample transcript.",
                channel_id="UC_TestChannel"
                # title, published_at, duration_sec all None
            )

            tool.run()

            call_args = mock_ingest.call_args[0][0]
            # Verify None values are NOT in payload
            self.assertNotIn("title", call_args)
            self.assertNotIn("published_at", call_args)
            self.assertNotIn("duration_sec", call_args)
            self.assertNotIn("channel_handle", call_args)

    @patch('core.rag.ingest_transcript.ingest')
    def test_run_long_transcript(self, mock_ingest):
        """Test handling of long transcripts (chunking test)."""
        mock_ingest.return_value = {
            "status": "success",
            "video_id": "test_video_123",
            "chunk_count": 25,
            "sinks": {
                "opensearch": {"status": "indexed", "indexed_count": 25}
            },
            "message": "Ingested 25 chunks"
        }

        long_transcript = "Sample transcript text. " * 1000  # ~25,000 characters

        tool = self.RagIndexTranscript(
            video_id="test_video_123",
            transcript_text=long_transcript,
            channel_id="UC_TestChannel"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["chunk_count"], 25)


if __name__ == "__main__":
    unittest.main()
