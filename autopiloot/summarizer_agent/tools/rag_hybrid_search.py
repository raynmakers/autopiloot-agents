"""
RAG Hybrid Search Tool

Mandatory summarizer_agent wrapper that calls the shared Hybrid RAG core library
for retrieval across all enabled sinks (OpenSearch, BigQuery, Zep) with RRF fusion.

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
    Perform hybrid retrieval search across all enabled RAG sinks with RRF fusion.

    Delegates to the shared core.rag.hybrid_retrieve module which handles:
    - Semantic search via Zep (vector embeddings + knowledge graph)
    - Keyword search via OpenSearch (BM25 + boolean filters)
    - SQL search via BigQuery (structured queries)
    - Reciprocal Rank Fusion (RRF) for result merging
    - Deduplication and provenance tracking
    - Observability and tracing

    Use this tool to search across all indexed content (transcripts, summaries,
    documents, LinkedIn posts) for strategic insights and content discovery.

    Architecture:
        - Thin wrapper: No retrieval logic in agent tools
        - Delegates to core.rag.hybrid_retrieve.search()
        - Configurable via settings.yaml (weights, fusion method)
        - Feature-flagged: Sinks enabled/disabled via config
        - Idempotent: Safe to retry, no side effects
    """

    query: str = Field(
        ...,
        description="Search query text (required)"
    )

    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional filters: channel_id, video_id, date_from, date_to, min_duration_sec, max_duration_sec"
    )

    limit: int = Field(
        default=20,
        description="Maximum number of results to return (default: 20)"
    )

    def run(self) -> str:
        """
        Execute hybrid search across all enabled RAG sinks.

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

        Example:
            >>> tool = RagHybridSearch(
            ...     query="How to scale SaaS business",
            ...     filters={"channel_id": "UC123"},
            ...     limit=10
            ... )
            >>> result = tool.run()
            >>> data = json.loads(result)
            >>> data["total_results"]
            10
            >>> data["results"][0]["score"]
            0.8542
        """
        try:
            # Call core library search function
            print(f"🔍 Hybrid Search: '{self.query}'")
            if self.filters:
                print(f"   Filters: {self.filters}")
            print(f"   Limit: {self.limit}")

            result = search(
                query=self.query,
                filters=self.filters,
                limit=self.limit
            )

            # Log result summary
            if result.get("error"):
                print(f"   ❌ Search failed: {result.get('message')}")
            elif result.get("total_results") == 0:
                print(f"   ⚪ No results found")
            else:
                print(f"   ✅ Found {result.get('total_results')} results")
                print(f"   Sources: {', '.join(result.get('sources_used', []))}")
                print(f"   Fusion: {result.get('fusion_method')}")
                print(f"   Latency: {result.get('latency_ms')}ms")

            return json.dumps(result, indent=2)

        except Exception as e:
            error_result = {
                "results": [],
                "total_results": 0,
                "sources_used": [],
                "error": "search_failed",
                "message": f"RAG hybrid search failed: {str(e)}",
                "query": self.query
            }
            return json.dumps(error_result, indent=2)


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: RagHybridSearch Tool")
    print("=" * 80)

    # Test 1: Basic search without filters
    print("\n1. Testing basic search:")
    tool = RagHybridSearch(
        query="How to hire A-players for a SaaS business"
    )

    result_json = tool.run()
    result = json.loads(result_json)

    print(f"   Query: {result.get('query', 'N/A')}")
    print(f"   Total Results: {result.get('total_results')}")
    print(f"   Sources Used: {result.get('sources_used', [])}")
    print(f"   Fusion Method: {result.get('fusion_method', 'N/A')}")
    print(f"   Latency: {result.get('latency_ms', 0)}ms")

    if result.get('results'):
        print(f"\n   First result:")
        first = result['results'][0]
        print(f"     chunk_id: {first.get('chunk_id')}")
        print(f"     title: {first.get('title')}")
        print(f"     score: {first.get('score', 0.0):.4f}")
        print(f"     sources: {first.get('sources', [])}")

    # Test 2: Search with channel filter
    print("\n2. Testing search with channel filter:")
    tool_filtered = RagHybridSearch(
        query="unit economics and customer acquisition cost",
        filters={"channel_id": "UCkP5J0pXI11VE81q7S7V1Jw"},
        limit=5
    )

    result_json = tool_filtered.run()
    result = json.loads(result_json)

    print(f"   Total Results: {result.get('total_results')}")
    print(f"   Sources Used: {result.get('sources_used', [])}")

    # Test 3: Search with date range filter
    print("\n3. Testing search with date range filter:")
    tool_date_filtered = RagHybridSearch(
        query="content strategy and LinkedIn",
        filters={
            "date_from": "2025-09-01T00:00:00Z",
            "date_to": "2025-10-31T23:59:59Z"
        },
        limit=10
    )

    result_json = tool_date_filtered.run()
    result = json.loads(result_json)

    print(f"   Total Results: {result.get('total_results')}")
    print(f"   Sources Used: {result.get('sources_used', [])}")
    print(f"   Coverage: {result.get('coverage', 0):.1f}%")

    # Test 4: Search with error handling
    print("\n4. Testing search with minimal query:")
    tool_minimal = RagHybridSearch(
        query="revenue",
        limit=3
    )

    result_json = tool_minimal.run()
    result = json.loads(result_json)

    print(f"   Total Results: {result.get('total_results')}")
    if result.get('error'):
        print(f"   Error: {result['message']}")

    print("\n" + "=" * 80)
    print("✅ Test completed")
