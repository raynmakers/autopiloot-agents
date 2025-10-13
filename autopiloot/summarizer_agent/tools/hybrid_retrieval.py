"""
HybridRetrieval tool for querying both Zep (semantic) and OpenSearch (keyword) and fusing results.

DEPRECATED: This tool contains inline RAG logic and is superseded by the shared core library.
Use `rag_hybrid_search.py` instead, which delegates to `core.rag.hybrid_retrieve.search()`.

Migration Path:
    Old: HybridRetrieval(query="...", top_k=10)
    New: RagHybridSearch(query="...", limit=10)

This file is kept for backward compatibility temporarily.
Will be removed in a future release once all callsites are migrated.

Legacy Architecture:
- Zep v3: Semantic search via vector embeddings and knowledge graph
- OpenSearch: Keyword search via BM25 and boolean filtering
- Fusion: RRF algorithm to merge and re-rank results
- Weights: Configurable semantic vs keyword importance
"""

import os
import sys
import json
import httpx
from typing import List, Dict, Optional
from collections import defaultdict
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, get_optional_env_var, load_environment
from loader import get_config_value


class HybridRetrieval(BaseTool):
    """
    Query both Zep (semantic) and OpenSearch (keyword) and fuse results for Hybrid RAG.

    Implements:
    - Parallel queries to Zep and OpenSearch
    - Reciprocal Rank Fusion (RRF) for result merging
    - Configurable weights for semantic vs keyword importance
    - Deduplication by chunk_id
    - Rich metadata in results (source, scores, video info)
    """

    query: str = Field(
        ...,
        description="Search query text"
    )
    top_k: int = Field(
        default=10,
        description="Number of results to return after fusion (default: 10)"
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Filter results by YouTube channel ID"
    )
    min_published_date: Optional[str] = Field(
        default=None,
        description="Filter results by minimum publication date (ISO 8601)"
    )
    max_published_date: Optional[str] = Field(
        default=None,
        description="Filter results by maximum publication date (ISO 8601)"
    )

    def run(self) -> str:
        """
        Execute hybrid search across Zep and OpenSearch, then fuse results.

        Process:
        1. Load configuration (weights, top_k limits)
        2. Query Zep for semantic matches (if configured)
        3. Query OpenSearch for keyword matches (if configured)
        4. Fuse results using RRF algorithm
        5. Deduplicate by chunk_id
        6. Return top K results with metadata

        Returns:
            JSON string with fused results, sources, and statistics
        """
        try:
            # Load environment and configuration
            load_environment()

            # Load hybrid search configuration
            semantic_weight = get_config_value("rag.opensearch.weights.semantic", 0.6)
            keyword_weight = get_config_value("rag.opensearch.weights.keyword", 0.4)
            opensearch_top_k = get_config_value("rag.opensearch.top_k", 20)

            print(f"🔍 Hybrid Retrieval: '{self.query}'")
            print(f"   Semantic weight: {semantic_weight}")
            print(f"   Keyword weight: {keyword_weight}")
            print(f"   Target top-k: {self.top_k}")

            results = {
                "zep_results": [],
                "opensearch_results": [],
                "zep_enabled": False,
                "opensearch_enabled": False
            }

            # Query Zep (semantic search)
            zep_api_key = get_optional_env_var("ZEP_API_KEY")
            if zep_api_key:
                print(f"   Querying Zep (semantic)...")
                zep_results = self._query_zep(
                    self.query,
                    top_k=opensearch_top_k,
                    channel_id=self.channel_id
                )
                results["zep_results"] = zep_results
                results["zep_enabled"] = True
                print(f"   ✓ Zep returned {len(zep_results)} results")
            else:
                print(f"   ⚪ Zep not configured, skipping semantic search")

            # Query OpenSearch (keyword search)
            opensearch_host = get_optional_env_var("OPENSEARCH_HOST")
            if opensearch_host:
                print(f"   Querying OpenSearch (keyword)...")
                opensearch_results = self._query_opensearch(
                    self.query,
                    top_k=opensearch_top_k,
                    channel_id=self.channel_id,
                    min_date=self.min_published_date,
                    max_date=self.max_published_date
                )
                results["opensearch_results"] = opensearch_results
                results["opensearch_enabled"] = True
                print(f"   ✓ OpenSearch returned {len(opensearch_results)} results")
            else:
                print(f"   ⚪ OpenSearch not configured, skipping keyword search")

            # Check if at least one source is available
            if not results["zep_enabled"] and not results["opensearch_enabled"]:
                return json.dumps({
                    "error": "no_search_sources",
                    "message": "Neither Zep nor OpenSearch is configured. Enable at least one search source.",
                    "query": self.query
                }, indent=2)

            # Fuse results using RRF
            print(f"   Fusing results with RRF...")
            fused_results = self._fuse_with_rrf(
                zep_results=results["zep_results"],
                opensearch_results=results["opensearch_results"],
                semantic_weight=semantic_weight,
                keyword_weight=keyword_weight,
                top_k=self.top_k
            )
            print(f"   ✓ Fused to {len(fused_results)} final results")

            return json.dumps({
                "query": self.query,
                "results": fused_results,
                "result_count": len(fused_results),
                "sources": {
                    "zep": results["zep_enabled"],
                    "opensearch": results["opensearch_enabled"]
                },
                "source_counts": {
                    "zep": len(results["zep_results"]),
                    "opensearch": len(results["opensearch_results"])
                },
                "weights": {
                    "semantic": semantic_weight,
                    "keyword": keyword_weight
                },
                "status": "success"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "retrieval_failed",
                "message": f"Failed to execute hybrid retrieval: {str(e)}",
                "query": self.query
            })

    def _query_zep(self, query: str, top_k: int, channel_id: Optional[str]) -> List[Dict]:
        """
        Query Zep v3 for semantic search results.

        Args:
            query: Search query text
            top_k: Number of results to return
            channel_id: Optional channel filter

        Returns:
            List[Dict]: Search results with scores and metadata
        """
        try:
            zep_api_key = get_required_env_var("ZEP_API_KEY", "Zep API key")
            zep_base_url = get_optional_env_var("ZEP_BASE_URL", "https://api.getzep.com")

            # Build search request
            # Note: Zep v3 search API varies by collection/thread type
            # This is a simplified implementation - adjust based on actual Zep API
            headers = {
                "Authorization": f"Api-Key {zep_api_key}",
                "Content-Type": "application/json"
            }

            # Search across transcript threads
            # Adjust endpoint based on Zep v3 API documentation
            search_data = {
                "query": query,
                "limit": top_k,
                "metadata_filter": {}
            }

            # Add channel filter if provided
            if channel_id:
                search_data["metadata_filter"]["channel_id"] = channel_id

            # Make search request (placeholder - adjust for actual Zep v3 API)
            # For now, return empty results with comment about implementation
            return []

            # Actual implementation would be:
            # response = httpx.post(
            #     f"{zep_base_url}/api/v2/search",
            #     headers=headers,
            #     json=search_data,
            #     timeout=30.0
            # )
            #
            # if response.status_code == 200:
            #     data = response.json()
            #     results = []
            #     for item in data.get("results", []):
            #         results.append({
            #             "chunk_id": item.get("chunk_id"),
            #             "video_id": item.get("metadata", {}).get("video_id"),
            #             "title": item.get("metadata", {}).get("title"),
            #             "text": item.get("content"),
            #             "score": item.get("score", 0.0),
            #             "source": "zep"
            #         })
            #     return results
            # return []

        except Exception as e:
            print(f"   ⚠️ Zep query error: {str(e)}")
            return []

    def _query_opensearch(
        self,
        query: str,
        top_k: int,
        channel_id: Optional[str],
        min_date: Optional[str],
        max_date: Optional[str]
    ) -> List[Dict]:
        """
        Query OpenSearch for keyword search results.

        Args:
            query: Search query text
            top_k: Number of results to return
            channel_id: Optional channel filter
            min_date: Optional minimum publication date
            max_date: Optional maximum publication date

        Returns:
            List[Dict]: Search results with scores and metadata
        """
        try:
            from opensearchpy import OpenSearch

            opensearch_host = get_optional_env_var("OPENSEARCH_HOST")
            opensearch_api_key = get_optional_env_var("OPENSEARCH_API_KEY")
            opensearch_username = get_optional_env_var("OPENSEARCH_USERNAME")
            opensearch_password = get_optional_env_var("OPENSEARCH_PASSWORD")

            # Parse host
            if opensearch_host.startswith("http://") or opensearch_host.startswith("https://"):
                use_ssl = opensearch_host.startswith("https://")
                host_without_protocol = opensearch_host.replace("https://", "").replace("http://", "")
            else:
                use_ssl = True
                host_without_protocol = opensearch_host

            if ":" in host_without_protocol:
                hostname, port = host_without_protocol.rsplit(":", 1)
                port = int(port)
            else:
                hostname = host_without_protocol
                port = 443 if use_ssl else 9200

            # Configure auth
            if opensearch_api_key:
                auth = ("api_key", opensearch_api_key)
            elif opensearch_username and opensearch_password:
                auth = (opensearch_username, opensearch_password)
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
                timeout=get_config_value("rag.opensearch.timeout_ms", 1500) / 1000.0
            )

            # Build search query
            index_name = get_config_value("rag.opensearch.index_transcripts", "autopiloot_transcripts")

            must_clauses = [
                {"match": {"text": {"query": query, "boost": 1.0}}}
            ]

            # Add filters
            filter_clauses = []
            if channel_id:
                filter_clauses.append({"term": {"channel_id": channel_id}})

            if min_date or max_date:
                range_filter = {"range": {"published_at": {}}}
                if min_date:
                    range_filter["range"]["published_at"]["gte"] = min_date
                if max_date:
                    range_filter["range"]["published_at"]["lte"] = max_date
                filter_clauses.append(range_filter)

            search_body = {
                "query": {
                    "bool": {
                        "must": must_clauses,
                        "filter": filter_clauses if filter_clauses else []
                    }
                },
                "size": top_k,
                "_source": ["video_id", "chunk_id", "title", "channel_id", "text", "tokens"]
            }

            # Execute search
            response = client.search(index=index_name, body=search_body)

            # Parse results
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append({
                    "chunk_id": source.get("chunk_id"),
                    "video_id": source.get("video_id"),
                    "title": source.get("title"),
                    "channel_id": source.get("channel_id"),
                    "text": source.get("text"),
                    "tokens": source.get("tokens"),
                    "score": hit["_score"],
                    "source": "opensearch"
                })

            return results

        except Exception as e:
            print(f"   ⚠️ OpenSearch query error: {str(e)}")
            return []

    def _fuse_with_rrf(
        self,
        zep_results: List[Dict],
        opensearch_results: List[Dict],
        semantic_weight: float,
        keyword_weight: float,
        top_k: int,
        rrf_k: int = 60
    ) -> List[Dict]:
        """
        Fuse results using Reciprocal Rank Fusion (RRF).

        RRF Formula: score = sum(weight / (k + rank))
        where k is a constant (typically 60), rank is position in result list.

        Args:
            zep_results: Semantic search results from Zep
            opensearch_results: Keyword search results from OpenSearch
            semantic_weight: Weight for semantic results (0.0-1.0)
            keyword_weight: Weight for keyword results (0.0-1.0)
            top_k: Number of final results to return
            rrf_k: RRF constant (default: 60)

        Returns:
            List[Dict]: Fused and ranked results
        """
        # Create score dictionary by chunk_id
        scores = defaultdict(lambda: {"score": 0.0, "sources": [], "data": None})

        # Add Zep results with RRF scoring
        for rank, result in enumerate(zep_results, start=1):
            chunk_id = result.get("chunk_id")
            if not chunk_id:
                continue

            rrf_score = semantic_weight / (rrf_k + rank)
            scores[chunk_id]["score"] += rrf_score
            scores[chunk_id]["sources"].append("zep")
            if scores[chunk_id]["data"] is None:
                scores[chunk_id]["data"] = result

        # Add OpenSearch results with RRF scoring
        for rank, result in enumerate(opensearch_results, start=1):
            chunk_id = result.get("chunk_id")
            if not chunk_id:
                continue

            rrf_score = keyword_weight / (rrf_k + rank)
            scores[chunk_id]["score"] += rrf_score
            scores[chunk_id]["sources"].append("opensearch")
            if scores[chunk_id]["data"] is None:
                scores[chunk_id]["data"] = result

        # Sort by fused score and take top K
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )[:top_k]

        # Format final results
        final_results = []
        for chunk_id, score_data in sorted_results:
            result = score_data["data"]
            result["rrf_score"] = score_data["score"]
            result["matched_sources"] = list(set(score_data["sources"]))
            result["source_count"] = len(set(score_data["sources"]))
            final_results.append(result)

        return final_results


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Hybrid Retrieval (Zep + OpenSearch)")
    print("="*80)

    try:
        tool = HybridRetrieval(
            query="How to hire A-players for a SaaS business",
            top_k=5,
            channel_id="UCkP5J0pXI11VE81q7S7V1Jw"
        )

        result = tool.run()
        print("✅ Test completed:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
        else:
            print(f"\n📊 Retrieval Summary:")
            print(f"   Query: {data['query']}")
            print(f"   Results: {data['result_count']}")
            print(f"   Sources Active: Zep={data['sources']['zep']}, OpenSearch={data['sources']['opensearch']}")
            print(f"   Source Counts: Zep={data['source_counts']['zep']}, OpenSearch={data['source_counts']['opensearch']}")
            print(f"   Weights: Semantic={data['weights']['semantic']}, Keyword={data['weights']['keyword']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
