import os
import json
import hashlib
from typing import Dict, Any
from google.cloud import firestore
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class SaveTranscriptRecord(BaseTool):
    def __init__(self):
        super().__init__()
        self.db = self._initialize_firestore()
    
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
        drive_ids = request.get('drive_ids', {})
        transcript_digest = request.get('transcript_digest', '')
        costs = request.get('costs', {})
        
        if not video_id:
            raise ValueError("video_id is required")
        if not drive_ids:
            raise ValueError("drive_ids is required")
        if not transcript_digest:
            transcript_digest = hashlib.sha256(video_id.encode()).hexdigest()[:16]
        
        try:
            video_ref = self.db.collection('videos').document(video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                raise ValueError(f"Video {video_id} does not exist")
            
            transcript_ref = self.db.collection('transcripts').document(video_id)
            
            transcript_data = {
                'video_id': video_id,
                'drive_id_txt': drive_ids.get('drive_id_txt'),
                'drive_id_json': drive_ids.get('drive_id_json'),
                'transcript_digest': transcript_digest,
                'costs': costs,
                'status': 'completed',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            transcript_ref.set(transcript_data)
            
            video_ref.update({
                'status': 'transcribed',
                'transcript_doc_ref': f"transcripts/{video_id}",
                'transcript_drive_id_txt': drive_ids.get('drive_id_txt'),
                'transcript_drive_id_json': drive_ids.get('drive_id_json'),
                'costs': {'transcription_usd': costs.get('transcription_usd', 0)},
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            return {"transcript_doc_ref": f"transcripts/{video_id}"}
            
        except Exception as e:
            raise RuntimeError(f"Failed to save transcript record: {str(e)}")


if __name__ == "__main__":
    tool = SaveTranscriptRecord()
    
    test_request = {
        "video_id": "test_video_123",
        "drive_ids": {
            "drive_id_txt": "drive_txt_123",
            "drive_id_json": "drive_json_123"
        },
        "transcript_digest": "abc123def456",
        "costs": {
            "transcription_usd": 0.65
        }
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")