"""
Enforce Policies tool for reliability policy enforcement and decision making.
Implements TASK-ORCH-0004 with centralized backoff, retry, and quota management.
"""

import os
import sys
import json
import math
from typing import Optional, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from datetime import datetime, timezone, timedelta

# Add config directory to path
from loader import (
    load_app_config,
    get_retry_max_attempts,
    get_retry_base_delay,
    get_youtube_daily_limit,
    get_assemblyai_daily_limit
)



class EnforcePolicies(BaseTool):
    """
    Centralized enforcement of reliability policies including retries, backoff, and quotas.
    
    Evaluates job context against configuration policies and returns actionable
    decisions for proceed, retry with delay, or dead letter queue routing.
    """
    
    job_context: Dict[str, Any] = Field(
        ...,
        description="Job context including: {'job_id': 'xyz', 'job_type': 'transcribe', 'retry_count': 2, 'last_attempt_at': '2025-01-27T10:00:00Z', 'error_type': 'quota_exceeded'}"
    )
    
    current_state: Dict[str, Any] = Field(
        ...,
        description="Current system state including: {'quota_usage': {'youtube': 8500}, 'daily_costs': {'transcription_usd': 3.50}, 'checkpoint_data': {...}}"
    )
    
    policy_overrides: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional policy overrides: {'max_attempts': 5, 'base_delay_sec': 120, 'quota_threshold': 0.9}"
    )
    
    def run(self) -> str:
        """
        Evaluates job context and returns policy enforcement decision.
        
        Returns:
            str: JSON string containing action decision and timing
            
        Raises:
            ValueError: If job context or current state is invalid
            RuntimeError: If policy evaluation fails
        """
        try:
            # Validate inputs
            self._validate_inputs()
            
            # Load configuration
            config = load_app_config()
            
            # Extract job information
            job_id = self.job_context.get("job_id")
            job_type = self.job_context.get("job_type")
            retry_count = self.job_context.get("retry_count", 0)
            error_type = self.job_context.get("error_type")
            last_attempt_str = self.job_context.get("last_attempt_at")
            
            # Parse last attempt timestamp
            last_attempt = None
            if last_attempt_str:
                try:
                    last_attempt = datetime.fromisoformat(last_attempt_str.replace('Z', '+00:00'))
                except ValueError:
                    last_attempt = datetime.now(timezone.utc)
            
            # Get policy configuration
            max_attempts = self.policy_overrides.get("max_attempts") if self.policy_overrides else None
            if max_attempts is None:
                max_attempts = get_retry_max_attempts(config)
            
            base_delay = self.policy_overrides.get("base_delay_sec") if self.policy_overrides else None
            if base_delay is None:
                base_delay = get_retry_base_delay(config)
            
            # Evaluate retry policy
            retry_decision = self._evaluate_retry_policy(retry_count, max_attempts, error_type)
            
            if retry_decision["action"] == "dlq":
                return json.dumps({
                    "action": "dlq",
                    "reason": retry_decision["reason"],
                    "job_id": job_id,
                    "retry_count": retry_count,
                    "max_attempts": max_attempts
                })
            
            # Evaluate quota constraints
            quota_decision = self._evaluate_quota_constraints(job_type, config)
            
            if quota_decision["action"] == "throttle":
                return json.dumps({
                    "action": "retry_in",
                    "delay_sec": quota_decision["retry_after_sec"],
                    "reason": quota_decision["reason"],
                    "job_id": job_id,
                    "quota_status": quota_decision["quota_status"]
                })
            
            # Calculate backoff delay for retries
            if retry_count > 0:
                backoff_delay = self._calculate_backoff_delay(retry_count, base_delay)
                
                # Check if enough time has passed since last attempt
                if last_attempt:
                    time_since_last = (datetime.now(timezone.utc) - last_attempt).total_seconds()
                    if time_since_last < backoff_delay:
                        remaining_delay = backoff_delay - time_since_last
                        return json.dumps({
                            "action": "retry_in",
                            "delay_sec": int(remaining_delay),
                            "reason": f"Backoff delay not yet satisfied (retry #{retry_count})",
                            "job_id": job_id,
                            "backoff_strategy": "exponential"
                        })
            
            # Evaluate checkpoint constraints
            checkpoint_decision = self._evaluate_checkpoint_constraints()
            
            if checkpoint_decision["action"] == "skip":
                return json.dumps({
                    "action": "skip",
                    "reason": checkpoint_decision["reason"],
                    "job_id": job_id,
                    "checkpoint_status": checkpoint_decision["checkpoint_status"]
                })
            
            # All policies satisfied - proceed
            return json.dumps({
                "action": "proceed",
                "reason": "All policy constraints satisfied",
                "job_id": job_id,
                "retry_count": retry_count,
                "policy_checks": {
                    "retry_policy": "passed",
                    "quota_constraints": "passed",
                    "backoff_timing": "satisfied",
                    "checkpoint_constraints": "passed"
                }
            })
            
        except Exception as e:
            return json.dumps({
                "error": f"Policy enforcement failed: {str(e)}",
                "action": "error"
            })
    
    def _validate_inputs(self):
        """Validate required fields in job context and current state."""
        required_job_fields = ["job_id", "job_type"]
        for field in required_job_fields:
            if field not in self.job_context:
                raise ValueError(f"Missing required job_context field: {field}")
        
        if not isinstance(self.current_state, dict):
            raise ValueError("current_state must be a dictionary")
    
    def _evaluate_retry_policy(self, retry_count: int, max_attempts: int, error_type: Optional[str]) -> Dict[str, Any]:
        """Evaluate whether job should be retried or sent to DLQ."""
        if retry_count >= max_attempts:
            return {
                "action": "dlq",
                "reason": f"Maximum retry attempts exceeded ({retry_count}/{max_attempts})"
            }
        
        # Check for terminal errors that shouldn't be retried
        terminal_errors = [
            "invalid_video_id",
            "video_too_long",
            "unsupported_format",
            "authorization_failed"
        ]
        
        if error_type in terminal_errors:
            return {
                "action": "dlq",
                "reason": f"Terminal error type: {error_type}"
            }
        
        return {
            "action": "retry",
            "reason": "Retry policy allows continuation"
        }
    
    def _evaluate_quota_constraints(self, job_type: str, config) -> Dict[str, Any]:
        """Evaluate quota usage and determine if job should be throttled."""
        quota_usage = self.current_state.get("quota_usage", {})
        
        # Get quota thresholds
        quota_threshold = self.policy_overrides.get("quota_threshold", 0.9) if self.policy_overrides else 0.9
        
        # Check YouTube API quota for scraping jobs
        if job_type in ["channel_scrape", "sheet_backfill"]:
            youtube_limit = get_youtube_daily_limit(config)
            youtube_used = quota_usage.get("youtube", 0)
            youtube_utilization = youtube_used / youtube_limit if youtube_limit > 0 else 0
            
            if youtube_utilization >= quota_threshold:
                # Calculate time until quota reset (typically midnight UTC)
                now = datetime.now(timezone.utc)
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                retry_after_sec = int((tomorrow - now).total_seconds())
                
                return {
                    "action": "throttle",
                    "reason": f"YouTube API quota threshold exceeded ({youtube_utilization:.1%})",
                    "retry_after_sec": retry_after_sec,
                    "quota_status": {
                        "used": youtube_used,
                        "limit": youtube_limit,
                        "utilization": youtube_utilization
                    }
                }
        
        # Check AssemblyAI quota for transcription jobs
        if job_type in ["single_video", "batch_transcribe"]:
            assemblyai_limit = get_assemblyai_daily_limit(config)
            assemblyai_used = quota_usage.get("assemblyai", 0)
            assemblyai_utilization = assemblyai_used / assemblyai_limit if assemblyai_limit > 0 else 0
            
            if assemblyai_utilization >= quota_threshold:
                # Calculate time until quota reset
                now = datetime.now(timezone.utc)
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                retry_after_sec = int((tomorrow - now).total_seconds())
                
                return {
                    "action": "throttle",
                    "reason": f"AssemblyAI quota threshold exceeded ({assemblyai_utilization:.1%})",
                    "retry_after_sec": retry_after_sec,
                    "quota_status": {
                        "used": assemblyai_used,
                        "limit": assemblyai_limit,
                        "utilization": assemblyai_utilization
                    }
                }
        
        return {
            "action": "proceed",
            "reason": "Quota constraints satisfied"
        }
    
    def _calculate_backoff_delay(self, retry_count: int, base_delay: int) -> int:
        """Calculate exponential backoff delay."""
        # Exponential backoff: base_delay * (2 ^ retry_count)
        # Cap at 24 hours (86400 seconds)
        delay = base_delay * (2 ** retry_count)
        return min(delay, 86400)
    
    def _evaluate_checkpoint_constraints(self) -> Dict[str, Any]:
        """Evaluate checkpoint-based constraints."""
        checkpoint_data = self.current_state.get("checkpoint_data", {})
        
        # For now, assume checkpoints are satisfied
        # In production, this would check lastPublishedAt, processing windows, etc.
        return {
            "action": "proceed",
            "reason": "Checkpoint constraints satisfied",
            "checkpoint_status": checkpoint_data
        }


