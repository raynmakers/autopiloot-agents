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
    document with complete linkage to Zep GraphRAG, transcript documents (stored in Firestore),
    and RAG reference artifacts for enhanced retrieval workflows.

    NOTE: Drive storage is NOT used. All data (transcripts, summaries, metadata) stored in Firestore.
    Summaries are additionally indexed in Zep for semantic search.

    Maintains full audit trail and reference integrity for coaching workflows.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for Firestore document reference"
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

    refs: Dict[str, Any] = Field(
        ...,
        description="References dictionary containing storage references including zep_doc_id and rag_refs"
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

            # Actual summary content
            "bullets": self.bullets,
            "key_concepts": self.key_concepts,
            "bullets_count": len(self.bullets),
            "concepts_count": len(self.key_concepts),

            # Core references from original specification
            "transcript_doc_ref": self.refs.get("transcript_doc_ref"),
            "prompt_id": self.prompt_id,
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

                # Actual summary content
                "bullets": self.bullets,
                "key_concepts": self.key_concepts,
                "bullets_count": len(self.bullets),
                "concepts_count": len(self.key_concepts),

                # References
                "transcript_doc_ref": self.refs.get("transcript_doc_ref"),
                "prompt_id": self.prompt_id,
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
    test_bullets = [
        "Focus on high-leverage activities that drive 80% of results",
        "Build systems and processes to eliminate repetitive decisions",
        "Delegate non-core tasks to preserve energy for strategic work"
    ]

    test_key_concepts = [
        "80/20 Principle",
        "Systems Thinking",
        "Strategic Delegation",
        "Energy Management"
    ]

    test_refs = {
        "zep_doc_id": "summary_test_video_123",
        "zep_collection": "autopiloot_guidelines",
        "transcript_doc_ref": "transcripts/test_video_123",
        "token_usage": {
            "input_tokens": 1500,
            "output_tokens": 300
        },
        "rag_refs": [
            {
                "type": "transcript_firestore",
                "ref": "transcripts/test_video_123"
            },
            {
                "type": "zep_doc",
                "ref": "summary_test_video_123"
            }
        ],
        "tags": ["coaching", "business", "automation"]
    }

    test_video_metadata = {
        "title": "How to Scale Your Business Without Burnout",
        "published_at": "2023-09-15T10:30:00Z",
        "channel_id": "UC1234567890"
    }

    tool = SaveSummaryRecordEnhanced(
        video_id="test_video_123",
        bullets=test_bullets,
        key_concepts=test_key_concepts,
        prompt_id="coach_v1_12345678",
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