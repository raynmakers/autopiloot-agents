import os
import json
from typing import Optional
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool


class MonitorTranscriptionBudget(BaseTool):
    """
    Monitor daily transcription spending against $5 budget limit.
    Prevents processing when threshold is reached for cost control.
    """
    
    estimated_cost_usd: Optional[float] = Field(
        default=None, 
        description="Optional estimated cost to check if it would exceed budget"
    )
    
    def run(self) -> str:
        """
        Check current daily transcription spending and budget status.
        
        Returns:
            JSON string with budget_status, daily_spent, remaining_budget, and can_process
        """
        # Validate required environment variables
        project_id = os.getenv("GCP_PROJECT_ID")
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        
        daily_limit = 5.0  # $5 daily limit
        
        try:
            # Initialize Firestore client
            db = firestore.Client(project=project_id)
            
            # Get today's date in UTC
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            # Query transcripts created today to calculate spending
            transcripts_ref = db.collection('transcripts')
            today_transcripts = transcripts_ref.where(
                'created_at', '>=', datetime.strptime(today, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            ).stream()
            
            daily_spent = 0.0
            transcript_count = 0
            
            for transcript in today_transcripts:
                transcript_data = transcript.to_dict()
                costs = transcript_data.get('costs', {})
                transcription_cost = costs.get('transcription_usd', 0)
                daily_spent += transcription_cost
                transcript_count += 1
            
            remaining_budget = daily_limit - daily_spent
            
            # Check if we can process new transcription
            can_process = True
            if self.estimated_cost_usd:
                can_process = (daily_spent + self.estimated_cost_usd) <= daily_limit
            else:
                can_process = remaining_budget > 0
            
            # Determine budget status
            usage_percentage = (daily_spent / daily_limit) * 100
            if usage_percentage >= 100:
                budget_status = "EXCEEDED"
            elif usage_percentage >= 90:
                budget_status = "WARNING"
            elif usage_percentage >= 70:
                budget_status = "CAUTION"
            else:
                budget_status = "OK"
            
            result = {
                "budget_status": budget_status,
                "daily_spent": round(daily_spent, 4),
                "daily_limit": daily_limit,
                "remaining_budget": round(remaining_budget, 4),
                "usage_percentage": round(usage_percentage, 1),
                "transcript_count_today": transcript_count,
                "can_process": can_process,
                "date": today
            }
            
            return json.dumps(result)
            
        except Exception as e:
            raise RuntimeError(f"Failed to monitor transcription budget: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = MonitorTranscriptionBudget(estimated_cost_usd=0.65)
    
    try:
        result = tool.run()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")