"""
StoreShortSummaryToDrive tool for storing short summaries in Google Drive with dual format support.
Implements TASK-SUM-0031 specification with JSON and Markdown storage for different use cases.
"""

import os
import sys
import json
from typing import Dict, Any
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var
from loader import load_app_config, get_drive_naming_format

# Google Drive API imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2.service_account import Credentials


class StoreShortSummaryToDrive(BaseTool):
    """
    Store short summary to Google Drive in both JSON and Markdown formats.
    
    Creates structured JSON for programmatic access and human-readable Markdown
    for review workflows. Uses configured folder IDs and naming conventions
    from settings.yaml for consistent organization.
    
    Returns Drive file ID for the primary storage format (JSON).
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for file naming and organization"
    )
    
    short_summary: Dict[str, Any] = Field(
        ..., 
        description="Generated summary containing bullets, key_concepts, prompt_id, and token_usage"
    )
    
    def run(self) -> str:
        """
        Store short summary to Google Drive in JSON and Markdown formats.
        
        Returns:
            str: JSON string containing short_drive_id (JSON file ID) for reference
        
        Raises:
            RuntimeError: If Drive storage fails
        """
        try:
            # Initialize Google Drive service
            drive_service = self._initialize_drive_service()
            
            # Get configuration
            config = load_app_config()
            folder_id = self._get_summaries_folder_id()
            
            # Generate timestamps and filenames
            timestamp = datetime.now(timezone.utc)
            date_str = timestamp.strftime('%Y-%m-%d')
            naming_format = get_drive_naming_format(config)
            
            # Create and store JSON file (primary format)
            json_content = self._create_json_content(self.short_summary, timestamp)
            json_filename = self._format_filename(naming_format, self.video_id, date_str, "summary", "json")
            json_drive_id = self._upload_to_drive(
                drive_service, 
                folder_id, 
                json_filename, 
                json_content, 
                "application/json"
            )
            
            # Create and store Markdown file (human-readable format)
            markdown_content = self._create_markdown_content(self.short_summary, timestamp)
            markdown_filename = self._format_filename(naming_format, self.video_id, date_str, "summary", "md")
            markdown_drive_id = self._upload_to_drive(
                drive_service, 
                folder_id, 
                markdown_filename, 
                markdown_content, 
                "text/markdown"
            )
            
            return json.dumps({
                "short_drive_id": json_drive_id  # Primary reference is JSON file
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to store summary to Drive: {str(e)}",
                "short_drive_id": None
            })
    
    def _initialize_drive_service(self):
        """Initialize Google Drive API service with proper authentication."""
        try:
            # Get service account credentials path
            credentials_path = get_required_env_var(
                "GOOGLE_APPLICATION_CREDENTIALS", 
                "Google service account credentials file path"
            )
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            # Initialize credentials with Drive scope
            credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            # Build and return Drive service
            return build('drive', 'v3', credentials=credentials)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Drive service: {str(e)}")
    
    def _get_summaries_folder_id(self) -> str:
        """Get Google Drive folder ID for summary storage."""
        folder_id = get_required_env_var(
            "GOOGLE_DRIVE_FOLDER_ID_SUMMARIES", 
            "Google Drive folder ID for summary storage"
        )
        return folder_id
    
    def _format_filename(self, naming_format: str, video_id: str, date: str, type_name: str, ext: str) -> str:
        """
        Format filename using naming convention from settings.yaml.
        
        Args:
            naming_format: Format string from configuration
            video_id: YouTube video identifier
            date: Date string for timestamping
            type_name: Type of file (e.g., 'summary')
            ext: File extension
            
        Returns:
            Formatted filename
        """
        return naming_format.format(
            video_id=video_id,
            date=date,
            type=type_name,
            ext=ext
        )
    
    def _create_json_content(self, summary: Dict[str, Any], timestamp: datetime) -> str:
        """
        Create structured JSON content for programmatic access.
        
        Args:
            summary: Summary data with bullets, concepts, metadata
            timestamp: Creation timestamp
            
        Returns:
            JSON string content
        """
        json_data = {
            "video_id": self.video_id,
            "bullets": summary.get("bullets", []),
            "key_concepts": summary.get("key_concepts", []),
            "prompt_id": summary.get("prompt_id", ""),
            "token_usage": summary.get("token_usage", {}),
            "metadata": {
                "created_at": timestamp.isoformat(),
                "bullets_count": len(summary.get("bullets", [])),
                "concepts_count": len(summary.get("key_concepts", [])),
                "source": "autopiloot_summarizer",
                "format_version": "1.0"
            }
        }
        
        return json.dumps(json_data, indent=2, ensure_ascii=False)
    
    def _create_markdown_content(self, summary: Dict[str, Any], timestamp: datetime) -> str:
        """
        Create human-readable Markdown content for review workflows.
        
        Args:
            summary: Summary data with bullets, concepts, metadata
            timestamp: Creation timestamp
            
        Returns:
            Markdown string content
        """
        bullets = summary.get("bullets", [])
        key_concepts = summary.get("key_concepts", [])
        prompt_id = summary.get("prompt_id", "")
        token_usage = summary.get("token_usage", {})
        
        markdown_parts = [
            f"# Video Summary: {self.video_id}",
            "",
            f"**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"**Prompt ID:** {prompt_id}",
            f"**Token Usage:** {token_usage.get('input_tokens', 0)} input, {token_usage.get('output_tokens', 0)} output",
            "",
            "## Actionable Insights",
            ""
        ]
        
        # Add bullets
        if bullets:
            for bullet in bullets:
                markdown_parts.append(f"- {bullet}")
        else:
            markdown_parts.append("*No actionable insights generated*")
        
        markdown_parts.extend([
            "",
            "## Key Concepts",
            ""
        ])
        
        # Add key concepts
        if key_concepts:
            for concept in key_concepts:
                markdown_parts.append(f"- {concept}")
        else:
            markdown_parts.append("*No key concepts identified*")
        
        markdown_parts.extend([
            "",
            "---",
            "",
            f"*Generated by Autopiloot Summarizer Agent*"
        ])
        
        return "\n".join(markdown_parts)
    
    def _upload_to_drive(
        self, 
        drive_service, 
        folder_id: str, 
        filename: str, 
        content: str, 
        mime_type: str
    ) -> str:
        """
        Upload content to Google Drive.
        
        Args:
            drive_service: Google Drive API service
            folder_id: Target folder ID
            filename: Name for the uploaded file
            content: File content as string
            mime_type: MIME type for the file
            
        Returns:
            Google Drive file ID
        """
        try:
            # Prepare file metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id],
                'mimeType': mime_type
            }
            
            # Create media upload object
            media = MediaInMemoryUpload(
                content.encode('utf-8'),
                mimetype=mime_type,
                resumable=True
            )
            
            # Upload file
            file_result = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()
            
            return file_result['id']
            
        except Exception as e:
            raise RuntimeError(f"Failed to upload {filename} to Drive: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    test_summary = {
        "bullets": [
            "Focus on understanding customer pain points before developing solutions",
            "Implement systematic sales processes with clear metrics and stages",
            "Build automated systems that can scale without constant manual intervention"
        ],
        "key_concepts": [
            "Customer acquisition cost optimization",
            "Systematic sales process design", 
            "Business automation and scaling",
            "Performance metrics tracking"
        ],
        "prompt_id": "coach_v1_12345678",
        "token_usage": {
            "input_tokens": 1500,
            "output_tokens": 300
        }
    }
    
    tool = StoreShortSummaryToDrive(
        video_id="test_video_123",
        short_summary=test_summary
    )
    
    try:
        result = tool.run()
        print("StoreShortSummaryToDrive test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Successfully stored to Drive with ID: {data['short_drive_id']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()