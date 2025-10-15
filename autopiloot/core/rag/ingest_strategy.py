"""
Strategy Content Ingest Flow

Handles ingestion of LinkedIn posts and strategic content to RAG sinks.
Optimized for short-form social content with engagement metadata.
"""

import os
import sys
from typing import Dict

from hashing import sha256_hex
from zep_upsert import upsert_transcript as upsert_content


def ingest(payload: dict) -> dict:
    """
    Ingest strategy content (LinkedIn posts, comments) to RAG sinks.

    Args:
        payload: Dictionary containing:
            - content_id (str): Unique content identifier (LinkedIn post ID)
            - content_text (str): Post/comment text
            - content_type (str): "post" or "comment"
            - author_id (str): LinkedIn author ID
            - author_name (str, optional): Author display name
            - published_at (str, optional): Publication timestamp
            - engagement (dict, optional): Likes, comments, shares counts

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - message: Human-readable status message

    Note:
        Strategy content is typically short (<500 tokens) so no chunking is needed.
        Primarily stored in Zep for semantic search of strategic insights.

    Example:
        >>> payload = {
        ...     "content_id": "linkedin_post_123",
        ...     "content_text": "Key insights on scaling SaaS...",
        ...     "content_type": "post",
        ...     "author_id": "alexhormozi"
        ... }
        >>> result = ingest(payload)
        >>> result["status"]
        "success"
    """
    try:
        # Extract payload
        content_id = payload.get("content_id")
        content_text = payload.get("content_text")
        author_id = payload.get("author_id")

        if not content_id or not content_text or not author_id:
            return {
                "status": "error",
                "message": "Missing required fields: content_id, content_text, author_id"
            }

        # Prepare metadata
        metadata = {
            "video_id": content_id,  # Reuse field for compatibility
            "chunk_id": content_id,  # Single chunk for short content
            "channel_id": author_id,
            "title": f"{payload.get('content_type', 'post')} by {payload.get('author_name', author_id)}",
            "content_sha256": sha256_hex(content_text),
            "tokens": len(content_text.split())  # Rough estimate
        }

        # Upsert to Zep (primary storage for strategy content)
        result = upsert_content(content_text, metadata)

        if result.get("status") == "upserted":
            return {
                "status": "success",
                "content_id": content_id,
                "message": f"Ingested strategy content to Zep"
            }
        elif result.get("status") == "skipped":
            return {
                "status": "success",
                "content_id": content_id,
                "message": "Strategy content ingestion skipped (Zep disabled)"
            }
        else:
            return {
                "status": "error",
                "content_id": content_id,
                "message": f"Failed to ingest strategy content: {result.get('message')}"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Strategy ingest failed: {str(e)}"
        }


if __name__ == "__main__":
    print("="*80)
    print("TEST: Strategy Content Ingest Flow")
    print("="*80)

    sample_payload = {
        "content_id": "linkedin_post_abc123",
        "content_text": "Key insights on scaling SaaS: Focus on unit economics, hire A-players, build systems early.",
        "content_type": "post",
        "author_id": "alexhormozi",
        "author_name": "Alex Hormozi",
        "published_at": "2025-10-08T14:30:00Z",
        "engagement": {"likes": 245, "comments": 18, "shares": 12}
    }

    print("\n1. Testing ingest():")
    result = ingest(sample_payload)
    print(f"   Status: {result['status']}")
    print(f"   Message: {result['message']}")

    print("\n" + "="*80)
    print("✅ Test completed")
