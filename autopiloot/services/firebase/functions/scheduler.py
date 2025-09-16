"""
Firebase Functions v2 for scheduling Autopiloot agents and monitoring.
Handles daily scraping schedule and budget monitoring.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from firebase_functions import scheduler_fn, firestore_fn, options
from firebase_admin import initialize_app, firestore
import logging

# Add autopiloot to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# Initialize Firebase Admin
initialize_app()
db = firestore.client()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy-initialized orchestrator agent singleton
_orchestrator_agent: Optional[Any] = None

def get_orchestrator_agent():
    """
    Get or create the orchestrator agent instance (lazy initialization).
    This minimizes cold start costs by deferring agent creation until needed.
    """
    global _orchestrator_agent
    if _orchestrator_agent is None:
        try:
            from orchestrator_agent.orchestrator_agent import orchestrator_agent
            _orchestrator_agent = orchestrator_agent
            logger.info("Orchestrator agent initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import orchestrator agent: {e}")
            # Fallback to None, functions will use existing logic
            _orchestrator_agent = None
    return _orchestrator_agent


# ==================================================================================
# SCHEDULED FUNCTION: Daily Scraper at 01:00 Europe/Amsterdam
# ==================================================================================

@scheduler_fn.on_schedule(
    schedule="0 1 * * *",  # Daily at 01:00
    timezone=scheduler_fn.Timezone("Europe/Amsterdam"),
    memory=options.MemoryOption.MB_512,
    timeout_sec=540,  # 9 minutes timeout
    max_instances=1,  # Only one instance at a time
)
def schedule_scraper_daily(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Scheduled function to run the Scraper agent daily at 01:00 Europe/Amsterdam.
    Uses orchestrator agent for coordination or falls back to direct agency usage.
    """
    try:
        logger.info(f"Starting daily scraper run at {event.timestamp}")

        # Try to use orchestrator agent first
        orchestrator = get_orchestrator_agent()
        if orchestrator:
            try:
                # Use orchestrator's planning and dispatch tools
                from orchestrator_agent.tools.plan_daily_run import PlanDailyRun
                from orchestrator_agent.tools.dispatch_scraper import DispatchScraper
                from orchestrator_agent.tools.emit_run_events import EmitRunEvents

                # Plan the daily run
                planner = PlanDailyRun()
                plan_result = planner.run()
                logger.info(f"Orchestrator planned daily run: {plan_result}")

                # Emit run start event
                event_emitter = EmitRunEvents()
                event_emitter.event_type = "run_started"
                event_emitter.metadata = {"timestamp": event.timestamp, "plan": plan_result}
                event_emitter.run()

                # Dispatch to scraper
                dispatcher = DispatchScraper()
                dispatch_result = dispatcher.run()
                logger.info(f"Orchestrator dispatched scraper: {dispatch_result}")

                # Emit run complete event
                event_emitter.event_type = "run_completed"
                event_emitter.metadata = {"timestamp": event.timestamp, "result": dispatch_result}
                event_emitter.run()

                return {
                    'ok': True,
                    'run_id': event.id if hasattr(event, 'id') else datetime.utcnow().isoformat(),
                    'method': 'orchestrator_agent',
                    'plan': plan_result,
                    'dispatch': dispatch_result
                }

            except Exception as e:
                logger.warning(f"Orchestrator agent failed, falling back to direct agency: {e}")

        # Fallback to direct agency usage
        from agency import AutopilootAgency

        # Initialize the agency
        agency = AutopilootAgency()

        # Get configured channel from settings
        from core.env_loader import get_config_value
        channels = get_config_value("scraper.handles", ["@AlexHormozi"])

        results = []
        for channel_handle in channels:
            logger.info(f"Processing channel: {channel_handle}")
            
            try:
                # Run the daily scrape for this channel
                result = agency.start_daily_scrape(channel_handle)
                
                # Log the result to Firestore for audit
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'daily_scrape',
                    'channel': channel_handle,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'result': str(result)[:1000],  # Truncate long results
                    'status': 'success'
                })
                
                results.append({
                    'channel': channel_handle,
                    'status': 'success',
                    'message': str(result)[:200]
                })
                
            except Exception as e:
                logger.error(f"Failed to scrape {channel_handle}: {str(e)}")
                
                # Log failure to audit
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'daily_scrape',
                    'channel': channel_handle,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'error': str(e),
                    'status': 'failed'
                })
                
                results.append({
                    'channel': channel_handle,
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info(f"Daily scraper completed. Processed {len(results)} channels")
        
        return {
            'ok': True,
            'run_id': event.id if hasattr(event, 'id') else datetime.utcnow().isoformat(),
            'channels_processed': len(results),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Critical error in daily scraper: {str(e)}")
        
        # Send error alert via Assistant agent
        try:
            _send_error_alert(
                message=f"Daily scraper failed critically",
                context={'error': str(e), 'timestamp': event.timestamp}
            )
        except:
            pass  # Don't fail on alert failure
        
        return {
            'ok': False,
            'run_id': event.id if hasattr(event, 'id') else datetime.utcnow().isoformat(),
            'error': str(e)
        }


# ==================================================================================
# EVENT-DRIVEN FUNCTION: Budget Monitor on Transcript Writes
# ==================================================================================

@firestore_fn.on_document_written(
    document="transcripts/{video_id}",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    max_instances=10,
)
def on_transcription_written(event: firestore_fn.Event[firestore_fn.Change[firestore_fn.DocumentSnapshot]]) -> None:
    """
    Triggered when a transcript document is created or updated.
    Monitors daily transcription budget and sends alerts when threshold exceeded.
    """
    try:
        # Get the video_id from the event
        video_id = event.params['video_id']
        
        # Get the document data
        if event.data.after:
            doc_data = event.data.after.to_dict()
        else:
            logger.warning(f"Transcript {video_id} was deleted, skipping budget check")
            return
        
        # Check if this is a new transcription (not an update)
        is_new = event.data.before is None or not event.data.before.exists
        
        if not is_new:
            logger.info(f"Transcript {video_id} was updated, not new. Skipping budget check.")
            return
        
        # Get the transcription cost
        costs = doc_data.get('costs', {})
        transcription_cost = costs.get('transcription_usd', 0)
        
        if transcription_cost <= 0:
            logger.warning(f"Transcript {video_id} has no cost data")
            return
        
        logger.info(f"New transcript {video_id} cost: ${transcription_cost:.2f}")
        
        # Calculate daily total
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = start_of_day + timedelta(days=1)
        
        # Query all transcripts created today
        transcripts_ref = db.collection('transcripts')
        query = transcripts_ref.where('created_at', '>=', start_of_day).where('created_at', '<', end_of_day)
        
        total_cost = 0.0
        transaction_count = 0
        
        for doc in query.stream():
            data = doc.to_dict()
            doc_costs = data.get('costs', {})
            doc_cost = doc_costs.get('transcription_usd', 0)
            total_cost += doc_cost
            transaction_count += 1
        
        # Get budget configuration
        from core.env_loader import get_config_value, env_loader
        daily_budget = get_config_value("budgets.transcription_daily_usd", 5.0)
        alert_threshold = env_loader.get_float_var("BUDGET_ALERT_THRESHOLD", 0.8)
        
        # Calculate percentage
        budget_percentage = (total_cost / daily_budget) * 100 if daily_budget > 0 else 0
        
        logger.info(f"Daily budget status: ${total_cost:.2f} / ${daily_budget:.2f} ({budget_percentage:.1f}%)")
        
        # Update daily costs document
        costs_ref = db.collection('costs_daily').document(today.isoformat())
        costs_ref.set({
            'date': today.isoformat(),
            'transcription_usd': total_cost,
            'transaction_count': transaction_count,
            'budget_usd': daily_budget,
            'budget_percentage': budget_percentage,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, merge=True)
        
        # Check if we need to send an alert
        if budget_percentage >= (alert_threshold * 100):
            logger.warning(f"Budget threshold exceeded: {budget_percentage:.1f}% of ${daily_budget:.2f}")
            
            # Send budget alert
            _send_budget_alert(
                date=today.isoformat(),
                total_cost=total_cost,
                daily_budget=daily_budget,
                budget_percentage=budget_percentage,
                transaction_count=transaction_count
            )
            
            # Log alert to audit
            audit_ref = db.collection('audit_logs').document()
            audit_ref.set({
                'type': 'budget_alert',
                'date': today.isoformat(),
                'total_cost_usd': total_cost,
                'budget_usd': daily_budget,
                'budget_percentage': budget_percentage,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'triggered_by': f"transcripts/{video_id}"
            })
        
    except Exception as e:
        logger.error(f"Error in budget monitor for transcript {video_id}: {str(e)}")
        
        # Log error but don't fail the function
        try:
            audit_ref = db.collection('audit_logs').document()
            audit_ref.set({
                'type': 'budget_monitor_error',
                'video_id': video_id,
                'error': str(e),
                'timestamp': firestore.SERVER_TIMESTAMP
            })
        except:
            pass


# ==================================================================================
# HELPER FUNCTIONS
# ==================================================================================

def _send_budget_alert(date: str, total_cost: float, daily_budget: float, 
                      budget_percentage: float, transaction_count: int) -> None:
    """
    Send budget alert via Assistant agent's Slack integration.
    """
    try:
        # Import Assistant tools
        from assistant.tools import FormatSlackBlocks, SendSlackMessage
        
        # Format the alert message
        formatter = FormatSlackBlocks()
        formatter.items = {
            'title': '⚠️ Transcription Budget Alert',
            'summary': f'Daily transcription budget has reached {budget_percentage:.1f}%',
            'fields': [
                {'label': 'Date', 'value': date},
                {'label': 'Spent', 'value': f'${total_cost:.2f}'},
                {'label': 'Budget', 'value': f'${daily_budget:.2f}'},
                {'label': 'Usage', 'value': f'{budget_percentage:.1f}%'},
                {'label': 'Transactions', 'value': str(transaction_count)}
            ],
            'footer': 'Consider pausing transcriptions if budget is critical'
        }
        
        blocks = formatter.run()
        
        # Send to Slack
        sender = SendSlackMessage()
        from core.env_loader import get_config_value
        sender.channel = get_config_value("notifications.slack.channel", "ops-autopiloot")
        sender.blocks = blocks['blocks']
        
        result = sender.run()
        logger.info(f"Budget alert sent to Slack: {result}")
        
    except Exception as e:
        logger.error(f"Failed to send budget alert: {str(e)}")
        # Don't raise - we don't want to fail the function if alerting fails


def _send_error_alert(message: str, context: Dict[str, Any]) -> None:
    """
    Send error alert via Assistant agent.
    """
    try:
        from assistant.tools import SendErrorAlert
        
        alert = SendErrorAlert()
        alert.message = message
        alert.context = context
        
        result = alert.run()
        logger.info(f"Error alert sent: {result}")
        
    except Exception as e:
        logger.error(f"Failed to send error alert: {str(e)}")


# ==================================================================================
# MANUAL TRIGGER FUNCTIONS (for testing)
# ==================================================================================

@firestore_fn.on_document_created(
    document="triggers/scraper_manual",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
)
def trigger_scraper_manual(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    """
    Manual trigger for testing the scraper.
    Create a document in triggers/scraper_manual to run the scraper immediately.
    """
    try:
        logger.info("Manual scraper trigger received")
        
        # Create a mock scheduled event
        from types import SimpleNamespace
        mock_event = SimpleNamespace(
            timestamp=datetime.utcnow().isoformat(),
            id=f"manual_{datetime.utcnow().timestamp()}"
        )
        
        # Run the scraper
        result = schedule_scraper_daily(mock_event)
        
        # Update the trigger document with result
        event.data.reference.update({
            'processed': True,
            'result': result,
            'processed_at': firestore.SERVER_TIMESTAMP
        })

        logger.info(f"Manual scraper completed: {result}")

    except Exception as e:
        logger.error(f"Manual scraper failed: {str(e)}")
        event.data.reference.update({
            'processed': True,
            'error': str(e),
            'processed_at': firestore.SERVER_TIMESTAMP
        })


# ==================================================================================
# SCHEDULED FUNCTION: Daily Digest at 07:00 Europe/Amsterdam
# ==================================================================================

@scheduler_fn.on_schedule(
    schedule="0 7 * * *",  # 07:00 daily
    timezone="Europe/Amsterdam",
    memory=options.MemoryOption.MB_256,
    timeout_sec=180
)
def daily_digest_delivery(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Send daily operational digest at 07:00 Europe/Amsterdam.

    PRD requirement: "Assistant daily Slack digest at 07:00" with comprehensive
    processing summary, costs, errors, and system health metrics.

    Runs 6 hours after the 01:00 scraper to allow complete processing.
    """
    logger.info("Starting daily digest delivery at 07:00 Europe/Amsterdam")

    try:
        from datetime import datetime, timedelta
        import pytz
        import json

        # Calculate yesterday's date in Europe/Amsterdam timezone
        ams_tz = pytz.timezone("Europe/Amsterdam")
        now_ams = datetime.now(ams_tz)
        yesterday_ams = now_ams - timedelta(days=1)
        yesterday_date = yesterday_ams.strftime("%Y-%m-%d")

        logger.info(f"Generating digest for date: {yesterday_date}")

        # Get observability agent (lazy initialization)
        observability_agent = get_observability_agent()

        if observability_agent is None:
            # Fallback: use tool directly
            from observability_agent.tools.generate_daily_digest import GenerateDailyDigest
            from observability_agent.tools.send_slack_message import SendSlackMessage

            # Generate digest
            digest_tool = GenerateDailyDigest(
                date=yesterday_date,
                timezone_name="Europe/Amsterdam"
            )

            digest_result = digest_tool.run()
            digest_data = json.loads(digest_result)

            if "error" in digest_data:
                logger.error(f"Digest generation failed: {digest_data['message']}")
                return {"error": "digest_generation_failed", "message": digest_data['message']}

            # Send to Slack
            slack_tool = SendSlackMessage(
                channel="ops-autopiloot",  # Default channel
                blocks=digest_data["slack_blocks"]
            )

            slack_result = slack_tool.run()
            slack_data = json.loads(slack_result)

        else:
            # Use full agent workflow
            try:
                # Create a message for the observability agent
                digest_message = f"Generate and send daily digest for {yesterday_date}"
                agent_result = observability_agent.run(digest_message)

                logger.info(f"Agent digest result: {str(agent_result)[:200]}")

            except Exception as agent_error:
                logger.warning(f"Agent workflow failed, using direct tool approach: {agent_error}")

                # Fallback to direct tool usage
                from observability_agent.tools.generate_daily_digest import GenerateDailyDigest
                from observability_agent.tools.send_slack_message import SendSlackMessage

                digest_tool = GenerateDailyDigest(
                    date=yesterday_date,
                    timezone_name="Europe/Amsterdam"
                )

                digest_result = digest_tool.run()
                digest_data = json.loads(digest_result)

                if "error" not in digest_data:
                    slack_tool = SendSlackMessage(
                        channel="ops-autopiloot",
                        blocks=digest_data["slack_blocks"]
                    )
                    slack_result = slack_tool.run()

        # Log successful execution to audit
        audit_ref = db.collection('audit_logs').document()
        audit_ref.set({
            'type': 'daily_digest',
            'date': yesterday_date,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'status': 'success',
            'execution_time': datetime.utcnow().isoformat()
        })

        logger.info("Daily digest delivery completed successfully")

        return {
            'ok': True,
            'date': yesterday_date,
            'timezone': 'Europe/Amsterdam',
            'execution_time': datetime.utcnow().isoformat(),
            'message': 'Daily digest sent successfully'
        }

    except Exception as e:
        logger.error(f"Daily digest delivery failed: {str(e)}")

        # Log failure to audit
        audit_ref = db.collection('audit_logs').document()
        audit_ref.set({
            'type': 'daily_digest',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'error': str(e),
            'status': 'failed'
        })

        # Send error alert to Slack
        try:
            from observability_agent.tools.send_error_alert import SendErrorAlert

            error_tool = SendErrorAlert(
                error_type="daily_digest_failed",
                message=f"Daily digest delivery failed: {str(e)}"
            )
            error_tool.run()

        except Exception as alert_error:
            logger.error(f"Failed to send error alert: {alert_error}")

        return {
            'ok': False,
            'error': str(e),
            'execution_time': datetime.utcnow().isoformat()
        }


# Lazy-initialized observability agent singleton
_observability_agent: Optional[Any] = None

def get_observability_agent():
    """
    Get or create the observability agent instance (lazy initialization).
    Used for daily digest delivery and error alerting.
    """
    global _observability_agent
    if _observability_agent is None:
        try:
            from observability_agent.observability_agent import observability_agent
            _observability_agent = observability_agent
            logger.info("Observability agent initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import observability agent: {e}")
            _observability_agent = None
    return _observability_agent