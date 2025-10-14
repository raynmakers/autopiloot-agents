"""
Tests for Summarizer Agent RAG Wrappers and Shims (TASK-0097)

Validates:
1. RagHybridSearch wrapper delegates to core.rag.hybrid_retrieve.search()
2. Deprecated shims (OpenSearch, BigQuery, Zep) delegate to core.rag.ingest_transcript.ingest()
3. Deprecation warnings are printed for shims
4. Backward-compatible response formats maintained by shims
5. Error handling in both wrappers and shims

Target: ≥80% coverage for wrapper and shim delegation logic
"""

import os
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestRagHybridSearchWrapper(unittest.TestCase):
    """Tests for RagHybridSearch wrapper (delegates to core library)"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_search_result = {
            "results": [
                {
                    "chunk_id": "abc123_chunk_1",
                    "video_id": "abc123",
                    "title": "Test Video",
                    "text": "Sample content",
                    "score": 0.85,
                    "sources": ["zep", "opensearch"]
                }
            ],
            "total_results": 1,
            "sources_used": ["zep", "opensearch"],
            "fusion_method": "rrf",
            "latency_ms": 145,
            "coverage": 100.0
        }

    @patch('summarizer_agent.tools.rag_hybrid_search.search')
    def test_wrapper_delegates_to_core_search(self, mock_search):
        """Test that RagHybridSearch delegates to core.rag.hybrid_retrieve.search()"""
        # Import after patching
        from summarizer_agent.tools.rag_hybrid_search import RagHybridSearch

        # Mock core library search
        mock_search.return_value = self.mock_search_result

        # Create and run tool
        tool = RagHybridSearch(
            query="How to hire A-players",
            filters={"channel_id": "UC123"},
            limit=10
        )
        result_json = tool.run()
        result = json.loads(result_json)

        # Verify delegation
        mock_search.assert_called_once_with(
            query="How to hire A-players",
            filters={"channel_id": "UC123"},
            limit=10
        )

        # Verify result structure
        self.assertEqual(result["total_results"], 1)
        self.assertEqual(result["sources_used"], ["zep", "opensearch"])

    @patch('summarizer_agent.tools.rag_hybrid_search.search')
    def test_wrapper_handles_empty_results(self, mock_search):
        """Test that wrapper handles empty search results gracefully"""
        from summarizer_agent.tools.rag_hybrid_search import RagHybridSearch

        # Mock empty result
        mock_search.return_value = {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "fusion_method": "rrf",
            "latency_ms": 50
        }

        tool = RagHybridSearch(query="nonexistent content")
        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["total_results"], 0)
        self.assertEqual(result["results"], [])

    @patch('summarizer_agent.tools.rag_hybrid_search.search')
    def test_wrapper_handles_core_library_error(self, mock_search):
        """Test that wrapper handles exceptions from core library"""
        from summarizer_agent.tools.rag_hybrid_search import RagHybridSearch

        # Mock exception
        mock_search.side_effect = RuntimeError("Core library error")

        tool = RagHybridSearch(query="test query")
        result_json = tool.run()
        result = json.loads(result_json)

        # Should return error response
        self.assertEqual(result["error"], "search_failed")
        self.assertIn("Core library error", result["message"])
        self.assertEqual(result["total_results"], 0)


class TestOpenSearchShim(unittest.TestCase):
    """Tests for IndexFullTranscriptToOpenSearch shim"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_ingest_result = {
            "status": "success",
            "chunk_count": 5,
            "content_hashes": ["hash1", "hash2", "hash3", "hash4", "hash5"],
            "total_tokens": 4500,
            "message": "Indexed successfully",
            "sinks": {
                "opensearch": {
                    "status": "indexed",
                    "index_name": "autopiloot_transcripts",
                    "chunks_indexed": 5
                }
            }
        }

    @patch('builtins.print')
    @patch('summarizer_agent.tools.index_full_transcript_to_opensearch.ingest')
    def test_shim_prints_deprecation_warning(self, mock_ingest, mock_print):
        """Test that shim prints deprecation warning"""
        from summarizer_agent.tools.index_full_transcript_to_opensearch import IndexFullTranscriptToOpenSearch

        mock_ingest.return_value = self.mock_ingest_result

        tool = IndexFullTranscriptToOpenSearch(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123"
        )
        tool.run()

        # Check that deprecation warning was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        deprecation_found = any("DEPRECATION WARNING" in call for call in print_calls)
        self.assertTrue(deprecation_found, "Deprecation warning should be printed")

    @patch('builtins.print')
    @patch('summarizer_agent.tools.index_full_transcript_to_opensearch.ingest')
    def test_shim_delegates_to_core_ingest(self, mock_ingest, mock_print):
        """Test that OpenSearch shim delegates to core.rag.ingest_transcript.ingest()"""
        from summarizer_agent.tools.index_full_transcript_to_opensearch import IndexFullTranscriptToOpenSearch

        mock_ingest.return_value = self.mock_ingest_result

        tool = IndexFullTranscriptToOpenSearch(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123",
            title="Test Video",
            published_at="2025-10-08T12:00:00Z"
        )
        result_json = tool.run()
        result = json.loads(result_json)

        # Verify delegation
        mock_ingest.assert_called_once()
        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["video_id"], "test123")
        self.assertEqual(call_args["transcript_text"], "Sample transcript")
        self.assertEqual(call_args["channel_id"], "UC123")

        # Verify backward-compatible response format
        self.assertEqual(result["status"], "indexed")
        self.assertEqual(result["video_id"], "test123")
        self.assertEqual(result["chunk_count"], 5)
        self.assertEqual(result["indexed_count"], 5)

    @patch('builtins.print')
    @patch('summarizer_agent.tools.index_full_transcript_to_opensearch.ingest')
    def test_shim_handles_skipped_status(self, mock_ingest, mock_print):
        """Test that shim handles skipped status (OpenSearch not configured)"""
        from summarizer_agent.tools.index_full_transcript_to_opensearch import IndexFullTranscriptToOpenSearch

        mock_ingest.return_value = {
            "status": "skipped",
            "message": "OpenSearch not configured"
        }

        tool = IndexFullTranscriptToOpenSearch(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123"
        )
        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "skipped")
        self.assertIn("not configured", result["message"])


