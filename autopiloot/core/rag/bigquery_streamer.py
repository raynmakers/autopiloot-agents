"""
BigQuery Streamer Module

Provides SQL-based analytics storage for Hybrid RAG.
Stores metadata only (no full text) with optional preview snippet.
"""

import os
import sys
from typing import List, Dict
from datetime import datetime

# Add config directory to path
from env_loader import get_optional_env_var


def stream_transcript_chunks(rows: List[dict]) -> dict:
    """
    Stream transcript chunk metadata to BigQuery for SQL analytics.

    Args:
        rows: List of rows to insert, each containing:
            - video_id (str): YouTube video ID
            - chunk_id (str): Unique chunk identifier
            - title (str, optional): Video title
            - channel_id (str, optional): YouTube channel ID
            - published_at (str, optional): Publication timestamp (ISO 8601)
            - duration_sec (int, optional): Video duration
            - content_sha256 (str): Content hash for deduplication
            - tokens (int): Token count
            - text_snippet (str, optional): Preview text (≤256 chars, metadata only)

    Returns:
        Dictionary containing:
        - status: "streamed", "skipped", or "error"
        - dataset: BigQuery dataset name
        - table: BigQuery table name
        - inserted_count: Number of rows inserted
        - skipped_count: Number of rows skipped (already exist)
        - error_count: Number of errors
        - errors: List of error details (if any)
        - message: Human-readable status message

    Feature Flags:
        - rag.bigquery.enabled: Enable/disable BigQuery streaming
        - Returns {"status": "skipped"} if disabled or misconfigured

    Idempotency:
        - Queries existing chunk_ids before insertion
        - Only inserts new chunks (skips existing)

    Table Management:
        - Creates dataset/table automatically if missing
        - Schema: video_id, chunk_id, title, channel_id, published_at,
                  duration_sec, content_sha256, tokens, text_snippet

    Example:
        >>> rows = [
        ...     {
        ...         "video_id": "abc123",
        ...         "chunk_id": "abc123_chunk_0",
        ...         "content_sha256": "hash...",
        ...         "tokens": 487,
        ...         "text_snippet": "Preview text..."
        ...     }
        ... ]
        >>> result = stream_transcript_chunks(rows)
        >>> result["status"]
        "streamed"
    """
    try:
        # Import config here to avoid circular imports
        from rag.config import is_sink_enabled, get_rag_value

        # Check if BigQuery is enabled
        if not is_sink_enabled("bigquery"):
            return {
                "status": "skipped",
                "message": "BigQuery sink is disabled in configuration",
                "inserted_count": 0,
                "skipped_count": len(rows)
            }

        # Check credentials
        gcp_project = get_optional_env_var("GCP_PROJECT_ID")
        credentials_path = get_optional_env_var("GOOGLE_APPLICATION_CREDENTIALS")

        if not gcp_project or not credentials_path:
            return {
                "status": "skipped",
                "message": "BigQuery not configured (GCP_PROJECT_ID or GOOGLE_APPLICATION_CREDENTIALS not set)",
                "inserted_count": 0,
                "skipped_count": len(rows)
            }

        # Load configuration
        dataset_name = get_rag_value("bigquery.dataset", "autopiloot")
        table_name = get_rag_value("bigquery.tables.transcript_chunks", "transcript_chunks")
        location = get_rag_value("bigquery.location", "EU")

        # Initialize BigQuery client
        try:
            from google.cloud import bigquery
        except ImportError:
            return {
                "status": "error",
                "message": "BigQuery library not installed. Run: pip install google-cloud-bigquery",
                "inserted_count": 0,
                "error_count": len(rows)
            }

        client = bigquery.Client(project=gcp_project)

        # Ensure dataset exists
        dataset_id = f"{gcp_project}.{dataset_name}"
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = location
        dataset = client.create_dataset(dataset, exists_ok=True)

        # Ensure table exists
        table_id = f"{dataset_id}.{table_name}"
        table_result = _ensure_table_exists(client, table_id, bigquery)
        if not table_result["success"]:
            return {
                "status": "error",
                "message": f"Failed to create table: {table_result['error']}",
                "dataset": dataset_name,
                "table": table_name,
                "inserted_count": 0,
                "error_count": len(rows)
            }

        # Check for existing chunks (idempotency)
        video_ids = list(set(row.get("video_id") for row in rows if row.get("video_id")))
        existing_chunk_ids = _get_existing_chunk_ids(client, table_id, video_ids)

        # Filter out existing chunks
        new_rows = [row for row in rows if row.get("chunk_id") not in existing_chunk_ids]

        if not new_rows:
            return {
                "status": "skipped",
                "dataset": dataset_name,
                "table": table_name,
                "inserted_count": 0,
                "skipped_count": len(rows),
                "message": f"All {len(rows)} chunks already exist in BigQuery"
            }

        # Insert new rows
        errors = client.insert_rows_json(table_id, new_rows)

        if errors:
            return {
                "status": "partial",
                "dataset": dataset_name,
                "table": table_name,
                "inserted_count": len(new_rows) - len(errors),
                "skipped_count": len(existing_chunk_ids),
                "error_count": len(errors),
                "errors": errors[:10],  # Limit error details
                "message": f"Inserted {len(new_rows) - len(errors)}/{len(new_rows)} new chunks with {len(errors)} errors"
            }

        return {
            "status": "streamed",
            "dataset": dataset_name,
            "table": table_name,
            "inserted_count": len(new_rows),
            "skipped_count": len(existing_chunk_ids),
            "message": f"Streamed {len(new_rows)} new chunks to BigQuery (skipped {len(existing_chunk_ids)} existing)"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"BigQuery streaming failed: {str(e)}",
            "inserted_count": 0,
            "error_count": len(rows) if rows else 0
        }


