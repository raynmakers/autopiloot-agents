"""
MarkVideoRejected tool for marking videos as rejected non-business content.
Prevents reprocessing of entertainment/music content that doesn't contain business insights.
"""

import os
import sys
import json
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore

# Add core and config directories to path
from env_loader import get_required_env_var
from audit_logger import audit_logger


class MarkVideoRejected(BaseTool):
    """
    Mark a video as rejected non-business content in Firestore.

    Updates the video document status to 'rejected_non_business' and stores the rejection
    reason. This prevents the system from repeatedly attempting to process entertainment
    or non-business content.

    Status progression for rejected content:
    transcribed → rejected_non_business (final state)
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID to mark as rejected"
    )

    content_type: str = Field(
        ...,
        description="Type of content (e.g., 'Song Lyrics', 'Entertainment', 'Music Video')"
    )

    reason: str = Field(
        ...,
        description="Detailed explanation of why content was rejected"
    )

    title: str = Field(
        default="",
        description="Video title for logging"
    )

    def run(self) -> str:
        """
        Mark video as rejected non-business content in Firestore.

        Process:
        1. Initialize Firestore client
        2. Update video status to 'rejected_non_business'
        3. Store rejection metadata (content_type, reason, rejected_at)
        4. Log rejection to audit trail

        Returns:
            JSON string with:
            - ok: Boolean indicating success
            - video_id: YouTube video ID
            - status: New status (rejected_non_business)
            - message: Confirmation message
        """
        try:
            # Initialize Firestore
            project_id = get_required_env_var(
                "GCP_PROJECT_ID",
                "Google Cloud Project ID for Firestore"
            )

            db = firestore.Client(project=project_id)

            # Get video document
            video_ref = db.collection('videos').document(self.video_id)
            video_doc = video_ref.get()

            if not video_doc.exists:
                return json.dumps({
                    "error": "video_not_found",
                    "message": f"Video {self.video_id} not found in Firestore",
                    "video_id": self.video_id
                })

            # Update video status with rejection metadata
            current_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

            video_ref.update({
                'status': 'rejected_non_business',
                'rejection': {
                    'content_type': self.content_type,
                    'reason': self.reason,
                    'rejected_at': current_time
                },
                'updated_at': firestore.SERVER_TIMESTAMP
            })

            # Log rejection to audit trail
            try:
                audit_logger.log_video_rejected(
                    video_id=self.video_id,
                    content_type=self.content_type,
                    reason=self.reason,
                    actor="SummarizerAgent"
                )
            except Exception as audit_error:
                # Don't fail if audit logging fails
                print(f"Warning: Audit logging failed: {str(audit_error)}")

            return json.dumps({
                "ok": True,
                "video_id": self.video_id,
                "status": "rejected_non_business",
                "content_type": self.content_type,
                "reason": self.reason,
                "message": f"Video {self.video_id} marked as rejected non-business content"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "rejection_failed",
                "message": f"Failed to mark video as rejected: {str(e)}",
                "video_id": self.video_id
            })


if __name__ == "__main__":
    print("=" * 80)
    print("MarkVideoRejected Tool Test")
    print("=" * 80)

    # Test 1: Mark Rick Astley video as rejected
    print("\nTEST 1: Mark Rick Astley video as rejected (non-business content)")
    print("-" * 80)

    tool = MarkVideoRejected(
        video_id="dQw4w9WgXcQ",
        content_type="Song Lyrics",
        reason="The transcript is composed entirely of the lyrics of 'Never Gonna Give You Up' by Rick Astley. It is designed for entertainment purposes and does not provide any direct business, marketing, sales, strategy, or educational content.",
        title="Never Gonna Give You Up - Rick Astley"
    )

    try:
        result = tool.run()
        print("\nResult:")
        print(result)

        data = json.loads(result)
        if data.get("ok"):
            print(f"\n✅ Success: Video marked as rejected")
            print(f"   Status: {data.get('status')}")
            print(f"   Content Type: {data.get('content_type')}")
        else:
            print(f"\n❌ Error: {data.get('message', 'Unknown error')}")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Testing complete!")
    print("\nNote: This marks videos as 'rejected_non_business' to prevent reprocessing")
    print("Status flow: transcribed → rejected_non_business (final state)")
    print("=" * 80)
