"""
Trace Hybrid Retrieval Observability Tool

Instruments hybrid RAG pipeline with comprehensive tracing, latency tracking,
error monitoring, and coverage analysis. Provides metrics for observability
and alerting.

Agency Swarm Tool for Hybrid RAG pipeline observability.
"""

from agency_swarm.tools import BaseTool
from pydantic import Field
from typing import List, Optional, Dict, Any
import json
import uuid
from datetime import datetime, timezone
from collections import defaultdict


class TraceHybridRetrieval(BaseTool):
    """
    Trace and monitor hybrid retrieval pipeline with comprehensive observability.

    Instruments retrieval pipeline to track per-source latency, error rates,
    coverage statistics, and fusion weights. Generates trace IDs for request
    correlation and provides metrics for alerting and daily digests.

    Use Case: Operational monitoring and performance analysis of hybrid RAG
    pipeline across Zep, OpenSearch, and BigQuery sources.
    """

    trace_id: Optional[str] = Field(
        default=None,
        description="Optional trace ID for request correlation (auto-generated if not provided)"
    )

    query: str = Field(
        ...,
        description="Search query being traced"
    )

    source_traces: str = Field(
        ...,
        description="JSON string containing per-source execution traces with latency and errors"
    )

    fusion_metadata: Optional[str] = Field(
        default=None,
        description="Optional JSON string with fusion weights and RRF scores"
    )

    user_id: Optional[str] = Field(
        default=None,
        description="Optional user ID for usage tracking"
    )

    def _generate_trace_id(self) -> str:
        """Generate unique trace ID for request correlation."""
        return f"trace_{uuid.uuid4().hex[:16]}"

    def _parse_source_traces(self, traces_str: str) -> List[Dict[str, Any]]:
        """Parse source traces JSON string."""
        try:
            return json.loads(traces_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in source_traces: {str(e)}")

    def _parse_fusion_metadata(self, metadata_str: Optional[str]) -> Optional[Dict[str, Any]]:
        """Parse fusion metadata JSON string."""
        if not metadata_str:
            return None
        try:
            return json.loads(metadata_str)
        except json.JSONDecodeError:
            return None

    def _calculate_latency_percentiles(self, latencies: List[float]) -> Dict[str, float]:
        """
        Calculate latency percentiles (p50, p95, p99).

        Returns: Dict with percentile values.
        """
        if not latencies:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            index = int((p / 100.0) * n)
            if index >= n:
                index = n - 1
            return sorted_latencies[index]

        return {
            "p50": percentile(50),
            "p95": percentile(95),
            "p99": percentile(99),
            "max": max(sorted_latencies)
        }

    def _analyze_source_performance(
        self,
        source_traces: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze per-source performance metrics.

        Returns: Dict with latency, error rates, and coverage per source.
        """
        source_metrics = defaultdict(lambda: {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "latencies": [],
            "errors": []
        })

        # Aggregate metrics per source
        for trace in source_traces:
            source = trace.get("source", "unknown")
            latency = trace.get("latency_ms", 0)
            error = trace.get("error")
            success = trace.get("success", True)

            metrics = source_metrics[source]
            metrics["total_calls"] += 1

            if success:
                metrics["successful_calls"] += 1
                metrics["latencies"].append(latency)
            else:
                metrics["failed_calls"] += 1
                if error:
                    metrics["errors"].append(error)

        # Calculate derived metrics
        performance = {}
        for source, metrics in source_metrics.items():
            total = metrics["total_calls"]
            success_rate = (metrics["successful_calls"] / total * 100) if total > 0 else 0
            error_rate = (metrics["failed_calls"] / total * 100) if total > 0 else 0

            latency_percentiles = self._calculate_latency_percentiles(metrics["latencies"])

            performance[source] = {
                "total_calls": total,
                "successful_calls": metrics["successful_calls"],
                "failed_calls": metrics["failed_calls"],
                "success_rate": round(success_rate, 2),
                "error_rate": round(error_rate, 2),
                "latency_percentiles": latency_percentiles,
                "avg_latency_ms": round(
                    sum(metrics["latencies"]) / len(metrics["latencies"]), 2
                ) if metrics["latencies"] else 0.0,
                "errors": metrics["errors"]
            }

        return performance

    def _calculate_coverage_stats(
        self,
        source_traces: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate source coverage statistics.

        Returns: Dict with coverage percentages and source availability.
        """
        total_sources = {"zep", "opensearch", "bigquery"}
        attempted_sources = set()
        successful_sources = set()

        for trace in source_traces:
            source = trace.get("source", "unknown")
            attempted_sources.add(source)

            if trace.get("success", False):
                successful_sources.add(source)

        coverage_percentage = (len(successful_sources) / len(total_sources) * 100)

        return {
            "total_sources_available": len(total_sources),
            "sources_attempted": len(attempted_sources),
            "sources_successful": len(successful_sources),
            "coverage_percentage": round(coverage_percentage, 2),
            "successful_sources": list(successful_sources),
            "failed_sources": list(attempted_sources - successful_sources),
            "unavailable_sources": list(total_sources - attempted_sources)
        }

    def _analyze_fusion_performance(
        self,
        fusion_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze fusion algorithm performance.

        Returns: Dict with fusion metrics and weight distribution.
        """
        if not fusion_metadata:
            return {
                "fusion_enabled": False,
                "message": "No fusion metadata provided"
            }

        return {
            "fusion_enabled": True,
            "algorithm": fusion_metadata.get("algorithm", "rrf"),
            "weights": fusion_metadata.get("weights", {}),
            "total_results": fusion_metadata.get("total_results", 0),
            "fused_results": fusion_metadata.get("fused_results", 0),
            "deduplication_count": fusion_metadata.get("deduplication_count", 0),
            "avg_rrf_score": fusion_metadata.get("avg_rrf_score", 0.0)
        }

    def _identify_slow_paths(
        self,
        source_performance: Dict[str, Any],
        threshold_ms: float = 1000.0
    ) -> List[Dict[str, Any]]:
        """
        Identify slow execution paths exceeding threshold.

        Returns: List of slow sources with details.
        """
        slow_paths = []

        for source, metrics in source_performance.items():
            p95_latency = metrics["latency_percentiles"].get("p95", 0.0)
            max_latency = metrics["latency_percentiles"].get("max", 0.0)

            if p95_latency > threshold_ms or max_latency > threshold_ms:
                slow_paths.append({
                    "source": source,
                    "p95_latency_ms": p95_latency,
                    "max_latency_ms": max_latency,
                    "threshold_ms": threshold_ms,
                    "severity": "high" if max_latency > threshold_ms * 2 else "medium"
                })

        return slow_paths

    def _check_alert_thresholds(
        self,
        source_performance: Dict[str, Any],
        coverage_stats: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check if metrics exceed alert thresholds.

        Returns: List of alerts that should be triggered.
        """
        alerts = []

        # Check error rate thresholds
        for source, metrics in source_performance.items():
            error_rate = metrics["error_rate"]

            if error_rate > 50:
                alerts.append({
                    "type": "high_error_rate",
                    "source": source,
                    "error_rate": error_rate,
                    "threshold": 50,
                    "severity": "critical",
                    "message": f"{source} error rate ({error_rate}%) exceeds 50% threshold"
                })
            elif error_rate > 25:
                alerts.append({
                    "type": "elevated_error_rate",
                    "source": source,
                    "error_rate": error_rate,
                    "threshold": 25,
                    "severity": "warning",
                    "message": f"{source} error rate ({error_rate}%) exceeds 25% threshold"
                })

        # Check latency thresholds
        for source, metrics in source_performance.items():
            p95_latency = metrics["latency_percentiles"].get("p95", 0.0)

            if p95_latency > 2000:
                alerts.append({
                    "type": "high_latency",
                    "source": source,
                    "p95_latency_ms": p95_latency,
                    "threshold_ms": 2000,
                    "severity": "warning",
                    "message": f"{source} p95 latency ({p95_latency}ms) exceeds 2000ms threshold"
                })

        # Check coverage thresholds
        coverage = coverage_stats["coverage_percentage"]
        if coverage < 33:
            alerts.append({
                "type": "low_coverage",
                "coverage_percentage": coverage,
                "threshold": 33,
                "severity": "critical",
                "message": f"Source coverage ({coverage}%) below 33% threshold (less than 1 source working)"
            })
        elif coverage < 67:
            alerts.append({
                "type": "degraded_coverage",
                "coverage_percentage": coverage,
                "threshold": 67,
                "severity": "warning",
                "message": f"Source coverage ({coverage}%) below 67% threshold (less than 2 sources working)"
            })

        return alerts

    def _generate_daily_digest_data(
        self,
        source_performance: Dict[str, Any],
        coverage_stats: Dict[str, Any],
        slow_paths: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate data for daily digest report.

        Returns: Dict with summary statistics for daily digest.
        """
        total_calls = sum(m["total_calls"] for m in source_performance.values())
        total_errors = sum(m["failed_calls"] for m in source_performance.values())

        avg_latencies = {
            source: metrics["avg_latency_ms"]
            for source, metrics in source_performance.items()
        }

        return {
            "summary": {
                "total_calls": total_calls,
                "total_errors": total_errors,
                "overall_error_rate": round(
                    (total_errors / total_calls * 100) if total_calls > 0 else 0, 2
                ),
                "coverage_percentage": coverage_stats["coverage_percentage"]
            },
            "per_source_latency": avg_latencies,
            "slow_paths_count": len(slow_paths),
            "slow_paths": slow_paths,
            "failed_sources": coverage_stats["failed_sources"],
            "unavailable_sources": coverage_stats["unavailable_sources"]
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def run(self) -> str:
        """
        Trace hybrid retrieval request and collect observability metrics.

        Returns: JSON string with comprehensive trace data and metrics.
        """
        try:
            # Generate or use provided trace ID
            trace_id = self.trace_id or self._generate_trace_id()

            # Parse inputs
            source_traces = self._parse_source_traces(self.source_traces)
            fusion_metadata = self._parse_fusion_metadata(self.fusion_metadata)

            # Analyze performance
            source_performance = self._analyze_source_performance(source_traces)
            coverage_stats = self._calculate_coverage_stats(source_traces)
            fusion_performance = self._analyze_fusion_performance(fusion_metadata)

            # Identify issues
            slow_paths = self._identify_slow_paths(source_performance, threshold_ms=1000.0)
            alerts = self._check_alert_thresholds(source_performance, coverage_stats)

            # Generate daily digest data
            daily_digest_data = self._generate_daily_digest_data(
                source_performance,
                coverage_stats,
                slow_paths
            )

            # Calculate total latency
            total_latency_ms = sum(
                trace.get("latency_ms", 0)
                for trace in source_traces
                if trace.get("success", False)
            )

            # Build response
            response = {
                "trace_id": trace_id,
                "query": self.query,
                "user_id": self.user_id,
                "timestamp": self._get_timestamp(),
                "performance": {
                    "total_latency_ms": total_latency_ms,
                    "source_performance": source_performance,
                    "coverage_stats": coverage_stats,
                    "fusion_performance": fusion_performance
                },
                "slow_paths": slow_paths,
                "alerts": alerts,
                "daily_digest_data": daily_digest_data,
                "raw_traces": source_traces,
                "status": "success"
            }

            return json.dumps(response, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "tracing_failed",
                "message": str(e),
                "timestamp": self._get_timestamp()
            })


if __name__ == "__main__":
    # Test block for standalone execution
    print("Testing TraceHybridRetrieval tool...")

    # Sample source traces with latencies and errors
    sample_traces = [
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
            "success": False,
            "latency_ms": 1500.0,
            "error": "Query timeout",
            "results_count": 0
        }
    ]

    # Sample fusion metadata
    fusion_metadata = {
        "algorithm": "rrf",
        "weights": {"semantic": 0.6, "keyword": 0.4},
        "total_results": 18,
        "fused_results": 15,
        "deduplication_count": 3,
        "avg_rrf_score": 0.85
    }

    # Test 1: Basic tracing
    print("\nTest 1: Basic tracing with all sources")
    tool = TraceHybridRetrieval(
        query="How to increase revenue",
        source_traces=json.dumps(sample_traces),
        fusion_metadata=json.dumps(fusion_metadata)
    )
    result = tool.run()
    data = json.loads(result)
    print(f"Trace ID: {data.get('trace_id')}")
    print(f"Total latency: {data['performance']['total_latency_ms']}ms")
    print(f"Coverage: {data['performance']['coverage_stats']['coverage_percentage']}%")
    print(f"Alerts: {len(data['alerts'])} triggered")

    # Test 2: High error rate scenario
    print("\nTest 2: High error rate scenario")
    error_traces = [
        {"source": "zep", "success": False, "latency_ms": 100, "error": "Connection timeout"},
        {"source": "zep", "success": False, "latency_ms": 100, "error": "Connection timeout"},
        {"source": "zep", "success": True, "latency_ms": 200},
        {"source": "opensearch", "success": True, "latency_ms": 300}
    ]
    tool = TraceHybridRetrieval(
        query="test query",
        source_traces=json.dumps(error_traces)
    )
    result = tool.run()
    data = json.loads(result)
    print(f"Alerts: {len(data['alerts'])}")
    for alert in data['alerts']:
        print(f"  - {alert['type']}: {alert['message']}")

    # Test 3: Slow path detection
    print("\nTest 3: Slow path detection")
    slow_traces = [
        {"source": "zep", "success": True, "latency_ms": 2500},
        {"source": "opensearch", "success": True, "latency_ms": 3000}
    ]
    tool = TraceHybridRetrieval(
        query="test query",
        source_traces=json.dumps(slow_traces)
    )
    result = tool.run()
    data = json.loads(result)
    print(f"Slow paths: {len(data['slow_paths'])}")
    for slow_path in data['slow_paths']:
        print(f"  - {slow_path['source']}: {slow_path['p95_latency_ms']}ms (severity: {slow_path['severity']})")

    # Test 4: Daily digest data
    print("\nTest 4: Daily digest data")
    tool = TraceHybridRetrieval(
        query="test query",
        source_traces=json.dumps(sample_traces),
        user_id="test_user"
    )
    result = tool.run()
    data = json.loads(result)
    digest = data['daily_digest_data']
    print(f"Total calls: {digest['summary']['total_calls']}")
    print(f"Total errors: {digest['summary']['total_errors']}")
    print(f"Coverage: {digest['summary']['coverage_percentage']}%")

    print("\n✅ All tests completed successfully")
