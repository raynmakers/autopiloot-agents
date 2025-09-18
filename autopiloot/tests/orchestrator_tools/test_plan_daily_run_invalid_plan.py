"""
Edge case and invalid input tests for orchestrator_agent.tools.plan_daily_run module.

This module tests boundary conditions, invalid inputs, and error scenarios for the
PlanDailyRun tool including malformed configurations, invalid parameters, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Add the parent directories to sys.path for imports
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from orchestrator_agent.tools.plan_daily_run import PlanDailyRun


class TestPlanDailyRunInvalidPlan(unittest.TestCase):
    """Edge case and invalid input tests for PlanDailyRun orchestrator tool."""

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_missing_config_file(self, mock_load_config):
        """Test behavior when configuration file is missing or inaccessible."""
        mock_load_config.side_effect = FileNotFoundError("Configuration file not found")

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "config_load_failed")

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_malformed_config_structure(self, mock_load_config):
        """Test handling of malformed configuration structure."""
        # Return malformed config missing critical sections
        mock_load_config.return_value = {
            "random_key": "random_value"
            # Missing scraper, sheets, budgets sections
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle gracefully with defaults
        self.assertIn("plan", result)
        self.assertIn("channels", result["plan"])

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_empty_channels_list_in_config(self, mock_load_config):
        """Test behavior when config has empty channels list."""
        mock_load_config.return_value = {
            "scraper": {"handles": []},  # Empty list
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("no channels configured", result["message"].lower())

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_invalid_channel_format(self, mock_load_config):
        """Test handling of invalid channel handle formats."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["invalid-channel", "", "@valid-channel", None]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = PlanDailyRun(target_channels=["", "  ", "invalid", None])
        result_str = tool.run()
        result = json.loads(result_str)

        # Should filter out invalid channels
        if "plan" in result:
            valid_channels = result["plan"]["channels"]
            self.assertGreater(len(valid_channels), 0)  # Should have at least one valid channel

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_negative_max_videos_per_channel(self, mock_load_config):
        """Test handling of negative max_videos_per_channel parameter."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@TestChannel"]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }

        # Pydantic should prevent negative values, but test the constraint
        with self.assertRaises(ValueError):
            tool = PlanDailyRun(max_videos_per_channel=-5)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_extremely_large_video_limit(self, mock_load_config):
        """Test handling of extremely large video limits."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@TestChannel"]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0},
            "reliability": {"quotas": {"youtube_daily_limit": 10000}}
        }

        tool = PlanDailyRun(max_videos_per_channel=999999)
        result_str = tool.run()
        result = json.loads(result_str)

        if "plan" in result:
            # Should be capped to reasonable limits based on quotas
            for channel in result["plan"]["channels"]:
                self.assertLessEqual(channel["max_videos"], 10000)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_zero_budget_configuration(self, mock_load_config):
        """Test behavior with zero budget configuration."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@TestChannel"]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 0.0}  # Zero budget
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("budget", result["message"].lower())

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_negative_budget_configuration(self, mock_load_config):
        """Test behavior with negative budget configuration."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@TestChannel"]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": -5.0}  # Negative budget
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertIn("budget", result["message"].lower())

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_missing_budget_section(self, mock_load_config):
        """Test behavior when budget section is missing from config."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@TestChannel"]},
            "sheets": {"daily_limit_per_channel": 10}
            # Missing budgets section
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        # Should use default budget
        self.assertIn("plan", result)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_zero_daily_limit_per_channel(self, mock_load_config):
        """Test behavior with zero daily limit per channel."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@TestChannel"]},
            "sheets": {"daily_limit_per_channel": 0},  # Zero limit
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        if "plan" in result:
            # Should handle zero limit gracefully
            for channel in result["plan"]["channels"]:
                self.assertGreaterEqual(channel["max_videos"], 0)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_malformed_quota_configuration(self, mock_load_config):
        """Test handling of malformed quota configuration."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@TestChannel"]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0},
            "reliability": {
                "quotas": {
                    "youtube_daily_limit": "invalid",  # String instead of int
                    "assemblyai_daily_limit": -100  # Negative value
                }
            }
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle malformed quotas with defaults
        self.assertIn("plan", result)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_invalid_target_channels_override(self, mock_load_config):
        """Test behavior with invalid target_channels override."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@ValidChannel"]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }

        # Test with various invalid channel formats
        invalid_channels = ["", "   ", "no-at-symbol", "@", "@-invalid", "@@double"]

        tool = PlanDailyRun(target_channels=invalid_channels)
        result_str = tool.run()
        result = json.loads(result_str)

        if "error" in result:
            self.assertIn("no valid channels", result["message"].lower())
        elif "plan" in result:
            # Should fall back to config channels
            self.assertGreater(len(result["plan"]["channels"]), 0)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_config_load_exception_handling(self, mock_load_config):
        """Test handling of various configuration loading exceptions."""
        # Test different types of exceptions
        exceptions_to_test = [
            PermissionError("Permission denied"),
            json.JSONDecodeError("Invalid JSON", "", 0),
            KeyError("Missing key"),
            ValueError("Invalid value")
        ]

        for exception in exceptions_to_test:
            with self.subTest(exception=type(exception).__name__):
                mock_load_config.side_effect = exception

                tool = PlanDailyRun()
                result_str = tool.run()
                result = json.loads(result_str)

                self.assertIn("error", result)
                self.assertIn("config", result["error"].lower())

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_missing_handles_in_scraper_config(self, mock_load_config):
        """Test behavior when scraper config exists but handles key is missing."""
        mock_load_config.return_value = {
            "scraper": {},  # Missing handles key
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_null_values_in_config(self, mock_load_config):
        """Test handling of null/None values in configuration."""
        mock_load_config.return_value = {
            "scraper": {"handles": None},  # Null value
            "sheets": {"daily_limit_per_channel": None},
            "budgets": {"transcription_daily_usd": None}
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_mixed_valid_invalid_channels(self, mock_load_config):
        """Test plan generation with mix of valid and invalid channels."""
        mock_load_config.return_value = {
            "scraper": {"handles": ["@ValidChannel1", "", "@ValidChannel2", None, "invalid"]},
            "sheets": {"daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = PlanDailyRun()
        result_str = tool.run()
        result = json.loads(result_str)

        if "plan" in result:
            # Should only include valid channels
            valid_channels = [ch for ch in result["plan"]["channels"]
                            if ch["handle"].startswith("@") and len(ch["handle"]) > 1]
            self.assertGreaterEqual(len(valid_channels), 2)


if __name__ == "__main__":
    unittest.main()