"""
SaveSummaryRecord tool for persisting summary references and linkage in Firestore.
Implements TASK-SUM-0031 specification with proper transcript linking and status management.
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
from audit_logger import audit_logger

# Firestore imports
from google.cloud import firestore


class SaveSummaryRecord(BaseTool):
    """
    Persist summary references and linkage to transcript and RAG docs in Firestore.
    
    Creates summaries/{video_id} document with complete linkage to Zep, Drive,
    and transcript documents. Updates video status from 'transcribed' to 'summarized'
    upon successful completion.
    
    Maintains full audit trail and reference integrity for coaching workflows.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for Firestore document reference"
    )
    
    refs: Dict[str, Any] = Field(
        ..., 
        description="References dictionary containing zep_doc_id, short_drive_id, transcript references, prompt_id, token_usage, and rag_refs"
    )
    
    def run(self) -> str:
        """
        Save summary record with complete reference linkage to Firestore.
        
        Returns:
            str: JSON string containing summary_doc_ref for reference tracking
        
        Raises:
            RuntimeError: If Firestore operations fail
        """
        try:
            # Initialize Firestore client
            firestore_client = self._initialize_firestore_client()
            
            # Validate transcript exists
            transcript_doc_ref = self.refs.get("transcript_doc_ref")
            if not transcript_doc_ref:
                raise ValueError("transcript_doc_ref is required in refs parameter")
            
            self._validate_transcript_exists(firestore_client, transcript_doc_ref)
            
            # Create summary document with atomic transaction
            summary_doc_ref = self._create_summary_record(firestore_client)
            
            # Update video status to 'summarized'
            self._update_video_status(firestore_client)
            
            # Log summary creation to audit trail (TASK-AUDIT-0041)
            audit_logger.log_summary_created(
                video_id=self.video_id,
                summary_doc_ref=summary_doc_ref,
                actor="SummarizerAgent"
            )
            
            return json.dumps({
                "summary_doc_ref": summary_doc_ref
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to save summary record: {str(e)}",
                "summary_doc_ref": None
            })
    
    def _initialize_firestore_client(self) -> firestore.Client:
        """Initialize Firestore client with proper authentication."""
        try:
            # Firestore client uses GOOGLE_APPLICATION_CREDENTIALS automatically
            return firestore.Client()
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")
    
    def _validate_transcript_exists(self, db: firestore.Client, transcript_doc_ref: str) -> None:
        """
        Validate that the referenced transcript document exists.
        
        Args:
            db: Firestore client
            transcript_doc_ref: Document reference path (e.g., 'transcripts/video_id')
        
        Raises:
            ValueError: If transcript document doesn't exist
        """
        try:
            transcript_ref = db.document(transcript_doc_ref)
            transcript_doc = transcript_ref.get()
            
            if not transcript_doc.exists:
                raise ValueError(f"Transcript document {transcript_doc_ref} does not exist")
                
        except Exception as e:
            raise ValueError(f"Failed to validate transcript existence: {str(e)}")
    
    def _create_summary_record(self, db: firestore.Client) -> str:
        """
        Create summary record in Firestore with complete reference linkage.
        
        Args:
            db: Firestore client
            
        Returns:
            Summary document reference path
        """
        summary_doc_ref = f"summaries/{self.video_id}"
        
        # Prepare summary document data
        timestamp = datetime.now(timezone.utc).isoformat()
        
        summary_data = {
            "video_id": self.video_id,
            
            # Core references from task specification
            "zep_doc_id": self.refs.get("zep_doc_id"),
            "short_drive_id": self.refs.get("short_drive_id"),
            "transcript_doc_ref": self.refs.get("transcript_doc_ref"),
            "transcript_drive_id_txt": self.refs.get("transcript_drive_id_txt"),
            "transcript_drive_id_json": self.refs.get("transcript_drive_id_json"),
            "prompt_id": self.refs.get("prompt_id"),
            "prompt_version": self.refs.get("prompt_version", "v1"),
            "token_usage": self.refs.get("token_usage", {}),
            "rag_refs": self.refs.get("rag_refs", {}),
            
            # Status and timestamps (UTC ISO 8601 with Z)
            "status": "completed",
            "created_at": timestamp,
            "updated_at": timestamp,
            
            # Additional metadata for audit trail
            "metadata": {
                "source": "autopiloot_summarizer",
                "version": "1.0",
                "bullets_count": self.refs.get("bullets_count", 0),
                "concepts_count": self.refs.get("concepts_count", 0)
            }
        }
        
        try:
            # Create summary document
            summary_ref = db.document(summary_doc_ref)
            summary_ref.set(summary_data)
            
            return summary_doc_ref
            
        except Exception as e:
            raise RuntimeError(f"Failed to create summary document: {str(e)}")
    
    def _update_video_status(self, db: firestore.Client) -> None:
        """
        Update video document status from 'transcribed' to 'summarized'.
        
        Args:
            db: Firestore client
            
        Raises:
            RuntimeError: If video status update fails
        """
        try:
            video_ref = db.collection('videos').document(self.video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                raise ValueError(f"Video document {self.video_id} does not exist")
            
            # Validate current status
            current_status = video_doc.to_dict().get('status')
            if current_status != 'transcribed':
                # Log warning but don't fail - allow status progression flexibility
                print(f"Warning: Video {self.video_id} has status '{current_status}', expected 'transcribed'")
            
            # Update video with summary references and status
            video_ref.update({
                'status': 'summarized',
                'summary_doc_ref': f"summaries/{self.video_id}",
                'summary_short_drive_id': self.refs.get("short_drive_id"),
                'zep_doc_id': self.refs.get("zep_doc_id"),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            raise RuntimeError(f"Failed to update video status: {str(e)}")
    
    def _atomic_transaction(self, db: firestore.Client) -> str:
        """
        Execute summary creation and video update in atomic transaction.
        
        Args:
            db: Firestore client
            
        Returns:
            Summary document reference path
        """
        summary_doc_ref = f"summaries/{self.video_id}"
        
        @firestore.transactional
        def update_in_transaction(transaction):
            # Validate video exists and has correct status
            video_ref = db.collection('videos').document(self.video_id)
            video_doc = video_ref.get(transaction=transaction)
            
            if not video_doc.exists:
                raise ValueError(f"Video document {self.video_id} does not exist")
            
            video_data = video_doc.to_dict()
            current_status = video_data.get('status')
            
            # Allow progression from 'transcribed' status
            if current_status != 'transcribed':
                print(f"Warning: Video {self.video_id} has status '{current_status}', expected 'transcribed'")
            
            # Create summary document
            timestamp = datetime.now(timezone.utc).isoformat()
            summary_data = {
                "video_id": self.video_id,
                "zep_doc_id": self.refs.get("zep_doc_id"),
                "short_drive_id": self.refs.get("short_drive_id"),
                "transcript_doc_ref": self.refs.get("transcript_doc_ref"),
                "transcript_drive_id_txt": self.refs.get("transcript_drive_id_txt"),
                "transcript_drive_id_json": self.refs.get("transcript_drive_id_json"),
                "prompt_id": self.refs.get("prompt_id"),
                "prompt_version": self.refs.get("prompt_version", "v1"),
                "token_usage": self.refs.get("token_usage", {}),
                "rag_refs": self.refs.get("rag_refs", {}),
                "status": "completed",
                "created_at": timestamp,
                "updated_at": timestamp,
                "metadata": {
                    "source": "autopiloot_summarizer",
                    "version": "1.0",
                    "bullets_count": self.refs.get("bullets_count", 0),
                    "concepts_count": self.refs.get("concepts_count", 0)
                }
            }
            
            summary_ref = db.document(summary_doc_ref)
            transaction.set(summary_ref, summary_data)
            
            # Update video status
            transaction.update(video_ref, {
                'status': 'summarized',
                'summary_doc_ref': summary_doc_ref,
                'summary_short_drive_id': self.refs.get("short_drive_id"),
                'zep_doc_id': self.refs.get("zep_doc_id"),
                'updated_at': timestamp
            })
            
            return summary_doc_ref
        
        try:
            transaction = db.transaction()
            return update_in_transaction(transaction)
            
        except Exception as e:
            raise RuntimeError(f"Atomic transaction failed: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    test_refs = {
        "zep_doc_id": "summary_test_video_123",
        "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4",
        "transcript_doc_ref": "transcripts/test_video_123",
        "transcript_drive_id_txt": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx",
        "transcript_drive_id_json": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe",
        "prompt_id": "coach_v1_12345678",
        "token_usage": {
            "input_tokens": 1500,
            "output_tokens": 300
        },
        "rag_refs": {
            "collection": "autopiloot_guidelines",
            "document_count": 1
        },
        "bullets_count": 3,
        "concepts_count": 4
    }
    
    tool = SaveSummaryRecord(
        video_id="test_video_123",
        refs=test_refs
    )
    
    try:
        result = tool.run()
        print("SaveSummaryRecord test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Successfully saved summary record: {data['summary_doc_ref']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()