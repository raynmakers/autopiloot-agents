import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import Field
from agency_swarm.tools import BaseTool

# Import centralized Slack utilities
from core.slack_utils import format_alert_blocks


class FormatSlackBlocks(BaseTool):
    """
    Create formatted Slack block layouts for rich messaging.

    UPDATED: This tool now delegates to core.slack_utils.format_alert_blocks
    for consistent formatting across the entire system. Maintains backward
    compatibility with the original interface while using the centralized utility.

    Generates structured JSON blocks for better visual presentation according to TASK-AST-0040 specifications.
    """

    items: Dict[str, Any] = Field(
        ...,
        description="Dictionary containing data to format into Slack blocks with various fields and context"
    )
    alert_type: str = Field(
        default="info",
        description="Type of alert: 'info', 'warning', 'error', 'budget', 'success', 'critical', 'dlq', 'quota', 'daily'"
    )

    def run(self) -> str:
        """
        Generate Slack blocks JSON for rich message formatting.

        Delegates to core.slack_utils.format_alert_blocks for consistent formatting.

        Returns:
            JSON string containing formatted Slack blocks structure
        """
        try:
            # Extract parameters from items dict
            title = self.items.get("title", "Alert")
            message = self.items.get("message", "")

            # Convert fields dict to details dict for centralized formatter
            details = None
            if "fields" in self.items and self.items["fields"]:
                details = self.items["fields"]

            # Parse timestamp if provided
            timestamp = None
            if "timestamp" in self.items:
                timestamp_str = self.items["timestamp"]
                try:
                    # Try parsing ISO format
                    from core.time_utils import parse_iso8601_z
                    timestamp = parse_iso8601_z(timestamp_str)
                except:
                    # Fallback to current time
                    from datetime import datetime, timezone
                    timestamp = datetime.now(timezone.utc)

            # Add component to details if provided
            if "component" in self.items:
                if details is None:
                    details = {}
                details["component"] = self.items["component"]

            # Delegate to centralized formatting utility
            blocks = format_alert_blocks(
                title=title,
                message=message,
                alert_type=self.alert_type,
                details=details,
                timestamp=timestamp
            )

            # Return formatted blocks as JSON string (maintain backward compatibility)
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

