"""
SubmitAssemblyAIJob tool for submitting transcription jobs to AssemblyAI.
Implements TASK-TRN-0021: Submit transcription with 70-min cap and cost estimation.
Updates Firestore job record for restart recovery and monitoring.
"""

import os
import sys
import json
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
import assemblyai as aai
from agency_swarm.tools import BaseTool
from dotenv import load_dotenv
from google.cloud import firestore

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from config.env_loader import get_required_env_var

load_dotenv()

# AssemblyAI pricing per hour (as of 2024)
ASSEMBLYAI_COST_PER_HOUR = 0.65  # USD


class SubmitAssemblyAIJob(BaseTool):
    """
    Submit a transcription job to AssemblyAI with quality controls and webhook support.

    Enforces 70-minute duration limit, provides cost estimation, and supports optional
    webhook callbacks for job completion notifications. Uses minimal features by default
    to optimize costs while maintaining high transcription quality.

    Updates Firestore job record with AssemblyAI job ID for restart recovery and monitoring.
    """

    job_id: Optional[str] = Field(
        default=None,
        description="Firestore job ID from jobs_transcription collection (for job tracking and restart recovery)"
    )
    remote_url: str = Field(
        ...,
        description="Direct audio stream URL from YouTube video for transcription"
    )
    video_id: str = Field(
        ...,
        description="YouTube video ID for tracking and metadata"
    )
    duration_sec: int = Field(
        ...,
        description="Video duration in seconds (must be ≤4200 for 70-minute limit)"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Optional webhook URL for job completion notifications from AssemblyAI"
    )
    enable_speaker_labels: bool = Field(
        default=False,
        description="Enable speaker diarization (increases cost)"
    )
    language_code: Optional[str] = Field(
        default=None,
        description="Optional language code (e.g., 'en', 'es', 'fr') for better accuracy"
    )
    
    @field_validator('duration_sec')
    @classmethod
    def validate_duration(cls, v):
        """Validate video duration is within 70-minute limit."""
        if v > 4200:
            raise ValueError(f"Video duration {v}s exceeds maximum 4200s (70 minutes)")
        if v <= 0:
            raise ValueError(f"Invalid duration: {v}s. Duration must be positive.")
        return v
    
    @field_validator('webhook_url')
    @classmethod
    def validate_webhook_url(cls, v):
        """Validate webhook URL format if provided."""
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError(f"Invalid webhook URL: {v}. Must start with http:// or https://")
        return v

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

    def run(self) -> str:
        """
        Submit transcription job to AssemblyAI with duration validation and cost estimation.
        
        Process:
        1. Validates duration is within 70-minute limit (handled by validator)
        2. Configures AssemblyAI with minimal features for cost efficiency
        3. Submits job with optional webhook support
        4. Calculates and returns estimated cost
        
        Returns:
            JSON string containing:
            - job_id: AssemblyAI job identifier
            - estimated_cost_usd: Estimated transcription cost
            - video_id: YouTube video ID for tracking
            - duration_sec: Video duration
            - webhook_enabled: Whether webhook callback is configured
        """
        # Initialize AssemblyAI with API key
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not api_key:
            return json.dumps({
                "error": "configuration_error",
                "message": "ASSEMBLYAI_API_KEY environment variable is required"
            })
        
        aai.settings.api_key = api_key
        
        try:
            # Build transcription configuration
            config_params = {
                "speaker_labels": self.enable_speaker_labels,
                "auto_highlights": False,
                "iab_categories": False,
                "content_safety": False,
                "summarization": False,
                "sentiment_analysis": False,
                "entity_detection": False,
                "format_text": True,  # Enable punctuation and capitalization
                "punctuate": True,
                "language_code": self.language_code
            }
            
            # Add webhook configuration if provided
            if self.webhook_url:
                webhook_secret = os.getenv("ASSEMBLYAI_WEBHOOK_SECRET")
                config_params.update({
                    "webhook_url": self.webhook_url,
                    "webhook_auth_header_name": "X-AssemblyAI-Webhook-Secret" if webhook_secret else None,
                    "webhook_auth_header_value": webhook_secret if webhook_secret else None
                })
            
            # Create transcription configuration
            config = aai.TranscriptionConfig(**config_params)
            
            # Submit transcription job
            transcriber = aai.Transcriber()
            transcript = transcriber.submit(self.remote_url, config=config)
            
            # Calculate estimated cost
            base_cost = (self.duration_sec / 3600) * ASSEMBLYAI_COST_PER_HOUR
            
            # Add cost for additional features
            if self.enable_speaker_labels:
                base_cost *= 1.15  # 15% additional for speaker diarization
            
            estimated_cost_usd = round(base_cost, 4)

            # Update Firestore job record if job_id provided
            if self.job_id:
                try:
                    db = self._initialize_firestore()
                    job_ref = db.collection('jobs_transcription').document(self.job_id)

                    # Update job with AssemblyAI details
                    job_ref.update({
                        'assemblyai_job_id': transcript.id,
                        'status': 'processing',
                        'estimated_cost_usd': estimated_cost_usd,
                        'remote_url': self.remote_url,
                        'features': {
                            'speaker_labels': self.enable_speaker_labels,
                            'language_code': self.language_code or 'auto'
                        },
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })
                except Exception as firestore_error:
                    # Log Firestore error but don't fail the submission
                    print(f"Warning: Failed to update Firestore job record: {str(firestore_error)}")

            # Prepare response
            result = {
                "job_id": transcript.id,
                "estimated_cost_usd": estimated_cost_usd,
                "video_id": self.video_id,
                "duration_sec": self.duration_sec,
                "webhook_enabled": bool(self.webhook_url),
                "status": "submitted",
                "features": {
                    "speaker_labels": self.enable_speaker_labels,
                    "language_code": self.language_code or "auto"
                }
            }

            # Add Firestore job ID to response if provided
            if self.job_id:
                result["firestore_job_id"] = self.job_id

            # Add webhook URL to response if configured
            if self.webhook_url:
                result["webhook_url"] = self.webhook_url

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "unexpected_error",
                "message": f"Failed to submit AssemblyAI job: {str(e)}",
                "video_id": self.video_id
            })


