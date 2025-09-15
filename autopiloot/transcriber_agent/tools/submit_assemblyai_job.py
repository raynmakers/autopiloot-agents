"""
SubmitAssemblyAIJob tool for submitting transcription jobs to AssemblyAI.
Implements TASK-TRN-0021: Submit transcription with 70-min cap and cost estimation.
"""

import os
import json
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
import assemblyai as aai
from agency_swarm.tools import BaseTool
from dotenv import load_dotenv

load_dotenv()

# AssemblyAI pricing per hour (as of 2024)
ASSEMBLYAI_COST_PER_HOUR = 0.65  # USD


class SubmitAssemblyAIJob(BaseTool):
    """
    Submit a transcription job to AssemblyAI with quality controls and webhook support.
    
    Enforces 70-minute duration limit, provides cost estimation, and supports optional
    webhook callbacks for job completion notifications. Uses minimal features by default
    to optimize costs while maintaining high transcription quality.
    """
    
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
            
            # Add webhook URL to response if configured
            if self.webhook_url:
                result["webhook_url"] = self.webhook_url
            
            return json.dumps(result, indent=2)
            
        except aai.exceptions.AuthenticationError as e:
            return json.dumps({
                "error": "authentication_error",
                "message": "Invalid AssemblyAI API key",
                "details": str(e)
            })
        except aai.exceptions.TranscriptError as e:
            return json.dumps({
                "error": "transcript_error",
                "message": "Failed to submit transcription job",
                "details": str(e)
            })
        except Exception as e:
            return json.dumps({
                "error": "unexpected_error",
                "message": f"Failed to submit AssemblyAI job: {str(e)}",
                "video_id": self.video_id
            })


if __name__ == "__main__":
    print("Testing SubmitAssemblyAIJob tool...")
    print("="*50)
    
    # Test 1: Basic submission without webhook
    print("\nTest 1: Basic job submission (10 minutes)")
    tool = SubmitAssemblyAIJob(
        remote_url="https://example.com/audio.mp3",
        video_id="test_video_123",
        duration_sec=600  # 10 minutes
    )
    
    try:
        result = tool.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"✅ Job submitted successfully")
            print(f"   Job ID: {data.get('job_id', 'N/A')}")
            print(f"   Estimated cost: ${data.get('estimated_cost_usd', 0):.4f}")
            print(f"   Duration: {data.get('duration_sec', 0)} seconds")
            print(f"   Webhook enabled: {data.get('webhook_enabled', False)}")
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    # Test 2: Submission with webhook
    print("\n" + "="*50)
    print("\nTest 2: Job submission with webhook (30 minutes)")
    tool_webhook = SubmitAssemblyAIJob(
        remote_url="https://example.com/audio.mp3",
        video_id="test_video_456",
        duration_sec=1800,  # 30 minutes
        webhook_url="https://example.com/webhook/callback"
    )
    
    try:
        result = tool_webhook.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"✅ Job submitted with webhook")
            print(f"   Job ID: {data.get('job_id', 'N/A')}")
            print(f"   Estimated cost: ${data.get('estimated_cost_usd', 0):.4f}")
            print(f"   Webhook URL: {data.get('webhook_url', 'N/A')}")
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
    
    # Test 4: With speaker labels and language code
    print("\n" + "="*50)
    print("\nTest 4: Job with speaker labels and language code (45 minutes)")
    tool_features = SubmitAssemblyAIJob(
        remote_url="https://example.com/audio.mp3",
        video_id="test_video_abc",
        duration_sec=2700,  # 45 minutes
        enable_speaker_labels=True,
        language_code="en"
    )
    
    try:
        result = tool_features.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"✅ Job submitted with additional features")
            print(f"   Job ID: {data.get('job_id', 'N/A')}")
            print(f"   Estimated cost: ${data.get('estimated_cost_usd', 0):.4f} (includes speaker labels)")
            print(f"   Features: {data.get('features', {})}")
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    print("\n" + "="*50)
    print("Testing complete!")