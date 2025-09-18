"""
Edge case tests for GenerateDailyDigest tool - Empty day scenarios.

This module tests the daily digest generation when there's no data, empty collections,
or minimal activity for the target date.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys
from datetime import datetime, timezone, timedelta
import pytz

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from observability_agent.tools.generate_daily_digest import GenerateDailyDigest


class TestDailyDigestEmptyDay(unittest.TestCase):
    """Test cases for daily digest generation with empty/minimal data scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = "2025-09-15"
        self.test_timezone = "Europe/Amsterdam"

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_completely_empty_day_no_data(self, mock_config, mock_env, mock_firestore):
        """Test digest generation when absolutely no data exists for the date."""
        # Mock environment and config
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        # Mock Firestore client with empty collections
        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # All collections return empty results
        empty_stream = Mock()
        empty_stream.stream.return_value = []

        mock_client.collection.return_value.where.return_value.where.return_value = empty_stream
        mock_client.collection.return_value.where.return_value = empty_stream
        mock_client.collection.return_value.document.return_value.get.return_value.exists = False

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle empty day gracefully
        self.assertIn("date", result)
        self.assertEqual(result["date"], self.test_date)
        self.assertIn("summary", result)
        self.assertIn("slack_blocks", result)

        # Summary should indicate no activity
        self.assertIn("0", str(result["summary"]["videos_processed"]))
        self.assertEqual(result["summary"]["total_cost_usd"], 0.0)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_videos_discovered_but_not_processed(self, mock_config, mock_env, mock_firestore):
        """Test digest when videos are discovered but none are processed."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Mock discovered videos but no transcripts or summaries
        discovered_videos = [
            Mock(to_dict=lambda: {
                "video_id": "video1",
                "title": "Unprocessed Video 1",
                "status": "discovered",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            }),
            Mock(to_dict=lambda: {
                "video_id": "video2",
                "title": "Unprocessed Video 2",
                "status": "discovered",
                "duration_sec": 2400,
                "source": "sheet",
                "created_at": datetime(2025, 9, 15, 14, 0, tzinfo=timezone.utc)
            })
        ]

        # Setup mock collection responses
        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = discovered_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            # Empty daily costs document
            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should show discovered but unprocessed videos
        self.assertEqual(result["summary"]["videos_discovered"], 2)
        self.assertEqual(result["summary"]["videos_transcribed"], 0)
        self.assertEqual(result["summary"]["videos_summarized"], 0)
        self.assertEqual(result["summary"]["total_cost_usd"], 0.0)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_no_costs_data_available(self, mock_config, mock_env, mock_firestore):
        """Test digest when no cost tracking data is available."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Mock some videos and transcripts but no cost data
        mock_videos = [
            Mock(to_dict=lambda: {
                "video_id": "video1",
                "title": "Test Video",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            })
        ]

        mock_transcripts = [
            Mock(to_dict=lambda: {
                "video_id": "video1",
                "status": "completed",
                # Missing costs field
                "created_at": datetime(2025, 9, 15, 11, 0, tzinfo=timezone.utc)
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = mock_videos
            elif collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = mock_transcripts
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            # No daily costs document
            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle missing cost data gracefully
        self.assertEqual(result["summary"]["total_cost_usd"], 0.0)
        self.assertEqual(result["summary"]["videos_transcribed"], 1)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_invalid_date_format(self, mock_config, mock_env, mock_firestore):
        """Test digest with invalid date format."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Test various invalid date formats
        invalid_dates = ["2025/09/15", "15-09-2025", "invalid-date", "", "2025-13-45"]

        for invalid_date in invalid_dates:
            with self.subTest(date=invalid_date):
                tool = GenerateDailyDigest(date=invalid_date, timezone_name=self.test_timezone)
                result_str = tool.run()
                result = json.loads(result_str)

                self.assertIn("error", result)
                self.assertIn("invalid_date", result["error"])

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_invalid_timezone(self, mock_config, mock_env, mock_firestore):
        """Test digest with invalid timezone."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Test with invalid timezone
        tool = GenerateDailyDigest(date=self.test_date, timezone_name="Invalid/Timezone")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("timezone", result["error"].lower())

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_firestore_connection_failure(self, mock_config, mock_env, mock_firestore):
        """Test digest when Firestore connection fails."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        # Mock Firestore client that raises connection error
        mock_firestore.side_effect = Exception("Connection failed")

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("firestore", result["error"].lower())

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_corrupted_document_data(self, mock_config, mock_env, mock_firestore):
        """Test digest with corrupted/malformed document data."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Mock documents with corrupted data
        corrupted_videos = [
            Mock(to_dict=lambda: {
                "video_id": None,  # Invalid video_id
                "title": "",  # Empty title
                "status": "unknown_status",
                "duration_sec": "not_a_number",  # Invalid duration
                "created_at": "invalid_timestamp"
            }),
            Mock(to_dict=lambda: None),  # Document returns None
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = corrupted_videos
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
        # Should filter out corrupted documents
        self.assertLessEqual(result["summary"]["videos_discovered"], 1)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_no_slack_blocks_in_response(self, mock_config, mock_env, mock_firestore):
        """Test that Slack blocks are always included even for empty days."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Empty collections
        empty_stream = Mock()
        empty_stream.stream.return_value = []
        mock_client.collection.return_value.where.return_value.where.return_value = empty_stream
        mock_client.collection.return_value.where.return_value = empty_stream
        mock_client.collection.return_value.document.return_value.get.return_value.exists = False

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Slack blocks should always be present
        self.assertIn("slack_blocks", result)
        self.assertIsInstance(result["slack_blocks"], list)
        self.assertGreater(len(result["slack_blocks"]), 0)

        # Should have at least header and summary blocks
        block_types = [block.get("type") for block in result["slack_blocks"]]
        self.assertIn("header", block_types)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_future_date_handling(self, mock_config, mock_env, mock_firestore):
        """Test digest generation for future dates."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Empty results for future date
        empty_stream = Mock()
        empty_stream.stream.return_value = []
        mock_client.collection.return_value.where.return_value.where.return_value = empty_stream
        mock_client.collection.return_value.where.return_value = empty_stream
        mock_client.collection.return_value.document.return_value.get.return_value.exists = False

        # Test with tomorrow's date
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        tool = GenerateDailyDigest(date=tomorrow, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should generate digest for future date (empty but valid)
        self.assertEqual(result["date"], tomorrow)
        self.assertEqual(result["summary"]["videos_processed"], 0)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_missing_required_environment_variables(self, mock_config, mock_env, mock_firestore):
        """Test digest when required environment variables are missing."""
        # Mock missing GCP_PROJECT_ID
        mock_env.side_effect = ValueError("GCP_PROJECT_ID environment variable is required")
        mock_config.side_effect = lambda key, default: default

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("environment", result["error"].lower())


if __name__ == "__main__":
    unittest.main()