import os
import json
from typing import List, Optional
from pydantic import Field
from google.cloud import firestore
from agency_swarm.tools import BaseTool


class SaveSummaryRecord(BaseTool):
    """
    Save summary metadata and references to Firestore.
    Updates video status from 'transcribed' to 'summarized' upon completion.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for Firestore document reference"
    )
    short_drive_id: str = Field(
        ..., 
        description="Google Drive file ID for the markdown summary file"
    )
    zep_document_id: Optional[str] = Field(
        default=None, 
        description="Zep document ID for semantic search reference"
    )
    bullets_count: int = Field(
        ..., 
        description="Number of actionable insights in summary"
    )
    concepts_count: int = Field(
        ..., 
        description="Number of key concepts identified"
    )
    
    def run(self) -> str:
        """
        Save summary record to Firestore and update video status to 'summarized'.
        
        Returns:
            JSON string with summary_doc_ref for reference tracking
        """
        # Validate required environment variables
        project_id = os.getenv("GCP_PROJECT_ID")
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        
        try:
            # Initialize Firestore client
            db = firestore.Client(project=project_id)
            
            # Verify video document exists
            video_ref = db.collection('videos').document(self.video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                raise ValueError(f"Video {self.video_id} does not exist in Firestore")
            
            # Create summary document
            summary_ref = db.collection('summaries').document(self.video_id)
            summary_data = {
                'video_id': self.video_id,
                'short_drive_id': self.short_drive_id,
                'zep_document_id': self.zep_document_id,
                'bullets_count': self.bullets_count,
                'concepts_count': self.concepts_count,
                'status': 'completed',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            summary_ref.set(summary_data)
            
            # Update video document with summary references and status change
            video_ref.update({
                'status': 'summarized',  # Change from 'transcribed' to 'summarized'
                'summary_doc_ref': f"summaries/{self.video_id}",
                'summary_drive_id': self.short_drive_id,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            result = {
                "summary_doc_ref": f"summaries/{self.video_id}",
                "video_status": "summarized",
                "video_id": self.video_id
            }
            
            return json.dumps(result)
            
        except Exception as e:
            raise RuntimeError(f"Failed to save summary record: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = SaveSummaryRecord(
        video_id="test_video_123",
        short_drive_id="drive_summary_123",
        zep_document_id="zep_doc_123",
        bullets_count=5,
        concepts_count=3
    )
    
    try:
        result = tool.run()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")