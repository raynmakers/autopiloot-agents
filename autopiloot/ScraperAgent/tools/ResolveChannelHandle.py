"""
ResolveChannelHandle tool for converting YouTube channel handles to channel IDs.
"""

import os
import sys
from typing import Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Add core directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
from env_loader import get_required_var, get_optional_var, env_loader


class ResolveChannelHandle(BaseTool):
    """
    Resolves a YouTube channel handle (like @AlexHormozi) to its corresponding channel ID.
    
    This tool uses the YouTube Data API v3 to search for channels by handle and returns
    the canonical channel ID needed for subsequent API calls.
    """
    
    channel_handle: str = Field(
        ..., 
        description="YouTube channel handle, e.g., '@AlexHormozi'. The @ symbol is optional."
    )
    
    def run(self) -> str:
        """
        Resolves the channel handle to a channel ID.
        
        Returns:
            str: The YouTube channel ID (e.g., "UCfV36TX5AejfAGIbtwTc7Zw")
            
        Raises:
            ValueError: If the channel handle is invalid or channel not found
            RuntimeError: If there's an API error
        """
        try:
            # Initialize YouTube API client
            youtube = self._initialize_youtube_client()
            
            # Clean the handle (remove @ if present)
            clean_handle = self.channel_handle.lstrip('@')
            
            # First try searching for the channel
            search_response = youtube.search().list(
                part="snippet",
                q=clean_handle,
                type="channel",
                maxResults=1
            ).execute()
            
            if search_response.get('items'):
                channel_id = search_response['items'][0]['snippet']['channelId']
                return channel_id
            
            # Fallback: try by username (legacy)
            channels_response = youtube.channels().list(
                part="id",
                forUsername=clean_handle
            ).execute()
            
            if channels_response.get('items'):
                channel_id = channels_response['items'][0]['id']
                return channel_id
            
            raise ValueError(f"Channel not found for handle: {self.channel_handle}")
            
        except Exception as e:
            if "Channel not found" in str(e):
                raise ValueError(str(e))
            else:
                raise RuntimeError(f"Failed to resolve channel handle: {str(e)}")
    
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
    tool = ResolveChannelHandle(channel_handle="@AlexHormozi")
    try:
        result = tool.run()
        print(f"Success: Channel ID = {result}")
    except Exception as e:
        print(f"Error: {str(e)}")