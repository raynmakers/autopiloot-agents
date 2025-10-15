"""
SaveVideoMetadata tool for storing video information in Firestore.
Implements TASK-SCR-0013 with idempotent upsert and status tracking.
"""

import os
import sys
import json
from typing import Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add core and config directories to path
from env_loader import get_required_env_var
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class SaveVideoMetadata(BaseTool):
    """
    Saves video metadata to Firestore with deduplication and status tracking.

    Upserts video information into the videos/{video_id} collection, ensuring
    idempotency by video_id and maintaining proper status progression. All
    timestamps are stored in UTC using ISO 8601 format with Z suffix.

    Status-Aware Deduplication:
    When source='sheet', skips videos already in pipeline (status in
    ['transcription_queued', 'transcribed', 'summarized', 'rejected_non_business'])
    to prevent duplicate processing and status resets. This ensures sheet backfills
    don't interfere with videos already being processed.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID (e.g., 'dQw4w9WgXcQ')"
    )
    
    url: str = Field(
        ..., 
        description="Full YouTube URL (e.g., 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')"
    )
    
    title: str = Field(
        ..., 
        description="Video title as returned by YouTube API"
    )
    
    published_at: str = Field(
        ..., 
        description="Publication date in ISO8601 UTC format with Z suffix (e.g., '2025-01-27T00:00:00Z')"
    )
    
    duration_sec: int = Field(
        ..., 
        description="Video duration in seconds", 
        ge=0
    )
    
    source: str = Field(
        ..., 
        description="Source of discovery: 'scrape' for YouTube API discovery or 'sheet' for Google Sheets backfill"
    )
    
    channel_id: Optional[str] = Field(
        None,
        description="YouTube channel ID (optional, auto-resolved from video if not provided)"
    )

    sheet_row_index: Optional[int] = Field(
        None,
        description="Sheet row index if video discovered via Google Sheets (for cleanup tracking)"
    )

    sheet_id: Optional[str] = Field(
        None,
        description="Google Sheet ID if video discovered via Google Sheets (for cleanup tracking)"
    )

    def run(self) -> str:
        """
        Saves the video metadata to Firestore with idempotent upsert.
        
        Returns:
            str: JSON string containing document reference path
            
        Raises:
            ValueError: If required fields are missing or invalid
            RuntimeError: If Firestore operation fails
        """
        try:
            # Validate business rules from configuration
            config = load_app_config()
            max_duration = config.get("idempotency", {}).get("max_video_duration_sec", 4200)
            
            if self.duration_sec > max_duration:
                return json.dumps({
                    "error": f"Video duration {self.duration_sec}s exceeds maximum {max_duration}s (70 minutes). Skipping according to business rules.",
                    "doc_ref": None
                })
            
            # Initialize Firestore client
            db = self._initialize_firestore()
            
            # Create document reference
            doc_ref = db.collection('videos').document(self.video_id)
            
            # Check if document already exists
            existing_doc = doc_ref.get()

            # Status-aware deduplication: prevent overwriting videos already in pipeline
            if existing_doc.exists:
                existing_data = existing_doc.to_dict()
                existing_status = existing_data.get('status')

                # If video is already in pipeline from sheet source, skip to prevent status reset
                # Only apply this check when current source is 'sheet' to avoid blocking scraper updates
                if self.source == 'sheet' and existing_status in ['transcription_queued', 'transcribed', 'summarized', 'rejected_non_business']:
                    return json.dumps({
                        "doc_ref": f"videos/{self.video_id}",
                        "operation": "skipped",
                        "video_id": self.video_id,
                        "status": existing_status,
                        "message": f"Video already in pipeline with status '{existing_status}', skipping sheet update to prevent duplicate processing"
                    }, indent=2)

            # Prepare video data with all required fields from PRD
            video_data = {
                'video_id': self.video_id,
                'url': self.url,
                'title': self.title,
                'published_at': self.published_at,
                'duration_sec': self.duration_sec,
                'source': self.source,  # "scrape" | "sheet"
                'status': 'discovered',  # Initial status per PRD
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            # Add optional channel_id if provided
            if self.channel_id:
                video_data['channel_id'] = self.channel_id

            # Add sheet metadata if provided (for cleanup tracking)
            if self.sheet_row_index is not None and self.sheet_id is not None:
                video_data['sheet_metadata'] = {
                    'sheet_id': self.sheet_id,
                    'row_index': self.sheet_row_index,
                    'processed_at': None  # Set when video reaches 'summarized' status
                }

            # Idempotent upsert: set created_at only for new documents
            if not existing_doc.exists:
                video_data['created_at'] = firestore.SERVER_TIMESTAMP
                doc_ref.set(video_data)
                operation = "created"
            else:
                # Update existing document (preserve created_at)
                doc_ref.update(video_data)
                operation = "updated"
            
            # Log video discovery to audit trail (TASK-AUDIT-0041)
            audit_logger.log_video_discovered(
                video_id=self.video_id,
                source=self.source,
                actor="ScraperAgent"
            )
            
            # Return JSON response as required by Agency Swarm v1.0.0
            return json.dumps({
                "doc_ref": f"videos/{self.video_id}",
                "operation": operation,
                "video_id": self.video_id,
                "status": "discovered"
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to save video metadata: {str(e)}",
                "doc_ref": None
            })
    
    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            # Get required project ID
            project_id = get_required_env_var(
                "GCP_PROJECT_ID", 
                "Google Cloud Project ID for Firestore"
            )
            
            # Get service account credentials path
            credentials_path = get_required_env_var(
                "GOOGLE_APPLICATION_CREDENTIALS", 
                "Google service account credentials file path"
            )
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            # Initialize Firestore client with project ID
            # The client will automatically use GOOGLE_APPLICATION_CREDENTIALS
            return firestore.Client(project=project_id)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    # Test the tool with two videos: one entertainment (Rick Astley) and one business (Dan Martell)
    print("="*80)
    print("TEST 1: Rick Astley - Never Gonna Give You Up (Entertainment/Music)")
    print("="*80)

    test_tool_1 = SaveVideoMetadata(
        video_id="dQw4w9WgXcQ",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up (Official Video)",
        published_at="2009-10-25T06:57:33Z",
        duration_sec=212,
        source="scrape",
        channel_id="UCuAXFkgsw1L7xaCfnd5JJOw"
    )

    try:
        result = test_tool_1.run()
        print("SaveVideoMetadata test result:")
        print(result)

        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['error']}")
        else:
            print(f"✅ Success: Saved to {data['doc_ref']}")
            print(f"   Operation: {data['operation']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("TEST 2: Dan Martell - How to 10x Your Business (Business/Educational)")
    print("="*80)

    test_tool_2 = SaveVideoMetadata(
        video_id="mZxDw92UXmA",
        url="https://www.youtube.com/watch?v=mZxDw92UXmA",
        title="Dan Martell - How to 10x Your Business",
        published_at="2024-01-15T12:00:00Z",
        duration_sec=1800,
        source="scrape",
        channel_id="UC5RV_s1Jh-jQI8HfygCLK9g"
    )

    try:
        result = test_tool_2.run()
        print("SaveVideoMetadata test result:")
        print(result)

        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['error']}")
        else:
            print(f"✅ Success: Saved to {data['doc_ref']}")
            print(f"   Operation: {data['operation']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("Testing complete! Use these videos to test the full pipeline:")
    print("- dQw4w9WgXcQ: Should be rejected by summarizer (non-business content)")
    print("- mZxDw92UXmA: Should be processed normally (business content)")
    print("="*80)