import os
import json
from typing import Dict, Any
import yt_dlp
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class GetVideoAudioUrl(BaseTool):
    def __init__(self):
        super().__init__()
    
    def _validate_env_vars(self):
        pass
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        video_url = request.get('video_url', '')
        
        if not video_url:
            raise ValueError("video_url is required")
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'format': 'bestaudio/best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                if info.get('age_limit', 0) >= 18:
                    raise ValueError("Video is age-restricted")
                
                if info.get('is_live'):
                    raise ValueError("Live videos are not supported")
                
                formats = info.get('formats', [])
                audio_formats = [f for f in formats if f.get('acodec') != 'none']
                
                if audio_formats:
                    best_audio = max(audio_formats, key=lambda x: x.get('abr', 0))
                    audio_url = best_audio.get('url')
                    
                    if audio_url:
                        return {"remote_url": audio_url}
                
                return {"remote_url": video_url}
                
        except yt_dlp.utils.DownloadError as e:
            if 'Private video' in str(e):
                raise ValueError("Video is private")
            elif 'Video unavailable' in str(e):
                raise ValueError("Video is unavailable")
            else:
                raise RuntimeError(f"Failed to get audio URL: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to get video audio URL: {str(e)}")


if __name__ == "__main__":
    tool = GetVideoAudioUrl()
    
    test_request = {
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: Audio URL obtained")
        print(f"Type: {'remote_url' if 'remote_url' in result else 'local_path'}")
    except Exception as e:
        print(f"Error: {str(e)}")