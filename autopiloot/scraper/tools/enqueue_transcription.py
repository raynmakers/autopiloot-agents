import os
import json
from typing import Dict, Any
from google.cloud import firestore
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class EnqueueTranscription(BaseTool):
    def __init__(self):
        super().__init__()
        self.db = self._initialize_firestore()
        self.max_duration_sec = 4200  # 70 minutes
    
    def _validate_env_vars(self):
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH")
        self.project_id = self.get_env_var("GCP_PROJECT_ID")
    
    def _initialize_firestore(self):
        return firestore.Client(
            project=self.project_id,
            credentials=None
        )
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        video_id = request.get('video_id', '')
        
        if not video_id:
            raise ValueError("video_id is required")
        
        try:
            video_ref = self.db.collection('videos').document(video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                raise ValueError(f"Video {video_id} does not exist")
            
            video_data = video_doc.to_dict()
            
            transcript_ref = self.db.collection('transcripts').document(video_id)
            if transcript_ref.get().exists:
                return {"job_id": None, "message": "Video already transcribed"}
            
            if video_data.get('duration_sec', 0) > self.max_duration_sec:
                return {
                    "job_id": None, 
                    "message": f"Video duration {video_data['duration_sec']}s exceeds max {self.max_duration_sec}s"
                }
            
            job_ref = self.db.collection('jobs').collection('transcription').document()
            
            job_data = {
                'video_id': video_id,
                'video_url': video_data.get('url'),
                'title': video_data.get('title'),
                'duration_sec': video_data.get('duration_sec'),
                'status': 'pending',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            job_ref.set(job_data)
            
            video_ref.update({
                'status': 'transcription_queued',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            return {"job_id": job_ref.id}
            
        except Exception as e:
            raise RuntimeError(f"Failed to enqueue transcription: {str(e)}")


if __name__ == "__main__":
    tool = EnqueueTranscription()
    
    test_request = {
        "video_id": "test_video_123"
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")