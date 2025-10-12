"""
IndexFullTranscriptToOpenSearch tool for indexing transcript chunks to OpenSearch.
Provides keyword/boolean search capabilities for Hybrid RAG alongside Zep semantic search.

OpenSearch Architecture:
- Index: autopiloot_transcripts (configurable)
- Documents: Individual transcript chunks with metadata
- Fields: video_id, chunk_id, title, channel_id, published_at, duration_sec, content_sha256, tokens, text
- Search: BM25 keyword matching, phrase queries, faceted filtering
"""

import os
import sys
import json
import hashlib
import tiktoken
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_optional_env_var, load_environment
from loader import get_config_value


class IndexFullTranscriptToOpenSearch(BaseTool):
    """
    Index full transcript chunks to OpenSearch for keyword/boolean search in Hybrid RAG.

    Implements:
    - Idempotent indexing with document IDs (video_id + chunk_id)
    - Same chunking as Zep tool for consistency
    - Rich metadata for filtering (channel, date, duration)
    - Content hashes for deduplication
    - Automatic index creation with proper mappings
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for document identification"
    )
    transcript_text: str = Field(
        ...,
        description="Full transcript text to chunk and index"
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
        Index transcript chunks to OpenSearch for keyword search.

        Process:
        1. Load OpenSearch configuration (host, auth, index name)
        2. Chunk transcript (same logic as Zep tool)
        3. Generate SHA-256 hashes for each chunk
        4. Initialize OpenSearch client
        5. Create index if not exists with proper mappings
        6. Index each chunk with metadata (idempotent by doc ID)
        7. Return indexing statistics

        Returns:
            JSON string with index_name, chunk_count, indexing status
        """
        try:
            # Load environment and configuration
            load_environment()

            # Get OpenSearch configuration
            opensearch_host = get_optional_env_var("OPENSEARCH_HOST")
            if not opensearch_host:
                return json.dumps({
                    "status": "skipped",
                    "message": "OpenSearch not configured (OPENSEARCH_HOST not set)",
                    "video_id": self.video_id
                }, indent=2)

            opensearch_api_key = get_optional_env_var("OPENSEARCH_API_KEY")
            opensearch_username = get_optional_env_var("OPENSEARCH_USERNAME")
            opensearch_password = get_optional_env_var("OPENSEARCH_PASSWORD")

            # Validate authentication
            if not opensearch_api_key and not (opensearch_username and opensearch_password):
                return json.dumps({
                    "error": "opensearch_auth_missing",
                    "message": "OpenSearch host configured but no authentication provided",
                    "video_id": self.video_id
                }, indent=2)

            # Load chunking and index configuration
            max_tokens = get_config_value("rag.zep.transcripts.chunking.max_tokens_per_chunk", 1000)
            overlap_tokens = get_config_value("rag.zep.transcripts.chunking.overlap_tokens", 100)
            index_name = get_config_value("rag.opensearch.index_transcripts", "autopiloot_transcripts")

            print(f"📤 Indexing transcript to OpenSearch...")
            print(f"   Host: {opensearch_host}")
            print(f"   Index: {index_name}")
            print(f"   Video ID: {self.video_id}")

            # Step 1: Chunk transcript (same as Zep tool)
            print(f"   Chunking transcript (max {max_tokens} tokens, {overlap_tokens} overlap)...")
            chunks = self._chunk_transcript(
                self.transcript_text,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens
            )
            print(f"   ✓ Created {len(chunks)} chunks")

            # Step 2: Prepare documents with metadata
            documents = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"{self.video_id}_chunk_{i+1}"
                chunk_hash = hashlib.sha256(chunk.encode('utf-8')).hexdigest()

                doc = {
                    "_id": chunk_id,  # Idempotent indexing by doc ID
                    "_index": index_name,
                    "video_id": self.video_id,
                    "chunk_id": chunk_id,
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "title": self.title,
                    "channel_id": self.channel_id,
                    "channel_handle": self.channel_handle,
                    "published_at": self.published_at,
                    "duration_sec": self.duration_sec,
                    "content_sha256": chunk_hash,
                    "tokens": self._count_tokens(chunk),
                    "text": chunk,
                    "indexed_at": datetime.utcnow().isoformat() + "Z"
                }
                documents.append(doc)

            # Step 3: Initialize OpenSearch client
            client = self._initialize_opensearch_client(
                opensearch_host,
                opensearch_api_key,
                opensearch_username,
                opensearch_password
            )

            # Step 4: Ensure index exists
            index_result = self._ensure_index_exists(client, index_name)
            if not index_result.get("success"):
                return json.dumps({
                    "error": "opensearch_index_creation_failed",
                    "message": f"Failed to create index: {index_result.get('error', 'Unknown error')}",
                    "index_name": index_name
                }, indent=2)

            # Step 5: Index documents
            print(f"   Indexing {len(documents)} chunks...")
            indexed_count = 0
            errors = []

            for doc in documents:
                index_result = self._index_document(client, doc)
                if index_result.get("success"):
                    indexed_count += 1
                else:
                    errors.append({
                        "chunk_id": doc["chunk_id"],
                        "error": index_result.get("error")
                    })

            print(f"   ✅ Indexed {indexed_count}/{len(documents)} chunks")
            if errors:
                print(f"   ⚠️ {len(errors)} indexing errors")

            return json.dumps({
                "index_name": index_name,
                "video_id": self.video_id,
                "chunk_count": len(documents),
                "indexed_count": indexed_count,
                "error_count": len(errors),
                "errors": errors if errors else None,
                "content_hashes": [doc["content_sha256"] for doc in documents],
                "status": "indexed" if indexed_count == len(documents) else "partial",
                "message": f"Indexed {indexed_count} chunks to OpenSearch index '{index_name}'"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "indexing_failed",
                "message": f"Failed to index transcript to OpenSearch: {str(e)}",
                "video_id": self.video_id
            })

    def _chunk_transcript(self, text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
        """Chunk transcript with token-aware overlap (same as Zep tool)."""
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)

        chunks = []
        start_idx = 0

        while start_idx < len(tokens):
            end_idx = min(start_idx + max_tokens, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            if end_idx < len(tokens):
                start_idx = end_idx - overlap_tokens
            else:
                break

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def _initialize_opensearch_client(self, host: str, api_key: Optional[str], username: Optional[str], password: Optional[str]):
        """Initialize OpenSearch client with authentication."""
        from opensearchpy import OpenSearch

        # Parse host to get hostname and port
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
            port = 9200 if not use_ssl else 443

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
            verify_certs=get_config_value("rag.opensearch.connection.verify_certs", True),
            ssl_assert_hostname=False,
            ssl_show_warn=False,
            timeout=get_config_value("rag.opensearch.timeout_ms", 1500) / 1000.0,
            max_retries=get_config_value("rag.opensearch.connection.max_retries", 3),
            retry_on_timeout=get_config_value("rag.opensearch.connection.retry_on_timeout", True)
        )

        return client

    def _ensure_index_exists(self, client, index_name: str) -> dict:
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

    def _index_document(self, client, doc: dict) -> dict:
        """Index individual document to OpenSearch."""
        try:
            doc_id = doc.pop("_id")
            index_name = doc.pop("_index")

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
    import traceback

    print("="*80)
    print("TEST: Index full transcript to OpenSearch with chunking")
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
        tool = IndexFullTranscriptToOpenSearch(
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
            print(f"\n📊 Indexing Summary:")
            print(f"   Index Name: {data['index_name']}")
            print(f"   Video ID: {data['video_id']}")
            print(f"   Chunk Count: {data['chunk_count']}")
            print(f"   Indexed Count: {data['indexed_count']}")
            print(f"   Error Count: {data['error_count']}")
            print(f"\n💡 {data['message']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
