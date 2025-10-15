"""
Zep Upsert Module

Provides semantic search storage for Hybrid RAG via Zep GraphRAG.
Handles thread/message creation with automatic embedding generation.
"""

import os
import sys
import json
import requests
from typing import Dict, Optional

# Add config directory to path
from env_loader import get_required_env_var, get_optional_env_var


def upsert_transcript(text: str, metadata: dict) -> dict:
    """
    Upsert transcript chunk to Zep for semantic search.

    Args:
        text: Chunk text content
        metadata: Metadata dictionary containing:
            - video_id (str): YouTube video ID
            - chunk_id (str): Unique chunk identifier
            - channel_id (str): YouTube channel ID
            - title (str, optional): Video title
            - published_at (str, optional): Publication date
            - duration_sec (int, optional): Video duration

    Returns:
        Dictionary containing:
        - status: "upserted", "skipped", or "error"
        - thread_id: Zep thread ID
        - message_id: Zep message ID (if created)
        - message: Human-readable status message

    Feature Flags:
        - rag.zep.transcripts.enabled: Enable/disable Zep storage
        - Returns {"status": "skipped"} if disabled or misconfigured

    Zep Architecture:
        - Uses Threads API (Zep v3) via HTTP
        - Thread ID format: "transcript_{video_id}"
        - User ID format: "youtube_{channel_id}"
        - Group format: "youtube_transcripts_{channel_id}"

    Example:
        >>> result = upsert_transcript(
        ...     text="Transcript chunk text...",
        ...     metadata={
        ...         "video_id": "abc123",
        ...         "chunk_id": "abc123_chunk_0",
        ...         "channel_id": "UC123"
        ...     }
        ... )
        >>> result["status"]
        "upserted"
    """
    try:
        # Import config here to avoid circular imports
        from rag.config import get_rag_flag, get_rag_value

        # Check if Zep is enabled
        if not get_rag_flag("zep.transcripts.enabled", False):
            return {
                "status": "skipped",
                "message": "Zep transcripts storage is disabled in configuration"
            }

        # Get Zep credentials
        zep_api_key = get_optional_env_var("ZEP_API_KEY")
        if not zep_api_key:
            return {
                "status": "skipped",
                "message": "Zep not configured (ZEP_API_KEY not set)"
            }

        zep_api_url = get_optional_env_var("ZEP_API_URL", "https://api.getzep.com")

        # Extract metadata
        video_id = metadata.get("video_id")
        chunk_id = metadata.get("chunk_id")
        channel_id = metadata.get("channel_id")

        if not video_id or not channel_id:
            return {
                "status": "error",
                "message": "Missing required metadata: video_id and channel_id"
            }

        # Build thread and user IDs
        thread_id_format = get_rag_value("zep.transcripts.thread_id_format", "transcript_{video_id}")
        user_id_format = get_rag_value("zep.transcripts.user_id_format", "youtube_{channel_id}")

        thread_id = thread_id_format.replace("{video_id}", video_id)
        user_id = user_id_format.replace("{channel_id}", channel_id)

        # Create or get thread
        thread_result = _ensure_thread_exists(zep_api_url, zep_api_key, thread_id, user_id, metadata)
        if not thread_result["success"]:
            return {
                "status": "error",
                "message": f"Failed to create/get thread: {thread_result['error']}"
            }

        # Add message to thread
        message_result = _add_message(zep_api_url, zep_api_key, thread_id, text, metadata)
        if not message_result["success"]:
            return {
                "status": "error",
                "message": f"Failed to add message: {message_result['error']}"
            }

        return {
            "status": "upserted",
            "thread_id": thread_id,
            "message_id": message_result.get("message_id"),
            "message": f"Upserted chunk to Zep thread '{thread_id}'"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Zep upsert failed: {str(e)}"
        }


def _ensure_thread_exists(api_url: str, api_key: str, thread_id: str, user_id: str, metadata: dict) -> dict:
    """Create thread if not exists."""
    try:
        # Check if thread exists
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(f"{api_url}/v3/threads/{thread_id}", headers=headers, timeout=5)

        if response.status_code == 200:
            return {"success": True, "status": "exists"}

        # Create thread
        thread_data = {
            "thread_id": thread_id,
            "user_id": user_id,
            "metadata": {
                "video_id": metadata.get("video_id"),
                "channel_id": metadata.get("channel_id"),
                "title": metadata.get("title"),
                "source": "youtube"
            }
        }

        response = requests.post(f"{api_url}/v3/threads", json=thread_data, headers=headers, timeout=5)
        response.raise_for_status()

        return {"success": True, "status": "created"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _add_message(api_url: str, api_key: str, thread_id: str, text: str, metadata: dict) -> dict:
    """Add message to thread."""
    try:
        headers = {"Authorization": f"Bearer {api_key}"}

        message_data = {
            "role": "user",
            "content": text,
            "metadata": {
                "chunk_id": metadata.get("chunk_id"),
                "video_id": metadata.get("video_id"),
                "channel_id": metadata.get("channel_id"),
                "content_sha256": metadata.get("content_sha256"),
                "tokens": metadata.get("tokens")
            }
        }

        response = requests.post(
            f"{api_url}/v3/threads/{thread_id}/messages",
            json=message_data,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()

        result = response.json()
        return {"success": True, "message_id": result.get("message_id")}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("="*80)
    print("TEST: Zep Upsert Module")
    print("="*80)

    # Sample data
    sample_text = "This is a sample transcript chunk for testing Zep upsert functionality."
    sample_metadata = {
        "video_id": "abc123",
        "chunk_id": "abc123_chunk_0",
        "channel_id": "UC123",
        "title": "How to Build a SaaS Business",
        "content_sha256": "hash123",
        "tokens": 15
    }

    print("\n1. Testing upsert_transcript():")
    result = upsert_transcript(sample_text, sample_metadata)
    print(f"   Status: {result['status']}")
    print(f"   Message: {result['message']}")
    if result.get("thread_id"):
        print(f"   Thread ID: {result['thread_id']}")
    if result.get("message_id"):
        print(f"   Message ID: {result['message_id']}")

    print("\n" + "="*80)
    print("✅ Test completed")
