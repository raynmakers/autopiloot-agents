"""
OpenSearch Indexer Module

Provides BM25 keyword indexing for Hybrid RAG.
Handles idempotent document indexing with automatic index creation.
"""

import os
import sys
from typing import List, Dict, Optional
from datetime import datetime

# Add config and core directories to path
from env_loader import get_optional_env_var


def index_transcript_chunks(docs: List[dict]) -> dict:
    """
    Index transcript chunks to OpenSearch with idempotent behavior.

    Args:
        docs: List of documents to index, each containing:
            - video_id (str): YouTube video ID
            - chunk_id (str): Unique chunk identifier
            - chunk_index (int): Chunk position (0-based)
            - total_chunks (int): Total chunks for this video
            - title (str): Video title
            - channel_id (str): YouTube channel ID
            - channel_handle (str, optional): Channel handle
            - published_at (str, optional): Publication date (ISO 8601)
            - duration_sec (int, optional): Video duration
            - content_sha256 (str): Content hash for deduplication
            - tokens (int): Token count
            - text (str): Full chunk text

    Returns:
        Dictionary containing:
        - status: "indexed", "skipped", or "error"
        - indexed_count: Number of documents indexed
        - skipped_count: Number of documents skipped (already exist)
        - error_count: Number of errors
        - errors: List of error details (if any)
        - index_name: OpenSearch index name
        - message: Human-readable status message

    Feature Flags:
        - rag.opensearch.enabled: Enable/disable OpenSearch indexing
        - Returns {"status": "skipped"} if disabled or misconfigured

    Idempotency:
        - Uses document ID = chunk_id for idempotent indexing
        - Duplicate chunk_ids will update existing documents

    Index Management:
        - Creates index automatically if missing
        - Uses proper mappings for efficient search:
          - video_id, chunk_id, channel_id: keyword (exact match)
          - title, text: text (full-text search with BM25)
          - published_at: date (range queries)
          - tokens, duration_sec: integer (numeric filters)

    Example:
        >>> docs = [
        ...     {
        ...         "video_id": "abc123",
        ...         "chunk_id": "abc123_chunk_0",
        ...         "text": "Transcript chunk text...",
        ...         "content_sha256": "hash...",
        ...         "tokens": 487,
        ...         # ... other fields
        ...     }
        ... ]
        >>> result = index_transcript_chunks(docs)
        >>> result["status"]
        "indexed"
        >>> result["indexed_count"]
        1
    """
    try:
        # Import config here to avoid circular imports
        from rag.config import is_sink_enabled, get_rag_value

        # Check if OpenSearch is enabled
        if not is_sink_enabled("opensearch"):
            return {
                "status": "skipped",
                "message": "OpenSearch sink is disabled in configuration",
                "indexed_count": 0,
                "skipped_count": len(docs)
            }

        # Get OpenSearch credentials
        host = get_optional_env_var("OPENSEARCH_HOST")
        if not host:
            return {
                "status": "skipped",
                "message": "OpenSearch not configured (OPENSEARCH_HOST not set)",
                "indexed_count": 0,
                "skipped_count": len(docs)
            }

        api_key = get_optional_env_var("OPENSEARCH_API_KEY")
        username = get_optional_env_var("OPENSEARCH_USERNAME")
        password = get_optional_env_var("OPENSEARCH_PASSWORD")

        # Validate authentication
        if not api_key and not (username and password):
            return {
                "status": "error",
                "message": "OpenSearch host configured but no authentication provided",
                "indexed_count": 0,
                "error_count": len(docs)
            }

        # Get index configuration
        index_name = get_rag_value("opensearch.index_transcripts", "autopiloot_transcripts")

        # Initialize OpenSearch client
        client = _initialize_client(host, api_key, username, password)

        # Ensure index exists with proper mappings
        index_result = _ensure_index_exists(client, index_name)
        if not index_result["success"]:
            return {
                "status": "error",
                "message": f"Failed to create index: {index_result['error']}",
                "indexed_count": 0,
                "error_count": len(docs)
            }

        # Index documents
        indexed_count = 0
        errors = []

        for doc in docs:
            # Extract doc ID
            doc_id = doc.get("chunk_id")
            if not doc_id:
                errors.append({
                    "error": "missing_chunk_id",
                    "doc": doc.get("video_id", "unknown")
                })
                continue

            # Prepare document for indexing
            index_doc = {
                "video_id": doc.get("video_id"),
                "chunk_id": doc_id,
                "chunk_index": doc.get("chunk_index"),
                "total_chunks": doc.get("total_chunks"),
                "title": doc.get("title"),
                "channel_id": doc.get("channel_id"),
                "channel_handle": doc.get("channel_handle"),
                "published_at": doc.get("published_at"),
                "duration_sec": doc.get("duration_sec"),
                "content_sha256": doc.get("content_sha256"),
                "tokens": doc.get("tokens"),
                "text": doc.get("text"),
                "indexed_at": datetime.utcnow().isoformat() + "Z"
            }

            # Index document
            result = _index_document(client, index_name, doc_id, index_doc)
            if result["success"]:
                indexed_count += 1
            else:
                errors.append({
                    "chunk_id": doc_id,
                    "error": result["error"]
                })

        # Build response
        return {
            "status": "indexed" if indexed_count > 0 else "error",
            "index_name": index_name,
            "indexed_count": indexed_count,
            "error_count": len(errors),
            "errors": errors if errors else None,
            "message": f"Indexed {indexed_count}/{len(docs)} chunks to OpenSearch"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"OpenSearch indexing failed: {str(e)}",
            "indexed_count": 0,
            "error_count": len(docs) if docs else 0
        }


