"""
Test suite for strategy_agent RAG search wrapper (rag_hybrid_search.py).

Tests wrapper initialization, filter handling, core library delegation,
and error handling for hybrid retrieval operations.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestRagHybridSearchWrapper(unittest.TestCase):
    """Test suite for RagHybridSearch tool wrapper."""

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
            'strategy_agent', 'tools', 'rag_hybrid_search.py'
        )
        spec = importlib.util.spec_from_file_location("rag_hybrid_search", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.RagHybridSearch = self.module.RagHybridSearch

    def tearDown(self):
        """Clean up after each test."""
        if "pydantic" in sys.modules:
            del sys.modules["pydantic"]
        if "agency_swarm" in sys.modules:
            del sys.modules['agency_swarm']
        if 'agency_swarm.tools' in sys.modules:
            del sys.modules['agency_swarm.tools']

    def test_init_with_required_fields(self):
        """Test initialization with only query (required)."""
        tool = self.RagHybridSearch(
            query="How to scale SaaS business"
        )

        self.assertEqual(tool.query, "How to scale SaaS business")
        self.assertIsNone(tool.filters)
        self.assertEqual(tool.limit, 20)  # default

    def test_init_with_custom_limit(self):
        """Test initialization with custom limit."""
        tool = self.RagHybridSearch(
            query="unit economics",
            limit=10
        )

        self.assertEqual(tool.limit, 10)

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_success(self, mock_search):
        """Test successful hybrid search."""
        mock_search.return_value = {
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "video_id": "video_123",
                    "title": "Test Video",
                    "text": "Sample text",
                    "score": 0.95,
                    "sources": ["zep", "opensearch"]
                }
            ],
            "total_results": 1,
            "sources_used": ["zep", "opensearch"],
            "fusion_method": "rrf",
            "latency_ms": 150,
            "source_latencies": {"zep": 80, "opensearch": 70},
            "coverage": 66.7,
            "trace_id": "trace_123"
        }

        tool = self.RagHybridSearch(
            query="How to scale SaaS"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["total_results"], 1)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["sources_used"], ["zep", "opensearch"])
        self.assertEqual(result["fusion_method"], "rrf")

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_with_channel_filter(self, mock_search):
        """Test search with channel_id filter."""
        mock_search.return_value = {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "fusion_method": "rrf",
            "latency_ms": 50,
            "source_latencies": {},
            "coverage": 0.0,
            "trace_id": "trace_123"
        }

        tool = self.RagHybridSearch(
            query="business strategy",
            filters={"channel_id": "UC123"}
        )

        tool.run()

        # Verify filter was passed to core library
        mock_search.assert_called_once_with(
            query="business strategy",
            filters={"channel_id": "UC123"},
            limit=20
        )

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_with_date_range_filter(self, mock_search):
        """Test search with date range filters."""
        mock_search.return_value = {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "fusion_method": "rrf",
            "latency_ms": 50,
            "source_latencies": {},
            "coverage": 0.0,
            "trace_id": "trace_123"
        }

        tool = self.RagHybridSearch(
            query="content strategy",
            filters={
                "date_from": "2025-09-01T00:00:00Z",
                "date_to": "2025-10-31T23:59:59Z"
            }
        )

        tool.run()

        call_args = mock_search.call_args
        self.assertEqual(call_args[1]["filters"]["date_from"], "2025-09-01T00:00:00Z")
        self.assertEqual(call_args[1]["filters"]["date_to"], "2025-10-31T23:59:59Z")

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_with_duration_filter(self, mock_search):
        """Test search with duration filters."""
        mock_search.return_value = {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "fusion_method": "rrf",
            "latency_ms": 50,
            "source_latencies": {},
            "coverage": 0.0,
            "trace_id": "trace_123"
        }

        tool = self.RagHybridSearch(
            query="video content",
            filters={
                "min_duration_sec": 600,
                "max_duration_sec": 3600
            }
        )

        tool.run()

        call_args = mock_search.call_args
        self.assertEqual(call_args[1]["filters"]["min_duration_sec"], 600)
        self.assertEqual(call_args[1]["filters"]["max_duration_sec"], 3600)

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_no_results(self, mock_search):
        """Test search that returns no results."""
        mock_search.return_value = {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "fusion_method": "rrf",
            "latency_ms": 100,
            "source_latencies": {},
            "coverage": 0.0,
            "trace_id": "trace_123",
            "message": "No results from any source"
        }

        tool = self.RagHybridSearch(
            query="nonexistent query"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["total_results"], 0)
        self.assertEqual(len(result["results"]), 0)
        self.assertIn("message", result)

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_error_handling(self, mock_search):
        """Test error handling when core library fails."""
        mock_search.side_effect = Exception("Connection timeout")

        tool = self.RagHybridSearch(
            query="test query"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["total_results"], 0)
        self.assertEqual(result["sources_used"], [])
        self.assertIn("error", result)
        self.assertIn("Connection timeout", result["message"])

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_returns_json_string(self, mock_search):
        """Test that run() returns a JSON string."""
        mock_search.return_value = {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "fusion_method": "rrf",
            "latency_ms": 50,
            "source_latencies": {},
            "coverage": 0.0,
            "trace_id": "trace_123"
        }

        tool = self.RagHybridSearch(
            query="test"
        )

        result = tool.run()

        # Verify it's a string
        self.assertIsInstance(result, str)

        # Verify it's valid JSON
        parsed = json.loads(result)
        self.assertIn("total_results", parsed)

    @patch('core.rag.hybrid_retrieve.search')
    def test_run_with_custom_limit(self, mock_search):
        """Test that custom limit is passed to core library."""
        mock_search.return_value = {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "fusion_method": "rrf",
            "latency_ms": 50,
            "source_latencies": {},
            "coverage": 0.0,
            "trace_id": "trace_123"
        }

        tool = self.RagHybridSearch(
            query="test query",
            limit=5
        )

        tool.run()

        # Verify limit was passed
        call_args = mock_search.call_args
        self.assertEqual(call_args[1]["limit"], 5)


if __name__ == "__main__":
    unittest.main()
