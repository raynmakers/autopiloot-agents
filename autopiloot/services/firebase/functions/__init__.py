"""
Firebase Functions entry point for Autopiloot scheduling and monitoring.
Exports all functions for deployment.
"""

# Import all functions to register them
from .scheduler import (
    schedule_scraper_daily,
    on_transcription_written,
    trigger_scraper_manual
)

# Export functions for Firebase to discover
__all__ = [
    'schedule_scraper_daily',
    'on_transcription_written',
    'trigger_scraper_manual'
]

# Function metadata for reference
FUNCTIONS = {
    'schedule_scraper_daily': {
        'type': 'scheduled',
        'schedule': '0 1 * * *',
        'timezone': 'Europe/Amsterdam',
        'description': 'Daily scraper for YouTube channels'
    },
    'on_transcription_written': {
        'type': 'firestore_trigger',
        'document': 'transcripts/{video_id}',
        'events': ['create', 'update'],
        'description': 'Budget monitor for transcription costs'
    },
    'trigger_scraper_manual': {
        'type': 'firestore_trigger',
        'document': 'triggers/scraper_manual',
        'events': ['create'],
        'description': 'Manual trigger for testing scraper'
    }
}
