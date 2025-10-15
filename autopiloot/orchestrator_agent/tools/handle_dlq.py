"""
Handle DLQ tool for routing failed jobs to dead letter queue.
Implements TASK-ORCH-0005 with standardized DLQ entry creation and context preservation.
"""

import os
import sys
import json
from typing import Optional, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add core and config directories to path
from env_loader import get_required_env_var
from firestore_client import get_firestore_client
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class HandleDLQ(BaseTool):
    """
    Routes failed jobs to dead letter queue with structured context preservation.
    
    Creates standardized DLQ entries in Firestore with comprehensive failure
    information for debugging and potential manual recovery operations.
    """
    
    job_id: str = Field(
        ...,
        description="Unique identifier of the failed job"
    )
    
    job_type: str = Field(
        ...,
        description="Type of job that failed (e.g., 'channel_scrape', 'single_video', 'batch_summarize')"
    )
    
    failure_context: Dict[str, Any] = Field(
        ...,
        description="Failure context including: {'error_type': 'api_timeout', 'error_message': 'Request timeout after 30s', 'retry_count': 3, 'last_attempt_at': '2025-01-27T12:00:00Z', 'original_inputs': {...}}"
    )
    
    recovery_hints: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional recovery hints: {'manual_action_required': True, 'suggested_fix': 'Check API credentials', 'retry_after': '2025-01-28T00:00:00Z'}"
    )
    
    def run(self) -> str:
        """
        Creates a DLQ entry with comprehensive failure information.
        
        Returns:
            str: JSON string containing DLQ reference and routing status
            
        Raises:
            ValueError: If required failure context is missing
            RuntimeError: If Firestore operation fails
        """
        try:
            # Validate inputs
            self._validate_inputs()
            
            # Initialize Firestore client
            db = get_firestore_client()
            
            # Generate DLQ entry ID
            current_time = datetime.now(timezone.utc)
            dlq_id = f"{self.job_type}_{self.job_id}_{current_time.strftime('%Y%m%d_%H%M%S')}"
            
            # Check for existing DLQ entry to prevent duplicates
            existing_entry = db.collection('jobs_deadletter').document(dlq_id).get()
            
            if existing_entry.exists:
                return json.dumps({
                    "dlq_ref": f"jobs_deadletter/{dlq_id}",
                    "status": "already_exists",
                    "message": "Job already in dead letter queue"
                })
            
            # Prepare DLQ payload with standardized structure
            dlq_payload = {
                "dlq_id": dlq_id,
                "original_job_id": self.job_id,
                "job_type": self.job_type,
                "failure_context": self.failure_context,
                "recovery_hints": self.recovery_hints or {},
                "dlq_created_at": firestore.SERVER_TIMESTAMP,
                "dlq_created_by": "OrchestratorAgent",
                "status": "dead_letter",
                "processing_attempts": self.failure_context.get("retry_count", 0) + 1,  # Include original attempt
                "severity": self._calculate_severity(),
                "recovery_priority": self._calculate_recovery_priority()
            }
            
            # Add job-type specific metadata
            dlq_payload.update(self._build_job_specific_metadata())
            
            # Create DLQ document
            dlq_ref = db.collection('jobs_deadletter').document(dlq_id)
            dlq_ref.set(dlq_payload)
            
            # Clean up original job if it exists in active collections
            self._cleanup_active_job(db)
            
            # Log DLQ routing to audit trail
            audit_logger.log_job_dlq_routed(
                job_id=self.job_id,
                job_type=self.job_type,
                dlq_id=dlq_id,
                error_type=self.failure_context.get("error_type"),
                actor="OrchestratorAgent"
            )
            
            return json.dumps({
                "dlq_ref": f"jobs_deadletter/{dlq_id}",
                "dlq_id": dlq_id,
                "status": "routed_to_dlq",
                "original_job_id": self.job_id,
                "job_type": self.job_type,
                "severity": dlq_payload["severity"],
                "recovery_priority": dlq_payload["recovery_priority"],
                "processing_attempts": dlq_payload["processing_attempts"]
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to route job to DLQ: {str(e)}",
                "dlq_ref": None
            })
    
    def _validate_inputs(self):
        """Validate required fields in failure context."""
        required_fields = ["error_type", "error_message"]
        for field in required_fields:
            if field not in self.failure_context:
                raise ValueError(f"Missing required failure_context field: {field}")
        
        if not isinstance(self.failure_context, dict):
            raise ValueError("failure_context must be a dictionary")
    
    def _calculate_severity(self) -> str:
        """Calculate failure severity based on error type and context."""
        error_type = self.failure_context.get("error_type", "").lower()
        retry_count = self.failure_context.get("retry_count", 0)
        
        # High severity errors
        high_severity_errors = [
            "authorization_failed",
            "data_corruption",
            "security_violation",
            "system_critical"
        ]
        
        # Medium severity errors
        medium_severity_errors = [
            "quota_exceeded", 
            "budget_exceeded",
            "invalid_configuration",
            "dependency_failure"
        ]
        
        if error_type in high_severity_errors:
            return "high"
        elif error_type in medium_severity_errors:
            return "medium"
        elif retry_count >= 5:  # Many retries indicate persistent issue
            return "medium"
        else:
            return "low"
    
    def _calculate_recovery_priority(self) -> str:
        """Calculate recovery priority for manual intervention."""
        severity = self._calculate_severity()
        job_type = self.job_type.lower()
        
        # Real-time jobs get higher priority
        realtime_jobs = ["channel_scrape", "single_video", "single_summary"]
        
        if severity == "high":
            return "urgent"
        elif severity == "medium" and job_type in realtime_jobs:
            return "high"
        elif job_type in realtime_jobs:
            return "medium"
        else:
            return "low"
    
    def _build_job_specific_metadata(self) -> Dict[str, Any]:
        """Build job-type specific metadata for DLQ entry."""
        metadata = {}
        
        original_inputs = self.failure_context.get("original_inputs", {})
        
        if self.job_type == "channel_scrape":
            metadata["target_channels"] = original_inputs.get("channels", [])
            metadata["estimated_quota_impact"] = len(original_inputs.get("channels", [])) * 100
            
        elif self.job_type in ["single_video", "batch_transcribe"]:
            if "video_id" in original_inputs:
                metadata["video_id"] = original_inputs["video_id"]
            if "video_ids" in original_inputs:
                metadata["video_ids"] = original_inputs["video_ids"]
                metadata["batch_size"] = len(original_inputs["video_ids"])
            metadata["estimated_cost_impact"] = self._estimate_transcription_cost(original_inputs)
            
        elif self.job_type in ["single_summary", "batch_summarize"]:
            if "video_id" in original_inputs:
                metadata["video_id"] = original_inputs["video_id"]
            if "video_ids" in original_inputs:
                metadata["video_ids"] = original_inputs["video_ids"]
            metadata["target_platforms"] = original_inputs.get("platforms", ["drive"])
        
        return metadata
    
    def _estimate_transcription_cost(self, original_inputs: Dict[str, Any]) -> float:
        """Estimate cost impact of failed transcription job."""
        if "video_id" in original_inputs:
            return 0.5  # Estimate per video
        elif "video_ids" in original_inputs:
            return len(original_inputs["video_ids"]) * 0.5
        return 0.0
    
    def _cleanup_active_job(self, db):
        """Remove job from active collections after DLQ routing."""
        # Determine which agent collection to clean up
        agent_map = {
            "channel_scrape": "scraper",
            "sheet_backfill": "scraper",
            "single_video": "transcriber",
            "batch_transcribe": "transcriber",
            "single_summary": "summarizer",
            "batch_summarize": "summarizer"
        }
        
        agent = agent_map.get(self.job_type)
        if not agent:
            return  # Unknown job type, skip cleanup
        
        try:
            # Try to delete from active collection
            active_ref = db.collection('jobs').document(agent).collection('active').document(self.job_id)
            if active_ref.get().exists:
                active_ref.delete()
        except Exception:
            # Ignore cleanup errors - DLQ routing is more important
            pass
    

