"""
StoreTranscriptToDrive tool for uploading transcript files to Google Drive.
Implements TASK-TRN-0022: Store transcripts in both TXT and JSON formats with proper organization.
"""

import os
import json
import hashlib
from typing import Dict, Any
from pydantic import Field, field_validator
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from datetime import datetime
from agency_swarm.tools import BaseTool
from dotenv import load_dotenv

load_dotenv()


class StoreTranscriptToDrive(BaseTool):
    """
    Store transcript files to Google Drive in both TXT and JSON formats.
    
    Creates organized, timestamped files following drive naming conventions.
    Uploads both human-readable text and structured JSON data for different
    downstream processing needs. Returns Drive file IDs for Firestore tracking.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for file naming and organization"
    )
    transcript_text: str = Field(
        ..., 
        description="Plain text transcript content for human-readable TXT file"
    )
    transcript_json: Dict[str, Any] = Field(
        ..., 
        description="Full structured transcript data for JSON file storage"
    )
    
    @field_validator('video_id')
    @classmethod
    def validate_video_id(cls, v):
        """Validate YouTube video ID format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("video_id cannot be empty")
        if len(v) > 50:  # YouTube video IDs are typically 11 characters
            raise ValueError("video_id seems too long for a valid YouTube ID")
        return v.strip()
    
    @field_validator('transcript_text')
    @classmethod
    def validate_transcript_text(cls, v):
        """Validate transcript text is not empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("transcript_text cannot be empty")
        return v
    
    @field_validator('transcript_json')
    @classmethod
    def validate_transcript_json(cls, v):
        """Validate transcript JSON has required fields."""
        if not isinstance(v, dict):
            raise ValueError("transcript_json must be a dictionary")
        
        required_fields = ['id', 'text', 'status']
        missing_fields = [field for field in required_fields if field not in v]
        if missing_fields:
            raise ValueError(f"transcript_json missing required fields: {missing_fields}")
        
        return v
    
    def run(self) -> str:
        """
        Upload transcript files to Google Drive with proper organization.
        
        Process:
        1. Validate environment configuration for Google Drive access
        2. Initialize Google Drive API client with service account
        3. Generate timestamped filenames following naming convention
        4. Upload TXT file for human readability
        5. Upload JSON file for structured data processing
        6. Return Drive file IDs for Firestore metadata tracking
        
        Returns:
            JSON string containing:
            - drive_id_txt: Google Drive file ID for text file
            - drive_id_json: Google Drive file ID for JSON file
            - txt_filename: Generated filename for text file
            - json_filename: Generated filename for JSON file
            - transcript_digest: SHA-256 hash of transcript text for verification
        """
        # Validate required environment variables
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        transcripts_folder_id = os.getenv("DRIVE_TRANSCRIPTS_FOLDER_ID")
        
        if not service_account_path:
            return json.dumps({
                "error": "configuration_error",
                "message": "GOOGLE_APPLICATION_CREDENTIALS environment variable is required"
            })
        
        if not transcripts_folder_id:
            return json.dumps({
                "error": "configuration_error",
                "message": "DRIVE_TRANSCRIPTS_FOLDER_ID environment variable is required"
            })
        
        try:
            # Initialize Google Drive API client
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            drive_service = build('drive', 'v3', credentials=credentials)
            
            # Generate transcript digest for verification
            transcript_digest = hashlib.sha256(self.transcript_text.encode('utf-8')).hexdigest()[:16]
            
            # Generate timestamped filenames following settings.yaml convention
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            
            # Upload TXT file (human-readable format)
            txt_filename = f"{self.video_id}_{date_str}_transcript.txt"
            txt_metadata = {
                'name': txt_filename,
                'parents': [transcripts_folder_id],
                'mimeType': 'text/plain',
                'description': f"Transcript text for YouTube video {self.video_id} - Generated {datetime.utcnow().isoformat()}Z"
            }
            
            # Prepare transcript text with metadata header
            formatted_text = f"""# YouTube Video Transcript
# Video ID: {self.video_id}
# Generated: {datetime.utcnow().isoformat()}Z
# Digest: {transcript_digest}