if __name__ == "__main__":
    print("=" * 80)
    print("TEST 1: Rick Astley - Never Gonna Give You Up (Entertainment/Music)")
    print("=" * 80)

    # Get audio URL for Rick Astley
    from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

    audio_tool_1 = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    audio_result_1 = audio_tool_1.run()
    audio_data_1 = json.loads(audio_result_1)

    if "error" in audio_data_1 or "remote_url" not in audio_data_1:
        print(f"❌ Failed to get audio URL: {audio_data_1.get('error', 'Unknown error')}")
    else:
        remote_url_1 = audio_data_1["remote_url"]
        video_id_1 = audio_data_1["video_id"]
        duration_sec_1 = audio_data_1["duration"]
        print(f"✅ Got remote URL for video: {audio_data_1['title']}")
        print(f"   Duration: {duration_sec_1} seconds")

        print("\nSubmitting to AssemblyAI...")
        tool_1 = SubmitAssemblyAIJob(
            remote_url=remote_url_1,
            video_id=video_id_1,
            duration_sec=duration_sec_1
        )

        try:
            result = tool_1.run()
            data = json.loads(result)
            if "error" in data:
                print(f"❌ Error: {data['message']}")
            else:
                print(f"✅ Job submitted successfully")
                print(f"   Job ID: {data.get('job_id', 'N/A')}")
                print(f"   Estimated cost: ${data.get('estimated_cost_usd', 0):.4f}")
                print(f"   Duration: {data.get('duration_sec', 0)} seconds")
        except Exception as e:
            print(f"❌ Test error: {str(e)}")

    print("\n" + "=" * 80)
    print("TEST 2: Dan Martell - How to 10x Your Business (Business/Educational)")
    print("=" * 80)

    # Get audio URL for Dan Martell
    audio_tool_2 = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=mZxDw92UXmA")
    audio_result_2 = audio_tool_2.run()
    audio_data_2 = json.loads(audio_result_2)

    if "error" in audio_data_2 or "remote_url" not in audio_data_2:
        print(f"❌ Failed to get audio URL: {audio_data_2.get('error', 'Unknown error')}")
    else:
        remote_url_2 = audio_data_2["remote_url"]
        video_id_2 = audio_data_2["video_id"]
        duration_sec_2 = audio_data_2["duration"]
        print(f"✅ Got remote URL for video: {audio_data_2['title']}")
        print(f"   Duration: {duration_sec_2} seconds")

        print("\nSubmitting to AssemblyAI...")
        tool_2 = SubmitAssemblyAIJob(
            remote_url=remote_url_2,
            video_id=video_id_2,
            duration_sec=duration_sec_2
        )

        try:
            result = tool_2.run()
            data = json.loads(result)
            if "error" in data:
                print(f"❌ Error: {data['message']}")
            else:
                print(f"✅ Job submitted successfully")
                print(f"   Job ID: {data.get('job_id', 'N/A')}")
                print(f"   Estimated cost: ${data.get('estimated_cost_usd', 0):.4f}")
                print(f"   Duration: {data.get('duration_sec', 0)} seconds")
        except Exception as e:
            print(f"❌ Test error: {str(e)}")
    
    # Test 3: Duration limit validation (should fail)
    print("\n" + "="*50)
    print("\nTest 3: Duration limit validation (90 minutes - should fail)")
    try:
        tool_long = SubmitAssemblyAIJob(
            remote_url="https://example.com/audio.mp3",
            video_id="test_video_789",
            duration_sec=5400  # 90 minutes - exceeds 70-minute limit
        )
        result = tool_long.run()
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

    # Test 4: Submission with Firestore job tracking (demonstrates restart recovery)
    print("\n" + "="*50)
    print("\nTest 4: Job submission with Firestore tracking (for restart recovery)")
    try:
        # First, create a Firestore job using EnqueueTranscription
        print("Creating Firestore job record...")
        from scraper_agent.tools.enqueue_transcription import EnqueueTranscription

        # Note: This requires a video to exist in Firestore videos collection
        # For testing, we'll just demonstrate the API with job_id parameter
        print("⚠️  Skipping Firestore job creation (requires existing video in Firestore)")
        print("   In production workflow:")
        print("   1. EnqueueTranscription creates job in jobs_transcription collection")
        print("   2. SubmitAssemblyAIJob receives job_id and updates it with assemblyai_job_id")
        print("   3. PollTranscriptionJob can resume using assemblyai_job_id after restart")

        # Demonstrate the API with a mock job_id
        tool_with_firestore = SubmitAssemblyAIJob(
            job_id="mock_firestore_job_123",  # Would be real Firestore document ID
            remote_url=remote_url,
            video_id=video_id,
            duration_sec=duration_sec
        )

        print("\n✅ Tool accepts job_id parameter for Firestore tracking")
        print(f"   job_id parameter: mock_firestore_job_123")
        print(f"   After submission, Firestore job document will be updated with:")
        print(f"   - assemblyai_job_id: [AssemblyAI transcript ID]")
        print(f"   - status: 'processing'")
        print(f"   - estimated_cost_usd: [cost estimate]")
        print(f"   - updated_at: [server timestamp]")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")

    print("\n" + "="*50)
    print("Testing complete!")
    print("\n📝 Workflow Summary:")
    print("1. ScraperAgent → EnqueueTranscription (creates Firestore job)")
    print("2. TranscriberAgent → GetVideoAudioUrl (gets remote audio URL)")
    print("3. TranscriberAgent → SubmitAssemblyAIJob (submits to AssemblyAI + updates Firestore)")
    print("4. TranscriberAgent → PollTranscriptionJob (monitors completion)")
    print("5. If system restarts: Query Firestore jobs with assemblyai_job_id to resume")