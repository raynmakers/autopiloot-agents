import os
import json
from typing import Optional
from pydantic import Field
from slack_sdk import WebClient
from datetime import datetime
from agency_swarm.tools import BaseTool


class SendErrorAlert(BaseTool):
    """
    Send critical error alerts to Slack for immediate attention.
    Formats error messages with context and urgency indicators.
    """
    
    error_message: str = Field(
        ..., 
        description="Error message or exception details to alert about"
    )
    component: str = Field(
        ..., 
        description="System component where error occurred (e.g., 'ScraperAgent', 'TranscriberAgent')"
    )
    severity: str = Field(
        default="HIGH", 
        description="Error severity level: LOW, MEDIUM, HIGH, CRITICAL"
    )
    context: Optional[str] = Field(
        default=None, 
        description="Additional context or data related to the error"
    )
    
    def run(self) -> str:
        """
        Send formatted error alert to Slack with urgency indicators.
        
        Returns:
            JSON string with alert_sent status and timestamp
        """
        # Validate required environment variables
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        alerts_channel = os.getenv("SLACK_ALERTS_CHANNEL", "#autopiloot-alerts")
        
        if not slack_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")
        
        try:
            # Initialize Slack client
            client = WebClient(token=slack_token)
            
            # Format error alert message
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            # Set emoji and formatting based on severity
            severity_emojis = {
                "LOW": "🟡",
                "MEDIUM": "🟠", 
                "HIGH": "🔴",
                "CRITICAL": "🚨"
            }
            
            emoji = severity_emojis.get(self.severity, "⚠️")
            
            # Create formatted message
            alert_text = f"{emoji} **{self.severity} ERROR ALERT** {emoji}\n\n"
            alert_text += f"**Component:** {self.component}\n"
            alert_text += f"**Time:** {timestamp}\n"
            alert_text += f"**Error:** {self.error_message}\n"
            
            if self.context:
                alert_text += f"**Context:** {self.context}\n"
            
            alert_text += "\n_Please investigate immediately._"
            
            # Send alert
            response = client.chat_postMessage(
                channel=alerts_channel,
                text=alert_text,
                username="Autopiloot Alert Bot",
                icon_emoji=emoji
            )
            
            result = {
                "alert_sent": response["ok"],
                "timestamp": response.get("ts"),
                "channel": alerts_channel,
                "severity": self.severity,
                "component": self.component
            }
            
            return json.dumps(result)
            
        except Exception as e:
            raise RuntimeError(f"Failed to send error alert: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = SendErrorAlert(
        error_message="YouTube API quota exceeded",
        component="ScraperAgent",
        severity="HIGH",
        context="Daily quota of 10,000 requests reached at 2:30 PM"
    )
    
    try:
        result = tool.run()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")