{self.transcript_text}
"""
            
            txt_media = MediaInMemoryUpload(
                formatted_text.encode('utf-8'),
                mimetype='text/plain',
                resumable=True
            )
            
            txt_result = drive_service.files().create(
                body=txt_metadata,
                media_body=txt_media,
                fields='id,name,size,createdTime'
            ).execute()
            
            # Upload JSON file (structured data format)
            json_filename = f"{self.video_id}_{date_str}_transcript.json"
            json_metadata = {
                'name': json_filename,
                'parents': [transcripts_folder_id],
                'mimeType': 'application/json',
                'description': f"Structured transcript data for YouTube video {self.video_id} - Generated {datetime.utcnow().isoformat()}Z"
            }
            
            # Enhance JSON with metadata
            enhanced_json = {
                **self.transcript_json,
                "metadata": {
                    "video_id": self.video_id,
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "transcript_digest": transcript_digest,
                    "autopiloot_version": "1.0.0"
                }
            }
            
            json_content = json.dumps(enhanced_json, indent=2, ensure_ascii=False)
            json_media = MediaInMemoryUpload(
                json_content.encode('utf-8'),
                mimetype='application/json',
                resumable=True
            )
            
            json_result = drive_service.files().create(
                body=json_metadata,
                media_body=json_media,
                fields='id,name,size,createdTime'
            ).execute()
            
            # Return structured result
            result = {
                "drive_id_txt": txt_result['id'],
                "drive_id_json": json_result['id'],
                "txt_filename": txt_filename,
                "json_filename": json_filename,
                "transcript_digest": transcript_digest,
                "files_uploaded": {
                    "txt": {
                        "id": txt_result['id'],
                        "name": txt_result['name'],
                        "size_bytes": int(txt_result.get('size', 0)),
                        "created_at": txt_result.get('createdTime')
                    },
                    "json": {
                        "id": json_result['id'],
                        "name": json_result['name'],
                        "size_bytes": int(json_result.get('size', 0)),
                        "created_at": json_result.get('createdTime')
                    }
                }
            }
            
            return json.dumps(result, indent=2)
            
        except service_account.exceptions.ServiceAccountCredentialsError as e:
            return json.dumps({
                "error": "credentials_error",
                "message": "Invalid Google service account credentials",
                "details": str(e)
            })
        except Exception as e:
            return json.dumps({
                "error": "upload_error",
                "message": f"Failed to store transcript to Drive: {str(e)}",
                "video_id": self.video_id
            })


if __name__ == "__main__":
    print("Testing StoreTranscriptToDrive tool...")
    print("="*50)
    
    # Test 1: Basic transcript storage
    print("\nTest 1: Basic transcript storage")
    tool = StoreTranscriptToDrive(
        video_id="test_video_123",
        transcript_text="This is a comprehensive test transcript with multiple sentences. It contains various punctuation marks, numbers like 42, and technical terms.",
        transcript_json={
            "id": "test_job_12345",
            "status": "completed",
            "text": "This is a comprehensive test transcript with multiple sentences. It contains various punctuation marks, numbers like 42, and technical terms.",
            "confidence": 0.9234,
            "audio_duration": 156.7,
            "language_code": "en",
            "words": [
                {"text": "This", "start": 0, "end": 240, "confidence": 0.95},
                {"text": "is", "start": 250, "end": 400, "confidence": 0.98}
            ]
        }
    )
    
    try:
        result = tool.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
            print(f"   Error type: {data['error']}")
        else:
            print(f"✅ Files uploaded successfully:")
            print(f"   TXT Drive ID: {data.get('drive_id_txt', 'N/A')}")
            print(f"   JSON Drive ID: {data.get('drive_id_json', 'N/A')}")
            print(f"   TXT filename: {data.get('txt_filename', 'N/A')}")
            print(f"   JSON filename: {data.get('json_filename', 'N/A')}")
            print(f"   Transcript digest: {data.get('transcript_digest', 'N/A')}")
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    # Test 2: Parameter validation - empty video_id
    print("\n" + "="*50)
    print("\nTest 2: Parameter validation (empty video_id)")
    try:
        invalid_tool = StoreTranscriptToDrive(
            video_id="",  # Empty video ID
            transcript_text="Test transcript",
            transcript_json={"id": "test", "text": "Test", "status": "completed"}
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 3: Parameter validation - empty transcript_text
    print("\n" + "="*50)
    print("\nTest 3: Parameter validation (empty transcript_text)")
    try:
        invalid_tool2 = StoreTranscriptToDrive(
            video_id="test_video_456",
            transcript_text="",  # Empty transcript
            transcript_json={"id": "test", "text": "Test", "status": "completed"}
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 4: Parameter validation - invalid transcript_json
    print("\n" + "="*50)
    print("\nTest 4: Parameter validation (invalid transcript_json)")
    try:
        invalid_tool3 = StoreTranscriptToDrive(
            video_id="test_video_789",
            transcript_text="Test transcript",
            transcript_json={"id": "test"}  # Missing required fields
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 5: Complex transcript data
    print("\n" + "="*50)
    print("\nTest 5: Complex transcript with speaker labels")
    complex_tool = StoreTranscriptToDrive(
        video_id="complex_video_abc",
        transcript_text="Speaker A: Hello, welcome to our podcast. Speaker B: Thanks for having me on the show. Speaker A: Let's dive right into the topic.",
        transcript_json={
            "id": "complex_job_67890",
            "status": "completed",
            "text": "Speaker A: Hello, welcome to our podcast. Speaker B: Thanks for having me on the show. Speaker A: Let's dive right into the topic.",
            "confidence": 0.8756,
            "audio_duration": 425.3,
            "language_code": "en",
            "utterances": [
                {
                    "speaker": "A",
                    "text": "Hello, welcome to our podcast.",
                    "start": 0,
                    "end": 2340,
                    "confidence": 0.92
                },
                {
                    "speaker": "B",
                    "text": "Thanks for having me on the show.",
                    "start": 2400,
                    "end": 4100,
                    "confidence": 0.89
                }
            ]
        }
    )
    
    try:
        result = complex_tool.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"✅ Complex transcript processed successfully:")
            print(f"   Files contain speaker diarization data")
            print(f"   Digest: {data.get('transcript_digest', 'N/A')[:8]}...")
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    print("\n" + "="*50)
    print("Testing complete!")
    print("\nNote: Actual uploads will fail without proper Google Drive credentials and folder configuration.")