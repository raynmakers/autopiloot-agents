"""
ListRecentUploads tool for fetching recent YouTube uploads using uploads playlist.
Implements checkpoint-based processing with lastPublishedAt persistence.
"""

import os
import sys
import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_var, env_loader
from loader import get_config_value
from reliability import QuotaManager

# Firebase Admin SDK for checkpoint persistence
try:
    import firebase_admin
    from firebase_admin import firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False


class ListRecentUploads(BaseTool):
    """
    Lists recent video uploads from a YouTube channel using uploads playlist.
    
    Uses the channel's uploads playlist to efficiently retrieve videos within
    a time window, implements checkpoint-based processing to skip already-seen
    videos, and includes quota management for production reliability.
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
        description="Maximum number of videos to return per page (1-50)",
        ge=1,
        le=50
    )
    use_checkpoint: bool = Field(
        default=True,
        description="Use lastPublishedAt checkpoint to skip already-processed videos"
    )
    
    def run(self) -> str:
        """
        Fetches recent uploads from the channel's uploads playlist.
        
        Returns:
            str: JSON string containing array of video objects with keys:
                 video_id, url, title, published_at, duration_sec
                 
        Raises:
            ValueError: If inputs are invalid
            RuntimeError: If API call fails or quota exceeded
        """
        try:
            # Initialize YouTube API client and quota manager
            youtube = self._initialize_youtube_client()
            quota_manager = QuotaManager()
            
            # Check quota availability
            if not quota_manager.is_service_available('youtube'):
                return json.dumps({
                    'error': 'YouTube API quota exhausted',
                    'items': [],
                    'quota_reset_time': quota_manager.get_quota_status('youtube')['reset_time']
                })
            
            # Get channel's uploads playlist ID
            uploads_playlist_id = self._get_uploads_playlist_id(youtube, self.channel_id)
            
            if not uploads_playlist_id:
                return json.dumps({'error': 'Could not find uploads playlist', 'items': []})
            
            # Load checkpoint if enabled
            checkpoint = None
            if self.use_checkpoint:
                checkpoint = self._load_checkpoint(self.channel_id)
            
            # Fetch videos from uploads playlist
            videos = self._fetch_playlist_videos(
                youtube, 
                uploads_playlist_id, 
                checkpoint,
                quota_manager
            )
            
            # Get detailed video information including durations
            detailed_videos = self._get_video_details(youtube, videos, quota_manager)
            
            # Filter by time window and apply limits
            filtered_videos = self._filter_videos_by_timeframe(detailed_videos)
            
            # Update checkpoint with latest video
            if self.use_checkpoint and filtered_videos:
                latest_video = max(filtered_videos, key=lambda v: v['published_at'])
                self._save_checkpoint(self.channel_id, latest_video['published_at'])
            
            # Update quota usage
            quota_manager.record_request('youtube', len(videos) + len(detailed_videos))
            
            return json.dumps({
                'items': filtered_videos[:self.page_size],
                'total_found': len(filtered_videos),
                'checkpoint_updated': self.use_checkpoint and len(filtered_videos) > 0
            }, indent=2)
            
        except Exception as e:
            return json.dumps({'error': f'Failed to list recent uploads: {str(e)}', 'items': []})
    
    def _get_uploads_playlist_id(self, youtube, channel_id: str) -> Optional[str]:
        """Get the uploads playlist ID for the channel."""
        try:
            channel_response = youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            
            if not channel_response.get('items'):
                return None
            
            uploads_playlist_id = (
                channel_response['items'][0]
                ['contentDetails']
                ['relatedPlaylists']
                ['uploads']
            )
            
            return uploads_playlist_id
            
        except Exception as e:
            raise RuntimeError(f"Failed to get uploads playlist: {str(e)}")
    
    def _fetch_playlist_videos(self, youtube, playlist_id: str, checkpoint: Optional[str], 
                              quota_manager: QuotaManager) -> List[Dict[str, Any]]:
        """Fetch videos from uploads playlist with checkpoint support."""
        videos = []
        next_page_token = None
        checkpoint_dt = None
        
        if checkpoint:
            try:
                checkpoint_dt = datetime.fromisoformat(checkpoint.replace('Z', '+00:00'))
            except:
                checkpoint_dt = None
        
        while len(videos) < self.page_size * 2:  # Fetch extra to account for filtering
            # Check quota before making request
            if not quota_manager.is_service_available('youtube'):
                break
            
            params = {
                'part': 'snippet',
                'playlistId': playlist_id,
                'maxResults': min(50, self.page_size * 2 - len(videos))
            }
            
            if next_page_token:
                params['pageToken'] = next_page_token
            
            try:
                response = youtube.playlistItems().list(**params).execute()
                quota_manager.record_request('youtube', 1)
                
                for item in response.get('items', []):
                    published_at = item['snippet']['publishedAt']
                    published_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    
                    # Skip if before checkpoint
                    if checkpoint_dt and published_dt <= checkpoint_dt:
                        continue
                    
                    # Skip if outside time window (early exit optimization)
                    since_dt = datetime.fromisoformat(self.since_utc.replace('Z', '+00:00'))
                    if published_dt < since_dt:
                        return videos  # Videos are ordered by date, so we can stop here
                    
                    videos.append({
                        'video_id': item['snippet']['resourceId']['videoId'],
                        'title': item['snippet']['title'],
                        'published_at': published_at,
                        'channel_title': item['snippet']['channelTitle']
                    })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                    
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit
                    quota_manager.mark_quota_exhausted('youtube')
                    break
                else:
                    raise RuntimeError(f"YouTube API error: {str(e)}")
        
        return videos
    
    def _get_video_details(self, youtube, videos: List[Dict[str, Any]], 
                          quota_manager: QuotaManager) -> List[Dict[str, Any]]:
        """Get detailed video information including durations."""
        if not videos:
            return []
        
        detailed_videos = []
        
        # Process videos in batches of 50 (API limit)
        for i in range(0, len(videos), 50):
            batch = videos[i:i + 50]
            video_ids = [video['video_id'] for video in batch]
            
            if not quota_manager.is_service_available('youtube'):
                break
            
            try:
                videos_response = youtube.videos().list(
                    part='snippet,contentDetails',
                    id=','.join(video_ids)
                ).execute()
                
                quota_manager.record_request('youtube', 1)
                
                # Create lookup for video details
                video_details = {item['id']: item for item in videos_response.get('items', [])}
                
                for video in batch:
                    video_id = video['video_id']
                    if video_id in video_details:
                        details = video_details[video_id]
                        duration_sec = self._parse_duration(details['contentDetails']['duration'])
                        
                        detailed_videos.append({
                            'video_id': video_id,
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'title': details['snippet']['title'],
                            'published_at': details['snippet']['publishedAt'],
                            'duration_sec': duration_sec
                        })
                        
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit
                    quota_manager.mark_quota_exhausted('youtube')
                    break
                else:
                    raise RuntimeError(f"YouTube API error: {str(e)}")
        
        return detailed_videos
    
    def _filter_videos_by_timeframe(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter videos by the specified time window."""
        since_dt = datetime.fromisoformat(self.since_utc.replace('Z', '+00:00'))
        until_dt = datetime.fromisoformat(self.until_utc.replace('Z', '+00:00'))
        
        filtered = []
        for video in videos:
            published_dt = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
            if since_dt <= published_dt <= until_dt:
                filtered.append(video)
        
        # Sort by publication date (newest first)
        filtered.sort(key=lambda v: v['published_at'], reverse=True)
        return filtered
    
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
    
    def _load_checkpoint(self, channel_id: str) -> Optional[str]:
        """Load the last processed timestamp for this channel."""
        if not FIREBASE_AVAILABLE:
            return None
        
        try:
            db = firestore.client()
            doc_ref = db.collection('checkpoints').document(f'youtube_uploads_{channel_id}')
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return data.get('last_published_at')
            
            return None
            
        except Exception:
            # If checkpoint loading fails, continue without it
            return None
    
    def _save_checkpoint(self, channel_id: str, last_published_at: str) -> None:
        """Save the last processed timestamp for this channel."""
        if not FIREBASE_AVAILABLE:
            return
        
        try:
            db = firestore.client()
            doc_ref = db.collection('checkpoints').document(f'youtube_uploads_{channel_id}')
            doc_ref.set({
                'channel_id': channel_id,
                'last_published_at': last_published_at,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'service': 'youtube_uploads'
            }, merge=True)
            
        except Exception:
            # If checkpoint saving fails, continue (don't fail the whole operation)
            pass
    
    def _initialize_youtube_client(self):
        """Initialize YouTube Data API client with authentication."""
        try:
            # Get API key (required)
            api_key = get_required_var("YOUTUBE_API_KEY", "YouTube Data API key")
            
            # Try service account authentication first (if available)
            try:
                service_account_path = env_loader.get_service_credentials()
                if service_account_path and os.path.exists(service_account_path):
                    credentials = service_account.Credentials.from_service_account_file(
                        service_account_path,
                        scopes=['https://www.googleapis.com/auth/youtube.readonly']
                    )
                    return build('youtube', 'v3', credentials=credentials)
            except Exception:
                pass  # Fall back to API key
            
            # Use API key authentication
            return build('youtube', 'v3', developerKey=api_key)
                
        except Exception as e:
            raise RuntimeError(f"Failed to initialize YouTube client: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    from datetime import datetime, timedelta
    
    # Test with a 24-hour window
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    tool = ListRecentUploads(
        channel_id="UCfV36TX5AejfAGIbtwTc7Zw",  # Example channel ID
        since_utc=yesterday.isoformat(),
        until_utc=now.isoformat(),
        page_size=10,
        use_checkpoint=False  # Disable for testing
    )
    
    try:
        result = tool.run()
        print("Success!")
        print("Result:")
        print(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()