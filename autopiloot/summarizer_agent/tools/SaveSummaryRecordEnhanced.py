"""
SaveSummaryRecordEnhanced tool for persisting enhanced summary references with Zep and RAG linkage.
Implements TASK-ZEP-0006 specification with comprehensive reference tracking in Firestore.
"""

import os
import sys
import json
from typing import Dict, Any, List
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


class SaveSummaryRecordEnhanced(BaseTool):
    """
    Persist enhanced summary references with Zep and RAG linkage to Firestore.
    
    Extends the basic SaveSummaryRecord functionality to include zep_doc_id
    and rag_refs storage as specified in TASK-ZEP-0006. Creates summaries/{video_id} 
    document with complete linkage to Zep GraphRAG, Drive storage, transcript documents,
    and RAG reference artifacts for enhanced retrieval workflows.
    
    Maintains full audit trail and reference integrity for coaching workflows.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for Firestore document reference"
    )
    
    refs: Dict[str, Any] = Field(
        ..., 
        description="References dictionary containing all storage references including zep_doc_id and rag_refs"
    )
    
    video_metadata: Dict[str, Any] = Field(
        ...,
        description="Complete video metadata for enhanced reference tracking"
    )
    
    def run(self) -> str:
        """
        Save enhanced summary record with comprehensive reference linkage to Firestore.
        
        Returns:
            str: JSON string containing summary_doc_ref and zep integration status
        
        Raises:
            RuntimeError: If Firestore operations fail
        """
        try:
            # Initialize Firestore client
            firestore_client = self._initialize_firestore_client()
            
            # Validate required references
            self._validate_required_references()
            
            # Validate transcript exists
            transcript_doc_ref = self.refs.get("transcript_doc_ref")
            self._validate_transcript_exists(firestore_client, transcript_doc_ref)
            
            # Create enhanced summary document with atomic transaction
            summary_doc_ref = self._create_enhanced_summary_record(firestore_client)
            
            # Update video status to 'summarized' with Zep references
            self._update_video_status_with_zep(firestore_client)
            
            # Log enhanced summary creation to audit trail (TASK-AUDIT-0041)
            audit_logger.log_summary_created(
                video_id=self.video_id,
                summary_doc_ref=summary_doc_ref,
                actor="SummarizerAgent"
            )
            
            return json.dumps({
                "summary_doc_ref": summary_doc_ref,
                "zep_doc_id": self.refs.get("zep_doc_id"),
                "rag_refs_count": len(self.refs.get("rag_refs", [])),
                "status": "completed"
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to save enhanced summary record: {str(e)}",
                "summary_doc_ref": None,
                "zep_doc_id": None
            })
    
    def _initialize_firestore_client(self) -> firestore.Client:
        """Initialize Firestore client with proper authentication."""
        try:
            # Firestore client uses GOOGLE_APPLICATION_CREDENTIALS automatically
            return firestore.Client()
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")
    
    def _validate_required_references(self) -> None:
        """
        Validate that all required references are present.
        
        Raises:
            ValueError: If required references are missing
        """
        required_refs = ["transcript_doc_ref", "zep_doc_id"]
        
        for ref in required_refs:
            if not self.refs.get(ref):
                raise ValueError(f"{ref} is required in refs parameter for enhanced summary record")
    
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
    
    def _create_enhanced_summary_record(self, db: firestore.Client) -> str:
        """
        Create enhanced summary record in Firestore with comprehensive reference linkage.
        
        Args:
            db: Firestore client
            
        Returns:
            Summary document reference path
        """
        summary_doc_ref = f"summaries/{self.video_id}"
        
        # Prepare enhanced summary document data
        timestamp = datetime.now(timezone.utc).isoformat()
        
        summary_data = {
            "video_id": self.video_id,
            
            # Core references from original specification
            "transcript_doc_ref": self.refs.get("transcript_doc_ref"),
            "transcript_drive_id_txt": self.refs.get("transcript_drive_id_txt"),
            "transcript_drive_id_json": self.refs.get("transcript_drive_id_json"),
            "short_drive_id": self.refs.get("short_drive_id"),
            "prompt_id": self.refs.get("prompt_id"),
            "prompt_version": self.refs.get("prompt_version", "v1"),
            "token_usage": self.refs.get("token_usage", {}),
            
            # Enhanced Zep GraphRAG references (TASK-ZEP-0006)
            "zep_doc_id": self.refs.get("zep_doc_id"),
            "zep_collection": self.refs.get("zep_collection", "autopiloot_guidelines"),
            "rag_refs": self.refs.get("rag_refs", []),
            
            # Video metadata for enhanced context
            "title": self.video_metadata.get("title", ""),
            "published_at": self.video_metadata.get("published_at", ""),
            "channel_id": self.video_metadata.get("channel_id", ""),
            "tags": self.refs.get("tags", []),
            
            # Status and timestamps (UTC ISO 8601 with Z)
            "status": "completed",
            "created_at": timestamp,
            "updated_at": timestamp,
            
            # Enhanced metadata for audit trail
            "metadata": {
                "source": "autopiloot_summarizer",
                "version": "2.0",  # Enhanced version
                "bullets_count": self.refs.get("bullets_count", 0),
                "concepts_count": self.refs.get("concepts_count", 0),
                "rag_refs_count": len(self.refs.get("rag_refs", [])),
                "zep_integration": "enabled"
            }
        }
        
        try:
            # Create enhanced summary document
            summary_ref = db.document(summary_doc_ref)
            summary_ref.set(summary_data)
            
            return summary_doc_ref
            
        except Exception as e:
            raise RuntimeError(f"Failed to create enhanced summary document: {str(e)}")
    
    def _update_video_status_with_zep(self, db: firestore.Client) -> None:
        """
        Update video document status with Zep GraphRAG references.
        
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
            
            # Update video with enhanced summary references and Zep linkage
            video_update_data = {
                'status': 'summarized',
                'summary_doc_ref': f"summaries/{self.video_id}",
                'summary_short_drive_id': self.refs.get("short_drive_id"),
                'zep_doc_id': self.refs.get("zep_doc_id"),
                'zep_collection': self.refs.get("zep_collection", "autopiloot_guidelines"),
                'rag_refs': self.refs.get("rag_refs", []),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            video_ref.update(video_update_data)
            
        except Exception as e:
            raise RuntimeError(f"Failed to update video status with Zep references: {str(e)}")
    
    def _atomic_transaction_enhanced(self, db: firestore.Client) -> str:
        """
        Execute enhanced summary creation and video update in atomic transaction.
        
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
            
            # Create enhanced summary document
            timestamp = datetime.now(timezone.utc).isoformat()
            summary_data = {
                "video_id": self.video_id,
                "transcript_doc_ref": self.refs.get("transcript_doc_ref"),
                "transcript_drive_id_txt": self.refs.get("transcript_drive_id_txt"),
                "transcript_drive_id_json": self.refs.get("transcript_drive_id_json"),
                "short_drive_id": self.refs.get("short_drive_id"),
                "prompt_id": self.refs.get("prompt_id"),
                "prompt_version": self.refs.get("prompt_version", "v1"),
                "token_usage": self.refs.get("token_usage", {}),
                
                # Enhanced Zep references
                "zep_doc_id": self.refs.get("zep_doc_id"),
                "zep_collection": self.refs.get("zep_collection", "autopiloot_guidelines"),
                "rag_refs": self.refs.get("rag_refs", []),
                
                # Video metadata
                "title": self.video_metadata.get("title", ""),
                "published_at": self.video_metadata.get("published_at", ""),
                "channel_id": self.video_metadata.get("channel_id", ""),
                "tags": self.refs.get("tags", []),
                
                "status": "completed",
                "created_at": timestamp,
                "updated_at": timestamp,
                "metadata": {
                    "source": "autopiloot_summarizer",
                    "version": "2.0",
                    "bullets_count": self.refs.get("bullets_count", 0),
                    "concepts_count": self.refs.get("concepts_count", 0),
                    "rag_refs_count": len(self.refs.get("rag_refs", [])),
                    "zep_integration": "enabled"
                }
            }
            
            summary_ref = db.document(summary_doc_ref)
            transaction.set(summary_ref, summary_data)
            
            # Update video status with Zep references
            transaction.update(video_ref, {
                'status': 'summarized',
                'summary_doc_ref': summary_doc_ref,
                'summary_short_drive_id': self.refs.get("short_drive_id"),
                'zep_doc_id': self.refs.get("zep_doc_id"),
                'zep_collection': self.refs.get("zep_collection", "autopiloot_guidelines"),
                'rag_refs': self.refs.get("rag_refs", []),
                'updated_at': timestamp
            })
            
            return summary_doc_ref
        
        try:
            transaction = db.transaction()
            return update_in_transaction(transaction)
            
        except Exception as e:
            raise RuntimeError(f"Enhanced atomic transaction failed: {str(e)}")


if __name__ == "__main__":
    # Test the enhanced tool
    test_refs = {
        "zep_doc_id": "summary_test_video_123",
        "zep_collection": "autopiloot_guidelines",
        "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4",
        "transcript_doc_ref": "transcripts/test_video_123",
        "transcript_drive_id_txt": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx",
        "transcript_drive_id_json": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe",
        "prompt_id": "coach_v1_12345678",
        "token_usage": {
            "input_tokens": 1500,
            "output_tokens": 300
        },
        "rag_refs": [
            {
                "type": "transcript_drive",
                "ref": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx"
            },
            {
                "type": "logic_doc",
                "ref": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe"
            }
        ],
        "tags": ["coaching", "business", "automation"],
        "bullets_count": 3,
        "concepts_count": 4
    }
    
    test_video_metadata = {
        "title": "How to Scale Your Business Without Burnout",
        "published_at": "2023-09-15T10:30:00Z",
        "channel_id": "UC1234567890"
    }
    
    tool = SaveSummaryRecordEnhanced(
        video_id="test_video_123",
        refs=test_refs,
        video_metadata=test_video_metadata
    )
    
    try:
        result = tool.run()
        print("SaveSummaryRecordEnhanced test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Successfully saved enhanced summary record: {data['summary_doc_ref']}")
            print(f"Zep Document ID: {data['zep_doc_id']}")
            print(f"RAG References: {data['rag_refs_count']} items")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()