if __name__ == "__main__":
    # Test retry policy enforcement
    print("Testing enforce_policies with retry scenario...")
    test_tool = EnforcePolicies(
        job_context={
            "job_id": "transcribe_20250127_120000",
            "job_type": "single_video",
            "retry_count": 2,
            "last_attempt_at": "2025-01-27T12:00:00Z",
            "error_type": "api_timeout"
        },
        current_state={
            "quota_usage": {
                "youtube": 5000,
                "assemblyai": 25
            },
            "daily_costs": {
                "transcription_usd": 2.50
            }
        }
    )
    
    try:
        result = test_tool.run()
        print("Policy enforcement result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Action: {data['action']}")
            print(f"Reason: {data['reason']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting with quota threshold exceeded...")
    test_tool_quota = EnforcePolicies(
        job_context={
            "job_id": "scrape_20250127_120000",
            "job_type": "channel_scrape",
            "retry_count": 0,
            "error_type": "quota_exceeded"
        },
        current_state={
            "quota_usage": {
                "youtube": 9500,  # Close to 10k limit
                "assemblyai": 10
            }
        }
    )
    
    try:
        result = test_tool_quota.run()
        print("Quota enforcement result:")
        print(result)
        
    except Exception as e:
        print(f"Quota test error: {str(e)}")