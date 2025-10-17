"""
Query DLQ tool for monitoring and analyzing dead letter queue entries.
Implements TASK-ORCH-0005 with filtering, statistics, and pattern analysis.
"""

import os
import sys
import json
from typing import Optional, List, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone, timedelta

# Add core and config directories to path
from env_loader import get_required_env_var
from firestore_client import get_firestore_client
from loader import load_app_config



class QueryDLQ(BaseTool):
    """
    Queries and analyzes dead letter queue entries with filtering and statistics.
    
    Provides insights into failure patterns, recovery priorities, and operational
    health by analyzing DLQ entries with comprehensive filtering capabilities.
    """
    
    filter_job_type: Optional[str] = Field(
        None,
        description="Filter by job type (e.g., 'single_video', 'channel_scrape'). If None, includes all types."
    )
    
    filter_video_id: Optional[str] = Field(
        None,
        description="Filter by specific video ID. If None, includes all videos."
    )
    
    filter_severity: Optional[str] = Field(
        None,
        description="Filter by severity level ('low', 'medium', 'high'). If None, includes all severities."
    )
    
    time_range_hours: Optional[int] = Field(
        24,
        description="Query entries from the last N hours. Default is 24 hours.",
        ge=1,
        le=720  # Max 30 days
    )
    
    include_statistics: bool = Field(
        True,
        description="Whether to include summary statistics in the response"
    )
    
    limit: int = Field(
        50,
        description="Maximum number of DLQ entries to return",
        ge=1,
        le=500
    )
    
    def run(self) -> str:
        """
        Queries DLQ entries with filters and returns analysis.
        
        Returns:
            str: JSON string containing filtered entries and optional statistics
            
        Raises:
            ValueError: If filter parameters are invalid
            RuntimeError: If Firestore operation fails
        """
        try:
            # Validate inputs
            self._validate_inputs()
            
            # Initialize Firestore client
            db = get_firestore_client()
            
            # Build query with filters
            query = db.collection('jobs_deadletter')
            
            # Apply time range filter
            if self.time_range_hours:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.time_range_hours)
                query = query.where('dlq_created_at', '>=', cutoff_time)
            
            # Apply job type filter
            if self.filter_job_type:
                query = query.where('job_type', '==', self.filter_job_type)
            
            # Apply severity filter
            if self.filter_severity:
                query = query.where('severity', '==', self.filter_severity)
            
            # Order by creation time (newest first) and limit
            query = query.order_by('dlq_created_at', direction=firestore.Query.DESCENDING).limit(self.limit)
            
            # Execute query
            docs = query.stream()
            
            # Process results
            entries = []
            video_id_matches = []
            
            for doc in docs:
                entry_data = doc.to_dict()
                entry_data['dlq_id'] = doc.id
                
                # Apply video_id filter if specified
                if self.filter_video_id:
                    if self._matches_video_id(entry_data, self.filter_video_id):
                        video_id_matches.append(entry_data)
                else:
                    entries.append(entry_data)
            
            # Use video_id filtered results if filter was applied
            if self.filter_video_id:
                entries = video_id_matches
            
            # Convert Firestore timestamps to ISO strings
            for entry in entries:
                if 'dlq_created_at' in entry and entry['dlq_created_at']:
                    entry['dlq_created_at'] = entry['dlq_created_at'].isoformat()
            
            # Build response
            response = {
                "query_executed_at": datetime.now(timezone.utc).isoformat(),
                "filters_applied": {
                    "job_type": self.filter_job_type,
                    "video_id": self.filter_video_id,
                    "severity": self.filter_severity,
                    "time_range_hours": self.time_range_hours
                },
                "entries_count": len(entries),
                "entries": entries
            }
            
            # Add statistics if requested
            if self.include_statistics:
                response["statistics"] = self._calculate_statistics(entries)
            
            return json.dumps(response, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to query DLQ: {str(e)}",
                "entries": []
            })
    
    def _validate_inputs(self):
        """Validate input parameters."""
        if self.filter_severity and self.filter_severity not in ["low", "medium", "high"]:
            raise ValueError("filter_severity must be 'low', 'medium', or 'high'")
        
        valid_job_types = [
            "channel_scrape", "sheet_backfill", 
            "single_video", "batch_transcribe",
            "single_summary", "batch_summarize"
        ]
        
        if self.filter_job_type and self.filter_job_type not in valid_job_types:
            raise ValueError(f"filter_job_type must be one of: {valid_job_types}")
    
    def _matches_video_id(self, entry_data: Dict[str, Any], target_video_id: str) -> bool:
        """Check if DLQ entry matches the target video ID."""
        # Check direct video_id field
        if entry_data.get("video_id") == target_video_id:
            return True
        
        # Check video_ids list for batch jobs
        video_ids = entry_data.get("video_ids", [])
        if target_video_id in video_ids:
            return True
        
        # Check original inputs
        original_inputs = entry_data.get("failure_context", {}).get("original_inputs", {})
        if original_inputs.get("video_id") == target_video_id:
            return True
        
        if target_video_id in original_inputs.get("video_ids", []):
            return True
        
        return False
    
    def _calculate_statistics(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for DLQ entries."""
        if not entries:
            return {
                "total_entries": 0,
                "by_job_type": {},
                "by_severity": {},
                "by_error_type": {},
                "recovery_priority_distribution": {},
                "average_processing_attempts": 0,
                "top_error_patterns": []
            }
        
        # Count by job type
        job_type_counts = {}
        severity_counts = {}
        error_type_counts = {}
        priority_counts = {}
        processing_attempts = []
        
        for entry in entries:
            # Job type distribution
            job_type = entry.get("job_type", "unknown")
            job_type_counts[job_type] = job_type_counts.get(job_type, 0) + 1
            
            # Severity distribution
            severity = entry.get("severity", "unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Error type distribution
            error_type = entry.get("failure_context", {}).get("error_type", "unknown")
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1
            
            # Recovery priority distribution
            priority = entry.get("recovery_priority", "unknown")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # Processing attempts
            attempts = entry.get("processing_attempts", 0)
            if attempts > 0:
                processing_attempts.append(attempts)
        
        # Calculate average processing attempts
        avg_attempts = sum(processing_attempts) / len(processing_attempts) if processing_attempts else 0
        
        # Find top error patterns
        top_errors = sorted(error_type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_entries": len(entries),
            "by_job_type": job_type_counts,
            "by_severity": severity_counts,
            "by_error_type": error_type_counts,
            "recovery_priority_distribution": priority_counts,
            "average_processing_attempts": round(avg_attempts, 2),
            "top_error_patterns": [{"error_type": error, "count": count} for error, count in top_errors]
        }
    

if __name__ == "__main__":
    # Test querying all DLQ entries
    print("Testing query_dlq with default filters...")
    test_tool = QueryDLQ(
        time_range_hours=48,
        include_statistics=True,
        limit=10
    )
    
    try:
        result = test_tool.run()
        print("DLQ query result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Found {data['entries_count']} DLQ entries")
            if "statistics" in data:
                stats = data["statistics"]
                print(f"Total entries: {stats['total_entries']}")
                print(f"Average attempts: {stats['average_processing_attempts']}")
                print(f"Top error: {stats['top_error_patterns'][0] if stats['top_error_patterns'] else 'None'}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting query_dlq with specific filters...")
    test_tool_filtered = QueryDLQ(
        filter_job_type="single_video",
        filter_severity="high",
        time_range_hours=24,
        include_statistics=True,
        limit=5
    )
    
    try:
        result = test_tool_filtered.run()
        print("Filtered DLQ query result:")
        data = json.loads(result)
        print(f"Filtered entries: {data['entries_count']}")
        
    except Exception as e:
        print(f"Filtered test error: {str(e)}")