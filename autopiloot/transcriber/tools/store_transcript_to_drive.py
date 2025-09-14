import os
import json
from typing import Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2 import service_account
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class StoreTranscriptToDrive(BaseTool):
    def __init__(self):
        super().__init__()
        self.drive = self._initialize_drive_client()
    
    def _validate_env_vars(self):
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH")
        self.drive_folder_id = self.get_env_var("DRIVE_TRANSCRIPTS_FOLDER_ID")
    
    def _initialize_drive_client(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_path,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        return build('drive', 'v3', credentials=credentials)
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        video_id = request.get('video_id', '')
        transcript_text = request.get('transcript_text', '')
        transcript_json = request.get('transcript_json', {})
        
        if not video_id:
            raise ValueError("video_id is required")
        if not transcript_text:
            raise ValueError("transcript_text is required")
        if not transcript_json:
            raise ValueError("transcript_json is required")
        
        try:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            
            txt_filename = f"{video_id}_{date_str}_transcript.txt"
            txt_metadata = {
                'name': txt_filename,
                'parents': [self.drive_folder_id],
                'mimeType': 'text/plain'
            }
            txt_media = MediaInMemoryUpload(
                transcript_text.encode('utf-8'),
                mimetype='text/plain',
                resumable=True
            )
            txt_file = self.drive.files().create(
                body=txt_metadata,
                media_body=txt_media,
                fields='id'
            ).execute()
            
            json_filename = f"{video_id}_{date_str}_transcript.json"
            json_metadata = {
                'name': json_filename,
                'parents': [self.drive_folder_id],
                'mimeType': 'application/json'
            }
            json_media = MediaInMemoryUpload(
                json.dumps(transcript_json, indent=2).encode('utf-8'),
                mimetype='application/json',
                resumable=True
            )
            json_file = self.drive.files().create(
                body=json_metadata,
                media_body=json_media,
                fields='id'
            ).execute()
            
            return {
                "drive_id_txt": txt_file['id'],
                "drive_id_json": json_file['id']
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to store transcript to Drive: {str(e)}")


if __name__ == "__main__":
    tool = StoreTranscriptToDrive()
    
    test_request = {
        "video_id": "test_video_123",
        "transcript_text": "This is a test transcript.",
        "transcript_json": {
            "id": "test_job_id",
            "text": "This is a test transcript.",
            "confidence": 0.95,
            "duration": 60
        }
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")