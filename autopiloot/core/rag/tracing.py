"""
Tracing and Observability Module

Provides comprehensive instrumentation for Hybrid RAG pipeline monitoring.
Tracks per-source latency, error rates, coverage, and fusion performance.
"""

import os
import sys
import uuid
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

# Add config directory to path

# In-memory metrics store (could be replaced with Firestore/Redis in production)
_metrics_store = {
    "retrieval_events": [],
    "latency_samples": defaultdict(list),
    "error_counts": defaultdict(int),
    "source_availability": defaultdict(list)
}


def create_trace_id() -> str:
    """
    Generate unique trace ID for a retrieval request.

    Returns:
        UUID string in format: "rag_<timestamp>_<uuid>"

    Example:
        >>> trace_id = create_trace_id()
        >>> trace_id.startswith("rag_")
        True
    """
    timestamp = int(time.time() * 1000)
    unique_id = str(uuid.uuid4())[:8]
    return f"rag_{timestamp}_{unique_id}"


def emit_retrieval_event(
    trace_id: str,
    query: str,
    filters: Optional[dict],
    total_results: int,
    sources_used: List[str],
    latency_ms: int,
    source_latencies: Dict[str, int],
    coverage: float
) -> None:
    """
    Emit retrieval event for observability tracking.

    Args:
        trace_id: Unique trace identifier
        query: Search query string
        filters: Query filters applied
        total_results: Number of results returned
        sources_used: List of sources that contributed results
        latency_ms: Total retrieval latency in milliseconds
        source_latencies: Per-source latency breakdown
        coverage: Percentage of sources that returned results

    Side Effects:
        - Stores event in metrics store
        - Checks thresholds and may trigger alerts
        - Updates latency and coverage metrics

    Example:
        >>> emit_retrieval_event(
        ...     trace_id="rag_123_abc",
        ...     query="revenue growth",
        ...     filters={"channel_id": "UC123"},
        ...     total_results=15,
        ...     sources_used=["zep", "opensearch"],
        ...     latency_ms=1234,
        ...     source_latencies={"zep": 567, "opensearch": 432},
        ...     coverage=66.7
        ... )
    """
    try:
        from rag.config import get_observability_config

        obs_config = get_observability_config()

        if not obs_config.get("enabled", True):
            return

        # Store retrieval event
        event = {
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "query": query,
            "filters": filters,
            "total_results": total_results,
            "sources_used": sources_used,
            "latency_ms": latency_ms,
            "source_latencies": source_latencies,
            "coverage": coverage
        }

        _metrics_store["retrieval_events"].append(event)

        # Update latency samples
        _metrics_store["latency_samples"]["total"].append(latency_ms)
        for source, lat in source_latencies.items():
            _metrics_store["latency_samples"][source].append(lat)

        # Update source availability
        for source in sources_used:
            _metrics_store["source_availability"][source].append(True)

        # Check thresholds and alert if needed
        _check_thresholds(latency_ms, source_latencies, coverage, obs_config)

        # Log if configured
        if obs_config.get("logging", {}).get("enabled", True):
            log_level = obs_config.get("logging", {}).get("log_level", "info")
            if log_level in ["debug", "info"]:
                print(f"[RAG Trace {trace_id}] query='{query[:50]}...' results={total_results} "
                      f"latency={latency_ms}ms coverage={coverage:.1f}% sources={sources_used}")

    except Exception as e:
        # Don't fail retrieval if observability fails
        print(f"Warning: Failed to emit retrieval event: {str(e)}")


def emit_ingest_event(
    operation: str,
    video_id: str,
    chunk_count: int,
    sinks_used: List[str],
    success_count: int,
    error_count: int,
    latency_ms: int
) -> None:
    """
    Emit ingest event for observability tracking.

    Args:
        operation: Ingest operation type ("transcript", "document", "strategy")
        video_id: Video or document identifier
        chunk_count: Number of chunks processed
        sinks_used: List of sinks used for storage
        success_count: Number of successful chunk ingests
        error_count: Number of failed chunk ingests
        latency_ms: Total ingest latency in milliseconds

    Example:
        >>> emit_ingest_event(
        ...     operation="transcript",
        ...     video_id="abc123",
        ...     chunk_count=10,
        ...     sinks_used=["zep", "opensearch", "bigquery"],
        ...     success_count=10,
        ...     error_count=0,
        ...     latency_ms=2345
        ... )
    """
    try:
        from rag.config import get_observability_config

        obs_config = get_observability_config()

        if not obs_config.get("enabled", True):
            return

        event = {
            "type": "ingest",
            "operation": operation,
            "video_id": video_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "chunk_count": chunk_count,
            "sinks_used": sinks_used,
            "success_count": success_count,
            "error_count": error_count,
            "latency_ms": latency_ms
        }

        _metrics_store["retrieval_events"].append(event)

        # Track error rate
        if error_count > 0:
            _metrics_store["error_counts"][operation] += error_count

        # Log ingest event
        if obs_config.get("logging", {}).get("enabled", True):
            status = "✅" if error_count == 0 else "⚠️"
            print(f"{status} [RAG Ingest] op={operation} video={video_id} chunks={chunk_count} "
                  f"sinks={sinks_used} success={success_count} errors={error_count} latency={latency_ms}ms")

    except Exception as e:
        print(f"Warning: Failed to emit ingest event: {str(e)}")


