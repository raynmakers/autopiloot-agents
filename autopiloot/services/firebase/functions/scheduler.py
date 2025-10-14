"""
Firebase Functions v2 for scheduling Autopiloot agents and monitoring.
Handles daily scraping schedule and budget monitoring.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from firebase_functions import scheduler_fn, firestore_fn, options
from firebase_admin import initialize_app, firestore
import logging

# Initialize Firebase Admin
initialize_app()
db = firestore.client()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import shared agent helpers
from .agent_helpers import get_orchestrator_agent, get_observability_agent, get_linkedin_agent, get_drive_agent


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
                from agents.autopiloot.orchestrator_agent.tools.plan_daily_run import PlanDailyRun
                from agents.autopiloot.orchestrator_agent.tools.dispatch_scraper import DispatchScraper
                from agents.autopiloot.orchestrator_agent.tools.emit_run_events import EmitRunEvents

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
                    'run_id': event.id if hasattr(event, 'id') else datetime.now(timezone.utc).isoformat(),
                    'method': 'orchestrator_agent',
                    'plan': plan_result,
                    'dispatch': dispatch_result
                }

            except Exception as e:
                logger.warning(f"Orchestrator agent failed, falling back to direct agency: {e}")

        # Fallback to direct agency usage
        from agents.autopiloot.agency import AutopilootAgency

        # Initialize the agency
        agency = AutopilootAgency()

        # Get configured channel from settings
        from agents.autopiloot.core.env_loader import get_config_value
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
            'run_id': event.id if hasattr(event, 'id') else datetime.now(timezone.utc).isoformat(),
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
            'run_id': event.id if hasattr(event, 'id') else datetime.now(timezone.utc).isoformat(),
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
        today = datetime.now(timezone.utc).date()
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
        from agents.autopiloot.core.env_loader import get_config_value, env_loader
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
        from agents.autopiloot.assistant_agent.tools import FormatSlackBlocks, SendSlackMessage
        
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
        from agents.autopiloot.core.env_loader import get_config_value
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
        from agents.autopiloot.assistant_agent.tools import SendErrorAlert
        
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
            timestamp=datetime.now(timezone.utc).isoformat(),
            id=f"manual_{datetime.now(timezone.utc).timestamp()}"
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
# NOTE: The schedule and timezone in the decorator are fixed at deployment time.
# Runtime configuration (channel, sections, timezone for date calc) can be changed
# via settings.yaml without redeployment.

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
    # Get configurable digest settings
    from agents.autopiloot.core.env_loader import get_config_value

    digest_enabled = get_config_value("notifications.slack.digest.enabled", True)
    digest_timezone = get_config_value("notifications.slack.digest.timezone", "Europe/Amsterdam")
    digest_channel = get_config_value("notifications.slack.digest.channel", "ops-autopiloot")

    if not digest_enabled:
        logger.info("Daily digest is disabled in configuration")
        return {"ok": True, "message": "Digest disabled in configuration"}

    logger.info(f"Starting daily digest delivery (timezone: {digest_timezone}, channel: {digest_channel})")

    try:
        from datetime import datetime, timedelta
        import pytz
        import json

        # Calculate yesterday's date in configured timezone
        tz = pytz.timezone(digest_timezone)
        now_tz = datetime.now(tz)
        yesterday_tz = now_tz - timedelta(days=1)
        yesterday_date = yesterday_tz.strftime("%Y-%m-%d")

        logger.info(f"Generating digest for date: {yesterday_date}")

        # Get observability agent (lazy initialization)
        observability_agent = get_observability_agent()

        if observability_agent is None:
            # Fallback: use tool directly
            from agents.autopiloot.observability_agent.tools.generate_daily_digest import GenerateDailyDigest
            from agents.autopiloot.observability_agent.tools.send_slack_message import SendSlackMessage

            # Generate digest
            digest_tool = GenerateDailyDigest(
                date=yesterday_date,
                timezone_name=digest_timezone
            )

            digest_result = digest_tool.run()
            digest_data = json.loads(digest_result)

            if "error" in digest_data:
                logger.error(f"Digest generation failed: {digest_data['message']}")
                return {"error": "digest_generation_failed", "message": digest_data['message']}

            # Send to Slack
            slack_tool = SendSlackMessage(
                channel=digest_channel,
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
                from agents.autopiloot.observability_agent.tools.generate_daily_digest import GenerateDailyDigest
                from agents.autopiloot.observability_agent.tools.send_slack_message import SendSlackMessage

                digest_tool = GenerateDailyDigest(
                    date=yesterday_date,
                    timezone_name=digest_timezone
                )

                digest_result = digest_tool.run()
                digest_data = json.loads(digest_result)

                if "error" not in digest_data:
                    slack_tool = SendSlackMessage(
                        channel=digest_channel,
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
            'execution_time': datetime.now(timezone.utc).isoformat()
        })

        logger.info("Daily digest delivery completed successfully")

        return {
            'ok': True,
            'date': yesterday_date,
            'timezone': digest_timezone,
            'channel': digest_channel,
            'execution_time': datetime.now(timezone.utc).isoformat(),
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
            from agents.autopiloot.observability_agent.tools.send_error_alert import SendErrorAlert

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
            'execution_time': datetime.now(timezone.utc).isoformat()
        }


# ==================================================================================
# SCHEDULED FUNCTION: LinkedIn Ingestion at 06:00 Europe/Amsterdam
# ==================================================================================

@scheduler_fn.on_schedule(
    schedule="0 6 * * *",  # Daily at 06:00
    timezone=scheduler_fn.Timezone("Europe/Amsterdam"),
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,  # 5 minutes timeout
    max_instances=1,  # Only one instance at a time
)
def schedule_linkedin_daily(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Scheduled function to run LinkedIn content ingestion daily at 06:00 Europe/Amsterdam.
    Processes configured LinkedIn profiles and stores content to Zep GraphRAG.
    """
    try:
        logger.info(f"Starting daily LinkedIn ingestion at {event.timestamp}")

        # Get LinkedIn configuration
        from agents.autopiloot.core.env_loader import get_config_value

        # Check if LinkedIn ingestion is enabled
        linkedin_enabled = get_config_value("linkedin.enabled", True)
        if not linkedin_enabled:
            logger.info("LinkedIn ingestion is disabled in configuration")
            return {"ok": True, "message": "LinkedIn ingestion disabled"}

        # Get configured profiles
        profiles = get_config_value("linkedin.profiles", [])
        if not profiles:
            logger.warning("No LinkedIn profiles configured for ingestion")
            return {"ok": True, "message": "No profiles configured"}

        # Get processing limits
        daily_limit = get_config_value("linkedin.processing.daily_limit_per_profile", 25)
        content_types = get_config_value("linkedin.processing.content_types", ["posts", "comments"])

        # Get LinkedIn agent
        linkedin_agent = get_linkedin_agent()
        if not linkedin_agent:
            logger.error("Failed to initialize LinkedIn agent")
            return {"ok": False, "error": "LinkedIn agent initialization failed"}

        results = []
        total_processed = 0
        total_errors = 0

        for profile in profiles:
            profile_id = profile.get("identifier", profile) if isinstance(profile, dict) else profile
            logger.info(f"Processing LinkedIn profile: {profile_id}")

            try:
                # Create ingestion workflow message
                workflow_message = f"""
                Run complete LinkedIn content ingestion for profile: {profile_id}

                Requirements:
                - Fetch up to {daily_limit} recent posts
                - Include comments and reactions for each post
                - Process content types: {', '.join(content_types)}
                - Normalize all content and deduplicate
                - Store in Zep GraphRAG with proper grouping
                - Save comprehensive audit record to Firestore

                Use the complete workflow: GetUserPosts → GetPostComments → GetPostReactions →
                NormalizeLinkedInContent → DeduplicateEntities → ComputeLinkedInStats →
                UpsertToZepGroup → SaveIngestionRecord
                """

                # Run the LinkedIn agent workflow
                result = linkedin_agent.run(workflow_message)

                # Parse result for metrics
                processed_count = 0
                error_count = 0

                # Extract metrics from result string (basic parsing)
                if "processed" in str(result).lower():
                    try:
                        import re
                        numbers = re.findall(r'\d+', str(result))
                        if numbers:
                            processed_count = int(numbers[0])
                    except:
                        processed_count = 1  # Assume at least 1 if successful

                total_processed += processed_count

                # Log successful profile processing
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'linkedin_ingestion',
                    'profile': profile_id,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'status': 'success',
                    'processed_count': processed_count,
                    'result': str(result)[:1000],  # Truncate long results
                    'run_id': event.id if hasattr(event, 'id') else datetime.now(timezone.utc).isoformat()
                })

                results.append({
                    'profile': profile_id,
                    'status': 'success',
                    'processed': processed_count,
                    'message': str(result)[:200]
                })

            except Exception as e:
                logger.error(f"Failed to process LinkedIn profile {profile_id}: {str(e)}")
                total_errors += 1

                # Log failure to audit
                audit_ref = db.collection('audit_logs').document()
                audit_ref.set({
                    'type': 'linkedin_ingestion',
                    'profile': profile_id,
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'status': 'failed',
                    'error': str(e),
                    'run_id': event.id if hasattr(event, 'id') else datetime.now(timezone.utc).isoformat()
                })

                results.append({
                    'profile': profile_id,
                    'status': 'failed',
                    'error': str(e)
                })

        logger.info(f"LinkedIn ingestion completed. Processed {len(results)} profiles, {total_processed} items total, {total_errors} errors")

        # Send summary to observability if significant activity
        if total_processed > 0 or total_errors > 0:
            try:
                _send_linkedin_summary(
                    profiles_processed=len(results),
                    items_processed=total_processed,
                    errors=total_errors,
                    results=results
                )
            except Exception as e:
                logger.warning(f"Failed to send LinkedIn summary: {e}")

        return {
            'ok': True,
            'run_id': event.id if hasattr(event, 'id') else datetime.now(timezone.utc).isoformat(),
            'profiles_processed': len(results),
            'items_processed': total_processed,
            'errors': total_errors,
            'results': results
        }

    except Exception as e:
        logger.error(f"Critical error in LinkedIn scheduler: {str(e)}")

        # Send error alert
        try:
            _send_error_alert(
                message=f"LinkedIn daily ingestion failed critically",
                context={'error': str(e), 'timestamp': event.timestamp}
            )
        except:
            pass  # Don't fail on alert failure

        return {
            'ok': False,
            'run_id': event.id if hasattr(event, 'id') else datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }


