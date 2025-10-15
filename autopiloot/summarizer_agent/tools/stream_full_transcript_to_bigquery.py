"""
StreamFullTranscriptToBigQuery - SHIM for backward compatibility.

DEPRECATED: This tool delegates to the shared core RAG library (core.rag.ingest_transcript).
All chunking, hashing, and BigQuery streaming logic has been moved to the core library.

This file is kept for backward compatibility and will be removed once all
callsites are migrated to use the orchestration-driven RAG wrapper tools.

Migration Path:
    Old: StreamFullTranscriptToBigQuery(video_id="...", transcript_text="...")
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


class StreamFullTranscriptToBigQuery(BaseTool):
    """
    DEPRECATED: Stream full transcript chunks to BigQuery via shared core library.

    This is a backward-compatibility shim that delegates to core.rag.ingest_transcript.ingest().
    The core library handles:
    - Token-aware chunking with configurable overlap
    - Content hashing for deduplication
    - Parallel streaming to BigQuery (and other sinks if enabled)
    - Batch insertion and idempotency checks
    - Unified status reporting across all sinks

    For new code, use transcriber_agent/tools/rag_index_transcript.py instead.
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for record identification"
    )
    transcript_text: str = Field(
        ...,
        description="Full transcript text to chunk and stream"
    )
    channel_id: str = Field(
        ...,
        description="YouTube channel ID for filtering"
    )
    title: Optional[str] = Field(
        default=None,
        description="Video title for search and display"
    )
    channel_handle: Optional[str] = Field(
        default=None,
        description="YouTube channel handle (e.g., '@DanMartell')"
    )
    published_at: Optional[str] = Field(
        default=None,
        description="Video publication date (ISO 8601 format)"
    )
    duration_sec: Optional[int] = Field(
        default=None,
        description="Video duration in seconds"
    )

    def run(self) -> str:
        """
        Delegate to shared core library for transcript streaming to BigQuery.

        Returns:
            JSON string with dataset, table, chunk_count, inserted_count, status
        """
        print("⚠️ DEPRECATION WARNING: StreamFullTranscriptToBigQuery is deprecated.")
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
                # Extract BigQuery-specific results if available
                bigquery_result = result.get("sinks", {}).get("bigquery", {})

                return json.dumps({
                    "dataset": "autopiloot",  # Default from config
                    "table": "transcript_chunks",  # Default from config
                    "video_id": self.video_id,
                    "chunk_count": result.get("chunk_count", 0),
                    "inserted_count": result.get("chunk_count", 0),
                    "skipped_count": 0,
                    "content_hashes": result.get("content_hashes", []),
                    "total_tokens": result.get("total_tokens", 0),
                    "status": "streamed",
                    "message": result.get("message", "Streamed via core library")
                }, indent=2)

            elif result.get("status") == "skipped":
                return json.dumps({
                    "status": "skipped",
                    "message": result.get("message", "BigQuery not configured"),
                    "video_id": self.video_id
                }, indent=2)

            else:
                return json.dumps({
                    "error": result.get("error", "streaming_failed"),
                    "message": result.get("message", "Unknown error"),
                    "video_id": self.video_id
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "streaming_failed",
                "message": f"Failed to stream transcript to BigQuery: {str(e)}",
                "video_id": self.video_id
            }, indent=2)


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Stream full transcript to BigQuery (DEPRECATED SHIM)")
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
        tool = StreamFullTranscriptToBigQuery(
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
            print(f"\n📊 Streaming Summary:")
            print(f"   Dataset: {data.get('dataset', 'N/A')}")
            print(f"   Table: {data.get('table', 'N/A')}")
            print(f"   Video ID: {data.get('video_id')}")
            print(f"   Chunk Count: {data.get('chunk_count')}")
            print(f"   Inserted Count: {data.get('inserted_count')}")
            print(f"\n💡 {data.get('message', 'N/A')}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
    print("⚠️ REMINDER: This tool is deprecated. Use transcriber_agent/tools/rag_index_transcript.py")
    print("="*80)