def _check_thresholds(
    latency_ms: int,
    source_latencies: Dict[str, int],
    coverage: float,
    obs_config: dict
) -> None:
    """Check if metrics exceed configured thresholds and alert if needed."""
    latency_config = obs_config.get("latency", {})
    coverage_config = obs_config.get("coverage", {})

    alerts = []

    # Check total latency
    slow_threshold = latency_config.get("slow_path_threshold_ms", 1000)
    critical_threshold = latency_config.get("alert_max_threshold_ms", 5000)

    if latency_ms > critical_threshold:
        alerts.append({
            "severity": "critical",
            "type": "latency",
            "message": f"Critical latency: {latency_ms}ms (threshold: {critical_threshold}ms)"
        })
    elif latency_ms > slow_threshold:
        alerts.append({
            "severity": "warning",
            "type": "latency",
            "message": f"Slow retrieval: {latency_ms}ms (threshold: {slow_threshold}ms)"
        })

    # Check per-source latency
    for source, lat in source_latencies.items():
        if lat > critical_threshold:
            alerts.append({
                "severity": "warning",
                "type": "source_latency",
                "message": f"Slow {source}: {lat}ms"
            })

    # Check coverage
    warning_coverage = coverage_config.get("warning_threshold", 67)
    critical_coverage = coverage_config.get("critical_threshold", 33)

    if coverage < critical_coverage:
        alerts.append({
            "severity": "critical",
            "type": "coverage",
            "message": f"Critical coverage: {coverage:.1f}% (threshold: {critical_coverage}%)"
        })
    elif coverage < warning_coverage:
        alerts.append({
            "severity": "warning",
            "type": "coverage",
            "message": f"Low coverage: {coverage:.1f}% (threshold: {warning_coverage}%)"
        })

    # Send alerts if configured
    if alerts and obs_config.get("alerts", {}).get("enabled", True):
        _send_alerts(alerts, obs_config)


def _send_alerts(alerts: List[dict], obs_config: dict) -> None:
    """Send alerts via configured channels (Slack, etc.)."""
    # This would integrate with observability_agent tools
    # For now, just log alerts
    for alert in alerts:
        severity_emoji = "🔴" if alert["severity"] == "critical" else "⚠️"
        print(f"{severity_emoji} RAG Alert [{alert['severity'].upper()}] {alert['type']}: {alert['message']}")


def get_metrics_summary(time_window_minutes: int = 60) -> dict:
    """
    Get summary of RAG metrics for the specified time window.

    Args:
        time_window_minutes: Time window in minutes (default: 60)

    Returns:
        Dictionary containing:
        - total_retrievals: Total number of retrieval requests
        - avg_latency_ms: Average total latency
        - p95_latency_ms: 95th percentile latency
        - avg_coverage: Average source coverage
        - per_source_latency: Average latency per source
        - error_rate: Overall error rate percentage
        - total_ingests: Total number of ingest operations

    Example:
        >>> summary = get_metrics_summary(time_window_minutes=60)
        >>> summary["total_retrievals"]
        125
        >>> summary["avg_latency_ms"]
        1234
    """
    try:
        # Filter events within time window
        cutoff_time = datetime.utcnow().timestamp() - (time_window_minutes * 60)

        retrieval_events = [
            e for e in _metrics_store["retrieval_events"]
            if e.get("timestamp") and _parse_timestamp(e["timestamp"]) > cutoff_time
        ]

        # Calculate latency metrics
        latencies = _metrics_store["latency_samples"]["total"]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            p95_latency = _calculate_percentile(latencies, 95)
        else:
            avg_latency = 0
            p95_latency = 0

        # Calculate per-source latency
        per_source_latency = {}
        for source, lats in _metrics_store["latency_samples"].items():
            if source != "total" and lats:
                per_source_latency[source] = sum(lats) / len(lats)

        # Calculate coverage
        coverage_values = [e.get("coverage", 0) for e in retrieval_events if "coverage" in e]
        avg_coverage = sum(coverage_values) / len(coverage_values) if coverage_values else 0

        # Count ingests
        ingest_events = [e for e in _metrics_store["retrieval_events"] if e.get("type") == "ingest"]

        return {
            "total_retrievals": len(retrieval_events),
            "avg_latency_ms": int(avg_latency),
            "p95_latency_ms": int(p95_latency),
            "avg_coverage": round(avg_coverage, 1),
            "per_source_latency": {k: int(v) for k, v in per_source_latency.items()},
            "total_ingests": len(ingest_events),
            "time_window_minutes": time_window_minutes
        }

    except Exception as e:
        return {
            "error": f"Failed to generate metrics summary: {str(e)}",
            "time_window_minutes": time_window_minutes
        }


