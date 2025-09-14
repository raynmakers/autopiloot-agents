import os
import json
from typing import Dict, Any
from google.cloud import firestore
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class SaveVideoMetadata(BaseTool):
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
        video = request.get('video', {})
        
        required_fields = ['video_id', 'url', 'title', 'published_at', 'duration_sec', 'source']
        for field in required_fields:
            if field not in video:
                raise ValueError(f"video.{field} is required")
        
        try:
            doc_ref = self.db.collection('videos').document(video['video_id'])
            
            existing_doc = doc_ref.get()
            
            video_data = {
                'video_id': video['video_id'],
                'url': video['url'],
                'title': video['title'],
                'published_at': video['published_at'],
                'duration_sec': video['duration_sec'],
                'source': video['source'],
                'status': 'discovered',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            if video.get('channel_id'):
                video_data['channel_id'] = video['channel_id']
            
            if existing_doc.exists:
                video_data.pop('created_at')
                doc_ref.update(video_data)
            else:
                doc_ref.set(video_data)
            
            return {"doc_ref": f"videos/{video['video_id']}"}
            
        except Exception as e:
            raise RuntimeError(f"Failed to save video metadata: {str(e)}")


if __name__ == "__main__":
    tool = SaveVideoMetadata()
    
    test_request = {
        "video": {
            "video_id": "test_video_123",
            "url": "https://www.youtube.com/watch?v=test_video_123",
            "title": "Test Video Title",
            "published_at": datetime.utcnow().isoformat() + "Z",
            "duration_sec": 600,
            "source": "scrape",
            "channel_id": "test_channel_id"
        }
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")