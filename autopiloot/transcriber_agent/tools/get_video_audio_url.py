"""
GetVideoAudioUrl tool for extracting direct audio URLs from YouTube videos.
Implements TASK-TRN-0020: Resolve audio source for AssemblyAI transcription.
"""

import os
import json
import tempfile
import yt_dlp
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


class GetVideoAudioUrl(BaseTool):
    """
    Extracts direct audio URL from YouTube videos for AssemblyAI transcription.
    
    Prefers remote URL for direct streaming to AssemblyAI, with fallback to local
    download if remote URL extraction fails. Handles age restrictions, live streams,
    and various error conditions gracefully.
    """
    
    video_url: str = Field(
        ...,
        description="YouTube video URL to extract audio from (e.g., 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')"
    )
    
    prefer_download: bool = Field(
        default=False,
        description="Force local download instead of remote URL extraction"
    )
    
    def run(self) -> str:
        """
        Extract audio URL from YouTube video, preferring remote URL for AssemblyAI.
        
        Priority:
        1. Try to extract remote audio URL directly from YouTube
        2. Fallback to downloading audio locally if remote fails or prefer_download=True
        3. Return error if both methods fail
        
        Returns:
            str: JSON string with either remote_url or local_path for audio
        """
        try:
            # First attempt: Extract remote URL (unless prefer_download is set)
            if not self.prefer_download:
                remote_result = self._extract_remote_url()
                if remote_result and "remote_url" in remote_result and remote_result["remote_url"]:
                    return json.dumps(remote_result, indent=2)
            
            # Second attempt: Download audio locally as fallback
            local_result = self._download_audio_locally()
            if local_result and "local_path" in local_result:
                return json.dumps(local_result, indent=2)
            
            # Both methods failed
            return json.dumps({
                "error": "Failed to extract audio URL via both remote and local methods",
                "remote_url": None,
                "local_path": None
            })
                
        except Exception as e:
            return json.dumps({
                "error": f"Failed to get video audio URL: {str(e)}",
                "remote_url": None,
                "local_path": None
            })
    
    def _extract_remote_url(self) -> Optional[dict]:
        """
        Extract remote audio URL without downloading.
        
        Returns:
            dict with remote_url or None if extraction fails
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                # More flexible format selection - try multiple options
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)
                
                # Check for restrictions
                if info.get('age_limit', 0) >= 18:
                    return {
                        "error": "age_restricted",
                        "message": "Video is age-restricted and cannot be processed",
                        "remote_url": None
                    }
                
                if info.get('is_live'):
                    return {
                        "error": "live_stream",
                        "message": "Live videos are not supported",
                        "remote_url": None
                    }
                
                # Extract best audio format URL
                formats = info.get('formats', [])
                audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('acodec') is not None]

                if audio_formats:
                    # Sort by bitrate to get best quality (handle None values)
                    audio_formats.sort(key=lambda x: x.get('abr') or 0, reverse=True)
                    best_audio = audio_formats[0]
                    audio_url = best_audio.get('url')
                    
                    if audio_url:
                        return {
                            "remote_url": audio_url,
                            "format": best_audio.get('ext', 'unknown'),
                            "bitrate": best_audio.get('abr', 0),
                            "duration": info.get('duration', 0),
                            "video_id": info.get('id'),
                            "title": info.get('title', 'Unknown')
                        }
                
                # Try direct video URL as last resort for remote processing
                return {
                    "remote_url": self.video_url,
                    "note": "Using original video URL for remote processing",
                    "duration": info.get('duration', 0)
                }
                
        except yt_dlp.utils.DownloadError as e:
            error_str = str(e)
            print(f"Remote URL extraction failed: {error_str}")
            if 'Private video' in error_str:
                return {"error": "private_video", "message": "Video is private and cannot be accessed"}
            elif 'Video unavailable' in error_str:
                return {"error": "unavailable", "message": "Video is unavailable"}
            else:
                return {"error": "download_error", "message": f"Failed to extract: {error_str}"}
        except Exception as e:
            print(f"Remote URL extraction exception: {str(e)}")
            return None  # Silent fail, will try local download
    
    def _download_audio_locally(self) -> Optional[dict]:
        """
        Download audio to local temporary file as fallback.
        
        Returns:
            dict with local_path or None if download fails
        """
        try:
            # Create temporary directory for audio download
            temp_dir = tempfile.mkdtemp(prefix="autopiloot_audio_")
            output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
            
            # Try to use FFmpeg if available, otherwise download original format
            ydl_opts = {
                'quiet': False,  # Enable output for debugging
                'no_warnings': False,
                # More flexible format selection for download
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
                'outtmpl': output_template,
            }

            # Only add FFmpeg post-processor if FFmpeg is available
            try:
                import subprocess
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
                print("FFmpeg detected - will convert to MP3")
            except (FileNotFoundError, subprocess.CalledProcessError):
                print("FFmpeg not found - will keep original format")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=True)

                # Find the downloaded file
                video_id = info.get('id')

                # Check for all possible extensions (including original formats)
                for ext in ['mp3', 'm4a', 'webm', 'ogg', 'wav', 'opus']:
                    file_path = os.path.join(temp_dir, f"{video_id}.{ext}")
                    if os.path.exists(file_path):
                        print(f"Found downloaded file: {file_path}")
                        return {
                            "local_path": file_path,
                            "format": ext,
                            "duration": info.get('duration', 0),
                            "video_id": video_id,
                            "title": info.get('title', 'Unknown'),
                            "note": "Audio downloaded locally for processing"
                        }

                # List what files were actually created
                print(f"Files in temp_dir: {os.listdir(temp_dir)}")
                return None  # Download completed but file not found
                
        except Exception:
            return None  # Silent fail


if __name__ == "__main__":
    # Test the tool with Agency Swarm v1.0.0 pattern
    print("Testing GetVideoAudioUrl tool...")
    
    # Test with a sample video URL
    tool = GetVideoAudioUrl(
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    
    try:
        result = tool.run()
        print("\nGetVideoAudioUrl test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data.get('message', data['error'])}")
        elif "remote_url" in data and data["remote_url"]:
            print(f"\n✅ Success: Remote audio URL obtained")
            print(f"   Format: {data.get('format', 'unknown')}")
            print(f"   Duration: {data.get('duration', 0)} seconds")
            print(f"   Bitrate: {data.get('bitrate', 'unknown')} kbps")
        elif "local_path" in data and data["local_path"]:
            print(f"\n✅ Success: Audio downloaded locally")
            print(f"   Path: {data['local_path']}")
            print(f"   Format: {data.get('format', 'unknown')}")
            print(f"   Duration: {data.get('duration', 0)} seconds")
        else:
            print("\n⚠️ Unexpected response format")
                
    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test with prefer_download option
    print("\n" + "="*50)
    print("Testing with prefer_download=True...")
    
    tool_download = GetVideoAudioUrl(
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        prefer_download=True
    )
    
    try:
        result = tool_download.run()
        data = json.loads(result)
        if "local_path" in data and data["local_path"]:
            print(f"✅ Local download successful: {data['local_path']}")
            # Clean up temp file
            if os.path.exists(data['local_path']):
                os.remove(data['local_path'])
                print("   Cleaned up temporary file")
        else:
            print("⚠️ Local download did not produce expected result")
    except Exception as e:
        print(f"❌ Download test error: {str(e)}")