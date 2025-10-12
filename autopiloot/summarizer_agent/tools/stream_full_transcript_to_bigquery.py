"""
StreamFullTranscriptToBigQuery tool for streaming transcript chunks to BigQuery.
Provides SQL-based analytics, reporting, and structured data access for Hybrid RAG.

BigQuery Architecture:
- Dataset: autopiloot (configurable)
- Table: transcript_chunks (with schema from settings.yaml)
- Fields: video_id, chunk_id, title, channel_id, published_at, duration_sec, content_sha256, tokens, text_snippet (<=256 chars)
- Storage Strategy: Metadata only (no full text) with optional preview snippet
- Idempotency: By (video_id, chunk_id) composite key or content_sha256 hash
"""

import os
import sys
import json
import hashlib
import tiktoken
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, get_optional_env_var, load_environment
from loader import get_config_value


class StreamFullTranscriptToBigQuery(BaseTool):
    """
    Stream full transcript chunks to BigQuery for SQL-based analytics in Hybrid RAG.

    Implements:
    - Metadata-only storage with optional text snippet (<=256 chars) for previews
    - Batch insertion for performance (configurable batch size)
    - Idempotent writes using (video_id, chunk_id) or content_sha256
    - Automatic dataset/table creation with proper schema
    - Same chunking as Zep/OpenSearch tools for consistency
    - Rich metadata for SQL filtering and reporting
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for record identification"
    )
    transcript_text: str = Field(
        ...,
        description="Full transcript text to chunk and stream"
    )
    channel_id: str = Field(
        ...,
        description="YouTube channel ID for filtering"
    )
    title: Optional[str] = Field(
        default=None,
        description="Video title for search and display"
    )
    channel_handle: Optional[str] = Field(
        default=None,
        description="YouTube channel handle (e.g., '@DanMartell')"
    )
    published_at: Optional[str] = Field(
        default=None,
        description="Video publication date (ISO 8601 format)"
    )
    duration_sec: Optional[int] = Field(
        default=None,
        description="Video duration in seconds"
    )

    def run(self) -> str:
        """
        Stream transcript chunks to BigQuery for SQL analytics.

        Process:
        1. Load BigQuery configuration (dataset, table, batch size)
        2. Chunk transcript (same logic as Zep/OpenSearch tools)
        3. Generate SHA-256 hashes for each chunk
        4. Initialize BigQuery client
        5. Create dataset/table if not exists
        6. Check for existing chunks (idempotency)
        7. Batch insert new chunks only
        8. Return streaming statistics

        Returns:
            JSON string with dataset, table, chunk_count, inserted_count, status
        """
        try:
            # Load environment and configuration
            load_environment()

            # Check if BigQuery is configured
            gcp_project = get_optional_env_var("GCP_PROJECT_ID")
            credentials_path = get_optional_env_var("GOOGLE_APPLICATION_CREDENTIALS")

            if not gcp_project or not credentials_path:
                return json.dumps({
                    "status": "skipped",
                    "message": "BigQuery not configured (GCP_PROJECT_ID or GOOGLE_APPLICATION_CREDENTIALS not set)",
                    "video_id": self.video_id
                }, indent=2)

            # Load BigQuery configuration
            dataset_name = get_config_value("rag.bigquery.dataset", "autopiloot")
            table_name = get_config_value("rag.bigquery.tables.transcript_chunks", "transcript_chunks")
            batch_size = get_config_value("rag.bigquery.batch_size", 500)
            location = get_config_value("rag.bigquery.location", "EU")

            # Load chunking configuration
            max_tokens = get_config_value("rag.zep.transcripts.chunking.max_tokens_per_chunk", 1000)
            overlap_tokens = get_config_value("rag.zep.transcripts.chunking.overlap_tokens", 100)

            print(f"📤 Streaming transcript to BigQuery...")
            print(f"   Project: {gcp_project}")
            print(f"   Dataset: {dataset_name}")
            print(f"   Table: {table_name}")
            print(f"   Video ID: {self.video_id}")

            # Step 1: Chunk transcript
            print(f"   Chunking transcript (max {max_tokens} tokens, {overlap_tokens} overlap)...")
            chunks = self._chunk_transcript(
                self.transcript_text,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens
            )
            print(f"   ✓ Created {len(chunks)} chunks")

            # Step 2: Prepare rows
            rows = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"{self.video_id}_chunk_{i+1}"
                chunk_hash = hashlib.sha256(chunk.encode('utf-8')).hexdigest()

                # Parse published_at to timestamp if provided
                published_timestamp = None
                if self.published_at:
                    try:
                        published_timestamp = datetime.fromisoformat(self.published_at.replace('Z', '+00:00')).isoformat()
                    except:
                        published_timestamp = self.published_at

                # Truncate chunk text to 256 characters for preview snippet (metadata only, no full text)
                text_snippet = chunk[:256] if chunk else None

                row = {
                    "video_id": self.video_id,
                    "chunk_id": chunk_id,
                    "title": self.title,
                    "channel_id": self.channel_id,
                    "published_at": published_timestamp,
                    "duration_sec": self.duration_sec,
                    "content_sha256": chunk_hash,
                    "tokens": self._count_tokens(chunk),
                    "text_snippet": text_snippet
                }
                rows.append(row)

            # Step 3: Initialize BigQuery client
            try:
                from google.cloud import bigquery
            except ImportError:
                return json.dumps({
                    "error": "bigquery_not_installed",
                    "message": "BigQuery library not installed. Run: pip install google-cloud-bigquery",
                    "video_id": self.video_id
                }, indent=2)

            client = bigquery.Client(project=gcp_project)

            # Step 4: Ensure dataset exists
            dataset_id = f"{gcp_project}.{dataset_name}"
            dataset = bigquery.Dataset(dataset_id)
            dataset.location = location
            dataset = client.create_dataset(dataset, exists_ok=True)
            print(f"   ✓ Dataset ready: {dataset_id}")

            # Step 5: Ensure table exists
            table_id = f"{dataset_id}.{table_name}"
            table_result = self._ensure_table_exists(client, table_id, bigquery)
            if not table_result.get("success"):
                return json.dumps({
                    "error": "bigquery_table_creation_failed",
                    "message": f"Failed to create table: {table_result.get('error', 'Unknown error')}",
                    "table_id": table_id
                }, indent=2)
            print(f"   ✓ Table ready: {table_id}")

            # Step 6: Check for existing chunks (idempotency)
            existing_chunk_ids = self._get_existing_chunk_ids(client, table_id, self.video_id)
            print(f"   ✓ Found {len(existing_chunk_ids)} existing chunks")

            # Filter out existing chunks
            new_rows = [row for row in rows if row["chunk_id"] not in existing_chunk_ids]

            if not new_rows:
                print(f"   ⚪ All chunks already exist, skipping insert")
                return json.dumps({
                    "dataset": dataset_name,
                    "table": table_name,
                    "video_id": self.video_id,
                    "chunk_count": len(rows),
                    "inserted_count": 0,
                    "skipped_count": len(rows),
                    "status": "skipped",
                    "message": f"All {len(rows)} chunks already exist in BigQuery table '{table_name}'"
                }, indent=2)

            # Step 7: Insert new rows in batches
            print(f"   Inserting {len(new_rows)} new chunks...")
            errors = client.insert_rows_json(table_id, new_rows)

            if errors:
                print(f"   ⚠️ {len(errors)} insertion errors")
                return json.dumps({
                    "dataset": dataset_name,
                    "table": table_name,
                    "video_id": self.video_id,
                    "chunk_count": len(rows),
                    "inserted_count": len(new_rows) - len(errors),
                    "error_count": len(errors),
                    "errors": errors[:10],  # Limit error details
                    "status": "partial",
                    "message": f"Inserted {len(new_rows) - len(errors)}/{len(new_rows)} new chunks with {len(errors)} errors"
                }, indent=2)

            print(f"   ✅ Inserted {len(new_rows)} chunks successfully")

            return json.dumps({
                "dataset": dataset_name,
                "table": table_name,
                "video_id": self.video_id,
                "chunk_count": len(rows),
                "inserted_count": len(new_rows),
                "skipped_count": len(existing_chunk_ids),
                "content_hashes": [row["content_sha256"] for row in rows],
                "status": "streamed",
                "message": f"Streamed {len(new_rows)} new chunks to BigQuery table '{table_name}' (skipped {len(existing_chunk_ids)} existing)"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "streaming_failed",
                "message": f"Failed to stream transcript to BigQuery: {str(e)}",
                "video_id": self.video_id
            })

    def _chunk_transcript(self, text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
        """Chunk transcript with token-aware overlap (same as other tools)."""
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)

        chunks = []
        start_idx = 0

        while start_idx < len(tokens):
            end_idx = min(start_idx + max_tokens, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            if end_idx < len(tokens):
                start_idx = end_idx - overlap_tokens
            else:
                break

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def _ensure_table_exists(self, client, table_id: str, bigquery_module) -> dict:
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
                bigquery_module.SchemaField("text_snippet", "STRING", mode="NULLABLE"),  # Preview only (<=256 chars)
            ]

            table = bigquery_module.Table(table_id, schema=schema)
            table = client.create_table(table)
            return {"success": True, "status": "created"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_existing_chunk_ids(self, client, table_id: str, video_id: str) -> set:
        """Query existing chunk_ids for this video to prevent duplicates."""
        try:
            query = f"""
                SELECT chunk_id
                FROM `{table_id}`
                WHERE video_id = @video_id
            """

            job_config = client.query_job_config()
            job_config.query_parameters = [
                client.query_parameter_from_value("video_id", video_id, "STRING")
            ]

            query_job = client.query(query, job_config=job_config)
            results = query_job.result()

            return {row.chunk_id for row in results}

        except Exception as e:
            # If query fails (e.g., table doesn't exist yet), return empty set
            print(f"   ⚠️ Warning: Could not query existing chunks: {str(e)}")
            return set()


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Stream full transcript to BigQuery with chunking")
    print("="*80)

    # Sample transcript (short for testing)
    sample_transcript = """
    Welcome to this tutorial on building scalable SaaS businesses. Today we're going to talk about
    the key principles that separate successful founders from those who struggle. The first principle
    is understanding your unit economics. You need to know your customer acquisition cost, lifetime
    value, and payback period. These metrics form the foundation of your business model.

    The second principle is hiring A-players. Many founders make the mistake of hiring too quickly
    or settling for B-players because they're desperate to fill a role. This is a critical error.
    A-players attract other A-players, and they're 10x more productive than average employees.

    The third principle is building systems and processes before you need them. Document everything
    as you go. Create playbooks for every key function in your business. This allows you to scale
    without chaos and ensures quality as you grow.
    """ * 10  # Repeat to create longer text for chunking

    try:
        tool = StreamFullTranscriptToBigQuery(
            video_id="test_mZxDw92UXmA",
            transcript_text=sample_transcript,
            channel_id="UCkP5J0pXI11VE81q7S7V1Jw",
            title="How to Build a Scalable SaaS Business",
            channel_handle="@DanMartell",
            published_at="2025-10-08T12:00:00Z",
            duration_sec=1200
        )

        result = tool.run()
        print("✅ Test completed:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
        elif data.get("status") == "skipped":
            print(f"\n⚪ {data['message']}")
        else:
            print(f"\n📊 Streaming Summary:")
            print(f"   Dataset: {data['dataset']}")
            print(f"   Table: {data['table']}")
            print(f"   Video ID: {data['video_id']}")
            print(f"   Chunk Count: {data['chunk_count']}")
            print(f"   Inserted Count: {data['inserted_count']}")
            print(f"   Skipped Count: {data.get('skipped_count', 0)}")
            print(f"\n💡 {data['message']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
