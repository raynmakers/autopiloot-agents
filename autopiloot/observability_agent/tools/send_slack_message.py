import os
import json
import sys
from typing import Optional, Dict, List
from pydantic import Field
from slack_sdk import WebClient
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, get_optional_env_var
from loader import load_app_config, get_config_value


class SendSlackMessage(BaseTool):
    """
    Send notifications to Slack for status updates and alerts according to TASK-AST-0040 specifications.
    Uses configured Slack channel from settings.yaml and supports both simple text and rich block formatting.
    """
    
    channel: str = Field(
        ..., 
        description="Slack channel ID or name to post message to"
    )
    blocks: Dict[str, List[Dict]] = Field(
        ..., 
        description="Slack blocks dictionary containing formatted blocks array for rich messaging"
    )
    
    def run(self) -> str:
        """
        Send message to Slack with rich block formatting per TASK-AST-0040 specifications.
        
        Returns:
            JSON string containing ts (timestamp) and channel as per SendSlackMessageResponse interface
        """
        try:
            # Get Slack API token from environment
            slack_token = get_required_env_var("SLACK_BOT_TOKEN", "Slack Bot Token for API access")
            
            # Load configuration to get default channel if needed
            try:
                config = load_app_config()
                default_channel = get_config_value("notifications.slack.channel", config)
                if default_channel and not self.channel.startswith('#'):
                    # Ensure channel has # prefix
                    default_channel = f"#{default_channel}" if not default_channel.startswith('#') else default_channel
            except Exception:
                # Fallback if config loading fails
                default_channel = "#ops-autopiloot"
            
            # Use provided channel or fall back to configured default
            target_channel = self.channel if self.channel else default_channel
            
            # Initialize Slack client
            client = WebClient(token=slack_token)
            
            # Prepare message payload with blocks
            payload = {
                "channel": target_channel,
                "blocks": self.blocks.get("blocks", [])
            }
            
            # Add fallback text for notifications
            if payload["blocks"]:
                # Extract text from blocks for fallback
                fallback_text = "Autopiloot Alert"
                for block in payload["blocks"]:
                    if block.get("type") == "header" and "text" in block:
                        fallback_text = block["text"].get("text", fallback_text)
                        break
                payload["text"] = fallback_text
            
            # Send message to Slack
            response = client.chat_postMessage(**payload)
            
            if not response["ok"]:
                raise RuntimeError(f"Slack API error: {response.get('error', 'Unknown error')}")
            
            # Return response matching SendSlackMessageResponse TypedDict
            result = {
                "ts": response.get("ts"),
                "channel": target_channel
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to send Slack message: {str(e)}",
                "ts": None,
                "channel": self.channel or "unknown"
            })


if __name__ == "__main__":
    # Test the tool with block formatting
    from format_slack_blocks import FormatSlackBlocks
    
    # First create formatted blocks
    formatter = FormatSlackBlocks(
        items={
            "title": "Test Alert",
            "message": "Testing Slack message functionality",
            "fields": {
                "Status": "OK",
                "Component": "SendSlackMessage"
            },
            "timestamp": "2025-09-15T15:00:00Z"
        },
        alert_type="info"
    )
    
    try:
        blocks_json = formatter.run()
        blocks_data = json.loads(blocks_json)
        
        # Test sending the message
        tool = SendSlackMessage(
            channel="#test-autopiloot",
            blocks=blocks_data
        )
        
        result = tool.run()
        print("SendSlackMessage test result:")
        print(result)
        
        # Parse result to verify structure
        data = json.loads(result)
        if "error" in data:
            print(f"Test failed: {data['error']}")
        else:
            print(f"Message sent successfully to {data['channel']} at {data['ts']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()

