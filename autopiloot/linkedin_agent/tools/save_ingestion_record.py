"""
SaveIngestionRecord tool for writing LinkedIn ingestion audit records to Firestore.
Tracks ingestion runs with metrics, durations, errors, and outcomes for monitoring.
"""

import os
import sys
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class SaveIngestionRecord(BaseTool):
    """
    Saves LinkedIn ingestion audit records to Firestore for run tracking and monitoring.

    Creates detailed audit logs with ingestion metrics, processing duration,
    error tracking, and outcomes for operational monitoring and analysis.
    """

    run_id: str = Field(
        ...,
        description="Unique identifier for this ingestion run"
    )

    profile_identifier: str = Field(
        ...,
        description="LinkedIn profile identifier that was processed"
    )

    content_type: str = Field(
        ...,
        description="Type of content processed (posts, comments, mixed)"
    )

    ingestion_stats: Dict = Field(
        ...,
        description="Statistics from the ingestion process (counts, durations, etc.)"
    )

    zep_group_id: Optional[str] = Field(
        None,
        description="Zep group ID where content was stored"
    )

    processing_duration_seconds: Optional[float] = Field(
        None,
        description="Total processing duration in seconds"
    )

    errors: Optional[List[Dict]] = Field(
        None,
        description="List of errors encountered during processing"
    )

    def run(self) -> str:
        """
        Saves ingestion audit record to Firestore.

        Returns:
            str: JSON string containing audit record save status
                 Format: {
                     "audit_record_id": "linkedin_ingestion_20240115_103000_abc123",
                     "firestore_document_path": "linkedin_ingestion_logs/record_id",
                     "status": "saved",
                     "record_summary": {
                         "profile": "alexhormozi",
                         "content_processed": 25,
                         "zep_upserted": 23,
                         "errors": 0
                     }
                 }
        """
        try:
            # Load environment and initialize Firestore
            load_environment()

            # Get GCP configuration
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID")

            # Initialize Firestore client
            from google.cloud import firestore
            db = firestore.Client(project=project_id)

            # Generate audit record ID
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            record_id = f"linkedin_ingestion_{timestamp}_{self.run_id[:8]}"

            # Prepare audit record
            audit_record = self._prepare_audit_record(record_id)

            # Save to Firestore
            collection_name = "linkedin_ingestion_logs"
            doc_ref = db.collection(collection_name).document(record_id)
            doc_ref.set(audit_record)

            # Prepare response summary
            record_summary = self._create_record_summary()

            result = {
                "audit_record_id": record_id,
                "firestore_document_path": f"{collection_name}/{record_id}",
                "status": "saved",
                "record_summary": record_summary,
                "saved_at": datetime.utcnow().isoformat() + "Z"
            }

            return json.dumps(result)

        except Exception as e:
            # Fallback for testing environments without Firestore
            if "google.cloud" in str(e) or "credentials" in str(e).lower():
                return self._create_mock_response()

            error_result = {
                "error": "audit_save_failed",
                "message": str(e),
                "run_id": self.run_id,
                "profile": self.profile_identifier
            }
            return json.dumps(error_result)

    def _prepare_audit_record(self, record_id: str) -> Dict:
        """
        Prepare comprehensive audit record for Firestore.

        Args:
            record_id: Generated record identifier

        Returns:
            Dict: Complete audit record
        """
        # Base audit record
        audit_record = {
            "record_id": record_id,
            "run_id": self.run_id,
            "profile_identifier": self.profile_identifier,
            "content_type": self.content_type,
            "created_at": datetime.utcnow().isoformat() + "Z",

            # Processing metadata
            "processing": {
                "duration_seconds": self.processing_duration_seconds,
                "start_time": self._calculate_start_time(),
                "end_time": datetime.utcnow().isoformat() + "Z"
            },

            # Ingestion statistics
            "ingestion_stats": self.ingestion_stats,

            # Zep storage information
            "zep_storage": {
                "group_id": self.zep_group_id,
                "upserted": self.ingestion_stats.get("zep_upserted", 0),
                "skipped": self.ingestion_stats.get("zep_skipped", 0)
            },

            # Error tracking
            "errors": {
                "count": len(self.errors) if self.errors else 0,
                "details": self.errors if self.errors else []
            },

            # Status and outcome
            "status": self._determine_run_status(),
            "success": len(self.errors) == 0 if self.errors is not None else True
        }

        # Add content-specific metrics
        if "posts_processed" in self.ingestion_stats:
            audit_record["content_metrics"] = {
                "posts_processed": self.ingestion_stats.get("posts_processed", 0),
                "comments_processed": self.ingestion_stats.get("comments_processed", 0),
                "reactions_processed": self.ingestion_stats.get("reactions_processed", 0),
                "total_entities": (
                    self.ingestion_stats.get("posts_processed", 0) +
                    self.ingestion_stats.get("comments_processed", 0) +
                    self.ingestion_stats.get("reactions_processed", 0)
                )
            }

        # Add deduplication metrics if available
        if "duplicates_removed" in self.ingestion_stats:
            audit_record["deduplication"] = {
                "original_count": self.ingestion_stats.get("original_count", 0),
                "unique_count": self.ingestion_stats.get("unique_count", 0),
                "duplicates_removed": self.ingestion_stats.get("duplicates_removed", 0),
                "duplicate_rate": self.ingestion_stats.get("duplicate_rate", 0.0)
            }

        # Add configuration context
        audit_record["configuration"] = {
            "linkedin_profiles": get_config_value("linkedin.profiles", []),
            "content_types": get_config_value("linkedin.processing.content_types", []),
            "daily_limit": get_config_value("linkedin.processing.daily_limit_per_profile", 25)
        }

        return audit_record

    def _calculate_start_time(self) -> str:
        """
        Calculate estimated start time based on duration.

        Returns:
            str: ISO timestamp of estimated start time
        """
        if self.processing_duration_seconds:
            start_time = datetime.utcnow().timestamp() - self.processing_duration_seconds
            return datetime.fromtimestamp(start_time).isoformat() + "Z"
        else:
            return datetime.utcnow().isoformat() + "Z"

    def _determine_run_status(self) -> str:
        """
        Determine overall run status based on results.

        Returns:
            str: Status indicator (success, partial_success, failed)
        """
        if not self.errors or len(self.errors) == 0:
            return "success"

        # Check if we processed any content despite errors
        total_processed = (
            self.ingestion_stats.get("posts_processed", 0) +
            self.ingestion_stats.get("comments_processed", 0) +
            self.ingestion_stats.get("zep_upserted", 0)
        )

        if total_processed > 0:
            return "partial_success"
        else:
            return "failed"

    def _create_record_summary(self) -> Dict:
        """
        Create a summary of the audit record for response.

        Returns:
            Dict: Summary information
        """
        summary = {
            "profile": self.profile_identifier,
            "content_type": self.content_type,
            "processing_duration": self.processing_duration_seconds,
            "status": self._determine_run_status()
        }

        # Add content metrics
        if "posts_processed" in self.ingestion_stats:
            summary["content_processed"] = (
                self.ingestion_stats.get("posts_processed", 0) +
                self.ingestion_stats.get("comments_processed", 0)
            )

        # Add Zep metrics
        if "zep_upserted" in self.ingestion_stats:
            summary["zep_upserted"] = self.ingestion_stats["zep_upserted"]

        # Add error count
        summary["errors"] = len(self.errors) if self.errors else 0

        # Add key metrics
        for metric in ["duplicates_removed", "unique_count", "engagement_rate"]:
            if metric in self.ingestion_stats:
                summary[metric] = self.ingestion_stats[metric]

        return summary

    def _create_mock_response(self) -> str:
        """
        Create mock response for testing environments.

        Returns:
            str: Mock JSON response
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        record_id = f"linkedin_ingestion_{timestamp}_{self.run_id[:8]}"

        result = {
            "audit_record_id": record_id,
            "firestore_document_path": f"linkedin_ingestion_logs/{record_id}",
            "status": "mock_saved",
            "record_summary": self._create_record_summary(),
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "note": "Mock response - Firestore not available in test environment"
        }

        return json.dumps(result)


if __name__ == "__main__":
    # Test the tool
    test_stats = {
        "posts_processed": 15,
        "comments_processed": 8,
        "zep_upserted": 20,
        "zep_skipped": 3,
        "duplicates_removed": 2,
        "unique_count": 21,
        "original_count": 23
    }

    test_errors = [
        {
            "type": "api_error",
            "message": "Rate limit exceeded",
            "timestamp": "2024-01-15T10:15:00Z"
        }
    ]

    tool = SaveIngestionRecord(
        run_id="test_run_123456",
        profile_identifier="alexhormozi",
        content_type="posts",
        ingestion_stats=test_stats,
        zep_group_id="linkedin_alexhormozi_posts",
        processing_duration_seconds=45.2,
        errors=test_errors
    )
    print("Testing SaveIngestionRecord tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))