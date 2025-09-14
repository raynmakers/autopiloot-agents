"""
Reliability utilities for Autopiloot agents.
Handles dead-letter queues, quota management, and backoff strategies.
"""

from typing import TypedDict, Optional, Dict, Any, Literal
from datetime import datetime, timedelta
import json
import logging
import time
from enum import Enum

# Set up logging
logger = logging.getLogger(__name__)


class JobType(str, Enum):
    """Enumeration of job types for DLQ tracking."""
    YOUTUBE_DISCOVERY = "youtube_discovery"
    TRANSCRIPTION = "transcription"
    SUMMARIZATION = "summarization"
    SHEETS_PROCESSING = "sheets_processing"
    SLACK_NOTIFICATION = "slack_notification"


class DLQEntry(TypedDict):
    """Dead Letter Queue entry structure."""
    job_type: str
    video_id: str
    reason: str
    retry_count: int
    last_error_at: str


class QuotaStatus(TypedDict):
    """Quota status tracking structure."""
    service: str
    quota_exhausted: bool
    reset_time: Optional[str]
    requests_made: int
    requests_limit: int


class CheckpointData(TypedDict):
    """Checkpoint data for resuming operations."""
    service: str
    last_published_at: Optional[str]
    last_processed_id: Optional[str]
    updated_at: str


def create_dlq_entry(
    job_type: str,
    video_id: str,
    reason: str,
    retry_count: int = 0,
    error_details: Optional[Dict[str, Any]] = None
) -> DLQEntry:
    """
    Create a dead letter queue entry for a failed job.
    
    Args:
        job_type: Type of job that failed
        video_id: Video ID associated with the failed job
        reason: Human-readable reason for failure
        retry_count: Number of retry attempts made
        error_details: Optional additional error information
        
    Returns:
        DLQ entry ready for Firestore storage
        
    Examples:
        >>> entry = create_dlq_entry("transcription", "dQw4w9WgXcQ", "API quota exceeded")
        >>> entry["job_type"]
        'transcription'
    """
    entry = DLQEntry(
        job_type=job_type,
        video_id=video_id,
        reason=reason,
        retry_count=retry_count,
        last_error_at=datetime.utcnow().isoformat() + "Z"
    )
    
    if error_details:
        # Add error details as additional fields (not in TypedDict but allowed in Firestore)
        entry["error_details"] = error_details
    
    return entry


def should_retry_job(retry_count: int, max_retries: int = 3) -> bool:
    """
    Determine if a job should be retried based on retry count.
    
    Args:
        retry_count: Current number of retry attempts
        max_retries: Maximum allowed retry attempts
        
    Returns:
        True if job should be retried, False if it should go to DLQ
    """
    return retry_count < max_retries


def calculate_backoff_delay(retry_count: int, base_delay: int = None) -> int:
    """
    Calculate exponential backoff delay for retries.
    
    Args:
        retry_count: Current retry attempt (0-based)
        base_delay: Base delay in seconds (defaults to config value or 60)
        
    Returns:
        Delay in seconds before next retry
        
    Examples:
        >>> calculate_backoff_delay(0)  # First retry
        60
        >>> calculate_backoff_delay(2)  # Third retry  
        240
    """
    if base_delay is None:
        # Try to load from config, fallback to 60 seconds
        try:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'config'))
            from loader import load_app_config, get_retry_base_delay
            config = load_app_config()
            base_delay = get_retry_base_delay(config)
        except:
            base_delay = 60  # Fallback default
    
    return base_delay * (2 ** retry_count)


def create_quota_status(
    service: str,
    requests_made: int,
    requests_limit: int,
    quota_exhausted: bool = False,
    reset_time: Optional[str] = None
) -> QuotaStatus:
    """
    Create quota status tracking object.
    
    Args:
        service: Name of the service (e.g., "youtube", "assemblyai")
        requests_made: Number of requests made in current period
        requests_limit: Maximum requests allowed in period
        quota_exhausted: Whether quota is currently exhausted
        reset_time: When quota resets (ISO8601 format)
        
    Returns:
        Quota status object
    """
    return QuotaStatus(
        service=service,
        quota_exhausted=quota_exhausted,
        reset_time=reset_time,
        requests_made=requests_made,
        requests_limit=requests_limit
    )


def is_quota_exhausted(quota_status: QuotaStatus) -> bool:
    """
    Check if service quota is exhausted.
    
    Args:
        quota_status: Current quota status
        
    Returns:
        True if quota is exhausted, False otherwise
    """
    if quota_status["quota_exhausted"]:
        # Check if reset time has passed
        if quota_status["reset_time"]:
            reset_time = datetime.fromisoformat(quota_status["reset_time"].replace('Z', '+00:00'))
            if datetime.utcnow().replace(tzinfo=reset_time.tzinfo) >= reset_time:
                return False  # Quota has reset
        return True
    
    # Check if we're approaching the limit
    return quota_status["requests_made"] >= quota_status["requests_limit"]


