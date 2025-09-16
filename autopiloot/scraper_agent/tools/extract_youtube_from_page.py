"""
ExtractYouTubeFromPage tool for extracting YouTube URLs from web pages.
Searches through HTML content to find embedded YouTube videos and links.
"""

import os
import json
import requests
from bs4 import BeautifulSoup
import re
from typing import List
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class ExtractYouTubeFromPage(BaseTool):
    """
    Extracts YouTube video URLs from a given web page.
    
    This tool fetches the HTML content of a web page and searches for YouTube URLs
    in various formats including embedded iframes, direct links, meta tags, and
    JavaScript content. Returns a structured list of unique YouTube video URLs.
    """
    
    page_url: str = Field(
        ...,
        description="The URL of the web page to extract YouTube links from"
    )
    
    def run(self) -> str:
        """
        Extract YouTube URLs from the specified web page.
        
        Returns:
            str: JSON string containing array of video objects with video_url field
        """
        try:
            youtube_urls = []
            youtube_pattern = re.compile(
                r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})'
            )
            
            # Fetch page content
            response = requests.get(self.page_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Search in raw HTML text
            for match in youtube_pattern.finditer(response.text):
                video_id = match.group(1)
                youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            # Search in iframe src attributes
            for iframe in soup.find_all('iframe'):
                src = iframe.get('src', '')
                if 'youtube.com/embed/' in src or 'youtube-nocookie.com/embed/' in src:
                    match = youtube_pattern.search(src)
                    if match:
                        video_id = match.group(1)
                        youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            # Search in link href attributes
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'youtube.com/watch' in href or 'youtu.be/' in href:
                    match = youtube_pattern.search(href)
                    if match:
                        video_id = match.group(1)
                        youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            # Search in meta og:video tags
            meta_og_video = soup.find('meta', property='og:video')
            if meta_og_video and meta_og_video.get('content'):
                match = youtube_pattern.search(meta_og_video['content'])
                if match:
                    video_id = match.group(1)
                    youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            # Search in script tags
            for script in soup.find_all('script'):
                if script.string:
                    for match in youtube_pattern.finditer(script.string):
                        video_id = match.group(1)
                        youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            # Deduplicate URLs
            youtube_urls = list(set(youtube_urls))
            
            # Format response according to task requirements
            videos = [{"video_url": url} for url in youtube_urls]
            
            response = {
                "videos": videos,
                "summary": {
                    "page_url": self.page_url,
                    "videos_found": len(videos)
                }
            }
            
            return json.dumps(response, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to extract YouTube URLs from page: {str(e)}",
                "videos": []
            })


if __name__ == "__main__":
    # Test the tool
    tool = ExtractYouTubeFromPage(
        page_url="https://www.youtube.com/"
    )
    
    try:
        result = tool.run()
        print("ExtractYouTubeFromPage test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Found {len(data['videos'])} YouTube URLs")
            for video in data['videos'][:3]:  # Show first 3
                print(f"  - {video['video_url']}")
                
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()