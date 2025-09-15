"""
Reliability utilities for Autopiloot Agency.
Implements dead letter queue patterns, retry policies, and job management
for robust error handling and recovery across all agents.
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class JobStatus(Enum):
    """Job execution status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior with exponential backoff."""
    max_attempts: int = 3
    base_delay_seconds: int = 60
    max_delay_seconds: int = 240
    exponential_base: float = 2.0
    
    def get_delay(self, attempt: int) -> int:
        """Calculate delay for given attempt using exponential backoff."""
        if attempt <= 0:
            return 0
        
        delay = self.base_delay_seconds * (self.exponential_base ** (attempt - 1))
        return min(int(delay), self.max_delay_seconds)


@dataclass
class JobRecord:
    """Record for tracking job execution and retry state."""
    job_id: str
    job_type: str
    payload: Dict[str, Any]
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    attempt_count: int = 0
    last_error: Optional[str] = None
    retry_policy: Optional[RetryPolicy] = None
    next_retry_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job record to dictionary for storage."""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.next_retry_at:
            data['next_retry_at'] = self.next_retry_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobRecord':
        """Create job record from dictionary."""
        data['status'] = JobStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if data.get('next_retry_at'):
            data['next_retry_at'] = datetime.fromisoformat(data['next_retry_at'])
        if data.get('retry_policy'):
            data['retry_policy'] = RetryPolicy(**data['retry_policy'])
        return cls(**data)


class DeadLetterQueue:
    """
    Dead Letter Queue implementation for handling failed jobs.
    Manages jobs that have exceeded retry attempts or encountered fatal errors.
    """
    
    def __init__(self, firestore_collection: str = "dlq_jobs"):
        """Initialize DLQ with Firestore collection."""
        self.collection_name = firestore_collection
        self._db = None
    
    def _get_firestore(self):
        """Get Firestore client instance."""
        if self._db is None:
            try:
                from google.cloud import firestore
                self._db = firestore.Client()
            except ImportError:
                raise RuntimeError("google-cloud-firestore is required for DLQ functionality")
        return self._db
    
    def add_job(self, job_record: JobRecord) -> None:
        """Add a failed job to the dead letter queue."""
        job_record.status = JobStatus.DEAD_LETTER
        job_record.updated_at = datetime.now(timezone.utc)
        
        db = self._get_firestore()
        doc_ref = db.collection(self.collection_name).document(job_record.job_id)
        doc_ref.set(job_record.to_dict())
    
    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve a job from the dead letter queue."""
        db = self._get_firestore()
        doc_ref = db.collection(self.collection_name).document(job_id)
        doc = doc_ref.get()
        
        if doc.exists:
            return JobRecord.from_dict(doc.to_dict())
        return None
    
    def list_jobs(self, limit: int = 100) -> List[JobRecord]:
        """List jobs in the dead letter queue."""
        db = self._get_firestore()
        query = db.collection(self.collection_name).limit(limit)
        
        jobs = []
        for doc in query.stream():
            jobs.append(JobRecord.from_dict(doc.to_dict()))
        
        return jobs
    
    def requeue_job(self, job_id: str, reset_attempts: bool = True) -> bool:
        """Remove job from DLQ and prepare for retry."""
        job_record = self.get_job(job_id)
        if not job_record:
            return False
        
        if reset_attempts:
            job_record.attempt_count = 0
        
        job_record.status = JobStatus.PENDING
        job_record.updated_at = datetime.now(timezone.utc)
        job_record.next_retry_at = None
        
        # Remove from DLQ
        db = self._get_firestore()
        doc_ref = db.collection(self.collection_name).document(job_id)
        doc_ref.delete()
        
        return True
    
    def delete_job(self, job_id: str) -> bool:
        """Permanently delete a job from the DLQ."""
        db = self._get_firestore()
        doc_ref = db.collection(self.collection_name).document(job_id)
        doc_ref.delete()
        return True


class JobRetryManager:
    """
    Manager for job retry logic and coordination with DLQ.
    Handles retry attempts, exponential backoff, and failure escalation.
    """
    
    def __init__(self, dlq: Optional[DeadLetterQueue] = None):
        """Initialize retry manager with optional DLQ."""
        self.dlq = dlq or DeadLetterQueue()
        self.default_policy = RetryPolicy()
    
    def should_retry(self, job_record: JobRecord) -> bool:
        """Determine if a job should be retried based on policy."""
        policy = job_record.retry_policy or self.default_policy
        return job_record.attempt_count < policy.max_attempts
    
    def schedule_retry(self, job_record: JobRecord, error_message: str) -> JobRecord:
        """Schedule a job for retry with exponential backoff."""
        job_record.attempt_count += 1
        job_record.last_error = error_message
        job_record.updated_at = datetime.now(timezone.utc)
        
        policy = job_record.retry_policy or self.default_policy
        
        if self.should_retry(job_record):
            # Schedule next retry
            delay_seconds = policy.get_delay(job_record.attempt_count)
            job_record.next_retry_at = datetime.now(timezone.utc).replace(
                second=0, microsecond=0
            ) + timedelta(seconds=delay_seconds)
            job_record.status = JobStatus.RETRYING
        else:
            # Send to dead letter queue
            job_record.status = JobStatus.FAILED
            self.dlq.add_job(job_record)
        
        return job_record
    
    def mark_success(self, job_record: JobRecord) -> JobRecord:
        """Mark a job as successfully completed."""
        job_record.status = JobStatus.COMPLETED
        job_record.updated_at = datetime.now(timezone.utc)
        job_record.next_retry_at = None
        return job_record
    
    def mark_fatal_error(self, job_record: JobRecord, error_message: str) -> JobRecord:
        """Mark a job as having a fatal error (no retries)."""
        job_record.last_error = error_message
        job_record.status = JobStatus.FAILED
        job_record.updated_at = datetime.now(timezone.utc)
        self.dlq.add_job(job_record)
        return job_record
    
    def get_retryable_jobs(self, current_time: Optional[datetime] = None) -> List[JobRecord]:
        """Get jobs that are ready for retry based on their scheduled time."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # This would typically query a job queue/database
        # For now, return empty list as this depends on specific storage implementation
        return []


# Helper functions for common reliability patterns
def with_retry(retry_policy: Optional[RetryPolicy] = None):
    """Decorator for adding retry logic to functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            policy = retry_policy or RetryPolicy()
            last_error = None
            
            for attempt in range(policy.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < policy.max_attempts - 1:
                        delay = policy.get_delay(attempt + 1)
                        time.sleep(delay)
                    else:
                        raise last_error
            
            raise last_error
        return wrapper
    return decorator


def create_job_record(
    job_id: str,
    job_type: str,
    payload: Dict[str, Any],
    retry_policy: Optional[RetryPolicy] = None
) -> JobRecord:
    """Create a new job record with default values."""
    return JobRecord(
        job_id=job_id,
        job_type=job_type,
        payload=payload,
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        retry_policy=retry_policy
    )