"""
RAG Index Summary Tool

Mandatory summarizer_agent wrapper that calls the shared Hybrid RAG core library
to index video summaries across all enabled sinks (OpenSearch, BigQuery, Zep).

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


class RagIndexSummary(BaseTool):
    """
    Index a video summary to all enabled RAG sinks.

    Delegates to the shared core.rag.ingest_document module which handles:
    - Token-aware chunking with configurable overlap
    - Content hashing for deduplication
    - Parallel ingestion to OpenSearch, BigQuery, and Zep
    - Unified status reporting across all sinks

    Use this tool after successfully generating a summary to make it
    searchable for future content strategy analysis and reference.

    Architecture:
        - Thin wrapper: No RAG logic in agent tools
        - Delegates to core.rag.ingest_document.ingest()
        - Type set to "summary" for proper schema mapping
        - Feature-flagged: Sinks enabled/disabled via config
        - Idempotent: Safe to retry, deduplicates by content hash
    """

    summary_id: str = Field(
        ...,
        description="Unique summary identifier (typically video_id, required)"
    )

    text: str = Field(
        ...,
        description="Full summary text to index (required)"
    )

    video_id: Optional[str] = Field(
        None,
        description="Associated YouTube video ID (optional, for linking)"
    )

    title: Optional[str] = Field(
        None,
        description="Video title (optional, improves searchability)"
    )

    tags: Optional[list] = Field(
        None,
        description="List of tags for categorization (optional)"
    )

    channel_id: Optional[str] = Field(
        None,
        description="YouTube channel ID (optional, for filtering)"
    )

    published_at: Optional[str] = Field(
        None,
        description="Video publication date (ISO 8601 format, optional)"
    )

    def run(self) -> str:
        """
        Execute the RAG indexing operation for a summary.

        Returns:
            JSON string containing operation result:
            - status: "success", "partial", or "error"
            - summary_id: The summary identifier
            - chunk_count: Number of chunks created
            - sinks: Per-sink results (opensearch, bigquery, zep)
            - message: Human-readable status message

        Example:
            >>> tool = RagIndexSummary(
            ...     summary_id="video_abc123",
            ...     text="Summary content...",
            ...     video_id="abc123",
            ...     title="Video Title"
            ... )
            >>> result = tool.run()
            >>> data = json.loads(result)
            >>> data["status"]
            "success"
        """
        try:
            # Build payload for core library
            payload = {
                "document_id": self.summary_id,
                "document_text": self.text,
                "document_type": "summary",
                "source": "summarizer",
            }

            # Add optional fields if provided
            if self.video_id:
                payload["video_id"] = self.video_id
            if self.title:
                payload["title"] = self.title
            if self.tags:
                payload["tags"] = self.tags
            if self.channel_id:
                payload["channel_id"] = self.channel_id
            if self.published_at:
                payload["published_at"] = self.published_at

            # Call core library
            print(f"📥 Indexing summary {self.summary_id} to Hybrid RAG...")
            result = ingest(payload)

            # Rename document_id to summary_id for clarity
            if "document_id" in result:
                result["summary_id"] = result.pop("document_id")

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
                        "type": "summary",
                        "source_ref": self.summary_id,
                        "created_by_agent": "summarizer_agent",
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
                "message": f"RAG summary indexing failed: {str(e)}",
                "summary_id": self.summary_id
            }
            return json.dumps(error_result, indent=2)


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: RagIndexSummary Tool")
    print("=" * 80)

    # Test 1: Full summary with complete metadata
    print("\n1. Testing with complete metadata:")
    tool = RagIndexSummary(
        summary_id="summary_abc123",
        text="""
        # Video Summary: How to Scale a SaaS Business

        ## Key Takeaways
        1. Focus on unit economics before scaling
        2. Hire A-players and build a strong culture
        3. Implement systems and processes early
        4. Track CAC, LTV, and payback period religiously

        ## Main Points

        ### Unit Economics Foundation
        The speaker emphasizes that understanding your unit economics is crucial.
        You need to know your customer acquisition cost (CAC), lifetime value (LTV),
        and payback period before attempting to scale. A healthy LTV:CAC ratio
        should be at least 3:1, ideally 5:1 for SaaS businesses.

        ### Hiring Strategy
        Don't settle for B-players just to fill roles quickly. A-players are 10x
        more productive and attract other A-players. Create a rigorous hiring
        process with multiple interview rounds and practical assessments.

        ### Systems and Processes
        Document everything as you go. Create playbooks for every key function.
        This allows you to scale without chaos and maintains quality as you grow.
        The best time to build systems is before you desperately need them.

        ### Key Metrics to Track
        - Monthly Recurring Revenue (MRR)
        - Customer Acquisition Cost (CAC)
        - Lifetime Value (LTV)
        - Churn Rate
        - Net Revenue Retention (NRR)

        ## Action Items
        1. Calculate your true CAC including all marketing and sales costs
        2. Measure LTV over 12, 24, and 36 month periods
        3. Build hiring scorecards for each role
        4. Document your top 5 business processes this quarter
        """ * 2,  # Repeat to create longer text
        video_id="abc123",
        title="How to Scale a SaaS Business - Complete Guide",
        tags=["saas", "scaling", "unit-economics", "hiring"],
        channel_id="UCkP5J0pXI11VE81q7S7V1Jw",
        published_at="2025-10-08T12:00:00Z"
    )

    result_json = tool.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Summary ID: {result.get('summary_id')}")
    print(f"   Chunk Count: {result.get('chunk_count')}")
    print(f"   Message: {result['message']}")

    if 'sinks' in result:
        print("\n   Sink Results:")
        for sink_name, sink_result in result['sinks'].items():
            print(f"     {sink_name}: {sink_result.get('status')} - {sink_result.get('message')}")

    # Test 2: Minimal payload with required fields only
    print("\n2. Testing with minimal payload:")
    tool_minimal = RagIndexSummary(
        summary_id="summary_xyz789",
        text="Short summary content for minimal testing. Key insight: focus on metrics."
    )

    result_json = tool_minimal.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Summary ID: {result.get('summary_id')}")
    print(f"   Message: {result['message']}")

    # Test 3: Summary with video_id linking
    print("\n3. Testing with video_id linking:")
    tool_linked = RagIndexSummary(
        summary_id="summary_linked_123",
        text="This summary is linked to a specific video for cross-referencing.",
        video_id="video_123",
        title="Linked Video Summary"
    )

    result_json = tool_linked.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Video ID: {result.get('video_id', 'N/A')}")
    print(f"   Message: {result['message']}")

    print("\n" + "=" * 80)
    print("✅ Test completed")
