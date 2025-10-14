"""
RAG Index LinkedIn Tool

Mandatory linkedin_agent wrapper that calls the shared Hybrid RAG core library
to index LinkedIn posts and comments across all enabled sinks.

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


class RagIndexLinkedin(BaseTool):
    """
    Index LinkedIn content (posts, comments) to all enabled RAG sinks.

    Delegates to the shared core.rag.ingest_document module which handles:
    - Token-aware chunking with configurable overlap
    - Content hashing for deduplication
    - Parallel ingestion to OpenSearch, BigQuery, and Zep
    - Unified status reporting across all sinks

    Use this tool after fetching LinkedIn posts or comments to make them
    searchable for content strategy analysis and competitive intelligence.

    Architecture:
        - Thin wrapper: No RAG logic in agent tools
        - Delegates to core.rag.ingest_document.ingest()
        - Type set to "linkedin" for proper schema mapping
        - Feature-flagged: Sinks enabled/disabled via config
        - Idempotent: Safe to retry, deduplicates by content hash
    """

    post_or_comment_id: str = Field(
        ...,
        description="Unique LinkedIn post or comment identifier (required, e.g., LinkedIn URN or activity ID)"
    )

    text: str = Field(
        ...,
        description="Full LinkedIn post or comment text to index (required)"
    )

    author: Optional[str] = Field(
        None,
        description="Author name or handle (optional, e.g., '@alexhormozi' or 'Alex Hormozi')"
    )

    permalink: Optional[str] = Field(
        None,
        description="Permanent link to the LinkedIn content (optional)"
    )

    created_at: Optional[str] = Field(
        None,
        description="Creation timestamp (ISO 8601 format, optional)"
    )

    tags: Optional[list] = Field(
        None,
        description="List of tags for categorization (optional, e.g., ['linkedin', 'post', 'engagement'])"
    )

    content_type: Optional[str] = Field(
        "post",
        description="Content type: 'post' or 'comment' (default: 'post')"
    )

    engagement: Optional[dict] = Field(
        None,
        description="Engagement metrics (optional, e.g., {'likes': 245, 'comments': 18, 'shares': 12})"
    )

    def run(self) -> str:
        """
        Execute the RAG indexing operation for LinkedIn content.

        Returns:
            JSON string containing operation result:
            - status: "success", "partial", or "error"
            - linkedin_id: The LinkedIn content identifier
            - chunk_count: Number of chunks created
            - sinks: Per-sink results (opensearch, bigquery, zep)
            - message: Human-readable status message

        Example:
            >>> tool = RagIndexLinkedin(
            ...     post_or_comment_id="linkedin_post_123",
            ...     text="Key insights on SaaS scaling...",
            ...     author="@alexhormozi",
            ...     tags=["linkedin", "saas", "scaling"]
            ... )
            >>> result = tool.run()
            >>> data = json.loads(result)
            >>> data["status"]
            "success"
        """
        try:
            # Build payload for core library
            payload = {
                "document_id": self.post_or_comment_id,
                "document_text": self.text,
                "document_type": "linkedin",
                "source": "linkedin",
            }

            # Build title from author and content type
            if self.author:
                payload["title"] = f"LinkedIn {self.content_type} by {self.author}"
            else:
                payload["title"] = f"LinkedIn {self.content_type}"

            # Add optional fields if provided
            if self.permalink:
                payload["source_uri"] = self.permalink
            if self.tags:
                payload["tags"] = self.tags
            if self.created_at:
                payload["published_at"] = self.created_at

            # Add engagement metrics to tags if provided
            if self.engagement:
                if not payload.get("tags"):
                    payload["tags"] = []
                # Add engagement as metadata tags
                likes = self.engagement.get("likes", 0)
                comments = self.engagement.get("comments", 0)
                shares = self.engagement.get("shares", 0)
                payload["tags"].extend([
                    f"likes:{likes}",
                    f"comments:{comments}",
                    f"shares:{shares}"
                ])

            # Call core library
            print(f"=å Indexing LinkedIn {self.content_type} {self.post_or_comment_id} to Hybrid RAG...")
            result = ingest(payload)

            # Rename document_id to linkedin_id for clarity
            if "document_id" in result:
                result["linkedin_id"] = result.pop("document_id")

            # Log result
            if result.get("status") == "success":
                print(f"    Indexed {result.get('chunk_count', 0)} chunks successfully")
            elif result.get("status") == "partial":
                print(f"     Partial indexing: {result.get('message')}")
            else:
                print(f"   L Indexing failed: {result.get('message')}")


            # Optional: Write Firestore reference for audit/discovery (best-effort, never blocks)
            if result.get("status") in ["success", "partial"]:
                try:
                    from core.rag.refs import upsert_ref

                    # Build reference document
                    ref = {
                        "type": "linkedin",
                        "source_ref": self.post_or_comment_id,
                        "created_by_agent": "linkedin_agent",
                        "content_hashes": result.get("content_hashes", []),
                        "chunk_count": result.get("chunk_count", 0),
                        "total_tokens": result.get("total_tokens", 0),
                        "indexing_status": result.get("status"),
                        "sink_statuses": result.get("sink_statuses", {}),
                        "indexing_duration_ms": result.get("indexing_duration_ms", 0)
                    }

                    # Add optional metadata
                    if payload.get("title"):
                        ref["title"] = payload["title"]
                    if self.created_at:
                        ref["published_at"] = self.created_at
                    if payload.get("tags"):
                        ref["tags"] = payload["tags"]

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
                "message": f"RAG LinkedIn indexing failed: {str(e)}",
                "linkedin_id": self.post_or_comment_id
            }
            return json.dumps(error_result, indent=2)


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: RagIndexLinkedin Tool")
    print("=" * 80)

    # Test 1: LinkedIn post with complete metadata
    print("\n1. Testing with LinkedIn post:")
    tool = RagIndexLinkedin(
        post_or_comment_id="linkedin_post_abc123",
        text="""
        =€ Key lessons from scaling our SaaS to $10M ARR:

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

        Which of these resonates most with your experience? =G

        #SaaS #Entrepreneurship #Scaling
        """,
        author="@alexhormozi",
        permalink="https://www.linkedin.com/feed/update/urn:li:activity:123456",
        created_at="2025-10-08T14:30:00Z",
        tags=["linkedin", "saas", "scaling"],
        content_type="post",
        engagement={"likes": 245, "comments": 18, "shares": 12}
    )

    result_json = tool.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   LinkedIn ID: {result.get('linkedin_id')}")
    print(f"   Chunk Count: {result.get('chunk_count')}")
    print(f"   Message: {result['message']}")

    if 'sinks' in result:
        print("\n   Sink Results:")
        for sink_name, sink_result in result['sinks'].items():
            print(f"     {sink_name}: {sink_result.get('status')} - {sink_result.get('message')}")

    # Test 2: LinkedIn comment with minimal metadata
    print("\n2. Testing with LinkedIn comment (minimal):")
    tool_comment = RagIndexLinkedin(
        post_or_comment_id="linkedin_comment_xyz789",
        text="Great insights! We've seen similar results when focusing on unit economics first. CAC payback in 6 months has been our target.",
        author="Dan Martell",
        content_type="comment"
    )

    result_json = tool_comment.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   LinkedIn ID: {result.get('linkedin_id')}")
    print(f"   Message: {result['message']}")

    # Test 3: LinkedIn post without author (edge case)
    print("\n3. Testing without author (edge case):")
    tool_no_author = RagIndexLinkedin(
        post_or_comment_id="linkedin_post_456",
        text="Anonymous LinkedIn post content for testing indexing without author metadata."
    )

    result_json = tool_no_author.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   Message: {result['message']}")

    # Test 4: Long LinkedIn post with high engagement
    print("\n4. Testing long post with high engagement:")
    tool_long = RagIndexLinkedin(
        post_or_comment_id="linkedin_post_long_789",
        text="""
        After analyzing 500+ SaaS companies, here's what separates the winners from the rest:

        =Ê UNIT ECONOMICS MASTERY
        Winners know their numbers cold:
        - CAC: $1,200 (industry avg: $2,000)
        - LTV: $6,000 (industry avg: $4,000)
        - LTV:CAC ratio: 5:1 (industry avg: 2:1)
        - Payback period: 6 months (industry avg: 14 months)

        <¯ HIRING PHILOSOPHY
        A-players compound. B-players don't.
        - Rigorous interview process (5-7 rounds)
        - Practical assessments (real work samples)
        - Culture fit interviews with entire team
        - Scorecards for every role
        - Higher compensation = lower total cost

        ™ SYSTEMS THINKING
        Build systems before you need them:
        - Document every process
        - Create playbooks for key functions
        - Automate repetitive tasks
        - Build dashboards for visibility
        - Track leading indicators, not lagging

        =¡ KEY INSIGHT
        Most founders scale too early. They try to grow before they have the fundamentals right.
        Get your unit economics profitable, hire slowly but pay well, and build systems as you go.

        Then and only then should you think about scaling.

        What's been your biggest lesson in scaling? Drop a comment below =G
        """ * 2,  # Repeat to create longer text
        author="Alex Hormozi",
        permalink="https://www.linkedin.com/feed/update/urn:li:activity:789012",
        created_at="2025-10-10T16:45:00Z",
        tags=["linkedin", "saas", "scaling", "unit-economics", "hiring"],
        content_type="post",
        engagement={"likes": 1250, "comments": 87, "shares": 45}
    )

    result_json = tool_long.run()
    result = json.loads(result_json)

    print(f"   Status: {result['status']}")
    print(f"   LinkedIn ID: {result.get('linkedin_id')}")
    print(f"   Chunk Count: {result.get('chunk_count')}")
    print(f"   Engagement: likes=1250, comments=87, shares=45")

    print("\n" + "=" * 80)
    print(" Test completed")
