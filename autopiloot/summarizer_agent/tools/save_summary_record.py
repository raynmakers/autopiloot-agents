import os
import sys
import json
import hashlib
from typing import List, Optional, Dict
from pydantic import Field, field_validator
from google.cloud import firestore
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool

# Add config directory to path
from config.env_loader import get_required_env_var


class SaveSummaryRecord(BaseTool):
    """
    Save summary content and metadata directly to Firestore.

    Stores complete summary data (bullets, key concepts, concept explanations) in Firestore summaries collection.
    Updates video status from 'transcribed' to 'summarized' upon completion.

    Zep v3 Integration:
    - Stores Zep v3 thread_id reference (via zep_document_id field)
    - Optionally stores user_id (channel) and message_uuids for full Zep v3 linkage
    - Zep v3 Architecture: Users = channels, Threads = videos, Messages = summaries

    Concept Explanations:
    - Each concept includes HOW it works (mechanics, implementation steps)
    - WHEN to use it (scenarios, business context)
    - WHY it's effective (underlying principles, real-world application)
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
    concept_explanations: List[Dict[str, str]] = Field(
        ...,
        description="Detailed explanations for each concept (array of {concept, explanation} objects)"
    )
    prompt_id: str = Field(
        ...,
        description="Unique identifier for the prompt used in generation"
    )
    zep_document_id: Optional[str] = Field(
        default=None,
        description="Zep v3 thread ID for semantic search reference (e.g., 'summary_VIDEO_ID')"
    )
    zep_user_id: Optional[str] = Field(
        default=None,
        description="Zep v3 user ID (channel name, e.g., 'danmartell' from '@DanMartell')"
    )
    zep_message_uuids: Optional[List[str]] = Field(
        default=None,
        description="Zep v3 message UUIDs from thread storage"
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
        try:
            project_id = get_required_env_var("GCP_PROJECT_ID", "GCP project ID for summary storage")
        except EnvironmentError as e:
            return json.dumps({
                "error": "configuration_error",
                "message": str(e)
            })

        try:
            # Initialize Firestore client
            db = firestore.Client(project=project_id)

            # Generate summary digest for verification (hash the bullets content)
            summary_text = "\n".join(self.bullets)
            summary_digest = hashlib.sha256(summary_text.encode('utf-8')).hexdigest()[:16]

            # Prepare summary document data
            summary_data = {
                # Core summary content
                'bullets': self.bullets,
                'key_concepts': self.key_concepts,
                'concept_explanations': self.concept_explanations,
                'bullets_count': len(self.bullets),
                'concepts_count': len(self.key_concepts),
                'summary_digest': summary_digest,

                # Prompt and generation metadata
                'prompt_id': self.prompt_id,

                # Zep v3 references for semantic search and retrieval
                'zep_thread_id': self.zep_document_id,  # Zep v3 thread ID (e.g., "summary_VIDEO_ID")
                'zep_user_id': self.zep_user_id,  # Zep v3 user ID (channel, e.g., "danmartell")
                'zep_message_uuids': self.zep_message_uuids or [],  # Zep v3 message UUIDs

                # Legacy field for backward compatibility
                'zep_document_id': self.zep_document_id,

                # Status and timestamps
                'status': 'completed',
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            # Use batch write for atomicity
            batch = db.batch()

            # Store/update summary document (using video_id as document ID)
            summary_ref = db.collection('summaries').document(self.video_id)
            batch.set(summary_ref, summary_data)

            # Update video status to 'summarized' with Zep v3 references
            video_ref = db.collection('videos').document(self.video_id)
            video_update = {
                'status': 'summarized',
                'summary_doc_ref': f"summaries/{self.video_id}",
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            # Add Zep v3 references to video document if available
            if self.zep_document_id:
                video_update['zep_thread_id'] = self.zep_document_id
            if self.zep_user_id:
                video_update['zep_user_id'] = self.zep_user_id
            if self.zep_message_uuids:
                video_update['zep_message_uuids'] = self.zep_message_uuids

            batch.update(video_ref, video_update)

            # Commit the batch
            batch.commit()

            # Return structured result with Zep v3 references
            result = {
                "video_id": self.video_id,
                "bullets_count": len(self.bullets),
                "concepts_count": len(self.key_concepts),
                "summary_digest": summary_digest,

                # Zep v3 references
                "zep_thread_id": self.zep_document_id,
                "zep_user_id": self.zep_user_id,
                "zep_message_uuids": self.zep_message_uuids or [],

                # Legacy field for backward compatibility
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

    # Test 1: Store Dan Martell summary to Firestore with Zep v3 references
    print("\nTest 1: Store Dan Martell summary to Firestore (Zep v3 integration)")
    tool = SaveSummaryRecord(
        video_id="mZxDw92UXmA",
        bullets=[
            "Focus on hiring A-players who can scale with your business, not just fill immediate gaps",
            "Use the 'Buyback Principle': calculate your hourly rate and systematically buy back your time by delegating tasks below that rate",
            "Implement the 1-3-1 framework: 1 priority for the year, 3 priorities for the quarter, 1 priority for the week",
            "Build systems and processes before you think you need them - document everything as you go",
            "Track your time in 15-minute increments for one week to identify where you're wasting energy on low-value tasks"
        ],
        key_concepts=[
            "Buyback Principle",
            "A-Player Hiring Framework",
            "1-3-1 Priority System",
            "Time Audit Methodology",
            "Systems Documentation",
            "Energy Management"
        ],
        concept_explanations=[
            {
                "concept": "Buyback Principle",
                "explanation": "HOW: Calculate your effective hourly rate (annual income ÷ 2000 hours). Identify tasks taking your time below this rate. Hire or delegate those tasks. WHEN: Use when you're overwhelmed, working 60+ hours/week, or stuck doing tasks worth less than your hourly rate. Most effective for entrepreneurs earning $100k+ who are still doing $20/hr tasks. WHY: Frees your time for high-leverage activities (strategy, sales, partnerships) that only you can do. Creates compound growth by focusing energy on revenue-generating work."
            },
            {
                "concept": "1-3-1 Priority System",
                "explanation": "HOW: Define 1 major goal for the year, break it into 3 quarterly priorities, then focus on 1 weekly priority that moves the needle. Review and adjust quarterly. WHEN: Use during strategic planning, when feeling scattered, or when team lacks focus. Essential for fast-growing companies with multiple opportunities. WHY: Prevents shiny object syndrome and ensures alignment across organization. Forces brutal prioritization, saying no to good ideas to focus on great ones."
            },
            {
                "concept": "A-Player Hiring Framework",
                "explanation": "HOW: Define role outcomes (not tasks), hire for trajectory (can they 10x with you?), use scorecards with clear metrics, conduct structured interviews testing problem-solving. WHEN: Use when scaling beyond 10 employees, entering new markets, or replacing underperformers. Critical during growth phases (Series A onwards). WHY: A-players attract other A-players, creating performance culture. They solve problems independently, require less management, and scale with the business rather than becoming bottlenecks."
            }
        ],
        prompt_id="coach_v1_20251008",
        zep_document_id="summary_mZxDw92UXmA",  # Zep v3 thread_id
        zep_user_id="danmartell",  # Zep v3 user_id (channel)
        zep_message_uuids=["9e75383f-de38-450e-946a-77f25f8a5580"]  # Zep v3 message UUIDs
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
            print(f"\n   📊 Zep v3 References:")
            print(f"   Thread ID: {data.get('zep_thread_id', 'N/A')}")
            print(f"   User ID: {data.get('zep_user_id', 'N/A')}")
            print(f"   Message UUIDs: {len(data.get('zep_message_uuids', []))} messages")
            print(f"   \n   Stored at: {data.get('stored_at', 'N/A')}")
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
    print("\n📝 Summary: Summaries stored in Firestore summaries/ collection with Zep v3 integration")
    print("   - Document ID: video_id (YouTube ID)")
    print("   - Content: bullets (list), key_concepts (list)")
    print("   - Metadata: prompt_id, summary_digest, timestamps")
    print("   - Zep v3 References: thread_id, user_id, message_uuids")
    print("   - Also updates videos/ collection status to 'summarized' with Zep v3 refs")
    print("   \n   Architecture: Users = channels, Threads = videos, Messages = summaries")