def _parse_timestamp(iso_timestamp: str) -> float:
    """Parse ISO 8601 timestamp to Unix timestamp."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.timestamp()
    except:
        return 0


def _calculate_percentile(values: List[float], percentile: int) -> float:
    """Calculate percentile of values list."""
    if not values:
        return 0
    sorted_values = sorted(values)
    index = int(len(sorted_values) * (percentile / 100.0))
    return sorted_values[min(index, len(sorted_values) - 1)]


def reset_metrics() -> None:
    """Reset all metrics (useful for testing)."""
    global _metrics_store
    _metrics_store = {
        "retrieval_events": [],
        "latency_samples": defaultdict(list),
        "error_counts": defaultdict(int),
        "source_availability": defaultdict(list)
    }


if __name__ == "__main__":
    print("="*80)
    print("TEST: Tracing and Observability Module")
    print("="*80)

    # Test 1: Create trace IDs
    print("\n1. Testing create_trace_id():")
    trace1 = create_trace_id()
    trace2 = create_trace_id()
    print(f"   Trace 1: {trace1}")
    print(f"   Trace 2: {trace2}")
    print(f"   Unique: {trace1 != trace2}")

    # Test 2: Emit retrieval event
    print("\n2. Testing emit_retrieval_event():")
    emit_retrieval_event(
        trace_id=trace1,
        query="How to increase revenue",
        filters={"channel_id": "UC123"},
        total_results=15,
        sources_used=["zep", "opensearch"],
        latency_ms=1234,
        source_latencies={"zep": 567, "opensearch": 432},
        coverage=66.7
    )
    print("   ✅ Retrieval event emitted")

    # Test 3: Emit ingest event
    print("\n3. Testing emit_ingest_event():")
    emit_ingest_event(
        operation="transcript",
        video_id="abc123",
        chunk_count=10,
        sinks_used=["zep", "opensearch", "bigquery"],
        success_count=10,
        error_count=0,
        latency_ms=2345
    )
    print("   ✅ Ingest event emitted")

    # Test 4: Emit event with threshold violations
    print("\n4. Testing threshold alerts:")
    emit_retrieval_event(
        trace_id=trace2,
        query="Test query",
        filters=None,
        total_results=5,
        sources_used=["zep"],
        latency_ms=6000,  # Exceeds critical threshold
        source_latencies={"zep": 6000},
        coverage=33.3  # Below warning threshold
    )
    print("   ✅ Threshold check completed (see alerts above)")

    # Test 5: Get metrics summary
    print("\n5. Testing get_metrics_summary():")
    summary = get_metrics_summary(time_window_minutes=60)
    print(f"   Total retrievals: {summary['total_retrievals']}")
    print(f"   Avg latency: {summary['avg_latency_ms']}ms")
    print(f"   P95 latency: {summary['p95_latency_ms']}ms")
    print(f"   Avg coverage: {summary['avg_coverage']}%")
    print(f"   Per-source latency: {summary['per_source_latency']}")
    print(f"   Total ingests: {summary['total_ingests']}")

    # Test 6: Reset metrics
    print("\n6. Testing reset_metrics():")
    reset_metrics()
    summary_after = get_metrics_summary()
    print(f"   Total retrievals after reset: {summary_after['total_retrievals']}")
    print("   ✅ Metrics reset successfully")

    print("\n" + "="*80)
    print("✅ All tests completed")
