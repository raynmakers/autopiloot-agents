import os
import json
from typing import Dict, Any, List
import requests
from bs4 import BeautifulSoup
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class ExtractYouTubeFromPage(BaseTool):
    def __init__(self):
        super().__init__()
    
    def _validate_env_vars(self):
        pass
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        page_url = request.get('page_url', '')
        
        if not page_url:
            raise ValueError("page_url is required")
        
        youtube_urls = []
        youtube_pattern = re.compile(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
        )
        
        try:
            response = requests.get(page_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
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
            
            meta_og_video = soup.find('meta', property='og:video')
            if meta_og_video and meta_og_video.get('content'):
                match = youtube_pattern.search(meta_og_video['content'])
                if match:
                    video_id = match.group(1)
                    youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            for script in soup.find_all('script'):
                if script.string:
                    for match in youtube_pattern.finditer(script.string):
                        video_id = match.group(1)
                        youtube_urls.append(f"https://www.youtube.com/watch?v={video_id}")
            
            youtube_urls = list(set(youtube_urls))
            
            videos = [{"video_url": url} for url in youtube_urls]
            
            return {"videos": videos}
            
        except Exception as e:
            raise RuntimeError(f"Failed to extract YouTube URLs from page: {str(e)}")


if __name__ == "__main__":
    tool = ExtractYouTubeFromPage()
    
    test_request = {
        "page_url": "https://www.youtube.com/"
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: Found {len(result.get('videos', []))} videos")
        if result.get('videos'):
            print(f"Videos: {json.dumps(result['videos'], indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")