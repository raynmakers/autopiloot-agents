"""
GetVideoAudioUrl tool for extracting direct audio URLs from YouTube videos.
Implements TASK-TRN-0020: Resolve audio source for AssemblyAI transcription.
Streams audio directly to Firebase Storage without local downloads.

IMPORTANT: Configure Firebase Storage Lifecycle Management for automatic cleanup:
- Files in tmp/transcription/ should auto-delete after 24 hours
- Set up via Firebase Console > Storage > Rules > Lifecycle
- Or use gcloud:
  gsutil lifecycle set lifecycle.json gs://your-bucket.firebasestorage.app

Example lifecycle.json:
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 1,
          "matchesPrefix": ["tmp/transcription/"]
        }
      }
    ]
  }
}

This ensures automatic cleanup even if CleanupTranscriptionAudio tool fails.
"""

import os
import json
import time
import yt_dlp
import requests
from agency_swarm.tools import BaseTool
from pydantic import Field
from typing import Optional
from google.cloud import storage
from datetime import timedelta

# Add core and config directories to path
import sys
from config.env_loader import get_required_env_var



class GetVideoAudioUrl(BaseTool):
    """
    Extracts audio from YouTube videos for AssemblyAI transcription.

    Streams audio directly to Firebase Storage for temporary hosting without local downloads.
    Returns a signed URL that won't expire during AssemblyAI processing.
    This prevents YouTube URL expiration issues that cause "Download error" failures.

    Workflow:
    1. Extract direct audio URL from YouTube (no download)
    2. Stream audio to Firebase Storage (tmp/transcription/ folder)
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
        description="Firebase Storage bucket name (defaults to GCP_PROJECT_ID.firebasestorage.app)"
    )
    
    def run(self) -> str:
        """
        Extract audio URL and stream directly to Firebase Storage.

        Process:
        1. Extract video metadata and direct audio URL from YouTube (no download)
        2. Check if audio file already exists in Firebase Storage and is <20 hours old
        3. If exists and fresh: return existing file's signed URL (skip download)
        4. If not: stream audio to Firebase Storage (tmp/transcription/ folder)
        5. Generate signed URL with 24-hour expiration
        6. Return storage_path and signed_url

        Returns:
            str: JSON string with:
            - storage_path: Firebase Storage path (for cleanup)
            - signed_url: Temporary signed URL for AssemblyAI
            - video_id: YouTube video ID
            - duration: Video duration in seconds
            - title: Video title
            - format: Audio format (m4a, webm, etc.)
            - cached: Boolean indicating if existing file was reused
        """
        timings = {}
        overall_start = time.time()

        try:
            # Step 1: Extract video metadata and direct audio URL
            step_start = time.time()
            print("Extracting video metadata and audio URL from YouTube...")
            video_info = self._extract_video_info()
            timings['extract_metadata'] = time.time() - step_start
            print(f"  ⏱️  Metadata extraction: {timings['extract_metadata']:.2f}s")

            if "error" in video_info:
                return json.dumps(video_info)

            # Step 2: Check if file already exists and is fresh
            step_start = time.time()
            print("Checking if audio file already exists in Firebase Storage...")
            existing_file = self._check_existing_file(
                video_id=video_info["video_id"],
                file_extension=video_info.get("format", "m4a")
            )
            timings['check_cache'] = time.time() - step_start
            print(f"  ⏱️  Cache check: {timings['check_cache']:.2f}s")

            if existing_file and existing_file.get("is_fresh"):
                timings['total'] = time.time() - overall_start
                print(f"✅ Found fresh audio file (age: {existing_file['age_hours']:.1f} hours)")
                print("Skipping download, reusing existing file...")
                print(f"  ⏱️  Total time: {timings['total']:.2f}s")

                result = {
                    "storage_path": existing_file["storage_path"],
                    "signed_url": existing_file["signed_url"],
                    "video_id": video_info["video_id"],
                    "duration": video_info.get("duration", 0),
                    "title": video_info.get("title", "Unknown"),
                    "format": video_info.get("format", "m4a"),
                    "cached": True,
                    "cache_age_hours": existing_file["age_hours"],
                    "timings": timings
                }
                return json.dumps(result, indent=2)

            # Step 3: Stream audio directly to Firebase Storage
            step_start = time.time()
            print("Streaming audio to Firebase Storage...")
            storage_result = self._stream_to_firebase_storage(
                audio_url=video_info["audio_url"],
                video_id=video_info["video_id"],
                file_extension=video_info.get("format", "m4a")
            )
            timings['upload_to_storage'] = time.time() - step_start
            print(f"  ⏱️  Upload to storage: {timings['upload_to_storage']:.2f}s")

            if "error" in storage_result:
                return json.dumps(storage_result)

            # Calculate totals
            timings['total'] = time.time() - overall_start
            duration_min = video_info.get("duration", 0) / 60
            print(f"\n📊 Performance Summary:")
            print(f"  Video duration: {duration_min:.1f} min")
            print(f"  Total time: {timings['total']:.2f}s")
            print(f"  Speed ratio: {duration_min * 60 / timings['total']:.1f}x realtime")

            # Return complete result
            result = {
                "storage_path": storage_result["storage_path"],
                "signed_url": storage_result["signed_url"],
                "video_id": video_info["video_id"],
                "duration": video_info.get("duration", 0),
                "title": video_info.get("title", "Unknown"),
                "format": video_info.get("format", "m4a"),
                "cached": False,
                "timings": timings
            }
            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "processing_failed",
                "message": f"Failed to process video audio: {str(e)}",
                "storage_path": None,
                "signed_url": None
            })
    
    def _check_existing_file(self, video_id: str, file_extension: str) -> Optional[dict]:
        """
        Check if audio file already exists in Firebase Storage and is fresh (<20 hours old).

        Args:
            video_id: YouTube video ID
            file_extension: File extension (e.g., 'm4a', 'webm')

        Returns:
            dict with storage_path, signed_url, is_fresh, age_hours if file exists and is fresh
            None if file doesn't exist or is too old
        """
        try:
            # Get project ID for bucket name
            project_id = get_required_env_var(
                "GCP_PROJECT_ID",
                "Google Cloud Project ID for Firebase Storage"
            )

            # Use provided bucket or default to project bucket
            # Firebase Storage bucket (newer projects use .firebasestorage.app)
            bucket_name = self.firebase_bucket or f"{project_id}.firebasestorage.app"

            # Initialize Storage client
            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(bucket_name)

            # Check if file exists
            storage_path = f"tmp/transcription/{video_id}.{file_extension}"
            blob = bucket.blob(storage_path)

            if not blob.exists():
                print(f"No existing file found at {storage_path}")
                return None

            # Get file metadata
            blob.reload()  # Refresh metadata

            # Check file age
            from datetime import datetime, timezone
            created_time = blob.time_created
            current_time = datetime.now(timezone.utc)
            age_hours = (current_time - created_time).total_seconds() / 3600

            # If file is older than 20 hours, don't reuse it
            if age_hours >= 20:
                print(f"Found file but it's too old ({age_hours:.1f} hours)")
                return None

            # File exists and is fresh - generate signed URL
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=24),
                method="GET"
            )

            return {
                "storage_path": storage_path,
                "signed_url": signed_url,
                "is_fresh": True,
                "age_hours": age_hours
            }

        except Exception as e:
            print(f"Error checking existing file: {str(e)}")
            return None

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
            # Firebase Storage bucket (newer projects use .firebasestorage.app)
            bucket_name = self.firebase_bucket or f"{project_id}.firebasestorage.app"

            # Initialize Storage client
            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(bucket_name)

            # Create storage path: tmp/transcription/video_id.extension
            storage_path = f"tmp/transcription/{video_id}.{file_extension}"
            blob = bucket.blob(storage_path)

            # Stream audio from YouTube to Firebase Storage with retry logic
            print(f"Streaming {file_extension} audio to Firebase Storage...")

            download_start = time.time()

            # Use requests session for better connection handling
            session = requests.Session()
            session.headers.update({'Connection': 'keep-alive'})

            # Download with retry on connection errors
            max_retries = 3
            retry_delay = 5

            for attempt in range(max_retries):
                try:
                    response = session.get(audio_url, stream=True, timeout=600)
                    response.raise_for_status()
                    print(f"  ⏱️  Started streaming from YouTube ({time.time() - download_start:.2f}s)")
                    break
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if attempt < max_retries - 1:
                        print(f"  ⚠️  Connection error (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise

            # Set custom metadata for 24-hour expiration tracking
            from datetime import datetime, timezone
            expiration_time = datetime.now(timezone.utc) + timedelta(hours=24)

            # Use resumable upload for better reliability with large files
            upload_start = time.time()

            # Upload with retry on connection errors
            for attempt in range(max_retries):
                try:
                    # Upload using resumable strategy for large files
                    # Chunk size helps with large uploads
                    blob.upload_from_file(
                        response.raw,
                        content_type=f"audio/{file_extension}",
                        timeout=600,  # Increased timeout for large files
                        checksum=None  # Disable checksum for streaming uploads
                    )
                    break
                except Exception as e:
                    if attempt < max_retries - 1 and ("Connection" in str(e) or "reset" in str(e).lower()):
                        print(f"  ⚠️  Upload error (attempt {attempt + 1}/{max_retries}), retrying...")
                        time.sleep(5)
                        # Re-fetch the stream
                        response = session.get(audio_url, stream=True, timeout=600)
                        response.raise_for_status()
                    else:
                        raise

            upload_duration = time.time() - upload_start
            print(f"  ⏱️  Upload completed: {upload_duration:.2f}s")

            # Estimate file size from content-length if available
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                speed_mbps = (size_mb / upload_duration) if upload_duration > 0 else 0
                print(f"  📦 File size: {size_mb:.1f} MB")
                print(f"  🚀 Upload speed: {speed_mbps:.2f} MB/s")

            # Close the session
            session.close()

            # Set metadata after upload (includes 24h expiration marker)
            blob.metadata = {
                'expires_at': expiration_time.isoformat(),
                'video_id': video_id,
                'purpose': 'temporary_transcription_audio'
            }
            blob.patch()

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
    print("\nNOTE: Files stored in tmp/transcription/ folder")
    print("Clean up after successful transcription using CleanupTranscriptionAudio tool")
    print("=" * 80)