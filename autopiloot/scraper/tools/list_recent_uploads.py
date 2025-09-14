import os
import json
from typing import Dict, Any, List
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class ListRecentUploads(BaseTool):
    def __init__(self):
        super().__init__()
        self.youtube = self._initialize_youtube_client()
    
    def _validate_env_vars(self):
        self.api_key = self.get_env_var("YOUTUBE_API_KEY", required=False)
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH", required=False)
        
        if not self.api_key and not self.service_account_path:
            raise ValueError("Either YOUTUBE_API_KEY or GOOGLE_SERVICE_ACCOUNT_PATH must be set")
    
    def _initialize_youtube_client(self):
        if self.service_account_path:
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=['https://www.googleapis.com/auth/youtube.readonly']
            )
            return build('youtube', 'v3', credentials=credentials)
        else:
            return build('youtube', 'v3', developerKey=self.api_key)
    
    def _parse_duration(self, duration: str) -> int:
        import re
        pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
        match = pattern.match(duration)
        
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        channel_id = request.get('channel_id', '')
        since_utc = request.get('since_utc', '')
        until_utc = request.get('until_utc', '')
        page_size = request.get('page_size', 50)
        
        if not channel_id:
            raise ValueError("channel_id is required")
        if not since_utc:
            raise ValueError("since_utc is required")
        if not until_utc:
            raise ValueError("until_utc is required")
        
        videos = []
        next_page_token = None
        
        try:
            while True:
                search_params = {
                    'part': 'id,snippet',
                    'channelId': channel_id,
                    'type': 'video',
                    'order': 'date',
                    'publishedAfter': since_utc,
                    'publishedBefore': until_utc,
                    'maxResults': min(page_size, 50)
                }
                
                if next_page_token:
                    search_params['pageToken'] = next_page_token
                
                response = self.youtube.search().list(**search_params).execute()
                
                video_ids = [item['id']['videoId'] for item in response.get('items', [])]
                
                if video_ids:
                    video_response = self.youtube.videos().list(
                        part='snippet,contentDetails',
                        id=','.join(video_ids)
                    ).execute()
                    
                    for video in video_response.get('items', []):
                        duration_sec = self._parse_duration(video['contentDetails']['duration'])
                        videos.append({
                            'video_id': video['id'],
                            'url': f"https://www.youtube.com/watch?v={video['id']}",
                            'title': video['snippet']['title'],
                            'published_at': video['snippet']['publishedAt'],
                            'duration_sec': duration_sec
                        })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(videos) >= page_size:
                    break
            
            return {"videos": videos[:page_size]}
            
        except Exception as e:
            raise RuntimeError(f"Failed to list recent uploads: {str(e)}")


if __name__ == "__main__":
    tool = ListRecentUploads()
    
    from datetime import datetime, timedelta
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    test_request = {
        "channel_id": "UCfV36TX5AejfAGIbtwTc7Zw",
        "since_utc": yesterday.isoformat(),
        "until_utc": now.isoformat(),
        "page_size": 10
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: Found {len(result.get('videos', []))} videos")
        if result.get('videos'):
            print(f"First video: {json.dumps(result['videos'][0], indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")