import json
from typing import List, Dict, Any
from pydantic import Field
from agency_swarm.tools import BaseTool


class FormatSlackBlocks(BaseTool):
    """
    Create formatted Slack block layouts for rich messaging.
    Generates structured JSON blocks for better visual presentation.
    """
    
    title: str = Field(
        ..., 
        description="Main title for the Slack message block"
    )
    fields: List[Dict[str, str]] = Field(
        ..., 
        description="List of field dictionaries with 'name' and 'value' keys"
    )
    color: str = Field(
        default="good", 
        description="Block color: 'good' (green), 'warning' (yellow), 'danger' (red), or hex code"
    )
    
    def run(self) -> str:
        """
        Generate Slack blocks JSON for rich message formatting.
        
        Returns:
            JSON string containing formatted Slack blocks structure
        """
        try:
            # Create header section
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": self.title
                    }
                }
            ]
            
            # Add fields section if provided
            if self.fields:
                fields_block = {
                    "type": "section",
                    "fields": []
                }
                
                for field in self.fields:
                    field_text = {
                        "type": "mrkdwn",
                        "text": f"*{field.get('name', 'Field')}:*\n{field.get('value', 'N/A')}"
                    }
                    fields_block["fields"].append(field_text)
                
                blocks.append(fields_block)
            
            # Add color divider
            color_map = {
                "good": "#36a64f",
                "warning": "#ffcc00", 
                "danger": "#ff0000"
            }
            
            block_color = color_map.get(self.color, self.color)
            
            # Add divider with color context
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Status: {self.color.upper()}"
                    }
                ]
            })
            
            return json.dumps(blocks, indent=2)
            
        except Exception as e:
            raise RuntimeError(f"Failed to format Slack blocks: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = FormatSlackBlocks(
        title="Daily Processing Summary",
        fields=[
            {"name": "Videos Processed", "value": "3"},
            {"name": "Transcriptions", "value": "2 completed"},
            {"name": "Budget Used", "value": "$1.30 / $5.00"}
        ],
        color="good"
    )
    
    try:
        result = tool.run()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")