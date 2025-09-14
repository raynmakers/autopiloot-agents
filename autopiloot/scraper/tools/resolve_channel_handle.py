import os
import json
from typing import Dict, Any
from googleapiclient.discovery import build
from google.oauth2 import service_account
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class ResolveChannelHandle(BaseTool):
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
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        channel_handle = request.get('channel_handle', '')
        
        if not channel_handle:
            raise ValueError("channel_handle is required")
        
        try:
            channel_handle = channel_handle.lstrip('@')
            
            response = self.youtube.search().list(
                part="snippet",
                q=channel_handle,
                type="channel",
                maxResults=1
            ).execute()
            
            if response.get('items'):
                channel_id = response['items'][0]['snippet']['channelId']
                return {"channel_id": channel_id}
            
            response = self.youtube.channels().list(
                part="id",
                forUsername=channel_handle
            ).execute()
            
            if response.get('items'):
                channel_id = response['items'][0]['id']
                return {"channel_id": channel_id}
            
            raise ValueError(f"Channel not found for handle: {channel_handle}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to resolve channel handle: {str(e)}")


if __name__ == "__main__":
    tool = ResolveChannelHandle()
    
    test_request = {
        "channel_handle": "@AlexHormozi"
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")