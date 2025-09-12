"""
Firebase Functions for Autopiloot scheduling and event handling.

This module contains:
1. Scheduled function for daily scraper runs at 01:00 Europe/Amsterdam
2. Event-driven function for transcription budget monitoring
"""

from firebase_functions import scheduler_fn, firestore_fn, options
from firebase_admin import initialize_app, firestore
import logging
from typing import Dict, Any

# Import core business logic
from core import create_scraper_job, process_transcription_budget, validate_video_id, validate_transcript_data

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
    
    This function creates a job in the Firestore 'jobs/scraper' collection
    to trigger the scraper agent to discover new videos.
    """
    logger.info("Starting daily scraper schedule trigger")
    db = _get_firestore_client()
    return create_scraper_job(db, TIMEZONE)

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
    
    db = _get_firestore_client()
    return process_transcription_budget(db, video_id, transcript_data)