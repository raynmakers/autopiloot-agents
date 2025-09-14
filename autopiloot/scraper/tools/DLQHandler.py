"""
DLQHandler tool for managing dead letter queue operations.
Handles failed jobs by writing them to the jobs_deadletter collection.
"""

import os
import sys
from typing import Optional, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from reliability import (
    create_dlq_entry, DLQEntry, JobType, should_retry_job,
    calculate_backoff_delay, log_dlq_entry, format_error_for_dlq
)
from env_loader import get_google_credentials_path

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

load_dotenv()


class DLQHandler(BaseTool):
    """
    Handles dead letter queue operations for failed jobs.
    
    This tool:
    1. Creates DLQ entries for jobs that fail after retries
    2. Writes failed jobs to the jobs_deadletter Firestore collection
    3. Provides retry logic and backoff calculations
    4. Logs failures for monitoring and debugging
    """
    
    job_type: str = Field(
        ...,
        description="Type of job that failed (e.g., 'transcription', 'youtube_discovery')"
    )
    
    video_id: str = Field(
        ...,
        description="Video ID associated with the failed job"
    )
    
    reason: str = Field(
        ...,
        description="Human-readable reason for job failure"
    )
    
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts made (default: 0)"
    )
    
    error_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional additional error information (JSON object)"
    )
    
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries before sending to DLQ (uses config value if None)"
    )

    def run(self) -> str:
        """
        Handle a failed job by either retrying or sending to DLQ.
        
        Returns:
            JSON string with retry decision and DLQ status
        """
        try:
            # Load configuration values
            from config.loader import load_app_config, get_retry_max_attempts, get_retry_base_delay
            config = load_app_config()
            
            # Use config values if not provided
            max_retries = self.max_retries if self.max_retries is not None else get_retry_max_attempts(config)
            base_delay = get_retry_base_delay(config)
            
            # Initialize Firestore if not already done
            if not firebase_admin._apps:
                cred = credentials.Certificate(get_google_credentials_path())
                firebase_admin.initialize_app(cred)
            
            db = firestore.client()
            
            # Determine if job should be retried
            should_retry = should_retry_job(self.retry_count, max_retries)
            
            if should_retry:
                # Calculate backoff delay for next retry
                backoff_delay = calculate_backoff_delay(self.retry_count, base_delay)
                
                response = {
                    "success": True,
                    "action": "retry",
                    "retry_count": self.retry_count,
                    "backoff_delay_seconds": backoff_delay,
                    "next_retry_in": f"{backoff_delay} seconds",
                    "max_retries": max_retries,
                    "message": f"Job will be retried in {backoff_delay} seconds (attempt {self.retry_count + 1}/{max_retries + 1})"
                }
                
                return str(response).replace("'", '"')
            
            else:
                # Create DLQ entry
                dlq_entry = create_dlq_entry(
                    job_type=self.job_type,
                    video_id=self.video_id,
                    reason=self.reason,
                    retry_count=self.retry_count,
                    error_details=self.error_details
                )
                
                # Generate unique document ID
                dlq_doc_id = f"{self.job_type}_{self.video_id}_{dlq_entry['last_error_at']}"
                
                # Write to Firestore DLQ collection
                dlq_ref = db.collection('jobs_deadletter').document(dlq_doc_id)
                dlq_ref.set(dlq_entry)
                
                # Log the DLQ entry
                log_dlq_entry(dlq_entry)
                
                response = {
                    "success": True,
                    "action": "dlq",
                    "dlq_entry": dlq_entry,
                    "dlq_document_id": dlq_doc_id,
                    "retry_count": self.retry_count,
                    "max_retries": max_retries,
                    "message": f"Job failed after {self.retry_count} retries and has been sent to dead letter queue"
                }
                
                return str(response).replace("'", '"')
                
        except Exception as e:
            error_msg = f"Failed to handle DLQ operation: {str(e)}"
            error_response = {
                "success": False,
                "error": error_msg,
                "job_type": self.job_type,
                "video_id": self.video_id
            }
            return str(error_response).replace("'", '"')


