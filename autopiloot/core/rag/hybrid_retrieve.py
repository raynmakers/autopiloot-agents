"""
Hybrid Retrieval Module

Combines semantic (Zep), keyword (OpenSearch), and SQL (BigQuery) retrieval
with Reciprocal Rank Fusion (RRF) for optimal result ranking.
"""

import os
import sys
import time
from typing import List, Dict, Optional, Any
from datetime import datetime

# Add config and core directories to path
from env_loader import get_optional_env_var


def search(query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 20) -> dict:
    """
    Perform hybrid retrieval combining semantic, keyword, and SQL search.

    Args:
        query: Search query string
        filters: Optional filters:
            - channel_id: Filter by YouTube channel ID
            - video_id: Filter by specific video ID
            - date_from: Filter by minimum publication date (ISO 8601)
            - date_to: Filter by maximum publication date (ISO 8601)
            - min_duration_sec: Minimum video duration
            - max_duration_sec: Maximum video duration
        limit: Maximum number of results to return (default: 20)

    Returns:
        Dictionary containing:
        - results: List of ranked results with scores and provenance
        - total_results: Total number of results after fusion
        - sources_used: List of sources that contributed results
        - fusion_method: Fusion algorithm used ("rrf", "weighted", etc.)
        - latency_ms: Total retrieval latency in milliseconds
        - source_latencies: Per-source latency breakdown
        - coverage: Percentage of sources that returned results
        - trace_id: Unique trace identifier for observability

    Fusion Algorithm:
        - Uses Reciprocal Rank Fusion (RRF) by default
        - RRF formula: score = Σ(1 / (k + rank)) for each source
        - k parameter (default: 60) controls rank discount
        - Deduplicates by content_sha256 hash
        - Preserves provenance (which sources contributed each result)

    Example:
        >>> result = search(
        ...     query="How to increase revenue",
        ...     filters={"channel_id": "UC123"},
        ...     limit=10
        ... )
        >>> len(result["results"])
        10
        >>> result["results"][0]
        {
            "chunk_id": "abc123_chunk_0",
            "video_id": "abc123",
            "title": "Revenue Growth Strategies",
            "text": "Chunk text...",
            "score": 0.8542,
            "sources": ["zep", "opensearch"],
            "provenance": {
                "zep": {"score": 0.92, "rank": 1},
                "opensearch": {"score": 0.78, "rank": 3}
            }
        }
    """
    try:
        from rag.config import get_retrieval_config, is_sink_enabled, get_rag_value
        from rag.tracing import create_trace_id, emit_retrieval_event

        # Generate trace ID for observability
        trace_id = create_trace_id()
        start_time = time.time()

        # Get retrieval configuration
        config = get_retrieval_config()
        top_k = config.get("top_k", limit)
        timeout_ms = config.get("timeout_ms", 2000)
        weights = config.get("weights", {})

        # Track which sources are available
        available_sources = []
        source_results = {}
        source_latencies = {}

        # Query each enabled source
        # 1. Zep (semantic search)
        if is_sink_enabled("zep"):
            available_sources.append("zep")
            zep_start = time.time()
            zep_results = _query_zep(query, filters, top_k, timeout_ms / 1000.0)
            source_latencies["zep"] = int((time.time() - zep_start) * 1000)
            if zep_results.get("status") == "success":
                source_results["zep"] = zep_results.get("results", [])

        # 2. OpenSearch (keyword search)
        if is_sink_enabled("opensearch"):
            available_sources.append("opensearch")
            os_start = time.time()
            os_results = _query_opensearch(query, filters, top_k, timeout_ms / 1000.0)
            source_latencies["opensearch"] = int((time.time() - os_start) * 1000)
            if os_results.get("status") == "success":
                source_results["opensearch"] = os_results.get("results", [])

        # 3. BigQuery (SQL/structured search)
        if is_sink_enabled("bigquery"):
            available_sources.append("bigquery")
            bq_start = time.time()
            bq_results = _query_bigquery(query, filters, top_k, timeout_ms / 1000.0)
            source_latencies["bigquery"] = int((time.time() - bq_start) * 1000)
            if bq_results.get("status") == "success":
                source_results["bigquery"] = bq_results.get("results", [])

        # Check if any sources returned results
        if not source_results:
            return {
                "results": [],
                "total_results": 0,
                "sources_used": [],
                "fusion_method": "none",
                "latency_ms": int((time.time() - start_time) * 1000),
                "source_latencies": source_latencies,
                "coverage": 0.0,
                "trace_id": trace_id,
                "message": "No results from any source"
            }

        # Perform fusion
        fusion_method = get_rag_value("experiments.default_parameters.fusion.algorithm", "rrf")
        rrf_k = get_rag_value("experiments.default_parameters.fusion.rrf_k", 60)

        if fusion_method == "rrf":
            fused_results = _rrf_fusion(source_results, rrf_k)
        elif fusion_method == "weighted":
            fused_results = _weighted_fusion(source_results, weights)
        else:
            # Fallback: simple concatenation
            fused_results = _simple_fusion(source_results)

        # Limit results
        fused_results = fused_results[:limit]

        # Calculate coverage
        coverage = (len(source_results) / len(available_sources) * 100) if available_sources else 0

        # Emit observability event
        total_latency = int((time.time() - start_time) * 1000)
        try:
            emit_retrieval_event(
                trace_id=trace_id,
                query=query,
                filters=filters,
                total_results=len(fused_results),
                sources_used=list(source_results.keys()),
                latency_ms=total_latency,
                source_latencies=source_latencies,
                coverage=coverage
            )
        except Exception as e:
            # Don't fail retrieval if observability fails
            print(f"Warning: Failed to emit retrieval event: {str(e)}")

        return {
            "results": fused_results,
            "total_results": len(fused_results),
            "sources_used": list(source_results.keys()),
            "fusion_method": fusion_method,
            "latency_ms": total_latency,
            "source_latencies": source_latencies,
            "coverage": coverage,
            "trace_id": trace_id
        }

    except Exception as e:
        return {
            "results": [],
            "total_results": 0,
            "sources_used": [],
            "error": "retrieval_failed",
            "message": f"Hybrid retrieval failed: {str(e)}",
            "latency_ms": int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
        }


