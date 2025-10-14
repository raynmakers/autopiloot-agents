"""
Transcript Ingest Flow

Coordinates chunking and ingestion across all enabled RAG sinks (OpenSearch, BigQuery, Zep).
Provides unified interface for transcript indexing with parallel sink processing.
"""

import os
import sys
from typing import Dict, List

# Add module directories to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from chunker import chunk_with_metadata
from hashing import sha256_hex
from opensearch_indexer import index_transcript_chunks
from bigquery_streamer import stream_transcript_chunks
from zep_upsert import upsert_transcript


def ingest(payload: dict) -> dict:
    """
    Ingest transcript to all enabled RAG sinks.

    Args:
        payload: Dictionary containing:
            - video_id (str): YouTube video ID
            - transcript_text (str): Full transcript text
            - channel_id (str): YouTube channel ID
            - title (str, optional): Video title
            - channel_handle (str, optional): Channel handle
            - published_at (str, optional): Publication date (ISO 8601)
            - duration_sec (int, optional): Video duration

    Returns:
        Dictionary containing:
        - status: "success", "partial", or "error"
        - chunk_count: Total chunks created
        - sinks: Dictionary of sink results (opensearch, bigquery, zep)
        - message: Human-readable status message

    Process:
        1. Load chunking configuration
        2. Chunk transcript with token-aware boundaries
        3. Generate content hashes for each chunk
        4. Prepare sink-specific payloads
        5. Send to enabled sinks in parallel (OpenSearch, BigQuery, Zep)
        6. Collect and aggregate results
        7. Return unified status

    Example:
        >>> payload = {
        ...     "video_id": "abc123",
        ...     "transcript_text": "Long transcript text...",
        ...     "channel_id": "UC123",
        ...     "title": "Video Title"
        ... }
        >>> result = ingest(payload)
        >>> result["status"]
        "success"
        >>> result["chunk_count"]
        10
        >>> result["sinks"]["opensearch"]["indexed_count"]
        10
    """
    try:
        # Import config
        from rag.config import get_chunking_config

        # Extract payload
        video_id = payload.get("video_id")
        transcript_text = payload.get("transcript_text")
        channel_id = payload.get("channel_id")

        if not video_id or not transcript_text or not channel_id:
            return {
                "status": "error",
                "message": "Missing required fields: video_id, transcript_text, channel_id"
            }

        # Get chunking configuration
        chunking_config = get_chunking_config()
        max_tokens = chunking_config["max_tokens_per_chunk"]
        overlap_tokens = chunking_config["overlap_tokens"]

        # Step 1: Chunk transcript
        chunks = chunk_with_metadata(
            text=transcript_text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            doc_id=video_id
        )

        chunk_count = len(chunks)

        # Step 2: Prepare documents for each sink
        opensearch_docs = []
        bigquery_rows = []
        zep_messages = []

        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            chunk_text = chunk["text"]
            chunk_hash = sha256_hex(chunk_text)

            # OpenSearch document
            opensearch_docs.append({
                "video_id": video_id,
                "chunk_id": chunk_id,
                "chunk_index": chunk["chunk_index"],
                "total_chunks": chunk["total_chunks"],
                "title": payload.get("title"),
                "channel_id": channel_id,
                "channel_handle": payload.get("channel_handle"),
                "published_at": payload.get("published_at"),
                "duration_sec": payload.get("duration_sec"),
                "content_sha256": chunk_hash,
                "tokens": chunk["tokens"],
                "text": chunk_text
            })

            # BigQuery row (metadata only, truncated preview)
            bigquery_rows.append({
                "video_id": video_id,
                "chunk_id": chunk_id,
                "title": payload.get("title"),
                "channel_id": channel_id,
                "published_at": payload.get("published_at"),
                "duration_sec": payload.get("duration_sec"),
                "content_sha256": chunk_hash,
                "tokens": chunk["tokens"],
                "text_snippet": chunk_text[:256] if len(chunk_text) > 256 else chunk_text
            })

            # Zep message
            zep_messages.append({
                "text": chunk_text,
                "metadata": {
                    "video_id": video_id,
                    "chunk_id": chunk_id,
                    "channel_id": channel_id,
                    "title": payload.get("title"),
                    "content_sha256": chunk_hash,
                    "tokens": chunk["tokens"]
                }
            })

        # Step 3: Send to enabled sinks
        sink_results = {}

        # OpenSearch (keyword search)
        opensearch_result = index_transcript_chunks(opensearch_docs)
        sink_results["opensearch"] = opensearch_result

        # BigQuery (SQL analytics)
        bigquery_result = stream_transcript_chunks(bigquery_rows)
        sink_results["bigquery"] = bigquery_result

        # Zep (semantic search)
        zep_results = []
        for msg in zep_messages:
            zep_result = upsert_transcript(msg["text"], msg["metadata"])
            zep_results.append(zep_result)

        # Aggregate Zep results
        zep_success = sum(1 for r in zep_results if r.get("status") == "upserted")
        zep_skipped = sum(1 for r in zep_results if r.get("status") == "skipped")
        zep_errors = sum(1 for r in zep_results if r.get("status") == "error")

        sink_results["zep"] = {
            "status": "upserted" if zep_success == len(zep_messages) else "partial" if zep_success > 0 else "error",
            "upserted_count": zep_success,
            "skipped_count": zep_skipped,
            "error_count": zep_errors,
            "message": f"Upserted {zep_success}/{len(zep_messages)} chunks to Zep"
        }

        # Step 4: Determine overall status
        any_success = any(
            result.get("status") in ["indexed", "streamed", "upserted"]
            for result in sink_results.values()
        )
        all_success = all(
            result.get("status") in ["indexed", "streamed", "upserted", "skipped"]
            for result in sink_results.values()
        )

        if all_success:
            overall_status = "success"
        elif any_success:
            overall_status = "partial"
        else:
            overall_status = "error"

        return {
            "status": overall_status,
            "video_id": video_id,
            "chunk_count": chunk_count,
            "sinks": sink_results,
            "message": f"Ingested {chunk_count} chunks to RAG sinks (status: {overall_status})"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Transcript ingest failed: {str(e)}"
        }


if __name__ == "__main__":
    print("="*80)
    print("TEST: Transcript Ingest Flow")
    print("="*80)

    # Sample payload
    sample_payload = {
        "video_id": "test_abc123",
        "transcript_text": """
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
        """ * 5,  # Repeat to create longer text
        "channel_id": "UC123",
        "title": "How to Build a Scalable SaaS Business",
        "channel_handle": "@DanMartell",
        "published_at": "2025-10-08T12:00:00Z",
        "duration_sec": 1200
    }

    print("\n1. Testing ingest():")
    result = ingest(sample_payload)
    print(f"   Status: {result['status']}")
    print(f"   Video ID: {result.get('video_id')}")
    print(f"   Chunk Count: {result.get('chunk_count')}")
    print(f"   Message: {result['message']}")

    print("\n2. Sink Results:")
    if "sinks" in result:
        for sink_name, sink_result in result["sinks"].items():
            print(f"   {sink_name}:")
            print(f"     Status: {sink_result.get('status')}")
            print(f"     Message: {sink_result.get('message')}")

    print("\n" + "="*80)
    print("✅ Test completed")
