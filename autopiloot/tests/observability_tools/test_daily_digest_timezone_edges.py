"""
Edge case tests for GenerateDailyDigest tool - Timezone edge scenarios.

This module tests the daily digest generation with timezone complexities including
DST transitions, timezone boundaries, cross-timezone data, and edge cases.
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


class TestDailyDigestTimezoneEdges(unittest.TestCase):
    """Test cases for daily digest generation with timezone edge scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = "2025-03-30"  # Near DST transition in Europe
        self.test_timezone = "Europe/Amsterdam"

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dst_transition_spring_forward(self, mock_config, mock_env, mock_firestore):
        """Test digest during DST spring forward transition (shorter day)."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # DST transition day: March 30, 2025 (Europe/Amsterdam springs forward)
        # 2:00 AM becomes 3:00 AM, so day is only 23 hours
        dst_date = "2025-03-30"

        # Videos created around DST transition time
        dst_videos = [
            Mock(to_dict=lambda: {
                "video_id": "pre_dst_video",
                "title": "Before DST",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 3, 30, 1, 30, tzinfo=timezone.utc)  # 1:30 AM UTC = 2:30 CET
            }),
            Mock(to_dict=lambda: {
                "video_id": "post_dst_video",
                "title": "After DST",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 3, 30, 1, 30, tzinfo=timezone.utc)  # Same UTC time, different local
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = dst_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=dst_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle DST transition gracefully
        self.assertEqual(result["date"], dst_date)
        self.assertIn("summary", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_dst_transition_fall_back(self, mock_config, mock_env, mock_firestore):
        """Test digest during DST fall back transition (longer day)."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # DST transition day: October 26, 2025 (Europe/Amsterdam falls back)
        # 3:00 AM becomes 2:00 AM, so day is 25 hours
        dst_date = "2025-10-26"

        # Videos created during the "repeated" hour
        dst_videos = [
            Mock(to_dict=lambda: {
                "video_id": "first_2am_video",
                "title": "First 2 AM",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 10, 26, 1, 0, tzinfo=timezone.utc)  # First 2 AM local
            }),
            Mock(to_dict=lambda: {
                "video_id": "second_2am_video",
                "title": "Second 2 AM",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 10, 26, 2, 0, tzinfo=timezone.utc)  # Second 2 AM local
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = dst_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=dst_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle DST transition gracefully and count both videos
        self.assertEqual(result["date"], dst_date)
        self.assertEqual(result["summary"]["videos_discovered"], 2)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_cross_timezone_data_utc_vs_local(self, mock_config, mock_env, mock_firestore):
        """Test digest when data spans timezone boundaries."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Videos created at timezone boundary times
        boundary_videos = [
            Mock(to_dict=lambda: {
                "video_id": "late_night_video",
                "title": "Late Night",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 9, 15, 22, 0, tzinfo=timezone.utc)  # 22:00 UTC = 00:00 Amsterdam next day
            }),
            Mock(to_dict=lambda: {
                "video_id": "early_morning_video",
                "title": "Early Morning",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 9, 16, 4, 0, tzinfo=timezone.utc)  # 04:00 UTC = 06:00 Amsterdam same day
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = boundary_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        # Generate digest for September 16, 2025
        tool = GenerateDailyDigest(date="2025-09-16", timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should include both videos as they're in the Amsterdam day
        self.assertEqual(result["summary"]["videos_discovered"], 2)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_invalid_timezone_fallback(self, mock_config, mock_env, mock_firestore):
        """Test digest with invalid timezone falls back gracefully."""
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

        # Invalid timezone should cause error
        tool = GenerateDailyDigest(date=self.test_date, timezone_name="Invalid/Timezone")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("timezone", result["error"].lower())

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_timezone_with_unusual_offset(self, mock_config, mock_env, mock_firestore):
        """Test digest with timezone having unusual offset (e.g., 30-minute offset)."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Videos in unusual timezone context
        offset_videos = [Mock(to_dict=lambda: {
            "video_id": "offset_video",
            "title": "Offset Timezone Video",
            "status": "transcribed",
            "duration_sec": 1800,
            "source": "scrape",
            "created_at": datetime(2025, 9, 15, 12, 0, tzinfo=timezone.utc)
        })]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = offset_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        # Test with Adelaide (UTC+9:30)
        tool = GenerateDailyDigest(date=self.test_date, timezone_name="Australia/Adelaide")
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle unusual offset timezone
        self.assertIn("summary", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_timezone_edge_case_utc_plus_14(self, mock_config, mock_env, mock_firestore):
        """Test digest with extreme timezone (UTC+14)."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Videos created in extreme timezone context
        extreme_videos = [Mock(to_dict=lambda: {
            "video_id": "extreme_tz_video",
            "title": "Extreme Timezone Video",
            "status": "transcribed",
            "duration_sec": 1800,
            "source": "scrape",
            "created_at": datetime(2025, 9, 15, 12, 0, tzinfo=timezone.utc)
        })]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = extreme_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        # Test with Kiritimati (UTC+14)
        tool = GenerateDailyDigest(date=self.test_date, timezone_name="Pacific/Kiritimati")
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle extreme timezone
        self.assertIn("summary", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_data_across_international_date_line(self, mock_config, mock_env, mock_firestore):
        """Test digest when data spans the international date line."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Videos created around international date line
        dateline_videos = [
            Mock(to_dict=lambda: {
                "video_id": "west_of_dateline",
                "title": "West of Date Line",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 9, 15, 11, 0, tzinfo=timezone.utc)  # Sept 15 in Samoa
            }),
            Mock(to_dict=lambda: {
                "video_id": "east_of_dateline",
                "title": "East of Date Line",
                "status": "transcribed",
                "duration_sec": 1800,
                "source": "scrape",
                "created_at": datetime(2025, 9, 15, 13, 0, tzinfo=timezone.utc)  # Sept 16 in Samoa
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = dateline_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        # Generate digest for September 16 Samoa time
        tool = GenerateDailyDigest(date="2025-09-16", timezone_name="Pacific/Apia")
        result_str = tool.run()
        result = json.loads(result_str)

        # Should correctly handle date line crossing
        self.assertIn("summary", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_leap_second_edge_case(self, mock_config, mock_env, mock_firestore):
        """Test digest on dates with potential leap second adjustments."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Videos created around potential leap second times
        leap_videos = [Mock(to_dict=lambda: {
            "video_id": "leap_second_video",
            "title": "Leap Second Video",
            "status": "transcribed",
            "duration_sec": 1800,
            "source": "scrape",
            "created_at": datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)  # End of year
        })]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "videos":
                mock_coll.where.return_value.where.return_value.stream.return_value = leap_videos
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date="2025-12-31", timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle edge timestamp cases
        self.assertIn("summary", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_empty_timezone_string(self, mock_config, mock_env, mock_firestore):
        """Test digest with empty timezone string."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: default

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        tool = GenerateDailyDigest(date=self.test_date, timezone_name="")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("timezone", result["error"].lower())

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_timezone_case_sensitivity(self, mock_config, mock_env, mock_firestore):
        """Test digest with different timezone name casing."""
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

        # Test various casings - should all fail as timezone names are case-sensitive
        invalid_timezones = ["europe/amsterdam", "EUROPE/AMSTERDAM", "Europe/amsterdam"]

        for invalid_tz in invalid_timezones:
            with self.subTest(timezone=invalid_tz):
                tool = GenerateDailyDigest(date=self.test_date, timezone_name=invalid_tz)
                result_str = tool.run()
                result = json.loads(result_str)

                self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()