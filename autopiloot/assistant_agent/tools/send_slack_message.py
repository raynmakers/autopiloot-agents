import os
import json
from typing import Optional
from pydantic import Field
from slack_sdk import WebClient
from agency_swarm.tools import BaseTool


class SendSlackMessage(BaseTool):
    """
    Send notifications to Slack for status updates and alerts.
    Supports both simple text and rich block formatting.
    """
    
    message: str = Field(
        ..., 
        description="Message text to send to Slack channel"
    )
    channel: Optional[str] = Field(
        default=None, 
        description="Slack channel ID or name (defaults to configured channel)"
    )
    blocks: Optional[str] = Field(
        default=None, 
        description="Optional JSON string of Slack blocks for rich formatting"
    )
    
    def run(self) -> str:
        """
        Send message to Slack with optional rich formatting.
        
        Returns:
            JSON string with message_sent status and timestamp
        """
        # Validate required environment variables
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        default_channel = os.getenv("SLACK_CHANNEL", "#autopiloot")
        
        if not slack_token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")
        
        channel = self.channel or default_channel
        
        try:
            # Initialize Slack client
            client = WebClient(token=slack_token)
            
            # Prepare message payload
            payload = {
                "channel": channel,
                "text": self.message
            }
            
            # Add blocks if provided
            if self.blocks:
                try:
                    blocks_data = json.loads(self.blocks)
                    payload["blocks"] = blocks_data
                except json.JSONDecodeError:
                    # If blocks parsing fails, send as plain text
                    pass
            
            # Send message
            response = client.chat_postMessage(**payload)
            
            result = {
                "message_sent": response["ok"],
                "timestamp": response.get("ts"),
                "channel": channel,
                "message_length": len(self.message)
            }
            
            return json.dumps(result)
            
        except Exception as e:
            raise RuntimeError(f"Failed to send Slack message: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = SendSlackMessage(
        message="Test notification from Autopiloot Agency",
        channel="#test"
    )
    
    try:
        result = tool.run()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")