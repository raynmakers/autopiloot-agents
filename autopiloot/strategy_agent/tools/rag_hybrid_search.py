"""
RAG Hybrid Search Tool

Mandatory strategy_agent wrapper that calls the shared Hybrid RAG core library
to perform hybrid retrieval combining semantic (Zep), keyword (OpenSearch),
and SQL (BigQuery) search with Reciprocal Rank Fusion.

This tool is discoverable by Agency Swarm and provides strict Pydantic validation.
"""

import os
import sys
import json
from typing import Optional, Dict, Any
from pydantic import Field

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from agency_swarm.tools import BaseTool
from core.rag.hybrid_retrieve import search


class RagHybridSearch(BaseTool):
    """
    Perform hybrid retrieval across semantic, keyword, and SQL sources.

    Delegates to the shared core.rag.hybrid_retrieve module which handles:
    - Parallel querying of Zep (semantic), OpenSearch (keyword), BigQuery (SQL)
    - Reciprocal Rank Fusion (RRF) for result ranking
    - Content deduplication by hash
    - Provenance tracking (which sources contributed each result)
    - Comprehensive observability and latency tracking

    Use this tool when you need to search across all indexed content
    (transcripts, documents, summaries) for strategic content analysis.
    """

    query: str = Field(
        ...,
        description="Search query string (required)"
    )

    filters: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Optional filters dictionary. Supported filters: "
            "channel_id (str), video_id (str), date_from (ISO 8601), "
            "date_to (ISO 8601), min_duration_sec (int), max_duration_sec (int)"
        )
    )

    limit: int = Field(
        20,
        description="Maximum number of results to return (default: 20)"
    )

    def run(self) -> str:
        """
        Execute the hybrid search operation.

        Returns:
            JSON string containing search results:
            - results: List of ranked results with scores and provenance
            - total_results: Total number of results after fusion
            - sources_used: List of sources that contributed results
            - fusion_method: Fusion algorithm used ("rrf", "weighted", etc.)
            - latency_ms: Total retrieval latency in milliseconds
            - source_latencies: Per-source latency breakdown
            - coverage: Percentage of sources that returned results
            - trace_id: Unique trace identifier for observability
        """
        try:
            # Call core library
            print(f"🔍 Searching across Hybrid RAG: '{self.query[:50]}...'")
            result = search(
                query=self.query,
                filters=self.filters,
                limit=self.limit
            )

            # Log result summary
            if result.get("total_results", 0) > 0:
                print(f"   ✅ Found {result['total_results']} results from {len(result.get('sources_used', []))} sources")
                print(f"   ⚡ Latency: {result.get('latency_ms', 0)}ms | Coverage: {result.get('coverage', 0):.1f}%")
            else:
                print(f"   ⚪ No results found")

            return json.dumps(result, indent=2)

        except Exception as e:
            error_result = {
                "results": [],
                "total_results": 0,
                "sources_used": [],
                "error": "hybrid_search_failed",
                "message": f"Hybrid search failed: {str(e)}",
                "query": self.query
            }
            return json.dumps(error_result, indent=2)


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: RagHybridSearch Tool")
    print("=" * 80)

    # Test 1: Simple search without filters
    print("\n1. Testing basic search:")
    tool = RagHybridSearch(
        query="How to increase revenue and scale SaaS business",
        limit=10
    )

    result_json = tool.run()
    result = json.loads(result_json)

    print(f"   Total results: {result.get('total_results', 0)}")
    print(f"   Sources used: {result.get('sources_used', [])}")
    print(f"   Fusion method: {result.get('fusion_method', 'unknown')}")
    print(f"   Latency: {result.get('latency_ms', 0)}ms")
    print(f"   Coverage: {result.get('coverage', 0):.1f}%")

    if result.get('results'):
        print("\n   First result:")
        first = result['results'][0]
        print(f"     - chunk_id: {first.get('chunk_id', 'N/A')}")
        print(f"     - score: {first.get('score', 0.0):.4f}")
        print(f"     - sources: {first.get('sources', [])}")
        print(f"     - text preview: {first.get('text', '')[:80]}...")

    # Test 2: Search with channel filter
    print("\n2. Testing search with channel filter:")
    tool_filtered = RagHybridSearch(
        query="unit economics CAC LTV",
        filters={"channel_id": "UC123"},
        limit=5
    )

    result_json = tool_filtered.run()
    result = json.loads(result_json)

    print(f"   Total results: {result.get('total_results', 0)}")
    print(f"   Applied filters: channel_id=UC123")

    # Test 3: Search with date range filter
    print("\n3. Testing search with date range:")
    tool_date_range = RagHybridSearch(
        query="business strategy",
        filters={
            "date_from": "2025-09-01T00:00:00Z",
            "date_to": "2025-10-31T23:59:59Z"
        },
        limit=5
    )

    result_json = tool_date_range.run()
    result = json.loads(result_json)

    print(f"   Total results: {result.get('total_results', 0)}")
    print(f"   Applied filters: date range Sep-Oct 2025")

    # Test 4: Search with duration filter
    print("\n4. Testing search with duration filter:")
    tool_duration = RagHybridSearch(
        query="content strategy",
        filters={
            "min_duration_sec": 600,  # At least 10 minutes
            "max_duration_sec": 3600  # At most 60 minutes
        },
        limit=5
    )

    result_json = tool_duration.run()
    result = json.loads(result_json)

    print(f"   Total results: {result.get('total_results', 0)}")
    print(f"   Applied filters: 10-60 minute videos")

    # Test 5: Empty query (edge case)
    print("\n5. Testing empty query (edge case):")
    tool_empty = RagHybridSearch(
        query="",
        limit=5
    )

    result_json = tool_empty.run()
    result = json.loads(result_json)

    print(f"   Total results: {result.get('total_results', 0)}")
    if result.get('error'):
        print(f"   Error: {result.get('message')}")

    print("\n" + "=" * 80)
    print("✅ Test completed")
