"""
Edge case tests for GenerateDailyDigest tool - Cost overrun scenarios.

This module tests the daily digest generation when costs exceed budgets,
budget thresholds are breached, and cost tracking anomalies occur.
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


class TestDailyDigestCostOverrun(unittest.TestCase):
    """Test cases for daily digest generation with cost overrun scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_date = "2025-09-15"
        self.test_timezone = "Europe/Amsterdam"

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_cost_exceeds_daily_budget_threshold(self, mock_config, mock_env, mock_firestore):
        """Test digest when transcription costs exceed daily budget threshold."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 5.0,
            "budgets.alert_threshold": 0.8
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # High-cost transcripts that exceed budget
        expensive_transcripts = []
        for i in range(10):
            expensive_transcripts.append(Mock(to_dict=lambda i=i: {
                "video_id": f"expensive_video_{i}",
                "status": "completed",
                "costs": {"transcription_usd": 1.2},  # $1.2 each = $12 total (>$5 budget)
                "created_at": datetime(2025, 9, 15, 10 + i, 0, tzinfo=timezone.utc)
            }))

        # Mock daily costs document showing budget overrun
        mock_daily_costs = Mock()
        mock_daily_costs.exists = True
        mock_daily_costs.to_dict.return_value = {
            "date": self.test_date,
            "transcription_usd": 12.0,
            "budget_usd": 5.0,
            "budget_percentage": 240.0,  # 240% of budget
            "transaction_count": 10
        }

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = expensive_transcripts
            elif collection_name == "costs_daily":
                mock_coll.document.return_value.get.return_value = mock_daily_costs
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should highlight budget overrun
        self.assertEqual(result["summary"]["total_cost_usd"], 12.0)
        self.assertGreater(result["summary"]["budget_usage_percent"], 100)
        self.assertIn("issues", result)

        # Should flag as major issue
        issues_text = json.dumps(result["issues"])
        self.assertIn("budget", issues_text.lower())
        self.assertIn("exceeded", issues_text.lower())

        # Slack blocks should show red alert
        slack_text = json.dumps(result["slack_blocks"])
        self.assertIn("🔴", slack_text)  # Red alert
        self.assertIn("240%", slack_text)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_costs_near_budget_threshold(self, mock_config, mock_env, mock_firestore):
        """Test digest when costs approach but don't exceed budget threshold."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 5.0,
            "budgets.alert_threshold": 0.8
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Costs at 85% of budget (above 80% threshold)
        near_threshold_transcripts = []
        for i in range(5):
            near_threshold_transcripts.append(Mock(to_dict=lambda i=i: {
                "video_id": f"video_{i}",
                "status": "completed",
                "costs": {"transcription_usd": 0.85},  # $0.85 each = $4.25 total (85% of $5)
                "created_at": datetime(2025, 9, 15, 10 + i, 0, tzinfo=timezone.utc)
            }))

        mock_daily_costs = Mock()
        mock_daily_costs.exists = True
        mock_daily_costs.to_dict.return_value = {
            "date": self.test_date,
            "transcription_usd": 4.25,
            "budget_usd": 5.0,
            "budget_percentage": 85.0,
            "transaction_count": 5
        }

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = near_threshold_transcripts
            elif collection_name == "costs_daily":
                mock_coll.document.return_value.get.return_value = mock_daily_costs
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should show warning about approaching threshold
        self.assertEqual(result["summary"]["budget_usage_percent"], 85.0)
        slack_text = json.dumps(result["slack_blocks"])
        self.assertIn("⚠️", slack_text)  # Warning emoji
        self.assertIn("85%", slack_text)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_cost_anomaly_single_expensive_video(self, mock_config, mock_env, mock_firestore):
        """Test digest when single video has anomalously high cost."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 5.0
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # One extremely expensive video among normal ones
        mixed_cost_transcripts = [
            Mock(to_dict=lambda: {
                "video_id": "expensive_anomaly",
                "status": "completed",
                "costs": {"transcription_usd": 4.5},  # Very expensive
                "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            }),
            Mock(to_dict=lambda: {
                "video_id": "normal_video_1",
                "status": "completed",
                "costs": {"transcription_usd": 0.2},  # Normal cost
                "created_at": datetime(2025, 9, 15, 11, 0, tzinfo=timezone.utc)
            }),
            Mock(to_dict=lambda: {
                "video_id": "normal_video_2",
                "status": "completed",
                "costs": {"transcription_usd": 0.15},  # Normal cost
                "created_at": datetime(2025, 9, 15, 12, 0, tzinfo=timezone.utc)
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = mixed_cost_transcripts
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should identify cost anomaly
        total_cost = 4.5 + 0.2 + 0.15
        self.assertEqual(result["summary"]["total_cost_usd"], total_cost)

        # Should include issue about high-cost video
        self.assertIn("issues", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_zero_budget_configuration(self, mock_config, mock_env, mock_firestore):
        """Test digest with zero budget configuration."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 0.0  # Zero budget
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Any cost would exceed zero budget
        minimal_transcripts = [Mock(to_dict=lambda: {
            "video_id": "any_video",
            "status": "completed",
            "costs": {"transcription_usd": 0.01},  # Minimal cost
            "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
        })]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = minimal_transcripts
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle zero budget gracefully
        self.assertIn("budget_usage_percent", result["summary"])
        # Any usage should be flagged as over budget
        self.assertGreater(result["summary"]["budget_usage_percent"], 100)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_negative_cost_values_in_data(self, mock_config, mock_env, mock_firestore):
        """Test digest with negative cost values (data corruption)."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 5.0
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Transcripts with negative costs (data corruption)
        corrupted_cost_transcripts = [
            Mock(to_dict=lambda: {
                "video_id": "negative_cost_1",
                "status": "completed",
                "costs": {"transcription_usd": -1.5},  # Negative cost
                "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            }),
            Mock(to_dict=lambda: {
                "video_id": "normal_cost",
                "status": "completed",
                "costs": {"transcription_usd": 2.0},  # Normal cost
                "created_at": datetime(2025, 9, 15, 11, 0, tzinfo=timezone.utc)
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = corrupted_cost_transcripts
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle negative costs gracefully (filter out or normalize)
        self.assertGreaterEqual(result["summary"]["total_cost_usd"], 0)
        self.assertIn("issues", result)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_missing_cost_data_in_transcripts(self, mock_config, mock_env, mock_firestore):
        """Test digest when transcripts are missing cost data."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 5.0
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Transcripts without cost information
        no_cost_transcripts = [
            Mock(to_dict=lambda: {
                "video_id": "no_cost_1",
                "status": "completed",
                # Missing costs field entirely
                "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            }),
            Mock(to_dict=lambda: {
                "video_id": "empty_costs",
                "status": "completed",
                "costs": {},  # Empty costs object
                "created_at": datetime(2025, 9, 15, 11, 0, tzinfo=timezone.utc)
            }),
            Mock(to_dict=lambda: {
                "video_id": "null_cost",
                "status": "completed",
                "costs": {"transcription_usd": None},  # Null cost
                "created_at": datetime(2025, 9, 15, 12, 0, tzinfo=timezone.utc)
            })
        ]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = no_cost_transcripts
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle missing cost data gracefully
        self.assertEqual(result["summary"]["total_cost_usd"], 0.0)
        self.assertEqual(result["summary"]["videos_transcribed"], 3)

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_extremely_high_individual_cost(self, mock_config, mock_env, mock_firestore):
        """Test digest with one video having extremely high cost."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 5.0
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # One video with unreasonably high cost
        extreme_cost_transcripts = [Mock(to_dict=lambda: {
            "video_id": "extreme_cost_video",
            "status": "completed",
            "costs": {"transcription_usd": 1000.0},  # $1000 for one video
            "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
        })]

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = extreme_cost_transcripts
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            mock_coll.document.return_value.get.return_value.exists = False
            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should flag as major cost anomaly
        self.assertEqual(result["summary"]["total_cost_usd"], 1000.0)
        self.assertGreater(result["summary"]["budget_usage_percent"], 1000)
        self.assertIn("issues", result)

        # Should include specific alert about extreme cost
        issues_text = json.dumps(result["issues"])
        self.assertIn("extreme", issues_text.lower())

    @patch('observability_agent.tools.generate_daily_digest.firestore.Client')
    @patch('observability_agent.tools.generate_daily_digest.get_required_env_var')
    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_cost_discrepancy_between_sources(self, mock_config, mock_env, mock_firestore):
        """Test digest when daily costs document doesn't match transcript totals."""
        mock_env.return_value = "test-project-id"
        mock_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": 5.0
        }.get(key, default)

        mock_client = Mock()
        mock_firestore.return_value = mock_client

        # Transcripts total to $3.00
        transcript_costs = [
            Mock(to_dict=lambda: {
                "video_id": "video_1",
                "status": "completed",
                "costs": {"transcription_usd": 1.5},
                "created_at": datetime(2025, 9, 15, 10, 0, tzinfo=timezone.utc)
            }),
            Mock(to_dict=lambda: {
                "video_id": "video_2",
                "status": "completed",
                "costs": {"transcription_usd": 1.5},
                "created_at": datetime(2025, 9, 15, 11, 0, tzinfo=timezone.utc)
            })
        ]

        # But daily costs document shows different total
        mock_daily_costs = Mock()
        mock_daily_costs.exists = True
        mock_daily_costs.to_dict.return_value = {
            "date": self.test_date,
            "transcription_usd": 5.5,  # Doesn't match transcript total
            "budget_usd": 5.0,
            "budget_percentage": 110.0,
            "transaction_count": 2
        }

        def mock_collection(collection_name):
            mock_coll = Mock()
            if collection_name == "transcripts":
                mock_coll.where.return_value.where.return_value.stream.return_value = transcript_costs
            elif collection_name == "costs_daily":
                mock_coll.document.return_value.get.return_value = mock_daily_costs
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
                mock_coll.where.return_value.stream.return_value = []

            return mock_coll

        mock_client.collection.side_effect = mock_collection

        tool = GenerateDailyDigest(date=self.test_date, timezone_name=self.test_timezone)
        result_str = tool.run()
        result = json.loads(result_str)

        # Should use daily costs document as authoritative
        self.assertEqual(result["summary"]["total_cost_usd"], 5.5)
        self.assertIn("issues", result)


if __name__ == "__main__":
    unittest.main()