class TestBigQueryShim(unittest.TestCase):
    """Tests for StreamFullTranscriptToBigQuery shim"""

    @patch('builtins.print')
    @patch('summarizer_agent.tools.stream_full_transcript_to_bigquery.ingest')
    def test_shim_prints_deprecation_warning(self, mock_ingest, mock_print):
        """Test that BigQuery shim prints deprecation warning"""
        from summarizer_agent.tools.stream_full_transcript_to_bigquery import StreamFullTranscriptToBigQuery

        mock_ingest.return_value = {
            "status": "success",
            "chunk_count": 3,
            "content_hashes": ["hash1", "hash2", "hash3"],
            "total_tokens": 2500
        }

        tool = StreamFullTranscriptToBigQuery(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123"
        )
        tool.run()

        # Check that deprecation warning was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        deprecation_found = any("DEPRECATION WARNING" in call for call in print_calls)
        self.assertTrue(deprecation_found, "Deprecation warning should be printed")

    @patch('builtins.print')
    @patch('summarizer_agent.tools.stream_full_transcript_to_bigquery.ingest')
    def test_shim_delegates_to_core_ingest(self, mock_ingest, mock_print):
        """Test that BigQuery shim delegates to core library"""
        from summarizer_agent.tools.stream_full_transcript_to_bigquery import StreamFullTranscriptToBigQuery

        mock_ingest.return_value = {
            "status": "success",
            "chunk_count": 3,
            "content_hashes": ["hash1", "hash2", "hash3"],
            "total_tokens": 2500,
            "sinks": {"bigquery": {"status": "streamed"}}
        }

        tool = StreamFullTranscriptToBigQuery(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123"
        )
        result_json = tool.run()
        result = json.loads(result_json)

        # Verify delegation
        mock_ingest.assert_called_once()

        # Verify backward-compatible response format
        self.assertEqual(result["status"], "streamed")
        self.assertEqual(result["dataset"], "autopiloot")
        self.assertEqual(result["table"], "transcript_chunks")
        self.assertEqual(result["chunk_count"], 3)


class TestZepShim(unittest.TestCase):
    """Tests for UpsertFullTranscriptToZep shim"""

    @patch('builtins.print')
    @patch('summarizer_agent.tools.upsert_full_transcript_to_zep.ingest')
    def test_shim_prints_deprecation_warning(self, mock_ingest, mock_print):
        """Test that Zep shim prints deprecation warning"""
        from summarizer_agent.tools.upsert_full_transcript_to_zep import UpsertFullTranscriptToZep

        mock_ingest.return_value = {
            "status": "success",
            "chunk_count": 4,
            "content_hashes": ["hash1", "hash2", "hash3", "hash4"],
            "total_tokens": 3500
        }

        tool = UpsertFullTranscriptToZep(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123"
        )
        tool.run()

        # Check that deprecation warning was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        deprecation_found = any("DEPRECATION WARNING" in call for call in print_calls)
        self.assertTrue(deprecation_found, "Deprecation warning should be printed")

    @patch('builtins.print')
    @patch('summarizer_agent.tools.upsert_full_transcript_to_zep.ingest')
    def test_shim_delegates_to_core_ingest(self, mock_ingest, mock_print):
        """Test that Zep shim delegates to core library"""
        from summarizer_agent.tools.upsert_full_transcript_to_zep import UpsertFullTranscriptToZep

        mock_ingest.return_value = {
            "status": "success",
            "chunk_count": 4,
            "content_hashes": ["hash1", "hash2", "hash3", "hash4"],
            "total_tokens": 3500,
            "sinks": {"zep": {"status": "stored"}}
        }

        tool = UpsertFullTranscriptToZep(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123",
            channel_handle="@TestChannel"
        )
        result_json = tool.run()
        result = json.loads(result_json)

        # Verify delegation
        mock_ingest.assert_called_once()

        # Verify backward-compatible response format
        self.assertEqual(result["status"], "stored")
        self.assertEqual(result["thread_id"], "transcript_test123")
        self.assertEqual(result["group"], "youtube_transcripts_UC123")
        self.assertEqual(result["chunk_count"], 4)
        self.assertEqual(result["channel_handle"], "@TestChannel")

    @patch('builtins.print')
    @patch('summarizer_agent.tools.upsert_full_transcript_to_zep.ingest')
    def test_shim_handles_error(self, mock_ingest, mock_print):
        """Test that shim handles errors from core library"""
        from summarizer_agent.tools.upsert_full_transcript_to_zep import UpsertFullTranscriptToZep

        mock_ingest.side_effect = RuntimeError("Zep connection error")

        tool = UpsertFullTranscriptToZep(
            video_id="test123",
            transcript_text="Sample transcript",
            channel_id="UC123"
        )
        result_json = tool.run()
        result = json.loads(result_json)

        # Should return error response
        self.assertEqual(result["error"], "storage_failed")
        self.assertIn("Zep connection error", result["message"])
        self.assertEqual(result["video_id"], "test123")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
