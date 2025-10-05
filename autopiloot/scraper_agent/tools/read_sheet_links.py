"""
ReadSheetLinks tool for reading page links from Google Sheets and extracting YouTube URLs.
Implements PRD specification: read sheet containing page links, fetch each page, extract YouTube URLs.
"""

import os
import sys
import json
import re
from typing import Optional, List, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv
import time

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var
from loader import load_app_config

# Google Sheets API
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

load_dotenv()


class ReadSheetLinks(BaseTool):
    """
    Read a Google Sheet containing page links; extract any YouTube video URLs contained in those pages.
    
    This tool implements the PRD specification:
    1. Reads page URLs from a Google Sheet
    2. Fetches each page and extracts embedded YouTube video URLs
    3. Returns both source_page_url and video_url for tracking
    
    Supports multiple YouTube URL formats including embeds, oEmbed, and direct links.
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
    
    timeout_sec: int = Field(
        10,
        description="HTTP timeout for fetching pages in seconds (default: 10)"
    )
    
    def run(self) -> str:
        """
        Read page links from Google Sheet and extract YouTube URLs from those pages.
        
        Returns:
            str: JSON string containing array of { source_page_url, video_url } objects
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
                        "pages_processed": 0,
                        "pages_failed": 0,
                        "youtube_urls_found": 0
                    }
                })
            
            # Process rows and extract YouTube URLs from pages
            results = []
            pages_processed = 0
            pages_failed = 0
            processed_count = 0
            
            for row in values:
                # Apply max_rows limit if specified
                if self.max_rows and processed_count >= self.max_rows:
                    break
                
                # Skip empty rows
                if not row or not row[0].strip():
                    continue
                
                page_url = row[0].strip()
                processed_count += 1
                
                # Validate page URL
                if not self._is_valid_url(page_url):
                    pages_failed += 1
                    continue
                
                # Extract YouTube URLs from this page
                try:
                    youtube_urls = self._extract_youtube_urls_from_page(page_url)
                    pages_processed += 1
                    
                    # Add results with source page tracking
                    for video_url in youtube_urls:
                        results.append({
                            "source_page_url": page_url,
                            "video_url": video_url
                        })
                        
                    # Small delay to be respectful to servers
                    time.sleep(0.5)
                    
                except Exception as e:
                    pages_failed += 1
                    print(f"Failed to process page {page_url}: {str(e)}")
                    continue
            
            # Deduplicate results by video_url while preserving source tracking
            unique_results = []
            seen_videos = set()
            
            for result in results:
                video_url = result["video_url"]
                if video_url not in seen_videos:
                    unique_results.append(result)
                    seen_videos.add(video_url)
            
            response = {
                "items": unique_results,
                "summary": {
                    "total_rows": len(values),
                    "processed_rows": processed_count,
                    "pages_processed": pages_processed,
                    "pages_failed": pages_failed,
                    "youtube_urls_found": len(unique_results),
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
    
    def _extract_youtube_urls_from_page(self, page_url: str) -> List[str]:
        """
        Extract YouTube URLs from a web page using multiple methods.

        Args:
            page_url: URL of the page to fetch and parse

        Returns:
            List of unique YouTube URLs found on the page
        """
        # Import requests and BeautifulSoup inside method for better testability
        import requests
        from bs4 import BeautifulSoup

        try:
            # Fetch page content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = requests.get(page_url, headers=headers, timeout=self.timeout_sec)
            response.raise_for_status()

            html_content = response.text
            youtube_urls = set()

            # Method 1: Parse HTML with BeautifulSoup
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract from iframe embeds
                for iframe in soup.find_all('iframe'):
                    src = iframe.get('src', '')
                    if 'youtube.com/embed' in src or 'youtu.be' in src:
                        video_url = self._normalize_youtube_url(src)
                        if video_url:
                            youtube_urls.add(video_url)
                
                # Extract from anchor links
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    if self._is_youtube_url(href):
                        video_url = self._normalize_youtube_url(href)
                        if video_url:
                            youtube_urls.add(video_url)
                
                # Extract from og:video meta tags
                for meta in soup.find_all('meta', property='og:video'):
                    content = meta.get('content', '')
                    if self._is_youtube_url(content):
                        video_url = self._normalize_youtube_url(content)
                        if video_url:
                            youtube_urls.add(video_url)
                            
            except Exception as e:
                print(f"BeautifulSoup parsing failed for {page_url}: {str(e)}")
            
            # Method 2: Regex extraction from raw HTML
            youtube_patterns = [
                r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
                r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
                r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
                r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})'
            ]
            
            for pattern in youtube_patterns:
                matches = re.finditer(pattern, html_content)
                for match in matches:
                    video_id = match.group(1)
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    youtube_urls.add(video_url)
            
            return list(youtube_urls)
            
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch page {page_url}: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to parse page {page_url}: {str(e)}")
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and accessible."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return bool(url_pattern.match(url))
    
    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a valid YouTube URL."""
        if not url:
            return False
            
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
    
    def _normalize_youtube_url(self, url: str) -> Optional[str]:
        """Normalize YouTube URL to standard watch format."""
        if not url:
            return None
            
        # Extract video ID
        video_id_patterns = [
            r'(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in video_id_patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                return f"https://www.youtube.com/watch?v={video_id}"
        
        return None
    
    def _initialize_sheets_service(self):
        """Initialize Google Sheets API service."""
        try:
            # Get service account credentials
            credentials_path = get_required_env_var(
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
    tool = ReadSheetLinks(
        range_a1="Sheet1!A1:A5",  # Read first 5 rows for testing
        max_rows=3,
        timeout_sec=15
    )
    
    try:
        result = tool.run()
        print("ReadSheetLinks test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Summary: {data['summary']}")
            print(f"Found {len(data['items'])} YouTube URLs from pages:")
            for item in data['items'][:3]:  # Show first 3
                print(f"  - Source: {item['source_page_url']}")
                print(f"    Video:  {item['video_url']}")
                print()
                
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()