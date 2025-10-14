"""
Best-Effort Firestore RAG References

Optional lightweight Firestore references for RAG artifacts.
Provides audit/discovery pointers without coupling RAG indexing to Firestore.

Architecture:
- Best-effort only: Never blocks or raises exceptions
- Feature-flagged: Controlled by rag.features.write_firestore_refs
- No hard dependency: RAG works perfectly without Firestore
- Audit trail: Helps operations team locate indexed artifacts
"""

import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from loader import get_config_value


def upsert_ref(ref: Dict[str, Any]) -> None:
    """
    Best-effort upsert of RAG reference to Firestore.

    This function NEVER raises exceptions and NEVER blocks indexing operations.
    All errors are caught and logged as warnings only.

    Args:
        ref: Dictionary containing reference fields:
            - type (str, required): "transcript", "summary", "document", "linkedin", "strategy"
            - source_ref (str, required): Original source identifier
            - created_by_agent (str, required): Agent name
            - content_hashes (list, required): SHA-256 hashes
            - chunk_count (int, required): Number of chunks
            - total_tokens (int, required): Total tokens
            - indexing_status (str, required): "success", "partial", or "error"
            - sink_statuses (dict, required): Per-sink status
            - indexing_duration_ms (int, required): Duration in milliseconds

            Optional fields:
            - opensearch_index (str): OpenSearch index name
            - bigquery_table (str): BigQuery table ID
            - zep_doc_id (str): Zep document/thread ID
            - title (str): Human-readable title
            - channel_id (str): YouTube channel ID
            - published_at (str): Publication date (ISO 8601)
            - tags (list): Categorization tags

    Returns:
        None (all operations are best-effort)

    Example:
        >>> upsert_ref({
        ...     "type": "transcript",
        ...     "source_ref": "abc123",
        ...     "created_by_agent": "transcriber_agent",
        ...     "content_hashes": ["a1b2c3..."],
        ...     "chunk_count": 10,
        ...     "total_tokens": 8500,
        ...     "indexing_status": "success",
        ...     "sink_statuses": {"opensearch": "indexed"},
        ...     "indexing_duration_ms": 5234
        ... })
    """
    try:
        # Check feature flag first (fast path for disabled)
        write_refs_enabled = get_config_value("rag.features.write_firestore_refs", False)

        if not write_refs_enabled:
            # Feature disabled - skip silently (no logging overhead)
            return

        # Validate required fields
        required_fields = [
            "type", "source_ref", "created_by_agent",
            "content_hashes", "chunk_count", "total_tokens",
            "indexing_status", "sink_statuses", "indexing_duration_ms"
        ]

        for field in required_fields:
            if field not in ref:
                print(f"Warning: RAG ref missing required field '{field}', skipping write")
                return

        # Initialize Firestore client
        try:
            from google.cloud import firestore
        except ImportError:
            print("Warning: google-cloud-firestore not installed, cannot write RAG refs")
            return

        # Get GCP project ID
        try:
            from env_loader import get_required_env_var
            project_id = get_required_env_var("GCP_PROJECT_ID", "GCP project for Firestore")
        except Exception as e:
            print(f"Warning: Failed to get GCP_PROJECT_ID: {str(e)}")
            return

        # Create Firestore client
        try:
            db = firestore.Client(project=project_id)
        except Exception as e:
            print(f"Warning: Failed to create Firestore client: {str(e)}")
            return

        # Build document ID from type and source_ref
        doc_id = f"{ref['type']}_{ref['source_ref']}"

        # Prepare document data
        doc_data = {
            # Required fields
            "type": ref["type"],
            "source_ref": ref["source_ref"],
            "created_at": firestore.SERVER_TIMESTAMP,
            "created_by_agent": ref["created_by_agent"],
            "content_hashes": ref["content_hashes"],
            "chunk_count": ref["chunk_count"],
            "total_tokens": ref["total_tokens"],
            "indexing_status": ref["indexing_status"],
            "sink_statuses": ref["sink_statuses"],
            "last_updated_at": firestore.SERVER_TIMESTAMP,
            "indexing_duration_ms": ref["indexing_duration_ms"]
        }

        # Add optional sink references
        if "opensearch_index" in ref:
            doc_data["opensearch_index"] = ref["opensearch_index"]
        if "bigquery_table" in ref:
            doc_data["bigquery_table"] = ref["bigquery_table"]
        if "zep_doc_id" in ref:
            doc_data["zep_doc_id"] = ref["zep_doc_id"]

        # Add optional metadata
        if "title" in ref:
            doc_data["title"] = ref["title"]
        if "channel_id" in ref:
            doc_data["channel_id"] = ref["channel_id"]
        if "published_at" in ref:
            doc_data["published_at"] = ref["published_at"]
        if "tags" in ref:
            doc_data["tags"] = ref["tags"]

        # Upsert to Firestore (best-effort)
        try:
            doc_ref = db.collection("rag_refs").document(doc_id)
            doc_ref.set(doc_data, merge=True)
            print(f"   ✓ RAG ref written to Firestore: rag_refs/{doc_id}")
        except Exception as e:
            print(f"Warning: Failed to write RAG ref to Firestore: {str(e)}")
            return

    except Exception as e:
        # Catch all exceptions at top level (best-effort guarantee)
        print(f"Warning: RAG ref write failed: {str(e)}")
        return


