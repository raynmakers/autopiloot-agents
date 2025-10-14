"""
RAG Index Document Tool

Mandatory drive_agent wrapper that calls the shared Hybrid RAG core library
to index Google Drive documents (PDFs, DOCX, TXT, MD) across all enabled sinks.

This tool is discoverable by Agency Swarm and provides strict Pydantic validation.
"""

import os
import sys
import json
from typing import Optional
from pydantic import Field

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from agency_swarm.tools import BaseTool
from core.rag.ingest_document import ingest


class RagIndexDocument(BaseTool):
    """
    Index a Google Drive document to all enabled RAG sinks.

    Delegates to the shared core.rag.ingest_document module which handles:
    - Token-aware chunking with configurable overlap
    - Content hashing for deduplication
    - Parallel ingestion to OpenSearch and BigQuery
    - Unified status reporting across all sinks

    Use this tool after successfully extracting text from a Drive document
    to make it searchable for future content strategy analysis.
    """

    doc_id: str = Field(
        ...,
        description="Unique document identifier (Google Drive file ID, required)"
    )

    text: str = Field(
        ...,
        description="Full document text to index (required)"
    )

    source_uri: Optional[str] = Field(
        None,
        description="Source URI or Drive link (optional)"
    )

    mime_type: Optional[str] = Field(
        None,
        description="Document MIME type (e.g., 'application/pdf', optional)"
    )

    title: Optional[str] = Field(
        None,
        description="Document title or filename (optional, improves searchability)"
    )

    tags: Optional[list] = Field(
        None,
        description="List of tags for categorization (optional)"
    )

    def run(self) -> str:
        """
        Execute the RAG indexing operation for a document.

        Returns:
            JSON string containing operation result:
            - status: "success", "partial", or "error"
            - chunk_count: Number of chunks created
            - sinks: Per-sink results (opensearch, bigquery)
            - message: Human-readable status
        """
        try:
            # Build payload for core library
            payload = {
                "document_id": self.doc_id,
                "document_text": self.text,
            }

            # Add optional fields if provided
            if self.source_uri:
                payload["source_uri"] = self.source_uri
            if self.mime_type:
                payload["mime_type"] = self.mime_type
            if self.title:
                payload["title"] = self.title
            if self.tags:
                payload["tags"] = self.tags

            # Set source to 'drive' for proper schema mapping
            payload["source"] = "drive"
            payload["document_type"] = self._infer_document_type()

            # Call core library
            print(f"📥 Indexing document {self.doc_id} to Hybrid RAG...")
            result = ingest(payload)

            # Log result
            if result.get("status") == "success":
                print(f"   ✅ Indexed {result.get('chunk_count', 0)} chunks successfully")
            elif result.get("status") == "partial":
                print(f"   ⚠️ Partial indexing: {result.get('message')}")
            else:
                print(f"   ❌ Indexing failed: {result.get('message')}")

            # Optional: Write Firestore reference for audit/discovery (best-effort, never blocks)
            if result.get("status") in ["success", "partial"]:
                try:
                    from core.rag.refs import upsert_ref

                    # Build reference document
                    ref = {
                        "type": "document",
                        "source_ref": self.doc_id,
                        "created_by_agent": "drive_agent",
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
                    if self.tags:
                        ref["tags"] = self.tags

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
                "error": "rag_indexing_failed",
                "message": f"RAG document indexing failed: {str(e)}",
                "doc_id": self.doc_id
            }
            return json.dumps(error_result, indent=2)

    def _infer_document_type(self) -> str:
        """Infer document type from MIME type or title."""
        if self.mime_type:
            if "pdf" in self.mime_type.lower():
                return "pdf"
            elif "word" in self.mime_type.lower() or "docx" in self.mime_type.lower():
                return "docx"
            elif "text" in self.mime_type.lower():
                return "txt"

        if self.title:
            title_lower = self.title.lower()
            if title_lower.endswith(".pdf"):
                return "pdf"
            elif title_lower.endswith(".docx") or title_lower.endswith(".doc"):
                return "docx"
            elif title_lower.endswith(".txt"):
                return "txt"
            elif title_lower.endswith(".md"):
                return "md"

        return "unknown"


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: RagIndexDocument Tool")
    print("=" * 80)

    # Test 1: PDF document with complete metadata
    print("\n1. Testing with PDF document:")
    tool = RagIndexDocument(
        doc_id="drive_file_abc123",
        text="""
        Strategic Planning Document

        Executive Summary
        This document outlines our strategic approach to scaling operations in Q4 2025.

        Key Objectives:
        1. Increase revenue by 40% through improved unit economics
        2. Expand team from 12 to 20 A-players
        3. Implement automated systems for customer onboarding

        Market Analysis:
        The SaaS market continues to show strong growth with CAC payback periods improving.
        Our competitive advantage lies in our superior customer retention rates.

        Financial Projections:
        - Q4 Revenue Target: $2.5M
        - Expected CAC: $1,200
        - LTV:CAC Ratio: 5:1
        """ * 3,  # Repeat to create longer text
        source_uri="https://drive.google.com/file/d/abc123",
        mime_type="application/pdf",
        title="Q4 2025 Strategic Planning.pdf",
        tags=["strategy", "planning", "q4-2025"]
    )

    result_json = tool.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Document ID: {result.get('document_id')}")
    print(f"   Chunk Count: {result.get('chunk_count')}")
    print(f"   Message: {result['message']}")

    if 'sinks' in result:
        print("\n   Sink Results:")
        for sink_name, sink_result in result['sinks'].items():
            print(f"     {sink_name}: {sink_result.get('status')} - {sink_result.get('message')}")

    # Test 2: Minimal payload with required fields only
    print("\n2. Testing with minimal payload:")
    tool_minimal = RagIndexDocument(
        doc_id="drive_file_xyz789",
        text="Short document content for minimal testing."
    )

    result_json = tool_minimal.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Message: {result['message']}")

    # Test 3: DOCX document
    print("\n3. Testing with DOCX document:")
    tool_docx = RagIndexDocument(
        doc_id="drive_file_docx456",
        text="Sample Word document content for testing.",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        title="Meeting Notes.docx"
    )

    result_json = tool_docx.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Inferred type: {tool_docx._infer_document_type()}")

    print("\n" + "=" * 80)
    print("✅ Test completed")
