"""
SaveDriveIngestionRecord tool for writing Google Drive ingestion audit records to Firestore.
Tracks ingestion runs with metrics, durations, errors, and outcomes for monitoring.
"""

import os
import sys
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class SaveDriveIngestionRecord(BaseTool):
    """
    Saves Google Drive ingestion audit records to Firestore for run tracking and monitoring.

    Creates detailed audit logs with ingestion metrics, processing duration,
    error tracking, and outcomes for operational monitoring and analysis.
    """

    run_id: str = Field(
        ...,
        description="Unique identifier for this ingestion run"
    )

    namespace: str = Field(
        ...,
        description="Zep namespace where Drive content was indexed"
    )

    targets_processed: List[Dict] = Field(
        ...,
        description="List of Drive targets (files/folders) that were processed"
    )

    ingestion_stats: Dict = Field(
        ...,
        description="Statistics from the ingestion process (counts, durations, etc.)"
    )

    processing_duration_seconds: Optional[float] = Field(
        None,
        description="Total processing duration in seconds"
    )

    checkpoint_data: Optional[Dict] = Field(
        None,
        description="Checkpoint information for resuming incremental processing"
    )

    errors: Optional[List[Dict]] = Field(
        None,
        description="List of errors encountered during processing"
    )

    sync_interval_minutes: Optional[int] = Field(
        None,
        description="Configured sync interval for this ingestion run"
    )

    def _prepare_audit_record(self, record_id: str) -> Dict[str, Any]:
        """Prepare the complete audit record for Firestore."""

        # Extract key metrics from ingestion stats
        total_files_discovered = self.ingestion_stats.get("files_discovered", 0)
        total_files_processed = self.ingestion_stats.get("files_processed", 0)
        total_text_extracted = self.ingestion_stats.get("text_extraction_count", 0)
        total_zep_upserted = self.ingestion_stats.get("zep_upserted", 0)
        total_chunks_created = self.ingestion_stats.get("chunks_created", 0)
        total_bytes_processed = self.ingestion_stats.get("bytes_processed", 0)

        # Calculate success rate
        success_rate = 0.0
        if total_files_discovered > 0:
            success_rate = (total_files_processed / total_files_discovered) * 100

        # Prepare target summary
        target_summary = []
        for target in self.targets_processed:
            target_summary.append({
                "id": target.get("id", "unknown"),
                "type": target.get("type", "unknown"),
                "name": target.get("name", "Unknown"),
                "files_found": target.get("files_found", 0),
                "files_processed": target.get("files_processed", 0),
                "errors": len(target.get("errors", []))
            })

        # Prepare error summary
        error_summary = {
            "total_errors": len(self.errors) if self.errors else 0,
            "error_types": {},
            "critical_errors": 0
        }

        if self.errors:
            for error in self.errors:
                error_type = error.get("type", "unknown")
                error_summary["error_types"][error_type] = error_summary["error_types"].get(error_type, 0) + 1

                if error.get("severity") == "critical":
                    error_summary["critical_errors"] += 1

        # Create comprehensive audit record
        audit_record = {
            # Record identification
            "record_id": record_id,
            "run_id": self.run_id,
            "namespace": self.namespace,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_type": "drive_agent",

            # Processing summary
            "summary": {
                "targets_configured": len(self.targets_processed),
                "files_discovered": total_files_discovered,
                "files_processed": total_files_processed,
                "text_extracted": total_text_extracted,
                "zep_documents_upserted": total_zep_upserted,
                "chunks_created": total_chunks_created,
                "bytes_processed": total_bytes_processed,
                "success_rate_percent": round(success_rate, 2)
            },

            # Performance metrics
            "performance": {
                "processing_duration_seconds": self.processing_duration_seconds,
                "avg_file_processing_seconds": (
                    self.processing_duration_seconds / max(1, total_files_processed)
                    if self.processing_duration_seconds and total_files_processed > 0 else None
                ),
                "files_per_minute": (
                    (total_files_processed * 60) / self.processing_duration_seconds
                    if self.processing_duration_seconds and self.processing_duration_seconds > 0 else None
                ),
                "sync_interval_minutes": self.sync_interval_minutes
            },

            # Target details
            "targets": target_summary,

            # Error tracking
            "errors": error_summary,
            "error_details": self.errors if self.errors else [],

            # Checkpoint information for incremental processing
            "checkpoint": self.checkpoint_data,

            # Full ingestion statistics
            "detailed_stats": self.ingestion_stats,

            # Operational metadata
            "metadata": {
                "firestore_collection": "drive_ingestion_logs",
                "indexed_at": datetime.now(timezone.utc).isoformat(),
                "agent_version": "1.0.0",
                "status": "completed" if error_summary["critical_errors"] == 0 else "completed_with_errors"
            }
        }

        return audit_record

    def _save_to_firestore(self, audit_record: Dict[str, Any]) -> str:
        """Save audit record to Firestore and return document path."""

        try:
            # Get GCP configuration
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID")

            # Initialize Firestore client
            from google.cloud import firestore
            db = firestore.Client(project=project_id)

            # Create document path: drive_ingestion_logs/{namespace}/{date}_{run_id}
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            document_id = f"{date_str}_{self.run_id}"

            # Use hierarchical structure: drive_ingestion_logs/{namespace}/{document_id}
            collection_path = f"drive_ingestion_logs"
            subcollection_path = f"{collection_path}/{self.namespace}/records"

            # Save to Firestore
            doc_ref = db.collection(subcollection_path).document(document_id)
            doc_ref.set(audit_record)

            # Also save a summary record at the namespace level for quick access
            summary_record = {
                "namespace": self.namespace,
                "date": date_str,
                "run_id": self.run_id,
                "record_id": audit_record["record_id"],
                "last_updated": firestore.SERVER_TIMESTAMP,
                "summary": audit_record["summary"],
                "performance": audit_record["performance"],
                "error_count": audit_record["errors"]["total_errors"],
                "status": audit_record["metadata"]["status"]
            }

            # Save summary to namespace level
            summary_ref = db.collection(collection_path).document(self.namespace)
            summary_ref.set({
                "last_ingestion": summary_record,
                "updated_at": firestore.SERVER_TIMESTAMP
            }, merge=True)

            return f"{subcollection_path}/{document_id}"

        except Exception as e:
            raise Exception(f"Failed to save audit record to Firestore: {str(e)}")

    def run(self) -> str:
        """
        Saves Drive ingestion audit record to Firestore.

        Returns:
            JSON string containing audit record save status
        """
        try:
            # Load environment
            load_environment()

            # Generate audit record ID
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            record_id = f"drive_ingestion_{timestamp}_{self.run_id[:8]}"

            # Prepare comprehensive audit record
            audit_record = self._prepare_audit_record(record_id)

            # Save to Firestore
            document_path = self._save_to_firestore(audit_record)

            # Prepare response summary
            summary = audit_record["summary"]
            performance = audit_record["performance"]

            result = {
                "audit_record_id": record_id,
                "firestore_document_path": document_path,
                "status": "saved",
                "record_summary": {
                    "namespace": self.namespace,
                    "targets_processed": summary["targets_configured"],
                    "files_discovered": summary["files_discovered"],
                    "files_processed": summary["files_processed"],
                    "zep_documents_upserted": summary["zep_documents_upserted"],
                    "chunks_created": summary["chunks_created"],
                    "processing_duration_seconds": performance["processing_duration_seconds"],
                    "success_rate_percent": summary["success_rate_percent"],
                    "errors": audit_record["errors"]["total_errors"],
                    "status": audit_record["metadata"]["status"]
                },
                "checkpoint_saved": self.checkpoint_data is not None,
                "next_sync_recommendation": (
                    f"Next sync recommended in {self.sync_interval_minutes} minutes"
                    if self.sync_interval_minutes else "Sync interval not configured"
                )
            }

            return json.dumps(result)

        except Exception as e:
            return json.dumps({
                "error": "save_failed",
                "message": f"Failed to save Drive ingestion record: {str(e)}",
                "details": {
                    "run_id": self.run_id,
                    "namespace": self.namespace,
                    "type": type(e).__name__
                }
            })


