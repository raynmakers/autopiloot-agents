"""
Comprehensive test suite for CacheHybridRetrieval tool.
Tests caching operations, hit ratio tracking, TTL, and bypass rules.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestCacheHybridRetrieval(unittest.TestCase):
    """Test suite for CacheHybridRetrieval tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'cache_hybrid_retrieval.py'
        )
        spec = importlib.util.spec_from_file_location("cache_hybrid_retrieval", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.CacheHybridRetrieval

        # Clear cache before each test
        self.ToolClass._memory_cache = {}
        self.ToolClass._cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    def tearDown(self):
        """Clean up after each test."""
        # Clear cache after each test
        self.ToolClass._memory_cache = {}
        self.ToolClass._cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    def test_normalize_query(self):
        """Test query normalization (lowercase, strip)."""
        tool = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        normalized = tool._normalize_query("  How To INCREASE Revenue  ")
        self.assertEqual(normalized, "how to increase revenue")

    def test_generate_cache_key_consistency(self):
        """Test cache key generation is consistent for same inputs."""
        tool = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        key1 = tool._generate_cache_key("test query", {"filter": "value"}, 10)
        key2 = tool._generate_cache_key("test query", {"filter": "value"}, 10)

        self.assertEqual(key1, key2)
        self.assertTrue(key1.startswith("hybrid_cache:"))

    def test_generate_cache_key_different_queries(self):
        """Test cache key generation differs for different queries."""
        tool = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        key1 = tool._generate_cache_key("query 1", None, 10)
        key2 = tool._generate_cache_key("query 2", None, 10)

        self.assertNotEqual(key1, key2)

    def test_generate_cache_key_different_filters(self):
        """Test cache key generation differs for different filters."""
        tool = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        key1 = tool._generate_cache_key("test", {"filter": "value1"}, 10)
        key2 = tool._generate_cache_key("test", {"filter": "value2"}, 10)

        self.assertNotEqual(key1, key2)

    def test_generate_cache_key_different_top_k(self):
        """Test cache key generation differs for different top_k."""
        tool = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        key1 = tool._generate_cache_key("test", None, 10)
        key2 = tool._generate_cache_key("test", None, 20)

        self.assertNotEqual(key1, key2)

    def test_should_bypass_cache_explicit_flag(self):
        """Test cache bypass with explicit flag."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            query="test",
            bypass_cache=True
        )

        should_bypass = tool._should_bypass_cache(None, 10)
        self.assertTrue(should_bypass)

    def test_should_bypass_cache_time_filter(self):
        """Test cache bypass with time-based filter."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            query="test"
        )

        should_bypass = tool._should_bypass_cache({"timestamp": "2025-10-13"}, 10)
        self.assertTrue(should_bypass)

    def test_should_bypass_cache_small_top_k(self):
        """Test cache bypass with small top_k."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            query="test"
        )

        should_bypass = tool._should_bypass_cache(None, 3)
        self.assertTrue(should_bypass)

    def test_should_bypass_cache_normal_conditions(self):
        """Test cache not bypassed under normal conditions."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            query="test"
        )

        should_bypass = tool._should_bypass_cache({"channel": "business"}, 10)
        self.assertFalse(should_bypass)

    def test_set_operation_success(self):
        """Test successful SET operation."""
        results_data = [{"doc_id": "1", "score": 0.95}]

        tool = self.ToolClass(
            backend="memory",
            operation="set",
            query="test query",
            filters=json.dumps({"channel": "business"}),
            top_k=10,
            results=json.dumps(results_data),
            ttl_seconds=3600
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "set")
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["bypass"])
        self.assertIn("cache_key", data)
        self.assertEqual(data["ttl_seconds"], 3600)

    def test_get_operation_cache_hit(self):
        """Test GET operation with cache hit."""
        # First, set a value
        results_data = [{"doc_id": "1", "score": 0.95}]

        tool_set = self.ToolClass(
            backend="memory",
            operation="set",
            query="test query",
            top_k=10,
            results=json.dumps(results_data),
            ttl_seconds=3600
        )
        tool_set.run()

        # Now, get the value (should hit)
        tool_get = self.ToolClass(
            backend="memory",
            operation="get",
            query="test query",
            top_k=10
        )

        result = tool_get.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "get")
        self.assertTrue(data["hit"])
        self.assertFalse(data["bypass"])
        self.assertEqual(data["results"], results_data)
        self.assertEqual(data["status"], "success")

    def test_get_operation_cache_miss(self):
        """Test GET operation with cache miss."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            query="nonexistent query",
            top_k=10
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "get")
        self.assertFalse(data["hit"])
        self.assertIsNone(data["results"])
        self.assertEqual(data["status"], "success")

    def test_get_operation_bypass(self):
        """Test GET operation with cache bypass."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            query="test",
            filters=json.dumps({"timestamp": "2025-10-13"}),
            top_k=10
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "get")
        self.assertFalse(data["hit"])
        self.assertTrue(data["bypass"])
        self.assertIn("reason", data)
        self.assertEqual(data["status"], "success")

    def test_delete_operation_success(self):
        """Test successful DELETE operation."""
        # First, set a value
        results_data = [{"doc_id": "1", "score": 0.95}]

        tool_set = self.ToolClass(
            backend="memory",
            operation="set",
            query="test query",
            top_k=10,
            results=json.dumps(results_data),
            ttl_seconds=3600
        )
        tool_set.run()

        # Now, delete it
        tool_delete = self.ToolClass(
            backend="memory",
            operation="delete",
            query="test query",
            top_k=10
        )

        result = tool_delete.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "delete")
        self.assertTrue(data["deleted"])
        self.assertEqual(data["status"], "success")

    def test_delete_operation_nonexistent(self):
        """Test DELETE operation on nonexistent key."""
        tool = self.ToolClass(
            backend="memory",
            operation="delete",
            query="nonexistent",
            top_k=10
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "delete")
        self.assertFalse(data["deleted"])
        self.assertEqual(data["status"], "success")

    def test_clear_operation(self):
        """Test CLEAR operation."""
        # Set multiple values
        for i in range(3):
            tool_set = self.ToolClass(
                backend="memory",
                operation="set",
                query=f"query {i}",
                top_k=10,
                results=json.dumps([{"doc_id": str(i)}]),
                ttl_seconds=3600
            )
            tool_set.run()

        # Now clear all
        tool_clear = self.ToolClass(
            backend="memory",
            operation="clear"
        )

        result = tool_clear.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "clear")
        self.assertEqual(data["cleared_count"], 3)
        self.assertEqual(data["backend"], "memory")
        self.assertEqual(data["status"], "success")

    def test_stats_operation(self):
        """Test STATS operation."""
        # Set a value
        tool_set = self.ToolClass(
            backend="memory",
            operation="set",
            query="test",
            top_k=10,
            results=json.dumps([{"doc_id": "1"}]),
            ttl_seconds=3600
        )
        tool_set.run()

        # Get it (hit)
        tool_get = self.ToolClass(
            backend="memory",
            operation="get",
            query="test",
            top_k=10
        )
        tool_get.run()

        # Get nonexistent (miss)
        tool_miss = self.ToolClass(
            backend="memory",
            operation="get",
            query="nonexistent",
            top_k=10
        )
        tool_miss.run()

        # Get stats
        tool_stats = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        result = tool_stats.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "stats")
        self.assertEqual(data["status"], "success")
        self.assertIn("stats", data)

        stats = data["stats"]
        self.assertEqual(stats["backend"], "memory")
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["sets"], 1)
        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["hit_ratio_percent"], 50.0)
        self.assertGreater(stats["cache_size"], 0)

    def test_ttl_expiration(self):
        """Test TTL expiration removes entries from cache."""
        # Set value with 1 second TTL
        tool_set = self.ToolClass(
            backend="memory",
            operation="set",
            query="test",
            top_k=10,
            results=json.dumps([{"doc_id": "1"}]),
            ttl_seconds=1
        )
        tool_set.run()

        # Immediately get it (should hit)
        tool_get1 = self.ToolClass(
            backend="memory",
            operation="get",
            query="test",
            top_k=10
        )
        result1 = tool_get1.run()
        data1 = json.loads(result1)
        self.assertTrue(data1["hit"])

        # Wait for TTL to expire
        time.sleep(1.1)

        # Get again (should miss due to expiration)
        tool_get2 = self.ToolClass(
            backend="memory",
            operation="get",
            query="test",
            top_k=10
        )
        result2 = tool_get2.run()
        data2 = json.loads(result2)
        self.assertFalse(data2["hit"])

    def test_set_operation_missing_results(self):
        """Test SET operation with missing results parameter."""
        tool = self.ToolClass(
            backend="memory",
            operation="set",
            query="test",
            top_k=10,
            # Missing results parameter
            ttl_seconds=3600
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "missing_results")

    def test_get_operation_missing_query(self):
        """Test GET operation with missing query parameter."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            # Missing query parameter
            top_k=10
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "missing_query")

    def test_invalid_operation(self):
        """Test invalid operation type."""
        tool = self.ToolClass(
            backend="memory",
            operation="invalid_op"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "invalid_operation")

    def test_cache_key_explicit(self):
        """Test using explicit cache key."""
        explicit_key = "explicit_cache_key"

        # Set with explicit key
        tool_set = self.ToolClass(
            backend="memory",
            operation="set",
            cache_key=explicit_key,
            query="test",
            results=json.dumps([{"doc_id": "1"}]),
            ttl_seconds=3600
        )
        result_set = tool_set.run()
        data_set = json.loads(result_set)
        self.assertEqual(data_set["cache_key"], explicit_key)

        # Get with explicit key
        tool_get = self.ToolClass(
            backend="memory",
            operation="get",
            cache_key=explicit_key,
            query="test"
        )
        result_get = tool_get.run()
        data_get = json.loads(result_get)
        self.assertTrue(data_get["hit"])

    def test_multiple_cache_entries(self):
        """Test multiple cache entries coexist."""
        queries = ["query 1", "query 2", "query 3"]

        # Set multiple entries
        for query in queries:
            tool = self.ToolClass(
                backend="memory",
                operation="set",
                query=query,
                top_k=10,
                results=json.dumps([{"query": query}]),
                ttl_seconds=3600
            )
            tool.run()

        # Verify all can be retrieved
        for query in queries:
            tool = self.ToolClass(
                backend="memory",
                operation="get",
                query=query,
                top_k=10
            )
            result = tool.run()
            data = json.loads(result)
            self.assertTrue(data["hit"])
            self.assertEqual(data["results"][0]["query"], query)

    def test_cache_stats_include_timestamp(self):
        """Test cache stats include timestamp."""
        tool = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("timestamp", data["stats"])
        self.assertTrue(data["stats"]["timestamp"].endswith("Z"))

    def test_hit_ratio_calculation(self):
        """Test hit ratio calculation with various scenarios."""
        # All hits
        tool_set = self.ToolClass(
            backend="memory",
            operation="set",
            query="test",
            top_k=10,
            results=json.dumps([{"doc_id": "1"}]),
            ttl_seconds=3600
        )
        tool_set.run()

        for _ in range(5):
            tool_get = self.ToolClass(
                backend="memory",
                operation="get",
                query="test",
                top_k=10
            )
            tool_get.run()

        tool_stats = self.ToolClass(
            backend="memory",
            operation="stats"
        )
        result = tool_stats.run()
        data = json.loads(result)

        # Should be 100% hit ratio
        self.assertEqual(data["stats"]["hit_ratio_percent"], 100.0)

    def test_filters_none_vs_empty(self):
        """Test cache key generation with None vs empty filters."""
        tool = self.ToolClass(
            backend="memory",
            operation="stats"
        )

        key1 = tool._generate_cache_key("test", None, 10)
        key2 = tool._generate_cache_key("test", {}, 10)

        # Different filters should produce different keys
        self.assertNotEqual(key1, key2)

    def test_set_operation_bypass(self):
        """Test SET operation with cache bypass."""
        tool = self.ToolClass(
            backend="memory",
            operation="set",
            query="test",
            filters=json.dumps({"timestamp": "2025-10-13"}),
            top_k=10,
            results=json.dumps([{"doc_id": "1"}]),
            ttl_seconds=3600
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "set")
        self.assertTrue(data["bypass"])
        self.assertIn("reason", data)
        self.assertEqual(data["status"], "success")

    def test_exception_handling_in_run(self):
        """Test exception handling in run method."""
        tool = self.ToolClass(
            backend="memory",
            operation="get",
            query="test",
            filters="invalid json {",  # Invalid JSON to trigger exception
            top_k=10
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "cache_operation_failed")
        self.assertIn("message", data)


if __name__ == '__main__':
    unittest.main()
