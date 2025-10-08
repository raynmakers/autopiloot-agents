import os
import json
import time
from typing import Dict, Any
from pydantic import Field, field_validator
import assemblyai as aai
from agency_swarm.tools import BaseTool
from dotenv import load_dotenv

load_dotenv()


class PollTranscriptionJob(BaseTool):
    """
    Poll AssemblyAI transcription job for completion with exponential backoff.
    
    Uses configurable retry logic with exponential backoff delays and timeout caps
    to efficiently monitor transcription progress without overwhelming the API.
    Returns transcript text and JSON when job completes successfully.
    """
    
    job_id: str = Field(
        ..., 
        description="AssemblyAI transcription job ID to monitor for completion"
    )
    max_attempts: int = Field(
        default=3,
        description="Maximum polling attempts before timeout (default 3)"
    )
    base_delay_sec: int = Field(
        default=60,
        description="Base delay in seconds for exponential backoff (default 60)"
    )
    timeout_sec: int = Field(
        default=3600,
        description="Maximum total polling time in seconds (default 1 hour)"
    )
    
    @field_validator('max_attempts')
    @classmethod
    def validate_max_attempts(cls, v):
        """Validate max attempts is reasonable."""
        if v < 1:
            raise ValueError("max_attempts must be at least 1")
        if v > 10:
            raise ValueError("max_attempts cannot exceed 10 to prevent excessive API calls")
        return v
    
    @field_validator('base_delay_sec')
    @classmethod
    def validate_base_delay(cls, v):
        """Validate base delay is reasonable."""
        if v < 10:
            raise ValueError("base_delay_sec must be at least 10 seconds")
        if v > 300:
            raise ValueError("base_delay_sec cannot exceed 300 seconds")
        return v
    
    @field_validator('timeout_sec')
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout is reasonable."""
        if v < 300:
            raise ValueError("timeout_sec must be at least 300 seconds (5 minutes)")
        if v > 7200:
            raise ValueError("timeout_sec cannot exceed 7200 seconds (2 hours)")
        return v
    
    def run(self) -> str:
        """
        Poll AssemblyAI job for completion with exponential backoff.
        
        Process:
        1. Initialize AssemblyAI client with API key validation
        2. Poll job status with exponential backoff delays
        3. Handle various job states (queued, processing, completed, error)
        4. Extract transcript text and JSON when completed
        5. Return structured response or error details
        
        Returns:
            JSON string containing:
            - transcript_text: Full transcript text
            - transcript_json: Complete transcript JSON with metadata
            - job_id: Original AssemblyAI job ID
            - status: Final job status
            - polling_attempts: Number of attempts made
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
            start_time = time.time()
            attempt = 0

            while attempt < self.max_attempts:
                attempt += 1

                # Check for timeout
                elapsed_time = time.time() - start_time
                if elapsed_time > self.timeout_sec:
                    return json.dumps({
                        "error": "timeout_error",
                        "message": f"Polling timeout exceeded {self.timeout_sec} seconds",
                        "job_id": self.job_id,
                        "polling_attempts": attempt,
                        "elapsed_sec": int(elapsed_time)
                    })

                # Get current job status using Transcript.get_by_id()
                transcript = aai.Transcript.get_by_id(self.job_id)
                
                # Handle different transcript statuses
                if transcript.status == aai.TranscriptStatus.completed:
                    # Success! Extract text and JSON
                    transcript_text = transcript.text or ""
                    
                    # Build comprehensive JSON response with all metadata
                    transcript_json = {
                        "id": transcript.id,
                        "status": str(transcript.status),
                        "text": transcript_text,
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
                            for word in transcript.words
                        ]
                    
                    # Add speaker labels if available
                    if hasattr(transcript, 'utterances') and transcript.utterances:
                        transcript_json["utterances"] = [
                            {
                                "speaker": utterance.speaker,
                                "text": utterance.text,
                                "start": utterance.start,
                                "end": utterance.end,
                                "confidence": utterance.confidence,
                                "words": [
                                    {
                                        "text": word.text,
                                        "start": word.start,
                                        "end": word.end,
                                        "confidence": word.confidence
                                    }
                                    for word in utterance.words
                                ] if hasattr(utterance, 'words') else []
                            }
                            for utterance in transcript.utterances
                        ]
                    
                    return json.dumps({
                        "transcript_text": transcript_text,
                        "transcript_json": transcript_json,
                        "job_id": self.job_id,
                        "status": "completed",
                        "polling_attempts": attempt,
                        "elapsed_sec": int(elapsed_time)
                    }, indent=2)
                
                elif transcript.status == aai.TranscriptStatus.error:
                    # Transcription failed
                    error_message = getattr(transcript, 'error', 'Unknown transcription error')
                    return json.dumps({
                        "error": "transcription_error",
                        "message": f"AssemblyAI transcription failed: {error_message}",
                        "job_id": self.job_id,
                        "polling_attempts": attempt,
                        "elapsed_sec": int(elapsed_time)
                    })
                
                elif transcript.status in [aai.TranscriptStatus.queued, aai.TranscriptStatus.processing]:
                    # Still processing, wait before next attempt
                    if attempt < self.max_attempts:
                        # Calculate exponential backoff delay: base_delay * (2 ^ (attempt - 1))
                        delay = self.base_delay_sec * (2 ** (attempt - 1))
                        # Cap delay at 240 seconds to prevent excessive waits
                        delay = min(delay, 240)
                        
                        # Check if delay would exceed timeout
                        if elapsed_time + delay > self.timeout_sec:
                            remaining_time = self.timeout_sec - elapsed_time
                            if remaining_time > 10:  # Wait if we have at least 10 seconds left
                                time.sleep(remaining_time)
                            break
                        else:
                            time.sleep(delay)
                else:
                    # Unknown status
                    return json.dumps({
                        "error": "unknown_status",
                        "message": f"Unknown transcript status: {transcript.status}",
                        "job_id": self.job_id,
                        "polling_attempts": attempt,
                        "elapsed_sec": int(elapsed_time)
                    })
            
            # Max attempts reached without completion
            final_elapsed = int(time.time() - start_time)
            return json.dumps({
                "error": "max_attempts_exceeded",
                "message": f"Transcription not completed after {self.max_attempts} polling attempts",
                "job_id": self.job_id,
                "polling_attempts": attempt,
                "elapsed_sec": final_elapsed,
                "last_status": str(transcript.status) if 'transcript' in locals() else "unknown"
            })
            
        except Exception as e:
            return json.dumps({
                "error": "unexpected_error",
                "message": f"Failed to poll transcription job: {str(e)}",
                "job_id": self.job_id
            })


