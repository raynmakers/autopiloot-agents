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


class StoreShortSummaryToDrive(BaseTool):
    def __init__(self):
        super().__init__()
        self.drive = self._initialize_drive_client()
    
    def _validate_env_vars(self):
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH")
        self.drive_folder_id = self.get_env_var("DRIVE_SUMMARIES_FOLDER_ID")
    
    def _initialize_drive_client(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_path,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        return build('drive', 'v3', credentials=credentials)
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        video_id = request.get('video_id', '')
        short_summary = request.get('short_summary', {})
        
        if not video_id:
            raise ValueError("video_id is required")
        if not short_summary:
            raise ValueError("short_summary is required")
        
        try:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            
            markdown_content = f"# Video Summary: {video_id}\n\n"
            markdown_content += f"Generated: {date_str}\n\n"
            
            markdown_content += "## Actionable Insights\n\n"
            for bullet in short_summary.get('bullets', []):
                markdown_content += f"- {bullet}\n"
            
            markdown_content += "\n## Key Concepts\n\n"
            for concept in short_summary.get('key_concepts', []):
                markdown_content += f"- {concept}\n"
            
            if short_summary.get('prompt_id'):
                markdown_content += f"\n---\n_Prompt ID: {short_summary['prompt_id']}_\n"
            
            md_filename = f"{video_id}_{date_str}_summary.md"
            md_metadata = {
                'name': md_filename,
                'parents': [self.drive_folder_id],
                'mimeType': 'text/markdown'
            }
            md_media = MediaInMemoryUpload(
                markdown_content.encode('utf-8'),
                mimetype='text/markdown',
                resumable=True
            )
            md_file = self.drive.files().create(
                body=md_metadata,
                media_body=md_media,
                fields='id'
            ).execute()
            
            json_filename = f"{video_id}_{date_str}_summary.json"
            json_metadata = {
                'name': json_filename,
                'parents': [self.drive_folder_id],
                'mimeType': 'application/json'
            }
            json_media = MediaInMemoryUpload(
                json.dumps(short_summary, indent=2).encode('utf-8'),
                mimetype='application/json',
                resumable=True
            )
            json_file = self.drive.files().create(
                body=json_metadata,
                media_body=json_media,
                fields='id'
            ).execute()
            
            return {"short_drive_id": md_file['id']}
            
        except Exception as e:
            raise RuntimeError(f"Failed to store summary to Drive: {str(e)}")


if __name__ == "__main__":
    tool = StoreShortSummaryToDrive()
    
    test_request = {
        "video_id": "test_video_123",
        "short_summary": {
            "bullets": [
                "Test insight 1",
                "Test insight 2"
            ],
            "key_concepts": [
                "Concept A",
                "Concept B"
            ],
            "prompt_id": "test_prompt"
        }
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")