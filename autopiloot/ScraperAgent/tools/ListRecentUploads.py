"""
ListRecentUploads tool for fetching recent YouTube videos from a channel.
"""

import os
import sys
import re
from typing import List, Dict, Any
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Add core directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
from env_loader import get_required_var, get_config_value, env_loader


class ListRecentUploads(BaseTool):
    """
    Lists recent video uploads from a YouTube channel within a specified time window.
    
    Retrieves video metadata including title, duration, and publication date for videos
    uploaded between the specified start and end times.
    """
    
    channel_id: str = Field(
        ..., 
        description="YouTube channel ID (e.g., 'UCfV36TX5AejfAGIbtwTc7Zw')"
    )
    since_utc: str = Field(
        ..., 
        description="Start time in ISO8601 UTC format (e.g., '2025-01-27T00:00:00Z')"
    )
    until_utc: str = Field(
        ..., 
        description="End time in ISO8601 UTC format (e.g., '2025-01-28T00:00:00Z')"
    )
    page_size: int = Field(
        default=50, 
        description="Maximum number of videos to return (1-50)",
        ge=1,
        le=50
    )
    
    def __post_init__(self):
        """Apply settings from configuration file."""
        # Override page_size with daily limit from config if not explicitly set
        if self.page_size == 50:  # Default value
            daily_limit = get_config_value("scraper.daily_limit_per_channel", 10)
            self.page_size = min(self.page_size, daily_limit)
    
    def run(self) -> List[Dict[str, Any]]:
        """
        Fetches recent uploads from the specified channel.
        
        Returns:
            List[Dict[str, Any]]: List of video dictionaries with keys:
                - video_id: YouTube video ID
                - url: Full YouTube URL
                - title: Video title
                - published_at: Publication date (ISO8601)
                - duration_sec: Duration in seconds
                
        Raises:
            ValueError: If inputs are invalid
            RuntimeError: If API call fails
        """
        try:
            # Initialize YouTube API client
            youtube = self._initialize_youtube_client()
            
            videos = []
            next_page_token = None
            
            while len(videos) < self.page_size:
                # Search for videos in the time window
                search_params = {
                    'part': 'id,snippet',
                    'channelId': self.channel_id,
                    'type': 'video',
                    'order': 'date',
                    'publishedAfter': self.since_utc,
                    'publishedBefore': self.until_utc,
                    'maxResults': min(50, self.page_size - len(videos))
                }
                
                if next_page_token:
                    search_params['pageToken'] = next_page_token
                
                search_response = youtube.search().list(**search_params).execute()
                
                # Extract video IDs
                video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                
                if not video_ids:
                    break
                
                # Get detailed video information including duration
                videos_response = youtube.videos().list(
                    part='snippet,contentDetails',
                    id=','.join(video_ids)
                ).execute()
                
                # Process each video
                for video in videos_response.get('items', []):
                    duration_sec = self._parse_duration(video['contentDetails']['duration'])
                    
                    videos.append({
                        'video_id': video['id'],
                        'url': f"https://www.youtube.com/watch?v={video['id']}",
                        'title': video['snippet']['title'],
                        'published_at': video['snippet']['publishedAt'],
                        'duration_sec': duration_sec
                    })
                
                # Check for next page
                next_page_token = search_response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return videos[:self.page_size]
            
        except Exception as e:
            raise RuntimeError(f"Failed to list recent uploads: {str(e)}")
    
    def _parse_duration(self, duration: str) -> int:
        """
        Parse ISO 8601 duration format (PT1H30M45S) to seconds.
        
        Args:
            duration: ISO 8601 duration string
            
        Returns:
            int: Duration in seconds
        """
        pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
        match = pattern.match(duration)
        
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def _initialize_youtube_client(self):
        """Initialize YouTube Data API client with authentication."""
        try:
            # Get API key (required)
            api_key = get_required_var("YOUTUBE_API_KEY", "YouTube Data API key")
            
            # Try service account authentication first (if available)
            try:
                service_account_path = env_loader.get_service_credentials()
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_path,
                    scopes=['https://www.googleapis.com/auth/youtube.readonly']
                )
                return build('youtube', 'v3', credentials=credentials)
            except Exception:
                # Fall back to API key authentication
                return build('youtube', 'v3', developerKey=api_key)
                
        except Exception as e:
            raise RuntimeError(f"Failed to initialize YouTube client: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    from datetime import datetime, timedelta
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    tool = ListRecentUploads(
        channel_id="UCfV36TX5AejfAGIbtwTc7Zw",  # Example channel ID
        since_utc=yesterday.isoformat(),
        until_utc=now.isoformat(),
        page_size=5
    )
    
    try:
        result = tool.run()
        print(f"Success: Found {len(result)} videos")
        for video in result:
            print(f"- {video['title']} ({video['duration_sec']}s)")
    except Exception as e:
        print(f"Error: {str(e)}")