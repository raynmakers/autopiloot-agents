"""
CleanupTranscriptionAudio tool for removing temporary audio files from Firebase Storage.
Implements cleanup after successful AssemblyAI transcription.
"""

import os
import sys
import json
from pydantic import Field
from agency_swarm.tools import BaseTool
from google.cloud import storage

# Add core and config directories to path
from config.env_loader import get_required_env_var



class CleanupTranscriptionAudio(BaseTool):
    """
    Delete temporary audio files from Firebase Storage after successful transcription.

    This tool should be called after PollTranscriptionJob completes successfully
    to clean up the temporary audio file uploaded to Firebase Storage.

    Workflow:
    1. Verify storage_path is provided
    2. Delete file from Firebase Storage
    3. Return confirmation or error

    Firebase Storage path format: tmp/transcription/video_id.{ext}
    """

    storage_path: str = Field(
        ...,
        description="Firebase Storage path to delete (e.g., 'tmp/transcription/dQw4w9WgXcQ.m4a')"
    )

    def run(self) -> str:
        """
        Delete temporary audio file from Firebase Storage.

        Returns:
            JSON string with:
            - success: Boolean indicating if deletion succeeded
            - storage_path: Path that was deleted
            - message: Human-readable result message
        """
        try:
            # Get project ID for bucket name
            project_id = get_required_env_var(
                "GCP_PROJECT_ID",
                "Google Cloud Project ID for Firebase Storage"
            )

            # Default to project bucket
            # Firebase Storage bucket (newer projects use .firebasestorage.app)
            bucket_name = f"{project_id}.firebasestorage.app"

            # Initialize Storage client
            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(bucket_name)

            # Get blob reference
            blob = bucket.blob(self.storage_path)

            # Check if file exists
            if not blob.exists():
                return json.dumps({
                    "success": False,
                    "storage_path": self.storage_path,
                    "message": f"File not found: {self.storage_path}"
                })

            # Delete the file
            blob.delete()

            return json.dumps({
                "success": True,
                "storage_path": self.storage_path,
                "message": f"Successfully deleted {self.storage_path}"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "storage_path": self.storage_path,
                "error": "cleanup_failed",
                "message": f"Failed to delete file: {str(e)}"
            })


if __name__ == "__main__":
    print("=" * 80)
    print("CleanupTranscriptionAudio Tool Test")
    print("=" * 80)
    print("\nThis tool deletes temporary audio files from Firebase Storage")
    print("after successful transcription completion.\n")

    # Test 1: Try to delete a non-existent file (expected to fail)
    print("TEST 1: Attempt to delete non-existent file")
    print("-" * 80)

    tool_1 = CleanupTranscriptionAudio(
        storage_path="tmp/transcription/test_nonexistent.m4a"
    )

    try:
        result = tool_1.run()
        print("\nCleanupTranscriptionAudio test result:")
        print(result)

        data = json.loads(result)
        if data.get("success"):
            print(f"\n✅ Success: {data.get('message')}")
        else:
            print(f"\n⚠️ Expected failure: {data.get('message')}")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST 2: Delete actual test file (if exists)")
    print("-" * 80)
    print("\nTo test deletion of actual files, first run:")
    print("  python transcriber_agent/tools/get_video_audio_url.py")
    print("\nThen use the storage_path from that output:")
    print("  python transcriber_agent/tools/cleanup_transcription_audio.py")
    print("\nExample usage in workflow:")
    print("  1. GetVideoAudioUrl → returns storage_path")
    print("  2. SubmitAssemblyAIJob → uses signed_url, stores storage_path")
    print("  3. PollTranscriptionJob → checks completion")
    print("  4. CleanupTranscriptionAudio → deletes using storage_path")

    print("\n" + "=" * 80)
    print("Testing complete!")
    print("=" * 80)
