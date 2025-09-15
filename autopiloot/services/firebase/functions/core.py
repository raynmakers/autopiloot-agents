"""
Core business logic for Firebase Functions without decorators.
This module contains the testable business logic separated from Firebase-specific code.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import requests
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TIMEZONE = "Europe/Amsterdam"
BUDGET_THRESHOLD = 0.8  # 80% of daily budget
SLACK_CHANNEL = "ops-autopiloot"

def send_slack_alert(message: str, context: Dict[str, Any] = None) -> bool:
    """
    Send alert message to Slack channel.
    
    Args:
        message: Alert message text
        context: Optional context data to include
        
    Returns:
        bool: True if successful, False otherwise
    """
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        logger.warning("SLACK_BOT_TOKEN not configured, skipping Slack alert")
        return False
    
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
                return True
            else:
                logger.error(f"Slack API error: {result.get('error')}")
                return False
        else:
            logger.error(f"Slack HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
        return False

def create_scraper_job(firestore_client, timezone_name: str = TIMEZONE) -> Dict[str, Any]:
    """
    Create a scraper job in Firestore.
    
    Args:
        firestore_client: Firestore client instance
        timezone_name: Timezone for the job
        
    Returns:
        Dict containing job creation result
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Create scraper job document
        job_data = {
            "job_type": "scraper_daily",
            "created_at": now.isoformat(),
            "status": "queued",
            "timezone": timezone_name,
            "source": "scheduled",
            "config": {
                "handles": ["@AlexHormozi"],
                "include_sheet_links": True,
                "backfill_months": 12
            }
        }
        
        # Write to jobs/scraper collection
        job_ref = firestore_client.collection("jobs").document("scraper").collection("daily").document()
        job_ref.set(job_data)
        
        logger.info(f"Created scraper job: {job_ref.id}")
        
        # Send success notification
        send_slack_alert(
            f"✅ Daily scraper job scheduled successfully at {now.isoformat()}",
            {"job_id": job_ref.id, "timezone": timezone_name}
        )
        
        return {"status": "success", "job_id": job_ref.id}
        
    except Exception as e:
        logger.error(f"Failed to create scraper job: {e}")
        send_slack_alert(
            f"🚨 Failed to schedule daily scraper job: {str(e)}",
            {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        raise

def process_transcription_budget(
    firestore_client, 
    video_id: str, 
    transcript_data: Dict[str, Any],
    daily_budget: float = 5.0
) -> Dict[str, Any]:
    """
    Process transcription budget monitoring for a completed transcript.
    
    Args:
        firestore_client: Firestore client instance
        video_id: Video identifier
        transcript_data: Transcript document data
        daily_budget: Daily budget limit in USD
        
    Returns:
        Dict containing processing result
    """
    try:
        transcription_cost = transcript_data.get("costs", {}).get("transcription_usd", 0.0)
        
        # Calculate daily budget usage
        today = datetime.now(timezone.utc).date().isoformat()
        
        # Aggregate daily costs
        transcripts_query = firestore_client.collection("transcripts").where(
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
        daily_costs_ref = firestore_client.collection("costs_daily").document(today)
        daily_costs_ref.set({
            "date": today,
            "transcription_usd_total": total_daily_cost,
            "transcript_count": transcript_count,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }, merge=True)
        
        # Check if budget threshold exceeded
        budget_usage_pct = (total_daily_cost / daily_budget) * 100
        
        logger.info(f"Daily budget usage: ${total_daily_cost:.2f}/{daily_budget:.2f} ({budget_usage_pct:.1f}%)")
        
        alert_sent = False
        if budget_usage_pct >= (BUDGET_THRESHOLD * 100):
            # Check if alert already sent today
            daily_costs_doc = daily_costs_ref.get()
            daily_costs_data = daily_costs_doc.to_dict() if daily_costs_doc.exists else {}
            alerts_sent = daily_costs_data.get("alerts_sent", [])
            
            alert_type = "budget_threshold"
            if alert_type not in alerts_sent:
                # Send budget alert
                alert_success = send_slack_alert(
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
                
                if alert_success:
                    # Mark alert as sent
                    alerts_sent.append(alert_type)
                    daily_costs_ref.set({"alerts_sent": alerts_sent}, merge=True)
                    alert_sent = True
                    logger.info(f"Budget alert sent for {today}")
            else:
                logger.info(f"Budget alert already sent for {today}")
        
        return {
            "status": "success",
            "video_id": video_id,
            "daily_cost": total_daily_cost,
            "budget_usage_pct": budget_usage_pct,
            "transcript_count": transcript_count,
            "alert_sent": alert_sent
        }
        
    except Exception as e:
        logger.error(f"Failed to process transcription budget: {e}")
        send_slack_alert(
            f"🚨 Error processing transcription budget monitoring: {str(e)}",
            {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        raise

def validate_video_id(video_id: Optional[str]) -> bool:
    """
    Validate video ID parameter.
    
    Args:
        video_id: Video identifier to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    return video_id is not None and isinstance(video_id, str) and len(video_id.strip()) > 0

def validate_transcript_data(transcript_data: Optional[Dict[str, Any]]) -> bool:
    """
    Validate transcript data structure.
    
    Args:
        transcript_data: Transcript data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not transcript_data or not isinstance(transcript_data, dict):
        return False
    
    # Check for required cost structure
    costs = transcript_data.get("costs")
    if not costs or not isinstance(costs, dict):
        return False
    
    # Check for transcription cost
    transcription_cost = costs.get("transcription_usd")
    if transcription_cost is None or not isinstance(transcription_cost, (int, float)):
        return False
    
    return True
