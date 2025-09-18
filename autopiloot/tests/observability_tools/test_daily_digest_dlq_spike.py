"""
Edge case tests for GenerateDailyDigest tool - DLQ spike scenarios.

This module tests the daily digest generation when there are high volumes of
dead letter queue items, anomalous error patterns, and system health degradation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from observability_agent.tools.generate_daily_digest import GenerateDailyDigest


class TestDailyDigestDLQSpike(unittest.TestCase):
    """Test cases for daily digest generation with DLQ spike scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = "2025-09-15"
        self.test_timezone = "Europe/Amsterdam"

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_extreme_dlq_volume(self, mock_config, mock_env, mock_firestore):
        """Test digest when DLQ has extremely high volume of failed jobs."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Generate large number of DLQ entries
        dlq_entries = []
        for i in range(100):  # 100 failed jobs
            dlq_entries.append(Mock(to_dict=lambda i=i: {
                "job_id": f"failed_job_{i}",
                "job_type": "transcription" if i % 2 == 0 else "summary",
                "error_type": "quota_exceeded" if i % 3 == 0 else "timeout",
                "retry_count": 3,
                "failed_at": datetime(2025, 9, 15, 10 + (i % 12), 0, tzinfo=timezone.utc),
                "error_message": f"Error message for job {i}"
            }))

        # Mock other collections with normal data
        normal_videos = [Mock(to_dict=lambda: {
            "video_id": "video1",
            "title": "Normal Video",
            "status": "summarized",
            "duration_sec": 1800,
            "source": "scrape",
            "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
        })]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = dlq_entries
            elif collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = normal_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should highlight DLQ spike in summary
        self.assertGreaterEqual(result["summary"]["errors_deadletter"], 50)
        self.assertIn("issues", result)
        self.assertGreater(len(result["issues"]), 0)

        # Slack blocks should indicate system issues
        slack_text = json.dumps(result["slack_blocks"])
        self.assertIn("⚠️", slack_text)  # Warning emoji
        self.assertIn("dead", slack_text.lower())

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dlq_with_same_error_pattern(self, mock_config, mock_env, mock_firestore):
        """Test digest when DLQ shows pattern of same error type."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # All DLQ entries have same error type (indicating systematic issue)
        dlq_entries = []
        for i in range(20):
            dlq_entries.append(Mock(to_dict=lambda i=i: {
                "job_id": f"failed_job_{i}",
                "job_type": "transcription",
                "error_type": "quota_exceeded",  # Same error for all
                "retry_count": 3,
                "failed_at": datetime(2025, 9, 15, 10 + (i % 12), 0, tzinfo=timezone.utc),
                "error_message": "YouTube API quota exceeded"
            }))

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = dlq_entries
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should identify pattern in issues
        self.assertIn("issues", result)
        issues_text = json.dumps(result["issues"])
        self.assertIn("quota_exceeded", issues_text)
        self.assertIn("pattern", issues_text.lower())

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dlq_exceeds_normal_processing_volume(self, mock_config, mock_env, mock_firestore):
        """Test digest when DLQ volume exceeds successful processing."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # More failures than successes
        dlq_entries = [Mock(to_dict=lambda i=i: {
            "job_id": f"failed_job_{i}",
            "job_type": "transcription",
            "error_type": "api_error",
            "retry_count": 3,
            "failed_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
        }) for i in range(50)]

        # Fewer successful videos
        successful_videos = [Mock(to_dict=lambda i=i: {
            "video_id": f"video_{i}",
            "title": f"Video {i}",
            "status": "summarized",
            "duration_sec": 1800,
            "source": "scrape",
            "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
        }) for i in range(5)]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = dlq_entries
            elif collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = successful_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should indicate system health issues
        self.assertGreater(result["summary"]["errors_deadletter"], result["summary"]["videos_processed"])
        self.assertIn("issues", result)

        # Health status should be degraded
        slack_text = json.dumps(result["slack_blocks"])
        self.assertIn("🔴", slack_text)  # Red status indicator

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dlq_with_multiple_error_types_analysis(self, mock_config, mock_env, mock_firestore):
        """Test digest analysis when DLQ has diverse error types."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Diverse error types
        error_types = [
            "quota_exceeded", "timeout", "api_error", "network_error",
            "authentication_failed", "rate_limited", "service_unavailable"
        ]

        dlq_entries = []
        for i, error_type in enumerate(error_types * 3):  # 21 entries total
            dlq_entries.append(Mock(to_dict=lambda i=i, et=error_type: {
                "job_id": f"failed_job_{i}",
                "job_type": "transcription",
                "error_type": et,
                "retry_count": 3,
                "failed_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            }))

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = dlq_entries
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should analyze error distribution
        self.assertIn("issues", result)
        self.assertGreaterEqual(len(result["issues"]), 1)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dlq_with_cascading_failures(self, mock_config, mock_env, mock_firestore):
        """Test digest when DLQ shows cascading failure pattern."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Simulate cascading failures - increasing failure rate over time
        dlq_entries = []
        base_time = datetime(2025, 9, 15, 8, 0, tzinfo=timezone.utc)

        for hour in range(12):  # 12 hours of data
            failures_this_hour = min(hour * 2, 20)  # Increasing failures
            for i in range(failures_this_hour):
                dlq_entries.append(Mock(to_dict=lambda h=hour, i=i: {
                    "job_id": f"failed_job_{h}_{i}",
                    "job_type": "transcription",
                    "error_type": "cascading_failure",
                    "retry_count": 3,
                    "failed_at": base_time + timedelta(hours=h, minutes=i*2)
                }))

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = dlq_entries
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should identify escalating pattern
        self.assertGreater(result["summary"]["errors_deadletter"], 50)
        self.assertIn("issues", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dlq_with_corrupted_job_data(self, mock_config, mock_env, mock_firestore):
        """Test digest when DLQ contains corrupted or malformed job data."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Mix of valid and corrupted DLQ entries
        dlq_entries = [
            # Valid entry
            Mock(to_dict=lambda: {
                "job_id": "valid_job_1",
                "job_type": "transcription",
                "error_type": "timeout",
                "retry_count": 3,
                "failed_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            }),
            # Corrupted entries
            Mock(to_dict=lambda: {
                "job_id": None,  # Missing job ID
                "job_type": "transcription",
                "error_type": "unknown"
            }),
            Mock(to_dict=lambda: None),  # Document returns None
            Mock(to_dict=lambda: {
                "job_id": "",  # Empty job ID
                "job_type": "",
                "error_type": None,
                "retry_count": "not_a_number",
                "failed_at": "invalid_timestamp"
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = dlq_entries
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle corrupted data gracefully
        self.assertIn("summary", result)
        self.assertGreaterEqual(result["summary"]["errors_deadletter"], 1)  # At least one valid

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dlq_memory_stress_large_dataset(self, mock_config, mock_env, mock_firestore):
        """Test digest with very large DLQ dataset (memory stress test)."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Simulate very large DLQ dataset
        def generate_large_dlq():
            for i in range(1000):  # 1000 entries
                yield Mock(to_dict=lambda i=i: {
                    "job_id": f"failed_job_{i}",
                    "job_type": "transcription",
                    "error_type": f"error_type_{i % 10}",
                    "retry_count": 3,
                    "failed_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc),
                    "error_message": f"Error message for job {i}" * 10  # Large message
                })

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = generate_large_dlq()
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle large dataset without memory issues
        self.assertIn("summary", result)
        self.assertGreaterEqual(result["summary"]["errors_deadletter"], 500)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dlq_zero_retry_attempts(self, mock_config, mock_env, mock_firestore):
        """Test digest when DLQ has jobs with zero retry attempts (immediate failures)."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Jobs that failed immediately without retries
        dlq_entries = [Mock(to_dict=lambda i=i: {
            "job_id": f"immediate_failure_{i}",
            "job_type": "transcription",
            "error_type": "validation_error",
            "retry_count": 0,  # No retries
            "failed_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
        }) for i in range(10)]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "jobs_deadletter":
                mock_coll.where.return_value.where.return_value.stream.return_value = dlq_entries
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should identify immediate failure pattern
        self.assertEqual(result["summary"]["errors_deadletter"], 10)
        self.assertIn("issues", result)


if __name__ == "__main__":
    unittest.main()