def _ensure_table_exists(client, table_id: str, bigquery_module) -> dict:
    """Create table if not exists with proper schema."""
    try:
        # Check if table exists
        try:
            client.get_table(table_id)
            return {"success": True, "status": "exists"}
        except:
            pass

        # Define schema (metadata only, no full text)
        schema = [
            bigquery_module.SchemaField("video_id", "STRING", mode="REQUIRED"),
            bigquery_module.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
            bigquery_module.SchemaField("title", "STRING", mode="NULLABLE"),
            bigquery_module.SchemaField("channel_id", "STRING", mode="NULLABLE"),
            bigquery_module.SchemaField("published_at", "TIMESTAMP", mode="NULLABLE"),
            bigquery_module.SchemaField("duration_sec", "INT64", mode="NULLABLE"),
            bigquery_module.SchemaField("content_sha256", "STRING", mode="NULLABLE"),
            bigquery_module.SchemaField("tokens", "INT64", mode="NULLABLE"),
            bigquery_module.SchemaField("text_snippet", "STRING", mode="NULLABLE"),
        ]

        table = bigquery_module.Table(table_id, schema=schema)
        table = client.create_table(table)
        return {"success": True, "status": "created"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_existing_chunk_ids(client, table_id: str, video_ids: List[str]) -> set:
    """Query existing chunk_ids for videos to prevent duplicates."""
    try:
        if not video_ids:
            return set()

        query = f"""
            SELECT chunk_id
            FROM `{table_id}`
            WHERE video_id IN UNNEST(@video_ids)
        """

        job_config = client.query_job_config()
        job_config.query_parameters = [
            client.query_parameter_from_value("video_ids", video_ids, "ARRAY<STRING>")
        ]

        query_job = client.query(query, job_config=job_config)
        results = query_job.result()

        return {row.chunk_id for row in results}

    except Exception:
        # If query fails, return empty set
        return set()


if __name__ == "__main__":
    print("="*80)
    print("TEST: BigQuery Streamer Module")
    print("="*80)

    # Sample rows
    sample_rows = [
        {
            "video_id": "abc123",
            "chunk_id": "abc123_chunk_0",
            "title": "How to Build a SaaS Business",
            "channel_id": "UC123",
            "published_at": "2025-10-08T12:00:00Z",
            "duration_sec": 1200,
            "content_sha256": "hash123",
            "tokens": 487,
            "text_snippet": "This is a preview..."
        },
        {
            "video_id": "abc123",
            "chunk_id": "abc123_chunk_1",
            "title": "How to Build a SaaS Business",
            "channel_id": "UC123",
            "published_at": "2025-10-08T12:00:00Z",
            "duration_sec": 1200,
            "content_sha256": "hash456",
            "tokens": 512,
            "text_snippet": "Another preview..."
        }
    ]

    print("\n1. Testing stream_transcript_chunks():")
    result = stream_transcript_chunks(sample_rows)
    print(f"   Status: {result['status']}")
    print(f"   Message: {result['message']}")
    print(f"   Inserted: {result.get('inserted_count', 0)}")
    print(f"   Skipped: {result.get('skipped_count', 0)}")

    print("\n" + "="*80)
    print("✅ Test completed")
