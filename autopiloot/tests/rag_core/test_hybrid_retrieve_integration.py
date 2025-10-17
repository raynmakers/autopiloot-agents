"""
Integration tests for hybrid retrieval and policy modules.

Tests hybrid_retrieve.py, retrieval_policy.py, and tracing.py with mocked sources.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add core/rag to path
from core.rag import hybrid_retrieve, retrieval_policy, tracing


class TestHybridRetrieveIntegration(unittest.TestCase):
    """Integration tests for hybrid retrieval module."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_results_zep = [
            {
                "chunk_id": "abc_0",
                "video_id": "abc123",
                "title": "Revenue Growth",
                "text": "Revenue growth strategies...",
                "score": 0.95,
                "content_sha256": "hash_abc_0",
                "source": "zep"
            }
        ]

        self.sample_results_opensearch = [
            {
                "chunk_id": "abc_1",
                "video_id": "abc123",
                "title": "Revenue Growth",
                "text": "Marketing tactics for revenue...",
                "score": 0.88,
                "content_sha256": "hash_abc_1",
                "source": "opensearch"
            }
        ]

    @patch('core.rag.hybrid_retrieve.is_sink_enabled')
    @patch('core.rag.hybrid_retrieve._query_zep')
    @patch('core.rag.hybrid_retrieve._query_opensearch')
    @patch('core.rag.hybrid_retrieve._query_bigquery')
    def test_search_with_mocked_sources(self, mock_bq, mock_os, mock_zep, mock_enabled):
        """Test search with mocked source responses."""
        # Configure mocks
        mock_enabled.side_effect = lambda sink: sink in ["zep", "opensearch"]

        mock_zep.return_value = {
            "status": "success",
            "results": self.sample_results_zep
        }

        mock_os.return_value = {
            "status": "success",
            "results": self.sample_results_opensearch
        }

        mock_bq.return_value = {"status": "skipped"}

        # Execute search
        result = hybrid_retrieve.search(
            query="revenue growth",
            filters={"channel_id": "UC123"},
            limit=10
        )

        # Verify results
        self.assertIn("results", result)
        self.assertIn("sources_used", result)
        self.assertIn("fusion_method", result)
        self.assertIn("latency_ms", result)

        # Verify sources
        self.assertIn("zep", result["sources_used"])
        self.assertIn("opensearch", result["sources_used"])

        # Verify results are deduplicated and ranked
        self.assertGreater(len(result["results"]), 0)

    def test_rrf_fusion(self):
        """Test RRF fusion algorithm."""
        source_results = {
            "zep": self.sample_results_zep,
            "opensearch": self.sample_results_opensearch
        }

        fused = hybrid_retrieve._rrf_fusion(source_results, k=60)

        # Verify fusion
        self.assertIsInstance(fused, list)
        self.assertGreater(len(fused), 0)

        # Verify structure
        for result in fused:
            self.assertIn("score", result)
            self.assertIn("sources", result)
            self.assertIn("provenance", result)

    def test_weighted_fusion(self):
        """Test weighted fusion algorithm."""
        source_results = {
            "zep": self.sample_results_zep,
            "opensearch": self.sample_results_opensearch
        }

        weights = {"zep": 0.6, "opensearch": 0.4}
        fused = hybrid_retrieve._weighted_fusion(source_results, weights)

        # Verify fusion
        self.assertIsInstance(fused, list)
        self.assertGreater(len(fused), 0)

        for result in fused:
            self.assertIn("score", result)


