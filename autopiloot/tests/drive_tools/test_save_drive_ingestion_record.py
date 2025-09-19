"""
Test suite for SaveDriveIngestionRecord tool.
Tests Firestore audit logging with comprehensive metrics and performance tracking.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock environment and dependencies before importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
}):
    from unittest.mock import MagicMock
    mock_base_tool = MagicMock()
    mock_field = MagicMock()

    with patch('drive_agent.tools.save_drive_ingestion_record.BaseTool', mock_base_tool):
        with patch('drive_agent.tools.save_drive_ingestion_record.Field', mock_field):
            from drive_agent.tools.save_drive_ingestion_record import SaveDriveIngestionRecord


class TestSaveDriveIngestionRecord(unittest.TestCase):
    """Test cases for SaveDriveIngestionRecord tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_targets = [
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

        self.sample_stats = {
            "files_discovered": 16,
            "files_processed": 15,
            "text_extraction_count": 15,
            "zep_upserted": 18,
            "chunks_created": 18,
            "bytes_processed": 2048000,
            "api_calls_made": 45
        }

        self.sample_errors = [
            {
                "file_id": "file_456",
                "type": "permission_error",
                "message": "Permission denied",
                "severity": "warning"
            }
        ]

        self.sample_checkpoint = {
            "last_sync_timestamp": "2025-01-15T10:30:00Z",
            "processed_file_ids": ["file_789"],
            "next_check_recommended": "2025-01-15T13:30:00Z"
        }

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_successful_record_save(self, mock_get_env, mock_load_env):
        """Test successful audit record save to Firestore."""
        mock_get_env.return_value = "test_project_id"

        # Mock Firestore client and operations
        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_summary_ref = MagicMock()

        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_summary_ref

        with patch('drive_agent.tools.save_drive_ingestion_record.firestore.Client', return_value=mock_db):
            tool = SaveDriveIngestionRecord(
                run_id="test_run_001",
                namespace="autopiloot_drive_content",
                targets_processed=self.sample_targets,
                ingestion_stats=self.sample_stats,
                processing_duration_seconds=125.5,
                checkpoint_data=self.sample_checkpoint,
                errors=self.sample_errors,
                sync_interval_minutes=60
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "saved")
        self.assertIn("audit_record_id", result)
        self.assertIn("firestore_document_path", result)

        # Check record summary
        summary = result["record_summary"]
        self.assertEqual(summary["namespace"], "autopiloot_drive_content")
        self.assertEqual(summary["files_processed"], 15)
        self.assertEqual(summary["zep_documents_upserted"], 18)
        self.assertEqual(summary["processing_duration_seconds"], 125.5)
        self.assertEqual(summary["errors"], 1)

        # Verify Firestore calls
        mock_doc_ref.set.assert_called_once()
        mock_summary_ref.set.assert_called_once()

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_minimal_record_save(self, mock_get_env, mock_load_env):
        """Test saving record with minimal required fields only."""
        mock_get_env.return_value = "test_project_id"

        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_summary_ref = MagicMock()

        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_summary_ref

        minimal_stats = {
            "files_discovered": 5,
            "files_processed": 5,
            "text_extraction_count": 5,
            "zep_upserted": 5
        }

        with patch('drive_agent.tools.save_drive_ingestion_record.firestore.Client', return_value=mock_db):
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
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "saved")
        summary = result["record_summary"]
        self.assertEqual(summary["files_processed"], 5)
        self.assertEqual(summary["success_rate_percent"], 100.0)

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_success_rate_calculation(self, mock_get_env, mock_load_env):
        """Test success rate calculation with partial failures."""
        mock_get_env.return_value = "test_project_id"

        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_summary_ref = MagicMock()

        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_summary_ref

        # 10 discovered, 8 processed = 80% success rate
        partial_stats = {
            "files_discovered": 10,
            "files_processed": 8,
            "text_extraction_count": 8,
            "zep_upserted": 8
        }

        with patch('drive_agent.tools.save_drive_ingestion_record.firestore.Client', return_value=mock_db):
            tool = SaveDriveIngestionRecord(
                run_id="test_run_003",
                namespace="test_namespace",
                targets_processed=self.sample_targets,
                ingestion_stats=partial_stats
            )
            result_str = tool.run()
            result = json.loads(result_str)

        summary = result["record_summary"]
        self.assertEqual(summary["success_rate_percent"], 80.0)

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_error_categorization(self, mock_get_env, mock_load_env):
        """Test error categorization and critical error detection."""
        mock_get_env.return_value = "test_project_id"

        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_summary_ref = MagicMock()

        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_summary_ref

        errors_with_critical = [
            {
                "file_id": "file_001",
                "type": "permission_error",
                "message": "Permission denied",
                "severity": "warning"
            },
            {
                "file_id": "file_002",
                "type": "api_error",
                "message": "API quota exceeded",
                "severity": "critical"
            },
            {
                "file_id": "file_003",
                "type": "permission_error",
                "message": "Access denied",
                "severity": "warning"
            }
        ]

        with patch('drive_agent.tools.save_drive_ingestion_record.firestore.Client', return_value=mock_db):
            tool = SaveDriveIngestionRecord(
                run_id="test_run_004",
                namespace="test_namespace",
                targets_processed=self.sample_targets,
                ingestion_stats=self.sample_stats,
                errors=errors_with_critical
            )
            result_str = tool.run()
            result = json.loads(result_str)

        summary = result["record_summary"]
        self.assertEqual(summary["errors"], 3)
        self.assertEqual(summary["status"], "completed_with_errors")  # Due to critical error

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_missing_gcp_project_id(self, mock_get_env, mock_load_env):
        """Test handling of missing GCP project ID."""
        mock_get_env.side_effect = Exception("GCP_PROJECT_ID not found")

        tool = SaveDriveIngestionRecord(
            run_id="test_run_005",
            namespace="test_namespace",
            targets_processed=self.sample_targets,
            ingestion_stats=self.sample_stats
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "save_failed")
        self.assertIn("GCP_PROJECT_ID not found", result["message"])

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_firestore_connection_error(self, mock_get_env, mock_load_env):
        """Test handling of Firestore connection errors."""
        mock_get_env.return_value = "test_project_id"

        with patch('drive_agent.tools.save_drive_ingestion_record.firestore.Client') as mock_client:
            mock_client.side_effect = Exception("Firestore connection failed")

            tool = SaveDriveIngestionRecord(
                run_id="test_run_006",
                namespace="test_namespace",
                targets_processed=self.sample_targets,
                ingestion_stats=self.sample_stats
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "save_failed")
        self.assertIn("Firestore connection failed", result["message"])

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_performance_metrics_calculation(self, mock_get_env, mock_load_env):
        """Test calculation of performance metrics."""
        mock_get_env.return_value = "test_project_id"

        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_summary_ref = MagicMock()

        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_summary_ref

        with patch('drive_agent.tools.save_drive_ingestion_record.firestore.Client', return_value=mock_db):
            tool = SaveDriveIngestionRecord(
                run_id="test_run_007",
                namespace="test_namespace",
                targets_processed=self.sample_targets,
                ingestion_stats=self.sample_stats,
                processing_duration_seconds=150.0  # 2.5 minutes
            )
            result_str = tool.run()
            result = json.loads(result_str)

        # Check that performance metrics are calculated
        self.assertIn("processing_duration_seconds", result["record_summary"])

        # Verify the saved audit record includes performance data
        saved_call = mock_doc_ref.set.call_args[0][0]
        self.assertIn("performance", saved_call)
        self.assertEqual(saved_call["performance"]["processing_duration_seconds"], 150.0)

    @patch('drive_agent.tools.save_drive_ingestion_record.load_environment')
    @patch('drive_agent.tools.save_drive_ingestion_record.get_required_env_var')
    def test_checkpoint_data_storage(self, mock_get_env, mock_load_env):
        """Test storage of checkpoint data for incremental processing."""
        mock_get_env.return_value = "test_project_id"

        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_summary_ref = MagicMock()

        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_summary_ref

        with patch('drive_agent.tools.save_drive_ingestion_record.firestore.Client', return_value=mock_db):
            tool = SaveDriveIngestionRecord(
                run_id="test_run_008",
                namespace="test_namespace",
                targets_processed=self.sample_targets,
                ingestion_stats=self.sample_stats,
                checkpoint_data=self.sample_checkpoint
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertTrue(result["checkpoint_saved"])

        # Verify checkpoint data is saved in audit record
        saved_call = mock_doc_ref.set.call_args[0][0]
        self.assertIn("checkpoint", saved_call)
        self.assertEqual(saved_call["checkpoint"], self.sample_checkpoint)


if __name__ == '__main__':
    unittest.main()