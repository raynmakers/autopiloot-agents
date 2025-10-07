"""
GetVideoAudioUrl tool for extracting direct audio URLs from YouTube videos.
Implements TASK-TRN-0020: Resolve audio source for AssemblyAI transcription.
Streams audio directly to Firebase Storage without local downloads.
"""

import os
import json
import yt_dlp
import requests
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv
from typing import Optional
from google.cloud import storage
from datetime import timedelta

# Add core and config directories to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from config.env_loader import get_required_env_var

load_dotenv()


class GetVideoAudioUrl(BaseTool):
    """
    Extracts audio from YouTube videos for AssemblyAI transcription.

    Streams audio directly to Firebase Storage for temporary hosting without local downloads.
    Returns a signed URL that won't expire during AssemblyAI processing.
    This prevents YouTube URL expiration issues that cause "Download error" failures.

    Workflow:
    1. Extract direct audio URL from YouTube (no download)
    2. Stream audio to Firebase Storage (transcription_temp/ folder)
    3. Generate signed URL with 24-hour expiration
    4. Return storage_path and signed_url for AssemblyAI
    5. File should be deleted after successful transcription using CleanupTranscriptionAudio

    Benefits:
    - No local filesystem usage (Firebase Functions compatible)
    - Efficient streaming (no temporary files)
    - Lower memory footprint
    """

    video_url: str = Field(
        ...,
        description="YouTube video URL to extract audio from (e.g., 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')"
    )

    firebase_bucket: Optional[str] = Field(
        default=None,
        description="Firebase Storage bucket name (defaults to GCP_PROJECT_ID.appspot.com)"
    )
    
    def run(self) -> str:
        """
        Extract audio URL and stream directly to Firebase Storage.

        Process:
        1. Extract video metadata and direct audio URL from YouTube (no download)
        2. Stream audio directly to Firebase Storage (transcription_temp/ folder)
        3. Generate signed URL with 24-hour expiration
        4. Return storage_path and signed_url

        Returns:
            str: JSON string with:
            - storage_path: Firebase Storage path (for cleanup)
            - signed_url: Temporary signed URL for AssemblyAI
            - video_id: YouTube video ID
            - duration: Video duration in seconds
            - title: Video title
            - format: Audio format (m4a, webm, etc.)
        """
        try:
            # Step 1: Extract video metadata and direct audio URL
            print("Extracting video metadata and audio URL from YouTube...")
            video_info = self._extract_video_info()

            if "error" in video_info:
                return json.dumps(video_info)

            # Step 2: Stream audio directly to Firebase Storage
            print("Streaming audio to Firebase Storage...")
            storage_result = self._stream_to_firebase_storage(
                audio_url=video_info["audio_url"],
                video_id=video_info["video_id"],
                file_extension=video_info.get("format", "m4a")
            )

            if "error" in storage_result:
                return json.dumps(storage_result)

            # Return complete result
            return json.dumps({
                "storage_path": storage_result["storage_path"],
                "signed_url": storage_result["signed_url"],
                "video_id": video_info["video_id"],
                "duration": video_info.get("duration", 0),
                "title": video_info.get("title", "Unknown"),
                "format": video_info.get("format", "m4a")
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "processing_failed",
                "message": f"Failed to process video audio: {str(e)}",
                "storage_path": None,
                "signed_url": None
            })
    
    def _extract_video_info(self) -> dict:
        """
        Extract video metadata and direct audio URL from YouTube without downloading.

        Returns:
            dict with video_id, audio_url, duration, title, format, or error
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
                'extract_flat': False,  # Need full extraction to get URL
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)

                if not info:
                    return {
                        "error": "extraction_failed",
                        "message": "Failed to extract video information"
                    }

                # Get the best audio format
                audio_format = None
                if 'url' in info:
                    # Direct URL available
                    audio_format = {
                        'url': info['url'],
                        'ext': info.get('ext', 'm4a')
                    }
                elif 'formats' in info:
                    # Find best audio format
                    audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                    if audio_formats:
                        # Sort by quality (audio bitrate)
                        audio_formats.sort(key=lambda x: x.get('abr', 0) or 0, reverse=True)
                        audio_format = audio_formats[0]

                if not audio_format or 'url' not in audio_format:
                    return {
                        "error": "no_audio_url",
                        "message": "Could not extract direct audio URL from video"
                    }

                return {
                    "video_id": info.get('id'),
                    "audio_url": audio_format['url'],
                    "format": audio_format.get('ext', 'm4a'),
                    "duration": info.get('duration', 0),
                    "title": info.get('title', 'Unknown')
                }

        except Exception as e:
            return {
                "error": "extraction_failed",
                "message": f"Failed to extract video info: {str(e)}"
            }

    def _stream_to_firebase_storage(
        self,
        audio_url: str,
        video_id: str,
        file_extension: str
    ) -> dict:
        """
        Stream audio directly from YouTube to Firebase Storage without local download.

        Args:
            audio_url: Direct audio URL from YouTube
            video_id: YouTube video ID
            file_extension: File extension (e.g., 'm4a', 'webm')

        Returns:
            dict with storage_path and signed_url, or error
        """
        try:
            # Get project ID for bucket name
            project_id = get_required_env_var(
                "GCP_PROJECT_ID",
                "Google Cloud Project ID for Firebase Storage"
            )

            # Use provided bucket or default to project bucket
            # Firebase now uses .firebasestorage.app for new projects
            bucket_name = self.firebase_bucket or f"{project_id}.firebasestorage.app"

            # Initialize Storage client
            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(bucket_name)

            # Create storage path: transcription_temp/video_id.extension
            storage_path = f"transcription_temp/{video_id}.{file_extension}"
            blob = bucket.blob(storage_path)

            # Stream audio from YouTube to Firebase Storage
            print(f"Streaming {file_extension} audio to Firebase Storage...")
            response = requests.get(audio_url, stream=True, timeout=300)
            response.raise_for_status()

            # Upload in chunks to handle large files efficiently
            blob.upload_from_file(
                response.raw,
                content_type=f"audio/{file_extension}",
                timeout=300
            )

            print(f"✅ Successfully uploaded to {storage_path}")

            # Generate signed URL with 24-hour expiration
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=24),
                method="GET"
            )

            return {
                "storage_path": storage_path,
                "signed_url": signed_url,
                "bucket": bucket_name
            }

        except requests.RequestException as e:
            return {
                "error": "stream_download_failed",
                "message": f"Failed to download audio stream: {str(e)}"
            }
        except Exception as e:
            return {
                "error": "firebase_upload_failed",
                "message": f"Failed to upload to Firebase Storage: {str(e)}"
            }


if __name__ == "__main__":
    # Test the tool with both test videos
    print("=" * 80)
    print("TEST 1: Rick Astley - Never Gonna Give You Up (Entertainment/Music)")
    print("=" * 80)

    tool_1 = GetVideoAudioUrl(
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    try:
        result = tool_1.run()
        print("\nGetVideoAudioUrl test result:")
        print(result)

        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data.get('message', data['error'])}")
        elif "signed_url" in data and data["signed_url"]:
            print(f"\n✅ Success: Audio streamed to Firebase Storage")
            print(f"   Storage path: {data.get('storage_path')}")
            print(f"   Format: {data.get('format', 'unknown')}")
            print(f"   Duration: {data.get('duration', 0)} seconds")
            print(f"   Signed URL (first 100 chars): {data['signed_url'][:100]}...")
            print(f"   ⚡ No local download - streamed directly to Firebase Storage")
        else:
            print("\n⚠️ Unexpected response format")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST 2: Dan Martell - How to 10x Your Business (Business/Educational)")
    print("=" * 80)

    tool_2 = GetVideoAudioUrl(
        video_url="https://www.youtube.com/watch?v=mZxDw92UXmA"
    )

    try:
        result = tool_2.run()
        print("\nGetVideoAudioUrl test result:")
        print(result)

        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data.get('message', data['error'])}")
        elif "signed_url" in data and data["signed_url"]:
            print(f"\n✅ Success: Audio streamed to Firebase Storage")
            print(f"   Storage path: {data.get('storage_path')}")
            print(f"   Format: {data.get('format', 'unknown')}")
            print(f"   Duration: {data.get('duration', 0)} seconds")
            print(f"   Signed URL (first 100 chars): {data['signed_url'][:100]}...")
            print(f"   ⚡ No local download - streamed directly to Firebase Storage")
        else:
            print("\n⚠️ Unexpected response format")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Testing complete! Both videos streamed to Firebase Storage:")
    print("- dQw4w9WgXcQ: Rick Astley (will be rejected at summarization)")
    print("- mZxDw92UXmA: Dan Martell (will be processed normally)")
    print("\n⚡ BENEFITS:")
    print("  - No local filesystem usage (Firebase Functions compatible)")
    print("  - Efficient streaming (no temporary files)")
    print("  - Lower memory footprint")
    print("\nNOTE: Files stored in transcription_temp/ folder")
    print("Clean up after successful transcription using CleanupTranscriptionAudio tool")
    print("=" * 80)