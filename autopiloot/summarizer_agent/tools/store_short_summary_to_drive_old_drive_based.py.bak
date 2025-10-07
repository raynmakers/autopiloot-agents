import os
import json
from typing import Dict, Any, List
from pydantic import Field
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2 import service_account
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool


class StoreShortSummaryToDrive(BaseTool):
    """
    Store summary to Google Drive in both Markdown and JSON formats.
    Creates human-readable and structured formats for different use cases.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for file naming and organization"
    )
    bullets: List[str] = Field(
        ..., 
        description="List of actionable insights from summary generation"
    )
    key_concepts: List[str] = Field(
        ..., 
        description="List of key concepts and frameworks identified"
    )
    prompt_id: str = Field(
        ..., 
        description="Unique identifier for the prompt used in generation"
    )
    
    def run(self) -> str:
        """
        Store summary to Google Drive in Markdown and JSON formats.
        
        Returns:
            JSON string with short_drive_id for the markdown file reference
        """
        # Validate required environment variables
        service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
        drive_folder_id = os.getenv("DRIVE_SUMMARIES_FOLDER_ID")
        
        if not service_account_path:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_PATH environment variable is required")
        if not drive_folder_id:
            raise ValueError("DRIVE_SUMMARIES_FOLDER_ID environment variable is required")
        
        try:
            # Initialize Google Drive client
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            drive = build('drive', 'v3', credentials=credentials)
            
            date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            # Create Markdown content for human readability
            markdown_content = f"# Video Summary: {self.video_id}\n\n"
            markdown_content += f"Generated: {date_str}\n\n"
            
            markdown_content += "## Actionable Insights\n\n"
            for bullet in self.bullets:
                markdown_content += f"- {bullet}\n"
            
            markdown_content += "\n## Key Concepts\n\n"
            for concept in self.key_concepts:
                markdown_content += f"- {concept}\n"
            
            markdown_content += f"\n---\n_Prompt ID: {self.prompt_id}_\n"
            
            # Store Markdown file
            md_filename = f"{self.video_id}_{date_str}_summary.md"
            md_metadata = {
                'name': md_filename,
                'parents': [drive_folder_id],
                'mimeType': 'text/markdown'
            }
            md_media = MediaInMemoryUpload(
                markdown_content.encode('utf-8'),
                mimetype='text/markdown',
                resumable=True
            )
            md_file = drive.files().create(
                body=md_metadata,
                media_body=md_media,
                fields='id'
            ).execute()
            
            # Create structured JSON data
            summary_data = {
                "video_id": self.video_id,
                "bullets": self.bullets,
                "key_concepts": self.key_concepts,
                "prompt_id": self.prompt_id,
                "generated_date": date_str
            }
            
            # Store JSON file for structured access
            json_filename = f"{self.video_id}_{date_str}_summary.json"
            json_metadata = {
                'name': json_filename,
                'parents': [drive_folder_id],
                'mimeType': 'application/json'
            }
            json_media = MediaInMemoryUpload(
                json.dumps(summary_data, indent=2).encode('utf-8'),
                mimetype='application/json',
                resumable=True
            )
            json_file = drive.files().create(
                body=json_metadata,
                media_body=json_media,
                fields='id'
            ).execute()
            
            result = {
                "short_drive_id": md_file['id'],
                "json_drive_id": json_file['id'],
                "md_filename": md_filename,
                "json_filename": json_filename
            }
            
            return json.dumps(result)
            
        except Exception as e:
            raise RuntimeError(f"Failed to store summary to Drive: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = StoreShortSummaryToDrive(
        video_id="test_video_123",
        bullets=["Test insight 1", "Test insight 2"],
        key_concepts=["Concept A", "Concept B"],
        prompt_id="test_prompt"
    )
    
    try:
        result = tool.run()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")