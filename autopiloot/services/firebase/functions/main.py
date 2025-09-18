"""
Firebase Functions for Autopiloot scheduling and event handling.

This module contains:
1. Scheduled function for daily scraper runs at 01:00 Europe/Amsterdam
2. Event-driven function for transcription budget monitoring
"""

from firebase_functions import scheduler_fn, firestore_fn, options
from firebase_admin import initialize_app, firestore
import logging
from typing import Dict, Any, Optional

# Import core business logic
from agents.autopiloot.services.firebase.functions.core import create_scraper_job, process_transcription_budget, validate_video_id, validate_transcript_data

# Import shared agent helpers
from .agent_helpers import get_orchestrator_agent

# Initialize Firebase Admin SDK
initialize_app()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TIMEZONE = "Europe/Amsterdam"

def _get_firestore_client():
    """Get Firestore client instance."""
    return firestore.client()

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

    This function uses the orchestrator agent to plan and dispatch daily runs,
    or falls back to creating a job in Firestore if agent is unavailable.
    """
    logger.info("Starting daily scraper schedule trigger")

    # Try to use orchestrator agent first
    orchestrator = get_orchestrator_agent()
    if orchestrator:
        try:
            # Use orchestrator's plan_daily_run tool
            from agents.autopiloot.orchestrator_agent.tools.plan_daily_run import PlanDailyRun

            planner = PlanDailyRun()
            result = planner.run()
            logger.info(f"Orchestrator planned daily run: {result}")

            # Dispatch to scraper via orchestrator
            from agents.autopiloot.orchestrator_agent.tools.dispatch_scraper import DispatchScraper
            dispatcher = DispatchScraper()
            dispatch_result = dispatcher.run()
            logger.info(f"Orchestrator dispatched scraper: {dispatch_result}")

            return {
                "status": "success",
                "method": "orchestrator_agent",
                "plan": result,
                "dispatch": dispatch_result
            }
        except Exception as e:
            logger.warning(f"Orchestrator agent failed, falling back to core logic: {e}")

    # Fallback to delegated core.py logic (which will try agents again)
    db = _get_firestore_client()
    result = create_scraper_job(db, TIMEZONE)

    # Add method indicator to show this came through main.py fallback
    if isinstance(result, dict):
        result["source"] = "main_py_fallback"

    return result

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
    # Extract video_id from the event path
    video_id = event.params.get("video_id")
    if not validate_video_id(video_id):
        logger.warning("No video_id in event params")
        return {"status": "error", "message": "No video_id"}
    
    logger.info(f"Processing transcription completion for video: {video_id}")
    
    # Get the transcript document to extract cost information
    if not event.data:
        logger.warning(f"No transcript data in event for video: {video_id}")
        return {"status": "error", "message": "No transcript data"}
    
    transcript_data = event.data.to_dict()
    if not validate_transcript_data(transcript_data):
        logger.warning(f"Invalid transcript data for video: {video_id}")
        return {"status": "error", "message": "Invalid transcript data"}
    
    # Try to use observability agent directly
    orchestrator = get_orchestrator_agent()
    if orchestrator:
        try:
            logger.info("Using observability agent for budget monitoring")
            from agents.autopiloot.observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

            budget_monitor = MonitorTranscriptionBudget()
            result = budget_monitor.run()

            # Parse result and add source information
            if isinstance(result, str):
                import json
                try:
                    result_data = json.loads(result)
                except json.JSONDecodeError:
                    result_data = {"status": "success", "raw_result": result}
            else:
                result_data = result

            return {
                "status": "success",
                "method": "observability_agent_direct",
                "video_id": video_id,
                "result": result_data
            }

        except Exception as e:
            logger.warning(f"Direct observability agent failed, falling back to core logic: {e}")

    # Fallback to delegated core.py logic (which will try agents again)
    db = _get_firestore_client()
    result = process_transcription_budget(db, video_id, transcript_data)

    # Add method indicator
    if isinstance(result, dict):
        result["source"] = "main_py_fallback"

    return result