"""
ResolveChannelHandles tool for batch conversion of YouTube channel handles to channel IDs.
Loads handles from settings.yaml and returns a mapping of handles to channel IDs.
"""

import os
import sys
import time
from typing import Dict, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_var, env_loader
from loader import load_app_config, get_config_value


class ResolveChannelHandles(BaseTool):
    """
    Resolves multiple YouTube channel handles to their corresponding channel IDs.
    
    Loads the list of handles from settings.yaml (scraper.handles) and returns
    a mapping of each handle to its channel ID using YouTube Data API v3.
    Includes retry logic for rate limits and transient failures.
    """
    
    max_retries: int = Field(
        3,
        description="Maximum number of retry attempts for API failures (default: 3)"
    )
    
    def run(self) -> str:
        """
        Resolves all configured channel handles to channel IDs.
        
        Returns:
            str: JSON string containing mapping of handles to channel IDs
                 Format: '{"@AlexHormozi": "UCfV36TX5AejfAGIbtwTc7Zw", ...}'
        """
        try:
            # Load handles from configuration
            handles = self._load_handles_from_config()
            
            if not handles:
                return '{"error": "No handles configured in settings.yaml"}'
            
            # Initialize YouTube API client
            youtube = self._initialize_youtube_client()
            
            # Resolve each handle to channel ID
            mapping = {}
            for handle in handles:
                try:
                    channel_id = self._resolve_single_handle(youtube, handle)
                    mapping[handle] = channel_id
                except Exception as e:
                    # Continue with other handles even if one fails
                    mapping[handle] = f"ERROR: {str(e)}"
            
            # Return as JSON string
            import json
            return json.dumps(mapping, indent=2)
            
        except Exception as e:
            return f'{{"error": "Failed to resolve channel handles: {str(e)}"}}'
    
    def _load_handles_from_config(self) -> List[str]:
        """Load channel handles from settings.yaml configuration."""
        try:
            config = load_app_config()
            handles = get_config_value("scraper.handles", ["@AlexHormozi"])
            
            # Ensure all handles start with @
            normalized_handles = []
            for handle in handles:
                if not handle.startswith('@'):
                    handle = f"@{handle}"
                normalized_handles.append(handle)
            
            return normalized_handles
            
        except Exception as e:
            raise RuntimeError(f"Failed to load handles from config: {str(e)}")
    
    def _resolve_single_handle(self, youtube, handle: str) -> str:
        """
        Resolve a single channel handle to channel ID with retry logic.
        
        Args:
            youtube: Authenticated YouTube API client
            handle: Channel handle (e.g., "@AlexHormozi")
            
        Returns:
            str: Channel ID (e.g., "UCfV36TX5AejfAGIbtwTc7Zw")
            
        Raises:
            ValueError: If channel not found
            RuntimeError: If API error persists after retries
        """
        clean_handle = handle.lstrip('@')
        
        for attempt in range(self.max_retries + 1):
            try:
                # First try searching for the channel by handle
                search_response = youtube.search().list(
                    part="snippet",
                    q=f"@{clean_handle}",  # Include @ in search
                    type="channel",
                    maxResults=5  # Get more results to find exact match
                ).execute()
                
                # Look for exact handle match in results
                if search_response.get('items'):
                    for item in search_response['items']:
                        # Check if this is the exact channel we're looking for
                        channel_id = item['snippet']['channelId']
                        
                        # Get channel details to verify handle
                        channel_response = youtube.channels().list(
                            part="snippet",
                            id=channel_id
                        ).execute()
                        
                        if channel_response.get('items'):
                            channel_data = channel_response['items'][0]['snippet']
                            # Check custom URL or title for match
                            if (hasattr(channel_data, 'customUrl') and 
                                channel_data.get('customUrl', '').lower() == f"@{clean_handle.lower()}"):
                                return channel_id
                            # If no custom URL, use the first search result
                            if attempt == self.max_retries:  # Last attempt, take best match
                                return channel_id
                
                # Fallback: try by username (legacy channels)
                channels_response = youtube.channels().list(
                    part="id",
                    forUsername=clean_handle
                ).execute()
                
                if channels_response.get('items'):
                    return channels_response['items'][0]['id']
                
                # If this is the last attempt, raise error
                if attempt == self.max_retries:
                    raise ValueError(f"Channel not found for handle: {handle}")
                
                # If no results, try next attempt
                continue
                
            except HttpError as e:
                if e.resp.status in [429, 500, 502, 503, 504]:  # Retryable errors
                    if attempt < self.max_retries:
                        # Exponential backoff: 1s, 2s, 4s
                        sleep_time = 2 ** attempt
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise RuntimeError(f"API error after {self.max_retries} retries: {str(e)}")
                else:
                    # Non-retryable error
                    raise RuntimeError(f"YouTube API error: {str(e)}")
            
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(1)  # Short delay before retry
                    continue
                else:
                    raise RuntimeError(f"Failed to resolve {handle}: {str(e)}")
        
        raise ValueError(f"Channel not found for handle: {handle}")
    
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
    tool = ResolveChannelHandles()
    try:
        result = tool.run()
        print("Success!")
        print("Handle to Channel ID mapping:")
        print(result)
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()