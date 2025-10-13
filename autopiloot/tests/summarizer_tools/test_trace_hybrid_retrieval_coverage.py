"""
Comprehensive test suite for TraceHybridRetrieval tool.
Tests latency tracking, error monitoring, coverage analysis, and alerting.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestTraceHybridRetrieval(unittest.TestCase):
    """Test suite for TraceHybridRetrieval tool."""

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
            'trace_hybrid_retrieval.py'
        )
        spec = importlib.util.spec_from_file_location("trace_hybrid_retrieval", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.TraceHybridRetrieval

        # Sample source traces
        self.sample_traces = [
            {
                "source": "zep",
                "success": True,
                "latency_ms": 450.5,
                "results_count": 10
            },
            {
                "source": "opensearch",
                "success": True,
                "latency_ms": 320.2,
                "results_count": 8
            },
            {
                "source": "bigquery",
                "success": True,
                "latency_ms": 500.0,
                "results_count": 5
            }
        ]

    def test_generate_trace_id(self):
        """Test trace ID generation (lines 62-64)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        trace_id = tool._generate_trace_id()

        self.assertTrue(trace_id.startswith("trace_"))
        self.assertEqual(len(trace_id), 22)  # trace_ + 16 hex chars

    def test_parse_source_traces_valid(self):
        """Test parsing valid source traces JSON (lines 66-72)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        parsed = tool._parse_source_traces(json.dumps(self.sample_traces))

        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["source"], "zep")

    def test_parse_source_traces_invalid(self):
        """Test parsing invalid source traces JSON (lines 66-72)."""
        tool = self.ToolClass(
            query="test",
            source_traces="invalid json"
        )

        with self.assertRaises(ValueError) as context:
            tool._parse_source_traces("invalid json")

        self.assertIn("Invalid JSON", str(context.exception))

    def test_parse_fusion_metadata_valid(self):
        """Test parsing valid fusion metadata (lines 74-81)."""
        fusion_data = {"algorithm": "rrf", "total_results": 10}
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        parsed = tool._parse_fusion_metadata(json.dumps(fusion_data))

        self.assertEqual(parsed["algorithm"], "rrf")
        self.assertEqual(parsed["total_results"], 10)

    def test_parse_fusion_metadata_none(self):
        """Test parsing None fusion metadata (lines 74-81)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        parsed = tool._parse_fusion_metadata(None)

        self.assertIsNone(parsed)

    def test_calculate_latency_percentiles(self):
        """Test latency percentile calculation (lines 83-100)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        percentiles = tool._calculate_latency_percentiles(latencies)

        self.assertIn("p50", percentiles)
        self.assertIn("p95", percentiles)
        self.assertIn("p99", percentiles)
        self.assertIn("max", percentiles)
        self.assertEqual(percentiles["max"], 1000)

    def test_calculate_latency_percentiles_empty(self):
        """Test latency percentile calculation with empty list (lines 83-100)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        percentiles = tool._calculate_latency_percentiles([])

        self.assertEqual(percentiles["p50"], 0.0)
        self.assertEqual(percentiles["p95"], 0.0)
        self.assertEqual(percentiles["p99"], 0.0)
        self.assertEqual(percentiles["max"], 0.0)

    def test_analyze_source_performance_all_success(self):
        """Test source performance analysis with all successful calls (lines 102-146)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        performance = tool._analyze_source_performance(self.sample_traces)

        # Check all sources present
        self.assertIn("zep", performance)
        self.assertIn("opensearch", performance)
        self.assertIn("bigquery", performance)

        # Check success rates
        for source, metrics in performance.items():
            self.assertEqual(metrics["success_rate"], 100.0)
            self.assertEqual(metrics["error_rate"], 0.0)

    def test_analyze_source_performance_with_errors(self):
        """Test source performance analysis with errors (lines 102-146)."""
        error_traces = [
            {"source": "zep", "success": False, "error": "Connection timeout"},
            {"source": "zep", "success": True, "latency_ms": 200},
            {"source": "opensearch", "success": True, "latency_ms": 300}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(error_traces)
        )

        performance = tool._analyze_source_performance(error_traces)

        # Zep should have 50% error rate (1 fail, 1 success)
        self.assertEqual(performance["zep"]["failed_calls"], 1)
        self.assertEqual(performance["zep"]["successful_calls"], 1)
        self.assertEqual(performance["zep"]["error_rate"], 50.0)

    def test_calculate_coverage_stats_full_coverage(self):
        """Test coverage calculation with full coverage (lines 148-168)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        coverage = tool._calculate_coverage_stats(self.sample_traces)

        self.assertEqual(coverage["coverage_percentage"], 100.0)
        self.assertEqual(coverage["sources_successful"], 3)
        self.assertEqual(len(coverage["successful_sources"]), 3)

    def test_calculate_coverage_stats_partial_failure(self):
        """Test coverage calculation with partial failures (lines 148-168)."""
        partial_traces = [
            {"source": "zep", "success": True, "latency_ms": 200},
            {"source": "opensearch", "success": False, "error": "Timeout"},
            {"source": "bigquery", "success": True, "latency_ms": 500}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(partial_traces)
        )

        coverage = tool._calculate_coverage_stats(partial_traces)

        self.assertEqual(coverage["sources_successful"], 2)
        self.assertIn("opensearch", coverage["failed_sources"])
        self.assertAlmostEqual(coverage["coverage_percentage"], 66.67, places=1)

    def test_calculate_coverage_stats_unavailable_sources(self):
        """Test coverage calculation with unavailable sources (lines 148-168)."""
        partial_traces = [
            {"source": "zep", "success": True, "latency_ms": 200}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(partial_traces)
        )

        coverage = tool._calculate_coverage_stats(partial_traces)

        self.assertEqual(len(coverage["unavailable_sources"]), 2)
        self.assertEqual(coverage["sources_attempted"], 1)

    def test_analyze_fusion_performance_with_metadata(self):
        """Test fusion performance analysis with metadata (lines 170-186)."""
        fusion_metadata = {
            "algorithm": "rrf",
            "weights": {"semantic": 0.6, "keyword": 0.4},
            "total_results": 20,
            "fused_results": 15,
            "deduplication_count": 5,
            "avg_rrf_score": 0.85
        }

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        fusion_perf = tool._analyze_fusion_performance(fusion_metadata)

        self.assertTrue(fusion_perf["fusion_enabled"])
        self.assertEqual(fusion_perf["algorithm"], "rrf")
        self.assertEqual(fusion_perf["deduplication_count"], 5)

    def test_analyze_fusion_performance_without_metadata(self):
        """Test fusion performance analysis without metadata (lines 170-186)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        fusion_perf = tool._analyze_fusion_performance(None)

        self.assertFalse(fusion_perf["fusion_enabled"])
        self.assertIn("message", fusion_perf)

    def test_identify_slow_paths_with_slow_sources(self):
        """Test slow path identification with slow sources (lines 188-207)."""
        slow_traces = [
            {"source": "zep", "success": True, "latency_ms": 2500},
            {"source": "opensearch", "success": True, "latency_ms": 3000}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(slow_traces)
        )

        performance = tool._analyze_source_performance(slow_traces)
        slow_paths = tool._identify_slow_paths(performance, threshold_ms=1000.0)

        self.assertEqual(len(slow_paths), 2)
        self.assertEqual(slow_paths[0]["source"], "zep")
        self.assertIn("severity", slow_paths[0])

    def test_identify_slow_paths_no_slow_sources(self):
        """Test slow path identification with no slow sources (lines 188-207)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        performance = tool._analyze_source_performance(self.sample_traces)
        slow_paths = tool._identify_slow_paths(performance, threshold_ms=1000.0)

        self.assertEqual(len(slow_paths), 0)

    def test_check_alert_thresholds_high_error_rate(self):
        """Test alert threshold checking for high error rates (lines 209-268)."""
        error_traces = [
            {"source": "zep", "success": False, "error": "Error 1"},
            {"source": "zep", "success": False, "error": "Error 2"},
            {"source": "zep", "success": False, "error": "Error 3"},
            {"source": "zep", "success": True, "latency_ms": 100}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(error_traces)
        )

        performance = tool._analyze_source_performance(error_traces)
        coverage = tool._calculate_coverage_stats(error_traces)
        alerts = tool._check_alert_thresholds(performance, coverage)

        # Should trigger high error rate alert (75% > 50%)
        error_alerts = [a for a in alerts if a["type"] == "high_error_rate"]
        self.assertGreater(len(error_alerts), 0)

    def test_check_alert_thresholds_high_latency(self):
        """Test alert threshold checking for high latency (lines 209-268)."""
        slow_traces = [
            {"source": "zep", "success": True, "latency_ms": 2500},
            {"source": "zep", "success": True, "latency_ms": 3000}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(slow_traces)
        )

        performance = tool._analyze_source_performance(slow_traces)
        coverage = tool._calculate_coverage_stats(slow_traces)
        alerts = tool._check_alert_thresholds(performance, coverage)

        # Should trigger high latency alert
        latency_alerts = [a for a in alerts if a["type"] == "high_latency"]
        self.assertGreater(len(latency_alerts), 0)

    def test_check_alert_thresholds_low_coverage(self):
        """Test alert threshold checking for low coverage (lines 209-268)."""
        low_coverage_traces = [
            {"source": "zep", "success": False, "error": "Failed"},
            {"source": "opensearch", "success": False, "error": "Failed"}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(low_coverage_traces)
        )

        performance = tool._analyze_source_performance(low_coverage_traces)
        coverage = tool._calculate_coverage_stats(low_coverage_traces)
        alerts = tool._check_alert_thresholds(performance, coverage)

        # Should trigger low coverage alert (0% < 33%)
        coverage_alerts = [a for a in alerts if a["type"] == "low_coverage"]
        self.assertGreater(len(coverage_alerts), 0)

    def test_generate_daily_digest_data(self):
        """Test daily digest data generation (lines 270-292)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        performance = tool._analyze_source_performance(self.sample_traces)
        coverage = tool._calculate_coverage_stats(self.sample_traces)
        slow_paths = tool._identify_slow_paths(performance, threshold_ms=1000.0)

        digest = tool._generate_daily_digest_data(performance, coverage, slow_paths)

        self.assertIn("summary", digest)
        self.assertIn("per_source_latency", digest)
        self.assertIn("slow_paths_count", digest)
        self.assertEqual(digest["summary"]["coverage_percentage"], 100.0)

    def test_run_success_with_all_sources(self):
        """Test successful run with all sources (lines 298-351)."""
        tool = self.ToolClass(
            query="How to increase revenue",
            source_traces=json.dumps(self.sample_traces)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertIn("trace_id", data)
        self.assertIn("performance", data)
        self.assertIn("alerts", data)
        self.assertIn("daily_digest_data", data)

    def test_run_with_trace_id_provided(self):
        """Test run with provided trace ID (lines 298-351)."""
        custom_trace_id = "trace_custom123"

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces),
            trace_id=custom_trace_id
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["trace_id"], custom_trace_id)

    def test_run_with_fusion_metadata(self):
        """Test run with fusion metadata (lines 298-351)."""
        fusion_metadata = {
            "algorithm": "rrf",
            "total_results": 20,
            "fused_results": 15
        }

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces),
            fusion_metadata=json.dumps(fusion_metadata)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertTrue(
            data["performance"]["fusion_performance"]["fusion_enabled"]
        )

    def test_run_with_user_id(self):
        """Test run with user ID (lines 298-351)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces),
            user_id="test_user_123"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["user_id"], "test_user_123")

    def test_run_calculates_total_latency(self):
        """Test total latency calculation (lines 337-341)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        result = tool.run()
        data = json.loads(result)

        expected_total = 450.5 + 320.2 + 500.0
        self.assertAlmostEqual(
            data["performance"]["total_latency_ms"],
            expected_total,
            places=1
        )

    def test_run_includes_raw_traces(self):
        """Test that raw traces are included in response (lines 343-346)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("raw_traces", data)
        self.assertEqual(len(data["raw_traces"]), 3)

    def test_exception_handling(self):
        """Test exception handling (lines 353-358)."""
        tool = self.ToolClass(
            query="test",
            source_traces="not valid json at all"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "tracing_failed")
        self.assertIn("message", data)

    def test_timestamp_generation(self):
        """Test timestamp generation (lines 294-296)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        timestamp = tool._get_timestamp()

        # Should be ISO 8601 format with timezone
        self.assertIn("T", timestamp)
        self.assertTrue(timestamp.endswith("Z") or "+" in timestamp)

    def test_performance_metrics_structure(self):
        """Test performance metrics structure in response (lines 343-350)."""
        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(self.sample_traces)
        )

        result = tool.run()
        data = json.loads(result)

        performance = data["performance"]
        self.assertIn("total_latency_ms", performance)
        self.assertIn("source_performance", performance)
        self.assertIn("coverage_stats", performance)
        self.assertIn("fusion_performance", performance)

    def test_alert_severity_levels(self):
        """Test alert severity levels (lines 209-268)."""
        critical_traces = [
            {"source": "zep", "success": False, "error": "Error"},
            {"source": "zep", "success": False, "error": "Error"}
        ]

        tool = self.ToolClass(
            query="test",
            source_traces=json.dumps(critical_traces)
        )

        performance = tool._analyze_source_performance(critical_traces)
        coverage = tool._calculate_coverage_stats(critical_traces)
        alerts = tool._check_alert_thresholds(performance, coverage)

        # Check that severity levels are assigned
        for alert in alerts:
            self.assertIn("severity", alert)
            self.assertIn(alert["severity"], ["critical", "warning", "info"])


if __name__ == '__main__':
    unittest.main()
