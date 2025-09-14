import os
import json
from typing import Dict, Any
import assemblyai as aai
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class SubmitAssemblyAIJob(BaseTool):
    def __init__(self):
        super().__init__()
        aai.settings.api_key = self.api_key
    
    def _validate_env_vars(self):
        self.api_key = self.get_env_var("ASSEMBLYAI_API_KEY")
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        remote_url = request.get('remote_url', '')
        metadata = request.get('metadata', {})
        webhook_url = request.get('webhook_url', '')
        
        if not remote_url:
            raise ValueError("remote_url is required")
        
        video_id = metadata.get('video_id', '')
        duration_sec = metadata.get('duration_sec', 0)
        
        if duration_sec > 4200:
            raise ValueError(f"Video duration {duration_sec}s exceeds maximum 4200s (70 minutes)")
        
        try:
            config = aai.TranscriptionConfig(
                speaker_labels=False,
                auto_highlights=False,
                iab_categories=False,
                content_safety=False,
                summarization=False,
                sentiment_analysis=False,
                entity_detection=False,
                webhook_url=webhook_url if webhook_url else None,
                webhook_auth_header_name="X-AssemblyAI-Webhook-Secret" if webhook_url else None,
                webhook_auth_header_value=os.getenv("ASSEMBLYAI_WEBHOOK_SECRET") if webhook_url else None
            )
            
            transcriber = aai.Transcriber()
            
            transcript = transcriber.submit(remote_url, config=config)
            
            estimated_cost_usd = (duration_sec / 3600) * 0.65
            
            return {
                "job_id": transcript.id,
                "estimated_cost_usd": round(estimated_cost_usd, 4)
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to submit AssemblyAI job: {str(e)}")


if __name__ == "__main__":
    tool = SubmitAssemblyAIJob()
    
    test_request = {
        "remote_url": "https://example.com/audio.mp3",
        "metadata": {
            "video_id": "test_video_123",
            "duration_sec": 600
        },
        "webhook_url": ""
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")