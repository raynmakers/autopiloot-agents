"""
Dispatch Scraper tool for coordinating ScraperAgent operations.
Implements TASK-ORCH-0003 with structured work orders and idempotency.
"""

import os
import sys
import json
from typing import Optional, List, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone

# Add core and config directories to path
from env_loader import get_required_env_var
from firestore_client import get_firestore_client
from loader import load_app_config
from audit_logger import audit_logger



class DispatchScraper(BaseTool):
    """
    Dispatches structured work orders to ScraperAgent for content discovery.
    
    Creates Firestore job documents for scraping operations with proper
    idempotency checks and status tracking. Supports both channel scraping
    and Google Sheets backfill processing.
    """
    
    job_type: str = Field(
        ...,
        description="Type of scraping job: 'channel_scrape' or 'sheet_backfill'"
    )
    
    inputs: Dict[str, Any] = Field(
        ...,
        description="Job-specific inputs: For channel_scrape: {'channels': ['@Handle'], 'limit_per_channel': 10}. For sheet_backfill: {'sheet_id': 'abc123', 'range': 'Sheet1!A:D'}"
    )
    
    policy_overrides: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional policy overrides: {'retry_max_attempts': 5, 'timeout_sec': 300}"
    )
    
    def run(self) -> str:
        """
        Creates a scraper job in Firestore with idempotency protection.
        
        Returns:
            str: JSON string containing job reference and dispatch status
            
        Raises:
            ValueError: If inputs are invalid for the specified job type
            RuntimeError: If Firestore operation fails
        """
        try:
            # Validate job type and inputs
            self._validate_inputs()
            
            # Load configuration
            config = load_app_config()
            
            # Initialize Firestore client
            db = get_firestore_client()
            
            # Generate job ID with timestamp for idempotency
            current_time = datetime.now(timezone.utc)
            job_id = f"{self.job_type}_{current_time.strftime('%Y%m%d_%H%M%S')}"
            
            # Check for existing job to prevent duplicates
            existing_job = db.collection('jobs').document('scraper').collection('active').document(job_id).get()
            
            if existing_job.exists:
                return json.dumps({
                    "job_ref": f"jobs/scraper/active/{job_id}",
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
                "priority": self._calculate_priority()
            }
            
            # Add job-specific metadata
            if self.job_type == "channel_scrape":
                job_payload["estimated_quota_usage"] = len(self.inputs.get("channels", [])) * 100
                job_payload["target_channels"] = self.inputs.get("channels", [])
            elif self.job_type == "sheet_backfill":
                job_payload["sheet_id"] = self.inputs.get("sheet_id")
                job_payload["sheet_range"] = self.inputs.get("range", "Sheet1!A:D")
            
            # Create job document
            job_ref = db.collection('jobs').document('scraper').collection('active').document(job_id)
            job_ref.set(job_payload)
            
            # Log dispatch action to audit trail
            audit_logger.log_job_dispatched(
                job_id=job_id,
                job_type=self.job_type,
                target_agent="ScraperAgent",
                actor="OrchestratorAgent"
            )
            
            return json.dumps({
                "job_ref": f"jobs/scraper/active/{job_id}",
                "job_id": job_id,
                "status": "dispatched",
                "job_type": self.job_type,
                "priority": job_payload["priority"],
                "estimated_quota_usage": job_payload.get("estimated_quota_usage", 0)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to dispatch scraper job: {str(e)}",
                "job_ref": None
            })
    
    def _validate_inputs(self):
        """Validate inputs based on job type."""
        if self.job_type == "channel_scrape":
            if "channels" not in self.inputs:
                raise ValueError("channel_scrape requires 'channels' in inputs")
            if not isinstance(self.inputs["channels"], list):
                raise ValueError("channels must be a list")
            if len(self.inputs["channels"]) == 0:
                raise ValueError("channels list cannot be empty")
                
        elif self.job_type == "sheet_backfill":
            if "sheet_id" not in self.inputs:
                raise ValueError("sheet_backfill requires 'sheet_id' in inputs")
            if not isinstance(self.inputs["sheet_id"], str):
                raise ValueError("sheet_id must be a string")
                
        else:
            raise ValueError(f"Invalid job_type: {self.job_type}. Must be 'channel_scrape' or 'sheet_backfill'")
    
    def _calculate_priority(self) -> str:
        """Calculate job priority based on type and inputs."""
        if self.job_type == "channel_scrape":
            return "high"  # Real-time channel discovery is high priority
        elif self.job_type == "sheet_backfill":
            return "medium"  # Backfill can be processed with lower priority
        return "low"
    

if __name__ == "__main__":
    # Test channel scrape dispatch
    print("Testing dispatch_scraper with channel_scrape...")
    test_tool = DispatchScraper(
        job_type="channel_scrape",
        inputs={
            "channels": ["@AlexHormozi"],
            "limit_per_channel": 10
        },
        policy_overrides={
            "retry_max_attempts": 3
        }
    )
    
    try:
        result = test_tool.run()
        print("Channel scrape dispatch result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Success: Dispatched {data['job_type']} job with ID {data['job_id']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting dispatch_scraper with sheet_backfill...")
    test_tool_sheet = DispatchScraper(
        job_type="sheet_backfill",
        inputs={
            "sheet_id": "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789",
            "range": "Sheet1!A:D"
        }
    )
    
    try:
        result = test_tool_sheet.run()
        print("Sheet backfill dispatch result:")
        print(result)
        
    except Exception as e:
        print(f"Sheet test error: {str(e)}")