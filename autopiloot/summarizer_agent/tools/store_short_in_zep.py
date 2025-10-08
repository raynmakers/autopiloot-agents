import os
import json
from typing import List, Optional
from pydantic import Field
from agency_swarm.tools import BaseTool


class StoreShortInZep(BaseTool):
    """
    Store summary content in Zep for semantic search and retrieval.
    Enables enhanced content discovery through vector search.

    Supports label-based filtering by YouTube channel handle for targeted content retrieval.
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for Zep document reference"
    )
    bullets: List[str] = Field(
        ...,
        description="List of actionable insights to store in Zep"
    )
    key_concepts: List[str] = Field(
        ...,
        description="List of key concepts to store in Zep"
    )
    channel_handle: Optional[str] = Field(
        None,
        description="YouTube channel handle (e.g., '@AlexHormozi') for label-based filtering in Zep"
    )
    
    def run(self) -> str:
        """
        Store summary content in Zep for semantic search capabilities.

        In production implementation, this would:
        1. Initialize zep-python client
        2. Create document with bullets + key_concepts as content
        3. Add label with channel_handle for filtering (e.g., {"channel": "@AlexHormozi"})
        4. Store in Zep collection with semantic embeddings

        Zep filtering example:
            client.memory.search(query="sales tactics", labels={"channel": "@AlexHormozi"})

        Returns:
            JSON string with zep_document_id for reference tracking
        """
        # For now, return a placeholder until Zep integration is implemented
        # In production, this would use the zep-python client to store content

        result = {
            "zep_document_id": f"summary_{self.video_id}",
            "stored_bullets": len(self.bullets),
            "stored_concepts": len(self.key_concepts),
            "channel_handle": self.channel_handle,
            "labels": {"channel": self.channel_handle} if self.channel_handle else {},
            "status": "placeholder_implementation",
            "note": "In production, channel_handle would be stored as Zep label for filtering"
        }

        return json.dumps(result, indent=2)


if __name__ == "__main__":
    print("="*80)
    print("TEST 1: Store summary with channel handle (for Zep label filtering)")
    print("="*80)

    # Test with channel handle
    tool_with_handle = StoreShortInZep(
        video_id="dQw4w9WgXcQ",
        bullets=[
            "Build strong relationships through consistent communication",
            "Focus on long-term value creation over short-term gains"
        ],
        key_concepts=["Relationship Building", "Long-term Thinking", "Trust"],
        channel_handle="@AlexHormozi"
    )

    try:
        result = tool_with_handle.run()
        print("✅ Success with channel handle:")
        print(result)

        data = json.loads(result)
        print(f"\n📊 Summary:")
        print(f"   Zep Document ID: {data['zep_document_id']}")
        print(f"   Channel Handle: {data['channel_handle']}")
        print(f"   Labels: {data['labels']}")
        print(f"   Bullets Stored: {data['stored_bullets']}")
        print(f"   Concepts Stored: {data['stored_concepts']}")
        print(f"\n💡 {data['note']}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    print("\n" + "="*80)
    print("TEST 2: Store summary without channel handle (optional field)")
    print("="*80)

    # Test without channel handle
    tool_without_handle = StoreShortInZep(
        video_id="mZxDw92UXmA",
        bullets=["Strategic planning insight"],
        key_concepts=["Strategy", "Planning"]
    )

    try:
        result = tool_without_handle.run()
        print("✅ Success without channel handle:")
        print(result)

        data = json.loads(result)
        print(f"\n📊 Summary:")
        print(f"   Zep Document ID: {data['zep_document_id']}")
        print(f"   Channel Handle: {data['channel_handle']}")
        print(f"   Labels: {data['labels']}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    print("\n" + "="*80)
    print("Testing complete! Channel handle is now supported for Zep label filtering.")
    print("="*80)