def _initialize_client(host: str, api_key: Optional[str], username: Optional[str], password: Optional[str]):
    """Initialize OpenSearch client with authentication."""
    from opensearchpy import OpenSearch
    from rag.config import get_rag_value

    # Parse host
    if host.startswith("http://") or host.startswith("https://"):
        use_ssl = host.startswith("https://")
        host_without_protocol = host.replace("https://", "").replace("http://", "")
    else:
        use_ssl = True
        host_without_protocol = host

    # Split host and port
    if ":" in host_without_protocol:
        hostname, port = host_without_protocol.rsplit(":", 1)
        port = int(port)
    else:
        hostname = host_without_protocol
        port = 443 if use_ssl else 9200

    # Configure authentication
    if api_key:
        auth = ("api_key", api_key)
    elif username and password:
        auth = (username, password)
    else:
        auth = None

    # Create client
    client = OpenSearch(
        hosts=[{"host": hostname, "port": port}],
        http_auth=auth,
        use_ssl=use_ssl,
        verify_certs=get_rag_value("opensearch.connection.verify_certs", True),
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        timeout=get_rag_value("opensearch.timeout_ms", 1500) / 1000.0,
        max_retries=get_rag_value("opensearch.connection.max_retries", 3),
        retry_on_timeout=get_rag_value("opensearch.connection.retry_on_timeout", True)
    )

    return client


def _ensure_index_exists(client, index_name: str) -> dict:
    """Create index if not exists with proper mappings."""
    try:
        # Check if index exists
        if client.indices.exists(index=index_name):
            return {"success": True, "status": "exists"}

        # Create index with mappings
        mappings = {
            "mappings": {
                "properties": {
                    "video_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "total_chunks": {"type": "integer"},
                    "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "channel_id": {"type": "keyword"},
                    "channel_handle": {"type": "keyword"},
                    "published_at": {"type": "date"},
                    "duration_sec": {"type": "integer"},
                    "content_sha256": {"type": "keyword"},
                    "tokens": {"type": "integer"},
                    "text": {"type": "text"},
                    "indexed_at": {"type": "date"}
                }
            }
        }

        client.indices.create(index=index_name, body=mappings)
        return {"success": True, "status": "created"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _index_document(client, index_name: str, doc_id: str, doc: dict) -> dict:
    """Index individual document to OpenSearch."""
    try:
        response = client.index(
            index=index_name,
            id=doc_id,
            body=doc,
            refresh=False  # Don't force refresh for performance
        )

        return {"success": True, "result": response.get("result")}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("="*80)
    print("TEST: OpenSearch Indexer Module")
    print("="*80)

    # Sample documents
    sample_docs = [
        {
            "video_id": "abc123",
            "chunk_id": "abc123_chunk_0",
            "chunk_index": 0,
            "total_chunks": 3,
            "title": "How to Build a SaaS Business",
            "channel_id": "UC123",
            "channel_handle": "@DanMartell",
            "published_at": "2025-10-08T12:00:00Z",
            "duration_sec": 1200,
            "content_sha256": "hash123",
            "tokens": 487,
            "text": "This is the first chunk of the transcript..."
        },
        {
            "video_id": "abc123",
            "chunk_id": "abc123_chunk_1",
            "chunk_index": 1,
            "total_chunks": 3,
            "title": "How to Build a SaaS Business",
            "channel_id": "UC123",
            "channel_handle": "@DanMartell",
            "published_at": "2025-10-08T12:00:00Z",
            "duration_sec": 1200,
            "content_sha256": "hash456",
            "tokens": 512,
            "text": "This is the second chunk of the transcript..."
        }
    ]

    print("\n1. Testing index_transcript_chunks():")
    result = index_transcript_chunks(sample_docs)
    print(f"   Status: {result['status']}")
    print(f"   Message: {result['message']}")
    print(f"   Indexed: {result.get('indexed_count', 0)}")
    print(f"   Errors: {result.get('error_count', 0)}")

    print("\n" + "="*80)
    print("✅ Test completed")
