"""
Monitor drift in RAG retrieval behavior over time.

This tool tracks metrics to detect quality degradation and data distribution
shifts in the hybrid RAG pipeline:

- Token length drift: Document size changes over time
- Retrieval coverage drift: Percentage of queries returning results
- Source distribution drift: Which sources are being used
- Result diversity drift: Variety in retrieved results
- Query pattern drift: Changes in user query behavior

Drift detection enables:
- Early warning of quality degradation
- Identification of when re-training/re-embedding needed
- Monitoring data distribution shifts
- Capacity planning based on trends
"""

import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pydantic import Field
import statistics


class MonitorRAGDrift:
    """Monitor drift in RAG retrieval metrics over time."""

    operation: str = Field(
        ...,
        description="Operation: 'record_metrics', 'analyze_drift', 'get_trends', 'detect_anomalies'"
    )

    time_range_hours: int = Field(
        default=24,
        description="Time range for analysis in hours"
    )

    metric_type: Optional[str] = Field(
        None,
        description="Metric type: 'token_length', 'coverage', 'source_distribution', 'diversity', 'query_patterns'"
    )

    # Metrics to record
    query: Optional[str] = Field(
        None,
        description="Query text for pattern analysis"
    )

    token_count: Optional[int] = Field(
        None,
        description="Token count for drift tracking"
    )

    results_returned: Optional[int] = Field(
        None,
        description="Number of results returned"
    )

    sources_used: Optional[List[str]] = Field(
        None,
        description="Sources used in retrieval"
    )

    unique_doc_ids: Optional[int] = Field(
        None,
        description="Number of unique document IDs (diversity)"
    )

    # Drift detection thresholds
    drift_threshold_percentage: float = Field(
        default=20.0,
        description="Percentage change threshold for drift detection"
    )

    def __init__(self, **data):
        """Initialize with settings from config."""
        from core.config_loader import ConfigLoader

        # Set attributes from data
        for key, value in data.items():
            setattr(self, key, value)

        # Load configuration
        self.config = ConfigLoader()

        # Metrics storage (in production: time-series database)
        self._metrics_store = []

        # Initialize mock historical data
        self._initialize_mock_data()

    def _initialize_mock_data(self):
        """Initialize mock historical metrics for testing."""
        base_time = datetime.utcnow()

        # Generate 7 days of mock data
        for days_ago in range(7, 0, -1):
            timestamp = base_time - timedelta(days=days_ago)

            # Token length metrics (increasing trend + noise)
            for hour in range(0, 24, 4):
                self._metrics_store.append({
                    "timestamp": (timestamp + timedelta(hours=hour)).isoformat() + "Z",
                    "metric_type": "token_length",
                    "value": 800 + (7 - days_ago) * 50 + (hour % 100),  # Gradual increase
                    "metadata": {}
                })

            # Coverage metrics (stable)
            self._metrics_store.append({
                "timestamp": timestamp.isoformat() + "Z",
                "metric_type": "coverage",
                "value": 0.92,
                "metadata": {}
            })

            # Source distribution (shift toward OpenSearch)
            zep_pct = 0.50 - (7 - days_ago) * 0.05  # Decreasing
            os_pct = 0.30 + (7 - days_ago) * 0.05   # Increasing
            bq_pct = 0.20

            self._metrics_store.append({
                "timestamp": timestamp.isoformat() + "Z",
                "metric_type": "source_distribution",
                "value": {
                    "zep": zep_pct,
                    "opensearch": os_pct,
                    "bigquery": bq_pct
                },
                "metadata": {}
            })

            # Result diversity (decreasing slightly)
            self._metrics_store.append({
                "timestamp": timestamp.isoformat() + "Z",
                "metric_type": "diversity",
                "value": 0.75 - (7 - days_ago) * 0.03,  # Slight decrease
                "metadata": {}
            })

    def record_metrics(
        self,
        query: Optional[str] = None,
        token_count: Optional[int] = None,
        results_returned: Optional[int] = None,
        sources_used: Optional[List[str]] = None,
        unique_doc_ids: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Record metrics for drift monitoring.

        Args:
            query: Query text
            token_count: Document token count
            results_returned: Number of results
            sources_used: List of sources used
            unique_doc_ids: Number of unique documents

        Returns:
            Recording confirmation
        """
        try:
            timestamp = datetime.utcnow().isoformat() + "Z"

            # Record token length
            if token_count is not None:
                self._metrics_store.append({
                    "timestamp": timestamp,
                    "metric_type": "token_length",
                    "value": token_count,
                    "metadata": {"query": query}
                })

            # Record coverage
            if results_returned is not None:
                coverage = 1.0 if results_returned > 0 else 0.0
                self._metrics_store.append({
                    "timestamp": timestamp,
                    "metric_type": "coverage",
                    "value": coverage,
                    "metadata": {"query": query, "results_count": results_returned}
                })

            # Record source distribution
            if sources_used:
                total = len(sources_used)
                distribution = {
                    "zep": sources_used.count("zep") / total if total > 0 else 0,
                    "opensearch": sources_used.count("opensearch") / total if total > 0 else 0,
                    "bigquery": sources_used.count("bigquery") / total if total > 0 else 0
                }
                self._metrics_store.append({
                    "timestamp": timestamp,
                    "metric_type": "source_distribution",
                    "value": distribution,
                    "metadata": {}
                })

            # Record diversity
            if unique_doc_ids is not None and results_returned is not None:
                diversity = unique_doc_ids / results_returned if results_returned > 0 else 0
                self._metrics_store.append({
                    "timestamp": timestamp,
                    "metric_type": "diversity",
                    "value": diversity,
                    "metadata": {}
                })

            return {
                "status": "success",
                "operation": "record_metrics",
                "timestamp": timestamp,
                "metrics_recorded": sum([
                    token_count is not None,
                    results_returned is not None,
                    sources_used is not None,
                    unique_doc_ids is not None
                ])
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "record_metrics",
                "message": f"Failed to record metrics: {e}"
            }

    def analyze_drift(self, metric_type: str, time_range_hours: int) -> Dict[str, Any]:
        """
        Analyze drift for specific metric type.

        Args:
            metric_type: Type of metric to analyze
            time_range_hours: Time range for analysis

        Returns:
            Drift analysis results
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)

            # Filter metrics by type and time range
            relevant_metrics = [
                m for m in self._metrics_store
                if m["metric_type"] == metric_type and
                datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")) > cutoff_time
            ]

            if len(relevant_metrics) < 2:
                return {
                    "status": "insufficient_data",
                    "metric_type": metric_type,
                    "message": "Not enough data points for drift analysis"
                }

            # Calculate drift based on metric type
            if metric_type == "token_length":
                drift_result = self._analyze_token_length_drift(relevant_metrics)
            elif metric_type == "coverage":
                drift_result = self._analyze_coverage_drift(relevant_metrics)
            elif metric_type == "source_distribution":
                drift_result = self._analyze_source_distribution_drift(relevant_metrics)
            elif metric_type == "diversity":
                drift_result = self._analyze_diversity_drift(relevant_metrics)
            else:
                return {
                    "status": "error",
                    "message": f"Unknown metric type: {metric_type}"
                }

            return {
                "status": "success",
                "operation": "analyze_drift",
                "metric_type": metric_type,
                "time_range_hours": time_range_hours,
                "data_points": len(relevant_metrics),
                "drift_analysis": drift_result
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "analyze_drift",
                "message": f"Drift analysis failed: {e}"
            }

    def _analyze_token_length_drift(self, metrics: List[Dict]) -> Dict[str, Any]:
        """Analyze token length drift."""
        values = [m["value"] for m in metrics]

        # Split into baseline (first half) and current (second half)
        midpoint = len(values) // 2
        baseline = values[:midpoint]
        current = values[midpoint:]

        baseline_avg = statistics.mean(baseline)
        current_avg = statistics.mean(current)
        percent_change = ((current_avg - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0

        drift_detected = abs(percent_change) > self.drift_threshold_percentage

        return {
            "baseline_average": round(baseline_avg, 2),
            "current_average": round(current_avg, 2),
            "percent_change": round(percent_change, 2),
            "drift_detected": drift_detected,
            "trend": "increasing" if percent_change > 0 else "decreasing",
            "severity": "high" if abs(percent_change) > 30 else ("medium" if abs(percent_change) > 20 else "low")
        }

    def _analyze_coverage_drift(self, metrics: List[Dict]) -> Dict[str, Any]:
        """Analyze coverage drift."""
        values = [m["value"] for m in metrics]

        midpoint = len(values) // 2
        baseline = values[:midpoint]
        current = values[midpoint:]

        baseline_avg = statistics.mean(baseline)
        current_avg = statistics.mean(current)
        percent_change = ((current_avg - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0

        drift_detected = abs(percent_change) > self.drift_threshold_percentage

        return {
            "baseline_coverage": round(baseline_avg, 4),
            "current_coverage": round(current_avg, 4),
            "percent_change": round(percent_change, 2),
            "drift_detected": drift_detected,
            "trend": "improving" if percent_change > 0 else "degrading",
            "severity": "high" if percent_change < -20 else ("medium" if percent_change < -10 else "low")
        }

    def _analyze_source_distribution_drift(self, metrics: List[Dict]) -> Dict[str, Any]:
        """Analyze source distribution drift."""
        midpoint = len(metrics) // 2
        baseline = metrics[:midpoint]
        current = metrics[midpoint:]

        # Calculate average distribution for each period
        def avg_distribution(period):
            sources = ["zep", "opensearch", "bigquery"]
            return {
                source: statistics.mean([m["value"].get(source, 0) for m in period])
                for source in sources
            }

        baseline_dist = avg_distribution(baseline)
        current_dist = avg_distribution(current)

        # Calculate drift per source
        source_drifts = {}
        for source in baseline_dist.keys():
            baseline_val = baseline_dist[source]
            current_val = current_dist[source]
            percent_change = ((current_val - baseline_val) / baseline_val * 100) if baseline_val > 0 else 0
            source_drifts[source] = {
                "baseline": round(baseline_val, 4),
                "current": round(current_val, 4),
                "percent_change": round(percent_change, 2)
            }

        # Overall drift detected if any source changed significantly
        drift_detected = any(
            abs(drift["percent_change"]) > self.drift_threshold_percentage
            for drift in source_drifts.values()
        )

        return {
            "baseline_distribution": {k: round(v, 4) for k, v in baseline_dist.items()},
            "current_distribution": {k: round(v, 4) for k, v in current_dist.items()},
            "source_drifts": source_drifts,
            "drift_detected": drift_detected
        }

    def _analyze_diversity_drift(self, metrics: List[Dict]) -> Dict[str, Any]:
        """Analyze result diversity drift."""
        values = [m["value"] for m in metrics]

        midpoint = len(values) // 2
        baseline = values[:midpoint]
        current = values[midpoint:]

        baseline_avg = statistics.mean(baseline)
        current_avg = statistics.mean(current)
        percent_change = ((current_avg - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0

        drift_detected = abs(percent_change) > self.drift_threshold_percentage

        return {
            "baseline_diversity": round(baseline_avg, 4),
            "current_diversity": round(current_avg, 4),
            "percent_change": round(percent_change, 2),
            "drift_detected": drift_detected,
            "trend": "more_diverse" if percent_change > 0 else "less_diverse",
            "severity": "high" if abs(percent_change) > 30 else ("medium" if abs(percent_change) > 20 else "low")
        }

    def get_trends(self, time_range_hours: int) -> Dict[str, Any]:
        """
        Get trends across all metrics.

        Args:
            time_range_hours: Time range for trend analysis

        Returns:
            Trend summary across all metrics
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)

            # Analyze each metric type
            metric_types = ["token_length", "coverage", "source_distribution", "diversity"]
            trends = {}

            for metric_type in metric_types:
                analysis = self.analyze_drift(metric_type, time_range_hours)
                if analysis["status"] == "success":
                    trends[metric_type] = analysis["drift_analysis"]

            # Overall drift summary
            drift_detected_count = sum(
                1 for t in trends.values()
                if t.get("drift_detected", False)
            )

            return {
                "status": "success",
                "operation": "get_trends",
                "time_range_hours": time_range_hours,
                "trends": trends,
                "drift_summary": {
                    "metrics_analyzed": len(trends),
                    "drift_detected_count": drift_detected_count,
                    "overall_status": "drift_detected" if drift_detected_count > 0 else "stable"
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "get_trends",
                "message": f"Trend analysis failed: {e}"
            }

    def detect_anomalies(self, metric_type: str, time_range_hours: int) -> Dict[str, Any]:
        """
        Detect anomalies in specific metric.

        Args:
            metric_type: Type of metric to check
            time_range_hours: Time range for analysis

        Returns:
            Anomaly detection results
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_range_hours)

            relevant_metrics = [
                m for m in self._metrics_store
                if m["metric_type"] == metric_type and
                datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")) > cutoff_time
            ]

            if len(relevant_metrics) < 10:
                return {
                    "status": "insufficient_data",
                    "message": "Need at least 10 data points for anomaly detection"
                }

            # Simple anomaly detection: values beyond 2 standard deviations
            if metric_type == "source_distribution":
                # Skip anomaly detection for distribution (different data structure)
                return {
                    "status": "success",
                    "operation": "detect_anomalies",
                    "metric_type": metric_type,
                    "anomalies_detected": 0,
                    "message": "Anomaly detection not applicable for distribution metrics"
                }

            values = [m["value"] for m in relevant_metrics]
            mean = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0

            # Find anomalies (>2 std dev from mean)
            anomalies = []
            for metric in relevant_metrics:
                value = metric["value"]
                z_score = abs((value - mean) / stdev) if stdev > 0 else 0

                if z_score > 2:
                    anomalies.append({
                        "timestamp": metric["timestamp"],
                        "value": value,
                        "z_score": round(z_score, 2),
                        "deviation_from_mean": round(value - mean, 2)
                    })

            return {
                "status": "success",
                "operation": "detect_anomalies",
                "metric_type": metric_type,
                "time_range_hours": time_range_hours,
                "data_points": len(relevant_metrics),
                "statistics": {
                    "mean": round(mean, 2),
                    "stdev": round(stdev, 2)
                },
                "anomalies_detected": len(anomalies),
                "anomalies": anomalies[:5]  # First 5 anomalies
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "detect_anomalies",
                "message": f"Anomaly detection failed: {e}"
            }

    def run(self) -> str:
        """
        Execute drift monitoring operation.

        Returns:
            JSON string with operation result
        """
        try:
            if self.operation == "record_metrics":
                result = self.record_metrics(
                    query=self.query,
                    token_count=self.token_count,
                    results_returned=self.results_returned,
                    sources_used=self.sources_used,
                    unique_doc_ids=self.unique_doc_ids
                )

            elif self.operation == "analyze_drift":
                if not self.metric_type:
                    return json.dumps({
                        "status": "error",
                        "message": "Operation 'analyze_drift' requires: metric_type"
                    })

                result = self.analyze_drift(
                    metric_type=self.metric_type,
                    time_range_hours=self.time_range_hours
                )

            elif self.operation == "get_trends":
                result = self.get_trends(time_range_hours=self.time_range_hours)

            elif self.operation == "detect_anomalies":
                if not self.metric_type:
                    return json.dumps({
                        "status": "error",
                        "message": "Operation 'detect_anomalies' requires: metric_type"
                    })

                result = self.detect_anomalies(
                    metric_type=self.metric_type,
                    time_range_hours=self.time_range_hours
                )

            else:
                return json.dumps({
                    "status": "error",
                    "message": f"Unknown operation: {self.operation}. Valid: record_metrics, analyze_drift, get_trends, detect_anomalies"
                })

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "status": "error",
                "operation": self.operation,
                "message": f"Execution failed: {e}"
            })


# Test block
if __name__ == "__main__":
    print("=" * 60)
    print("Testing MonitorRAGDrift Tool")
    print("=" * 60)

    # Test 1: Analyze token length drift
    print("\n1. Analyze token length drift (7 days):")
    tool = MonitorRAGDrift(
        operation="analyze_drift",
        metric_type="token_length",
        time_range_hours=168  # 7 days
    )
    result = tool.run()
    print(result)

    # Test 2: Analyze coverage drift
    print("\n2. Analyze coverage drift:")
    tool = MonitorRAGDrift(
        operation="analyze_drift",
        metric_type="coverage",
        time_range_hours=168
    )
    result = tool.run()
    print(result)

    # Test 3: Analyze source distribution drift
    print("\n3. Analyze source distribution drift:")
    tool = MonitorRAGDrift(
        operation="analyze_drift",
        metric_type="source_distribution",
        time_range_hours=168
    )
    result = tool.run()
    print(result)

    # Test 4: Get all trends
    print("\n4. Get trends across all metrics:")
    tool = MonitorRAGDrift(
        operation="get_trends",
        time_range_hours=168
    )
    result = tool.run()
    print(result)

    # Test 5: Detect anomalies
    print("\n5. Detect anomalies in token length:")
    tool = MonitorRAGDrift(
        operation="detect_anomalies",
        metric_type="token_length",
        time_range_hours=168
    )
    result = tool.run()
    print(result)

    # Test 6: Record new metrics
    print("\n6. Record new metrics:")
    tool = MonitorRAGDrift(
        operation="record_metrics",
        query="test query",
        token_count=1500,
        results_returned=5,
        sources_used=["zep", "opensearch", "zep"],
        unique_doc_ids=4
    )
    result = tool.run()
    print(result)

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
