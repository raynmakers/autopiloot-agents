import os
import json
from typing import Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class SendSlackMessage(BaseTool):
    def __init__(self):
        super().__init__()
        self.client = WebClient(token=self.slack_token)
    
    def _validate_env_vars(self):
        self.slack_token = self.get_env_var("SLACK_BOT_TOKEN")
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        channel = request.get('channel', '')
        blocks = request.get('blocks', [])
        
        if not channel:
            raise ValueError("channel is required")
        if not blocks:
            raise ValueError("blocks is required")
        
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                unfurl_links=False,
                unfurl_media=False
            )
            
            return {
                "ts": response['ts'],
                "channel": response['channel']
            }
            
        except SlackApiError as e:
            if e.response['error'] == 'channel_not_found':
                raise ValueError(f"Channel {channel} not found")
            elif e.response['error'] == 'not_in_channel':
                raise ValueError(f"Bot is not in channel {channel}")
            elif e.response['error'] == 'invalid_blocks':
                raise ValueError("Invalid Slack blocks format")
            else:
                raise RuntimeError(f"Slack API error: {e.response['error']}")
        except Exception as e:
            raise RuntimeError(f"Failed to send Slack message: {str(e)}")


if __name__ == "__main__":
    tool = SendSlackMessage()
    
    test_request = {
        "channel": os.getenv("SLACK_CHANNEL", "#general"),
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Test message from Autopiloot"
                }
            }
        ]
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: Message sent to {result['channel']} at {result['ts']}")
    except Exception as e:
        print(f"Error: {str(e)}")