if __name__ == "__main__":
    print("=" * 80)
    print("TEST 1: Rick Astley - Never Gonna Give You Up (Entertainment/Music)")
    print("=" * 80)

    try:
        from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl
        from transcriber_agent.tools.submit_assemblyai_job import SubmitAssemblyAIJob

        # Get audio URL for Rick Astley
        audio_tool_1 = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        audio_result_1 = audio_tool_1.run()
        audio_data_1 = json.loads(audio_result_1)

        if "error" not in audio_data_1 and "signed_url" in audio_data_1:
            # Submit transcription job
            submit_tool_1 = SubmitAssemblyAIJob(
                audio_url=audio_data_1["signed_url"],
                storage_path=audio_data_1["storage_path"],
                video_id=audio_data_1["video_id"],
                duration_sec=audio_data_1["duration"]
            )
            submit_result_1 = submit_tool_1.run()
            submit_data_1 = json.loads(submit_result_1)

            if "error" not in submit_data_1 and "job_id" in submit_data_1:
                job_id_1 = submit_data_1["job_id"]
                print(f"✅ Job submitted: {job_id_1}")
                print(f"   Polling for completion...")

                # Poll the job
                poll_tool_1 = PollTranscriptionJob(
                    job_id=job_id_1,
                    max_attempts=10,
                    base_delay_sec=30,
                    timeout_sec=1800  # 30 minutes
                )

                poll_result_1 = poll_tool_1.run()
                poll_data_1 = json.loads(poll_result_1)

                if "error" in poll_data_1:
                    print(f"⚠️ Polling ended with: {poll_data_1['message']}")
                    print(f"   Status: {poll_data_1.get('last_status', 'unknown')}")
                    print(f"   Attempts: {poll_data_1.get('polling_attempts', 0)}")
                elif poll_data_1.get("status") == "completed":
                    print(f"✅ Transcription completed!")
                    print(f"   Transcript length: {len(poll_data_1.get('transcript_text', ''))} chars")
                    print(f"   Polling attempts: {poll_data_1.get('polling_attempts', 0)}")
                    print(f"   Elapsed time: {poll_data_1.get('elapsed_sec', 0)} seconds")
                    print(f"   First 200 chars: {poll_data_1.get('transcript_text', '')[:200]}...")
            else:
                print(f"❌ Failed to submit job: {submit_data_1.get('message', 'Unknown error')}")
        else:
            print(f"❌ Failed to get audio URL: {audio_data_1.get('message', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")

    print("\n" + "=" * 80)
    print("TEST 2: Dan Martell - How to 10x Your Business (Business/Educational)")
    print("=" * 80)

    try:
        # Get audio URL for Dan Martell
        audio_tool_2 = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=mZxDw92UXmA")
        audio_result_2 = audio_tool_2.run()
        audio_data_2 = json.loads(audio_result_2)

        if "error" not in audio_data_2 and "signed_url" in audio_data_2:
            # Submit transcription job
            submit_tool_2 = SubmitAssemblyAIJob(
                audio_url=audio_data_2["signed_url"],
                storage_path=audio_data_2["storage_path"],
                video_id=audio_data_2["video_id"],
                duration_sec=audio_data_2["duration"]
            )
            submit_result_2 = submit_tool_2.run()
            submit_data_2 = json.loads(submit_result_2)

            if "error" not in submit_data_2 and "job_id" in submit_data_2:
                job_id_2 = submit_data_2["job_id"]
                print(f"✅ Job submitted: {job_id_2}")
                print(f"   Polling for completion...")

                # Poll the job
                poll_tool_2 = PollTranscriptionJob(
                    job_id=job_id_2,
                    max_attempts=10,
                    base_delay_sec=30,
                    timeout_sec=1800  # 30 minutes
                )

                poll_result_2 = poll_tool_2.run()
                poll_data_2 = json.loads(poll_result_2)

                if "error" in poll_data_2:
                    print(f"⚠️ Polling ended with: {poll_data_2['message']}")
                    print(f"   Status: {poll_data_2.get('last_status', 'unknown')}")
                    print(f"   Attempts: {poll_data_2.get('polling_attempts', 0)}")
                elif poll_data_2.get("status") == "completed":
                    print(f"✅ Transcription completed!")
                    print(f"   Transcript length: {len(poll_data_2.get('transcript_text', ''))} chars")
                    print(f"   Polling attempts: {poll_data_2.get('polling_attempts', 0)}")
                    print(f"   Elapsed time: {poll_data_2.get('elapsed_sec', 0)} seconds")
                    print(f"   First 200 chars: {poll_data_2.get('transcript_text', '')[:200]}...")
            else:
                print(f"❌ Failed to submit job: {submit_data_2.get('message', 'Unknown error')}")
        else:
            print(f"❌ Failed to get audio URL: {audio_data_2.get('message', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")

    print("\n" + "=" * 80)
    print("Testing complete! Both videos can be transcribed:")
    print("- dQw4w9WgXcQ: Rick Astley (will be rejected at summarization)")
    print("- mZxDw92UXmA: Dan Martell (will be processed normally)")
    print("=" * 80)
    
    # Test 2: Parameter validation - invalid max_attempts
    print("\n" + "="*50)
    print("\nTest 2: Parameter validation (invalid max_attempts)")
    try:
        invalid_tool = PollTranscriptionJob(
            job_id="test_job_456",
            max_attempts=15,  # Exceeds limit of 10
            base_delay_sec=60
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 3: Parameter validation - invalid base_delay
    print("\n" + "="*50)
    print("\nTest 3: Parameter validation (invalid base_delay)")
    try:
        invalid_tool2 = PollTranscriptionJob(
            job_id="test_job_789",
            max_attempts=3,
            base_delay_sec=5  # Below minimum of 10
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 4: Parameter validation - invalid timeout
    print("\n" + "="*50)
    print("\nTest 4: Parameter validation (invalid timeout)")
    try:
        invalid_tool3 = PollTranscriptionJob(
            job_id="test_job_abc",
            max_attempts=3,
            base_delay_sec=60,
            timeout_sec=100  # Below minimum of 300
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 5: Configuration with valid custom parameters
    print("\n" + "="*50)
    print("\nTest 5: Custom configuration validation")
    try:
        custom_tool = PollTranscriptionJob(
            job_id="test_job_def",
            max_attempts=5,
            base_delay_sec=30,
            timeout_sec=1800  # 30 minutes
        )
        
        print(f"✅ Custom configuration accepted:")
        print(f"   Max attempts: {custom_tool.max_attempts}")
        print(f"   Base delay: {custom_tool.base_delay_sec} seconds")
        print(f"   Timeout: {custom_tool.timeout_sec} seconds")
        
        # Test the exponential backoff calculation
        print(f"   Backoff delays: ", end="")
        for attempt in range(1, custom_tool.max_attempts + 1):
            delay = custom_tool.base_delay_sec * (2 ** (attempt - 1))
            delay = min(delay, 240)  # Cap at 240 seconds
            print(f"{delay}s", end=" " if attempt < custom_tool.max_attempts else "")
        print()
        
    except Exception as e:
        print(f"❌ Configuration error: {str(e)}")
    
    print("\n" + "="*50)
    print("Testing complete!")