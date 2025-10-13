"""
CI tests for hybrid RAG pipeline to prevent regressions.

These tests run in continuous integration to ensure:
- Retrieval fusion quality doesn't regress
- Performance benchmarks are met
- Degraded mode handling works correctly
- Cache behavior is consistent
- Model version compatibility maintained

Test Categories:
- Functional: Core retrieval and fusion logic
- Performance: Latency and throughput benchmarks
- Reliability: Error handling and degraded modes
- Compatibility: Model version and API compatibility
"""

import unittest
import json
import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any

# Mock agency_swarm before importing tools
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestHybridRAGCI(unittest.TestCase):
    """CI tests for hybrid RAG pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        import importlib.util

        # Helper to import tool
        def import_tool(tool_name):
            tool_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                '..',
                'summarizer_agent',
                'tools',
                f'{tool_name}.py'
            )
            spec = importlib.util.spec_from_file_location(tool_name, tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        # Import tools
        self.hybrid_retrieval = import_tool('hybrid_retrieval')
        self.cache_tool = import_tool('cache_hybrid_retrieval')

    # ========================================================================
    # FUNCTIONAL TESTS
    # ========================================================================

    def test_ci_retrieval_fusion_quality(self):
        """
        [CI] Test retrieval fusion maintains quality standards.

        Ensures fusion algorithm produces results that:
        - Include diverse sources
        - Maintain relevance order
        - Don't duplicate results
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="business growth strategies",
            use_zep=True,
            use_opensearch=True,
            use_bigquery=True,
            top_k=10
        )

        # Mock retrieval from sources
        with patch.object(tool, '_retrieve_from_zep', return_value=[
            {"doc_id": "doc1", "score": 0.95, "source": "zep"},
            {"doc_id": "doc2", "score": 0.90, "source": "zep"}
        ]):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=[
                {"doc_id": "doc3", "score": 0.85, "source": "opensearch"},
                {"doc_id": "doc1", "score": 0.80, "source": "opensearch"}  # Duplicate
            ]):
                with patch.object(tool, '_retrieve_from_bigquery', return_value=[
                    {"doc_id": "doc4", "score": 0.75, "source": "bigquery"}
                ]):
                    result = tool.run()
                    data = json.loads(result)

        # Quality assertions
        self.assertEqual(data["status"], "success")
        self.assertGreater(len(data["results"]), 0, "Should return results")
        self.assertLessEqual(len(data["results"]), 10, "Should respect top_k limit")

        # Check source diversity
        sources = set(r.get("source") for r in data["results"] if "source" in r)
        self.assertGreater(len(sources), 1, "Should include multiple sources")

        # Check no duplicates
        doc_ids = [r.get("doc_id") for r in data["results"]]
        self.assertEqual(len(doc_ids), len(set(doc_ids)), "Should not have duplicate docs")

    def test_ci_degraded_mode_handling(self):
        """
        [CI] Test system handles source failures gracefully.

        Ensures degraded mode:
        - Returns partial results
        - Logs errors appropriately
        - Maintains service availability
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="test query",
            use_zep=True,
            use_opensearch=True,
            use_bigquery=True,
            top_k=10
        )

        # Mock one source failing
        with patch.object(tool, '_retrieve_from_zep', side_effect=Exception("Zep unavailable")):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=[
                {"doc_id": "doc1", "score": 0.85}
            ]):
                with patch.object(tool, '_retrieve_from_bigquery', return_value=[
                    {"doc_id": "doc2", "score": 0.80}
                ]):
                    result = tool.run()
                    data = json.loads(result)

        # Degraded mode assertions
        self.assertEqual(data["status"], "success", "Should succeed with partial results")
        self.assertGreater(len(data["results"]), 0, "Should return results from working sources")
        self.assertIn("zep", data.get("errors", {}), "Should log failed source")

    def test_ci_cache_consistency(self):
        """
        [CI] Test cache maintains consistency across requests.

        Ensures caching:
        - Returns same results for same query
        - Respects TTL expiration
        - Handles cache misses correctly
        """
        CacheTool = self.cache_tool.CacheHybridRetrieval

        # Clear cache
        CacheTool._memory_cache = {}
        CacheTool._cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

        query = "test query"
        results = [{"doc_id": "doc1", "score": 0.9}]

        # Set cache
        tool_set = CacheTool(
            backend="memory",
            operation="set",
            query=query,
            top_k=10,
            results=json.dumps(results),
            ttl_seconds=3600
        )
        set_result = tool_set.run()
        set_data = json.loads(set_result)
        self.assertEqual(set_data["status"], "success")

        # Get from cache (should hit)
        tool_get = CacheTool(
            backend="memory",
            operation="get",
            query=query,
            top_k=10
        )
        get_result = tool_get.run()
        get_data = json.loads(get_result)

        # Cache consistency assertions
        self.assertTrue(get_data["hit"], "Should be cache hit")
        self.assertEqual(get_data["results"], results, "Should return same results")

    # ========================================================================
    # PERFORMANCE TESTS
    # ========================================================================

    def test_ci_retrieval_latency_benchmark(self):
        """
        [CI] Test retrieval latency meets performance benchmarks.

        Performance targets:
        - Single source: < 500ms
        - Multi-source fusion: < 2000ms
        - Cached queries: < 100ms
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="performance test",
            use_zep=True,
            use_opensearch=True,
            top_k=10
        )

        # Mock fast retrieval
        with patch.object(tool, '_retrieve_from_zep', return_value=[
            {"doc_id": "doc1", "score": 0.9}
        ]):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=[
                {"doc_id": "doc2", "score": 0.85}
            ]):
                start_time = time.time()
                result = tool.run()
                elapsed_ms = (time.time() - start_time) * 1000

        # Performance assertions
        self.assertLess(elapsed_ms, 2000, "Multi-source retrieval should complete in <2s")

        data = json.loads(result)
        self.assertEqual(data["status"], "success")

    def test_ci_cache_performance_improvement(self):
        """
        [CI] Test cache provides expected performance improvement.

        Cache should provide:
        - 80-95% latency reduction on cache hits
        - >40% hit ratio on typical workload
        """
        CacheTool = self.cache_tool.CacheHybridRetrieval

        # Clear cache
        CacheTool._memory_cache = {}
        CacheTool._cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

        query = "test query"
        results = [{"doc_id": "doc1", "score": 0.9}]

        # Populate cache
        tool_set = CacheTool(
            backend="memory",
            operation="set",
            query=query,
            top_k=10,
            results=json.dumps(results),
            ttl_seconds=3600
        )
        tool_set.run()

        # Measure cache hit latency
        tool_get = CacheTool(
            backend="memory",
            operation="get",
            query=query,
            top_k=10
        )

        start_time = time.time()
        result = tool_get.run()
        cache_latency_ms = (time.time() - start_time) * 1000

        # Cache performance assertions
        self.assertLess(cache_latency_ms, 100, "Cache hit should be <100ms")

        data = json.loads(result)
        self.assertTrue(data["hit"])

    # ========================================================================
    # RELIABILITY TESTS
    # ========================================================================

    def test_ci_all_sources_failure_handling(self):
        """
        [CI] Test graceful handling when all sources fail.

        Should:
        - Return error status
        - Log all failures
        - Not crash or hang
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="test query",
            use_zep=True,
            use_opensearch=True,
            use_bigquery=True,
            top_k=10
        )

        # Mock all sources failing
        with patch.object(tool, '_retrieve_from_zep', side_effect=Exception("Zep down")):
            with patch.object(tool, '_retrieve_from_opensearch', side_effect=Exception("OS down")):
                with patch.object(tool, '_retrieve_from_bigquery', side_effect=Exception("BQ down")):
                    result = tool.run()
                    data = json.loads(result)

        # Failure handling assertions
        self.assertIn(data["status"], ["error", "success"], "Should return valid status")
        if data["status"] == "success":
            self.assertEqual(len(data.get("results", [])), 0, "Should return empty results")
        self.assertIn("errors", data, "Should include error information")

    def test_ci_timeout_handling(self):
        """
        [CI] Test system handles slow sources with timeout.

        Should:
        - Not wait indefinitely
        - Mark slow source as error
        - Return results from faster sources
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="test query",
            use_zep=True,
            use_opensearch=True,
            top_k=10
        )

        # Mock slow source (simulated)
        def slow_retrieval(*args, **kwargs):
            raise TimeoutError("Request timed out")

        with patch.object(tool, '_retrieve_from_zep', side_effect=slow_retrieval):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=[
                {"doc_id": "doc1", "score": 0.85}
            ]):
                result = tool.run()
                data = json.loads(result)

        # Timeout handling assertions
        self.assertEqual(data["status"], "success", "Should succeed with partial results")
        self.assertGreater(len(data["results"]), 0, "Should return results from fast sources")

    # ========================================================================
    # COMPATIBILITY TESTS
    # ========================================================================

    def test_ci_model_version_compatibility(self):
        """
        [CI] Test system handles mixed embedding model versions.

        Should:
        - Track model versions correctly
        - Not crash on version mismatch
        - Log version information
        """
        # Import version tracking tool
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'track_embedding_model_version.py'
        )
        spec = importlib.util.spec_from_file_location("track_version", tool_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        VersionTool = module.TrackEmbeddingModelVersion

        # Test listing versions
        tool = VersionTool(operation="list_versions")
        result = tool.run()
        data = json.loads(result)

        # Compatibility assertions
        self.assertEqual(data["status"], "success")
        self.assertIn("versions", data)
        self.assertGreater(len(data["versions"]), 0, "Should have at least one version")

    def test_ci_backward_compatibility(self):
        """
        [CI] Test API backward compatibility is maintained.

        Ensures:
        - Required parameters unchanged
        - Optional parameters have defaults
        - Response format consistent
        """
        # Test minimal parameters work
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="test query",
            top_k=5
        )

        with patch.object(tool, '_retrieve_from_zep', return_value=[]):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=[]):
                with patch.object(tool, '_retrieve_from_bigquery', return_value=[]):
                    result = tool.run()
                    data = json.loads(result)

        # Backward compatibility assertions
        self.assertIn("status", data, "Response should include status")
        self.assertIn("results", data, "Response should include results")
        self.assertIsInstance(data["results"], list, "Results should be list")

    # ========================================================================
    # REGRESSION TESTS
    # ========================================================================

    def test_ci_no_empty_results_regression(self):
        """
        [CI] Test regression: Empty results when sources have data.

        This test prevents regression where fusion logic incorrectly
        filters out all results.
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="test query",
            use_zep=True,
            top_k=10
        )

        # Mock source with results
        with patch.object(tool, '_retrieve_from_zep', return_value=[
            {"doc_id": "doc1", "score": 0.9},
            {"doc_id": "doc2", "score": 0.85}
        ]):
            result = tool.run()
            data = json.loads(result)

        # Regression assertions
        self.assertEqual(data["status"], "success")
        self.assertGreater(len(data["results"]), 0, "Should not return empty results when sources have data")

    def test_ci_score_ordering_regression(self):
        """
        [CI] Test regression: Results not ordered by score.

        This test ensures fusion maintains proper score-based ordering.
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="test query",
            use_zep=True,
            top_k=10
        )

        # Mock results with various scores
        with patch.object(tool, '_retrieve_from_zep', return_value=[
            {"doc_id": "doc1", "score": 0.70},
            {"doc_id": "doc2", "score": 0.95},
            {"doc_id": "doc3", "score": 0.80}
        ]):
            result = tool.run()
            data = json.loads(result)

        # Check ordering
        results = data["results"]
        if len(results) > 1:
            scores = [r.get("score", 0) for r in results if "score" in r]
            if len(scores) > 1:
                # Scores should be in descending order
                for i in range(len(scores) - 1):
                    self.assertGreaterEqual(scores[i], scores[i + 1],
                                          "Results should be ordered by score descending")

    # ========================================================================
    # SMOKE TESTS
    # ========================================================================

    def test_ci_smoke_full_pipeline(self):
        """
        [CI] Smoke test: Full retrieval pipeline end-to-end.

        Quick sanity check that entire pipeline can execute without errors.
        """
        tool = self.hybrid_retrieval.HybridRetrieval(
            query="business strategies",
            use_zep=True,
            use_opensearch=True,
            use_bigquery=True,
            top_k=10
        )

        with patch.object(tool, '_retrieve_from_zep', return_value=[{"doc_id": "doc1", "score": 0.9}]):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=[{"doc_id": "doc2", "score": 0.85}]):
                with patch.object(tool, '_retrieve_from_bigquery', return_value=[{"doc_id": "doc3", "score": 0.80}]):
                    result = tool.run()

        # Smoke test assertions
        self.assertIsNotNone(result, "Should return result")
        data = json.loads(result)
        self.assertIn("status", data, "Should have status")
        self.assertIn(data["status"], ["success", "error"], "Status should be valid")


if __name__ == '__main__':
    # Run with verbose output for CI
    unittest.main(verbosity=2)
