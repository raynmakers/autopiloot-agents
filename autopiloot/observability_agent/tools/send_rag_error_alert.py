"""
SendRagErrorAlert tool for sending Slack notifications when RAG ingestion operations fail.
Provides visibility into Zep, OpenSearch, and BigQuery ingestion failures.

Alert Types:
- Zep upsert failures (semantic search)
- OpenSearch indexing failures (keyword search)
- BigQuery streaming failures (SQL analytics)
- Hybrid retrieval failures
"""

import os
import sys
import json
from typing import Optional, Dict
from pydantic import Field
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import load_environment
from loader import load_app_config, get_config_value
from audit_logger import audit_logger


class SendRagErrorAlert(BaseTool):
    """
    Send Slack alert when RAG ingestion operations fail.

    Implements:
    - Formatted Slack notifications for RAG failures
    - Contextual error information (video, operation, system)
    - Integration with alert throttling system
    - Audit logging for compliance
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID where error occurred"
    )
    operation: str = Field(
        ...,
        description="RAG operation that failed: 'zep_upsert', 'opensearch_index', 'bigquery_stream', 'hybrid_retrieval'"
    )
    storage_system: str = Field(
        ...,
        description="Storage system involved: 'zep', 'opensearch', 'bigquery', 'hybrid'"
    )
    error_message: str = Field(
        ...,
        description="Error message describing the failure"
    )
    error_type: str = Field(
        default="unknown",
        description="Error type: 'connection', 'authentication', 'quota', 'validation', 'timeout', 'unknown'"
    )
    video_title: Optional[str] = Field(
        default=None,
        description="Video title for context"
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="YouTube channel ID"
    )
    additional_context: Optional[Dict] = Field(
        default=None,
        description="Additional context (chunk count, tokens, etc.)"
    )

    def run(self) -> str:
        """
        Send formatted Slack alert for RAG ingestion failure.

        Process:
        1. Load Slack configuration from settings.yaml
        2. Format error alert with contextual information
        3. Send to configured Slack channel
        4. Log alert to audit trail
        5. Return alert delivery status

        Returns:
            JSON string with alert delivery status and timestamp
        """
        try:
            # Load environment
            load_environment()

            # Import Slack tools
            from .format_slack_blocks import FormatSlackBlocks
            from .send_slack_message import SendSlackMessage

            # Load Slack configuration
            config = load_app_config()
            slack_channel = get_config_value("notifications.slack.channel", config, default="ops-autopiloot")

            # Ensure channel has # prefix
            if not slack_channel.startswith('#'):
                slack_channel = f"#{slack_channel}"

            print(f"⚠️ Sending RAG error alert...")
            print(f"   Video: {self.video_id}")
            print(f"   Operation: {self.operation}")
            print(f"   System: {self.storage_system}")
            print(f"   Error: {self.error_message[:100]}...")

            # Build alert fields
            fields = {
                "Video ID": self.video_id,
                "Operation": self.operation,
                "Storage System": self.storage_system.upper(),
                "Error Type": self.error_type
            }

            if self.video_title:
                fields["Video Title"] = self.video_title
            if self.channel_id:
                fields["Channel ID"] = self.channel_id

            # Add additional context if provided
            if self.additional_context:
                if 'chunk_count' in self.additional_context:
                    fields["Chunks"] = str(self.additional_context['chunk_count'])
                if 'tokens_processed' in self.additional_context:
                    fields["Tokens"] = str(self.additional_context['tokens_processed'])

            # Format alert items
            alert_items = {
                "title": f"RAG Ingestion Failure: {self.storage_system.upper()}",
                "message": f"Failed to ingest video transcript to {self.storage_system}.\n\n**Error**: {self.error_message}",
                "fields": fields,
                "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "component": "RAG Ingestion Pipeline",
                "severity": "high"
            }

            # Format Slack blocks
            formatter = FormatSlackBlocks(items=alert_items, alert_type="error")
            blocks_json = formatter.run()
            blocks_data = json.loads(blocks_json)

            # Send to Slack
            messenger = SendSlackMessage(channel=slack_channel, blocks=blocks_data)
            message_result = messenger.run()

            # Check if message was sent successfully
            message_data = json.loads(message_result)
            success = "error" not in message_data and message_data.get("ts") is not None

            if success:
                print(f"   ✓ Alert sent to {slack_channel}")

                # Log alert to audit trail
                audit_logger.log_error_alert(
                    error_type=f"rag_{self.operation}",
                    video_id=self.video_id,
                    message=self.error_message,
                    context={
                        "operation": self.operation,
                        "storage_system": self.storage_system,
                        "error_type": self.error_type
                    },
                    actor="ObservabilityAgent"
                )

                return json.dumps({
                    "video_id": self.video_id,
                    "operation": self.operation,
                    "storage_system": self.storage_system,
                    "alert_sent": True,
                    "channel": slack_channel,
                    "timestamp": message_data.get("ts"),
                    "status": "success"
                }, indent=2)
            else:
                error_msg = message_data.get("error", "Unknown error")
                print(f"   ⚠️ Failed to send alert: {error_msg}")

                return json.dumps({
                    "video_id": self.video_id,
                    "operation": self.operation,
                    "alert_sent": False,
                    "error": error_msg,
                    "status": "failed"
                })

        except Exception as e:
            return json.dumps({
                "error": "alert_failed",
                "message": f"Failed to send RAG error alert: {str(e)}",
                "video_id": self.video_id,
                "operation": self.operation
            })


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Send RAG Error Alert")
    print("="*80)

    try:
        tool = SendRagErrorAlert(
            video_id="test_mZxDw92UXmA",
            operation="zep_upsert",
            storage_system="zep",
            error_message="Connection timeout after 30s: Failed to connect to Zep API at https://api.getzep.com",
            error_type="timeout",
            video_title="How to Build a Scalable SaaS Business - Dan Martell",
            channel_id="UCkP5J0pXI11VE81q7S7V1Jw",
            additional_context={
                "chunk_count": 12,
                "tokens_processed": 5000
            }
        )

        result = tool.run()
        print("✅ Test completed:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
        else:
            print(f"\n📨 Alert Summary:")
            print(f"   Alert Sent: {data.get('alert_sent', False)}")
            print(f"   Channel: {data.get('channel', 'N/A')}")
            print(f"   Status: {data.get('status', 'unknown')}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
