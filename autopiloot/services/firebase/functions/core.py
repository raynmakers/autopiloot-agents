"""
Core business logic for Firebase Functions - delegated to orchestrator agent.
This module serves as an adapter layer to the full orchestrator agent workflow.

DEPRECATED: This simplified implementation is being phased out in favor of
full orchestrator agent integration. Functions should use the agent directly.
"""

import logging
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Add path for orchestrator imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy-initialized orchestrator agent
_orchestrator_agent: Optional[Any] = None

def get_orchestrator_agent():
    """Get or create orchestrator agent instance (lazy initialization)."""
    global _orchestrator_agent
    if _orchestrator_agent is None:
        try:
            from orchestrator_agent.orchestrator_agent import orchestrator_agent
            _orchestrator_agent = orchestrator_agent
            logger.info("Orchestrator agent initialized in core.py adapter")
        except ImportError as e:
            logger.error(f"Failed to import orchestrator agent in core.py: {e}")
            _orchestrator_agent = None
    return _orchestrator_agent

# Configuration
TIMEZONE = "Europe/Amsterdam"
BUDGET_THRESHOLD = 0.8  # 80% of daily budget
SLACK_CHANNEL = "ops-autopiloot"


def _send_slack_alert_simple(message: str, context: Dict[str, Any] = None) -> bool:
    """
    Send simple Slack alert (fallback implementation).

    Args:
        message: Alert message text
        context: Optional context data to include

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use observability agent's Slack tools if available
        from observability_agent.tools.send_slack_message import SendSlackMessage
        from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

        formatter = FormatSlackBlocks()
        formatter.title = "Firebase Function Alert"
        formatter.summary = message
        if context:
            formatter.fields = [{"label": k, "value": str(v)} for k, v in context.items()]

        blocks_result = formatter.run()

        sender = SendSlackMessage()
        sender.channel = SLACK_CHANNEL
        if isinstance(blocks_result, str):
            import json
            try:
                blocks_data = json.loads(blocks_result)
                sender.blocks = blocks_data.get("blocks", [])
            except:
                sender.text = message
        else:
            sender.text = message

        result = sender.run()
        logger.info(f"Sent Slack alert via agent tools: {result}")
        return True

    except ImportError:
        logger.info("Observability agent not available, using direct Slack API")
        return send_slack_alert(message, context)
    except Exception as e:
        logger.warning(f"Agent Slack tools failed, falling back to direct API: {e}")
        return send_slack_alert(message, context)

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
    Create a scraper job via orchestrator agent (DEPRECATED - use agent directly).

    This function delegates to the orchestrator agent's planning and dispatch tools,
    falling back to simplified logic if the agent is unavailable.

    Args:
        firestore_client: Firestore client instance
        timezone_name: Timezone for the job

    Returns:
        Dict containing job creation result
    """
    # Try orchestrator agent first
    orchestrator = get_orchestrator_agent()
    if orchestrator:
        try:
            logger.info("Delegating scraper job creation to orchestrator agent")

            # Use orchestrator's planning tool
            from orchestrator_agent.tools.plan_daily_run import PlanDailyRun
            planner = PlanDailyRun()
            plan_result = planner.run()
            logger.info(f"Orchestrator planned daily run: {plan_result}")

            # Emit run start event
            from orchestrator_agent.tools.emit_run_events import EmitRunEvents
            event_emitter = EmitRunEvents()
            event_emitter.event_type = "run_started"
            event_emitter.metadata = {"timezone": timezone_name, "source": "scheduled_function"}
            event_emitter.run()

            # Use orchestrator's dispatch tool
            from orchestrator_agent.tools.dispatch_scraper import DispatchScraper
            dispatcher = DispatchScraper()
            dispatch_result = dispatcher.run()
            logger.info(f"Orchestrator dispatched scraper: {dispatch_result}")

            # Return orchestrator result
            return {
                "status": "success",
                "method": "orchestrator_agent",
                "plan": plan_result,
                "dispatch": dispatch_result,
                "timezone": timezone_name
            }

        except Exception as e:
            logger.warning(f"Orchestrator agent failed in core.py, falling back to simplified logic: {e}")

    # Fallback to simplified implementation
    logger.info("Using simplified scraper job creation (fallback)")
    try:
        now = datetime.now(timezone.utc)

        # Create scraper job document
        job_data = {
            "job_type": "scraper_daily",
            "created_at": now.isoformat(),
            "status": "queued",
            "timezone": timezone_name,
            "source": "scheduled_fallback",
            "config": {
                "handles": ["@AlexHormozi"],
                "include_sheet_links": True,
                "backfill_months": 12
            }
        }

        # Write to jobs/scraper collection
        job_ref = firestore_client.collection("jobs").document("scraper").collection("daily").document()
        job_ref.set(job_data)

        logger.info(f"Created fallback scraper job: {job_ref.id}")

        # Send success notification via simplified alert
        _send_slack_alert_simple(
            f"✅ Daily scraper job scheduled (fallback) at {now.isoformat()}",
            {"job_id": job_ref.id, "timezone": timezone_name}
        )

        return {"status": "success", "job_id": job_ref.id, "method": "fallback"}

    except Exception as e:
        logger.error(f"Failed to create fallback scraper job: {e}")
        _send_slack_alert_simple(
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
    Process transcription budget monitoring via observability agent (DEPRECATED).

    This function delegates to the observability agent's budget monitoring tools,
    falling back to simplified logic if the agent is unavailable.

    Args:
        firestore_client: Firestore client instance
        video_id: Video identifier
        transcript_data: Transcript document data
        daily_budget: Daily budget limit in USD

    Returns:
        Dict containing processing result
    """
    # Try observability agent tools first
    try:
        logger.info("Delegating budget monitoring to observability agent")

        # Use observability agent's budget monitoring tool
        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        budget_monitor = MonitorTranscriptionBudget()
        result = budget_monitor.run()
        logger.info(f"Observability agent budget monitoring result: {result}")

        # Parse the JSON result
        if isinstance(result, str):
            import json
            try:
                result_data = json.loads(result)
            except json.JSONDecodeError:
                result_data = {"status": "success", "method": "observability_agent", "raw_result": result}
        else:
            result_data = result

        return {
            "status": "success",
            "method": "observability_agent",
            "video_id": video_id,
            "agent_result": result_data
        }

    except ImportError as e:
        logger.warning(f"Observability agent not available, falling back to simplified logic: {e}")
    except Exception as e:
        logger.warning(f"Observability agent failed in core.py, falling back to simplified logic: {e}")

    # Fallback to simplified implementation
    logger.info("Using simplified budget monitoring (fallback)")
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
                # Send budget alert via simplified alert
                alert_success = _send_slack_alert_simple(
                    f"⚠️ Daily transcription budget threshold reached (fallback)!\n"
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
                        "latest_video_id": video_id,
                        "method": "fallback"
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
            "method": "fallback",
            "video_id": video_id,
            "daily_cost": total_daily_cost,
            "budget_usage_pct": budget_usage_pct,
            "transcript_count": transcript_count,
            "alert_sent": alert_sent
        }
        
    except Exception as e:
        logger.error(f"Failed to process transcription budget (fallback): {e}")
        _send_slack_alert_simple(
            f"🚨 Error processing transcription budget monitoring (fallback): {str(e)}",
            {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat(), "method": "fallback"}
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
