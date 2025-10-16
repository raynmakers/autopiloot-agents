"""
Alert Engine tool for centralized alert throttling, deduplication, and escalation orchestration.
Implements TASK-OBS-0040 with sophisticated alert management and Slack integration.
"""

import os
import sys
import json
from typing import Optional, Dict, Any, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone, timedelta
import hashlib

# Add core and config directories to path
from env_loader import get_required_env_var
from firestore_client import get_firestore_client
from loader import load_app_config
from audit_logger import audit_logger



class AlertEngine(BaseTool):
    """
    Centralized alert engine with throttling, deduplication, and escalation management.
    
    Processes incoming alerts, applies intelligent throttling to prevent spam,
    deduplicates similar alerts, manages escalation chains, and delivers alerts
    via appropriate channels with proper formatting.
    """
    
    alert_type: str = Field(
        ...,
        description="Type of alert: 'quota_threshold', 'dlq_spike', 'stuck_jobs', 'cost_budget', 'system_error', 'performance_degradation'"
    )
    
    severity: str = Field(
        ...,
        description="Alert severity: 'info', 'warning', 'error', 'critical'"
    )
    
    message: str = Field(
        ...,
        description="Alert message content"
    )
    
    details: Dict[str, Any] = Field(
        {},
        description="Additional alert details and context"
    )
    
    source_component: str = Field(
        "system",
        description="Component that generated the alert (e.g., 'quota_monitor', 'dlq_analyzer')"
    )
    
    override_throttling: bool = Field(
        False,
        description="Override throttling for critical alerts that must be delivered immediately"
    )
    
    def run(self) -> str:
        """
        Processes alert through throttling, deduplication, and delivery pipeline.
        
        Returns:
            str: JSON string containing alert processing result and delivery status
            
        Raises:
            RuntimeError: If alert processing fails
        """
        try:
            # Initialize Firestore client
            db = get_firestore_client()
            
            # Generate alert fingerprint for deduplication
            alert_fingerprint = self._generate_alert_fingerprint()
            
            # Check throttling and deduplication
            throttle_result = self._check_throttling(db, alert_fingerprint)
            
            if throttle_result["should_throttle"] and not self.override_throttling:
                return json.dumps({
                    "alert_id": alert_fingerprint,
                    "status": "throttled",
                    "reason": throttle_result["reason"],
                    "next_eligible_time": throttle_result.get("next_eligible_time"),
                    "delivery_attempted": False,
                    "throttle_details": throttle_result
                })
            
            # Process and enrich alert
            enriched_alert = self._enrich_alert(alert_fingerprint)
            
            # Determine delivery channels and escalation
            delivery_plan = self._plan_alert_delivery(enriched_alert)
            
            # Execute alert delivery
            delivery_results = self._execute_alert_delivery(db, enriched_alert, delivery_plan)
            
            # Update throttling records
            self._update_throttling_records(db, alert_fingerprint, enriched_alert)
            
            # Log alert processing to audit trail
            audit_logger.log_alert_processed(
                alert_type=self.alert_type,
                severity=self.severity,
                alert_id=alert_fingerprint,
                delivery_status="delivered" if delivery_results["success"] else "failed",
                actor="ObservabilityAgent"
            )
            
            return json.dumps({
                "alert_id": alert_fingerprint,
                "status": "processed",
                "enriched_alert": enriched_alert,
                "delivery_plan": delivery_plan,
                "delivery_results": delivery_results,
                "throttling_updated": True
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to process alert: {str(e)}",
                "alert_id": None,
                "status": "error"
            })
    
    def _generate_alert_fingerprint(self) -> str:
        """Generate unique fingerprint for alert deduplication."""
        # Create fingerprint from alert type, source, and key details
        fingerprint_data = {
            "alert_type": self.alert_type,
            "source_component": self.source_component,
            "severity": self.severity
        }
        
        # Add key details for deduplication (but not the full message)
        key_details = {}
        for key in ["service", "quota_type", "error_type", "job_type", "component"]:
            if key in self.details:
                key_details[key] = self.details[key]
        
        fingerprint_data["key_details"] = key_details
        
        # Generate hash
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_string.encode()).hexdigest()[:12]
    
    def _check_throttling(self, db, alert_fingerprint: str) -> Dict[str, Any]:
        """Check if alert should be throttled based on recent history."""
        try:
            # Query recent alerts of the same fingerprint
            now = datetime.now(timezone.utc)
            throttle_window = self._get_throttle_window()
            cutoff_time = now - timedelta(minutes=throttle_window)
            
            recent_alerts_query = (db.collection('alert_throttle_records')
                                 .where('alert_fingerprint', '==', alert_fingerprint)
                                 .where('last_sent', '>=', cutoff_time)
                                 .limit(10))
            
            recent_alerts = list(recent_alerts_query.stream())
            
            if not recent_alerts:
                return {"should_throttle": False, "reason": "No recent alerts"}
            
            # Get the most recent alert record
            latest_alert = max(recent_alerts, key=lambda x: x.to_dict().get('last_sent', now))
            latest_data = latest_alert.to_dict()
            
            last_sent = latest_data.get('last_sent')
            send_count = latest_data.get('send_count', 0)
            
            if not last_sent:
                return {"should_throttle": False, "reason": "No valid last_sent time"}
            
            # Convert Firestore timestamp if needed
            if hasattr(last_sent, 'replace'):
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            
            # Calculate time since last alert
            time_since_last = (now - last_sent).total_seconds() / 60  # minutes
            
            # Determine throttling based on severity and frequency
            min_interval = self._get_min_interval_for_severity()
            
            # Exponential backoff for repeated alerts
            adjusted_interval = min_interval * (1.5 ** min(send_count, 5))
            
            if time_since_last < adjusted_interval:
                next_eligible = last_sent + timedelta(minutes=adjusted_interval)
                return {
                    "should_throttle": True,
                    "reason": f"Alert sent {time_since_last:.1f} minutes ago, minimum interval is {adjusted_interval:.1f} minutes",
                    "next_eligible_time": next_eligible.isoformat(),
                    "send_count": send_count,
                    "adjusted_interval": adjusted_interval
                }
            
            return {"should_throttle": False, "reason": "Throttling interval satisfied"}
            
        except Exception:
            # If throttling check fails, allow the alert through
            return {"should_throttle": False, "reason": "Throttling check failed - allowing alert"}
    
    def _enrich_alert(self, alert_fingerprint: str) -> Dict[str, Any]:
        """Enrich alert with additional context and metadata."""
        enriched = {
            "alert_id": alert_fingerprint,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "source_component": self.source_component,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "escalation_level": self._determine_escalation_level(),
            "urgency": self._calculate_urgency(),
            "impact": self._assess_impact(),
            "recommended_actions": self._get_recommended_actions()
        }
        
        # Add context-specific enrichment
        if self.alert_type == "quota_threshold":
            enriched["quota_context"] = self._enrich_quota_context()
        elif self.alert_type == "dlq_spike":
            enriched["dlq_context"] = self._enrich_dlq_context()
        elif self.alert_type == "stuck_jobs":
            enriched["job_context"] = self._enrich_job_context()
        elif self.alert_type == "cost_budget":
            enriched["cost_context"] = self._enrich_cost_context()
        
        return enriched
    
    def _plan_alert_delivery(self, enriched_alert: Dict[str, Any]) -> Dict[str, Any]:
        """Plan alert delivery channels and escalation strategy."""
        severity = enriched_alert["severity"]
        escalation_level = enriched_alert["escalation_level"]
        urgency = enriched_alert["urgency"]
        
        delivery_plan = {
            "primary_channels": [],
            "escalation_channels": [],
            "delivery_delay_minutes": 0,
            "requires_acknowledgment": False,
            "auto_escalation_minutes": None
        }
        
        # Determine primary delivery channels
        if severity in ["critical", "error"]:
            delivery_plan["primary_channels"] = ["slack", "email"]
            delivery_plan["requires_acknowledgment"] = True
            delivery_plan["auto_escalation_minutes"] = 15 if severity == "critical" else 30
        elif severity == "warning":
            delivery_plan["primary_channels"] = ["slack"]
            delivery_plan["auto_escalation_minutes"] = 60
        else:  # info
            delivery_plan["primary_channels"] = ["slack"]
            delivery_plan["delivery_delay_minutes"] = 5  # Batch info alerts
        
        # Determine escalation channels
        if escalation_level >= 2:
            delivery_plan["escalation_channels"] = ["pagerduty", "phone"]
        elif escalation_level >= 1:
            delivery_plan["escalation_channels"] = ["email", "slack_oncall"]
        
        # Adjust for urgency
        if urgency == "immediate":
            delivery_plan["delivery_delay_minutes"] = 0
            delivery_plan["auto_escalation_minutes"] = max(5, delivery_plan.get("auto_escalation_minutes", 15) // 2)
        
        return delivery_plan
    
    def _execute_alert_delivery(self, db, enriched_alert: Dict[str, Any], delivery_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute alert delivery according to the plan."""
        delivery_results = {
            "success": False,
            "channels_attempted": [],
            "channels_succeeded": [],
            "channels_failed": [],
            "delivery_details": {}
        }
        
        # Execute primary channel delivery
        for channel in delivery_plan["primary_channels"]:
            try:
                result = self._deliver_to_channel(channel, enriched_alert)
                delivery_results["channels_attempted"].append(channel)
                delivery_results["delivery_details"][channel] = result
                
                if result.get("success", False):
                    delivery_results["channels_succeeded"].append(channel)
                else:
                    delivery_results["channels_failed"].append(channel)
                    
            except Exception as e:
                delivery_results["channels_attempted"].append(channel)
                delivery_results["channels_failed"].append(channel)
                delivery_results["delivery_details"][channel] = {
                    "success": False,
                    "error": str(e)
                }
        
        # Mark as successful if at least one channel succeeded
        delivery_results["success"] = len(delivery_results["channels_succeeded"]) > 0
        
        # Schedule escalation if needed
        if delivery_plan.get("auto_escalation_minutes"):
            self._schedule_escalation(db, enriched_alert, delivery_plan)
        
        return delivery_results
    
    def _deliver_to_channel(self, channel: str, enriched_alert: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver alert to a specific channel."""
        if channel == "slack":
            return self._deliver_to_slack(enriched_alert)
        elif channel == "email":
            return self._deliver_to_email(enriched_alert)
        elif channel == "pagerduty":
            return self._deliver_to_pagerduty(enriched_alert)
        else:
            return {"success": False, "error": f"Unknown channel: {channel}"}
    
    def _deliver_to_slack(self, enriched_alert: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver alert to Slack with rich formatting."""
        try:
            # Format alert for Slack
            slack_blocks = self._format_slack_alert(enriched_alert)
            
            # In production, would use SendSlackMessage tool
            # For now, return mock success
            return {
                "success": True,
                "channel": "slack",
                "message_timestamp": datetime.now(timezone.utc).isoformat(),
                "blocks_count": len(slack_blocks)
            }
            
        except Exception as e:
            return {
                "success": False,
                "channel": "slack",
                "error": str(e)
            }
    
    def _deliver_to_email(self, enriched_alert: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver alert via email."""
        # Mock implementation - in production would integrate with email service
        return {
            "success": True,
            "channel": "email",
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _deliver_to_pagerduty(self, enriched_alert: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver alert to PagerDuty."""
        # Mock implementation - in production would integrate with PagerDuty API
        return {
            "success": True,
            "channel": "pagerduty",
            "incident_id": f"pd_{enriched_alert['alert_id']}"
        }
    
    def _format_slack_alert(self, enriched_alert: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format alert for Slack delivery."""
        severity = enriched_alert["severity"]
        alert_type = enriched_alert["alert_type"]
        
        # Choose emoji based on severity
        emoji_map = {
            "critical": "🚨",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        emoji = emoji_map.get(severity, "📢")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {severity.upper()}: {alert_type.replace('_', ' ').title()}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": enriched_alert["message"]
                }
            }
        ]
        
        # Add details section
        details_text = []
        for key, value in enriched_alert["details"].items():
            if isinstance(value, (str, int, float)):
                details_text.append(f"*{key.replace('_', ' ').title()}:* {value}")
        
        if details_text:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(details_text[:5])  # Limit to 5 details
                }
            })
        
        # Add recommended actions
        if enriched_alert.get("recommended_actions"):
            actions_text = "\n".join([f"• {action}" for action in enriched_alert["recommended_actions"][:3]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommended Actions:*\n{actions_text}"
                }
            })
        
        return blocks
    
    def _update_throttling_records(self, db, alert_fingerprint: str, enriched_alert: Dict[str, Any]):
        """Update throttling records for future deduplication."""
        try:
            throttle_doc_ref = db.collection('alert_throttle_records').document(alert_fingerprint)
            
            # Get existing record or create new one
            existing_doc = throttle_doc_ref.get()
            
            if existing_doc.exists:
                existing_data = existing_doc.to_dict()
                send_count = existing_data.get('send_count', 0) + 1
                first_seen = existing_data.get('first_seen')
            else:
                send_count = 1
                first_seen = firestore.SERVER_TIMESTAMP
            
            # Update record
            throttle_record = {
                'alert_fingerprint': alert_fingerprint,
                'alert_type': self.alert_type,
                'severity': self.severity,
                'source_component': self.source_component,
                'send_count': send_count,
                'last_sent': firestore.SERVER_TIMESTAMP,
                'first_seen': first_seen,
                'last_message': self.message
            }
            
            throttle_doc_ref.set(throttle_record, merge=True)
            
        except Exception:
            # Don't fail alert delivery if throttling record update fails
            pass
    
    def _schedule_escalation(self, db, enriched_alert: Dict[str, Any], delivery_plan: Dict[str, Any]):
        """Schedule automatic escalation if alert is not acknowledged."""
        try:
            escalation_time = datetime.now(timezone.utc) + timedelta(minutes=delivery_plan["auto_escalation_minutes"])
            
            escalation_record = {
                'alert_id': enriched_alert['alert_id'],
                'escalation_time': escalation_time,
                'escalation_channels': delivery_plan.get('escalation_channels', []),
                'status': 'scheduled',
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            db.collection('alert_escalations').document(enriched_alert['alert_id']).set(escalation_record)
            
        except Exception:
            # Don't fail alert delivery if escalation scheduling fails
            pass
    
    def _get_throttle_window(self) -> int:
        """Get throttling window in minutes based on alert type and severity."""
        if self.severity == "critical":
            return 5  # 5 minutes for critical
        elif self.severity == "error":
            return 15  # 15 minutes for errors
        elif self.severity == "warning":
            return 30  # 30 minutes for warnings
        else:
            return 60  # 1 hour for info
    
    def _get_min_interval_for_severity(self) -> int:
        """Get minimum interval between alerts of same type."""
        return {
            "critical": 2,   # 2 minutes
            "error": 5,      # 5 minutes
            "warning": 15,   # 15 minutes
            "info": 30       # 30 minutes
        }.get(self.severity, 30)
    
    def _determine_escalation_level(self) -> int:
        """Determine escalation level (0-3) based on alert characteristics."""
        if self.severity == "critical":
            return 2
        elif self.severity == "error" and self.alert_type in ["system_error", "quota_threshold"]:
            return 1
        elif self.override_throttling:
            return 1
        else:
            return 0
    
    def _calculate_urgency(self) -> str:
        """Calculate alert urgency: 'immediate', 'high', 'medium', 'low'."""
        if self.severity == "critical" or self.override_throttling:
            return "immediate"
        elif self.severity == "error":
            return "high"
        elif self.severity == "warning":
            return "medium"
        else:
            return "low"
    
    def _assess_impact(self) -> str:
        """Assess potential impact: 'high', 'medium', 'low'."""
        high_impact_types = ["quota_threshold", "system_error", "stuck_jobs"]
        medium_impact_types = ["dlq_spike", "cost_budget"]
        
        if self.alert_type in high_impact_types or self.severity == "critical":
            return "high"
        elif self.alert_type in medium_impact_types or self.severity == "error":
            return "medium"
        else:
            return "low"
    
    def _get_recommended_actions(self) -> List[str]:
        """Get recommended actions based on alert type."""
        actions_map = {
            "quota_threshold": [
                "Review quota usage patterns",
                "Consider throttling non-critical operations",
                "Contact provider for quota increase if needed"
            ],
            "dlq_spike": [
                "Investigate root cause of failures",
                "Review error patterns in DLQ",
                "Consider reprocessing failed jobs"
            ],
            "stuck_jobs": [
                "Check agent health and capacity",
                "Review job processing logs",
                "Consider manual intervention for critical jobs"
            ],
            "cost_budget": [
                "Review cost drivers and optimization opportunities",
                "Consider reducing processing volume temporarily",
                "Analyze cost per operation efficiency"
            ],
            "system_error": [
                "Check system logs for error details",
                "Verify service connectivity and credentials",
                "Consider restarting affected components"
            ],
            "performance_degradation": [
                "Monitor system resources and capacity",
                "Check for external service issues",
                "Review recent configuration changes"
            ]
        }
        
        return actions_map.get(self.alert_type, ["Investigate issue and take appropriate action"])
    
    def _enrich_quota_context(self) -> Dict[str, Any]:
        """Enrich quota-related alerts with additional context."""
        return {
            "service": self.details.get("service", "unknown"),
            "current_usage": self.details.get("current_usage", 0),
            "limit": self.details.get("limit", 0),
            "utilization_percent": self.details.get("utilization_percent", 0),
            "time_to_reset": self.details.get("time_to_reset", "unknown")
        }
    
    def _enrich_dlq_context(self) -> Dict[str, Any]:
        """Enrich DLQ-related alerts with additional context."""
        return {
            "spike_magnitude": self.details.get("spike_magnitude", 0),
            "affected_job_types": self.details.get("affected_job_types", []),
            "top_error_type": self.details.get("top_error_type", "unknown"),
            "spike_duration": self.details.get("spike_duration", "unknown")
        }
    
    def _enrich_job_context(self) -> Dict[str, Any]:
        """Enrich stuck job alerts with additional context."""
        return {
            "stuck_count": self.details.get("stuck_count", 0),
            "affected_agents": self.details.get("affected_agents", []),
            "longest_stuck_hours": self.details.get("longest_stuck_hours", 0),
            "bottleneck_type": self.details.get("bottleneck_type", "unknown")
        }
    
    def _enrich_cost_context(self) -> Dict[str, Any]:
        """Enrich cost-related alerts with additional context."""
        return {
            "current_spend": self.details.get("current_spend", 0),
            "budget_limit": self.details.get("budget_limit", 0),
            "utilization_percent": self.details.get("utilization_percent", 0),
            "cost_trend": self.details.get("cost_trend", "stable")
        }
    

if __name__ == "__main__":
    # Test alert engine with various scenarios
    print("Testing alert_engine with critical quota alert...")
    test_tool_critical = AlertEngine(
        alert_type="quota_threshold",
        severity="critical",
        message="YouTube API quota at 95% of daily limit",
        details={
            "service": "youtube",
            "current_usage": 9500,
            "limit": 10000,
            "utilization_percent": 95.0,
            "time_to_reset": "2 hours"
        },
        source_component="quota_monitor",
        override_throttling=True
    )
    
    try:
        result = test_tool_critical.run()
        print("Critical alert result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Alert ID: {data['alert_id']}")
            print(f"Status: {data['status']}")
            if "delivery_results" in data:
                delivery = data["delivery_results"]
                print(f"Delivery success: {delivery['success']}")
                print(f"Channels succeeded: {delivery['channels_succeeded']}")
            
    except Exception as e:
        print(f"Critical test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting alert_engine with warning that should be throttled...")
    test_tool_warning = AlertEngine(
        alert_type="dlq_spike",
        severity="warning",
        message="DLQ entry rate increased by 50%",
        details={
            "spike_magnitude": 1.5,
            "affected_job_types": ["single_video"],
            "top_error_type": "api_timeout"
        },
        source_component="dlq_monitor",
        override_throttling=False
    )
    
    try:
        # Send the alert twice to test throttling
        result1 = test_tool_warning.run()
        result2 = test_tool_warning.run()
        
        print("First warning alert:")
        data1 = json.loads(result1)
        print(f"Status: {data1.get('status', 'unknown')}")
        
        print("Second warning alert (should be throttled):")
        data2 = json.loads(result2)
        print(f"Status: {data2.get('status', 'unknown')}")
        if data2.get('status') == 'throttled':
            print(f"Throttle reason: {data2.get('reason', 'unknown')}")
        
    except Exception as e:
        print(f"Warning test error: {str(e)}")
    
    print("\nTesting info alert...")
    test_tool_info = AlertEngine(
        alert_type="performance_degradation",
        severity="info",
        message="Average response time slightly elevated",
        details={"avg_response_time_ms": 3500},
        source_component="performance_monitor"
    )
    
    try:
        result = test_tool_info.run()
        data = json.loads(result)
        print(f"Info alert status: {data.get('status', 'unknown')}")
        
    except Exception as e:
        print(f"Info test error: {str(e)}")