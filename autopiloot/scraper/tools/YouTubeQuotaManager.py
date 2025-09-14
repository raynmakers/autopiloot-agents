"""
YouTubeQuotaManager tool for managing YouTube API quota and checkpoints.
Implements lastPublishedAt checkpoint and quota exhaustion handling.
"""

import os
import sys
from typing import Optional, Dict, Any, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from reliability import (
    QuotaManager, create_checkpoint, CheckpointData, QuotaStatus,
    get_next_reset_time, should_pause_for_quota
)
from loader import load_app_config
from env_loader import get_api_key

# Google APIs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()


class YouTubeQuotaManager(BaseTool):
    """
    Manages YouTube API quota and implements checkpoint-based video discovery.
    
    This tool:
    1. Tracks YouTube API quota usage and enforces limits
    2. Implements lastPublishedAt checkpoint to resume from last processed video
    3. Handles quota exhaustion with backoff and retry strategies
    4. Provides quota status and next available time information
    """
    
    channel_handle: str = Field(
        ...,
        description="YouTube channel handle to query (e.g., '@AlexHormozi')"
    )
    
    max_results: int = Field(
        default=10,
        description="Maximum number of videos to fetch (default: 10)"
    )
    
    last_published_at: Optional[str] = Field(
        None,
        description="Last processed video timestamp (ISO8601) for checkpoint resume"
    )
    
    check_quota_only: bool = Field(
        False,
        description="If True, only check quota status without making API calls"
    )

    def run(self) -> str:
        """
        Manage YouTube API quota and fetch videos with checkpoint support.
        
        Returns:
            JSON string with quota status, videos found, and checkpoint data
        """
        try:
            # Initialize quota manager
            quota_manager = QuotaManager()
            
            # YouTube API quota limit (default: 10,000 units per day)
            # Channel search: ~100 units, video list: ~1 unit per video
            daily_quota_limit = 10000
            estimated_cost_per_request = 101  # 100 for search + 1 per video
            
            # Check current quota status
            current_quota = quota_manager.get_quota_info("youtube")
            if current_quota and should_pause_for_quota(current_quota):
                return self._create_quota_exhausted_response(current_quota)
            
            # If only checking quota, return status
            if self.check_quota_only:
                if current_quota:
                    return self._create_quota_status_response(current_quota)
                else:
                    return '{"quota_available": true, "requests_made": 0, "requests_limit": 10000}'
            
            # Set up YouTube API
            api_key = get_api_key("youtube")
            youtube = build('youtube', 'v3', developerKey=api_key)
            
            # Track API request for quota management
            quota_status = quota_manager.track_request("youtube", daily_quota_limit)
            
            # Step 1: Resolve channel handle to channel ID
            search_response = youtube.search().list(
                part='snippet',
                q=self.channel_handle,
                type='channel',
                maxResults=1
            ).execute()
            
            if not search_response.get('items'):
                return f'{{"error": "Channel not found for handle: {self.channel_handle}"}}'
            
            channel_id = search_response['items'][0]['snippet']['channelId']
            
            # Step 2: Get channel uploads playlist ID
            channels_response = youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            
            if not channels_response.get('items'):
                return f'{{"error": "Channel details not found for ID: {channel_id}"}}'
            
            uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Step 3: Get recent videos with checkpoint support
            playlist_params = {
                'part': 'snippet,contentDetails',
                'playlistId': uploads_playlist_id,
                'maxResults': self.max_results
            }
            
            # Apply checkpoint filter if provided
            published_after = None
            if self.last_published_at:
                published_after = self.last_published_at
                # Note: YouTube API doesn't support publishedAfter for playlist items
                # We'll filter client-side
            
            playlist_response = youtube.playlistItems().list(**playlist_params).execute()
            
            # Track additional API requests
            quota_manager.track_request("youtube", daily_quota_limit)
            
            # Process videos and apply checkpoint filtering
            videos = []
            new_checkpoint = None
            
            for item in playlist_response.get('items', []):
                video_id = item['snippet']['resourceId']['videoId']
                published_at = item['snippet']['publishedAt']
                title = item['snippet']['title']
                
                # Apply checkpoint filtering
                if published_after:
                    if published_at <= published_after:
                        continue  # Skip videos older than checkpoint
                
                # Get video duration for filtering
                video_details = youtube.videos().list(
                    part='contentDetails',
                    id=video_id
                ).execute()
                
                # Track video details API request
                quota_manager.track_request("youtube", daily_quota_limit)
                
                if video_details.get('items'):
                    duration = video_details['items'][0]['contentDetails']['duration']
                    # Parse ISO 8601 duration (PT4M13S -> 253 seconds)
                    duration_seconds = self._parse_duration(duration)
                    
                    video_data = {
                        'video_id': video_id,
                        'title': title,
                        'published_at': published_at,
                        'duration_seconds': duration_seconds,
                        'url': f'https://www.youtube.com/watch?v={video_id}',
                        'channel_id': channel_id
                    }
                    
                    videos.append(video_data)
                    
                    # Update checkpoint to most recent video
                    if not new_checkpoint or published_at > new_checkpoint:
                        new_checkpoint = published_at
            
            # Create checkpoint data
            checkpoint_data = create_checkpoint(
                service="youtube",
                last_published_at=new_checkpoint,
                last_processed_id=videos[0]['video_id'] if videos else None
            )
            
            # Prepare response
            response = {
                "success": True,
                "quota_status": {
                    "service": "youtube",
                    "requests_made": quota_status["requests_made"],
                    "requests_limit": quota_status["requests_limit"],
                    "quota_exhausted": quota_status["quota_exhausted"],
                    "reset_time": quota_status.get("reset_time")
                },
                "videos_found": len(videos),
                "videos": videos,
                "checkpoint": checkpoint_data,
                "channel_info": {
                    "handle": self.channel_handle,
                    "channel_id": channel_id,
                    "uploads_playlist_id": uploads_playlist_id
                }
            }
            
            return str(response).replace("'", '"')
            
        except HttpError as e:
            error_details = e.error_details[0] if e.error_details else {}
            
            # Handle quota exceeded specifically
            if e.resp.status == 403 and 'quotaExceeded' in str(error_details):
                quota_status = quota_manager.track_request("youtube", daily_quota_limit)
                quota_status["quota_exhausted"] = True
                quota_status["reset_time"] = get_next_reset_time("youtube")
                
                return self._create_quota_exhausted_response(quota_status)
            
            error_msg = f"YouTube API error: {str(e)}"
            return f'{{"error": "{error_msg}", "status_code": {e.resp.status}}}'
            
        except Exception as e:
            error_msg = f"Failed to manage YouTube quota: {str(e)}"
            return f'{{"error": "{error_msg}"}}'
    
    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse ISO 8601 duration string to seconds.
        
        Args:
            duration_str: ISO 8601 duration (e.g., "PT4M13S")
            
        Returns:
            Duration in seconds
        """
        import re
        
        # Parse PT4M13S format
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def _create_quota_exhausted_response(self, quota_status: QuotaStatus) -> str:
        """Create response for quota exhausted scenario."""
        response = {
            "success": False,
            "quota_exhausted": True,
            "quota_status": quota_status,
            "message": "YouTube API quota exhausted. Processing will resume when quota resets.",
            "resume_time": quota_status.get("reset_time")
        }
        return str(response).replace("'", '"')
    
    def _create_quota_status_response(self, quota_status: QuotaStatus) -> str:
        """Create response for quota status check."""
        response = {
            "quota_available": not quota_status["quota_exhausted"],
            "quota_status": quota_status,
            "requests_made": quota_status["requests_made"],
            "requests_limit": quota_status["requests_limit"]
        }
        return str(response).replace("'", '"')


if __name__ == "__main__":
    # Test the tool
    tool = YouTubeQuotaManager(
        channel_handle="@AlexHormozi",
        max_results=5,
        check_quota_only=True
    )
    result = tool.run()
    print("YouTubeQuotaManager result:")
    print(result)