def _query_zep(query: str, filters: Optional[dict], top_k: int, timeout: float) -> dict:
    """Query Zep for semantic search results."""
    try:
        # Import Zep client
        import requests
        from rag.config import get_rag_value

        api_key = get_optional_env_var("ZEP_API_KEY")
        if not api_key:
            return {"status": "skipped", "message": "Zep API key not configured"}

        # Zep API endpoint
        base_url = "https://api.getzep.com/v2"

        # Query Zep for transcript search
        # Using memory search endpoint with collection filter
        collection_name = get_rag_value("zep.namespace.drive", "autopiloot-dev")

        response = requests.post(
            f"{base_url}/memory/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "query": query,
                "collection": collection_name,
                "limit": top_k
            },
            timeout=timeout
        )

        if response.status_code != 200:
            return {"status": "error", "message": f"Zep query failed: {response.status_code}"}

        data = response.json()
        results = []

        for item in data.get("results", []):
            results.append({
                "chunk_id": item.get("metadata", {}).get("chunk_id"),
                "video_id": item.get("metadata", {}).get("video_id"),
                "title": item.get("metadata", {}).get("title"),
                "text": item.get("content", ""),
                "score": item.get("score", 0.0),
                "content_sha256": item.get("metadata", {}).get("content_sha256"),
                "source": "zep"
            })

        return {"status": "success", "results": results}

    except Exception as e:
        return {"status": "error", "message": f"Zep query error: {str(e)}"}


