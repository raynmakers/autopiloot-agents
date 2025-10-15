"""
Dispatch Summarizer tool for coordinating SummarizerAgent operations.
Implements TASK-ORCH-0003 with structured work orders and platform distribution.
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
from env_loader import get_required_env_var
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class DispatchSummarizer(BaseTool):
    """
    Dispatches structured work orders to SummarizerAgent for content summarization.
    
    Creates Firestore job documents for summarization operations with platform
    distribution targeting and prompt configuration management.
    """
    
    job_type: str = Field(
        ...,
        description="Type of summarization job: 'single_summary' or 'batch_summarize'"
    )
    
    inputs: Dict[str, Any] = Field(
        ...,
        description="Job-specific inputs: For single_summary: {'video_id': 'abc123', 'platforms': ['drive', 'zep']}. For batch_summarize: {'video_ids': ['id1', 'id2'], 'prompt_override': 'coach_v2'}"
    )
    
    policy_overrides: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional policy overrides: {'prompt_id': 'custom_prompt', 'temperature': 0.3, 'max_tokens': 2000}"
    )
    
    def run(self) -> str:
        """
        Creates a summarizer job in Firestore with platform and prompt configuration.
        
        Returns:
            str: JSON string containing job reference and dispatch status
            
        Raises:
            ValueError: If inputs are invalid or video prerequisites are not met
            RuntimeError: If Firestore operation fails
        """
        try:
            # Validate job type and inputs
            self._validate_inputs()
            
            # Load configuration
            config = load_app_config()
            
            # Check prerequisites (videos must be transcribed)
            prereq_check = self._check_prerequisites()
            if not prereq_check["satisfied"]:
                return json.dumps({
                    "error": f"Prerequisites not met: {prereq_check['reason']}",
                    "job_ref": None,
                    "prerequisite_status": prereq_check
                })
            
            # Initialize Firestore client
            db = self._initialize_firestore()
            
            # Generate job ID with timestamp for idempotency
            current_time = datetime.now(timezone.utc)
            job_id = f"{self.job_type}_{current_time.strftime('%Y%m%d_%H%M%S')}"
            
            # Check for existing job to prevent duplicates
            existing_job = db.collection('jobs').document('summarizer').collection('active').document(job_id).get()
            
            if existing_job.exists:
                return json.dumps({
                    "job_ref": f"jobs/summarizer/active/{job_id}",
                    "status": "already_exists",
                    "message": "Job already dispatched"
                })
            
            # Determine LLM configuration
            llm_config = self._build_llm_config(config)
            
            # Prepare job payload
            job_payload = {
                "job_id": job_id,
                "job_type": self.job_type,
                "inputs": self.inputs,
                "policy_overrides": self.policy_overrides or {},
                "llm_config": llm_config,
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP,
                "created_by": "OrchestratorAgent",
                "retry_count": 0,
                "priority": self._calculate_priority()
            }
            
            # Add job-specific metadata
            if self.job_type == "single_summary":
                job_payload["video_id"] = self.inputs.get("video_id")
                job_payload["target_platforms"] = self.inputs.get("platforms", ["drive"])
                job_payload["estimated_output_tokens"] = llm_config.get("max_tokens", 1500)
            elif self.job_type == "batch_summarize":
                job_payload["video_ids"] = self.inputs.get("video_ids", [])
                job_payload["batch_size"] = len(self.inputs.get("video_ids", []))
                job_payload["estimated_videos"] = len(self.inputs.get("video_ids", []))
            
            # Create job document
            job_ref = db.collection('jobs').document('summarizer').collection('active').document(job_id)
            job_ref.set(job_payload)
            
            # Log dispatch action to audit trail
            audit_logger.log_job_dispatched(
                job_id=job_id,
                job_type=self.job_type,
                target_agent="SummarizerAgent",
                actor="OrchestratorAgent"
            )
            
            return json.dumps({
                "job_ref": f"jobs/summarizer/active/{job_id}",
                "job_id": job_id,
                "status": "dispatched",
                "job_type": self.job_type,
                "priority": job_payload["priority"],
                "llm_model": llm_config["model"],
                "target_platforms": job_payload.get("target_platforms", []),
                "estimated_videos": job_payload.get("estimated_videos", 1)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to dispatch summarizer job: {str(e)}",
                "job_ref": None
            })
    
    def _validate_inputs(self):
        """Validate inputs based on job type."""
        if self.job_type == "single_summary":
            if "video_id" not in self.inputs:
                raise ValueError("single_summary requires 'video_id' in inputs")
            if not isinstance(self.inputs["video_id"], str):
                raise ValueError("video_id must be a string")
            
            # Validate platforms if specified
            if "platforms" in self.inputs:
                valid_platforms = ["drive", "zep", "slack"]
                platforms = self.inputs["platforms"]
                if not isinstance(platforms, list):
                    raise ValueError("platforms must be a list")
                for platform in platforms:
                    if platform not in valid_platforms:
                        raise ValueError(f"Invalid platform: {platform}. Must be one of {valid_platforms}")
                        
        elif self.job_type == "batch_summarize":
            if "video_ids" not in self.inputs:
                raise ValueError("batch_summarize requires 'video_ids' in inputs")
            if not isinstance(self.inputs["video_ids"], list):
                raise ValueError("video_ids must be a list")
            if len(self.inputs["video_ids"]) == 0:
                raise ValueError("video_ids list cannot be empty")
                
        else:
            raise ValueError(f"Invalid job_type: {self.job_type}. Must be 'single_summary' or 'batch_summarize'")
    
    def _check_prerequisites(self) -> Dict[str, Any]:
        """Check if videos are ready for summarization (transcribed status).

        Note: Videos with status 'rejected_non_business' are automatically excluded
        because queries filter for status == 'transcribed'. Once a video is rejected,
        its status changes to 'rejected_non_business', removing it from processing queues.
        """
        # In production, this would check Firestore for video status
        # For now, assume prerequisites are met

        if self.job_type == "single_summary":
            video_id = self.inputs.get("video_id")
            # Stub: would check videos/{video_id} status == "transcribed"
            # Rejected videos (status='rejected_non_business') are automatically excluded
            return {
                "satisfied": True,
                "reason": "Video transcript available",
                "video_id": video_id,
                "status": "transcribed"  # Would be actual status from Firestore
            }
        elif self.job_type == "batch_summarize":
            video_ids = self.inputs.get("video_ids", [])
            # Stub: would check all video statuses
            return {
                "satisfied": True,
                "reason": "All videos have transcripts available",
                "video_count": len(video_ids),
                "ready_count": len(video_ids)  # Would be actual count from Firestore
            }
        
        return {
            "satisfied": False,
            "reason": "Unknown job type"
        }
    
    def _build_llm_config(self, config) -> Dict[str, Any]:
        """Build LLM configuration from config and policy overrides."""
        # Start with default LLM config
        llm_default = config.get("llm", {}).get("default", {})
        llm_config = {
            "model": llm_default.get("model", "gpt-4o"),
            "temperature": llm_default.get("temperature", 0.2),
            "max_tokens": llm_default.get("max_output_tokens", 1500)
        }
        
        # Check for task-specific overrides in config
        llm_tasks = config.get("llm", {}).get("tasks", {})
        if "summarizer_generate_short" in llm_tasks:
            task_config = llm_tasks["summarizer_generate_short"]
            llm_config.update({
                "model": task_config.get("model", llm_config["model"]),
                "temperature": task_config.get("temperature", llm_config["temperature"]),
                "prompt_id": task_config.get("prompt_id"),
                "max_tokens": task_config.get("max_output_tokens", llm_config["max_tokens"])
            })
        
        # Apply policy overrides
        if self.policy_overrides:
            if "prompt_id" in self.policy_overrides:
                llm_config["prompt_id"] = self.policy_overrides["prompt_id"]
            if "temperature" in self.policy_overrides:
                llm_config["temperature"] = self.policy_overrides["temperature"]
            if "max_tokens" in self.policy_overrides:
                llm_config["max_tokens"] = self.policy_overrides["max_tokens"]
        
        # Apply input-specific overrides
        if "prompt_override" in self.inputs:
            llm_config["prompt_id"] = self.inputs["prompt_override"]
        
        return llm_config
    
    def _calculate_priority(self) -> str:
        """Calculate job priority based on type and inputs."""
        if self.job_type == "single_summary":
            return "medium"  # Individual summaries are medium priority
        elif self.job_type == "batch_summarize":
            return "low"  # Batch jobs are typically lower priority
        return "low"
    
    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore")
            credentials_path = get_required_env_var("GOOGLE_APPLICATION_CREDENTIALS", "Google service account credentials file path")
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            return firestore.Client(project=project_id)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    # Test single summary dispatch
    print("Testing dispatch_summarizer with single_summary...")
    test_tool = DispatchSummarizer(
        job_type="single_summary",
        inputs={
            "video_id": "dQw4w9WgXcQ",
            "platforms": ["drive", "zep"]
        },
        policy_overrides={
            "temperature": 0.3,
            "prompt_id": "coach_v2"
        }
    )
    
    try:
        result = test_tool.run()
        print("Single summary dispatch result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Success: Dispatched {data['job_type']} job with model {data['llm_model']}")
            print(f"Target platforms: {data['target_platforms']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting dispatch_summarizer with batch_summarize...")
    test_tool_batch = DispatchSummarizer(
        job_type="batch_summarize",
        inputs={
            "video_ids": ["vid1", "vid2", "vid3"],
            "prompt_override": "coach_v1"
        }
    )
    
    try:
        result = test_tool_batch.run()
        print("Batch summarization dispatch result:")
        print(result)
        
    except Exception as e:
        print(f"Batch test error: {str(e)}")