class DLQQuery(BaseTool):
    """
    Query dead letter queue entries for monitoring and analysis.
    
    This tool:
    1. Retrieves DLQ entries by job type or video ID
    2. Provides statistics on failure patterns
    3. Helps identify problematic jobs for manual intervention
    """
    
    job_type: Optional[str] = Field(
        None,
        description="Filter by job type (optional)"
    )
    
    video_id: Optional[str] = Field(
        None,
        description="Filter by specific video ID (optional)"
    )
    
    limit: int = Field(
        default=10,
        description="Maximum number of entries to return (default: 10)"
    )
    
    include_stats: bool = Field(
        default=True,
        description="Include failure statistics in response (default: True)"
    )

    def run(self) -> str:
        """
        Query DLQ entries with optional filtering.
        
        Returns:
            JSON string with DLQ entries and statistics
        """
        try:
            # Initialize Firestore if not already done
            if not firebase_admin._apps:
                cred = credentials.Certificate(get_google_credentials_path())
                firebase_admin.initialize_app(cred)
            
            db = firestore.client()
            
            # Build query
            query = db.collection('jobs_deadletter')
            
            # Apply filters
            if self.job_type:
                query = query.where(filter=FieldFilter('job_type', '==', self.job_type))
            
            if self.video_id:
                query = query.where(filter=FieldFilter('video_id', '==', self.video_id))
            
            # Order by most recent and limit results
            query = query.order_by('last_error_at', direction=firestore.Query.DESCENDING)
            query = query.limit(self.limit)
            
            # Execute query
            docs = query.stream()
            
            # Process results
            entries = []
            for doc in docs:
                entry_data = doc.to_dict()
                entry_data['document_id'] = doc.id
                entries.append(entry_data)
            
            # Calculate statistics if requested
            stats = {}
            if self.include_stats:
                stats = self._calculate_dlq_stats(db)
            
            response = {
                "success": True,
                "entries_found": len(entries),
                "entries": entries,
                "query_filters": {
                    "job_type": self.job_type,
                    "video_id": self.video_id,
                    "limit": self.limit
                }
            }
            
            if stats:
                response["statistics"] = stats
            
            return str(response).replace("'", '"')
            
        except Exception as e:
            error_msg = f"Failed to query DLQ entries: {str(e)}"
            error_response = {
                "success": False,
                "error": error_msg
            }
            return str(error_response).replace("'", '"')
    
    def _calculate_dlq_stats(self, db) -> Dict[str, Any]:
        """Calculate DLQ statistics."""
        try:
            # Get all DLQ entries for stats
            all_docs = db.collection('jobs_deadletter').stream()
            
            stats = {
                "total_entries": 0,
                "by_job_type": {},
                "by_retry_count": {},
                "recent_failures": 0  # Last 24 hours
            }
            
            from datetime import datetime, timedelta
            yesterday = datetime.utcnow() - timedelta(hours=24)
            
            for doc in all_docs:
                data = doc.to_dict()
                stats["total_entries"] += 1
                
                # Count by job type
                job_type = data.get("job_type", "unknown")
                stats["by_job_type"][job_type] = stats["by_job_type"].get(job_type, 0) + 1
                
                # Count by retry count
                retry_count = data.get("retry_count", 0)
                stats["by_retry_count"][str(retry_count)] = stats["by_retry_count"].get(str(retry_count), 0) + 1
                
                # Count recent failures
                error_time_str = data.get("last_error_at", "")
                if error_time_str:
                    try:
                        error_time = datetime.fromisoformat(error_time_str.replace('Z', '+00:00'))
                        if error_time.replace(tzinfo=None) > yesterday:
                            stats["recent_failures"] += 1
                    except:
                        pass  # Skip invalid timestamps
            
            return stats
            
        except Exception:
            return {"error": "Failed to calculate statistics"}


if __name__ == "__main__":
    # Test the DLQ handler
    dlq_handler = DLQHandler(
        job_type="transcription",
        video_id="test123",
        reason="API quota exceeded",
        retry_count=0
    )
    
    print("DLQHandler test (retry scenario):")
    result = dlq_handler.run()
    print(result)
    
    # Test DLQ query
    dlq_query = DLQQuery(
        job_type="transcription",
        limit=5
    )
    
    print("\nDLQQuery test:")
    print("Note: Run with valid Firestore credentials to test fully")
