"""
ReadSheetLinksSimple tool for reading YouTube links from Google Sheets.
Simplified implementation focused on single-column YouTube URL extraction.
"""

import os
import sys
import json
import re
from typing import Optional, List, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_var
from loader import load_app_config

# Google Sheets API
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

load_dotenv()


class ReadSheetLinksSimple(BaseTool):
    """
    Reads YouTube links from a single-column Google Sheet.
    
    This tool reads a Google Sheet containing YouTube URLs in column A,
    validates and deduplicates the URLs, and returns them in a structured format.
    Designed for backfill scenarios where a sheet contains a list of YouTube links.
    """
    
    sheet_id: Optional[str] = Field(
        None,
        description="Google Sheet ID to read from. If not provided, uses sheet ID from settings.yaml"
    )
    
    range_a1: str = Field(
        "Sheet1!A:A",
        description="A1 notation range to read from the sheet (default: 'Sheet1!A:A')"
    )
    
    max_rows: Optional[int] = Field(
        None,
        description="Maximum number of rows to process. If not provided, processes all rows"
    )
    
    def run(self) -> str:
        """
        Read YouTube links from the Google Sheet.
        
        Returns:
            str: JSON string containing array of video_url objects
        """
        try:
            # Load configuration
            config = load_app_config()
            
            # Determine sheet ID
            sheet_id = self.sheet_id or config.get("sheet")
            if not sheet_id:
                return json.dumps({
                    "error": "No sheet ID provided or configured in settings.yaml",
                    "items": []
                })
            
            # Initialize Google Sheets API
            service = self._initialize_sheets_service()
            
            # Read sheet data
            sheet_data = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=self.range_a1
            ).execute()
            
            values = sheet_data.get('values', [])
            
            if not values:
                return json.dumps({
                    "items": [],
                    "summary": {
                        "total_rows": 0,
                        "valid_urls": 0,
                        "invalid_urls": 0
                    }
                })
            
            # Process rows and extract YouTube URLs
            valid_urls = []
            invalid_count = 0
            processed_count = 0
            
            for row in values:
                # Apply max_rows limit if specified
                if self.max_rows and processed_count >= self.max_rows:
                    break
                
                # Skip empty rows
                if not row or not row[0].strip():
                    continue
                
                url = row[0].strip()
                processed_count += 1
                
                # Validate YouTube URL
                if self._is_youtube_url(url):
                    # Normalize URL format
                    normalized_url = self._normalize_youtube_url(url)
                    if normalized_url not in valid_urls:  # Deduplicate
                        valid_urls.append(normalized_url)
                else:
                    invalid_count += 1
            
            # Format response according to task requirements
            items = [{"video_url": url} for url in valid_urls]
            
            response = {
                "items": items,
                "summary": {
                    "total_rows": len(values),
                    "processed_rows": processed_count,
                    "valid_urls": len(valid_urls),
                    "invalid_urls": invalid_count,
                    "sheet_id": sheet_id,
                    "range": self.range_a1
                }
            }
            
            return json.dumps(response, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to read sheet links: {str(e)}",
                "items": []
            })
    
    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a valid YouTube URL."""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in youtube_patterns:
            if re.search(pattern, url):
                return True
        
        return False
    
    def _normalize_youtube_url(self, url: str) -> str:
        """Normalize YouTube URL to standard watch format."""
        # Extract video ID
        video_id_patterns = [
            r'(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in video_id_patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                return f"https://www.youtube.com/watch?v={video_id}"
        
        # If no match found, return original URL
        return url
    
    def _initialize_sheets_service(self):
        """Initialize Google Sheets API service."""
        try:
            # Get service account credentials
            credentials_path = get_required_var(
                "GOOGLE_APPLICATION_CREDENTIALS", 
                "Google service account credentials file path"
            )
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            
            service = build('sheets', 'v4', credentials=credentials)
            return service
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Sheets service: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = ReadSheetLinksSimple(
        range_a1="Sheet1!A1:A10",  # Read first 10 rows for testing
        max_rows=5
    )
    
    try:
        result = tool.run()
        print("ReadSheetLinksSimple test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Found {len(data['items'])} valid YouTube URLs")
            for item in data['items'][:3]:  # Show first 3
                print(f"  - {item['video_url']}")
                
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()