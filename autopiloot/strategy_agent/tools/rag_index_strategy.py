"""
RAG Index Strategy Tool (Optional, Feature-Flagged)

Optional strategy_agent wrapper that calls the shared Hybrid RAG core library
to index strategic content (LinkedIn posts, content briefs, strategy analyses).

This tool is feature-flagged by `rag.features.persist_strategies` (default: false).
When disabled, returns "skipped" status without attempting to index.

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
from core.rag.config import get_rag_flag
from core.rag.ingest_strategy import ingest


class RagIndexStrategy(BaseTool):
    """
    Index strategic content to RAG sinks (feature-flagged, optional).

    Delegates to the shared core.rag.ingest_strategy module which handles:
    - Feature flag checking (rag.features.persist_strategies)
    - Content hashing for deduplication
    - Ingestion to Zep for semantic search
    - Graceful skipping when feature is disabled

    Use this tool to index LinkedIn posts, content briefs, or strategic
    analyses for future reference and content strategy insights.

    IMPORTANT: This tool is controlled by the `rag.features.persist_strategies`
    configuration flag. When disabled (default), it returns "skipped" without
    attempting to index, allowing the strategy agent to function normally
    without requiring RAG infrastructure.

    Architecture:
        - Thin wrapper: No RAG logic in agent tools
        - Delegates to core.rag.ingest_strategy.ingest()
        - Feature-flagged: Controlled by rag.features.persist_strategies
        - Type set to "strategy" for proper schema mapping
        - Idempotent: Safe to retry, deduplicates by content hash
    """

    strategy_id: str = Field(
        ...,
        description="Unique strategy content identifier (e.g., LinkedIn post ID, required)"
    )

    text: str = Field(
        ...,
        description="Full strategy content text to index (required)"
    )

    title: Optional[str] = Field(
        None,
        description="Content title or description (optional)"
    )

    tags: Optional[list] = Field(
        None,
        description="List of tags for categorization (optional, e.g., ['linkedin', 'post', 'engagement'])"
    )

    author_id: Optional[str] = Field(
        None,
        description="Author identifier (optional, e.g., LinkedIn user ID or handle)"
    )

    published_at: Optional[str] = Field(
        None,
        description="Publication date (ISO 8601 format, optional)"
    )

    content_type: Optional[str] = Field(
        None,
        description="Content type (optional, e.g., 'linkedin_post', 'content_brief', 'analysis')"
    )

    def run(self) -> str:
        """
        Execute the RAG indexing operation for strategic content.

        Checks feature flag first. If rag.features.persist_strategies is false,
        returns skipped status immediately without attempting to index.

        Returns:
            JSON string containing operation result:
            - status: "success", "skipped", or "error"
            - strategy_id: The strategy content identifier
            - message: Human-readable status message
            - feature_enabled: Boolean indicating if feature is enabled

        Example:
            >>> tool = RagIndexStrategy(
            ...     strategy_id="linkedin_post_123",
            ...     text="Key insights on SaaS scaling...",
            ...     title="LinkedIn Post by Alex Hormozi",
            ...     tags=["linkedin", "saas", "scaling"]
            ... )
            >>> result = tool.run()
            >>> data = json.loads(result)
            >>> data["status"]
            "skipped"  # If feature disabled
        """
        try:
            # Check feature flag first
            feature_enabled = get_rag_flag("features.persist_strategies", default=False)

            if not feature_enabled:
                return json.dumps({
                    "status": "skipped",
                    "strategy_id": self.strategy_id,
                    "message": "Strategy indexing skipped (rag.features.persist_strategies is false)",
                    "feature_enabled": False
                }, indent=2)

            # Build payload for core library
            payload = {
                "content_id": self.strategy_id,
                "content_text": self.text,
                "content_type": self.content_type or "strategy",
                "author_id": self.author_id or "unknown"
            }

            # Add optional fields if provided
            if self.title:
                payload["title"] = self.title
            if self.tags:
                payload["tags"] = self.tags
            if self.published_at:
                payload["published_at"] = self.published_at

            # Call core library
            print(f"📥 Indexing strategy content {self.strategy_id} to Hybrid RAG...")
            result = ingest(payload)

            # Rename content_id to strategy_id for clarity
            if "content_id" in result:
                result["strategy_id"] = result.pop("content_id")

            # Add feature flag status
            result["feature_enabled"] = True

            # Log result
            if result.get("status") == "success":
                print(f"   ✅ Indexed strategy content successfully")
            elif result.get("status") == "skipped":
                print(f"   ⚪ Strategy indexing skipped: {result.get('message')}")
            else:
                print(f"   ❌ Indexing failed: {result.get('message')}")


            # Optional: Write Firestore reference for audit/discovery (best-effort, never blocks)
            if result.get("status") == "success":
                try:
                    from core.rag.refs import upsert_ref

                    # Build reference document
                    ref = {
                        "type": "strategy",
                        "source_ref": self.strategy_id,
                        "created_by_agent": "strategy_agent",
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
                "message": f"RAG strategy indexing failed: {str(e)}",
                "strategy_id": self.strategy_id,
                "feature_enabled": get_rag_flag("features.persist_strategies", default=False)
            }
            return json.dumps(error_result, indent=2)


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: RagIndexStrategy Tool (Feature-Flagged)")
    print("=" * 80)

    # Test 1: LinkedIn post with complete metadata
    print("\n1. Testing with LinkedIn post:")
    tool = RagIndexStrategy(
        strategy_id="linkedin_post_abc123",
        text="""
        🚀 Key lessons from scaling our SaaS to $10M ARR:

        1. Unit economics BEFORE growth
           - Know your CAC, LTV, payback period
           - Don't scale broken economics

        2. A-players compound
           - One A-player > 3 B-players
           - They attract other A-players
           - Worth 2x the salary

        3. Systems beat heroes
           - Document everything
           - Build playbooks early
           - Scale without chaos

        Which of these resonates most with your experience? 👇

        #SaaS #Entrepreneurship #Scaling
        """,
        title="LinkedIn Post: Scaling SaaS to $10M ARR",
        tags=["linkedin", "saas", "scaling", "unit-economics"],
        author_id="alexhormozi",
        published_at="2025-10-08T14:30:00Z",
        content_type="linkedin_post"
    )

    result_json = tool.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Feature Enabled: {result.get('feature_enabled')}")
    print(f"   Strategy ID: {result.get('strategy_id')}")
    print(f"   Message: {result['message']}")

    # Test 2: Content brief (minimal payload)
    print("\n2. Testing with content brief (minimal):")
    tool_brief = RagIndexStrategy(
        strategy_id="content_brief_xyz789",
        text="Target audience: SaaS founders. Key message: Focus on unit economics. CTA: Download our guide."
    )

    result_json = tool_brief.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Feature Enabled: {result.get('feature_enabled')}")
    print(f"   Message: {result['message']}")

    # Test 3: Strategy analysis with tags
    print("\n3. Testing with strategy analysis:")
    tool_analysis = RagIndexStrategy(
        strategy_id="analysis_content_456",
        text="""
        Content Strategy Analysis - Q4 2025

        Top performing content types:
        1. Case studies (+245% engagement)
        2. How-to guides (+180% engagement)
        3. Data-driven posts (+150% engagement)

        Recommended content calendar:
        - 2x case studies per week
        - 1x how-to guide per week
        - 3x data-driven posts per week
        """,
        title="Q4 2025 Content Strategy Analysis",
        tags=["analysis", "content-strategy", "q4-2025"],
        content_type="analysis",
        author_id="strategy_agent"
    )

    result_json = tool_analysis.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Feature Enabled: {result.get('feature_enabled')}")
    print(f"   Message: {result['message']}")

    print("\n" + "=" * 80)
    print("✅ Test completed")
    print("\nNOTE: If all tests show 'skipped' status, the feature flag")
    print("      'rag.features.persist_strategies' is disabled (default).")
    print("      Enable it in config/settings.yaml to activate strategy indexing.")
