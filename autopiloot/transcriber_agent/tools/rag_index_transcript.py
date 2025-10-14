"""
RAG Index Transcript Tool

Thin wrapper that indexes transcript to Hybrid RAG via core library.
Exposes indexing to Agency Swarm without duplicating RAG logic.
"""

import os
import sys
import json
from typing import Optional
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add core directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))


class RagIndexTranscript(BaseTool):
    """
    Index transcript to Hybrid RAG storage (Zep, OpenSearch, BigQuery).

    Delegates to shared core.rag.ingest_transcript module for all indexing logic.
    Validates inputs and builds payload for core library consumption.

    Architecture:
        - Thin wrapper: No RAG logic in agent tools
        - Delegates to core.rag.ingest_transcript.ingest()
        - Feature-flagged: Sinks enabled/disabled via config
        - Idempotent: Safe to retry, deduplicates by content hash

    Usage:
        This tool should be called after save_transcript_record completes.
        It ensures transcript content is indexed for semantic + keyword search.
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID (primary identifier)"
    )
    transcript_text: str = Field(
        ...,
        description="Full transcript text to index"
    )
    channel_id: str = Field(
        ...,
        description="YouTube channel ID for filtering"
    )
    title: Optional[str] = Field(
        default=None,
        description="Video title for search context"
    )
    published_at: Optional[str] = Field(
        default=None,
        description="Video publication date (ISO 8601 format)"
    )
    duration_sec: Optional[int] = Field(
        default=None,
        description="Video duration in seconds"
    )
    channel_handle: Optional[str] = Field(
        default=None,
        description="YouTube channel handle (e.g., '@DanMartell')"
    )

    def run(self) -> str:
        """
        Index transcript to Hybrid RAG storage.

        Process:
        1. Validate inputs
        2. Build payload for core library
        3. Call core.rag.ingest_transcript.ingest(payload)
        4. Return JSON string with indexing results

        Returns:
            JSON string containing:
            - status: "indexed", "partial", or "skipped"
            - sinks_used: List of sinks that indexed content
            - chunk_count: Number of chunks created
            - indexed_counts: Per-sink indexing results
            - errors: Any errors encountered (if applicable)

        Example:
            >>> tool = RagIndexTranscript(
            ...     video_id="abc123",
            ...     transcript_text="Full transcript...",
            ...     channel_id="UC123",
            ...     title="Video Title"
            ... )
            >>> result = tool.run()
            >>> data = json.loads(result)
            >>> data["status"]
            "indexed"
        """
        try:
            # Import core library function
            from rag.ingest_transcript import ingest

            # Build payload
            payload = {
                "video_id": self.video_id,
                "transcript_text": self.transcript_text,
                "channel_id": self.channel_id,
                "title": self.title,
                "published_at": self.published_at,
                "duration_sec": self.duration_sec,
                "channel_handle": self.channel_handle
            }

            # Call core library
            print(f"📥 Indexing transcript for video {self.video_id} to Hybrid RAG...")
            result = ingest(payload)

            # Log result
            if result.get("status") == "indexed":
                print(f"   ✅ Indexed {result.get('chunk_count', 0)} chunks to {len(result.get('sinks_used', []))} sinks")
            elif result.get("status") == "skipped":
                print(f"   ⚪ Indexing skipped: {result.get('message', 'All sinks disabled')}")
            else:
                print(f"   ⚠️ Indexing partial: {result.get('message', 'Some sinks failed')}")

            # Optional: Write Firestore reference for audit/discovery (best-effort, never blocks)
            if result.get("status") in ["indexed", "partial"]:
                try:
                    from rag.refs import upsert_ref

                    # Build reference document
                    ref = {
                        "type": "transcript",
                        "source_ref": self.video_id,
                        "created_by_agent": "transcriber_agent",
                        "content_hashes": result.get("content_hashes", []),
                        "chunk_count": result.get("chunk_count", 0),
                        "total_tokens": result.get("total_tokens", 0),
                        "indexing_status": result.get("status"),
                        "sink_statuses": result.get("sink_statuses", {}),
                        "indexing_duration_ms": result.get("indexing_duration_ms", 0)
                    }

                    # Add optional metadata
                    if self.title:
                        ref["title"] = self.title
                    if self.channel_id:
                        ref["channel_id"] = self.channel_id
                    if self.published_at:
                        ref["published_at"] = self.published_at

                    # Add optional sink references
                    if "opensearch_index" in result:
                        ref["opensearch_index"] = result["opensearch_index"]
                    if "bigquery_table" in result:
                        ref["bigquery_table"] = result["bigquery_table"]
                    if "zep_doc_id" in result:
                        ref["zep_doc_id"] = result["zep_doc_id"]

                    # Write reference (best-effort, never raises)
                    upsert_ref(ref)
                except Exception:
                    # Silently ignore ref write failures (best-effort only)
                    pass

            return json.dumps(result, indent=2)

        except Exception as e:
            error_result = {
                "status": "error",
                "error": "wrapper_failed",
                "message": f"RAG indexing wrapper failed: {str(e)}",
                "video_id": self.video_id
            }
            return json.dumps(error_result, indent=2)


if __name__ == "__main__":
    print("="*80)
    print("TEST: RAG Index Transcript Tool")
    print("="*80)

    # Test with sample data
    sample_transcript = """
    Welcome to this tutorial on building scalable SaaS businesses. Today we're going to talk about
    the key principles that separate successful founders from those who struggle. The first principle
    is understanding your unit economics. You need to know your customer acquisition cost, lifetime
    value, and payback period. These metrics form the foundation of your business model.
    """ * 5

    tool = RagIndexTranscript(
        video_id="test_abc123",
        transcript_text=sample_transcript,
        channel_id="UCkP5J0pXI11VE81q7S7V1Jw",
        title="How to Build a Scalable SaaS Business",
        channel_handle="@DanMartell",
        published_at="2025-10-08T12:00:00Z",
        duration_sec=1200
    )

    print("\n1. Running RAG indexing...")
    result = tool.run()

    print("\n2. Result:")
    print(result)

    # Parse and display summary
    try:
        data = json.loads(result)
        print("\n3. Summary:")
        print(f"   Status: {data.get('status')}")
        print(f"   Sinks used: {data.get('sinks_used', [])}")
        print(f"   Chunk count: {data.get('chunk_count', 0)}")
    except json.JSONDecodeError:
        print("   Failed to parse result JSON")

    print("\n" + "="*80)
    print("✅ Test completed")
