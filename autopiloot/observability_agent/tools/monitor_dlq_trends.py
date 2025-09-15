"""
Monitor DLQ Trends tool for analyzing dead letter queue patterns and spikes.
Implements TASK-OBS-0040 with trend analysis and anomaly detection.
"""

import os
import sys
import json
from typing import Optional, Dict, Any, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_var
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class MonitorDLQTrends(BaseTool):
    """
    Monitors dead letter queue trends and identifies anomalous patterns.
    
    Analyzes DLQ entries over configurable time windows, identifies top failure
    reasons, detects spikes in failure rates, and provides alerting for anomalies.
    """
    
    analysis_window_hours: int = Field(
        24,
        description="Time window for trend analysis in hours. Default 24 hours.",
        ge=1,
        le=168  # Max 1 week
    )
    
    spike_threshold: float = Field(
        2.0,
        description="Multiplier for spike detection. Alert if current rate > threshold * baseline. Default 2.0",
        ge=1.1,
        le=10.0
    )
    
    include_recommendations: bool = Field(
        True,
        description="Include operational recommendations based on trends"
    )
    
    def run(self) -> str:
        """
        Analyzes DLQ trends and returns pattern analysis with alert recommendations.
        
        Returns:
            str: JSON string containing trend analysis, top failures, and alerts
            
        Raises:
            RuntimeError: If DLQ trend analysis fails
        """
        try:
            # Initialize Firestore client
            db = self._initialize_firestore()
            
            # Calculate analysis window
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=self.analysis_window_hours)
            
            # Get DLQ entries for the analysis window
            dlq_entries = self._get_dlq_entries(db, start_time, end_time)
            
            # Analyze trends and patterns
            trend_analysis = self._analyze_trends(dlq_entries, start_time, end_time)
            failure_patterns = self._analyze_failure_patterns(dlq_entries)
            temporal_analysis = self._analyze_temporal_patterns(dlq_entries, start_time, end_time)
            
            # Detect anomalies and spikes
            alerts = self._detect_anomalies(trend_analysis, failure_patterns, temporal_analysis)
            
            # Generate operational recommendations
            recommendations = []
            if self.include_recommendations:
                recommendations = self._generate_recommendations(failure_patterns, temporal_analysis, alerts)
            
            # Log DLQ monitoring to audit trail
            audit_logger.log_dlq_monitored(
                entries_analyzed=len(dlq_entries),
                top_error_type=failure_patterns["top_errors"][0]["error_type"] if failure_patterns["top_errors"] else "none",
                alert_count=len(alerts),
                actor="ObservabilityAgent"
            )
            
            return json.dumps({
                "analysis_timestamp": end_time.isoformat(),
                "analysis_window": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_hours": self.analysis_window_hours
                },
                "trend_analysis": trend_analysis,
                "failure_patterns": failure_patterns,
                "temporal_analysis": temporal_analysis,
                "alerts": alerts,
                "recommendations": recommendations,
                "health_score": self._calculate_dlq_health_score(trend_analysis, failure_patterns)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to monitor DLQ trends: {str(e)}",
                "trend_analysis": None
            })
    
    def _get_dlq_entries(self, db, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve DLQ entries from Firestore within the analysis window."""
        try:
            query = (db.collection('jobs_deadletter')
                    .where('dlq_created_at', '>=', start_time)
                    .where('dlq_created_at', '<=', end_time)
                    .order_by('dlq_created_at', direction=firestore.Query.DESCENDING)
                    .limit(1000))  # Reasonable limit for analysis
            
            entries = []
            for doc in query.stream():
                entry_data = doc.to_dict()
                entry_data['dlq_id'] = doc.id
                
                # Convert timestamp to ISO string if needed
                if 'dlq_created_at' in entry_data and hasattr(entry_data['dlq_created_at'], 'isoformat'):
                    entry_data['dlq_created_at'] = entry_data['dlq_created_at'].isoformat()
                
                entries.append(entry_data)
            
            return entries
            
        except Exception as e:
            # Return empty list if query fails
            return []
    
    def _analyze_trends(self, entries: List[Dict[str, Any]], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Analyze overall DLQ trends and rates."""
        total_entries = len(entries)
        duration_hours = (end_time - start_time).total_seconds() / 3600
        
        # Calculate rate metrics
        entries_per_hour = total_entries / duration_hours if duration_hours > 0 else 0
        
        # Group by job type
        job_type_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for entry in entries:
            job_type = entry.get('job_type', 'unknown')
            severity = entry.get('severity', 'unknown')
            job_type_counts[job_type] += 1
            severity_counts[severity] += 1
        
        # Calculate baseline rate (historical comparison would be done here)
        # For now, use a simple heuristic: < 1 per hour is normal
        baseline_rate = 0.5  # entries per hour
        rate_change = (entries_per_hour - baseline_rate) / baseline_rate if baseline_rate > 0 else 0
        
        return {
            "total_entries": total_entries,
            "duration_hours": duration_hours,
            "entries_per_hour": round(entries_per_hour, 2),
            "baseline_rate": baseline_rate,
            "rate_change": round(rate_change, 2),
            "job_type_distribution": dict(job_type_counts),
            "severity_distribution": dict(severity_counts),
            "trend_status": self._get_trend_status(rate_change)
        }
    
    def _analyze_failure_patterns(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze failure patterns and identify top error types."""
        error_type_counts = defaultdict(int)
        error_details = defaultdict(list)
        
        for entry in entries:
            failure_context = entry.get('failure_context', {})
            error_type = failure_context.get('error_type', 'unknown')
            error_message = failure_context.get('error_message', '')
            
            error_type_counts[error_type] += 1
            error_details[error_type].append({
                'dlq_id': entry.get('dlq_id'),
                'job_type': entry.get('job_type'),
                'error_message': error_message[:100] + '...' if len(error_message) > 100 else error_message,
                'created_at': entry.get('dlq_created_at')
            })
        
        # Sort by frequency
        top_errors = [
            {
                'error_type': error_type,
                'count': count,
                'percentage': round((count / len(entries)) * 100, 1) if entries else 0,
                'recent_examples': error_details[error_type][:3]  # Top 3 examples
            }
            for error_type, count in sorted(error_type_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return {
            "top_errors": top_errors[:10],  # Top 10 error types
            "unique_error_types": len(error_type_counts),
            "error_diversity": self._calculate_error_diversity(error_type_counts, len(entries))
        }
    
    def _analyze_temporal_patterns(self, entries: List[Dict[str, Any]], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Analyze temporal patterns in DLQ entries."""
        hourly_counts = defaultdict(int)
        
        for entry in entries:
            created_at_str = entry.get('dlq_created_at')
            if created_at_str:
                try:
                    # Parse timestamp and get hour
                    if isinstance(created_at_str, str):
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    else:
                        created_at = created_at_str
                    
                    hour_key = created_at.strftime('%Y-%m-%d %H:00')
                    hourly_counts[hour_key] += 1
                except ValueError:
                    continue
        
        # Calculate peak and valley hours
        if hourly_counts:
            peak_hour = max(hourly_counts, key=hourly_counts.get)
            valley_hour = min(hourly_counts, key=hourly_counts.get)
            peak_count = hourly_counts[peak_hour]
            valley_count = hourly_counts[valley_hour]
        else:
            peak_hour = valley_hour = None
            peak_count = valley_count = 0
        
        # Calculate variance to detect spikes
        counts = list(hourly_counts.values()) if hourly_counts else [0]
        avg_count = sum(counts) / len(counts)
        variance = sum((x - avg_count) ** 2 for x in counts) / len(counts)
        
        return {
            "hourly_distribution": dict(sorted(hourly_counts.items())),
            "peak_hour": peak_hour,
            "peak_count": peak_count,
            "valley_hour": valley_hour,
            "valley_count": valley_count,
            "average_per_hour": round(avg_count, 2),
            "variance": round(variance, 2),
            "volatility": "high" if variance > avg_count else "medium" if variance > avg_count / 2 else "low"
        }
    
    def _detect_anomalies(self, trend_analysis: Dict[str, Any], failure_patterns: Dict[str, Any], temporal_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies and generate alerts."""
        alerts = []
        
        # Check for rate spikes
        rate_change = trend_analysis.get('rate_change', 0)
        if rate_change > self.spike_threshold - 1:  # Convert multiplier to percentage
            severity = "critical" if rate_change > 3 else "warning"
            alerts.append({
                "type": "rate_spike",
                "severity": severity,
                "message": f"DLQ entry rate increased by {rate_change * 100:.1f}% above baseline",
                "metric": "entries_per_hour",
                "current_value": trend_analysis.get('entries_per_hour', 0),
                "threshold": trend_analysis.get('baseline_rate', 0) * self.spike_threshold
            })
        
        # Check for high error concentration
        top_errors = failure_patterns.get('top_errors', [])
        if top_errors and top_errors[0]['percentage'] > 60:
            alerts.append({
                "type": "error_concentration",
                "severity": "warning",
                "message": f"Single error type accounts for {top_errors[0]['percentage']}% of DLQ entries",
                "metric": "error_concentration",
                "dominant_error": top_errors[0]['error_type'],
                "percentage": top_errors[0]['percentage']
            })
        
        # Check for temporal volatility
        volatility = temporal_analysis.get('volatility', 'low')
        if volatility == "high":
            alerts.append({
                "type": "temporal_volatility",
                "severity": "warning",
                "message": "High volatility detected in DLQ entry timing",
                "metric": "temporal_variance",
                "variance": temporal_analysis.get('variance', 0),
                "pattern": "irregular_spikes"
            })
        
        return alerts
    
    def _generate_recommendations(self, failure_patterns: Dict[str, Any], temporal_analysis: Dict[str, Any], alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate operational recommendations based on analysis."""
        recommendations = []
        
        # Recommendations based on top errors
        top_errors = failure_patterns.get('top_errors', [])
        if top_errors:
            top_error = top_errors[0]
            error_type = top_error['error_type']
            
            if error_type == "api_timeout":
                recommendations.append({
                    "category": "retry_policy",
                    "priority": "high",
                    "action": "Increase timeout values for API calls",
                    "rationale": f"API timeouts account for {top_error['percentage']}% of failures"
                })
            elif error_type == "quota_exceeded":
                recommendations.append({
                    "category": "resource_management",
                    "priority": "critical",
                    "action": "Implement quota-aware throttling",
                    "rationale": f"Quota violations account for {top_error['percentage']}% of failures"
                })
            elif error_type == "authorization_failed":
                recommendations.append({
                    "category": "security",
                    "priority": "critical",
                    "action": "Review and refresh API credentials",
                    "rationale": f"Authorization failures account for {top_error['percentage']}% of failures"
                })
        
        # Recommendations based on temporal patterns
        if temporal_analysis.get('volatility') == "high":
            recommendations.append({
                "category": "stability",
                "priority": "medium",
                "action": "Investigate load balancing and rate limiting",
                "rationale": "High temporal volatility suggests uneven load distribution"
            })
        
        # Recommendations based on alerts
        for alert in alerts:
            if alert['type'] == "rate_spike":
                recommendations.append({
                    "category": "incident_response",
                    "priority": "urgent",
                    "action": "Investigate root cause of failure rate spike",
                    "rationale": f"DLQ rate increased by {alert.get('current_value', 0):.1f} entries/hour"
                })
        
        return recommendations
    
    def _calculate_error_diversity(self, error_type_counts: Dict[str, int], total_entries: int) -> float:
        """Calculate error diversity using Shannon entropy."""
        if total_entries == 0:
            return 0.0
        
        entropy = 0.0
        for count in error_type_counts.values():
            probability = count / total_entries
            if probability > 0:
                entropy -= probability * (probability ** 0.5)  # Simplified entropy calculation
        
        return round(entropy, 3)
    
    def _get_trend_status(self, rate_change: float) -> str:
        """Get human-readable trend status."""
        if rate_change > 1.0:
            return "deteriorating"
        elif rate_change > 0.2:
            return "concerning"
        elif rate_change > -0.1:
            return "stable"
        else:
            return "improving"
    
    def _calculate_dlq_health_score(self, trend_analysis: Dict[str, Any], failure_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall DLQ health score."""
        # Base score starts at 100
        score = 100.0
        
        # Penalize high entry rate
        entries_per_hour = trend_analysis.get('entries_per_hour', 0)
        if entries_per_hour > 2:
            score -= min(30, entries_per_hour * 10)  # Cap penalty at 30 points
        
        # Penalize error concentration
        top_errors = failure_patterns.get('top_errors', [])
        if top_errors and top_errors[0]['percentage'] > 50:
            score -= (top_errors[0]['percentage'] - 50) * 0.5
        
        # Penalize rate increases
        rate_change = trend_analysis.get('rate_change', 0)
        if rate_change > 0:
            score -= min(25, rate_change * 25)
        
        score = max(0, min(100, score))
        
        if score >= 80:
            status = "healthy"
        elif score >= 60:
            status = "concerning"
        elif score >= 40:
            status = "degraded"
        else:
            status = "critical"
        
        return {
            "score": round(score, 1),
            "status": status,
            "factors": {
                "entry_rate_impact": min(30, entries_per_hour * 10),
                "concentration_impact": (top_errors[0]['percentage'] - 50) * 0.5 if top_errors and top_errors[0]['percentage'] > 50 else 0,
                "trend_impact": min(25, max(0, rate_change * 25))
            }
        }
    
    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            project_id = get_required_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore")
            credentials_path = get_required_var("GOOGLE_APPLICATION_CREDENTIALS", "Google service account credentials file path")
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            return firestore.Client(project=project_id)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    # Test DLQ trends monitoring
    print("Testing monitor_dlq_trends...")
    test_tool = MonitorDLQTrends(
        analysis_window_hours=24,
        spike_threshold=2.0,
        include_recommendations=True
    )
    
    try:
        result = test_tool.run()
        print("DLQ trends monitoring result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            trend = data['trend_analysis']
            print(f"Entries analyzed: {trend['total_entries']}")
            print(f"Rate: {trend['entries_per_hour']} per hour")
            print(f"Trend: {trend['trend_status']}")
            print(f"Health score: {data['health_score']['score']} ({data['health_score']['status']})")
            print(f"Alerts: {len(data['alerts'])}")
            print(f"Recommendations: {len(data['recommendations'])}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting with shorter window...")
    test_tool_short = MonitorDLQTrends(
        analysis_window_hours=6,
        spike_threshold=1.5,
        include_recommendations=False
    )
    
    try:
        result = test_tool_short.run()
        data = json.loads(result)
        if "error" not in data:
            print(f"Short window analysis: {data['trend_analysis']['total_entries']} entries")
        
    except Exception as e:
        print(f"Short window test error: {str(e)}")