class TestRetrievalPolicyIntegration(unittest.TestCase):
    """Integration tests for retrieval policy module."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_results = [
            {
                "chunk_id": "abc_0",
                "video_id": "abc123",
                "channel_id": "UC123",
                "text": "Call me at 555-123-4567 for details.",
                "score": 0.95
            },
            {
                "chunk_id": "def_0",
                "video_id": "def456",
                "channel_id": "UC456",
                "text": "Revenue grew to $1M last quarter.",
                "score": 0.88
            }
        ]

    def test_enforce_policy_channel_filter(self):
        """Test policy enforcement with channel filtering."""
        policy_context = {
            "allowed_channels": ["UC123"],
            "redact_pii": False
        }

        result = retrieval_policy.enforce_policy(
            self.sample_results,
            policy_context=policy_context
        )

        # Verify filtering
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["filtered_count"], 1)
        self.assertEqual(result["results"][0]["channel_id"], "UC123")

    def test_enforce_policy_pii_redaction(self):
        """Test PII redaction."""
        policy_context = {
            "redact_pii": True
        }

        result = retrieval_policy.enforce_policy(
            self.sample_results,
            policy_context=policy_context
        )

        # Check that PII was detected
        self.assertGreater(result["redacted_count"], 0)

        # Verify phone number was redacted in first result
        first_result_text = result["results"][0]["text"]
        self.assertNotIn("555-123-4567", first_result_text)

    def test_enforce_policy_audit_only_mode(self):
        """Test audit-only mode (logs violations but doesn't filter)."""
        policy_context = {
            "allowed_channels": ["UC123"],
            "mode": "audit_only"
        }

        result = retrieval_policy.enforce_policy(
            self.sample_results,
            policy_context=policy_context
        )

        # In audit_only mode, all results should be returned
        self.assertEqual(len(result["results"]), len(self.sample_results))
        self.assertEqual(result["policy_mode"], "audit_only")

    def test_validate_policy_config(self):
        """Test policy configuration validation."""
        validation = retrieval_policy.validate_policy_config()

        self.assertIn("valid", validation)
        self.assertIn("errors", validation)
        self.assertIn("warnings", validation)
        self.assertIn("recommendations", validation)

        self.assertIsInstance(validation["valid"], bool)


class TestTracingIntegration(unittest.TestCase):
    """Integration tests for tracing module."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset metrics before each test
        tracing.reset_metrics()

    def test_create_trace_id(self):
        """Test trace ID generation."""
        trace1 = tracing.create_trace_id()
        trace2 = tracing.create_trace_id()

        self.assertIsInstance(trace1, str)
        self.assertTrue(trace1.startswith("rag_"))
        self.assertNotEqual(trace1, trace2)

    def test_emit_retrieval_event(self):
        """Test retrieval event emission."""
        trace_id = tracing.create_trace_id()

        # Emit event
        tracing.emit_retrieval_event(
            trace_id=trace_id,
            query="test query",
            filters={"channel_id": "UC123"},
            total_results=10,
            sources_used=["zep", "opensearch"],
            latency_ms=1234,
            source_latencies={"zep": 567, "opensearch": 432},
            coverage=66.7
        )

        # Verify event was stored
        summary = tracing.get_metrics_summary()
        self.assertEqual(summary["total_retrievals"], 1)

    def test_emit_ingest_event(self):
        """Test ingest event emission."""
        tracing.emit_ingest_event(
            operation="transcript",
            video_id="abc123",
            chunk_count=10,
            sinks_used=["zep", "opensearch"],
            success_count=10,
            error_count=0,
            latency_ms=2345
        )

        # Verify event was stored
        summary = tracing.get_metrics_summary()
        self.assertEqual(summary["total_ingests"], 1)

    def test_get_metrics_summary(self):
        """Test metrics summary generation."""
        # Emit some events
        trace1 = tracing.create_trace_id()
        tracing.emit_retrieval_event(
            trace_id=trace1,
            query="query 1",
            filters=None,
            total_results=5,
            sources_used=["zep"],
            latency_ms=1000,
            source_latencies={"zep": 1000},
            coverage=33.3
        )

        trace2 = tracing.create_trace_id()
        tracing.emit_retrieval_event(
            trace_id=trace2,
            query="query 2",
            filters=None,
            total_results=10,
            sources_used=["zep", "opensearch"],
            latency_ms=1500,
            source_latencies={"zep": 800, "opensearch": 700},
            coverage=66.7
        )

        # Get summary
        summary = tracing.get_metrics_summary(time_window_minutes=60)

        self.assertEqual(summary["total_retrievals"], 2)
        self.assertIn("avg_latency_ms", summary)
        self.assertIn("p95_latency_ms", summary)
        self.assertIn("avg_coverage", summary)
        self.assertIn("per_source_latency", summary)

    def test_reset_metrics(self):
        """Test metrics reset."""
        # Emit event
        trace_id = tracing.create_trace_id()
        tracing.emit_retrieval_event(
            trace_id=trace_id,
            query="test",
            filters=None,
            total_results=5,
            sources_used=["zep"],
            latency_ms=1000,
            source_latencies={"zep": 1000},
            coverage=33.3
        )

        # Verify event exists
        summary_before = tracing.get_metrics_summary()
        self.assertEqual(summary_before["total_retrievals"], 1)

        # Reset
        tracing.reset_metrics()

        # Verify metrics cleared
        summary_after = tracing.get_metrics_summary()
        self.assertEqual(summary_after["total_retrievals"], 0)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
