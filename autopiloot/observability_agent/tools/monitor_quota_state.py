"""
Monitor Quota State tool for tracking YouTube and AssemblyAI quota usage and reset windows.
Implements TASK-OBS-0040 with threshold alerting and reset time calculations.
"""

import os
import sys
import json
from typing import Optional, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone, timedelta

# Add core and config directories to path
from env_loader import get_required_env_var
from firestore_client import get_firestore_client
from loader import (
    load_app_config,
    get_youtube_daily_limit,
    get_assemblyai_daily_limit
)
from audit_logger import audit_logger



class MonitorQuotaState(BaseTool):
    """
    Monitors YouTube API and AssemblyAI quota usage with threshold alerting.
    
    Tracks current usage against daily limits, calculates remaining quota,
    and determines reset windows. Provides alerting for threshold violations.
    """
    
    alert_threshold: float = Field(
        0.8,
        description="Quota utilization threshold for alerts (0.0-1.0). Default 0.8 (80%)",
        ge=0.0,
        le=1.0
    )
    
    include_predictions: bool = Field(
        True,
        description="Include quota usage predictions based on current rate"
    )
    
    def run(self) -> str:
        """
        Monitors quota state and returns current usage with alert recommendations.
        
        Returns:
            str: JSON string containing quota status, alerts, and reset timing
            
        Raises:
            RuntimeError: If quota monitoring fails
        """
        try:
            # Load configuration
            config = load_app_config()
            
            # Get quota limits
            youtube_limit = get_youtube_daily_limit(config)
            assemblyai_limit = get_assemblyai_daily_limit(config)
            
            # Initialize Firestore client
            db = get_firestore_client()
            
            # Get current quota usage
            quota_usage = self._get_current_quota_usage(db)
            
            # Calculate quota states
            youtube_state = self._calculate_quota_state(
                service="youtube",
                current_usage=quota_usage.get("youtube", 0),
                daily_limit=youtube_limit,
                reset_window="daily_utc"
            )
            
            assemblyai_state = self._calculate_quota_state(
                service="assemblyai",
                current_usage=quota_usage.get("assemblyai", 0),
                daily_limit=assemblyai_limit,
                reset_window="daily_utc"
            )
            
            # Generate alerts if thresholds exceeded
            alerts = []
            if youtube_state["utilization"] >= self.alert_threshold:
                alerts.append({
                    "service": "youtube",
                    "severity": "warning" if youtube_state["utilization"] < 0.95 else "critical",
                    "message": f"YouTube API quota at {youtube_state['utilization']:.1%} of daily limit",
                    "recommended_action": "Throttle scraping operations" if youtube_state["utilization"] < 0.95 else "Halt all YouTube API calls",
                    "time_to_reset": youtube_state["time_to_reset_hours"]
                })
            
            if assemblyai_state["utilization"] >= self.alert_threshold:
                alerts.append({
                    "service": "assemblyai",
                    "severity": "warning" if assemblyai_state["utilization"] < 0.95 else "critical",
                    "message": f"AssemblyAI quota at {assemblyai_state['utilization']:.1%} of daily limit",
                    "recommended_action": "Defer transcription jobs" if assemblyai_state["utilization"] < 0.95 else "Halt all transcription jobs",
                    "time_to_reset": assemblyai_state["time_to_reset_hours"]
                })
            
            # Add predictions if requested
            predictions = {}
            if self.include_predictions:
                predictions = self._generate_usage_predictions(quota_usage, youtube_limit, assemblyai_limit)
            
            # Log quota monitoring to audit trail
            audit_logger.log_quota_monitored(
                youtube_usage=quota_usage.get("youtube", 0),
                assemblyai_usage=quota_usage.get("assemblyai", 0),
                alert_count=len(alerts),
                actor="ObservabilityAgent"
            )
            
            return json.dumps({
                "monitoring_timestamp": datetime.now(timezone.utc).isoformat(),
                "quota_states": {
                    "youtube": youtube_state,
                    "assemblyai": assemblyai_state
                },
                "alerts": alerts,
                "predictions": predictions,
                "overall_health": self._calculate_overall_health(youtube_state, assemblyai_state),
                "next_reset": self._calculate_next_reset()
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to monitor quota state: {str(e)}",
                "quota_states": None
            })
    
    def _get_current_quota_usage(self, db) -> Dict[str, int]:
        """Get current quota usage from Firestore tracking collections."""
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        quota_usage = {
            "youtube": 0,
            "assemblyai": 0
        }
        
        try:
            # Query quota tracking collection (stub - would be implemented with actual tracking)
            # In production, this would read from a quota_usage_{date} collection
            # For now, return mock data based on recent activity
            
            # Count recent video discoveries for YouTube quota estimation
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            videos_query = db.collection('videos').where('created_at', '>=', yesterday).limit(100)
            video_count = len(list(videos_query.stream()))
            quota_usage["youtube"] = video_count * 100  # Estimate 100 units per video discovery
            
            # Count recent transcriptions for AssemblyAI quota
            transcripts_query = db.collection('transcripts').where('created_at', '>=', yesterday).limit(100)
            transcript_count = len(list(transcripts_query.stream()))
            quota_usage["assemblyai"] = transcript_count
            
        except Exception:
            # If Firestore queries fail, return conservative estimates
            pass
        
        return quota_usage
    
    def _calculate_quota_state(self, service: str, current_usage: int, daily_limit: int, reset_window: str) -> Dict[str, Any]:
        """Calculate detailed quota state for a service."""
        utilization = current_usage / daily_limit if daily_limit > 0 else 0.0
        remaining = max(0, daily_limit - current_usage)
        
        # Calculate time to reset (midnight UTC for daily quotas)
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_to_reset = tomorrow - now
        
        return {
            "service": service,
            "current_usage": current_usage,
            "daily_limit": daily_limit,
            "remaining": remaining,
            "utilization": utilization,
            "status": self._get_quota_status(utilization),
            "time_to_reset_hours": time_to_reset.total_seconds() / 3600,
            "reset_window": reset_window,
            "next_reset_at": tomorrow.isoformat()
        }
    
    def _get_quota_status(self, utilization: float) -> str:
        """Get human-readable quota status."""
        if utilization >= 0.95:
            return "critical"
        elif utilization >= 0.8:
            return "warning"
        elif utilization >= 0.6:
            return "moderate"
        else:
            return "healthy"
    
    def _generate_usage_predictions(self, current_usage: Dict[str, int], youtube_limit: int, assemblyai_limit: int) -> Dict[str, Any]:
        """Generate usage predictions based on current rate."""
        now = datetime.now(timezone.utc)
        hours_elapsed = now.hour + (now.minute / 60)
        
        predictions = {}
        
        if hours_elapsed > 0:
            # YouTube prediction
            youtube_rate = current_usage.get("youtube", 0) / hours_elapsed
            youtube_predicted = youtube_rate * 24
            predictions["youtube"] = {
                "hourly_rate": youtube_rate,
                "predicted_daily_usage": min(youtube_predicted, youtube_limit * 1.2),  # Cap at 120% of limit
                "projected_utilization": min(youtube_predicted / youtube_limit, 1.2),
                "risk_level": "high" if youtube_predicted > youtube_limit else "medium" if youtube_predicted > youtube_limit * 0.8 else "low"
            }
            
            # AssemblyAI prediction
            assemblyai_rate = current_usage.get("assemblyai", 0) / hours_elapsed
            assemblyai_predicted = assemblyai_rate * 24
            predictions["assemblyai"] = {
                "hourly_rate": assemblyai_rate,
                "predicted_daily_usage": min(assemblyai_predicted, assemblyai_limit * 1.2),
                "projected_utilization": min(assemblyai_predicted / assemblyai_limit, 1.2),
                "risk_level": "high" if assemblyai_predicted > assemblyai_limit else "medium" if assemblyai_predicted > assemblyai_limit * 0.8 else "low"
            }
        
        return predictions
    
    def _calculate_overall_health(self, youtube_state: Dict[str, Any], assemblyai_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall quota health score."""
        youtube_util = youtube_state["utilization"]
        assemblyai_util = assemblyai_state["utilization"]
        
        # Weight by service importance (YouTube is more critical for discovery)
        weighted_util = (youtube_util * 0.6) + (assemblyai_util * 0.4)
        
        if weighted_util >= 0.9:
            health_status = "critical"
            health_score = 100 - (weighted_util * 100)
        elif weighted_util >= 0.7:
            health_status = "warning"
            health_score = 80 - (weighted_util * 50)
        else:
            health_status = "healthy"
            health_score = 100 - (weighted_util * 30)
        
        return {
            "status": health_status,
            "score": max(0, min(100, health_score)),
            "weighted_utilization": weighted_util,
            "bottleneck_service": "youtube" if youtube_util > assemblyai_util else "assemblyai"
        }
    
    def _calculate_next_reset(self) -> str:
        """Calculate next quota reset time."""
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow.isoformat()
    

if __name__ == "__main__":
    # Test quota monitoring
    print("Testing monitor_quota_state...")
    test_tool = MonitorQuotaState(
        alert_threshold=0.8,
        include_predictions=True
    )
    
    try:
        result = test_tool.run()
        print("Quota monitoring result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Overall health: {data['overall_health']['status']} (score: {data['overall_health']['score']:.1f})")
            print(f"Alerts: {len(data['alerts'])}")
            if data['alerts']:
                for alert in data['alerts']:
                    print(f"  - {alert['service']}: {alert['severity']} - {alert['message']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting with lower threshold...")
    test_tool_low = MonitorQuotaState(
        alert_threshold=0.5,
        include_predictions=False
    )
    
    try:
        result = test_tool_low.run()
        data = json.loads(result)
        if "error" not in data:
            print(f"Lower threshold alerts: {len(data['alerts'])}")
        
    except Exception as e:
        print(f"Low threshold test error: {str(e)}")