def _send_linkedin_summary(profiles_processed: int, items_processed: int,
                          errors: int, results: list) -> None:
    """
    Send LinkedIn ingestion summary via Assistant agent's Slack integration.
    """
    try:
        # Import Assistant tools
        from agents.autopiloot.assistant_agent.tools import FormatSlackBlocks, SendSlackMessage

        # Determine status emoji and summary
        if errors == 0:
            status_emoji = "✅"
            status_text = "All profiles processed successfully"
        elif errors < profiles_processed:
            status_emoji = "⚠️"
            status_text = f"Partial success: {errors} profiles failed"
        else:
            status_emoji = "❌"
            status_text = "All profiles failed"

        # Format the summary message
        formatter = FormatSlackBlocks()
        formatter.items = {
            'title': f'{status_emoji} LinkedIn Ingestion Summary',
            'summary': status_text,
            'fields': [
                {'label': 'Profiles Processed', 'value': str(profiles_processed)},
                {'label': 'Content Items', 'value': str(items_processed)},
                {'label': 'Errors', 'value': str(errors)},
                {'label': 'Success Rate', 'value': f"{((profiles_processed - errors) / profiles_processed * 100):.1f}%" if profiles_processed > 0 else "0%"}
            ],
            'footer': f'LinkedIn ingestion completed at {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC'
        }

        # Add profile details if there are failures
        if errors > 0:
            failed_profiles = [r['profile'] for r in results if r['status'] == 'failed']
            if failed_profiles:
                formatter.items['fields'].append({
                    'label': 'Failed Profiles',
                    'value': ', '.join(failed_profiles[:5])  # Limit to first 5
                })

        blocks = formatter.run()

        # Send to Slack
        sender = SendSlackMessage()
        from agents.autopiloot.core.env_loader import get_config_value
        sender.channel = get_config_value("notifications.slack.channel", "ops-autopiloot")
        sender.blocks = blocks['blocks']

        result = sender.run()
        logger.info(f"LinkedIn summary sent to Slack: {result}")

    except Exception as e:
        logger.error(f"Failed to send LinkedIn summary: {str(e)}")


