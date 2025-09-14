import os
import json
from typing import Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class SendErrorAlert(BaseTool):
    def __init__(self):
        super().__init__()
        self.client = WebClient(token=self.slack_token) if self.slack_token else None
    
    def _validate_env_vars(self):
        self.slack_token = self.get_env_var("SLACK_BOT_TOKEN", required=False)
        self.slack_channel = self.get_env_var("SLACK_ALERTS_CHANNEL", required=False) or "#alerts"
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        message = request.get('message', '')
        context = request.get('context', {})
        
        if not message:
            raise ValueError("message is required")
        
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚨 Error Alert",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:* {message}"
                    }
                }
            ]
            
            if context:
                fields = []
                for key, value in context.items():
                    if len(fields) < 10:
                        value_str = str(value)[:100]
                        fields.append({
                            "type": "mrkdwn",
                            "text": f"*{key}:*\n{value_str}"
                        })
                
                if fields:
                    blocks.append({
                        "type": "section",
                        "fields": fields
                    })
            
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Timestamp: {datetime.utcnow().isoformat()}Z"
                    }
                ]
            })
            
            if self.client:
                try:
                    response = self.client.chat_postMessage(
                        channel=self.slack_channel,
                        blocks=blocks,
                        unfurl_links=False,
                        unfurl_media=False
                    )
                    
                    return {
                        "status": "alert_sent",
                        "channel": response['channel'],
                        "timestamp": response['ts']
                    }
                except SlackApiError as e:
                    print(f"Failed to send Slack error alert: {e.response['error']}")
                    return {
                        "status": "alert_failed",
                        "error": e.response['error']
                    }
            else:
                print(f"Error Alert (Slack not configured): {message}")
                if context:
                    print(f"Context: {json.dumps(context, indent=2)}")
                
                return {
                    "status": "logged_only",
                    "message": "Slack not configured, error logged to console"
                }
            
        except Exception as e:
            raise RuntimeError(f"Failed to send error alert: {str(e)}")


if __name__ == "__main__":
    tool = SendErrorAlert()
    
    test_request = {
        "message": "Test error: Failed to process video",
        "context": {
            "video_id": "test_video_123",
            "error_type": "TranscriptionError",
            "agent": "Transcriber",
            "duration": "120s"
        }
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {result['status']}")
        if result.get('channel'):
            print(f"Sent to channel: {result['channel']}")
    except Exception as e:
        print(f"Error: {str(e)}")