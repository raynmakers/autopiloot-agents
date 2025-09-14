import os
import json
from typing import Dict, Any
from google.cloud import firestore
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class SaveSummaryRecord(BaseTool):
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
        refs = request.get('refs', {})
        
        if not video_id:
            raise ValueError("video_id is required")
        if not refs:
            raise ValueError("refs is required")
        
        try:
            video_ref = self.db.collection('videos').document(video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                raise ValueError(f"Video {video_id} does not exist")
            
            transcript_doc_ref = refs.get('transcript_doc_ref')
            if transcript_doc_ref:
                transcript_ref = self.db.document(transcript_doc_ref)
                if not transcript_ref.get().exists:
                    raise ValueError(f"Transcript {transcript_doc_ref} does not exist")
            
            summary_ref = self.db.collection('summaries').document(video_id)
            
            summary_data = {
                'video_id': video_id,
                'zep_doc_id': refs.get('zep_doc_id'),
                'short_drive_id': refs.get('short_drive_id'),
                'transcript_doc_ref': refs.get('transcript_doc_ref'),
                'transcript_drive_id_txt': refs.get('transcript_drive_id_txt'),
                'transcript_drive_id_json': refs.get('transcript_drive_id_json'),
                'prompt_id': refs.get('prompt_id'),
                'token_usage': refs.get('token_usage', {}),
                'rag_refs': refs.get('rag_refs', []),
                'status': 'completed',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            summary_ref.set(summary_data)
            
            video_ref.update({
                'status': 'summarized',
                'summary_short_doc_ref': f"summaries/{video_id}",
                'summary_short_drive_id': refs.get('short_drive_id'),
                'zep_doc_id': refs.get('zep_doc_id'),
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            return {"summary_doc_ref": f"summaries/{video_id}"}
            
        except Exception as e:
            raise RuntimeError(f"Failed to save summary record: {str(e)}")


if __name__ == "__main__":
    tool = SaveSummaryRecord()
    
    test_request = {
        "video_id": "test_video_123",
        "refs": {
            "zep_doc_id": "summary_test_video_123",
            "short_drive_id": "drive_summary_123",
            "transcript_doc_ref": "transcripts/test_video_123",
            "transcript_drive_id_txt": "drive_txt_123",
            "transcript_drive_id_json": "drive_json_123",
            "prompt_id": "summary_test_gpt4",
            "token_usage": {
                "input_tokens": 500,
                "output_tokens": 200
            },
            "rag_refs": []
        }
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")