def _query_opensearch(query: str, filters: Optional[dict], top_k: int, timeout: float) -> dict:
    """Query OpenSearch for keyword search results."""
    try:
        from opensearchpy import OpenSearch
        from rag.config import get_rag_value

        host = get_optional_env_var("OPENSEARCH_HOST")
        if not host:
            return {"status": "skipped", "message": "OpenSearch not configured"}

        api_key = get_optional_env_var("OPENSEARCH_API_KEY")
        username = get_optional_env_var("OPENSEARCH_USERNAME")
        password = get_optional_env_var("OPENSEARCH_PASSWORD")

        # Initialize client
        if host.startswith("http://") or host.startswith("https://"):
            use_ssl = host.startswith("https://")
            host_without_protocol = host.replace("https://", "").replace("http://", "")
        else:
            use_ssl = True
            host_without_protocol = host

        if ":" in host_without_protocol:
            hostname, port = host_without_protocol.rsplit(":", 1)
            port = int(port)
        else:
            hostname = host_without_protocol
            port = 443 if use_ssl else 9200

        if api_key:
            auth = ("api_key", api_key)
        elif username and password:
            auth = (username, password)
        else:
            return {"status": "error", "message": "OpenSearch authentication not configured"}

        client = OpenSearch(
            hosts=[{"host": hostname, "port": port}],
            http_auth=auth,
            use_ssl=use_ssl,
            verify_certs=get_rag_value("opensearch.connection.verify_certs", True),
            ssl_assert_hostname=False,
            ssl_show_warn=False,
            timeout=timeout
        )

        # Build query
        index_name = get_rag_value("opensearch.index_transcripts", "autopiloot_transcripts")

        query_body = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"text": query}}
                    ]
                }
            },
            "size": top_k
        }

        # Add filters
        if filters:
            filter_clauses = []
            if filters.get("channel_id"):
                filter_clauses.append({"term": {"channel_id": filters["channel_id"]}})
            if filters.get("video_id"):
                filter_clauses.append({"term": {"video_id": filters["video_id"]}})
            if filter_clauses:
                query_body["query"]["bool"]["filter"] = filter_clauses

        # Execute search
        response = client.search(index=index_name, body=query_body)

        results = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            results.append({
                "chunk_id": source.get("chunk_id"),
                "video_id": source.get("video_id"),
                "title": source.get("title"),
                "text": source.get("text"),
                "score": hit.get("_score", 0.0),
                "content_sha256": source.get("content_sha256"),
                "source": "opensearch"
            })

        return {"status": "success", "results": results}

    except Exception as e:
        return {"status": "error", "message": f"OpenSearch query error: {str(e)}"}


def _query_bigquery(query: str, filters: Optional[dict], top_k: int, timeout: float) -> dict:
    """Query BigQuery for SQL-based search results."""
    try:
        from google.cloud import bigquery
        from rag.config import get_rag_value

        project_id = get_optional_env_var("GCP_PROJECT_ID")
        if not project_id:
            return {"status": "skipped", "message": "BigQuery not configured"}

        client = bigquery.Client(project=project_id)

        dataset = get_rag_value("bigquery.dataset", "autopiloot")
        table = get_rag_value("bigquery.tables.transcript_chunks", "transcript_chunks")
        table_id = f"{project_id}.{dataset}.{table}"

        # Build SQL query with text search
        where_clauses = []
        params = []

        # Text search on snippet
        where_clauses.append("LOWER(text_snippet) LIKE LOWER(@query_pattern)")
        params.append(bigquery.ScalarQueryParameter("query_pattern", "STRING", f"%{query}%"))

        # Add filters
        if filters:
            if filters.get("channel_id"):
                where_clauses.append("channel_id = @channel_id")
                params.append(bigquery.ScalarQueryParameter("channel_id", "STRING", filters["channel_id"]))
            if filters.get("video_id"):
                where_clauses.append("video_id = @video_id")
                params.append(bigquery.ScalarQueryParameter("video_id", "STRING", filters["video_id"]))

        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"

        sql = f"""
            SELECT video_id, chunk_id, title, text_snippet as text, content_sha256
            FROM `{table_id}`
            WHERE {where_clause}
            LIMIT @top_k
        """
        params.append(bigquery.ScalarQueryParameter("top_k", "INT64", top_k))

        job_config = bigquery.QueryJobConfig(query_parameters=params)
        query_job = client.query(sql, job_config=job_config, timeout=timeout)
        rows = query_job.result()

        results = []
        for row in rows:
            results.append({
                "chunk_id": row.chunk_id,
                "video_id": row.video_id,
                "title": row.title,
                "text": row.text,
                "score": 1.0,  # BigQuery doesn't provide relevance scores
                "content_sha256": row.content_sha256,
                "source": "bigquery"
            })

        return {"status": "success", "results": results}

    except Exception as e:
        return {"status": "error", "message": f"BigQuery query error: {str(e)}"}