if __name__ == "__main__":
    # Test DLQ routing for failed transcription job
    print("Testing handle_dlq with failed transcription...")
    test_tool = HandleDLQ(
        job_id="transcribe_20250127_120000",
        job_type="single_video",
        failure_context={
            "error_type": "api_timeout",
            "error_message": "AssemblyAI API request timeout after 30 seconds",
            "retry_count": 3,
            "last_attempt_at": "2025-01-27T12:30:00Z",
            "original_inputs": {
                "video_id": "dQw4w9WgXcQ",
                "priority": "high"
            }
        },
        recovery_hints={
            "manual_action_required": True,
            "suggested_fix": "Check AssemblyAI API status and retry manually",
            "retry_after": "2025-01-27T18:00:00Z"
        }
    )
    
    try:
        result = test_tool.run()
        print("DLQ routing result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Success: Routed {data['original_job_id']} to DLQ")
            print(f"Severity: {data['severity']}, Priority: {data['recovery_priority']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting DLQ routing for authorization failure...")
    test_tool_auth = HandleDLQ(
        job_id="scrape_20250127_120000",
        job_type="channel_scrape",
        failure_context={
            "error_type": "authorization_failed",
            "error_message": "YouTube API key invalid or quota exceeded",
            "retry_count": 0,
            "original_inputs": {
                "channels": ["@AlexHormozi"],
                "limit_per_channel": 10
            }
        }
    )
    
    try:
        result = test_tool_auth.run()
        print("Authorization failure DLQ result:")
        print(result)
        
    except Exception as e:
        print(f"Auth test error: {str(e)}")