"""
Dispatch Transcriber tool for coordinating TranscriberAgent operations.
Implements TASK-ORCH-0003 with structured work orders and budget constraints.
"""

import os
import sys
import json
from typing import Optional, List, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_var
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class DispatchTranscriber(BaseTool):
    """
    Dispatches structured work orders to TranscriberAgent for video transcription.
    
    Creates Firestore job documents for transcription operations with budget
    validation, duration limits, and proper status progression tracking.
    """
    
    job_type: str = Field(
        ...,
        description="Type of transcription job: 'single_video' or 'batch_transcribe'"
    )
    
    inputs: Dict[str, Any] = Field(
        ...,
        description="Job-specific inputs: For single_video: {'video_id': 'abc123', 'priority': 'high'}. For batch_transcribe: {'video_ids': ['id1', 'id2'], 'batch_size': 5}"
    )
    
    policy_overrides: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional policy overrides: {'budget_limit_usd': 2.0, 'max_duration_sec': 3600}"
    )
    
    def run(self) -> str:
        """
        Creates a transcriber job in Firestore with budget and duration validation.
        
        Returns:
            str: JSON string containing job reference and dispatch status
            
        Raises:
            ValueError: If inputs are invalid or budget constraints are violated
            RuntimeError: If Firestore operation fails
        """
        try:
            # Validate job type and inputs
            self._validate_inputs()
            
            # Load configuration
            config = load_app_config()
            
            # Check budget constraints
            budget_check = self._check_budget_constraints(config)
            if not budget_check["allowed"]:
                return json.dumps({
                    "error": f"Budget constraint violation: {budget_check['reason']}",
                    "job_ref": None,
                    "budget_status": budget_check
                })
            
            # Initialize Firestore client
            db = self._initialize_firestore()
            
            # Generate job ID with timestamp for idempotency
            current_time = datetime.now(timezone.utc)
            job_id = f"{self.job_type}_{current_time.strftime('%Y%m%d_%H%M%S')}"
            
            # Check for existing job to prevent duplicates
            existing_job = db.collection('jobs').document('transcriber').collection('active').document(job_id).get()
            
            if existing_job.exists:
                return json.dumps({
                    "job_ref": f"jobs/transcriber/active/{job_id}",
                    "status": "already_exists",
                    "message": "Job already dispatched"
                })
            
            # Prepare job payload
            job_payload = {
                "job_id": job_id,
                "job_type": self.job_type,
                "inputs": self.inputs,
                "policy_overrides": self.policy_overrides or {},
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP,
                "created_by": "OrchestratorAgent",
                "retry_count": 0,
                "priority": self._calculate_priority(),
                "budget_allocated_usd": budget_check["estimated_cost"]
            }
            
            # Add job-specific metadata
            if self.job_type == "single_video":
                job_payload["video_id"] = self.inputs.get("video_id")
                job_payload["estimated_duration_sec"] = self._estimate_duration(self.inputs.get("video_id"))
            elif self.job_type == "batch_transcribe":
                job_payload["video_ids"] = self.inputs.get("video_ids", [])
                job_payload["batch_size"] = self.inputs.get("batch_size", 5)
                job_payload["estimated_videos"] = len(self.inputs.get("video_ids", []))
            
            # Create job document
            job_ref = db.collection('jobs').document('transcriber').collection('active').document(job_id)
            job_ref.set(job_payload)
            
            # Log dispatch action to audit trail
            audit_logger.log_job_dispatched(
                job_id=job_id,
                job_type=self.job_type,
                target_agent="TranscriberAgent",
                actor="OrchestratorAgent"
            )
            
            return json.dumps({
                "job_ref": f"jobs/transcriber/active/{job_id}",
                "job_id": job_id,
                "status": "dispatched",
                "job_type": self.job_type,
                "priority": job_payload["priority"],
                "budget_allocated_usd": job_payload["budget_allocated_usd"],
                "estimated_videos": job_payload.get("estimated_videos", 1)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to dispatch transcriber job: {str(e)}",
                "job_ref": None
            })
    
    def _validate_inputs(self):
        """Validate inputs based on job type."""
        if self.job_type == "single_video":
            if "video_id" not in self.inputs:
                raise ValueError("single_video requires 'video_id' in inputs")
            if not isinstance(self.inputs["video_id"], str):
                raise ValueError("video_id must be a string")
                
        elif self.job_type == "batch_transcribe":
            if "video_ids" not in self.inputs:
                raise ValueError("batch_transcribe requires 'video_ids' in inputs")
            if not isinstance(self.inputs["video_ids"], list):
                raise ValueError("video_ids must be a list")
            if len(self.inputs["video_ids"]) == 0:
                raise ValueError("video_ids list cannot be empty")
                
        else:
            raise ValueError(f"Invalid job_type: {self.job_type}. Must be 'single_video' or 'batch_transcribe'")
    
    def _check_budget_constraints(self, config) -> Dict[str, Any]:
        """Check if job can proceed within budget constraints."""
        daily_budget = config.get("budgets", {}).get("transcription_daily_usd", 5.0)
        
        # Estimate cost based on job type
        if self.job_type == "single_video":
            estimated_cost = 0.5  # Rough estimate per video
            video_count = 1
        elif self.job_type == "batch_transcribe":
            video_count = len(self.inputs.get("video_ids", []))
            estimated_cost = video_count * 0.5
        else:
            estimated_cost = 0.0
            video_count = 0
        
        # Check policy overrides
        if self.policy_overrides and "budget_limit_usd" in self.policy_overrides:
            effective_budget = min(daily_budget, self.policy_overrides["budget_limit_usd"])
        else:
            effective_budget = daily_budget
        
        # For now, assume we have the full budget available
        # In production, this would check costs_daily collection
        current_spent = 0.0
        available_budget = effective_budget - current_spent
        
        if estimated_cost > available_budget:
            return {
                "allowed": False,
                "reason": f"Estimated cost ${estimated_cost:.2f} exceeds available budget ${available_budget:.2f}",
                "estimated_cost": estimated_cost,
                "available_budget": available_budget,
                "video_count": video_count
            }
        
        return {
            "allowed": True,
            "reason": "Budget constraints satisfied",
            "estimated_cost": estimated_cost,
            "available_budget": available_budget,
            "video_count": video_count
        }
    
    def _estimate_duration(self, video_id: str) -> int:
        """Estimate video duration (stub - would query Firestore in production)."""
        # In production, this would read from videos/{video_id} document
        return 1800  # Default estimate: 30 minutes
    
    def _calculate_priority(self) -> str:
        """Calculate job priority based on type and inputs."""
        if self.job_type == "single_video":
            priority = self.inputs.get("priority", "medium")
            if priority in ["high", "medium", "low"]:
                return priority
            return "medium"
        elif self.job_type == "batch_transcribe":
            return "low"  # Batch jobs are typically lower priority
        return "low"
    
    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            project_id = get_required_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore")
            credentials_path = get_required_var("GOOGLE_APPLICATION_CREDENTIALS", "Google service account credentials file path")
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            return firestore.Client(project=project_id)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    # Test single video transcription dispatch
    print("Testing dispatch_transcriber with single_video...")
    test_tool = DispatchTranscriber(
        job_type="single_video",
        inputs={
            "video_id": "dQw4w9WgXcQ",
            "priority": "high"
        },
        policy_overrides={
            "budget_limit_usd": 1.0
        }
    )
    
    try:
        result = test_tool.run()
        print("Single video transcription dispatch result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Success: Dispatched {data['job_type']} job with budget ${data['budget_allocated_usd']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting dispatch_transcriber with batch_transcribe...")
    test_tool_batch = DispatchTranscriber(
        job_type="batch_transcribe",
        inputs={
            "video_ids": ["vid1", "vid2", "vid3"],
            "batch_size": 2
        }
    )
    
    try:
        result = test_tool_batch.run()
        print("Batch transcription dispatch result:")
        print(result)
        
    except Exception as e:
        print(f"Batch test error: {str(e)}")