if __name__ == "__main__":
    # Test the tool
    print("Testing SaveDriveIngestionRecord tool...")

    # Sample ingestion data for testing
    test_targets = [
        {
            "id": "folder_123",
            "type": "folder",
            "name": "Strategy Documents",
            "files_found": 15,
            "files_processed": 14,
            "errors": ["file_456: Permission denied"]
        },
        {
            "id": "file_789",
            "type": "file",
            "name": "Playbook.docx",
            "files_found": 1,
            "files_processed": 1,
            "errors": []
        }
    ]

    test_stats = {
        "files_discovered": 16,
        "files_processed": 15,
        "text_extraction_count": 15,
        "zep_upserted": 18,  # More than files due to chunking
        "chunks_created": 18,
        "bytes_processed": 2048000,
        "api_calls_made": 45,
        "extraction_methods": {
            "pdf": 8,
            "docx": 4,
            "text": 3
        }
    }

    test_errors = [
        {
            "file_id": "file_456",
            "type": "permission_error",
            "message": "Permission denied",
            "severity": "warning"
        }
    ]

    test_checkpoint = {
        "last_sync_timestamp": "2025-01-15T10:30:00Z",
        "processed_file_ids": ["file_789"],
        "next_check_recommended": "2025-01-15T13:30:00Z"
    }

    # Test 1: Successful ingestion record
    print("\n1. Testing successful ingestion record...")
    tool = SaveDriveIngestionRecord(
        run_id="test_run_001",
        namespace="autopiloot_drive_content",
        targets_processed=test_targets,
        ingestion_stats=test_stats,
        processing_duration_seconds=125.5,
        checkpoint_data=test_checkpoint,
        errors=test_errors,
        sync_interval_minutes=60
    )
    result = tool.run()
    result_json = json.loads(result)

    if "error" not in result_json:
        print("Success! Record summary:")
        summary = result_json.get("record_summary", {})
        print(f"  Namespace: {summary.get('namespace')}")
        print(f"  Files processed: {summary.get('files_processed')}")
        print(f"  Zep documents: {summary.get('zep_documents_upserted')}")
        print(f"  Success rate: {summary.get('success_rate_percent')}%")
        print(f"  Processing time: {summary.get('processing_duration_seconds')}s")
        print(f"  Status: {summary.get('status')}")
        print(f"  Firestore path: {result_json.get('firestore_document_path')}")
    else:
        print(f"Error: {result_json.get('error')}")
        print(f"Message: {result_json.get('message')}")

    # Test 2: Minimal record (no optional fields)
    print("\n2. Testing minimal ingestion record...")
    minimal_stats = {
        "files_discovered": 5,
        "files_processed": 5,
        "text_extraction_count": 5,
        "zep_upserted": 5
    }

    tool = SaveDriveIngestionRecord(
        run_id="test_run_002",
        namespace="test_namespace",
        targets_processed=[{
            "id": "test_file",
            "type": "file",
            "name": "test.txt",
            "files_found": 1,
            "files_processed": 1
        }],
        ingestion_stats=minimal_stats
    )
    result = tool.run()
    result_json = json.loads(result)

    if "error" not in result_json:
        print("Minimal record saved successfully")
        print(f"  Record ID: {result_json.get('audit_record_id')}")
    else:
        print(f"Error: {result_json.get('error')}")

    # Test 3: Error handling
    print("\n3. Testing error handling...")
    try:
        tool = SaveDriveIngestionRecord(
            run_id="test_run_003",
            namespace="test_namespace",
            targets_processed=[],  # Empty targets
            ingestion_stats={}  # Empty stats
        )
        result = tool.run()
        result_json = json.loads(result)

        if "error" in result_json:
            print(f"Expected error handling: {result_json.get('error')}")
        else:
            print("Record saved despite empty data")

    except Exception as e:
        print(f"Exception during error test: {str(e)}")

    print("\nAudit record testing completed!")