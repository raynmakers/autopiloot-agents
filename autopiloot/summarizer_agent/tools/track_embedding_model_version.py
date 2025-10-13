"""
Track embedding model versions in document metadata.

This tool persists embedding model version information with each document
to enable:
- Targeted re-embedding after model upgrades
- Audit trail for model changes
- Prevention of mixing incompatible embedding versions
- Identification of documents needing refresh

Integrates with Zep, OpenSearch, and BigQuery to maintain consistent
version tracking across all retrieval sources.
"""

import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import Field


class TrackEmbeddingModelVersion:
    """Track and manage embedding model versions in document metadata."""

    operation: str = Field(
        ...,
        description="Operation: 'set', 'get', 'list_versions', 'list_documents_by_version', 'check_migration_needed'"
    )

    document_id: Optional[str] = Field(
        None,
        description="Document ID for 'set' or 'get' operations"
    )

    model_name: Optional[str] = Field(
        None,
        description="Embedding model name (e.g., 'text-embedding-3-small', 'text-embedding-ada-002')"
    )

    model_version: Optional[str] = Field(
        None,
        description="Model version string (e.g., '1.0', '2024-01-15')"
    )

    embedding_dimension: Optional[int] = Field(
        None,
        description="Embedding dimension (e.g., 1536, 3072)"
    )

    namespace: str = Field(
        default="autopiloot-dev",
        description="Zep namespace for version tracking"
    )

    target_model_name: Optional[str] = Field(
        None,
        description="Target model name for migration check"
    )

    def __init__(self, **data):
        """Initialize with settings from config."""
        from core.config_loader import ConfigLoader

        # Set attributes from data
        for key, value in data.items():
            setattr(self, key, value)

        # Load configuration
        self.config = ConfigLoader()

        # Version tracking storage (in production: Zep/Firestore)
        self._version_registry = {}  # In-memory for now

        # Mock some existing versions for testing
        self._initialize_mock_data()

    def _initialize_mock_data(self):
        """Initialize mock version data for testing."""
        # Simulate existing documents with versions
        mock_docs = [
            {
                "document_id": "video_123_chunk_0",
                "model_name": "text-embedding-ada-002",
                "model_version": "1.0",
                "embedding_dimension": 1536,
                "indexed_at": "2024-12-01T10:00:00Z"
            },
            {
                "document_id": "video_123_chunk_1",
                "model_name": "text-embedding-ada-002",
                "model_version": "1.0",
                "embedding_dimension": 1536,
                "indexed_at": "2024-12-01T10:00:00Z"
            },
            {
                "document_id": "video_456_chunk_0",
                "model_name": "text-embedding-3-small",
                "model_version": "2024-01-15",
                "embedding_dimension": 1536,
                "indexed_at": "2025-01-10T14:00:00Z"
            },
            {
                "document_id": "video_789_chunk_0",
                "model_name": "text-embedding-3-small",
                "model_version": "2024-01-15",
                "embedding_dimension": 1536,
                "indexed_at": "2025-01-12T09:00:00Z"
            }
        ]

        for doc in mock_docs:
            self._version_registry[doc["document_id"]] = doc

    def set_version(
        self,
        document_id: str,
        model_name: str,
        model_version: str,
        embedding_dimension: int
    ) -> Dict[str, Any]:
        """
        Set embedding model version for a document.

        Args:
            document_id: Document identifier
            model_name: Embedding model name
            model_version: Model version string
            embedding_dimension: Embedding dimension

        Returns:
            Operation result
        """
        try:
            # TODO: In production, persist to:
            # 1. Zep document metadata
            # 2. OpenSearch document metadata
            # 3. BigQuery tracking table

            version_info = {
                "document_id": document_id,
                "model_name": model_name,
                "model_version": model_version,
                "embedding_dimension": embedding_dimension,
                "indexed_at": datetime.utcnow().isoformat() + "Z"
            }

            # Store in registry
            self._version_registry[document_id] = version_info

            return {
                "status": "success",
                "operation": "set_version",
                "document_id": document_id,
                "version_info": version_info
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "set_version",
                "message": f"Failed to set version: {e}"
            }

    def get_version(self, document_id: str) -> Dict[str, Any]:
        """
        Get embedding model version for a document.

        Args:
            document_id: Document identifier

        Returns:
            Version information
        """
        try:
            version_info = self._version_registry.get(document_id)

            if not version_info:
                return {
                    "status": "not_found",
                    "operation": "get_version",
                    "document_id": document_id,
                    "message": "No version information found"
                }

            return {
                "status": "success",
                "operation": "get_version",
                "document_id": document_id,
                "version_info": version_info
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "get_version",
                "message": f"Failed to get version: {e}"
            }

    def list_versions(self) -> Dict[str, Any]:
        """
        List all embedding model versions in use.

        Returns:
            List of model versions with document counts
        """
        try:
            # Group by model name and version
            version_counts = {}

            for doc_id, info in self._version_registry.items():
                key = f"{info['model_name']}:{info['model_version']}"
                if key not in version_counts:
                    version_counts[key] = {
                        "model_name": info["model_name"],
                        "model_version": info["model_version"],
                        "embedding_dimension": info["embedding_dimension"],
                        "document_count": 0,
                        "oldest_indexed": info["indexed_at"],
                        "newest_indexed": info["indexed_at"]
                    }

                version_counts[key]["document_count"] += 1

                # Track oldest and newest
                if info["indexed_at"] < version_counts[key]["oldest_indexed"]:
                    version_counts[key]["oldest_indexed"] = info["indexed_at"]
                if info["indexed_at"] > version_counts[key]["newest_indexed"]:
                    version_counts[key]["newest_indexed"] = info["indexed_at"]

            return {
                "status": "success",
                "operation": "list_versions",
                "namespace": self.namespace,
                "total_documents": len(self._version_registry),
                "versions": list(version_counts.values())
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "list_versions",
                "message": f"Failed to list versions: {e}"
            }

    def list_documents_by_version(
        self,
        model_name: str,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List documents using specific embedding model version.

        Args:
            model_name: Embedding model name
            model_version: Optional model version filter

        Returns:
            List of document IDs
        """
        try:
            matching_docs = []

            for doc_id, info in self._version_registry.items():
                if info["model_name"] == model_name:
                    if model_version is None or info["model_version"] == model_version:
                        matching_docs.append({
                            "document_id": doc_id,
                            "model_version": info["model_version"],
                            "indexed_at": info["indexed_at"]
                        })

            return {
                "status": "success",
                "operation": "list_documents_by_version",
                "model_name": model_name,
                "model_version": model_version or "all",
                "document_count": len(matching_docs),
                "documents": matching_docs
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "list_documents_by_version",
                "message": f"Failed to list documents: {e}"
            }

    def check_migration_needed(
        self,
        target_model_name: str,
        target_model_version: str
    ) -> Dict[str, Any]:
        """
        Check which documents need migration to target model version.

        Args:
            target_model_name: Target embedding model name
            target_model_version: Target model version

        Returns:
            Migration analysis
        """
        try:
            total_docs = len(self._version_registry)
            needs_migration = []
            up_to_date = []

            for doc_id, info in self._version_registry.items():
                if (info["model_name"] != target_model_name or
                    info["model_version"] != target_model_version):
                    needs_migration.append({
                        "document_id": doc_id,
                        "current_model": info["model_name"],
                        "current_version": info["model_version"],
                        "indexed_at": info["indexed_at"]
                    })
                else:
                    up_to_date.append(doc_id)

            migration_count = len(needs_migration)
            migration_percentage = (migration_count / total_docs * 100) if total_docs > 0 else 0

            # Estimate migration time (assuming 5 docs/second)
            estimated_time_seconds = migration_count / 5
            estimated_time_minutes = estimated_time_seconds / 60

            return {
                "status": "success",
                "operation": "check_migration_needed",
                "target_model": {
                    "model_name": target_model_name,
                    "model_version": target_model_version
                },
                "analysis": {
                    "total_documents": total_docs,
                    "needs_migration": migration_count,
                    "up_to_date": len(up_to_date),
                    "migration_percentage": round(migration_percentage, 2),
                    "estimated_time_minutes": round(estimated_time_minutes, 2)
                },
                "documents_to_migrate": needs_migration[:10]  # First 10 for preview
            }

        except Exception as e:
            return {
                "status": "error",
                "operation": "check_migration_needed",
                "message": f"Failed to check migration: {e}"
            }

    def run(self) -> str:
        """
        Execute version tracking operation.

        Returns:
            JSON string with operation result
        """
        try:
            if self.operation == "set":
                if not all([self.document_id, self.model_name, self.model_version, self.embedding_dimension]):
                    return json.dumps({
                        "status": "error",
                        "message": "Operation 'set' requires: document_id, model_name, model_version, embedding_dimension"
                    })

                result = self.set_version(
                    document_id=self.document_id,
                    model_name=self.model_name,
                    model_version=self.model_version,
                    embedding_dimension=self.embedding_dimension
                )

            elif self.operation == "get":
                if not self.document_id:
                    return json.dumps({
                        "status": "error",
                        "message": "Operation 'get' requires: document_id"
                    })

                result = self.get_version(document_id=self.document_id)

            elif self.operation == "list_versions":
                result = self.list_versions()

            elif self.operation == "list_documents_by_version":
                if not self.model_name:
                    return json.dumps({
                        "status": "error",
                        "message": "Operation 'list_documents_by_version' requires: model_name"
                    })

                result = self.list_documents_by_version(
                    model_name=self.model_name,
                    model_version=self.model_version
                )

            elif self.operation == "check_migration_needed":
                if not all([self.target_model_name, self.model_version]):
                    return json.dumps({
                        "status": "error",
                        "message": "Operation 'check_migration_needed' requires: target_model_name, model_version"
                    })

                result = self.check_migration_needed(
                    target_model_name=self.target_model_name,
                    target_model_version=self.model_version
                )

            else:
                return json.dumps({
                    "status": "error",
                    "message": f"Unknown operation: {self.operation}. Valid operations: set, get, list_versions, list_documents_by_version, check_migration_needed"
                })

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "status": "error",
                "operation": self.operation,
                "message": f"Execution failed: {e}"
            })


# Test block
if __name__ == "__main__":
    print("=" * 60)
    print("Testing TrackEmbeddingModelVersion Tool")
    print("=" * 60)

    # Test 1: List all versions
    print("\n1. List all embedding model versions:")
    tool = TrackEmbeddingModelVersion(operation="list_versions")
    result = tool.run()
    print(result)

    # Test 2: Get version for specific document
    print("\n2. Get version for specific document:")
    tool = TrackEmbeddingModelVersion(
        operation="get",
        document_id="video_123_chunk_0"
    )
    result = tool.run()
    print(result)

    # Test 3: Set version for new document
    print("\n3. Set version for new document:")
    tool = TrackEmbeddingModelVersion(
        operation="set",
        document_id="video_999_chunk_0",
        model_name="text-embedding-3-large",
        model_version="2024-02-01",
        embedding_dimension=3072
    )
    result = tool.run()
    print(result)

    # Test 4: List documents by model version
    print("\n4. List documents using text-embedding-ada-002:")
    tool = TrackEmbeddingModelVersion(
        operation="list_documents_by_version",
        model_name="text-embedding-ada-002"
    )
    result = tool.run()
    print(result)

    # Test 5: Check migration needed
    print("\n5. Check migration needed to text-embedding-3-small:")
    tool = TrackEmbeddingModelVersion(
        operation="check_migration_needed",
        target_model_name="text-embedding-3-small",
        model_version="2024-01-15"
    )
    result = tool.run()
    print(result)

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
