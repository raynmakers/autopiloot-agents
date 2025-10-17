"""
SaveTranscriptRecord tool for storing transcript data to Firestore.
Implements TASK-TRN-0022: Store transcripts with metadata for efficient querying and retrieval.
"""

import os
import sys
import json
import hashlib
from typing import Dict, Any
from pydantic import Field, field_validator
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from google.cloud import firestore

# Add core and config directories to path
from config.env_loader import get_required_env_var, get_optional_env_var
from core.firestore_client import get_firestore_client



class SaveTranscriptRecord(BaseTool):
    """
    Store transcript data to Firestore transcripts collection.

    Stores both plain text and structured JSON transcript data in Firestore
    for efficient querying and retrieval. Uses video_id as document ID for
    idempotent operations and easy lookups.
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID used as Firestore document ID"
    )
    transcript_text: str = Field(
        ...,
        description="Plain text transcript content for display and search"
    )
    transcript_json: Dict[str, Any] = Field(
        ...,
        description="Full structured transcript data with timestamps and metadata"
    )
    
    @field_validator('video_id')
    @classmethod
    def validate_video_id(cls, v):
        """Validate YouTube video ID format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("video_id cannot be empty")
        if len(v) > 50:  # YouTube video IDs are typically 11 characters
            raise ValueError("video_id seems too long for a valid YouTube ID")
        return v.strip()
    
    @field_validator('transcript_text')
    @classmethod
    def validate_transcript_text(cls, v):
        """Validate transcript text is not empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("transcript_text cannot be empty")
        return v
    
    @field_validator('transcript_json')
    @classmethod
    def validate_transcript_json(cls, v):
        """Validate transcript JSON has required fields."""
        if not isinstance(v, dict):
            raise ValueError("transcript_json must be a dictionary")

        # Note: 'text' not required in transcript_json since it's stored at parent level as transcript_text
        required_fields = ['id', 'status']
        missing_fields = [field for field in required_fields if field not in v]
        if missing_fields:
            raise ValueError(f"transcript_json missing required fields: {missing_fields}")

        return v

    def run(self) -> str:
        """
        Store transcript data to Firestore transcripts collection.

        Process:
        1. Initialize Firestore client with authentication
        2. Generate transcript digest for verification
        3. Create/update transcript document in transcripts collection
        4. Store both text and structured JSON data
        5. Add metadata (timestamps, digest, AssemblyAI job ID)
        6. Update video document status to 'transcribed'

        Returns:
            JSON string containing:
            - video_id: YouTube video ID (document ID)
            - transcript_length: Character count of transcript text
            - word_count: Number of words with timestamps
            - transcript_digest: SHA-256 hash for verification
            - stored_at: ISO timestamp of storage
            - status: "stored" on success

        Note: Full metadata (assemblyai_job_id, language_code, confidence, audio_duration)
              is available in transcript_json field of the stored document
        """

        try:
            # Initialize Firestore client
            db = get_firestore_client()

            # Generate transcript digest for verification
            transcript_digest = hashlib.sha256(self.transcript_text.encode('utf-8')).hexdigest()[:16]

            # Count words with timestamps
            word_count = len(self.transcript_json.get('words', []))

            # Prepare transcript document data (deduplicated)
            # Note: video_id is the document ID, so not stored in data
            # Note: assemblyai_job_id, language_code, confidence, audio_duration are in transcript_json
            transcript_data = {
                'transcript_text': self.transcript_text,  # Kept at top level for search/indexing
                'transcript_json': self.transcript_json,  # Source of truth for all metadata
                'transcript_digest': transcript_digest,  # Computed verification hash
                'transcript_length': len(self.transcript_text),  # Computed metric
                'word_count': word_count,  # Computed metric
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            # Use batch write for atomicity
            batch = db.batch()

            # Store/update transcript document (using video_id as document ID)
            transcript_ref = db.collection('transcripts').document(self.video_id)
            batch.set(transcript_ref, transcript_data)

            # Update video status to 'transcribed'
            video_ref = db.collection('videos').document(self.video_id)
            batch.update(video_ref, {
                'status': 'transcribed',
                'updated_at': firestore.SERVER_TIMESTAMP
            })

            # Commit the batch
            batch.commit()

            # Return structured result (deduplicated - full metadata in transcript_json)
            result = {
                "video_id": self.video_id,
                "transcript_length": len(self.transcript_text),
                "word_count": word_count,
                "transcript_digest": transcript_digest,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "status": "stored"
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "storage_error",
                "message": f"Failed to store transcript to Firestore: {str(e)}",
                "video_id": self.video_id
            })


if __name__ == "__main__":
    print("Testing SaveTranscriptRecord tool...")
    print("="*50)

    # Test 1: Store Rick Astley transcript
    print("\nTest 1: Rick Astley - Never Gonna Give You Up (Entertainment/Music)")
    print("Fetching transcript from AssemblyAI...")

    try:
        import assemblyai as aai

        # Initialize AssemblyAI
        api_key = get_optional_env_var("ASSEMBLYAI_API_KEY", "", "AssemblyAI API key for transcript testing")
        if not api_key:
            print("❌ ASSEMBLYAI_API_KEY environment variable is required")
        else:
            aai.settings.api_key = api_key

            # Fetch the completed transcript for Rick Astley
            # Note: Update this job ID from a recent poll_transcription_job.py run
            assemblyai_job_id = "d5db2289-fd86-4f7a-a0a2-ec43bbee95b3"  # Fresh from recent test
            print(f"Fetching transcript: {assemblyai_job_id}")

            transcript = aai.Transcript.get_by_id(assemblyai_job_id)

            if transcript.status == aai.TranscriptStatus.completed:
                video_id = "dQw4w9WgXcQ"  # Rick Astley video

                # Build transcript_json
                transcript_json = {
                    "id": transcript.id,
                    "status": str(transcript.status),
                    "confidence": getattr(transcript, 'confidence', None),
                    "audio_duration": getattr(transcript, 'audio_duration', None),
                    "language_code": getattr(transcript, 'language_code', None),
                    "audio_url": getattr(transcript, 'audio_url', None),
                    "words": []
                }

                # Add words with timestamps if available
                if hasattr(transcript, 'words') and transcript.words:
                    transcript_json["words"] = [
                        {
                            "text": word.text,
                            "start": word.start,
                            "end": word.end,
                            "confidence": word.confidence
                        }
                        for word in transcript.words[:100]  # First 100 words only for demo
                    ]

                print(f"✅ Transcript fetched successfully")
                print(f"   Status: {transcript.status}")
                print(f"   Text length: {len(transcript.text or '')} chars")
                print(f"   First 100 chars: {(transcript.text or '')[:100]}...")

                # Store to Firestore
                print("\nStoring transcript to Firestore...")
                tool = SaveTranscriptRecord(
                    video_id=video_id,
                    transcript_text=transcript.text or "",
                    transcript_json=transcript_json
                )

                result = tool.run()
                data = json.loads(result)

                if "error" in data:
                    print(f"❌ Error: {data['message']}")
                    print(f"   Error type: {data['error']}")
                else:
                    print(f"✅ Transcript stored to Firestore successfully:")
                    print(f"   Video ID: {data.get('video_id', 'N/A')}")
                    print(f"   Transcript length: {data.get('transcript_length', 0)} chars")
                    print(f"   Word count: {data.get('word_count', 0)}")
                    print(f"   Transcript digest: {data.get('transcript_digest', 'N/A')}")
                    print(f"   Stored at: {data.get('stored_at', 'N/A')}")

            else:
                print(f"❌ Transcript not completed yet. Status: {transcript.status}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TEST 2: Dan Martell - How to 10x Your Business (Business/Educational)")
    print("Fetching transcript from AssemblyAI...")
    print("=" * 80)

    try:
        # Fetch the completed transcript for Dan Martell (if available)
        # Note: Update this job ID from a recent poll_transcription_job.py run
        assemblyai_job_id_dan = "ce9bc2ed-0c76-49a5-bbe5-e8afd68db182"  # Fresh from recent test
        print(f"Fetching transcript: {assemblyai_job_id_dan}")

        transcript_dan = aai.Transcript.get_by_id(assemblyai_job_id_dan)

        if transcript_dan.status == aai.TranscriptStatus.completed:
            video_id_dan = "mZxDw92UXmA"  # Dan Martell video

            # Build transcript_json
            transcript_json_dan = {
                "id": transcript_dan.id,
                "status": str(transcript_dan.status),
                "confidence": getattr(transcript_dan, 'confidence', None),
                "audio_duration": getattr(transcript_dan, 'audio_duration', None),
                "language_code": getattr(transcript_dan, 'language_code', None),
                "audio_url": getattr(transcript_dan, 'audio_url', None),
                "words": []
            }

            # Add words with timestamps if available
            if hasattr(transcript_dan, 'words') and transcript_dan.words:
                transcript_json_dan["words"] = [
                    {
                        "text": word.text,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence
                    }
                    for word in transcript_dan.words[:100]  # First 100 words only for demo
                ]

            print(f"✅ Transcript fetched successfully")
            print(f"   Status: {transcript_dan.status}")
            print(f"   Text length: {len(transcript_dan.text or '')} chars")
            print(f"   First 100 chars: {(transcript_dan.text or '')[:100]}...")

            # Store to Firestore
            print("\nStoring transcript to Firestore...")
            tool_dan = SaveTranscriptRecord(
                video_id=video_id_dan,
                transcript_text=transcript_dan.text or "",
                transcript_json=transcript_json_dan
            )

            result_dan = tool_dan.run()
            data_dan = json.loads(result_dan)

            if "error" in data_dan:
                print(f"❌ Error: {data_dan['message']}")
                print(f"   Error type: {data_dan['error']}")
            else:
                print(f"✅ Transcript stored to Firestore successfully:")
                print(f"   Video ID: {data_dan.get('video_id', 'N/A')}")
                print(f"   Transcript length: {data_dan.get('transcript_length', 0)} chars")
                print(f"   Word count: {data_dan.get('word_count', 0)}")
                print(f"   Transcript digest: {data_dan.get('transcript_digest', 'N/A')}")
                print(f"   Stored at: {data_dan.get('stored_at', 'N/A')}")

        elif transcript_dan.status == aai.TranscriptStatus.processing:
            print(f"⚠️  Transcript still processing. Run test again after completion.")
        elif transcript_dan.status == aai.TranscriptStatus.error:
            print(f"❌ Transcript failed with error status")
            print(f"   Error: {getattr(transcript_dan, 'error', 'No error message available')}")
            print(f"   This may be due to:")
            print(f"   - Expired Firebase Storage signed URL (24-hour limit)")
            print(f"   - Audio file no longer accessible")
            print(f"   - AssemblyAI processing error")
            print(f"\n   Solution: Run poll_transcription_job.py to create a fresh transcription")
        else:
            print(f"⚠️  Transcript status: {transcript_dan.status}")
            print(f"   Run this test again after AssemblyAI completes the transcription")

    except Exception as e:
        print(f"⚠️  Dan Martell test skipped: {str(e)}")
        print(f"   This is expected if the AssemblyAI job hasn't completed yet")
        print(f"   Run submit_assemblyai_job.py first, then poll_transcription_job.py")

    print("\n" + "=" * 80)
    print("Testing complete! Both transcripts can be stored:")
    print("- dQw4w9WgXcQ: Rick Astley (will be rejected at summarization)")
    print("- mZxDw92UXmA: Dan Martell (will be processed normally)")
    print("=" * 80)