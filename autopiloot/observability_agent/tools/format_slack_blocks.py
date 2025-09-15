import json
from typing import List, Dict, Any
from pydantic import Field
from agency_swarm.tools import BaseTool


class FormatSlackBlocks(BaseTool):
    """
    Create formatted Slack block layouts for rich messaging.
    Generates structured JSON blocks for better visual presentation according to TASK-AST-0040 specifications.
    """
    
    items: Dict[str, Any] = Field(
        ..., 
        description="Dictionary containing data to format into Slack blocks with various fields and context"
    )
    alert_type: str = Field(
        default="info", 
        description="Type of alert: 'info', 'warning', 'error', 'budget', 'success'"
    )
    
    def run(self) -> str:
        """
        Generate Slack blocks JSON for rich message formatting per TASK-AST-0040 specifications.
        
        Returns:
            JSON string containing formatted Slack blocks structure
        """
        try:
            # Determine alert styling based on type
            alert_config = {
                "info": {"emoji": "ℹ️", "color": "#36a64f", "title": "Information"},
                "warning": {"emoji": "⚠️", "color": "#ffcc00", "title": "Warning"},
                "error": {"emoji": "🚨", "color": "#ff0000", "title": "Error Alert"},
                "budget": {"emoji": "💰", "color": "#ff6600", "title": "Budget Alert"},
                "success": {"emoji": "✅", "color": "#36a64f", "title": "Success"}
            }
            
            config = alert_config.get(self.alert_type, alert_config["info"])
            
            # Create header with emoji and title
            title = self.items.get("title", config["title"])
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{config['emoji']} {title}"
                    }
                }
            ]
            
            # Add main content section
            if "message" in self.items:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.items["message"]
                    }
                })
            
            # Add fields section if provided
            if "fields" in self.items and self.items["fields"]:
                fields_block = {
                    "type": "section",
                    "fields": []
                }
                
                for field_name, field_value in self.items["fields"].items():
                    field_text = {
                        "type": "mrkdwn",
                        "text": f"*{field_name}:*\n{field_value}"
                    }
                    fields_block["fields"].append(field_text)
                
                blocks.append(fields_block)
            
            # Add divider
            blocks.append({"type": "divider"})
            
            # Add context footer with timestamp
            context_elements = []
            
            if "timestamp" in self.items:
                context_elements.append({
                    "type": "mrkdwn",
                    "text": f"🕒 {self.items['timestamp']}"
                })
            
            if "component" in self.items:
                context_elements.append({
                    "type": "mrkdwn",
                    "text": f"📍 {self.items['component']}"
                })
            
            if context_elements:
                blocks.append({
                    "type": "context",
                    "elements": context_elements
                })
            
            # Return formatted blocks as JSON string
            result = {"blocks": blocks}
            return json.dumps(result, indent=2)
            
        except Exception as e:
            raise RuntimeError(f"Failed to format Slack blocks: {str(e)}")


if __name__ == "__main__":
    # Test the tool with budget alert
    tool = FormatSlackBlocks(
        items={
            "title": "Budget Alert",
            "message": "Transcription budget threshold reached",
            "fields": {
                "Daily Budget": "$5.00",
                "Amount Spent": "$4.10",
                "Usage": "82%",
                "Remaining": "$0.90"
            },
            "timestamp": "2025-09-15T14:30:00Z",
            "component": "MonitorTranscriptionBudget"
        },
        alert_type="budget"
    )
    
    try:
        result = tool.run()
        print("FormatSlackBlocks test result:")
        print(result)
        
        # Test with error alert
        error_tool = FormatSlackBlocks(
            items={
                "title": "Transcription Failed",
                "message": "AssemblyAI job failed after 3 retry attempts",
                "fields": {
                    "Video ID": "xyz123",
                    "Error": "API timeout",
                    "Attempts": "3/3"
                },
                "timestamp": "2025-09-15T14:45:00Z",
                "component": "TranscriberAgent"
            },
            alert_type="error"
        )
        
        error_result = error_tool.run()
        print("\nError alert test result:")
        print(error_result)
        
    except Exception as e:
        print(f"Test error: {str(e)}")

