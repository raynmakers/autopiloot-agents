"""
Orchestrate RAG Ingestion tool for coordinating fan-out after transcript save.
Implements TASK-RAG-0072O with retry logic, DLQ routing, and non-blocking failures.

Fan-out sequence:
1. Zep upsert (semantic search)
2. OpenSearch index (keyword search)
3. BigQuery stream (SQL analytics)
"""

import os
import sys
import json
import time
from typing import Dict, Any, Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class OrchestrateRagIngestion(BaseTool):
    """
    Orchestrates RAG ingestion fan-out after transcript save with retry and DLQ.

    Coordinates sequential ingestion to:
    - Zep (semantic search via vector embeddings)
    - OpenSearch (keyword search via BM25)
    - BigQuery (SQL analytics with metadata-only storage)

    Features:
    - Idempotent operations via content hashing
    - Retry logic with exponential backoff
    - DLQ routing for failed operations
    - Non-blocking failures with alerts
    - Comprehensive status tracking
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for RAG ingestion"
    )

    max_retries: int = Field(
        default=2,
        description="Maximum retry attempts per RAG operation (default: 2)"
    )

    retry_delay_sec: int = Field(
        default=5,
        description="Base delay in seconds between retries with exponential backoff (default: 5)"
    )

    def run(self) -> str:
        """
        Execute RAG fan-out with retry logic and failure handling.

        Process:
        1. Validate transcript exists in Firestore
        2. Load transcript text and video metadata
        3. Call Zep upsert with retry
        4. Call OpenSearch index with retry
        5. Call BigQuery stream with retry
        6. Return aggregated status

        Returns:
            JSON string with per-system status and overall result

        Raises:
            ValueError: If video or transcript doesn't exist
            RuntimeError: If critical Firestore operation fails
        """
        try:
            # Load configuration
            config = load_app_config()

            # Check if RAG auto-ingest is enabled
            auto_ingest_enabled = config.get("rag", {}).get("auto_ingest_after_transcription", False)

            if not auto_ingest_enabled:
                return json.dumps({
                    "status": "skipped",
                    "message": "RAG auto-ingest disabled in settings.yaml",
                    "video_id": self.video_id,
                    "config_flag": "rag.auto_ingest_after_transcription"
                }, indent=2)

            print(f"🚀 Orchestrating RAG ingestion for video: {self.video_id}")

            # Initialize Firestore
            db = self._initialize_firestore()

            # Load transcript and video metadata
            transcript_data = self._load_transcript_data(db)
            if "error" in transcript_data:
                return json.dumps(transcript_data, indent=2)

            print(f"   ✓ Loaded transcript ({transcript_data['char_count']} chars)")

            # Initialize results tracking
            results = {
                "video_id": self.video_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operations": {}
            }

            # Operation sequence: Zep → OpenSearch → BigQuery
            operations = [
                {"name": "zep", "tool": "UpsertFullTranscriptToZep"},
                {"name": "opensearch", "tool": "IndexFullTranscriptToOpenSearch"},
                {"name": "bigquery", "tool": "StreamFullTranscriptToBigQuery"}
            ]

            # Execute each operation with retry
            for op in operations:
                op_name = op["name"]
                print(f"\n📤 Starting {op_name.upper()} ingestion...")

                op_result = self._execute_with_retry(
                    operation_name=op_name,
                    tool_name=op["tool"],
                    transcript_data=transcript_data
                )

                results["operations"][op_name] = op_result

                if op_result["status"] == "success":
                    print(f"   ✅ {op_name.upper()}: {op_result['message']}")
                elif op_result["status"] == "skipped":
                    print(f"   ⚪ {op_name.upper()}: {op_result['message']}")
                else:
                    print(f"   ❌ {op_name.upper()}: {op_result['message']}")

            # Calculate overall status
            success_count = sum(1 for op in results["operations"].values() if op["status"] == "success")
            skipped_count = sum(1 for op in results["operations"].values() if op["status"] == "skipped")
            failed_count = sum(1 for op in results["operations"].values() if op["status"] == "failed")

            if success_count + skipped_count == len(operations):
                overall_status = "success"
                message = f"All RAG operations completed ({success_count} success, {skipped_count} skipped)"
            elif success_count > 0:
                overall_status = "partial"
                message = f"Partial RAG ingestion ({success_count} success, {failed_count} failed, {skipped_count} skipped)"
            else:
                overall_status = "failed"
                message = f"All RAG operations failed ({failed_count} failed, {skipped_count} skipped)"

            results["overall_status"] = overall_status
            results["message"] = message
            results["success_count"] = success_count
            results["failed_count"] = failed_count
            results["skipped_count"] = skipped_count

            print(f"\n{'='*60}")
            print(f"✅ RAG Orchestration Complete: {message}")
            print(f"{'='*60}")

            # Log orchestration result to audit trail
            audit_logger.log_custom_event(
                event_type="rag_orchestration_complete",
                entity_id=self.video_id,
                details={
                    "overall_status": overall_status,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "operations": {k: v["status"] for k, v in results["operations"].items()}
                },
                actor="OrchestratorAgent"
            )

            return json.dumps(results, indent=2)

        except Exception as e:
            error_msg = str(e)
            print(f"❌ RAG orchestration error: {error_msg}")

            return json.dumps({
                "error": "orchestration_failed",
                "message": f"Failed to orchestrate RAG ingestion: {error_msg}",
                "video_id": self.video_id
            })

    def _load_transcript_data(self, db) -> Dict[str, Any]:
        """Load transcript text and video metadata from Firestore."""
        try:
            # Load transcript
            transcript_ref = db.collection('transcripts').document(self.video_id)
            transcript_doc = transcript_ref.get()

            if not transcript_doc.exists:
                return {
                    "error": "transcript_not_found",
                    "message": f"No transcript found for video {self.video_id}",
                    "video_id": self.video_id
                }

            transcript_data = transcript_doc.to_dict()
            transcript_text = transcript_data.get('transcript_text')

            if not transcript_text:
                return {
                    "error": "transcript_text_missing",
                    "message": f"Transcript document exists but text is empty for video {self.video_id}",
                    "video_id": self.video_id
                }

            # Load video metadata
            video_ref = db.collection('videos').document(self.video_id)
            video_doc = video_ref.get()

            video_metadata = {}
            if video_doc.exists:
                video_data = video_doc.to_dict()
                video_metadata = {
                    "title": video_data.get('title'),
                    "channel_id": video_data.get('channel_id'),
                    "channel_handle": video_data.get('channel_handle'),
                    "published_at": video_data.get('published_at'),
                    "duration_sec": video_data.get('duration_sec')
                }

            return {
                "video_id": self.video_id,
                "transcript_text": transcript_text,
                "char_count": len(transcript_text),
                **video_metadata
            }

        except Exception as e:
            return {
                "error": "firestore_load_failed",
                "message": f"Failed to load transcript data: {str(e)}",
                "video_id": self.video_id
            }

    def _execute_with_retry(
        self,
        operation_name: str,
        tool_name: str,
        transcript_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute RAG operation with retry logic and DLQ routing.

        Args:
            operation_name: Name of operation (zep, opensearch, bigquery)
            tool_name: Tool class name to execute
            transcript_data: Transcript text and video metadata

        Returns:
            Dict with status, message, and optional error details
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.retry_delay_sec * (2 ** (attempt - 1))  # Exponential backoff
                    print(f"   ⏳ Retry {attempt}/{self.max_retries} after {delay}s delay...")
                    time.sleep(delay)

                # Execute RAG tool
                result = self._call_rag_tool(tool_name, transcript_data)
                result_data = json.loads(result)

                # Check if operation was successful
                if "error" in result_data:
                    last_error = result_data["message"]

                    # Check if error is retryable
                    if self._is_retryable_error(result_data.get("error")):
                        continue  # Retry
                    else:
                        # Non-retryable error, fail immediately
                        break

                # Check for success status
                if result_data.get("status") in ["stored", "indexed", "streamed", "success"]:
                    return {
                        "status": "success",
                        "message": result_data.get("message", f"{operation_name} completed successfully"),
                        "details": result_data
                    }

                # Check for skipped status (service not configured)
                if result_data.get("status") == "skipped":
                    return {
                        "status": "skipped",
                        "message": result_data.get("message", f"{operation_name} not configured"),
                        "details": result_data
                    }

                # Unexpected status
                last_error = f"Unexpected status: {result_data.get('status')}"

            except Exception as e:
                last_error = str(e)
                print(f"   ⚠️ Attempt {attempt + 1} failed: {last_error}")

        # All retries exhausted, route to DLQ and send alert
        self._handle_failure(operation_name, last_error, transcript_data)

        return {
            "status": "failed",
            "message": f"{operation_name} failed after {self.max_retries + 1} attempts: {last_error}",
            "error": last_error,
            "retry_count": self.max_retries + 1
        }

    def _call_rag_tool(self, tool_name: str, transcript_data: Dict[str, Any]) -> str:
        """Dynamically import and execute RAG tool."""
        # Import tool module
        tool_module_name = self._snake_case(tool_name)
        module_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            f'{tool_module_name}.py'
        )

        if not os.path.exists(module_path):
            raise FileNotFoundError(f"Tool module not found: {module_path}")

        # Dynamic import
        import importlib.util
        spec = importlib.util.spec_from_file_location(tool_module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get tool class
        tool_class = getattr(module, tool_name)

        # Create tool instance with transcript data
        tool_instance = tool_class(
            video_id=transcript_data["video_id"],
            transcript_text=transcript_data["transcript_text"],
            channel_id=transcript_data.get("channel_id"),
            title=transcript_data.get("title"),
            channel_handle=transcript_data.get("channel_handle"),
            published_at=transcript_data.get("published_at"),
            duration_sec=transcript_data.get("duration_sec")
        )

        # Execute tool
        return tool_instance.run()

    def _is_retryable_error(self, error_type: str) -> bool:
        """Determine if error is retryable."""
        # Retryable errors
        retryable = [
            "connection",
            "timeout",
            "rate_limit",
            "service_unavailable",
            "temporary_failure"
        ]

        # Non-retryable errors
        non_retryable = [
            "authentication",
            "authorization",
            "invalid_input",
            "not_found",
            "already_exists"
        ]

        error_lower = error_type.lower() if error_type else ""

        for retryable_type in retryable:
            if retryable_type in error_lower:
                return True

        for non_retryable_type in non_retryable:
            if non_retryable_type in error_lower:
                return False

        # Default to retryable for unknown errors
        return True

    def _handle_failure(
        self,
        operation_name: str,
        error_message: str,
        transcript_data: Dict[str, Any]
    ):
        """Route failed operation to DLQ and send alert."""
        try:
            # Import HandleDLQ tool
            sys.path.append(os.path.join(os.path.dirname(__file__)))
            from handle_dlq import HandleDLQ

            # Create DLQ entry
            dlq_tool = HandleDLQ(
                job_id=f"rag_{operation_name}_{self.video_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                job_type=f"rag_{operation_name}_ingestion",
                failure_context={
                    "error_type": "rag_ingestion_failure",
                    "error_message": error_message,
                    "retry_count": self.max_retries,
                    "last_attempt_at": datetime.now(timezone.utc).isoformat(),
                    "original_inputs": {
                        "video_id": self.video_id,
                        "operation": operation_name,
                        "title": transcript_data.get("title"),
                        "channel_id": transcript_data.get("channel_id")
                    }
                },
                recovery_hints={
                    "manual_action_required": True,
                    "suggested_fix": f"Check {operation_name} service status and credentials",
                    "retry_tool": "OrchestrateRagIngestion",
                    "retry_params": {"video_id": self.video_id}
                }
            )

            dlq_result = dlq_tool.run()
            print(f"   📋 DLQ: Routed to dead letter queue")

        except Exception as dlq_error:
            print(f"   ⚠️ Warning: Failed to route to DLQ: {str(dlq_error)}")

        try:
            # Send error alert
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'observability_agent', 'tools'))
            from send_rag_error_alert import SendRagErrorAlert

            alerter = SendRagErrorAlert(
                video_id=self.video_id,
                operation=f"{operation_name}_ingestion",
                storage_system=operation_name,
                error_message=error_message,
                error_type="ingestion_failure",
                video_title=transcript_data.get("title"),
                channel_id=transcript_data.get("channel_id"),
                additional_context={
                    "retry_count": self.max_retries,
                    "orchestrator": "OrchestrateRagIngestion"
                }
            )

            alert_result = alerter.run()
            print(f"   📢 Alert: Sent to Slack")

        except Exception as alert_error:
            print(f"   ⚠️ Warning: Failed to send alert: {str(alert_error)}")

    def _snake_case(self, name: str) -> str:
        """Convert PascalCase to snake_case."""
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore")
            credentials_path = get_required_env_var("GOOGLE_APPLICATION_CREDENTIALS", "Google service account credentials file path")

            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")

            return firestore.Client(project=project_id)

        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Orchestrate RAG Ingestion")
    print("="*80)

    # Test with a video that has a transcript
    test_video_id = "dQw4w9WgXcQ"  # Replace with actual test video ID

    try:
        tool = OrchestrateRagIngestion(
            video_id=test_video_id,
            max_retries=1,  # Reduced for testing
            retry_delay_sec=2
        )

        result = tool.run()
        print("\n" + "="*80)
        print("✅ Test completed:")
        print("="*80)
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
        else:
            print(f"\n📊 Orchestration Summary:")
            print(f"   Overall Status: {data['overall_status']}")
            print(f"   Success: {data['success_count']}")
            print(f"   Failed: {data['failed_count']}")
            print(f"   Skipped: {data['skipped_count']}")
            print(f"\n   Operations:")
            for op_name, op_result in data['operations'].items():
                print(f"   - {op_name.upper()}: {op_result['status']} - {op_result['message']}")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
