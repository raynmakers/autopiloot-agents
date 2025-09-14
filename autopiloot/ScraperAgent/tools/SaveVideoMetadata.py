"""
SaveVideoMetadata tool for storing video information in Firestore.
"""

import os
import sys
from typing import Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime

# Add core directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
from env_loader import get_required_var, get_config_value, env_loader


class SaveVideoMetadata(BaseTool):
    """
    Saves video metadata to Firestore with deduplication and status tracking.
    
    Upserts video information into the videos collection, ensuring idempotency
    by video_id and maintaining proper status progression.
    """
    
    video_id: str = Field(..., description="YouTube video ID (e.g., 'dQw4w9WgXcQ')")
    url: str = Field(..., description="Full YouTube URL")
    title: str = Field(..., description="Video title")
    published_at: str = Field(..., description="Publication date in ISO8601 format")
    duration_sec: int = Field(..., description="Video duration in seconds", ge=0)
    source: str = Field(..., description="Source of discovery: 'scrape' or 'sheet'")
    channel_id: str = Field(default="", description="YouTube channel ID (optional)")
    
    def run(self) -> str:
        """
        Saves the video metadata to Firestore.
        
        Returns:
            str: Document reference path (e.g., "videos/dQw4w9WgXcQ")
            
        Raises:
            ValueError: If required fields are missing or invalid
            RuntimeError: If Firestore operation fails
        """
        try:
            # Validate against business rules from settings
            max_duration = get_config_value("idempotency.max_video_duration_sec", 4200)
            if self.duration_sec > max_duration:
                raise ValueError(
                    f"Video duration {self.duration_sec}s exceeds maximum {max_duration}s (70 minutes). "
                    f"Video will be skipped according to business rules."
                )
            
            # Initialize Firestore client
            db = self._initialize_firestore()
            
            # Create document reference
            doc_ref = db.collection('videos').document(self.video_id)
            
            # Check if document already exists
            existing_doc = doc_ref.get()
            
            # Prepare video data
            video_data = {
                'video_id': self.video_id,
                'url': self.url,
                'title': self.title,
                'published_at': self.published_at,
                'duration_sec': self.duration_sec,
                'source': self.source,
                'status': 'discovered',
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            # Add optional fields
            if self.channel_id:
                video_data['channel_id'] = self.channel_id
            
            # Set created_at only for new documents
            if not existing_doc.exists:
                video_data['created_at'] = firestore.SERVER_TIMESTAMP
                doc_ref.set(video_data)
            else:
                # Update existing document (preserve created_at)
                video_data.pop('created_at', None)
                doc_ref.update(video_data)
            
            return f"videos/{self.video_id}"
            
        except Exception as e:
            raise RuntimeError(f"Failed to save video metadata: {str(e)}")
    
    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            # Get required project ID
            project_id = get_required_var("GCP_PROJECT_ID", "Google Cloud Project ID")
            
            # Get service credentials (will handle both GOOGLE_SERVICE_ACCOUNT_PATH and GOOGLE_APPLICATION_CREDENTIALS)
            credentials_path = env_loader.get_service_credentials()
            
            # Initialize Firestore client
            return firestore.Client(project=project_id)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    from datetime import datetime, timezone
    
    tool = SaveVideoMetadata(
        video_id="test_video_123",
        url="https://www.youtube.com/watch?v=test_video_123",
        title="Test Video Title",
        published_at=datetime.now(timezone.utc).isoformat(),
        duration_sec=600,
        source="scrape",
        channel_id="test_channel_id"
    )
    
    try:
        result = tool.run()
        print(f"Success: Saved to {result}")
    except Exception as e:
        print(f"Error: {str(e)}")