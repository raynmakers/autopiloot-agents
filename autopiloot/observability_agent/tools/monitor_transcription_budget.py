import os
import json
import sys
from typing import Optional
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool

# Add core and config directories to path
from env_loader import get_required_env_var
from loader import load_app_config, get_config_value
from audit_logger import audit_logger


class MonitorTranscriptionBudget(BaseTool):
    """
    Monitor daily transcription spending against configured budget limit from settings.yaml.
    Implements TASK-AST-0040 requirements with 80% threshold alerting and Slack notifications.
    """
    
    date: str = Field(
        ..., 
        description="Date to monitor in YYYY-MM-DD format (UTC)"
    )
    
    def run(self) -> str:
        """
        Check daily transcription spending and send alerts per TASK-AST-0040 requirements.
        
        Returns:
            JSON string with status and total_usd as per BudgetMonitorResponse interface
        """
        try:
            # Get project ID and initialize Firestore
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore access")
            db = firestore.Client(project=project_id)
            
            # Load budget configuration from settings.yaml
            config = load_app_config()
            daily_limit = get_config_value("budgets.transcription_daily_usd", config, default=5.0)
            
            # Parse the date and create start/end timestamps
            try:
                target_date = datetime.strptime(self.date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                next_date = target_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise ValueError(f"Invalid date format: {self.date}. Expected YYYY-MM-DD")
            
            # Query transcripts and costs for the specified date
            daily_spent = 0.0
            transcript_count = 0
            
            # Check costs_daily collection first for efficiency
            costs_doc_ref = db.collection('costs_daily').document(self.date)
            costs_doc = costs_doc_ref.get()
            
            if costs_doc.exists:
                costs_data = costs_doc.to_dict()
                daily_spent = costs_data.get('transcription_usd', 0.0)
                transcript_count = costs_data.get('transcript_count', 0)
            else:
                # Fallback to querying transcripts collection
                transcripts_ref = db.collection('transcripts')
                day_transcripts = transcripts_ref.where(
                    'created_at', '>=', target_date
                ).where(
                    'created_at', '<=', next_date
                ).stream()
                
                for transcript in day_transcripts:
                    transcript_data = transcript.to_dict()
                    costs = transcript_data.get('costs', {})
                    transcription_cost = costs.get('transcription_usd', 0.0)
                    daily_spent += float(transcription_cost)
                    transcript_count += 1
            
            # Calculate usage percentage and determine status
            usage_percentage = (daily_spent / daily_limit) * 100 if daily_limit > 0 else 0
            
            # Determine status based on TASK-AST-0040 requirements (80% threshold)
            if usage_percentage >= 100:
                status = "EXCEEDED"
                should_alert = True
            elif usage_percentage >= 80:  # TASK-AST-0040 specified 80% alert threshold
                status = "THRESHOLD_REACHED"
                should_alert = True
            elif usage_percentage >= 70:
                status = "WARNING"
                should_alert = False
            else:
                status = "OK"
                should_alert = False
            
            # Send Slack alert if threshold reached (80% or more)
            alert_sent = False
            if should_alert:
                alert_sent = self._send_budget_alert(daily_spent, daily_limit, usage_percentage, self.date)
            
            # Return result matching BudgetMonitorResponse interface
            result = {
                "status": status,
                "total_usd": round(daily_spent, 4),
                "daily_limit": daily_limit,
                "usage_percentage": round(usage_percentage, 1),
                "transcript_count": transcript_count,
                "alert_sent": alert_sent,
                "date": self.date
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to monitor transcription budget: {str(e)}",
                "status": "ERROR",
                "total_usd": 0.0
            })
    
    def _send_budget_alert(self, spent: float, limit: float, percentage: float, date: str) -> bool:
        """Send budget alert to Slack using configured channel."""
        try:
            # Import tools here to avoid circular dependencies
            from .format_slack_blocks import FormatSlackBlocks
            from .send_slack_message import SendSlackMessage
            
            # Load Slack channel configuration
            config = load_app_config()
            slack_channel = get_config_value("notifications.slack.channel", config, default="ops-autopiloot")
            
            # Ensure channel has # prefix
            if not slack_channel.startswith('#'):
                slack_channel = f"#{slack_channel}"
            
            # Format alert message
            alert_items = {
                "title": "Budget Threshold Alert",
                "message": f"Daily transcription budget has reached {percentage:.1f}% usage.",
                "fields": {
                    "Daily Budget": f"${limit:.2f}",
                    "Amount Spent": f"${spent:.2f}",
                    "Usage": f"{percentage:.1f}%",
                    "Remaining": f"${limit - spent:.2f}",
                    "Date": date
                },
                "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "component": "MonitorTranscriptionBudget"
            }
            
            # Format blocks
            formatter = FormatSlackBlocks(items=alert_items, alert_type="budget")
            blocks_json = formatter.run()
            blocks_data = json.loads(blocks_json)
            
            # Send to Slack
            messenger = SendSlackMessage(channel=slack_channel, blocks=blocks_data)
            message_result = messenger.run()
            
            # Check if message was sent successfully
            message_data = json.loads(message_result)
            success = "error" not in message_data and message_data.get("ts") is not None
            
            # Log budget alert to audit trail (TASK-AUDIT-0041)
            if success:
                audit_logger.log_budget_alert(
                    date=date,
                    amount_spent=spent,
                    threshold_percentage=percentage,
                    actor="ObservabilityAgent"
                )
            
            return success
            
        except Exception as e:
            print(f"Warning: Failed to send budget alert to Slack: {str(e)}")
            return False


if __name__ == "__main__":
    # Test the tool with current date
    from datetime import datetime, timezone
    
    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    tool = MonitorTranscriptionBudget(date=current_date)
    
    try:
        result = tool.run()
        print("MonitorTranscriptionBudget test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Test failed: {data['error']}")
        else:
            print(f"\nBudget Status: {data['status']}")
            print(f"Total Spent: ${data['total_usd']}")
            print(f"Usage: {data['usage_percentage']}%")
            if data.get('alert_sent'):
                print("Alert sent to Slack!")
                
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()

