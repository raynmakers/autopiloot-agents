import os
import json
import sys
from typing import Dict, Any
from pydantic import Field
from datetime import datetime, timezone, timedelta
from google.cloud import firestore
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var
from loader import load_app_config, get_config_value
from audit_logger import audit_logger


class SendErrorAlert(BaseTool):
    """
    Send critical error alerts to Slack with throttling per TASK-AST-0040 requirements.
    Implements 1 alert per type per hour throttling policy and formats alerts with context.
    """
    
    message: str = Field(
        ..., 
        description="Error message or exception details to alert about"
    )
    context: Dict[str, Any] = Field(
        ..., 
        description="Dictionary containing additional context or data related to the error"
    )
    
    def run(self) -> str:
        """
        Send formatted error alert to Slack with throttling per TASK-AST-0040 requirements.
        
        Returns:
            JSON string with status message as per task specification
        """
        try:
            # Extract alert type and component from context
            alert_type = self.context.get("type", "error")
            component = self.context.get("component", "Unknown")
            severity = self.context.get("severity", "HIGH")
            
            # Check throttling before sending (1 alert per type per hour per TASK-AST-0040)
            if not self._should_send_alert(alert_type):
                return json.dumps({
                    "status": "THROTTLED",
                    "message": f"Alert throttled: {alert_type} already sent within last hour",
                    "alert_type": alert_type,
                    "throttle_remaining": "< 1 hour"
                })
            
            # Load configuration
            config = load_app_config()
            slack_channel = get_config_value("notifications.slack.channel", config, default="ops-autopiloot")
            
            # Ensure channel has # prefix
            if not slack_channel.startswith('#'):
                slack_channel = f"#{slack_channel}"
            
            # Format alert items for Slack blocks
            alert_items = {
                "title": f"{severity} Error Alert",
                "message": self.message,
                "fields": {
                    "Component": component,
                    "Severity": severity,
                    "Alert Type": alert_type
                },
                "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "component": component
            }
            
            # Add additional context fields
            for key, value in self.context.items():
                if key not in ["type", "component", "severity"]:
                    alert_items["fields"][key.replace("_", " ").title()] = str(value)
            
            # Send alert using existing tools
            success = self._send_slack_alert(slack_channel, alert_items, severity)
            
            if success:
                # Record alert in throttling system
                self._record_alert_sent(alert_type)
                
                # Log error alert to audit trail (TASK-AUDIT-0041)
                audit_logger.write_audit_log(
                    actor="AssistantAgent",
                    action="error_alert_sent",
                    entity="slack_alert",
                    entity_id=alert_type,
                    details={
                        "alert_type": alert_type,
                        "component": component,
                        "severity": severity,
                        "channel": slack_channel
                    }
                )
                
                return json.dumps({
                    "status": "SENT",
                    "message": f"Error alert sent successfully for {alert_type}",
                    "alert_type": alert_type,
                    "component": component,
                    "channel": slack_channel
                })
            else:
                return json.dumps({
                    "status": "FAILED",
                    "message": "Failed to send error alert to Slack",
                    "alert_type": alert_type,
                    "component": component
                })
                
        except Exception as e:
            return json.dumps({
                "error": f"Failed to send error alert: {str(e)}",
                "status": "ERROR"
            })
    
    def _should_send_alert(self, alert_type: str) -> bool:
        """Check if alert should be sent based on throttling policy (1 per type per hour)."""
        try:
            # Get Firestore client
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore access")
            db = firestore.Client(project=project_id)
            
            # Check alert throttling collection
            throttle_doc_ref = db.collection('alert_throttling').document(alert_type)
            throttle_doc = throttle_doc_ref.get()
            
            if not throttle_doc.exists:
                return True  # No previous alert recorded
            
            throttle_data = throttle_doc.to_dict()
            last_sent = throttle_data.get('last_sent')
            
            if not last_sent:
                return True
            
            # Parse timestamp and check if more than 1 hour has passed
            if isinstance(last_sent, str):
                last_sent = datetime.fromisoformat(last_sent.replace('Z', '+00:00'))
            
            time_diff = datetime.now(timezone.utc) - last_sent
            return time_diff >= timedelta(hours=1)
            
        except Exception as e:
            print(f"Warning: Throttling check failed, allowing alert: {str(e)}")
            return True  # Allow alert if throttling check fails
    
    def _record_alert_sent(self, alert_type: str) -> None:
        """Record that an alert was sent for throttling purposes."""
        try:
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore access")
            db = firestore.Client(project=project_id)
            
            # Update throttling record
            throttle_doc_ref = db.collection('alert_throttling').document(alert_type)
            throttle_doc_ref.set({
                'alert_type': alert_type,
                'last_sent': datetime.now(timezone.utc),
                'count': firestore.Increment(1)
            }, merge=True)
            
        except Exception as e:
            print(f"Warning: Failed to record alert throttling: {str(e)}")
    
    def _send_slack_alert(self, channel: str, alert_items: Dict[str, Any], severity: str) -> bool:
        """Send alert to Slack using FormatSlackBlocks and SendSlackMessage tools."""
        try:
            from .format_slack_blocks import FormatSlackBlocks
            from .send_slack_message import SendSlackMessage
            
            # Determine alert type based on severity
            alert_type_map = {
                "LOW": "warning",
                "MEDIUM": "warning",
                "HIGH": "error",
                "CRITICAL": "error"
            }
            
            alert_type = alert_type_map.get(severity, "error")
            
            # Format blocks
            formatter = FormatSlackBlocks(items=alert_items, alert_type=alert_type)
            blocks_json = formatter.run()
            blocks_data = json.loads(blocks_json)
            
            # Send to Slack
            messenger = SendSlackMessage(channel=channel, blocks=blocks_data)
            message_result = messenger.run()
            
            # Check if message was sent successfully
            message_data = json.loads(message_result)
            return "error" not in message_data and message_data.get("ts") is not None
            
        except Exception as e:
            print(f"Warning: Failed to send Slack alert: {str(e)}")
            return False


