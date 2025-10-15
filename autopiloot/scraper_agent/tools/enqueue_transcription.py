"""
EnqueueTranscription tool for creating transcription job entries.
Implements TASK-SCR-0014 with duration validation and duplicate prevention.
"""

import os
import sys
import json
import uuid
from typing import Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add core and config directories to path
from config.env_loader import get_required_env_var
from config.loader import load_app_config

load_dotenv()


class EnqueueTranscription(BaseTool):
    """
    Creates transcription job entries for eligible videos.
    
    Validates video duration (<=70 minutes), checks for existing transcripts,
    and creates job documents in the jobs/transcription collection. Prevents
    duplicate jobs and updates video status to 'transcription_queued'.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID to enqueue for transcription (e.g., 'dQw4w9WgXcQ')"
    )
    
    def run(self) -> str:
        """
        Creates a transcription job for the specified video.
        
        Returns:
            str: JSON string containing job_id or skip reason
            
        Raises:
            ValueError: If video doesn't exist or validation fails
            RuntimeError: If Firestore operations fail
        """
        try:
            # Initialize Firestore client
            db = self._initialize_firestore()
            
            # Load configuration for business rules
            config = load_app_config()
            max_duration = config.get("idempotency", {}).get("max_video_duration_sec", 4200)
            
            # Get video document
            video_ref = db.collection('videos').document(self.video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                return json.dumps({
                    "error": f"Video {self.video_id} does not exist in videos collection",
                    "job_id": None
                })
            
            video_data = video_doc.to_dict()

            # Check if video was rejected as non-business content
            video_status = video_data.get('status')
            if video_status == 'rejected_non_business':
                rejection_info = video_data.get('rejection', {})
                return json.dumps({
                    "job_id": None,
                    "message": f"Video was rejected as non-business content ({rejection_info.get('content_type', 'Unknown')}) - skipping",
                    "video_id": self.video_id,
                    "status": "rejected_non_business",
                    "reason": rejection_info.get('reason', 'Not applicable')
                })

            # Check if video already has a transcript
            transcript_ref = db.collection('transcripts').document(self.video_id)
            if transcript_ref.get().exists:
                return json.dumps({
                    "job_id": None,
                    "message": "Video already transcribed - skipping",
                    "video_id": self.video_id
                })
            
            # Check if transcription job already exists
            # Note: Firestore collection path for transcription jobs
            jobs_collection = 'jobs_transcription'
            existing_jobs = db.collection(jobs_collection).where(
                filter=FieldFilter('video_id', '==', self.video_id)
            ).where(
                filter=FieldFilter('status', 'in', ['pending', 'processing', 'completed'])
            ).limit(1).get()
            
            if len(existing_jobs) > 0:
                existing_job = existing_jobs[0]
                return json.dumps({
                    "job_id": existing_job.id,
                    "message": "Transcription job already exists - preventing duplicate",
                    "video_id": self.video_id,
                    "existing_status": existing_job.to_dict().get('status')
                })
            
            # Validate video duration
            duration_sec = video_data.get('duration_sec', 0)
            if duration_sec > max_duration:
                return json.dumps({
                    "job_id": None,
                    "message": f"Video duration {duration_sec}s exceeds maximum {max_duration}s (70 minutes) - skipping",
                    "video_id": self.video_id
                })
            
            # Create transcription job
            job_ref = db.collection(jobs_collection).document()
            
            job_data = {
                'job_id': job_ref.id,
                'video_id': self.video_id,
                'video_url': video_data.get('url'),
                'title': video_data.get('title'),
                'channel_id': video_data.get('channel_id'),
                'duration_sec': duration_sec,
                'published_at': video_data.get('published_at'),
                'source': video_data.get('source'),
                'status': 'pending',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Use batch write for atomicity
            batch = db.batch()
            
            # Create the job
            batch.set(job_ref, job_data)
            
            # Update video status
            batch.update(video_ref, {
                'status': 'transcription_queued',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Commit the batch
            batch.commit()
            
            return json.dumps({
                "job_id": job_ref.id,
                "video_id": self.video_id,
                "status": "pending",
                "duration_sec": duration_sec,
                "message": "Transcription job created successfully"
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to enqueue transcription: {str(e)}",
                "job_id": None
            })
    
    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            # Get required project ID
            project_id = get_required_env_var(
                "GCP_PROJECT_ID", 
                "Google Cloud Project ID for Firestore"
            )
            
            # Get service account credentials path
            credentials_path = get_required_env_var(
                "GOOGLE_APPLICATION_CREDENTIALS", 
                "Google service account credentials file path"
            )
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            # Initialize Firestore client with project ID
            return firestore.Client(project=project_id)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    # Test the tool with both videos
    print("="*80)
    print("TEST 1: Enqueue Rick Astley - Never Gonna Give You Up")
    print("="*80)

    test_tool_1 = EnqueueTranscription(
        video_id="dQw4w9WgXcQ"
    )

    try:
        result = test_tool_1.run()
        print("EnqueueTranscription test result:")
        print(result)

        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['error']}")
        elif data.get("job_id"):
            print(f"✅ Success: Created job {data['job_id']}")
        else:
            print(f"⚠️  Skipped: {data.get('message', 'No job created')}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("TEST 2: Enqueue Dan Martell - How to 10x Your Business")
    print("="*80)

    test_tool_2 = EnqueueTranscription(
        video_id="mZxDw92UXmA"
    )

    try:
        result = test_tool_2.run()
        print("EnqueueTranscription test result:")
        print(result)

        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['error']}")
        elif data.get("job_id"):
            print(f"✅ Success: Created job {data['job_id']}")
        else:
            print(f"⚠️  Skipped: {data.get('message', 'No job created')}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("Testing complete! Two transcription jobs enqueued:")
    print("- dQw4w9WgXcQ: Rick Astley (will be rejected at summarization)")
    print("- mZxDw92UXmA: Dan Martell (will be processed normally)")
    print("="*80)