# ==================================================================================
# SCHEDULED FUNCTION: Drive Content Ingestion every 3 hours
# ==================================================================================

@scheduler_fn.on_schedule(
    schedule="0 */3 * * *",  # Every 3 hours
    timezone=scheduler_fn.Timezone("Europe/Amsterdam"),
    memory=options.MemoryOption.MB_512,
    timeout_sec=480,  # 8 minutes timeout
    max_instances=1,  # Only one instance at a time
)
def schedule_drive_ingestion(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Scheduled function to run Google Drive content ingestion every 3 hours.
    Tracks configured Drive files/folders and indexes new/updated content into Zep GraphRAG.
    """
    try:
        logger.info(f"Starting Drive content ingestion at {event.timestamp}")

        # Get Drive configuration
        from agents.autopiloot.core.env_loader import get_config_value

        # Check if Drive ingestion is enabled
        drive_enabled = get_config_value("drive.enabled", True)
        if not drive_enabled:
            logger.info("Drive ingestion is disabled in configuration")
            return {"ok": True, "message": "Drive ingestion disabled"}

        # Get configured targets
        drive_config = get_config_value("drive", {})
        tracking_config = drive_config.get("tracking", {})
        targets = tracking_config.get("targets", [])

        if not targets:
            logger.warning("No Drive targets configured for ingestion")
            return {"ok": True, "message": "No targets configured"}

        # Get processing configuration
        sync_interval = tracking_config.get("sync_interval_minutes", 60)
        max_file_size_mb = tracking_config.get("max_file_size_mb", 10)

        # Get Zep namespace
        rag_config = get_config_value("rag", {})
        zep_config = rag_config.get("zep", {})
        namespace_config = zep_config.get("namespace", {})
        zep_namespace = namespace_config.get("drive", "autopiloot_drive_content")

        # Get Drive agent
        drive_agent = get_drive_agent()
        if not drive_agent:
            logger.error("Failed to initialize Drive agent")
            return {"ok": False, "error": "Drive agent initialization failed"}

        # Generate run ID
        run_id = f"drive_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now(timezone.utc)

        logger.info(f"Processing {len(targets)} Drive targets with run ID: {run_id}")

        try:
            # Create comprehensive ingestion workflow message
            workflow_message = f"""
            Run complete Google Drive content ingestion for {len(targets)} configured targets.

            Configuration:
            - Zep namespace: {zep_namespace}
            - Sync interval: {sync_interval} minutes
            - Max file size: {max_file_size_mb} MB
            - Run ID: {run_id}

            Requirements:
            1. Load all tracked targets from configuration
            2. For each target, resolve folder tree or get file metadata
            3. List changes since last checkpoint (if available)
            4. Fetch content for new/updated files within size limits
            5. Extract clean text from all supported formats (PDF, DOCX, etc.)
            6. Upsert documents to Zep GraphRAG with proper metadata
            7. Save comprehensive audit record to Firestore with:
               - Processing metrics and performance data
               - Target-by-target results and error tracking
               - Checkpoint data for next incremental run
               - Success rates and recommendations

            Use the complete workflow: ListTrackedTargetsFromConfig → ResolveFolderTree/ListDriveChanges →
            FetchFileContent → ExtractTextFromDocument → UpsertDriveDocsToZep → SaveDriveIngestionRecord

            Handle errors gracefully and ensure audit trail is maintained for operational monitoring.
            """

            # Run the Drive agent workflow
            result = drive_agent.run(workflow_message)

            # Calculate processing duration
            end_time = datetime.now(timezone.utc)
            processing_duration = (end_time - start_time).total_seconds()

            # Parse result for metrics (basic parsing)
            processed_files = 0
            zep_documents = 0
            errors = 0

            # Extract metrics from result string (basic parsing)
            result_str = str(result).lower()
            if "processed" in result_str or "upserted" in result_str:
                try:
                    import re
                    # Look for numbers in the result
                    numbers = re.findall(r'\d+', str(result))
                    if numbers:
                        processed_files = int(numbers[0]) if len(numbers) > 0 else 0
                        zep_documents = int(numbers[1]) if len(numbers) > 1 else processed_files
                except:
                    processed_files = 1  # Assume at least 1 if successful

            if "error" in result_str or "failed" in result_str:
                errors = 1

            # Log successful ingestion run
            audit_ref = db.collection('audit_logs').document()
            audit_ref.set({
                'type': 'drive_ingestion',
                'run_id': run_id,
                'namespace': zep_namespace,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'status': 'success' if errors == 0 else 'completed_with_errors',
                'targets_configured': len(targets),
                'files_processed': processed_files,
                'zep_documents_upserted': zep_documents,
                'processing_duration_seconds': processing_duration,
                'sync_interval_minutes': sync_interval,
                'result': str(result)[:1000],  # Truncate long results
                'event_id': event.id if hasattr(event, 'id') else None
            })

            logger.info(f"Drive ingestion completed successfully. Run ID: {run_id}, Files: {processed_files}, Duration: {processing_duration:.1f}s")

            return {
                'ok': True,
                'run_id': run_id,
                'namespace': zep_namespace,
                'targets_configured': len(targets),
                'files_processed': processed_files,
                'zep_documents_upserted': zep_documents,
                'processing_duration_seconds': processing_duration,
                'sync_interval_minutes': sync_interval,
                'errors': errors,
                'message': f'Drive ingestion completed with {processed_files} files processed'
            }

        except Exception as workflow_error:
            # Calculate duration even for failed runs
            end_time = datetime.now(timezone.utc)
            processing_duration = (end_time - start_time).total_seconds()

            logger.error(f"Drive agent workflow failed: {str(workflow_error)}")

            # Log failure to audit
            audit_ref = db.collection('audit_logs').document()
            audit_ref.set({
                'type': 'drive_ingestion',
                'run_id': run_id,
                'namespace': zep_namespace,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'status': 'failed',
                'targets_configured': len(targets),
                'processing_duration_seconds': processing_duration,
                'error': str(workflow_error),
                'event_id': event.id if hasattr(event, 'id') else None
            })

            # Send error alert
            try:
                _send_drive_error_alert(
                    run_id=run_id,
                    targets_count=len(targets),
                    error=str(workflow_error),
                    duration=processing_duration
                )
            except Exception as alert_error:
                logger.warning(f"Failed to send Drive error alert: {alert_error}")

            return {
                'ok': False,
                'run_id': run_id,
                'namespace': zep_namespace,
                'targets_configured': len(targets),
                'processing_duration_seconds': processing_duration,
                'error': str(workflow_error)
            }

    except Exception as e:
        logger.error(f"Critical error in Drive scheduler: {str(e)}")

        # Send critical error alert
        try:
            _send_error_alert(
                message=f"Drive ingestion scheduler failed critically",
                context={'error': str(e), 'timestamp': event.timestamp}
            )
        except:
            pass  # Don't fail on alert failure

        return {
            'ok': False,
            'run_id': f"failed_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            'error': str(e)
        }


def _send_drive_error_alert(run_id: str, targets_count: int, error: str, duration: float) -> None:
    """
    Send Drive ingestion error alert via Assistant agent's Slack integration.
    """
    try:
        # Import Assistant tools
        from agents.autopiloot.assistant_agent.tools import FormatSlackBlocks, SendSlackMessage

        # Format the error alert
        formatter = FormatSlackBlocks()
        formatter.items = {
            'title': '🔴 Drive Ingestion Failed',
            'summary': f'Scheduled Drive content ingestion failed after {duration:.1f} seconds',
            'fields': [
                {'label': 'Run ID', 'value': run_id},
                {'label': 'Targets Configured', 'value': str(targets_count)},
                {'label': 'Processing Duration', 'value': f'{duration:.1f}s'},
                {'label': 'Error', 'value': error[:200] + '...' if len(error) > 200 else error}
            ],
            'footer': 'Check Drive agent logs and configuration for resolution'
        }

        blocks = formatter.run()

        # Send to Slack
        sender = SendSlackMessage()
        from agents.autopiloot.core.env_loader import get_config_value
        sender.channel = get_config_value("notifications.slack.channel", "ops-autopiloot")
        sender.blocks = blocks['blocks']

        result = sender.run()
        logger.info(f"Drive error alert sent to Slack: {result}")

    except Exception as e:
        logger.error(f"Failed to send Drive error alert: {str(e)}")


# ==================================================================================
# SCHEDULED FUNCTION: Thread Cleanup at 02:00 Europe/Amsterdam
# ==================================================================================

@scheduler_fn.on_schedule(
    schedule="0 2 * * *",  # Daily at 02:00
    timezone=scheduler_fn.Timezone("Europe/Amsterdam"),
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    max_instances=1,  # Only one instance at a time
)
def cleanup_old_threads(event: scheduler_fn.ScheduledEvent) -> Dict[str, Any]:
    """
    Scheduled function to clean up old conversation threads daily at 02:00 Europe/Amsterdam.

    Removes conversation threads older than the configured retention period to prevent
    unbounded Firestore growth and manage storage costs.

    Part of Agency Swarm v1.2.0 conversation persistence feature (TASK-AGS-0097).
    """
    try:
        logger.info(f"Starting thread cleanup at {event.timestamp}")

        # Get cleanup configuration
        from agents.autopiloot.config.loader import get_config_value

        persistence_config = get_config_value("agency.persistence", {})
        retention_days = persistence_config.get("retention_days", 30)
        collection = persistence_config.get("collection", "agency_threads")

        # Check if persistence is enabled
        if not persistence_config.get("enabled", True):
            logger.info("Thread persistence is disabled, skipping cleanup")
            return {"ok": True, "message": "Thread persistence disabled"}

        logger.info(f"Cleaning threads in '{collection}' older than {retention_days} days")

        # Import cleanup utility
        from agents.autopiloot.core.thread_cleanup import cleanup_old_threads as do_cleanup, get_thread_stats

        # Get stats before cleanup
        stats_before = get_thread_stats(collection=collection)
        logger.info(f"Thread stats before cleanup: {stats_before}")

        # Perform cleanup
        deleted_count = do_cleanup(retention_days=retention_days, collection=collection)

        # Get stats after cleanup
        stats_after = get_thread_stats(collection=collection)
        logger.info(f"Thread stats after cleanup: {stats_after}")

        # Log successful cleanup to audit
        audit_ref = db.collection('audit_logs').document()
        audit_ref.set({
            'type': 'thread_cleanup',
            'collection': collection,
            'retention_days': retention_days,
            'threads_deleted': deleted_count,
            'threads_remaining': stats_after['total_threads'],
            'oldest_thread_age_days': stats_after['oldest_thread_age_days'],
            'timestamp': firestore.SERVER_TIMESTAMP,
            'status': 'success',
            'event_id': event.id if hasattr(event, 'id') else None
        })

        logger.info(f"Thread cleanup completed successfully. Deleted {deleted_count} old threads, {stats_after['total_threads']} remaining")

        return {
            'ok': True,
            'collection': collection,
            'retention_days': retention_days,
            'deleted_count': deleted_count,
            'remaining_threads': stats_after['total_threads'],
            'oldest_thread_age_days': stats_after['oldest_thread_age_days'],
            'execution_time': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Thread cleanup failed: {str(e)}")

        # Log failure to audit
        try:
            audit_ref = db.collection('audit_logs').document()
            audit_ref.set({
                'type': 'thread_cleanup',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'error': str(e),
                'status': 'failed',
                'event_id': event.id if hasattr(event, 'id') else None
            })
        except:
            pass  # Don't fail on audit logging failure

        # Send error alert
        try:
            _send_error_alert(
                message=f"Thread cleanup failed",
                context={'error': str(e), 'timestamp': event.timestamp}
            )
        except:
            pass  # Don't fail on alert failure

        return {
            'ok': False,
            'error': str(e),
            'execution_time': datetime.now(timezone.utc).isoformat()
        }


# Agent getters are imported from shared helpers above