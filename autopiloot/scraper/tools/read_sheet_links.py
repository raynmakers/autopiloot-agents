import os
import json
from typing import Dict, Any, List
from googleapiclient.discovery import build
from google.oauth2 import service_account
import requests
from bs4 import BeautifulSoup
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class ReadSheetLinks(BaseTool):
    def __init__(self):
        super().__init__()
        self.sheets = self._initialize_sheets_client()
    
    def _validate_env_vars(self):
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH")
    
    def _initialize_sheets_client(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        return build('sheets', 'v4', credentials=credentials)
    
    def _extract_youtube_urls(self, page_url: str) -> List[str]:
        youtube_urls = []
        youtube_pattern = re.compile(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
        )
        
        try:
            response = requests.get(page_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for match in youtube_pattern.finditer(response.text):
                video_id = match.group(1)
                youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            for iframe in soup.find_all('iframe'):
                src = iframe.get('src', '')
                if 'youtube.com/embed/' in src or 'youtube-nocookie.com/embed/' in src:
                    match = youtube_pattern.search(src)
                    if match:
                        video_id = match.group(1)
                        youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'youtube.com/watch' in href or 'youtu.be/' in href:
                    match = youtube_pattern.search(href)
                    if match:
                        video_id = match.group(1)
                        youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            youtube_urls = list(set(youtube_urls))
            
        except Exception as e:
            print(f"Error extracting YouTube URLs from {page_url}: {str(e)}")
        
        return youtube_urls
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        sheet_id = request.get('sheet_id', '')
        range_a1 = request.get('range_a1', 'A:A')
        
        if not sheet_id:
            raise ValueError("sheet_id is required")
        
        try:
            result = self.sheets.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_a1
            ).execute()
            
            values = result.get('values', [])
            
            extracted_videos = []
            
            for row in values:
                if row and row[0]:
                    page_url = row[0].strip()
                    if not page_url:
                        continue
                    
                    if not page_url.startswith(('http://', 'https://')):
                        page_url = f"https://{page_url}"
                    
                    youtube_urls = self._extract_youtube_urls(page_url)
                    
                    for video_url in youtube_urls:
                        extracted_videos.append({
                            'source_page_url': page_url,
                            'video_url': video_url
                        })
            
            return {"videos": extracted_videos}
            
        except Exception as e:
            raise RuntimeError(f"Failed to read sheet links: {str(e)}")


if __name__ == "__main__":
    tool = ReadSheetLinks()
    
    test_request = {
        "sheet_id": os.getenv("TEST_SHEET_ID", "placeholder_sheet_id"),
        "range_a1": "A:A"
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: Found {len(result.get('videos', []))} videos")
        if result.get('videos'):
            print(f"First video: {json.dumps(result['videos'][0], indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")