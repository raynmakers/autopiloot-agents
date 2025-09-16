"""
Test suite for GenerateDailyDigest tool - PRD daily digest requirement
Tests comprehensive digest generation with metrics, Slack formatting, and error handling
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


class TestGenerateDailyDigest(unittest.TestCase):
    """Test cases for the daily digest generation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = "2025-09-15"
        self.test_timezone = "Europe/Amsterdam"

        # Sample Firestore data for testing
        self.sample_videos = [
            {
                "video_id": "test_video_1",
                "title": "Business Strategy Masterclass",
                "status": "summarized",
                "duration_sec": 3600,
                "source": "scrape",
                "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            },
            {
                "video_id": "test_video_2",
                "title": "Sales Training Session",
                "status": "transcribed",
                "duration_sec": 2400,
                "source": "sheet",
                "created_at": datetime(2025, 9, 15, 14, 30, tzinfo=timezone.utc)
            }
        ]

        self.sample_transcripts = [
            {
                "costs": {"transcription_usd": 1.50},
                "created_at": datetime(2025, 9, 15, 11, 0, tzinfo=timezone.utc)
            },
            {
                "costs": {"transcription_usd": 1.20},
                "created_at": datetime(2025, 9, 15, 15, 0, tzinfo=timezone.utc)
            }
        ]

        self.sample_summaries = [
            {"created_at": datetime(2025, 9, 15, 12, 0, tzinfo=timezone.utc)}
        ]

        self.sample_cost_doc = {
            "transcription_usd_total": 2.70,
            "alerts_sent": 0
        }

        self.sample_dlq_entries = [
            {
                "job_type": "transcription",
                "reason": "timeout",
                "retry_count": 3,
                "created_at": datetime(2025, 9, 15, 16, 0, tzinfo=timezone.utc)
            }
        ]

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.load_app_config')
    @patch('observability_agent.tools.generate_daily_digest.audit_logger')
    def test_successful_digest_generation(self, mock_audit, mock_config, mock_firestore):
        """Test successful digest generation with sample data."""
        # Setup mocks
        mock_db = Mock()
        mock_firestore.return_value = mock_db

        mock_config.return_value = {
            "google_drive": {
                "folder_id_transcripts": "transcript_folder_123",
                "folder_id_summaries": "summary_folder_456"
            }
        }

        # Mock Firestore queries
        self._setup_firestore_mocks(mock_db)

        # Create and run tool
        tool = GenerateDailyDigest(
            date=self.test_date,
            timezone_name=self.test_timezone
        )

        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["date"], self.test_date)
        self.assertEqual(result_data["timezone"], self.test_timezone)

        # Check metrics
        metrics = result_data["metrics"]
        self.assertEqual(metrics["videos_discovered"], 2)
        self.assertEqual(metrics["videos_transcribed"], 2)
        self.assertEqual(metrics["summaries_generated"], 1)
        self.assertEqual(metrics["total_cost_usd"], 2.70)
        self.assertEqual(metrics["dlq_entries"], 1)

        # Check Slack blocks structure
        slack_blocks = result_data["slack_blocks"]
        self.assertIsInstance(slack_blocks, list)
        self.assertGreater(len(slack_blocks), 5)  # Header, sections, footer

        # Verify audit logging
        mock_audit.log.assert_called_once()

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.load_app_config')
    @patch('observability_agent.tools.generate_daily_digest.audit_logger')
    def test_empty_day_digest(self, mock_audit, mock_config, mock_firestore):
        """Test digest generation when no videos were processed."""
        # Setup mocks for empty day
        mock_db = Mock()
        mock_firestore.return_value = mock_db

        mock_config.return_value = {"google_drive": {}}

        # Mock empty Firestore queries
        self._setup_empty_firestore_mocks(mock_db)

        # Create and run tool
        tool = GenerateDailyDigest(
            date=self.test_date,
            timezone_name=self.test_timezone
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assertions for empty day
        self.assertNotIn("error", result_data)
        metrics = result_data["metrics"]
        self.assertEqual(metrics["videos_discovered"], 0)
        self.assertEqual(metrics["videos_transcribed"], 0)
        self.assertEqual(metrics["summaries_generated"], 0)
        self.assertEqual(metrics["total_cost_usd"], 0.0)
        self.assertEqual(metrics["dlq_entries"], 0)

        # Should still have Slack blocks
        self.assertIn("slack_blocks", result_data)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.load_app_config')
    @patch('observability_agent.tools.generate_daily_digest.audit_logger')
    def test_high_activity_day(self, mock_audit, mock_config, mock_firestore):
        """Test digest generation with high activity and budget threshold."""
        # Setup mocks
        mock_db = Mock()
        mock_firestore.return_value = mock_db

        mock_config.return_value = {"google_drive": {}}

        # Mock high-activity data
        self._setup_high_activity_mocks(mock_db)

        # Create and run tool
        tool = GenerateDailyDigest(
            date=self.test_date,
            timezone_name=self.test_timezone
        )

        result = tool.run()
        result_data = json.loads(result)

        # Check high activity metrics
        metrics = result_data["metrics"]
        self.assertGreaterEqual(metrics["videos_discovered"], 5)
        self.assertGreater(metrics["total_cost_usd"], 4.0)  # Close to $5 budget
        self.assertGreater(metrics["budget_percentage"], 80.0)  # Above warning threshold

        # Check digest content reflects high activity
        digest_content = result_data["digest_content"]
        self.assertIn("budget_status", digest_content)
        self.assertIn("🟡", digest_content["budget_status"]["emoji"])  # Warning emoji

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.load_app_config')
    @patch('observability_agent.tools.generate_daily_digest.audit_logger')
    def test_error_conditions_with_dlq(self, mock_audit, mock_config, mock_firestore):
        """Test digest generation with errors and DLQ entries."""
        # Setup mocks
        mock_db = Mock()
        mock_firestore.return_value = mock_db

        mock_config.return_value = {"google_drive": {}}

        # Mock data with multiple DLQ entries
        self._setup_error_condition_mocks(mock_db)

        # Create and run tool
        tool = GenerateDailyDigest(
            date=self.test_date,
            timezone_name=self.test_timezone
        )

        result = tool.run()
        result_data = json.loads(result)

        # Check error handling
        metrics = result_data["metrics"]
        self.assertGreater(metrics["dlq_entries"], 2)

        # Check error section in digest
        digest_content = result_data["digest_content"]
        self.assertIn("issues", digest_content)
        self.assertNotEqual(digest_content["issues"]["summary"], "None")

    def test_timezone_handling(self):
        """Test proper timezone conversion for Europe/Amsterdam."""
        # Test with different timezone
        tool = GenerateDailyDigest(
            date=self.test_date,
            timezone_name="US/Pacific"
        )

        # Check that timezone is properly stored
        self.assertEqual(tool.timezone_name, "US/Pacific")

        # Test default timezone
        tool_default = GenerateDailyDigest(date=self.test_date)
        self.assertEqual(tool_default.timezone_name, "Europe/Amsterdam")

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.load_app_config')
    @patch('observability_agent.tools.generate_daily_digest.audit_logger')
    def test_slack_block_validation(self, mock_audit, mock_config, mock_firestore):
        """Test that Slack blocks conform to Block Kit standards."""
        # Setup basic mocks
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        mock_config.return_value = {"google_drive": {}}
        self._setup_firestore_mocks(mock_db)

        # Create and run tool
        tool = GenerateDailyDigest(
            date=self.test_date,
            timezone_name=self.test_timezone
        )

        result = tool.run()
        result_data = json.loads(result)

        # Validate Slack block structure
        slack_blocks = result_data["slack_blocks"]

        # Check required block types
        block_types = [block.get("type") for block in slack_blocks]
        self.assertIn("header", block_types)
        self.assertIn("section", block_types)
        self.assertIn("context", block_types)

        # Validate header block
        header_blocks = [b for b in slack_blocks if b.get("type") == "header"]
        self.assertEqual(len(header_blocks), 1)
        self.assertIn("text", header_blocks[0])
        self.assertEqual(header_blocks[0]["text"]["type"], "plain_text")

        # Validate section blocks have proper mrkdwn format
        section_blocks = [b for b in slack_blocks if b.get("type") == "section"]
        for section in section_blocks:
            self.assertIn("text", section)
            self.assertEqual(section["text"]["type"], "mrkdwn")

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.audit_logger')
    def test_firestore_connection_error(self, mock_audit, mock_firestore):
        """Test error handling when Firestore connection fails."""
        # Make Firestore client raise an exception
        mock_firestore.side_effect = Exception("Firestore connection failed")

        # Create and run tool
        tool = GenerateDailyDigest(
            date=self.test_date,
            timezone_name=self.test_timezone
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should return error response
        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "digest_generation_failed")
        self.assertIn("Firestore connection failed", result_data["message"])

        # Should log error to audit
        mock_audit.log.assert_called_once()

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.load_app_config')
    @patch('observability_agent.tools.generate_daily_digest.audit_logger')
    def test_date_edge_cases(self, mock_audit, mock_config, mock_firestore):
        """Test date handling for edge cases like month boundaries."""
        # Setup mocks
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        mock_config.return_value = {"google_drive": {}}
        self._setup_firestore_mocks(mock_db)

        # Test month boundary date
        tool = GenerateDailyDigest(
            date="2025-10-01",  # First day of month
            timezone_name=self.test_timezone
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should process successfully
        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["date"], "2025-10-01")

    def _setup_firestore_mocks(self, mock_db):
        """Helper to setup Firestore mocks with sample data."""
        # Mock videos collection
        mock_videos_collection = Mock()
        mock_videos_query = Mock()
        mock_videos_stream = Mock()

        mock_videos_docs = []
        for i, video in enumerate(self.sample_videos):
            mock_doc = Mock()
            mock_doc.id = video["video_id"]
            mock_doc.to_dict.return_value = video
            mock_videos_docs.append(mock_doc)

        mock_videos_stream.return_value = mock_videos_docs
        mock_videos_query.stream = mock_videos_stream
        mock_videos_collection.where.return_value.where.return_value = mock_videos_query
        mock_db.collection.side_effect = lambda name: {
            'videos': mock_videos_collection,
            'transcripts': self._mock_transcripts_collection(),
            'summaries': self._mock_summaries_collection(),
            'costs_daily': self._mock_costs_collection(),
            'jobs_deadletter': self._mock_dlq_collection()
        }[name]

    def _mock_transcripts_collection(self):
        """Mock transcripts collection."""
        mock_collection = Mock()
        mock_query = Mock()
        mock_stream = Mock()

        mock_docs = []
        for transcript in self.sample_transcripts:
            mock_doc = Mock()
            mock_doc.to_dict.return_value = transcript
            mock_docs.append(mock_doc)

        mock_stream.return_value = mock_docs
        mock_query.stream = mock_stream
        mock_collection.where.return_value.where.return_value = mock_query
        return mock_collection

    def _mock_summaries_collection(self):
        """Mock summaries collection."""
        mock_collection = Mock()
        mock_query = Mock()
        mock_stream = Mock()

        mock_docs = []
        for summary in self.sample_summaries:
            mock_doc = Mock()
            mock_doc.to_dict.return_value = summary
            mock_docs.append(mock_doc)

        mock_stream.return_value = mock_docs
        mock_query.stream = mock_stream
        mock_collection.where.return_value.where.return_value = mock_query
        return mock_collection

    def _mock_costs_collection(self):
        """Mock costs_daily collection."""
        mock_collection = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = self.sample_cost_doc
        mock_collection.document.return_value.get.return_value = mock_doc
        return mock_collection

    def _mock_dlq_collection(self):
        """Mock DLQ collection."""
        mock_collection = Mock()
        mock_query = Mock()
        mock_stream = Mock()

        mock_docs = []
        for dlq_entry in self.sample_dlq_entries:
            mock_doc = Mock()
            mock_doc.to_dict.return_value = dlq_entry
            mock_docs.append(mock_doc)

        mock_stream.return_value = mock_docs
        mock_query.stream = mock_stream
        mock_collection.where.return_value.where.return_value = mock_query
        return mock_collection

    def _setup_empty_firestore_mocks(self, mock_db):
        """Setup mocks for empty day scenario."""
        mock_collection = Mock()
        mock_query = Mock()
        mock_stream = Mock()
        mock_stream.return_value = []  # Empty results
        mock_query.stream = mock_stream
        mock_collection.where.return_value.where.return_value = mock_query

        # Empty cost document
        mock_cost_doc = Mock()
        mock_cost_doc.exists = False
        mock_collection.document.return_value.get.return_value = mock_cost_doc

        mock_db.collection.return_value = mock_collection

    def _setup_high_activity_mocks(self, mock_db):
        """Setup mocks for high activity day scenario."""
        # Generate high activity data
        high_activity_videos = []
        for i in range(8):  # 8 videos discovered
            high_activity_videos.append({
                "video_id": f"high_activity_video_{i}",
                "title": f"High Activity Video {i}",
                "status": "summarized",
                "duration_sec": 1800,
                "source": "scrape"
            })

        high_activity_transcripts = []
        for i in range(7):  # 7 transcribed
            high_activity_transcripts.append({
                "costs": {"transcription_usd": 0.65}  # Total: $4.55
            })

        # Mock collections with high activity data
        self._setup_collection_with_data(mock_db, 'videos', high_activity_videos)
        self._setup_collection_with_data(mock_db, 'transcripts', high_activity_transcripts)
        self._setup_collection_with_data(mock_db, 'summaries', [{}] * 6)  # 6 summaries

        # High cost day
        mock_cost_collection = Mock()
        mock_cost_doc = Mock()
        mock_cost_doc.exists = True
        mock_cost_doc.to_dict.return_value = {"transcription_usd_total": 4.55}
        mock_cost_collection.document.return_value.get.return_value = mock_cost_doc

        mock_db.collection.side_effect = lambda name: {
            'costs_daily': mock_cost_collection
        }.get(name, self._mock_default_collection())

    def _setup_error_condition_mocks(self, mock_db):
        """Setup mocks for error condition scenario."""
        # Multiple DLQ entries
        error_dlq_entries = [
            {"job_type": "transcription", "reason": "timeout", "retry_count": 3},
            {"job_type": "summarization", "reason": "api_error", "retry_count": 2},
            {"job_type": "transcription", "reason": "quota_exceeded", "retry_count": 3}
        ]

        self._setup_collection_with_data(mock_db, 'jobs_deadletter', error_dlq_entries)
        self._setup_collection_with_data(mock_db, 'videos', self.sample_videos[:1])  # Some videos
        self._setup_collection_with_data(mock_db, 'transcripts', [])  # No transcripts
        self._setup_collection_with_data(mock_db, 'summaries', [])  # No summaries

    def _setup_collection_with_data(self, mock_db, collection_name, data):
        """Helper to setup a collection mock with specific data."""
        mock_collection = Mock()
        mock_query = Mock()
        mock_stream = Mock()

        mock_docs = []
        for item in data:
            mock_doc = Mock()
            mock_doc.to_dict.return_value = item
            mock_docs.append(mock_doc)

        mock_stream.return_value = mock_docs
        mock_query.stream = mock_stream
        mock_collection.where.return_value.where.return_value = mock_query

        # Add to db collection mapping
        if not hasattr(mock_db, '_collections'):
            mock_db._collections = {}
        mock_db._collections[collection_name] = mock_collection

        # Update side_effect function
        def collection_side_effect(name):
            return mock_db._collections.get(name, self._mock_default_collection())

        mock_db.collection.side_effect = collection_side_effect

    def _mock_default_collection(self):
        """Default empty collection mock."""
        mock_collection = Mock()
        mock_query = Mock()
        mock_stream = Mock()
        mock_stream.return_value = []
        mock_query.stream = mock_stream
        mock_collection.where.return_value.where.return_value = mock_query
        return mock_collection


if __name__ == '__main__':
    unittest.main()