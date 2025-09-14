import os
import json
import time
from typing import Dict, Any
import assemblyai as aai
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class PollTranscriptionJob(BaseTool):
    def __init__(self):
        super().__init__()
        aai.settings.api_key = self.api_key
    
    def _validate_env_vars(self):
        self.api_key = self.get_env_var("ASSEMBLYAI_API_KEY")
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        job_id = request.get('job_id', '')
        
        if not job_id:
            raise ValueError("job_id is required")
        
        try:
            transcriber = aai.Transcriber()
            transcript = aai.Transcript.get_by_id(job_id)
            
            max_attempts = 60
            poll_interval = 5
            attempt = 0
            
            while attempt < max_attempts:
                if transcript.status == aai.TranscriptStatus.completed:
                    transcript_json = {
                        "id": transcript.id,
                        "text": transcript.text,
                        "words": [
                            {
                                "text": word.text,
                                "start": word.start,
                                "end": word.end,
                                "confidence": word.confidence
                            } for word in (transcript.words or [])
                        ] if transcript.words else [],
                        "confidence": transcript.confidence,
                        "duration": transcript.audio_duration,
                        "status": "completed"
                    }
                    
                    return {
                        "transcript_text": transcript.text,
                        "transcript_json": transcript_json
                    }
                
                elif transcript.status == aai.TranscriptStatus.error:
                    raise RuntimeError(f"Transcription failed: {transcript.error}")
                
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(min(poll_interval * (2 ** min(attempt // 10, 3)), 30))
                    transcript = aai.Transcript.get_by_id(job_id)
            
            raise RuntimeError(f"Transcription timed out after {max_attempts * poll_interval} seconds")
            
        except Exception as e:
            raise RuntimeError(f"Failed to poll transcription job: {str(e)}")


if __name__ == "__main__":
    tool = PollTranscriptionJob()
    
    test_request = {
        "job_id": "test_job_id"
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: Transcript received")
        print(f"Text length: {len(result.get('transcript_text', ''))}")
    except Exception as e:
        print(f"Error: {str(e)}")