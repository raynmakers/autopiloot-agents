"""
UpsertFullTranscriptToZep tool for storing full transcripts in Zep v3 for Hybrid RAG.
Implements token-aware chunking, content hashing, and metadata enrichment.

Zep v3 Architecture for Transcripts:
- Groups: Per-channel organization (e.g., "youtube_transcripts_UC1234567890")
- Threads: Represent individual video transcripts (e.g., "transcript_VIDEO_ID")
- Messages: Contain chunked transcript text with metadata (chunk_id, position, hash)
- Knowledge Graph: Zep automatically builds from transcript content for semantic search
"""

import os
import sys
import json
import hashlib
import tiktoken
from typing import List, Dict, Optional
from datetime import datetime, timezone
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import get_config_value


class UpsertFullTranscriptToZep(BaseTool):
    """
    Store full transcript in Zep v3 with token-aware chunking for Hybrid RAG.

    Implements:
    - Token-aware chunking with configurable overlap
    - SHA-256 content hashing for idempotency
    - Firestore metadata updates (zep_transcript_doc_id, rag_ingested_at)
    - Rich metadata per chunk (video info, chunk position, timestamps)
    - Automatic knowledge graph building in Zep
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
        Store full transcript in Zep v3 with chunking and metadata.

        Process:
        1. Load configuration (chunking params, metadata options)
        2. Chunk transcript with token-aware overlap
        3. Generate SHA-256 hashes for each chunk
        4. Ensure user and group exist in Zep
        5. Create thread for this transcript
        6. Store chunks as messages with metadata
        7. Update Firestore with zep_transcript_doc_id and rag_ingested_at
        8. Return storage confirmation with chunk statistics

        Returns:
            JSON string with thread_id, chunk_count, storage status
        """
        try:
            # Load environment and configuration
            load_environment()

            # Get Zep configuration
            zep_api_key = get_required_env_var("ZEP_API_KEY", "Zep API key for GraphRAG")
            zep_base_url = os.getenv("ZEP_BASE_URL", "https://api.getzep.com")

            # Load chunking configuration
            max_tokens = get_config_value("rag.zep.transcripts.chunking.max_tokens_per_chunk", 1000)
            overlap_tokens = get_config_value("rag.zep.transcripts.chunking.overlap_tokens", 100)

            # Load ID formats
            group_format = get_config_value("rag.zep.transcripts.group_format", "youtube_transcripts_{channel_id}")
            thread_id_format = get_config_value("rag.zep.transcripts.thread_id_format", "transcript_{video_id}")
            user_id_format = get_config_value("rag.zep.transcripts.user_id_format", "youtube_{channel_id}")

            # Define identifiers
            user_id = user_id_format.format(channel_id=self.channel_id)
            group = group_format.format(channel_id=self.channel_id)
            thread_id = thread_id_format.format(video_id=self.video_id)

            print(f"📤 Storing full transcript in Zep v3...")
            print(f"   User ID: {user_id}")
            print(f"   Group: {group}")
            print(f"   Thread ID: {thread_id}")

            # Step 1: Chunk transcript
            print(f"   Chunking transcript (max {max_tokens} tokens, {overlap_tokens} overlap)...")
            chunks = self._chunk_transcript(
                self.transcript_text,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens
            )
            print(f"   ✓ Created {len(chunks)} chunks")

            # Step 2: Generate content hashes
            chunks_with_hashes = []
            for i, chunk in enumerate(chunks):
                chunk_hash = hashlib.sha256(chunk.encode('utf-8')).hexdigest()
                chunks_with_hashes.append({
                    "chunk_id": f"{self.video_id}_chunk_{i+1}",
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "text": chunk,
                    "content_sha256": chunk_hash,
                    "tokens": self._count_tokens(chunk)
                })

            # Initialize HTTP client
            zep_client = self._initialize_http_client(zep_api_key, zep_base_url)

            # Step 3: Ensure user exists
            user_result = self._ensure_user_exists(zep_client, zep_base_url, user_id)
            if not user_result.get("success"):
                return json.dumps({
                    "error": "zep_user_creation_failed",
                    "message": f"Failed to create user: {user_result.get('error', 'Unknown error')}",
                    "channel_id": self.channel_id
                }, indent=2)

            # Step 4: Ensure group exists
            group_result = self._ensure_group_exists(zep_client, zep_base_url, group)
            if not group_result.get("success"):
                return json.dumps({
                    "error": "zep_group_creation_failed",
                    "message": f"Failed to create group: {group_result.get('error', 'Unknown error')}",
                    "group": group
                }, indent=2)

            # Step 5: Create thread
            thread_result = self._create_thread(zep_client, zep_base_url, thread_id, user_id, group)
            if not thread_result.get("success"):
                return json.dumps({
                    "error": "zep_thread_creation_failed",
                    "message": f"Failed to create thread: {thread_result.get('error', 'Unknown error')}",
                    "video_id": self.video_id
                }, indent=2)

            # Step 6: Store chunks as messages
            print(f"   Storing {len(chunks_with_hashes)} chunks to Zep...")
            message_results = []
            for chunk_data in chunks_with_hashes:
                message_result = self._add_chunk_message(
                    zep_client,
                    zep_base_url,
                    thread_id,
                    chunk_data
                )
                if message_result.get("success"):
                    message_results.append(message_result.get("message_uuid"))
                else:
                    print(f"   ⚠️ Warning: Failed to store chunk {chunk_data['chunk_id']}: {message_result.get('error')}")

            # Step 7: Update Firestore with Zep reference
            if self.firestore_doc_ref:
                firestore_result = self._update_firestore_metadata(
                    thread_id,
                    chunks_with_hashes
                )
                if not firestore_result.get("success"):
                    print(f"   ⚠️ Warning: Failed to update Firestore: {firestore_result.get('error')}")

            print(f"   ✅ Transcript stored successfully!")
            print(f"   Message UUIDs: {len(message_results)} chunks stored")

            return json.dumps({
                "thread_id": thread_id,
                "group": group,
                "chunk_count": len(chunks_with_hashes),
                "message_uuids": message_results,
                "total_tokens": sum(c["tokens"] for c in chunks_with_hashes),
                "content_hashes": [c["content_sha256"] for c in chunks_with_hashes],
                "channel_handle": self.channel_handle,
                "status": "stored",
                "message": f"Transcript stored in Zep v3: {len(chunks_with_hashes)} chunks across thread '{thread_id}'"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "storage_failed",
                "message": f"Failed to store transcript in Zep: {str(e)}",
                "video_id": self.video_id
            })

    def _chunk_transcript(self, text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
        """
        Chunk transcript with token-aware overlap for context continuity.

        Args:
            text: Full transcript text
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Token overlap between consecutive chunks

        Returns:
            List[str]: List of text chunks
        """
        # Initialize tokenizer (cl100k_base for gpt-4/gpt-3.5)
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)

        chunks = []
        start_idx = 0

        while start_idx < len(tokens):
            # Define chunk boundaries
            end_idx = min(start_idx + max_tokens, len(tokens))

            # Extract chunk tokens
            chunk_tokens = tokens[start_idx:end_idx]

            # Decode back to text
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            # Move start index forward (with overlap)
            if end_idx < len(tokens):
                start_idx = end_idx - overlap_tokens
            else:
                break

        return chunks

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            int: Token count
        """
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def _initialize_http_client(self, api_key: str, base_url: str):
        """Initialize HTTP client for Zep v3 API."""
        import httpx

        client = httpx.Client(
            headers={
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        return client

    def _ensure_user_exists(self, client, base_url: str, user_id: str) -> dict:
        """Ensure user exists in Zep (idempotent)."""
        try:
            user_data = {
                "user_id": user_id,
                "metadata": {
                    "source": "youtube",
                    "type": "channel"
                }
            }

            response = client.post(f"{base_url}/api/v2/users", json=user_data)

            if response.status_code in [200, 201]:
                return {"success": True, "user_id": user_id, "status": "created"}
            elif response.status_code in [400, 409]:
                error_text = response.text.lower()
                if "already exists" in error_text or "user_id" in error_text:
                    return {"success": True, "user_id": user_id, "status": "already_exists"}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ensure_group_exists(self, client, base_url: str, group_name: str) -> dict:
        """Ensure group exists in Zep (idempotent)."""
        try:
            group_data = {
                "group_id": group_name,
                "name": group_name,
                "metadata": {
                    "source": "youtube",
                    "type": "transcripts"
                }
            }

            response = client.post(f"{base_url}/api/v2/groups", json=group_data)

            if response.status_code in [200, 201]:
                return {"success": True, "group_name": group_name, "status": "created"}
            elif response.status_code in [400, 409]:
                error_text = response.text.lower()
                if "already exists" in error_text:
                    return {"success": True, "group_name": group_name, "status": "already_exists"}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_thread(self, client, base_url: str, thread_id: str, user_id: str, group: str) -> dict:
        """Create thread in Zep for this transcript."""
        try:
            thread_data = {
                "thread_id": thread_id,
                "user_id": user_id,
                "metadata": {
                    "video_id": self.video_id,
                    "title": self.title,
                    "channel_id": self.channel_id,
                    "channel_handle": self.channel_handle,
                    "published_at": self.published_at,
                    "duration_sec": self.duration_sec,
                    "source": "youtube",
                    "type": "transcript",
                    "group": group
                }
            }

            response = client.post(f"{base_url}/api/v2/threads", json=thread_data)

            if response.status_code in [200, 201]:
                result = response.json()
                return {"success": True, "thread_uuid": result.get("uuid"), "status": "created"}
            elif response.status_code in [400, 409]:
                error_text = response.text.lower()
                if "already exists" in error_text:
                    return {"success": True, "status": "already_exists"}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _add_chunk_message(self, client, base_url: str, thread_id: str, chunk_data: dict) -> dict:
        """Add individual chunk as message to thread."""
        try:
            message_data = {
                "messages": [
                    {
                        "role": "assistant",
                        "content": chunk_data["text"],
                        "metadata": {
                            "type": "transcript_chunk",
                            "video_id": self.video_id,
                            "chunk_id": chunk_data["chunk_id"],
                            "chunk_index": chunk_data["chunk_index"],
                            "total_chunks": chunk_data["total_chunks"],
                            "content_sha256": chunk_data["content_sha256"],
                            "tokens": chunk_data["tokens"],
                            "stored_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                ]
            }

            response = client.post(
                f"{base_url}/api/v2/threads/{thread_id}/messages",
                json=message_data
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "message_uuid": result.get("message_uuids", [])[0] if result.get("message_uuids") else None
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_firestore_metadata(self, thread_id: str, chunks: List[dict]) -> dict:
        """Update Firestore document with Zep metadata."""
        try:
            from google.cloud import firestore

            # Initialize Firestore
            project_id = get_required_env_var("GCP_PROJECT_ID", "GCP project for Firestore")
            db = firestore.Client(project=project_id)

            # Prepare metadata
            content_sha256_list = [chunk["content_sha256"] for chunk in chunks]
            total_transcript_hash = hashlib.sha256(self.transcript_text.encode('utf-8')).hexdigest()

            # Update document
            doc_ref = db.collection("transcripts").document(self.video_id)
            doc_ref.update({
                "zep_transcript_doc_id": thread_id,
                "rag_ingested_at": firestore.SERVER_TIMESTAMP,
                "content_sha256": total_transcript_hash,
                "chunk_count": len(chunks),
                "chunk_hashes": content_sha256_list
            })

            return {"success": True, "doc_path": f"transcripts/{self.video_id}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Store full transcript in Zep v3 with chunking")
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
        else:
            print(f"\n📊 Storage Summary:")
            print(f"   Thread ID: {data['thread_id']}")
            print(f"   Group: {data['group']}")
            print(f"   Chunk Count: {data['chunk_count']}")
            print(f"   Total Tokens: {data['total_tokens']}")
            print(f"   Messages Stored: {len(data['message_uuids'])}")
            print(f"\n💡 {data['message']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
