"""
Generate Daily Digest tool for creating morning operational summaries.
Implements PRD requirement for 07:00 daily digest with comprehensive metrics and Slack delivery.
"""

import os
import sys
import json
from typing import Optional, Dict, Any, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone, timedelta
import pytz
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var
from loader import load_app_config, get_config_value
from audit_logger import audit_logger

load_dotenv()


class GenerateDailyDigest(BaseTool):
    """
    Generates comprehensive daily operational digest for morning delivery at 07:00.

    PRD requirement: "Assistant daily Slack digest at 07:00" with processing summary,
    costs, errors, and quick links to Drive folders and system status.
    """

    date: str = Field(
        ...,
        description="Date for digest in YYYY-MM-DD format (usually yesterday's date)"
    )

    timezone_name: str = Field(
        default="Europe/Amsterdam",
        description="Timezone for date calculations and scheduling"
    )

    def run(self) -> str:
        """
        Generate comprehensive daily digest with processing metrics, costs, and health status.

        Returns:
            JSON string containing digest content with Slack-formatted blocks
        """
        try:
            # Initialize Firestore client
            db = firestore.Client()
            config = load_app_config()

            # Parse date and calculate time boundaries
            target_date = datetime.strptime(self.date, "%Y-%m-%d")
            tz = pytz.timezone(self.timezone_name)

            # Calculate day boundaries in specified timezone
            day_start = tz.localize(target_date.replace(hour=0, minute=0, second=0, microsecond=0))
            day_end = day_start + timedelta(days=1)

            # Convert to UTC for Firestore queries
            day_start_utc = day_start.astimezone(timezone.utc)
            day_end_utc = day_end.astimezone(timezone.utc)

            # Collect metrics from Firestore
            metrics = self._collect_daily_metrics(db, day_start_utc, day_end_utc)

            # Generate digest content
            digest_content = self._create_digest_content(metrics, self.date, config)

            # Format as Slack blocks
            slack_blocks = self._format_slack_blocks(digest_content)

            # Audit log the digest generation
            audit_logger.log(
                actor="ObservabilityAgent",
                action="generate_daily_digest",
                entity="daily_digest",
                entity_id=self.date,
                details={
                    "metrics": metrics,
                    "timezone": self.timezone_name,
                    "blocks_count": len(slack_blocks)
                }
            )

            result = {
                "date": self.date,
                "timezone": self.timezone_name,
                "metrics": metrics,
                "digest_content": digest_content,
                "slack_blocks": slack_blocks,
                "summary": f"Daily digest generated for {self.date} with {metrics['videos_discovered']} videos processed"
            }

            return json.dumps(result, default=str)

        except Exception as e:
            error_msg = f"Failed to generate daily digest for {self.date}: {str(e)}"
            audit_logger.log(
                actor="ObservabilityAgent",
                action="generate_daily_digest_error",
                entity="daily_digest",
                entity_id=self.date,
                details={"error": error_msg}
            )
            return json.dumps({"error": "digest_generation_failed", "message": error_msg})

    def _collect_daily_metrics(self, db: firestore.Client, start_utc: datetime, end_utc: datetime) -> Dict[str, Any]:
        """Collect comprehensive metrics from Firestore for the target day."""
        metrics = {
            "videos_discovered": 0,
            "videos_transcribed": 0,
            "summaries_generated": 0,
            "total_cost_usd": 0.0,
            "budget_percentage": 0.0,
            "dlq_entries": 0,
            "failed_jobs": 0,
            "top_videos": [],
            "errors": [],
            "cost_details": {}
        }

        try:
            # Query videos discovered in the target day
            videos_ref = db.collection('videos')
            videos_query = videos_ref.where('created_at', '>=', start_utc).where('created_at', '<', end_utc)

            discovered_videos = []
            for doc in videos_query.stream():
                video_data = doc.to_dict()
                discovered_videos.append({
                    "video_id": doc.id,
                    "title": video_data.get("title", "Unknown"),
                    "status": video_data.get("status", "unknown"),
                    "duration_sec": video_data.get("duration_sec", 0),
                    "source": video_data.get("source", "unknown")
                })

            metrics["videos_discovered"] = len(discovered_videos)
            metrics["top_videos"] = sorted(discovered_videos, key=lambda x: x.get("duration_sec", 0), reverse=True)[:5]

            # Count transcriptions completed
            transcripts_ref = db.collection('transcripts')
            transcripts_query = transcripts_ref.where('created_at', '>=', start_utc).where('created_at', '<', end_utc)

            total_cost = 0.0
            for doc in transcripts_query.stream():
                transcript_data = doc.to_dict()
                metrics["videos_transcribed"] += 1
                cost = transcript_data.get("costs", {}).get("transcription_usd", 0.0)
                total_cost += cost

            metrics["total_cost_usd"] = total_cost

            # Count summaries generated
            summaries_ref = db.collection('summaries')
            summaries_query = summaries_ref.where('created_at', '>=', start_utc).where('created_at', '<', end_utc)

            for doc in summaries_query.stream():
                metrics["summaries_generated"] += 1

            # Check daily cost document
            date_str = start_utc.strftime("%Y-%m-%d")
            cost_doc_ref = db.collection('costs_daily').document(date_str)
            cost_doc = cost_doc_ref.get()

            if cost_doc.exists:
                cost_data = cost_doc.to_dict()
                daily_total = cost_data.get("transcription_usd_total", 0.0)
                metrics["cost_details"] = cost_data

                # Calculate budget percentage (configurable via settings)
                daily_budget = get_config_value("budgets.transcription_daily_usd", 5.0)
                if daily_budget > 0:
                    metrics["budget_percentage"] = (daily_total / daily_budget) * 100

            # Query dead letter queue entries
            dlq_ref = db.collection('jobs_deadletter')
            dlq_query = dlq_ref.where('created_at', '>=', start_utc).where('created_at', '<', end_utc)

            dlq_entries = []
            for doc in dlq_query.stream():
                dlq_data = doc.to_dict()
                dlq_entries.append({
                    "job_type": dlq_data.get("job_type", "unknown"),
                    "reason": dlq_data.get("reason", "unknown"),
                    "retry_count": dlq_data.get("retry_count", 0)
                })

            metrics["dlq_entries"] = len(dlq_entries)
            metrics["errors"] = dlq_entries[:3]  # Top 3 errors for digest

        except Exception as e:
            metrics["collection_error"] = str(e)

        return metrics

    def _create_digest_content(self, metrics: Dict[str, Any], date: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured digest content from collected metrics."""

        # Calculate processing efficiency
        discovered = metrics["videos_discovered"]
        transcribed = metrics["videos_transcribed"]
        summarized = metrics["summaries_generated"]

        processing_flow = f"{discovered} → {transcribed} → {summarized}"

        # Budget status with emoji
        budget_pct = metrics["budget_percentage"]
        if budget_pct >= 90:
            budget_emoji = "🔴"
            budget_status = "CRITICAL"
        elif budget_pct >= 80:
            budget_emoji = "🟡"
            budget_status = "WARNING"
        else:
            budget_emoji = "🟢"
            budget_status = "HEALTHY"

        # Error summary
        dlq_count = metrics["dlq_entries"]
        error_summary = "None" if dlq_count == 0 else f"{dlq_count} DLQ entries"

        # Quick links (configurable)
        drive_base_url = "https://drive.google.com/drive/folders"
        links = {
            "transcripts": f"{drive_base_url}/{config.get('google_drive', {}).get('folder_id_transcripts', 'unknown')}",
            "summaries": f"{drive_base_url}/{config.get('google_drive', {}).get('folder_id_summaries', 'unknown')}",
            "firestore": "https://console.firebase.google.com/project/your-project/firestore"
        }

        return {
            "header": f"🌅 Daily Autopiloot Digest - {date}",
            "processing_summary": {
                "flow": processing_flow,
                "discovered": discovered,
                "transcribed": transcribed,
                "summarized": summarized,
                "completion_rate": f"{(summarized/max(discovered,1)*100):.1f}%" if discovered > 0 else "0%"
            },
            "budget_status": {
                "emoji": budget_emoji,
                "status": budget_status,
                "spent": f"${metrics['total_cost_usd']:.2f}",
                "percentage": f"{budget_pct:.1f}%",
                "limit": "$5.00"
            },
            "issues": {
                "summary": error_summary,
                "dlq_count": dlq_count,
                "errors": metrics["errors"][:3]
            },
            "links": links,
            "top_videos": metrics["top_videos"][:3]
        }

    def _format_slack_blocks(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format digest content as Slack Block Kit blocks."""
        # Get configured sections from settings
        enabled_sections = get_config_value(
            "notifications.slack.digest.sections",
            ["summary", "budgets", "issues", "links"]
        )

        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": content["header"]
            }
        })

        # Processing Summary Section
        if "summary" in enabled_sections:
            processing = content["processing_summary"]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📊 Processing Summary*\n"
                           f"Pipeline Flow: `{processing['flow']}`\n"
                           f"Completion Rate: *{processing['completion_rate']}*"
                }
            })

        # Budget Status Section
        if "budgets" in enabled_sections:
            budget = content["budget_status"]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*💰 Budget Status* {budget['emoji']}\n"
                           f"Daily Spend: *{budget['spent']}* / {budget['limit']} ({budget['percentage']})\n"
                           f"Status: *{budget['status']}*"
                }
            })

        # Issues & Health Section
        if "issues" in enabled_sections:
            issues = content["issues"]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚠️ Issues & Health*\n"
                           f"Errors: {issues['summary']}\n"
                           f"DLQ Entries: {issues['dlq_count']}"
                }
            })

        # Top Videos (if any)
        if content["top_videos"]:
            video_list = "\n".join([
                f"• {video['title'][:50]}... ({video['duration_sec']//60}min)"
                for video in content["top_videos"]
            ])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎥 Top Videos Processed*\n{video_list}"
                }
            })

        # Quick Links Section
        if "links" in enabled_sections:
            links = content["links"]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔗 Quick Links*\n"
                           f"<{links['transcripts']}|📄 Transcripts> | "
                           f"<{links['summaries']}|📝 Summaries> | "
                           f"<{links['firestore']}|🔥 Firestore>"
                }
            })

        # Footer with timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Generated at {datetime.now().strftime('%H:%M %Z')} | Autopiloot v1.0"
                }
            ]
        })

        return blocks


if __name__ == "__main__":
    # Test the tool with yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    tool = GenerateDailyDigest(
        date=yesterday,
        timezone_name="Europe/Amsterdam"
    )

    result = tool.run()
    print("Daily Digest Generation Test:")
    print("=" * 50)

    try:
        parsed_result = json.loads(result)
        if "error" in parsed_result:
            print(f"❌ Error: {parsed_result['message']}")
        else:
            print(f"✅ Successfully generated digest for {parsed_result['date']}")
            print(f"📊 Videos processed: {parsed_result['metrics']['videos_discovered']}")
            print(f"💰 Total cost: ${parsed_result['metrics']['total_cost_usd']:.2f}")
            print(f"📱 Slack blocks: {len(parsed_result['slack_blocks'])}")
            print(f"🏥 DLQ entries: {parsed_result['metrics']['dlq_entries']}")
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response: {result}")