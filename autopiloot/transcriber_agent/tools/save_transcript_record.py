"""
SaveTranscriptRecord tool for persisting transcript metadata to Firestore.
Implements TASK-TRN-0022: Save transcript record with Drive IDs and status progression.
"""

import os
import json
import hashlib
import sys
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import Field, validator
from google.cloud import firestore
from google.oauth2 import service_account
from agency_swarm.tools import BaseTool
from dotenv import load_dotenv

# Add core directory to path for audit logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

load_dotenv()

from audit_logger import audit_logger


class SaveTranscriptRecord(BaseTool):
    """
    Save transcript metadata and Drive file references to Firestore.
    
    Creates structured metadata record linking video to transcript files stored
    in Google Drive. Updates video status progression from 'transcription_queued'
    to 'transcribed' with proper UTC timestamps and cost tracking for budget monitoring.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for Firestore document reference"
    )
    drive_ids: Dict[str, str] = Field(
        ...,
        description="Dictionary with drive_id_txt and drive_id_json keys for transcript files"
    )
    transcript_digest: str = Field(
        ...,
        description="SHA-256 hash digest of transcript content for integrity verification"
    )
    costs: Dict[str, float] = Field(
        ...,
        description="Dictionary with transcription_usd cost for budget tracking"
    )
    
    @validator('video_id')
    def validate_video_id(cls, v):
        """Validate YouTube video ID format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("video_id cannot be empty")
        if len(v) > 50:
            raise ValueError("video_id seems too long for a valid YouTube ID")
        return v.strip()
    
    @validator('drive_ids')
    def validate_drive_ids(cls, v):
        """Validate drive_ids contains required keys."""
        if not isinstance(v, dict):
            raise ValueError("drive_ids must be a dictionary")
        
        required_keys = ['drive_id_txt', 'drive_id_json']
        missing_keys = [key for key in required_keys if key not in v]
        if missing_keys:
            raise ValueError(f"drive_ids missing required keys: {missing_keys}")
        
        # Validate drive IDs are not empty
        for key, value in v.items():
            if not value or len(str(value).strip()) == 0:
                raise ValueError(f"drive_ids.{key} cannot be empty")
        
        return v
    
    @validator('transcript_digest')
    def validate_transcript_digest(cls, v):
        """Validate transcript digest format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("transcript_digest cannot be empty")
        # Basic hex validation (flexible length for different hash formats)
        if not all(c in '0123456789abcdefABCDEF' for c in v.strip()):
            raise ValueError("transcript_digest must be a valid hex string")
        return v.strip()
    
    @validator('costs')
    def validate_costs(cls, v):
        """Validate costs structure and values."""
        if not isinstance(v, dict):
            raise ValueError("costs must be a dictionary")
        
        if 'transcription_usd' not in v:
            raise ValueError("costs must include 'transcription_usd' key")
        
        cost = v['transcription_usd']
        if not isinstance(cost, (int, float)):
            raise ValueError("transcription_usd must be a number")
        
        if cost < 0:
            raise ValueError("transcription_usd cannot be negative")
        
        return v
    
    def run(self) -> str:
        """
        Save transcript metadata to Firestore with proper status progression.
        
        Process:
        1. Validate environment configuration for Firestore access
        2. Initialize Firestore client with service account authentication
        3. Verify video document exists and is in correct status
        4. Create comprehensive transcript metadata document
        5. Update video document with transcript references and status change
        6. Return document references for tracking
        
        Returns:
            JSON string containing:
            - transcript_doc_ref: Firestore document reference path
            - video_status: Updated video status (transcribed)
            - video_id: YouTube video identifier
            - created_at: UTC timestamp of record creation
        """
        # Validate required environment variables
        project_id = os.getenv("GCP_PROJECT_ID")
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if not project_id:
            return json.dumps({
                "error": "configuration_error",
                "message": "GCP_PROJECT_ID environment variable is required"
            })
        
        if not service_account_path:
            return json.dumps({
                "error": "configuration_error",
                "message": "GOOGLE_APPLICATION_CREDENTIALS environment variable is required"
            })
        
        try:
            # Initialize Firestore client with service account
            credentials = service_account.Credentials.from_service_account_file(service_account_path)
            db = firestore.Client(project=project_id, credentials=credentials)
            
            # Get current UTC timestamp for consistency
            current_time = datetime.now(timezone.utc)
            current_time_iso = current_time.isoformat()
            
            # Verify video document exists and check status
            video_ref = db.collection('videos').document(self.video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                return json.dumps({
                    "error": "document_not_found",
                    "message": f"Video document {self.video_id} does not exist in Firestore",
                    "video_id": self.video_id
                })
            
            video_data = video_doc.to_dict()
            current_status = video_data.get('status', 'unknown')
            
            # Verify video is in expected status for transcription completion
            expected_statuses = ['transcription_queued', 'processing', 'queued']  # Allow flexible status checking
            if current_status not in expected_statuses and current_status != 'transcribed':
                return json.dumps({
                    "error": "invalid_status",
                    "message": f"Video {self.video_id} has status '{current_status}', expected one of {expected_statuses}",
                    "video_id": self.video_id,
                    "current_status": current_status
                })
            
            # Create comprehensive transcript document
            transcript_ref = db.collection('transcripts').document(self.video_id)
            transcript_data = {
                'video_id': self.video_id,
                'drive_ids': self.drive_ids,
                'transcript_digest': self.transcript_digest,
                'costs': self.costs,
                'status': 'completed',
                'created_at': current_time_iso,
                'updated_at': current_time_iso,
                'metadata': {
                    'autopiloot_version': '1.0.0',
                    'created_by': 'transcriber_agent',
                    'processing_completed_at': current_time_iso
                },
                # Include video metadata for reference
                'video_metadata': {
                    'title': video_data.get('title', ''),
                    'channel_title': video_data.get('channel_title', ''),
                    'published_at': video_data.get('published_at', ''),
                    'duration_sec': video_data.get('duration_sec', 0)
                }
            }
            
            # Use atomic transaction to ensure consistency
            transaction = db.transaction()
            
            @firestore.transactional
            def update_records(transaction, video_ref, transcript_ref, video_update_data, transcript_data):\n                # Set transcript document\n                transaction.set(transcript_ref, transcript_data)\n                # Update video document\n                transaction.update(video_ref, video_update_data)\n                return True\n            \n            # Prepare video update data\n            video_update_data = {\n                'status': 'transcribed',  # Progress from 'transcription_queued' to 'transcribed'\n                'transcript_doc_ref': f\"transcripts/{self.video_id}\",\n                'transcript_drive_ids': self.drive_ids,\n                'transcript_digest': self.transcript_digest,\n                'costs': firestore.ArrayUnion([{\n                    'type': 'transcription',\n                    'amount_usd': self.costs['transcription_usd'],\n                    'timestamp': current_time_iso,\n                    'provider': 'assemblyai'\n                }]) if 'costs' not in video_data else self.costs,\n                'updated_at': current_time_iso,\n                'processing_completed_at': current_time_iso\n            }\n            \n            # Execute transaction\n            update_records(transaction, video_ref, transcript_ref, video_update_data, transcript_data)\n            \n            # Prepare successful response\n            result = {\n                \"transcript_doc_ref\": f\"transcripts/{self.video_id}\",\n                \"video_status\": \"transcribed\",\n                \"video_id\": self.video_id,\n                \"created_at\": current_time_iso,\n                \"drive_ids\": self.drive_ids,\n                \"transcript_digest\": self.transcript_digest,\n                \"costs\": self.costs,\n                \"status_change\": {\n                    \"from\": current_status,\n                    \"to\": \"transcribed\"\n                }\n            }\n            \n            # Log transcript creation to audit trail (TASK-AUDIT-0041)
            audit_logger.log_transcript_created(
                video_id=self.video_id,
                transcript_doc_ref=f"transcripts/{self.video_id}",
                actor="TranscriberAgent"
            )
            
            # Log cost update to audit trail
            audit_logger.log_cost_updated(
                date=current_time.strftime('%Y-%m-%d'),
                cost_usd=self.costs['transcription_usd'],
                cost_type="transcription",
                actor="TranscriberAgent"
            )
            
            return json.dumps(result, indent=2)\n            \n        except service_account.exceptions.ServiceAccountCredentialsError as e:\n            return json.dumps({\n                \"error\": \"credentials_error\",\n                \"message\": \"Invalid Google service account credentials\",\n                \"details\": str(e)\n            })\n        except Exception as e:\n            return json.dumps({\n                \"error\": \"firestore_error\",\n                \"message\": f\"Failed to save transcript record: {str(e)}\",\n                \"video_id\": self.video_id\n            })


if __name__ == "__main__":
    print("Testing SaveTranscriptRecord tool...")
    print("="*50)
    
    # Test 1: Basic transcript record saving
    print("\nTest 1: Basic transcript record creation")
    tool = SaveTranscriptRecord(
        video_id="test_video_123",
        drive_ids={
            "drive_id_txt": "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789",
            "drive_id_json": "1XyZ9876543210abcDEFghiJKLmnOpQrStuVwx"
        },
        transcript_digest="a1b2c3d4e5f67890",
        costs={
            "transcription_usd": 0.6875
        }
    )
    
    try:
        result = tool.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
            print(f"   Error type: {data['error']}")
        else:
            print(f"✅ Transcript record saved successfully:")
            print(f"   Document ref: {data.get('transcript_doc_ref', 'N/A')}")
            print(f"   Video status: {data.get('video_status', 'N/A')}")
            print(f"   Created at: {data.get('created_at', 'N/A')}")
            print(f"   Status change: {data.get('status_change', {}).get('from', 'N/A')} → {data.get('status_change', {}).get('to', 'N/A')}")
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    # Test 2: Parameter validation - empty video_id
    print("\n" + "="*50)
    print("\nTest 2: Parameter validation (empty video_id)")
    try:
        invalid_tool = SaveTranscriptRecord(
            video_id="",  # Empty video ID
            drive_ids={"drive_id_txt": "test_txt", "drive_id_json": "test_json"},
            transcript_digest="abcd1234",
            costs={"transcription_usd": 1.0}
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 3: Parameter validation - invalid drive_ids
    print("\n" + "="*50)
    print("\nTest 3: Parameter validation (missing drive_id keys)")
    try:
        invalid_tool2 = SaveTranscriptRecord(
            video_id="test_video_456",
            drive_ids={"drive_id_txt": "test_txt"},  # Missing drive_id_json
            transcript_digest="abcd1234",
            costs={"transcription_usd": 1.0}
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 4: Parameter validation - invalid transcript_digest
    print("\n" + "="*50)
    print("\nTest 4: Parameter validation (invalid transcript_digest)")
    try:
        invalid_tool3 = SaveTranscriptRecord(
            video_id="test_video_789",
            drive_ids={"drive_id_txt": "test_txt", "drive_id_json": "test_json"},
            transcript_digest="invalid_hex_123xyz",  # Contains non-hex characters
            costs={"transcription_usd": 1.0}
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 5: Parameter validation - invalid costs
    print("\n" + "="*50)
    print("\nTest 5: Parameter validation (negative transcription cost)")
    try:
        invalid_tool4 = SaveTranscriptRecord(
            video_id="test_video_abc",
            drive_ids={"drive_id_txt": "test_txt", "drive_id_json": "test_json"},
            transcript_digest="abcd1234",
            costs={"transcription_usd": -0.5}  # Negative cost
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    
    # Test 6: Complex valid configuration
    print("\n" + "="*50)
    print("\nTest 6: Complex transcript record with full data")
    complex_tool = SaveTranscriptRecord(
        video_id="dQw4w9WgXcQ",  # Rick Roll video ID format
        drive_ids={
            "drive_id_txt": "1BcD3efGhIJkLmNoPqRSTuVwxyz0123456789",
            "drive_id_json": "1YzX9876543210defGHIjklMNOpQrStuVwxAb"
        },
        transcript_digest="f1e2d3c4b5a67890abcdef1234567890",  # 32 char hex
        costs={
            "transcription_usd": 2.4375
        }
    )
    
    try:
        result = complex_tool.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"✅ Complex transcript record processed successfully:")
            print(f"   Video ID: {data.get('video_id', 'N/A')}")
            print(f"   Digest: {data.get('transcript_digest', 'N/A')}")
            print(f"   Cost: ${data.get('costs', {}).get('transcription_usd', 0):.4f}")
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    print("\n" + "="*50)
    print("Testing complete!")
    print("\nNote: Actual Firestore operations will fail without proper GCP credentials and project configuration.")