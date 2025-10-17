"""
UpsertFullTranscriptToZep - SHIM for backward compatibility.

DEPRECATED: This tool delegates to the shared core RAG library (core.rag.ingest_transcript).
All chunking, hashing, and Zep v3 upsertion logic has been moved to the core library.

This file is kept for backward compatibility and will be removed once all
callsites are migrated to use the orchestration-driven RAG wrapper tools.

Migration Path:
    Old: UpsertFullTranscriptToZep(video_id="...", transcript_text="...")
    New: RagIndexTranscript(video_id="...", text="...")  # In transcriber_agent

Deprecation Notice:
    This tool is deprecated as of 2025-10-14. Please migrate to the transcriber_agent
    wrapper tool (rag_index_transcript.py) which calls the shared core library.
"""

import os
import sys
import json
from typing import Optional
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add parent directory to path for imports
from core.rag.ingest_transcript import ingest


class UpsertFullTranscriptToZep(BaseTool):
    """
    DEPRECATED: Store full transcript in Zep v3 via shared core library.

    This is a backward-compatibility shim that delegates to core.rag.ingest_transcript.ingest().
    The core library handles:
    - Token-aware chunking with configurable overlap
    - SHA-256 content hashing for idempotency
    - Parallel upsertion to Zep (and other sinks if enabled)
    - Automatic knowledge graph building in Zep
    - Unified status reporting across all sinks

    For new code, use transcriber_agent/tools/rag_index_transcript.py instead.
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for Zep thread reference"
    )
    transcript_text: str = Field(
        ...,
        description="Full transcript text to store and chunk"
    )
    channel_id: str = Field(
        ...,
        description="YouTube channel ID (e.g., 'UC1234567890') for group organization"
    )
    title: Optional[str] = Field(
        default=None,
        description="Video title for metadata"
    )
    channel_handle: Optional[str] = Field(
        default=None,
        description="YouTube channel handle (e.g., '@DanMartell') for metadata"
    )
    published_at: Optional[str] = Field(
        default=None,
        description="Video publication date (ISO 8601 format)"
    )
    duration_sec: Optional[int] = Field(
        default=None,
        description="Video duration in seconds"
    )
    firestore_doc_ref: Optional[str] = Field(
        default=None,
        description="Firestore document reference path (transcripts/{video_id})"
    )

    def run(self) -> str:
        """
        Delegate to shared core library for transcript storage in Zep.

        Returns:
            JSON string with thread_id, chunk_count, storage status
        """
        print("⚠️ DEPRECATION WARNING: UpsertFullTranscriptToZep is deprecated.")
        print("   Use transcriber_agent/tools/rag_index_transcript.py instead.")
        print("   This shim will be removed in a future release.")
        print()

        try:
            # Build payload for core library
            payload = {
                "video_id": self.video_id,
                "transcript_text": self.transcript_text,
                "channel_id": self.channel_id
            }

            # Add optional fields if provided
            if self.title:
                payload["title"] = self.title
            if self.channel_handle:
                payload["channel_handle"] = self.channel_handle
            if self.published_at:
                payload["published_at"] = self.published_at
            if self.duration_sec:
                payload["duration_sec"] = self.duration_sec

            # Delegate to core library
            print(f"📤 Delegating to core.rag.ingest_transcript...")
            result = ingest(payload)

            # Transform result to match legacy format
            if result.get("status") == "success":
                # Extract Zep-specific results if available
                zep_result = result.get("sinks", {}).get("zep", {})

                # Construct thread ID from video ID (matching legacy format)
                thread_id = f"transcript_{self.video_id}"
                group = f"youtube_transcripts_{self.channel_id}"

                return json.dumps({
                    "thread_id": thread_id,
                    "group": group,
                    "chunk_count": result.get("chunk_count", 0),
                    "message_uuids": [],  # Core library doesn't expose individual message UUIDs
                    "total_tokens": result.get("total_tokens", 0),
                    "content_hashes": result.get("content_hashes", []),
                    "channel_handle": self.channel_handle,
                    "status": "stored",
                    "message": result.get("message", "Stored via core library")
                }, indent=2)

            elif result.get("status") == "skipped":
                return json.dumps({
                    "status": "skipped",
                    "message": result.get("message", "Zep not configured"),
                    "video_id": self.video_id
                }, indent=2)

            else:
                return json.dumps({
                    "error": result.get("error", "storage_failed"),
                    "message": result.get("message", "Unknown error"),
                    "video_id": self.video_id
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "storage_failed",
                "message": f"Failed to store transcript in Zep: {str(e)}",
                "video_id": self.video_id
            }, indent=2)


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Store full transcript in Zep v3 (DEPRECATED SHIM)")
    print("="*80)

    # Sample transcript (short for testing)
    sample_transcript = """
    Welcome to this tutorial on building scalable SaaS businesses. Today we're going to talk about
    the key principles that separate successful founders from those who struggle. The first principle
    is understanding your unit economics. You need to know your customer acquisition cost, lifetime
    value, and payback period. These metrics form the foundation of your business model.

    The second principle is hiring A-players. Many founders make the mistake of hiring too quickly
    or settling for B-players because they're desperate to fill a role. This is a critical error.
    A-players attract other A-players, and they're 10x more productive than average employees.

    The third principle is building systems and processes before you need them. Document everything
    as you go. Create playbooks for every key function in your business. This allows you to scale
    without chaos and ensures quality as you grow.
    """ * 10  # Repeat to create longer text for chunking

    try:
        tool = UpsertFullTranscriptToZep(
            video_id="test_mZxDw92UXmA",
            transcript_text=sample_transcript,
            channel_id="UCkP5J0pXI11VE81q7S7V1Jw",
            title="How to Build a Scalable SaaS Business",
            channel_handle="@DanMartell",
            published_at="2025-10-08T12:00:00Z",
            duration_sec=1200
        )

        result = tool.run()
        print("✅ Test completed:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
        elif data.get("status") == "skipped":
            print(f"\n⚪ {data['message']}")
        else:
            print(f"\n📊 Storage Summary:")
            print(f"   Thread ID: {data.get('thread_id', 'N/A')}")
            print(f"   Group: {data.get('group', 'N/A')}")
            print(f"   Chunk Count: {data.get('chunk_count')}")
            print(f"   Total Tokens: {data.get('total_tokens')}")
            print(f"\n💡 {data.get('message', 'N/A')}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
    print("⚠️ REMINDER: This tool is deprecated. Use transcriber_agent/tools/rag_index_transcript.py")
    print("="*80)
