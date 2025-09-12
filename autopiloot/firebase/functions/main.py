"""
Firebase Functions for Autopiloot scheduling and event handling.

This module contains:
1. Scheduled function for daily scraper runs at 01:00 Europe/Amsterdam
2. Event-driven function for transcription budget monitoring
"""

from firebase_functions import scheduler_fn, firestore_fn, options
from firebase_admin import initialize_app, firestore
import os
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any
import requests

# Initialize Firebase Admin SDK
initialize_app()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TIMEZONE = "Europe/Amsterdam"
BUDGET_THRESHOLD = 0.8  # 80% of daily budget
SLACK_CHANNEL = "ops-autopiloot"

def _get_firestore_client():
    """Get Firestore client instance."""
    return firestore.client()

def _send_slack_alert(message: str, context: Dict[str, Any] = None):
    """Send alert message to Slack channel."""
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        logger.warning("SLACK_BOT_TOKEN not configured, skipping Slack alert")
        return
    
    try:
        payload = {
            "channel": f"#{SLACK_CHANNEL}",
            "text": message,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        }
        
        if context:
            payload["blocks"].append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Context:*\n```{json.dumps(context, indent=2)}```"
                    }
                ]
            })
        
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {slack_token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info(f"Slack alert sent successfully: {result.get('ts')}")
            else:
                logger.error(f"Slack API error: {result.get('error')}")
        else:
            logger.error(f"Slack HTTP error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")

@scheduler_fn.on_schedule(
    schedule="0 1 * * *",
    timezone=TIMEZONE,
    region="europe-west1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=300
)
def schedule_scraper_daily(req) -> Dict[str, Any]:
    """
    Scheduled function to trigger daily scraper run at 01:00 Europe/Amsterdam.
    
    This function creates a job in the Firestore 'jobs/scraper' collection
    to trigger the scraper agent to discover new videos.
    """
    try:
        logger.info("Starting daily scraper schedule trigger")
        
        db = _get_firestore_client()
        now = datetime.now(timezone.utc)
        
        # Create scraper job document
        job_data = {
            "job_type": "scraper_daily",
            "created_at": now.isoformat(),
            "status": "queued",
            "timezone": TIMEZONE,
            "source": "scheduled",
            "config": {
                "handles": ["@AlexHormozi"],
                "include_sheet_links": True,
                "backfill_months": 12
            }
        }
        
        # Write to jobs/scraper collection
        job_ref = db.collection("jobs").document("scraper").collection("daily").document()
        job_ref.set(job_data)
        
        logger.info(f"Created scraper job: {job_ref.id}")
        
        # Send success notification
        _send_slack_alert(
            f"✅ Daily scraper job scheduled successfully at {now.isoformat()}",
            {"job_id": job_ref.id, "timezone": TIMEZONE}
        )
        
        return {"status": "success", "job_id": job_ref.id}
        
    except Exception as e:
        logger.error(f"Failed to schedule scraper job: {e}")
        _send_slack_alert(
            f"🚨 Failed to schedule daily scraper job: {str(e)}",
            {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        raise

@firestore_fn.on_document_written(
    document="transcripts/{video_id}",
    region="europe-west1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=180
)
def on_transcription_written(event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None]) -> Dict[str, Any]:
    """
    Event-driven function triggered when a transcript is written to Firestore.
    
    Monitors daily transcription budget and sends alerts when 80% threshold is reached.
    """
    try:
        # Extract video_id from the event path
        video_id = event.params.get("video_id")
        if not video_id:
            logger.warning("No video_id in event params")
            return {"status": "error", "message": "No video_id"}
        
        logger.info(f"Processing transcription completion for video: {video_id}")
        
        # Get the transcript document to extract cost information
        if not event.data:
            logger.warning(f"No transcript data in event for video: {video_id}")
            return {"status": "error", "message": "No transcript data"}
        
        transcript_data = event.data.to_dict()
        transcription_cost = transcript_data.get("costs", {}).get("transcription_usd", 0.0)
        
        # Calculate daily budget usage
        db = _get_firestore_client()
        today = datetime.now(timezone.utc).date().isoformat()
        daily_budget = 5.0  # $5 default, should be loaded from settings
        
        # Aggregate daily costs
        transcripts_query = db.collection("transcripts").where(
            "created_at", ">=", f"{today}T00:00:00Z"
        ).where(
            "created_at", "<", f"{today}T23:59:59Z"
        )
        
        total_daily_cost = 0.0
        transcript_count = 0
        
        for doc in transcripts_query.stream():
            doc_data = doc.to_dict()
            cost = doc_data.get("costs", {}).get("transcription_usd", 0.0)
            total_daily_cost += cost
            transcript_count += 1
        
        # Update daily costs collection
        daily_costs_ref = db.collection("costs_daily").document(today)
        daily_costs_ref.set({
            "date": today,
            "transcription_usd_total": total_daily_cost,
            "transcript_count": transcript_count,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }, merge=True)
        
        # Check if budget threshold exceeded
        budget_usage_pct = (total_daily_cost / daily_budget) * 100
        
        logger.info(f"Daily budget usage: ${total_daily_cost:.2f}/{daily_budget:.2f} ({budget_usage_pct:.1f}%)")
        
        if budget_usage_pct >= (BUDGET_THRESHOLD * 100):
            # Check if alert already sent today
            daily_costs_doc = daily_costs_ref.get()
            daily_costs_data = daily_costs_doc.to_dict() if daily_costs_doc.exists else {}
            alerts_sent = daily_costs_data.get("alerts_sent", [])
            
            alert_type = "budget_threshold"
            if alert_type not in alerts_sent:
                # Send budget alert
                _send_slack_alert(
                    f"⚠️ Daily transcription budget threshold reached!\n"
                    f"Current usage: ${total_daily_cost:.2f} / ${daily_budget:.2f} ({budget_usage_pct:.1f}%)\n"
                    f"Threshold: {BUDGET_THRESHOLD * 100:.0f}%\n"
                    f"Transcripts processed today: {transcript_count}",
                    {
                        "date": today,
                        "total_cost": total_daily_cost,
                        "budget": daily_budget,
                        "usage_pct": budget_usage_pct,
                        "threshold_pct": BUDGET_THRESHOLD * 100,
                        "transcript_count": transcript_count,
                        "latest_video_id": video_id
                    }
                )
                
                # Mark alert as sent
                alerts_sent.append(alert_type)
                daily_costs_ref.set({"alerts_sent": alerts_sent}, merge=True)
                
                logger.info(f"Budget alert sent for {today}")
            else:
                logger.info(f"Budget alert already sent for {today}")
        
        return {
            "status": "success",
            "video_id": video_id,
            "daily_cost": total_daily_cost,
            "budget_usage_pct": budget_usage_pct
        }
        
    except Exception as e:
        logger.error(f"Failed to process transcription event: {e}")
        _send_slack_alert(
            f"🚨 Error processing transcription budget monitoring: {str(e)}",
            {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        raise