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
import time

# Add core and config directories to path
from config.env_loader import get_required_env_var
from config.loader import load_app_config

# Google Sheets API
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials



class ReadSheetLinks(BaseTool):
    """
    Read a Google Sheet containing links; extract YouTube video URLs from them.

    Handles two cases:
    1. Direct YouTube URLs: Extracts and normalizes the video URL directly
    2. External page URLs: Fetches the page and extracts any embedded YouTube videos

    Focus: YouTube videos only (other platforms are skipped)
    Returns source_page_url, video_url, platform, sheet_row_index, and sheet_id for tracking.

    Enhanced with row tracking: Each result includes sheet_row_index for downstream
    cleanup via RemoveSheetRow after successful processing.
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
        Read page links from Google Sheet and extract YouTube video URLs from those pages.

        Returns:
            str: JSON string containing array of { source_page_url, video_url, platform,
                 sheet_row_index, sheet_id } objects.
                 Platform will always be "youtube"
                 sheet_row_index is 1-based row number for RemoveSheetRow compatibility
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

            for row_index, row in enumerate(values, start=1):
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

                # Check if the URL is already a direct YouTube URL
                try:
                    if self._is_youtube_url(page_url):
                        # Direct YouTube URL - just extract and return it
                        normalized_url = self._normalize_youtube_url(page_url)
                        if normalized_url:
                            results.append({
                                "source_page_url": page_url,
                                "video_url": normalized_url,
                                "platform": "youtube",
                                "sheet_row_index": row_index,
                                "sheet_id": sheet_id
                            })
                            pages_processed += 1
                    else:
                        # External page - fetch and extract embedded YouTube videos
                        youtube_urls = self._extract_youtube_urls_from_page(page_url)
                        pages_processed += 1

                        if not youtube_urls:
                            print(f"No YouTube videos found on page: {page_url}")

                        # Add results with source page tracking
                        for video_url in youtube_urls:
                            results.append({
                                "source_page_url": page_url,
                                "video_url": video_url,
                                "platform": "youtube",
                                "sheet_row_index": row_index,
                                "sheet_id": sheet_id
                            })
                            print(f"Found YouTube video: {video_url}")

                        # Small delay to be respectful to servers
                        time.sleep(0.5)

                except Exception as e:
                    pages_failed += 1
                    print(f"Failed to process page {page_url}: {str(e)}")
                    continue
            
            # Deduplicate results by video ID
            unique_results = []
            seen_video_ids = set()

            for result in results:
                video_url = result["video_url"]

                # Extract YouTube video ID for deduplication
                match = re.search(r'v=([a-zA-Z0-9_-]{11})', video_url)
                video_id = match.group(1) if match else video_url

                if video_id not in seen_video_ids:
                    unique_results.append(result)
                    seen_video_ids.add(video_id)

            # Count by platform
            platform_counts = {}
            for result in unique_results:
                platform = result.get("platform", "unknown")
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            response = {
                "items": unique_results,
                "summary": {
                    "total_rows": len(values),
                    "processed_rows": processed_count,
                    "pages_processed": pages_processed,
                    "pages_failed": pages_failed,
                    "videos_found": len(unique_results),
                    "by_platform": platform_counts,
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
            List of YouTube URLs found on the page
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
                    if src and self._is_youtube_url(src):
                        normalized = self._normalize_youtube_url(src)
                        if normalized:
                            youtube_urls.add(normalized)

                # Extract from anchor links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if self._is_youtube_url(href):
                        normalized = self._normalize_youtube_url(href)
                        if normalized:
                            youtube_urls.add(normalized)

                # Extract from og:video meta tags
                for meta in soup.find_all('meta', property='og:video'):
                    content = meta.get('content', '')
                    if content and self._is_youtube_url(content):
                        normalized = self._normalize_youtube_url(content)
                        if normalized:
                            youtube_urls.add(normalized)

            except Exception as e:
                print(f"BeautifulSoup parsing failed for {page_url}: {str(e)}")

            # Method 2: Regex extraction from raw HTML
            youtube_patterns = [
                r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
                r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
                r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            ]

            for pattern in youtube_patterns:
                matches = re.finditer(pattern, html_content)
                for match in matches:
                    video_id = match.group(1)
                    youtube_urls.add(f"https://www.youtube.com/watch?v={video_id}")

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
            print(f"Found {len(data['items'])} video(s) from pages:")
            for item in data['items'][:5]:  # Show first 5
                print(f"  - Source: {item['source_page_url']}")
                print(f"    Video:  {item['video_url']}")
                print(f"    Platform: {item['platform']}")
                print()
                
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()