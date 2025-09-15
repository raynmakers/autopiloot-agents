"""
Plan Daily Run tool for orchestrating daily content processing operations.
Implements TASK-ORCH-0002 with quota-aware planning and checkpoint management.
"""

import os
import sys
import json
from typing import Optional, List, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from loader import (
    load_app_config, 
    get_youtube_daily_limit, 
    get_assemblyai_daily_limit,
    get_retry_base_delay,
    get_retry_max_attempts
)

load_dotenv()


class PlanDailyRun(BaseTool):
    """
    Computes the actionable plan for today's content processing run.
    
    Analyzes configuration, quotas, budgets, and checkpoint state to determine
    what channels to process, limits per channel, and operational windows.
    Respects daily spend limits, YouTube API quotas, and checkpoint-based resumption.
    """
    
    target_channels: Optional[List[str]] = Field(
        None,
        description="Optional list of channel handles to override config (e.g., ['@AlexHormozi']). Uses config default if not specified."
    )
    
    max_videos_per_channel: Optional[int] = Field(
        None,
        description="Optional override for daily video limit per channel. Uses config default if not specified.",
        ge=0
    )
    
    def run(self) -> str:
        """
        Generates a daily processing plan based on configuration and current state.
        
        Returns:
            str: JSON string containing the daily plan with channels, limits, windows, and checkpoints
            
        Raises:
            ValueError: If configuration is invalid or missing required fields
            RuntimeError: If plan generation fails
        """
        try:
            # Load configuration
            config = load_app_config()
            
            # Determine target channels
            channels = self.target_channels or config.get("scraper", {}).get("handles", ["@AlexHormozi"])
            
            # Determine per-channel limits
            per_channel_limit = self.max_videos_per_channel or config.get("scraper", {}).get("daily_limit_per_channel", 10)
            
            # Get quota information
            youtube_quota = get_youtube_daily_limit(config)
            assemblyai_limit = get_assemblyai_daily_limit(config)
            
            # Get retry configuration
            max_attempts = get_retry_max_attempts(config)
            base_delay = get_retry_base_delay(config)
            
            # Get budget constraints
            transcription_budget = config.get("budgets", {}).get("transcription_daily_usd", 5.0)
            
            # Calculate operational windows
            current_time = datetime.now(timezone.utc)
            
            # Define processing windows based on European timezone for scheduling
            windows = [
                "scraping_window: 01:00-02:00 Europe/Amsterdam",
                "transcription_window: 02:00-06:00 Europe/Amsterdam", 
                "summarization_window: 06:00-08:00 Europe/Amsterdam"
            ]
            
            # Generate checkpoint information (stub for now - would read from Firestore in production)
            checkpoints = {
                "last_scrape_completed": None,  # Would be loaded from Firestore
                "last_published_at": {},  # Per-channel checkpoint: channel_id -> timestamp
                "pending_transcriptions": 0,  # Count of jobs in transcription queue
                "daily_quota_used": {
                    "youtube_api_units": 0,  # Would be calculated from quota tracking
                    "assemblyai_transcriptions": 0,  # Would be loaded from costs_daily collection
                    "transcription_cost_usd": 0.0
                }
            }
            
            # Calculate estimated resource requirements
            total_videos_planned = len(channels) * per_channel_limit
            estimated_quota_usage = total_videos_planned * 100  # Rough estimate: 100 units per video discovery
            
            # Generate warnings if approaching limits
            warnings = []
            if estimated_quota_usage > youtube_quota * 0.8:
                warnings.append(f"Estimated quota usage ({estimated_quota_usage}) approaching YouTube daily limit ({youtube_quota})")
            
            if total_videos_planned > assemblyai_limit:
                warnings.append(f"Planned videos ({total_videos_planned}) exceed AssemblyAI daily limit ({assemblyai_limit})")
            
            # Construct the daily plan
            daily_plan = {
                "plan_generated_at": current_time.isoformat(),
                "channels": channels,
                "per_channel_limit": per_channel_limit,
                "total_videos_planned": total_videos_planned,
                "windows": windows,
                "checkpoints": checkpoints,
                "resource_limits": {
                    "youtube_daily_quota": youtube_quota,
                    "assemblyai_daily_limit": assemblyai_limit,
                    "transcription_budget_usd": transcription_budget,
                    "estimated_quota_usage": estimated_quota_usage
                },
                "retry_policy": {
                    "max_attempts": max_attempts,
                    "base_delay_sec": base_delay,
                    "backoff_strategy": "exponential"
                },
                "warnings": warnings,
                "operational_status": "planned"
            }
            
            return json.dumps(daily_plan, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to generate daily plan: {str(e)}",
                "plan": None
            })


if __name__ == "__main__":
    # Test the tool with default configuration
    print("Testing plan_daily_run with default config...")
    test_tool = PlanDailyRun()
    
    try:
        result = test_tool.run()
        print("Plan Daily Run test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Success: Generated plan for {len(data['channels'])} channels")
            print(f"Total videos planned: {data['total_videos_planned']}")
            print(f"Warnings: {len(data['warnings'])}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting with custom parameters...")
    test_tool_custom = PlanDailyRun(
        target_channels=["@TestChannel1", "@TestChannel2"],
        max_videos_per_channel=5
    )
    
    try:
        result = test_tool_custom.run()
        data = json.loads(result)
        if "error" not in data:
            print(f"Custom test: {len(data['channels'])} channels, {data['per_channel_limit']} videos per channel")
        else:
            print(f"Custom test error: {data['error']}")
            
    except Exception as e:
        print(f"Custom test error: {str(e)}")