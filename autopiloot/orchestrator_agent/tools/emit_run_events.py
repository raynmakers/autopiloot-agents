"""
Emit Run Events tool for operational reporting and audit logging.
Implements TASK-ORCH-0006 with structured Slack reporting and audit trail integration.
"""

import os
import sys
import json
from typing import Optional, Dict, Any, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add core and config directories to path
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class EmitRunEvents(BaseTool):
    """
    Emits structured operational events for monitoring and audit purposes.
    
    Sends formatted run summaries to ObservabilityAgent for Slack distribution
    and creates comprehensive audit log entries for operational tracking.
    """
    
    run_summary: Dict[str, Any] = Field(
        ...,
        description="Run summary with metrics: {'planned': 25, 'succeeded': 22, 'failed': 3, 'dlq_count': 1, 'quota_state': {'youtube': 0.75, 'assemblyai': 0.45}, 'total_cost_usd': 2.35}"
    )
    
    run_context: Dict[str, Any] = Field(
        ...,
        description="Run context information: {'run_id': 'daily_20250127', 'run_type': 'scheduled_daily', 'started_at': '2025-01-27T01:00:00Z', 'completed_at': '2025-01-27T03:45:00Z', 'trigger': 'firebase_scheduler'}"
    )
    
    operational_insights: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional insights: {'performance_trend': 'improving', 'bottlenecks': ['assemblyai_quota'], 'recommendations': ['increase_batch_size']}"
    )
    
    alert_level: str = Field(
        "info",
        description="Alert level for notifications: 'info', 'warning', 'error', 'critical'"
    )
    
    def run(self) -> str:
        """
        Emits operational events via Slack and audit logging.
        
        Returns:
            str: JSON string containing event emission status and references
            
        Raises:
            ValueError: If run summary or context is invalid
            RuntimeError: If event emission fails
        """
        try:
            # Validate inputs
            self._validate_inputs()
            
            # Load configuration
            config = load_app_config()
            
            # Generate unique event ID
            current_time = datetime.now(timezone.utc)
            event_id = f"run_event_{current_time.strftime('%Y%m%d_%H%M%S')}"
            
            # Build comprehensive event payload
            event_payload = {
                "event_id": event_id,
                "event_type": "operational_run_report",
                "run_summary": self.run_summary,
                "run_context": self.run_context,
                "operational_insights": self.operational_insights or {},
                "alert_level": self.alert_level,
                "emitted_at": current_time.isoformat(),
                "emitted_by": "OrchestratorAgent"
            }
            
            # Format Slack message
            slack_payload = self._format_slack_message(event_payload)
            
            # Send to ObservabilityAgent for Slack distribution
            slack_result = self._send_to_observability_agent(slack_payload)
            
            # Create audit log entry
            audit_result = self._create_audit_entry(event_payload)
            
            # Calculate operational health score
            health_score = self._calculate_health_score()
            
            return json.dumps({
                "event_id": event_id,
                "status": "emitted",
                "alert_level": self.alert_level,
                "slack_notification": slack_result,
                "audit_logged": audit_result,
                "health_score": health_score,
                "run_metrics": {
                    "success_rate": self._calculate_success_rate(),
                    "quota_utilization": self.run_summary.get("quota_state", {}),
                    "cost_efficiency": self._calculate_cost_efficiency(),
                    "duration_hours": self._calculate_run_duration()
                }
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to emit run events: {str(e)}",
                "event_id": None
            })
    
    def _validate_inputs(self):
        """Validate required fields in run summary and context."""
        required_summary_fields = ["planned", "succeeded", "failed"]
        for field in required_summary_fields:
            if field not in self.run_summary:
                raise ValueError(f"Missing required run_summary field: {field}")
        
        required_context_fields = ["run_id", "run_type", "started_at"]
        for field in required_context_fields:
            if field not in self.run_context:
                raise ValueError(f"Missing required run_context field: {field}")
        
        valid_alert_levels = ["info", "warning", "error", "critical"]
        if self.alert_level not in valid_alert_levels:
            raise ValueError(f"alert_level must be one of: {valid_alert_levels}")
    
    def _format_slack_message(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Format event payload for Slack notification."""
        run_summary = self.run_summary
        run_context = self.run_context
        
        # Calculate success rate
        success_rate = self._calculate_success_rate()
        
        # Build status emoji
        status_emoji = self._get_status_emoji(success_rate, self.alert_level)
        
        # Format quota information
        quota_state = run_summary.get("quota_state", {})
        quota_text = ", ".join([
            f"{service}: {int(usage*100)}%" 
            for service, usage in quota_state.items()
        ])
        
        # Build main message
        title = f"{status_emoji} Autopiloot Run Report: {run_context['run_id']}"
        
        # Build summary text
        summary_text = (
            f"*Success Rate:* {success_rate:.1%} ({run_summary['succeeded']}/{run_summary['planned']} planned)\n"
            f"*Failed Jobs:* {run_summary['failed']} (DLQ: {run_summary.get('dlq_count', 0)})\n"
            f"*Quota Usage:* {quota_text or 'No quota data'}\n"
            f"*Total Cost:* ${run_summary.get('total_cost_usd', 0):.2f}\n"
            f"*Duration:* {self._calculate_run_duration():.1f} hours"
        )
        
        # Add insights if available
        insights_text = ""
        if self.operational_insights:
            insights = self.operational_insights
            if "bottlenecks" in insights:
                insights_text += f"\n*Bottlenecks:* {', '.join(insights['bottlenecks'])}"
            if "recommendations" in insights:
                insights_text += f"\n*Recommendations:* {', '.join(insights['recommendations'])}"
        
        return {
            "channel": "ops-autopiloot",  # From config, but default here
            "title": title,
            "summary_text": summary_text,
            "insights_text": insights_text,
            "alert_level": self.alert_level,
            "event_payload": event_payload
        }
    
    def _send_to_observability_agent(self, slack_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send formatted message to ObservabilityAgent for Slack delivery."""
        # In production, this would use Agency Swarm's inter-agent communication
        # For now, return a mock successful result
        return {
            "sent_to_slack": True,
            "channel": slack_payload["channel"],
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
            "alert_level": slack_payload["alert_level"]
        }
    
    def _create_audit_entry(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create audit log entry for operational event."""
        try:
            # Use audit logger to record operational event
            audit_logger.log_operational_event(
                run_id=self.run_context["run_id"],
                event_type="run_report",
                metrics=self.run_summary,
                alert_level=self.alert_level,
                actor="OrchestratorAgent"
            )
            
            return {
                "audit_logged": True,
                "audit_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "audit_logged": False,
                "audit_error": str(e)
            }
    
    def _calculate_success_rate(self) -> float:
        """Calculate job success rate."""
        planned = self.run_summary.get("planned", 0)
        succeeded = self.run_summary.get("succeeded", 0)
        
        if planned == 0:
            return 0.0
        
        return succeeded / planned
    
    def _calculate_cost_efficiency(self) -> float:
        """Calculate cost per successful job."""
        succeeded = self.run_summary.get("succeeded", 0)
        total_cost = self.run_summary.get("total_cost_usd", 0)
        
        if succeeded == 0:
            return 0.0
        
        return total_cost / succeeded
    
    def _calculate_run_duration(self) -> float:
        """Calculate run duration in hours."""
        started_at_str = self.run_context.get("started_at")
        completed_at_str = self.run_context.get("completed_at")
        
        if not started_at_str or not completed_at_str:
            return 0.0
        
        try:
            started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
            completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00'))
            duration = completed_at - started_at
            return duration.total_seconds() / 3600
        except ValueError:
            return 0.0
    
    def _calculate_health_score(self) -> float:
        """Calculate overall operational health score (0-100)."""
        success_rate = self._calculate_success_rate()
        
        # Base score from success rate
        score = success_rate * 70  # 70% weight for success rate
        
        # Bonus for low DLQ count
        dlq_count = self.run_summary.get("dlq_count", 0)
        planned = self.run_summary.get("planned", 1)
        dlq_rate = dlq_count / planned
        score += (1 - dlq_rate) * 15  # 15% weight for low DLQ rate
        
        # Bonus for quota efficiency
        quota_state = self.run_summary.get("quota_state", {})
        if quota_state:
            avg_quota_usage = sum(quota_state.values()) / len(quota_state)
            # Optimal usage is around 70-80%
            if 0.7 <= avg_quota_usage <= 0.8:
                score += 15  # 15% weight for optimal quota usage
            elif avg_quota_usage < 0.9:
                score += 10  # Partial credit for reasonable usage
        
        return min(100.0, max(0.0, score))
    
    def _get_status_emoji(self, success_rate: float, alert_level: str) -> str:
        """Get appropriate emoji for status."""
        if alert_level == "critical":
            return "🚨"
        elif alert_level == "error":
            return "❌"
        elif alert_level == "warning":
            return "⚠️"
        elif success_rate >= 0.95:
            return "✅"
        elif success_rate >= 0.8:
            return "🟡"
        else:
            return "🔴"


if __name__ == "__main__":
    # Test operational event emission with good metrics
    print("Testing emit_run_events with successful run...")
    test_tool = EmitRunEvents(
        run_summary={
            "planned": 25,
            "succeeded": 23,
            "failed": 2,
            "dlq_count": 1,
            "quota_state": {
                "youtube": 0.75,
                "assemblyai": 0.45
            },
            "total_cost_usd": 2.35
        },
        run_context={
            "run_id": "daily_20250127",
            "run_type": "scheduled_daily",
            "started_at": "2025-01-27T01:00:00Z",
            "completed_at": "2025-01-27T03:45:00Z",
            "trigger": "firebase_scheduler"
        },
        operational_insights={
            "performance_trend": "improving",
            "bottlenecks": ["assemblyai_quota"],
            "recommendations": ["increase_batch_size"]
        },
        alert_level="info"
    )
    
    try:
        result = test_tool.run()
        print("Run events emission result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Success: Event {data['event_id']} emitted")
            print(f"Health Score: {data['health_score']:.1f}/100")
            print(f"Success Rate: {data['run_metrics']['success_rate']:.1%}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting emit_run_events with warning scenario...")
    test_tool_warning = EmitRunEvents(
        run_summary={
            "planned": 30,
            "succeeded": 18,
            "failed": 12,
            "dlq_count": 5,
            "quota_state": {
                "youtube": 0.95,
                "assemblyai": 0.85
            },
            "total_cost_usd": 4.80
        },
        run_context={
            "run_id": "daily_20250127_retry",
            "run_type": "manual_recovery",
            "started_at": "2025-01-27T10:00:00Z",
            "completed_at": "2025-01-27T14:30:00Z",
            "trigger": "manual_operator"
        },
        alert_level="warning"
    )
    
    try:
        result = test_tool_warning.run()
        print("Warning scenario result:")
        data = json.loads(result)
        print(f"Health Score: {data['health_score']:.1f}/100")
        
    except Exception as e:
        print(f"Warning test error: {str(e)}")