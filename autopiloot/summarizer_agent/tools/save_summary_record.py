import os
import json
import hashlib
from typing import List, Optional
from pydantic import Field, field_validator
from google.cloud import firestore
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool


class SaveSummaryRecord(BaseTool):
    """
    Save summary content and metadata directly to Firestore.
    Stores complete summary data (bullets, key concepts) in Firestore summaries collection.
    Updates video status from 'transcribed' to 'summarized' upon completion.
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
    zep_document_id: Optional[str] = Field(
        default=None,
        description="Zep document ID for semantic search reference"
    )

    @field_validator('video_id')
    @classmethod
    def validate_video_id(cls, v):
        """Validate YouTube video ID format."""
        if not v or len(v.strip()) == 0:
            raise ValueError("video_id cannot be empty")
        if len(v) > 50:
            raise ValueError("video_id seems too long for a valid YouTube ID")
        return v.strip()

    @field_validator('bullets')
    @classmethod
    def validate_bullets(cls, v):
        """Validate bullets list is not empty."""
        if not v or len(v) == 0:
            raise ValueError("bullets list cannot be empty")
        return v

    @field_validator('key_concepts')
    @classmethod
    def validate_key_concepts(cls, v):
        """Validate key_concepts list is not empty."""
        if not v or len(v) == 0:
            raise ValueError("key_concepts list cannot be empty")
        return v
    
    def run(self) -> str:
        """
        Save summary content and metadata to Firestore summaries collection.

        Process:
        1. Initialize Firestore client with authentication
        2. Generate summary digest for verification
        3. Create/update summary document in summaries collection
        4. Store actual summary content (bullets, key_concepts)
        5. Add metadata (timestamps, prompt_id, Zep reference)
        6. Update video document status to 'summarized'

        Returns:
            JSON string containing:
            - video_id: YouTube video ID (document ID)
            - bullets_count: Number of actionable insights
            - concepts_count: Number of key concepts
            - summary_digest: SHA-256 hash for verification
            - zep_document_id: Zep document reference (if provided)
            - stored_at: ISO timestamp of storage
            - status: "stored" on success
        """
        # Validate required environment variables
        project_id = os.getenv("GCP_PROJECT_ID")
        if not project_id:
            return json.dumps({
                "error": "configuration_error",
                "message": "GCP_PROJECT_ID environment variable is required"
            })

        try:
            # Initialize Firestore client
            db = firestore.Client(project=project_id)

            # Generate summary digest for verification (hash the bullets content)
            summary_text = "\n".join(self.bullets)
            summary_digest = hashlib.sha256(summary_text.encode('utf-8')).hexdigest()[:16]

            # Prepare summary document data
            summary_data = {
                'bullets': self.bullets,
                'key_concepts': self.key_concepts,
                'prompt_id': self.prompt_id,
                'zep_document_id': self.zep_document_id,
                'bullets_count': len(self.bullets),
                'concepts_count': len(self.key_concepts),
                'summary_digest': summary_digest,
                'status': 'completed',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            # Use batch write for atomicity
            batch = db.batch()

            # Store/update summary document (using video_id as document ID)
            summary_ref = db.collection('summaries').document(self.video_id)
            batch.set(summary_ref, summary_data)

            # Update video status to 'summarized'
            video_ref = db.collection('videos').document(self.video_id)
            batch.update(video_ref, {
                'status': 'summarized',
                'summary_doc_ref': f"summaries/{self.video_id}",
                'updated_at': firestore.SERVER_TIMESTAMP
            })

            # Commit the batch
            batch.commit()

            # Return structured result
            result = {
                "video_id": self.video_id,
                "bullets_count": len(self.bullets),
                "concepts_count": len(self.key_concepts),
                "summary_digest": summary_digest,
                "zep_document_id": self.zep_document_id,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "status": "stored"
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "storage_error",
                "message": f"Failed to save summary to Firestore: {str(e)}",
                "video_id": self.video_id
            })


if __name__ == "__main__":
    print("Testing SaveSummaryRecord tool...")
    print("="*50)

    # Test 1: Basic summary storage
    print("\nTest 1: Store summary to Firestore")
    tool = SaveSummaryRecord(
        video_id="test_video_123",
        bullets=[
            "Insight 1: Focus on fundamentals",
            "Insight 2: Build sustainable systems",
            "Insight 3: Measure what matters"
        ],
        key_concepts=["Framework A", "Methodology B", "Strategy C"],
        prompt_id="test_prompt_v1",
        zep_document_id="zep_doc_123"
    )

    try:
        result = tool.run()
        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
            print(f"   Error type: {data['error']}")
        else:
            print(f"✅ Summary stored to Firestore successfully:")
            print(f"   Video ID: {data.get('video_id', 'N/A')}")
            print(f"   Bullets count: {data.get('bullets_count', 0)}")
            print(f"   Concepts count: {data.get('concepts_count', 0)}")
            print(f"   Summary digest: {data.get('summary_digest', 'N/A')}")
            print(f"   Zep document ID: {data.get('zep_document_id', 'N/A')}")
            print(f"   Stored at: {data.get('stored_at', 'N/A')}")
    except Exception as e:
        print(f"❌ Test error: {str(e)}")

    # Test 2: Validation - empty bullets
    print("\n" + "="*50)
    print("\nTest 2: Parameter validation (empty bullets)")
    try:
        invalid_tool = SaveSummaryRecord(
            video_id="test_video_456",
            bullets=[],  # Empty list
            key_concepts=["Concept A"],
            prompt_id="test_prompt"
        )
        print("❌ Should have failed validation but didn't")
    except ValueError as e:
        print(f"✅ Validation working correctly: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

    print("\n" + "="*50)
    print("Testing complete!")
    print("\n📝 Summary: Summaries stored in Firestore summaries/ collection")
    print("   - Document ID: video_id (YouTube ID)")
    print("   - Content: bullets (list), key_concepts (list)")
    print("   - Metadata: prompt_id, zep_document_id, summary_digest")
    print("   - Also updates videos/ collection status to 'summarized'")