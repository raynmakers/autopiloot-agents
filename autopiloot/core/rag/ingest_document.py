"""
Document Ingest Flow

Handles ingestion of Google Drive documents (PDFs, DOCX, TXT, MD) to RAG sinks.
Similar to transcript ingest but with document-specific metadata.
"""

import os
import sys
from typing import Dict

# Add module directories to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from chunker import chunk_with_metadata
from hashing import sha256_hex
from opensearch_indexer import index_transcript_chunks as index_documents
from bigquery_streamer import stream_transcript_chunks as stream_documents
from zep_upsert import upsert_transcript as upsert_document


def ingest(payload: dict) -> dict:
    """
    Ingest document to all enabled RAG sinks.

    Args:
        payload: Dictionary containing:
            - document_id (str): Unique document identifier (Drive file ID)
            - document_text (str): Full document text
            - document_type (str): Document type (pdf, docx, txt, md)
            - title (str, optional): Document title/filename
            - source (str): Source system ("drive", "upload")
            - folder_path (str, optional): Drive folder path

    Returns:
        Dictionary containing:
        - status: "success", "partial", or "error"
        - chunk_count: Total chunks created
        - sinks: Dictionary of sink results
        - message: Human-readable status message

    Example:
        >>> payload = {
        ...     "document_id": "drive_file_123",
        ...     "document_text": "Document content...",
        ...     "document_type": "pdf",
        ...     "title": "Strategy Document.pdf",
        ...     "source": "drive"
        ... }
        >>> result = ingest(payload)
        >>> result["status"]
        "success"
    """
    try:
        from rag.config import get_chunking_config

        # Extract payload
        document_id = payload.get("document_id")
        document_text = payload.get("document_text")

        if not document_id or not document_text:
            return {
                "status": "error",
                "message": "Missing required fields: document_id, document_text"
            }

        # Get chunking configuration
        chunking_config = get_chunking_config()
        max_tokens = chunking_config["max_tokens_per_chunk"]
        overlap_tokens = chunking_config["overlap_tokens"]

        # Chunk document
        chunks = chunk_with_metadata(
            text=document_text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            doc_id=document_id
        )

        chunk_count = len(chunks)

        # Prepare sink payloads (similar to transcript ingest)
        opensearch_docs = []
        bigquery_rows = []

        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            chunk_text = chunk["text"]
            chunk_hash = sha256_hex(chunk_text)

            # Adapt to document schema
            opensearch_docs.append({
                "video_id": document_id,  # Reuse field for compatibility
                "chunk_id": chunk_id,
                "chunk_index": chunk["chunk_index"],
                "total_chunks": chunk["total_chunks"],
                "title": payload.get("title"),
                "channel_id": payload.get("source", "drive"),  # Source as channel_id
                "content_sha256": chunk_hash,
                "tokens": chunk["tokens"],
                "text": chunk_text
            })

            bigquery_rows.append({
                "video_id": document_id,
                "chunk_id": chunk_id,
                "title": payload.get("title"),
                "channel_id": payload.get("source", "drive"),
                "content_sha256": chunk_hash,
                "tokens": chunk["tokens"],
                "text_snippet": chunk_text[:256]
            })

        # Send to sinks
        sink_results = {
            "opensearch": index_documents(opensearch_docs),
            "bigquery": stream_documents(bigquery_rows)
        }

        # Determine status
        any_success = any(r.get("status") in ["indexed", "streamed"] for r in sink_results.values())
        all_success = all(r.get("status") in ["indexed", "streamed", "skipped"] for r in sink_results.values())

        overall_status = "success" if all_success else "partial" if any_success else "error"

        return {
            "status": overall_status,
            "document_id": document_id,
            "chunk_count": chunk_count,
            "sinks": sink_results,
            "message": f"Ingested {chunk_count} document chunks (status: {overall_status})"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Document ingest failed: {str(e)}"
        }


if __name__ == "__main__":
    print("="*80)
    print("TEST: Document Ingest Flow")
    print("="*80)

    sample_payload = {
        "document_id": "drive_file_abc123",
        "document_text": "Sample document text for testing..." * 50,
        "document_type": "pdf",
        "title": "Strategy Document.pdf",
        "source": "drive",
        "folder_path": "/Strategy Docs"
    }

    print("\n1. Testing ingest():")
    result = ingest(sample_payload)
    print(f"   Status: {result['status']}")
    print(f"   Document ID: {result.get('document_id')}")
    print(f"   Chunk Count: {result.get('chunk_count')}")
    print(f"   Message: {result['message']}")

    print("\n" + "="*80)
    print("✅ Test completed")