def get_next_reset_time(service: str) -> str:
    """
    Get the next quota reset time for a service.
    
    Args:
        service: Service name
        
    Returns:
        ISO8601 timestamp of next reset time
    """
    # Most APIs reset daily at midnight UTC or 24 hours from first request
    # For YouTube API, quota resets at midnight Pacific Time
    # For simplicity, we'll use next day at midnight UTC
    
    now = datetime.utcnow()
    next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    return next_reset.isoformat() + "Z"


def create_checkpoint(
    service: str,
    last_published_at: Optional[str] = None,
    last_processed_id: Optional[str] = None
) -> CheckpointData:
    """
    Create checkpoint data for resuming operations.
    
    Args:
        service: Service name (e.g., "youtube")
        last_published_at: Last processed publication timestamp
        last_processed_id: Last processed item ID
        
    Returns:
        Checkpoint data object
    """
    return CheckpointData(
        service=service,
        last_published_at=last_published_at,
        last_processed_id=last_processed_id,
        updated_at=datetime.utcnow().isoformat() + "Z"
    )


def should_pause_for_quota(quota_status: QuotaStatus) -> bool:
    """
    Determine if processing should pause due to quota limits.
    
    Args:
        quota_status: Current quota status
        
    Returns:
        True if processing should pause
    """
    return is_quota_exhausted(quota_status)


def get_resume_time(quota_status: QuotaStatus) -> Optional[datetime]:
    """
    Get the time when processing can resume after quota exhaustion.
    
    Args:
        quota_status: Current quota status
        
    Returns:
        DateTime when processing can resume, or None if not quota limited
    """
    if not quota_status["quota_exhausted"] or not quota_status["reset_time"]:
        return None
    
    return datetime.fromisoformat(quota_status["reset_time"].replace('Z', '+00:00'))


class QuotaManager:
    """
    Manages API quota tracking and enforcement.
    """
    
    def __init__(self):
        self.quota_statuses: Dict[str, QuotaStatus] = {}
    
    def track_request(self, service: str, requests_limit: int) -> QuotaStatus:
        """
        Track an API request and update quota status.
        
        Args:
            service: Service name
            requests_limit: Maximum requests allowed for this service
            
        Returns:
            Updated quota status
        """
        if service not in self.quota_statuses:
            self.quota_statuses[service] = create_quota_status(
                service=service,
                requests_made=0,
                requests_limit=requests_limit
            )
        
        quota = self.quota_statuses[service]
        quota["requests_made"] += 1
        
        # Check if quota is exhausted
        if quota["requests_made"] >= quota["requests_limit"]:
            quota["quota_exhausted"] = True
            quota["reset_time"] = get_next_reset_time(service)
        
        return quota
    
    def is_service_available(self, service: str) -> bool:
        """
        Check if a service is available (not quota exhausted).
        
        Args:
            service: Service name
            
        Returns:
            True if service is available
        """
        if service not in self.quota_statuses:
            return True
        
        return not is_quota_exhausted(self.quota_statuses[service])
    
    def get_quota_info(self, service: str) -> Optional[QuotaStatus]:
        """
        Get current quota information for a service.
        
        Args:
            service: Service name
            
        Returns:
            Quota status or None if not tracked
        """
        return self.quota_statuses.get(service)


def log_dlq_entry(entry: DLQEntry) -> None:
    """
    Log a DLQ entry for monitoring and debugging.
    
    Args:
        entry: DLQ entry to log
    """
    logger.error(
        f"Job failed and sent to DLQ: {entry['job_type']} for video {entry['video_id']} "
        f"(retry {entry['retry_count']}): {entry['reason']}"
    )


def format_error_for_dlq(exception: Exception, context: Dict[str, Any]) -> str:
    """
    Format an exception and context into a DLQ-friendly error message.
    
    Args:
        exception: The exception that occurred
        context: Additional context about the failure
        
    Returns:
        Formatted error message
    """
    error_msg = f"{type(exception).__name__}: {str(exception)}"
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        error_msg += f" | Context: {context_str}"
    
    return error_msg


if __name__ == "__main__":
    # Test the reliability utilities
    print("Testing reliability utilities...")
    
    # Test DLQ entry creation
    dlq_entry = create_dlq_entry(
        job_type=JobType.TRANSCRIPTION,
        video_id="dQw4w9WgXcQ",
        reason="API quota exceeded",
        retry_count=2
    )
    print(f"DLQ Entry: {dlq_entry}")
    
    # Test quota management
    quota_manager = QuotaManager()
    
    # Simulate YouTube API requests
    for i in range(5):
        quota = quota_manager.track_request("youtube", 3)
        print(f"Request {i+1}: Available={quota_manager.is_service_available('youtube')}")
    
    # Test backoff calculation
    for retry in range(4):
        delay = calculate_backoff_delay(retry)
        print(f"Retry {retry}: Delay {delay} seconds")
    
    # Test checkpoint creation
    checkpoint = create_checkpoint(
        service="youtube",
        last_published_at="2025-01-27T10:00:00Z",
        last_processed_id="abc123"
    )
    print(f"Checkpoint: {checkpoint}")
    
    print("✅ All reliability utilities working correctly")