def get_ref(ref_type: str, source_ref: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort retrieval of RAG reference from Firestore.

    This function NEVER raises exceptions. Returns None on any error.

    Args:
        ref_type: Type of reference ("transcript", "summary", etc.)
        source_ref: Original source identifier

    Returns:
        Dictionary with reference data, or None if not found or error

    Example:
        >>> ref = get_ref("transcript", "abc123")
        >>> if ref:
        ...     print(f"Found ref with {ref['chunk_count']} chunks")
    """
    try:
        # Check feature flag
        write_refs_enabled = get_config_value("rag.features.write_firestore_refs", False)

        if not write_refs_enabled:
            # Feature disabled - return None silently
            return None

        # Initialize Firestore
        try:
            from google.cloud import firestore
            from env_loader import get_required_env_var

            project_id = get_required_env_var("GCP_PROJECT_ID", "GCP project")
            db = firestore.Client(project=project_id)
        except Exception:
            return None

        # Build document ID
        doc_id = f"{ref_type}_{source_ref}"

        # Get document
        doc_ref = db.collection("rag_refs").document(doc_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        return doc.to_dict()

    except Exception as e:
        print(f"Warning: RAG ref retrieval failed: {str(e)}")
        return None


def query_refs(
    ref_type: Optional[str] = None,
    indexing_status: Optional[str] = None,
    created_by_agent: Optional[str] = None,
    limit: int = 100
) -> list:
    """
    Best-effort query of RAG references from Firestore.

    This function NEVER raises exceptions. Returns empty list on any error.

    Args:
        ref_type: Optional filter by type
        indexing_status: Optional filter by status ("success", "partial", "error")
        created_by_agent: Optional filter by agent name
        limit: Maximum number of results (default: 100)

    Returns:
        List of reference dictionaries, or empty list on error

    Example:
        >>> refs = query_refs(ref_type="transcript", indexing_status="partial")
        >>> print(f"Found {len(refs)} partial transcript refs")
    """
    try:
        # Check feature flag
        write_refs_enabled = get_config_value("rag.features.write_firestore_refs", False)

        if not write_refs_enabled:
            return []

        # Initialize Firestore
        try:
            from google.cloud import firestore
            from env_loader import get_required_env_var

            project_id = get_required_env_var("GCP_PROJECT_ID", "GCP project")
            db = firestore.Client(project=project_id)
        except Exception:
            return []

        # Build query
        query = db.collection("rag_refs")

        if ref_type:
            query = query.where("type", "==", ref_type)
        if indexing_status:
            query = query.where("indexing_status", "==", indexing_status)
        if created_by_agent:
            query = query.where("created_by_agent", "==", created_by_agent)

        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)

        # Execute query
        docs = query.get()

        results = []
        for doc in docs:
            data = doc.to_dict()
            data["_id"] = doc.id  # Include document ID
            results.append(data)

        return results

    except Exception as e:
        print(f"Warning: RAG ref query failed: {str(e)}")
        return []


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: Best-Effort RAG References")
    print("=" * 80)

    # Test 1: Upsert reference with feature flag disabled (default)
    print("\n1. Testing upsert with feature flag disabled:")
    upsert_ref({
        "type": "transcript",
        "source_ref": "test_abc123",
        "created_by_agent": "transcriber_agent",
        "content_hashes": ["a1b2c3d4..."],
        "chunk_count": 10,
        "total_tokens": 8500,
        "indexing_status": "success",
        "sink_statuses": {"opensearch": "indexed"},
        "indexing_duration_ms": 5234
    })
    print("   (Should skip silently - feature disabled)")

    # Test 2: Missing required field
    print("\n2. Testing upsert with missing required field:")
    upsert_ref({
        "type": "transcript",
        "source_ref": "test_xyz789",
        # Missing created_by_agent
        "content_hashes": ["b2c3d4e5..."],
        "chunk_count": 5,
        "total_tokens": 4200
    })
    print("   (Should log warning about missing field)")

    # Test 3: Get reference
    print("\n3. Testing get_ref:")
    ref = get_ref("transcript", "test_abc123")
    if ref:
        print(f"   Found ref with {ref['chunk_count']} chunks")
    else:
        print("   No ref found (expected - feature disabled or not exists)")

    # Test 4: Query references
    print("\n4. Testing query_refs:")
    refs = query_refs(ref_type="transcript", limit=10)
    print(f"   Found {len(refs)} transcript refs")

    print("\n" + "=" * 80)
    print("✅ Test completed (best-effort - no exceptions raised)")
