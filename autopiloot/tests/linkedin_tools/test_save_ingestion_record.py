"""
Unit tests for SaveIngestionRecord tool.
Tests Firestore integration, audit record creation, and mock handling.
"""

import unittest
import json
from unittest.mock import patch, Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.save_ingestion_record import SaveIngestionRecord


class TestSaveIngestionRecord(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.test_stats = {
            "posts_processed": 15,
            "comments_processed": 45,
            "reactions_processed": 200,
            "zep_upserted": 58,
            "zep_skipped": 2,
            "duplicates_removed": 3,
            "unique_count": 57,
            "original_count": 60,
            "duplicate_rate": 0.05
        }

        self.test_errors = [
            {
                "type": "api_rate_limit",
                "message": "Rate limit exceeded for LinkedIn API",
                "timestamp": "2024-01-15T10:15:00Z",
                "retry_count": 3
            },
            {
                "type": "zep_timeout",
                "message": "Zep upsert timeout after 30 seconds",
                "timestamp": "2024-01-15T10:20:00Z",
                "batch_size": 10
            }
        ]

        self.tool = SaveIngestionRecord(
            run_id="test_run_123456",
            profile_identifier="alexhormozi",
            content_type="mixed",
            ingestion_stats=self.test_stats,
            zep_group_id="linkedin_alexhormozi_mixed",
            processing_duration_seconds=180.5,
            errors=self.test_errors
        )

    @patch('linkedin_agent.tools.save_ingestion_record.firestore.Client')
    @patch('linkedin_agent.tools.save_ingestion_record.load_environment')
    @patch('linkedin_agent.tools.save_ingestion_record.get_required_env_var')
    @patch('linkedin_agent.tools.save_ingestion_record.get_config_value')
    def test_successful_audit_save(self, mock_config, mock_env_var, mock_load_env, mock_firestore):
        """Test successful audit record save to Firestore."""
        # Mock environment and configuration
        mock_env_var.return_value = "test-gcp-project"
        mock_config.side_effect = lambda key, default: {
            "linkedin.profiles": ["alexhormozi", "garyvee"],
            "linkedin.processing.content_types": ["posts", "comments"],
            "linkedin.processing.daily_limit_per_profile": 25
        }.get(key, default)

        # Mock Firestore client
        mock_db = Mock()
        mock_collection = Mock()
        mock_doc_ref = Mock()

        mock_firestore.return_value = mock_db
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["status"], "saved")
        self.assertIn("linkedin_ingestion_", result_data["audit_record_id"])
        self.assertEqual(result_data["firestore_document_path"], f"linkedin_ingestion_logs/{result_data['audit_record_id']}")

        # Check record summary
        summary = result_data["record_summary"]
        self.assertEqual(summary["profile"], "alexhormozi")
        self.assertEqual(summary["content_type"], "mixed")
        self.assertEqual(summary["processing_duration"], 180.5)
        self.assertEqual(summary["status"], "partial_success")  # Has errors but processed content
        self.assertEqual(summary["content_processed"], 60)  # posts + comments
        self.assertEqual(summary["zep_upserted"], 58)
        self.assertEqual(summary["errors"], 2)

        # Verify Firestore calls
        mock_db.collection.assert_called_with("linkedin_ingestion_logs")
        mock_doc_ref.set.assert_called_once()

        # Check the audit record structure
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["run_id"], "test_run_123456")
        self.assertEqual(set_call_args["profile_identifier"], "alexhormozi")
        self.assertEqual(set_call_args["content_type"], "mixed")
        self.assertEqual(set_call_args["processing"]["duration_seconds"], 180.5)
        self.assertEqual(set_call_args["ingestion_stats"], self.test_stats)
        self.assertEqual(set_call_args["zep_storage"]["group_id"], "linkedin_alexhormozi_mixed")
        self.assertEqual(set_call_args["errors"]["count"], 2)
        self.assertEqual(set_call_args["errors"]["details"], self.test_errors)

    def test_mock_response_fallback(self):
        """Test mock response when Firestore is not available."""
        # Run without mocking Firestore (will trigger mock response)
        result = self.tool.run()
        result_data = json.loads(result)

        # Should return mock response
        self.assertEqual(result_data["status"], "mock_saved")
        self.assertIn("Mock response", result_data["note"])
        self.assertIn("linkedin_ingestion_", result_data["audit_record_id"])

        # Should still have proper record summary
        summary = result_data["record_summary"]
        self.assertEqual(summary["profile"], "alexhormozi")
        self.assertEqual(summary["content_type"], "mixed")

    def test_status_determination(self):
        """Test run status determination logic."""
        # Test success status (no errors)
        tool_success = SaveIngestionRecord(
            run_id="success_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={"posts_processed": 10, "zep_upserted": 10},
            errors=[]
        )

        status = tool_success._determine_run_status()
        self.assertEqual(status, "success")

        # Test partial success (errors but content processed)
        tool_partial = SaveIngestionRecord(
            run_id="partial_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={"posts_processed": 5, "zep_upserted": 3},
            errors=[{"type": "minor_error", "message": "Some issue"}]
        )

        status = tool_partial._determine_run_status()
        self.assertEqual(status, "partial_success")

        # Test failed status (errors and no content processed)
        tool_failed = SaveIngestionRecord(
            run_id="failed_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={"posts_processed": 0, "zep_upserted": 0},
            errors=[{"type": "critical_error", "message": "Complete failure"}]
        )

        status = tool_failed._determine_run_status()
        self.assertEqual(status, "failed")

    def test_comprehensive_audit_record(self):
        """Test comprehensive audit record structure."""
        tool = SaveIngestionRecord(
            run_id="comprehensive_test",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={
                "posts_processed": 20,
                "comments_processed": 50,
                "reactions_processed": 100,
                "zep_upserted": 65,
                "zep_skipped": 5,
                "duplicates_removed": 8,
                "unique_count": 62,
                "original_count": 70,
                "duplicate_rate": 0.114
            },
            processing_duration_seconds=240.0,
            errors=None
        )

        # Test audit record preparation
        record = tool._prepare_audit_record("test_record_id")

        # Check basic fields
        self.assertEqual(record["record_id"], "test_record_id")
        self.assertEqual(record["run_id"], "comprehensive_test")
        self.assertEqual(record["profile_identifier"], "testuser")
        self.assertEqual(record["content_type"], "posts")

        # Check processing info
        self.assertEqual(record["processing"]["duration_seconds"], 240.0)
        self.assertIn("start_time", record["processing"])
        self.assertIn("end_time", record["processing"])

        # Check Zep storage info
        self.assertEqual(record["zep_storage"]["upserted"], 65)
        self.assertEqual(record["zep_storage"]["skipped"], 5)

        # Check content metrics
        self.assertIn("content_metrics", record)
        metrics = record["content_metrics"]
        self.assertEqual(metrics["posts_processed"], 20)
        self.assertEqual(metrics["comments_processed"], 50)
        self.assertEqual(metrics["reactions_processed"], 100)
        self.assertEqual(metrics["total_entities"], 170)

        # Check deduplication metrics
        self.assertIn("deduplication", record)
        dedup = record["deduplication"]
        self.assertEqual(dedup["original_count"], 70)
        self.assertEqual(dedup["unique_count"], 62)
        self.assertEqual(dedup["duplicates_removed"], 8)
        self.assertEqual(dedup["duplicate_rate"], 0.114)

        # Check status and success
        self.assertEqual(record["status"], "success")
        self.assertTrue(record["success"])

    def test_start_time_calculation(self):
        """Test start time calculation from duration."""
        tool = SaveIngestionRecord(
            run_id="time_test",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={"posts_processed": 1},
            processing_duration_seconds=120.0
        )

        start_time = tool._calculate_start_time()

        # Should be ISO format timestamp
        self.assertTrue(start_time.endswith("Z"))
        self.assertIn("T", start_time)

        # Should be roughly 2 minutes ago (allowing for test execution time)
        from datetime import datetime
        calculated_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        now = datetime.utcnow()
        diff_seconds = (now - calculated_time).total_seconds()
        self.assertGreater(diff_seconds, 115)  # At least 115 seconds ago
        self.assertLess(diff_seconds, 125)     # But not more than 125 seconds ago

    def test_record_summary_creation(self):
        """Test record summary creation for response."""
        summary = self.tool._create_record_summary()

        # Check basic fields
        self.assertEqual(summary["profile"], "alexhormozi")
        self.assertEqual(summary["content_type"], "mixed")
        self.assertEqual(summary["processing_duration"], 180.5)
        self.assertEqual(summary["status"], "partial_success")

        # Check calculated fields
        self.assertEqual(summary["content_processed"], 60)  # posts + comments
        self.assertEqual(summary["zep_upserted"], 58)
        self.assertEqual(summary["errors"], 2)

        # Check included metrics
        self.assertEqual(summary["duplicates_removed"], 3)
        self.assertEqual(summary["unique_count"], 57)

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            SaveIngestionRecord()  # Missing all required fields

        with self.assertRaises(Exception):
            SaveIngestionRecord(
                run_id="test",
                profile_identifier="user"
                # Missing content_type and ingestion_stats
            )

        # Test with minimal required fields
        tool = SaveIngestionRecord(
            run_id="minimal_test",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={"posts_processed": 5}
        )
        self.assertEqual(tool.run_id, "minimal_test")
        self.assertEqual(tool.profile_identifier, "testuser")
        self.assertEqual(tool.content_type, "posts")
        self.assertIsNone(tool.zep_group_id)
        self.assertIsNone(tool.processing_duration_seconds)
        self.assertIsNone(tool.errors)

        # Test with optional fields
        tool_full = SaveIngestionRecord(
            run_id="full_test",
            profile_identifier="testuser",
            content_type="mixed",
            ingestion_stats={"total": 100},
            zep_group_id="test_group",
            processing_duration_seconds=60.0,
            errors=[{"type": "test", "message": "test error"}]
        )
        self.assertEqual(tool_full.zep_group_id, "test_group")
        self.assertEqual(tool_full.processing_duration_seconds, 60.0)
        self.assertEqual(len(tool_full.errors), 1)


if __name__ == '__main__':
    unittest.main()