def _rrf_fusion(source_results: Dict[str, List[dict]], k: int = 60) -> List[dict]:
    """
    Perform Reciprocal Rank Fusion across multiple result sets.

    RRF formula: score = Σ(1 / (k + rank)) for each source
    """
    from rag.hashing import sha256_hex

    # Build unified result set with provenance
    unified = {}

    for source_name, results in source_results.items():
        for rank, result in enumerate(results, start=1):
            # Use content hash as deduplication key
            key = result.get("content_sha256") or sha256_hex(result.get("text", ""))

            if key not in unified:
                unified[key] = {
                    **result,
                    "rrf_score": 0.0,
                    "sources": [],
                    "provenance": {}
                }

            # Add RRF score contribution
            rrf_score = 1.0 / (k + rank)
            unified[key]["rrf_score"] += rrf_score

            # Track provenance
            if source_name not in unified[key]["sources"]:
                unified[key]["sources"].append(source_name)
            unified[key]["provenance"][source_name] = {
                "score": result.get("score", 0.0),
                "rank": rank
            }

    # Sort by RRF score descending
    ranked_results = sorted(unified.values(), key=lambda x: x["rrf_score"], reverse=True)

    # Clean up internal fields and rename rrf_score to score
    for result in ranked_results:
        result["score"] = result.pop("rrf_score")
        result.pop("content_sha256", None)

    return ranked_results


def _weighted_fusion(source_results: Dict[str, List[dict]], weights: Dict[str, float]) -> List[dict]:
    """Perform weighted fusion based on source weights."""
    from rag.hashing import sha256_hex

    unified = {}

    for source_name, results in source_results.items():
        weight = weights.get(source_name, 1.0)

        for result in results:
            key = result.get("content_sha256") or sha256_hex(result.get("text", ""))

            if key not in unified:
                unified[key] = {
                    **result,
                    "weighted_score": 0.0,
                    "sources": [],
                    "provenance": {}
                }

            # Add weighted score
            score = result.get("score", 0.0) * weight
            unified[key]["weighted_score"] += score

            if source_name not in unified[key]["sources"]:
                unified[key]["sources"].append(source_name)
            unified[key]["provenance"][source_name] = {"score": result.get("score", 0.0)}

    # Sort by weighted score
    ranked_results = sorted(unified.values(), key=lambda x: x["weighted_score"], reverse=True)

    for result in ranked_results:
        result["score"] = result.pop("weighted_score")
        result.pop("content_sha256", None)

    return ranked_results


def _simple_fusion(source_results: Dict[str, List[dict]]) -> List[dict]:
    """Simple concatenation fusion (fallback)."""
    from rag.hashing import sha256_hex

    unified = {}

    for source_name, results in source_results.items():
        for result in results:
            key = result.get("content_sha256") or sha256_hex(result.get("text", ""))

            if key not in unified:
                unified[key] = {
                    **result,
                    "sources": [source_name],
                    "provenance": {source_name: {"score": result.get("score", 0.0)}}
                }
            else:
                if source_name not in unified[key]["sources"]:
                    unified[key]["sources"].append(source_name)
                unified[key]["provenance"][source_name] = {"score": result.get("score", 0.0)}

    results = list(unified.values())
    for result in results:
        result.pop("content_sha256", None)

    return results


if __name__ == "__main__":
    print("="*80)
    print("TEST: Hybrid Retrieval Module")
    print("="*80)

    # Test search function
    print("\n1. Testing search() with sample query:")
    result = search(
        query="How to increase revenue",
        filters={"channel_id": "UC123"},
        limit=10
    )

    print(f"   Status: {result.get('status', 'success')}")
    print(f"   Total results: {result['total_results']}")
    print(f"   Sources used: {result['sources_used']}")
    print(f"   Fusion method: {result['fusion_method']}")
    print(f"   Latency: {result['latency_ms']}ms")
    print(f"   Coverage: {result['coverage']:.1f}%")

    if result['results']:
        print(f"\n   First result:")
        first = result['results'][0]
        print(f"     - chunk_id: {first.get('chunk_id')}")
        print(f"     - score: {first.get('score', 0.0):.4f}")
        print(f"     - sources: {first.get('sources')}")

    print("\n" + "="*80)
    print("✅ Test completed")
