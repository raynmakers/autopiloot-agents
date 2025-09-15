"""
Audit logging utility for Autopiloot Agency.
Implements TASK-AUDIT-0041 requirements for tracking key actions in Firestore audit_logs collection.
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from google.cloud import firestore

# Add config directory to path for configuration imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'config'))

from env_loader import get_required_env_var


class AuditLogger:
    """
    Centralized audit logging utility for tracking key system actions.
    
    Implements TASK-AUDIT-0041 specification with comprehensive action tracking,
    no PII capture, and structured Firestore storage in audit_logs collection.
    """
    
    def __init__(self):
        """Initialize audit logger with Firestore client."""
        self._db = None
    
    def _get_firestore_client(self) -> firestore.Client:
        """Get or create Firestore client with lazy initialization."""
        if self._db is None:
            try:
                project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore access")
                self._db = firestore.Client(project=project_id)
            except Exception as e:
                print(f"Warning: Failed to initialize Firestore client for audit logging: {str(e)}")
                # Return None to indicate audit logging is disabled
                return None
        return self._db
    
    def write_audit_log(
        self, 
        actor: str, 
        action: str, 
        entity: str, 
        entity_id: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Write audit log entry to Firestore per TASK-AUDIT-0041 specification.
        
        Args:
            actor: System component or agent performing the action (e.g., "TranscriberAgent")
            action: Action being performed (e.g., "transcript_created", "alert_sent")  
            entity: Type of entity being acted upon (e.g., "transcript", "video", "slack_message")
            entity_id: Unique identifier of the entity (e.g., video_id, job_id)
            details: Optional additional context data (no PII allowed)
            
        Returns:
            bool: True if audit log written successfully, False if failed
            
        Note:
            Failures are logged but do not raise exceptions to avoid disrupting main workflows.
        """
        try:
            db = self._get_firestore_client()
            if db is None:
                return False
            
            # Create audit log entry per AuditLogEntry TypedDict specification
            timestamp = datetime.now(timezone.utc).isoformat()
            
            audit_entry = {
                "actor": actor,
                "action": action, 
                "entity": entity,
                "entity_id": entity_id,
                "timestamp": timestamp,
                "details": details or {}
            }
            
            # Write to audit_logs collection with auto-generated ID
            audit_ref = db.collection("audit_logs").document()
            audit_ref.set(audit_entry)
            
            return True
            
        except Exception as e:
            # Log error but don't raise exception to avoid disrupting main workflows
            print(f"Warning: Failed to write audit log entry: {str(e)}")
            return False
    
    def log_transcript_created(self, video_id: str, transcript_doc_ref: str, actor: str = "TranscriberAgent") -> bool:
        """Log transcript creation event."""
        return self.write_audit_log(
            actor=actor,
            action="transcript_created",
            entity="transcript", 
            entity_id=video_id,
            details={
                "transcript_doc_ref": transcript_doc_ref,
                "event_type": "transcription_completed"
            }
        )
    
    def log_summary_created(self, video_id: str, summary_doc_ref: str, actor: str = "SummarizerAgent") -> bool:
        """Log summary creation event."""
        return self.write_audit_log(
            actor=actor,
            action="summary_created", 
            entity="summary",
            entity_id=video_id,
            details={
                "summary_doc_ref": summary_doc_ref,
                "event_type": "summarization_completed"
            }
        )
    
    def log_slack_alert_sent(self, alert_type: str, channel: str, message_ts: str, actor: str = "AssistantAgent") -> bool:
        """Log Slack alert sending event."""
        return self.write_audit_log(
            actor=actor,
            action="alert_sent",
            entity="slack_message",
            entity_id=message_ts,
            details={
                "alert_type": alert_type,
                "channel": channel,
                "event_type": "notification_sent"
            }
        )
    
    def log_budget_alert(self, date: str, amount_spent: float, threshold_percentage: float, actor: str = "AssistantAgent") -> bool:
        """Log budget threshold alert event."""
        return self.write_audit_log(
            actor=actor,
            action="budget_alert_sent",
            entity="budget_threshold",
            entity_id=date,
            details={
                "amount_spent_usd": amount_spent,
                "threshold_percentage": threshold_percentage,
                "event_type": "budget_monitoring"
            }
        )
    
    def log_cost_updated(self, date: str, cost_usd: float, cost_type: str, actor: str = "TranscriberAgent") -> bool:
        """Log cost tracking update event."""
        return self.write_audit_log(
            actor=actor,
            action="cost_updated",
            entity="daily_costs",
            entity_id=date,
            details={
                "cost_usd": cost_usd,
                "cost_type": cost_type,
                "event_type": "cost_tracking"
            }
        )
    
    def log_video_discovered(self, video_id: str, source: str, actor: str = "ScraperAgent") -> bool:
        """Log video discovery event."""
        return self.write_audit_log(
            actor=actor,
            action="video_discovered",
            entity="video",
            entity_id=video_id,
            details={
                "source": source,
                "event_type": "content_discovery"
            }
        )
    
    def log_job_failed(self, job_id: str, job_type: str, error_message: str, actor: str = "System") -> bool:
        """Log job failure event for dead letter queue tracking."""
        return self.write_audit_log(
            actor=actor,
            action="job_failed", 
            entity="job",
            entity_id=job_id,
            details={
                "job_type": job_type,
                "error_message": error_message,
                "event_type": "system_failure"
            }
        )


# Global audit logger instance for easy import and usage
audit_logger = AuditLogger()


def write_audit_log(actor: str, action: str, entity: str, entity_id: str, details: Optional[Dict[str, Any]] = None) -> bool:
    """
    Convenience function for writing audit log entries.
    
    This is the main function referenced in TASK-AUDIT-0041 specification.
    """
    return audit_logger.write_audit_log(actor, action, entity, entity_id, details)


if __name__ == "__main__":
    # Test the audit logging functionality
    print("Testing AuditLogger functionality...")
    
    # Test basic audit logging
    success1 = write_audit_log(
        actor="TestActor",
        action="test_action",
        entity="test_entity", 
        entity_id="test_123",
        details={"test_field": "test_value"}
    )
    print(f"Basic audit log test: {'✅ PASSED' if success1 else '❌ FAILED'}")
    
    # Test transcript creation logging
    success2 = audit_logger.log_transcript_created(
        video_id="video_123",
        transcript_doc_ref="transcripts/video_123"
    )
    print(f"Transcript creation audit log: {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    # Test Slack alert logging
    success3 = audit_logger.log_slack_alert_sent(
        alert_type="budget_threshold",
        channel="#ops-autopiloot",
        message_ts="1234567890.123"
    )
    print(f"Slack alert audit log: {'✅ PASSED' if success3 else '❌ FAILED'}")
    
    # Test budget alert logging
    success4 = audit_logger.log_budget_alert(
        date="2025-09-15",
        amount_spent=4.25,
        threshold_percentage=85.0
    )
    print(f"Budget alert audit log: {'✅ PASSED' if success4 else '❌ FAILED'}")
    
    if all([success1, success2, success3, success4]):
        print("\n🎉 All audit logging tests passed!")
    else:
        print("\n⚠️  Some audit logging tests failed - check Firestore configuration")