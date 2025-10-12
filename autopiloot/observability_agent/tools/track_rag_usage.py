"""
TrackRagUsage tool for tracking token and embedding usage across RAG systems.
Stores daily usage metrics in Firestore for cost monitoring and observability.

Usage Tracking:
- Token counts for chunking operations
- Embedding API calls and costs (if applicable)
- Storage operations across Zep, OpenSearch, BigQuery
- Daily aggregation for reporting and alerting
"""

import os
import sys
import json
from typing import Optional
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value
from audit_logger import audit_logger


class TrackRagUsage(BaseTool):
    """
    Track RAG system usage metrics for cost monitoring and observability.

    Implements:
    - Daily token usage aggregation per video/operation
    - Storage operation tracking (Zep, OpenSearch, BigQuery)
    - Cost estimation for embedding APIs
    - Firestore persistence in rag_usage_daily collection
    - Audit logging for compliance
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for usage tracking"
    )
    operation: str = Field(
        ...,
        description="RAG operation type: 'zep_upsert', 'opensearch_index', 'bigquery_stream', 'hybrid_retrieval'"
    )
    tokens_processed: int = Field(
        default=0,
        description="Number of tokens processed during operation"
    )
    chunks_created: int = Field(
        default=0,
        description="Number of chunks created/processed"
    )
    embeddings_generated: int = Field(
        default=0,
        description="Number of embeddings generated (if applicable)"
    )
    storage_system: str = Field(
        default="unknown",
        description="Storage system used: 'zep', 'opensearch', 'bigquery', 'hybrid'"
    )
    status: str = Field(
        default="success",
        description="Operation status: 'success', 'partial', 'failed'"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )

    def run(self) -> str:
        """
        Record RAG usage metrics to Firestore for daily aggregation and monitoring.

        Process:
        1. Validate environment and configuration
        2. Get current date for daily aggregation
        3. Update rag_usage_daily document with incremental metrics
        4. Log to audit trail for compliance
        5. Return summary with totals

        Returns:
            JSON string with tracking status and daily totals
        """
        try:
            # Load environment
            load_environment()

            # Get project ID and initialize Firestore
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID")
            db = firestore.Client(project=project_id)

            # Get current date for daily aggregation
            current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            timestamp = datetime.now(timezone.utc).isoformat()

            print(f"📊 Tracking RAG usage for {self.video_id}...")
            print(f"   Operation: {self.operation}")
            print(f"   Tokens: {self.tokens_processed}")
            print(f"   Chunks: {self.chunks_created}")
            print(f"   Storage: {self.storage_system}")

            # Reference to daily usage document
            usage_doc_ref = db.collection('rag_usage_daily').document(current_date)

            # Use transaction for atomic updates
            @firestore.transactional
            def update_usage(transaction, doc_ref):
                snapshot = doc_ref.get(transaction=transaction)

                if snapshot.exists:
                    data = snapshot.to_dict()
                else:
                    data = {
                        'date': current_date,
                        'total_tokens': 0,
                        'total_chunks': 0,
                        'total_embeddings': 0,
                        'total_videos': 0,
                        'operations': {},
                        'storage_systems': {},
                        'videos_processed': [],
                        'errors': [],
                        'created_at': timestamp,
                        'updated_at': timestamp
                    }

                # Update totals
                data['total_tokens'] += self.tokens_processed
                data['total_chunks'] += self.chunks_created
                data['total_embeddings'] += self.embeddings_generated

                # Track unique videos
                videos = data.get('videos_processed', [])
                if self.video_id not in videos:
                    videos.append(self.video_id)
                    data['total_videos'] = len(videos)
                data['videos_processed'] = videos

                # Track operations
                operations = data.get('operations', {})
                if self.operation not in operations:
                    operations[self.operation] = {'count': 0, 'tokens': 0, 'chunks': 0}
                operations[self.operation]['count'] += 1
                operations[self.operation]['tokens'] += self.tokens_processed
                operations[self.operation]['chunks'] += self.chunks_created
                data['operations'] = operations

                # Track storage systems
                storage_systems = data.get('storage_systems', {})
                if self.storage_system not in storage_systems:
                    storage_systems[self.storage_system] = {'count': 0, 'tokens': 0}
                storage_systems[self.storage_system]['count'] += 1
                storage_systems[self.storage_system]['tokens'] += self.tokens_processed
                data['storage_systems'] = storage_systems

                # Track errors
                if self.status != 'success' and self.error_message:
                    errors = data.get('errors', [])
                    errors.append({
                        'video_id': self.video_id,
                        'operation': self.operation,
                        'error': self.error_message,
                        'timestamp': timestamp
                    })
                    # Keep last 50 errors
                    data['errors'] = errors[-50:]

                data['updated_at'] = timestamp

                # Write back to Firestore
                transaction.set(doc_ref, data)

                return data

            # Execute transaction
            transaction = db.transaction()
            updated_data = update_usage(transaction, usage_doc_ref)

            print(f"   ✓ Usage tracked in rag_usage_daily/{current_date}")
            print(f"   Daily totals: {updated_data['total_tokens']} tokens, {updated_data['total_chunks']} chunks")

            # Log to audit trail
            audit_logger.log_tool_execution(
                tool_name="TrackRagUsage",
                video_id=self.video_id,
                params={
                    "operation": self.operation,
                    "tokens": self.tokens_processed,
                    "chunks": self.chunks_created,
                    "storage": self.storage_system,
                    "status": self.status
                },
                outcome="success",
                actor="ObservabilityAgent"
            )

            return json.dumps({
                "video_id": self.video_id,
                "operation": self.operation,
                "tokens_processed": self.tokens_processed,
                "chunks_created": self.chunks_created,
                "storage_system": self.storage_system,
                "status": self.status,
                "date": current_date,
                "daily_totals": {
                    "total_tokens": updated_data['total_tokens'],
                    "total_chunks": updated_data['total_chunks'],
                    "total_videos": updated_data['total_videos']
                },
                "tracking_status": "recorded"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "tracking_failed",
                "message": f"Failed to track RAG usage: {str(e)}",
                "video_id": self.video_id,
                "operation": self.operation
            })


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Track RAG Usage")
    print("="*80)

    try:
        tool = TrackRagUsage(
            video_id="test_mZxDw92UXmA",
            operation="zep_upsert",
            tokens_processed=2500,
            chunks_created=3,
            embeddings_generated=3,
            storage_system="zep",
            status="success"
        )

        result = tool.run()
        print("✅ Test completed:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
        else:
            print(f"\n📊 Usage Tracking Summary:")
            print(f"   Video: {data['video_id']}")
            print(f"   Operation: {data['operation']}")
            print(f"   Tokens: {data['tokens_processed']}")
            print(f"   Chunks: {data['chunks_created']}")
            print(f"   Daily Totals: {data['daily_totals']['total_tokens']} tokens")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