if __name__ == "__main__":
    # Test the tool with different error scenarios
    
    # Test 1: API quota error
    tool1 = SendErrorAlert(
        message="YouTube API quota exceeded",
        context={
            "type": "api_quota",
            "component": "ScraperAgent",
            "severity": "HIGH",
            "quota_used": 10000,
            "time_occurred": "2025-09-15T14:30:00Z",
            "affected_videos": 5
        }
    )
    
    try:
        result1 = tool1.run()
        print("SendErrorAlert test result 1 (API Quota):")
        print(result1)
        
        # Parse result
        data1 = json.loads(result1)
        print(f"Status: {data1.get('status')}")
        
    except Exception as e:
        print(f"Test 1 error: {str(e)}")
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: Transcription failure
    tool2 = SendErrorAlert(
        message="AssemblyAI transcription job failed after maximum retries",
        context={
            "type": "transcription_failure",
            "component": "TranscriberAgent",
            "severity": "CRITICAL",
            "video_id": "xyz123",
            "retry_attempts": 3,
            "error_code": "timeout",
            "job_id": "abc456"
        }
    )
    
    try:
        result2 = tool2.run()
        print("SendErrorAlert test result 2 (Transcription Failure):")
        print(result2)
        
        # Parse result
        data2 = json.loads(result2)
        print(f"Status: {data2.get('status')}")
        
    except Exception as e:
        print(f"Test 2 error: {str(e)}")
    
    print("\n" + "="*50 + "\n")
    
    # Test 3: Test throttling (same alert type as test 1)
    tool3 = SendErrorAlert(
        message="Another API quota issue",
        context={
            "type": "api_quota",  # Same type as test 1
            "component": "SummarizerAgent", 
            "severity": "MEDIUM"
        }
    )
    
    try:
        result3 = tool3.run()
        print("SendErrorAlert test result 3 (Should be throttled):")
        print(result3)
        
        # Parse result
        data3 = json.loads(result3)
        print(f"Status: {data3.get('status')}")
        
    except Exception as e:
        print(f"Test 3 error: {str(e)}")