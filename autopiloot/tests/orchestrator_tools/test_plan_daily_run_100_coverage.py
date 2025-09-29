"""
Comprehensive test suite for PlanDailyRun tool targeting 100% coverage.
Tests daily planning, configuration loading, quota calculations, and warnings.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import sys
import os
from datetime import datetime, timezone


# Mock external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'dotenv': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Import the tool after mocking
from orchestrator_agent.tools.plan_daily_run import PlanDailyRun

# Patch PlanDailyRun __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.target_channels = kwargs.get('target_channels', None)
    self.max_videos_per_channel = kwargs.get('max_videos_per_channel', None)

PlanDailyRun.__init__ = patched_init


class TestPlanDailyRun100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for PlanDailyRun."""

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_successful_plan_generation_defaults(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test successful plan generation with default configuration (lines 60-138)."""
        mock_config.return_value = {
            "scraper": {
                "handles": ["@AlexHormozi", "@TestChannel"],
                "daily_limit_per_channel": 10
            },
            "budgets": {
                "transcription_daily_usd": 5.0
            }
        }
        mock_youtube.return_value = 10000
        mock_assemblyai.return_value = 50
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        self.assertIn("plan_generated_at", data)
        self.assertEqual(len(data["channels"]), 2)
        self.assertEqual(data["per_channel_limit"], 10)
        self.assertEqual(data["total_videos_planned"], 20)
        self.assertEqual(data["operational_status"], "planned")
        self.assertEqual(data["retry_policy"]["max_attempts"], 3)
        self.assertEqual(data["retry_policy"]["base_delay_sec"], 60)

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_plan_generation_with_overrides(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test plan generation with channel and limit overrides (lines 65, 68)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@Default"], "daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }
        mock_youtube.return_value = 10000
        mock_assemblyai.return_value = 50
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun(
            target_channels=["@CustomChannel1", "@CustomChannel2"],
            max_videos_per_channel=5
        )
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["channels"], ["@CustomChannel1", "@CustomChannel2"])
        self.assertEqual(data["per_channel_limit"], 5)
        self.assertEqual(data["total_videos_planned"], 10)

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_operational_windows(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test operational windows generation (lines 85-89)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@Test"], "daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }
        mock_youtube.return_value = 10000
        mock_assemblyai.return_value = 50
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(len(data["windows"]), 3)
        self.assertIn("scraping_window", data["windows"][0])
        self.assertIn("transcription_window", data["windows"][1])
        self.assertIn("summarization_window", data["windows"][2])

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_checkpoint_structure(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test checkpoint structure generation (lines 92-101)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@Test"], "daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }
        mock_youtube.return_value = 10000
        mock_assemblyai.return_value = 50
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        checkpoints = data["checkpoints"]
        self.assertIn("last_scrape_completed", checkpoints)
        self.assertIn("last_published_at", checkpoints)
        self.assertIn("pending_transcriptions", checkpoints)
        self.assertIn("daily_quota_used", checkpoints)
        self.assertEqual(checkpoints["daily_quota_used"]["youtube_api_units"], 0)

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_resource_calculations(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test resource requirement calculations (lines 104-105)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@Channel1", "@Channel2"], "daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }
        mock_youtube.return_value = 10000
        mock_assemblyai.return_value = 50
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["total_videos_planned"], 20)
        self.assertEqual(data["resource_limits"]["estimated_quota_usage"], 2000)

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_quota_warning_generation(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test warning generation for approaching quota limit (lines 109-110)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@C1", "@C2", "@C3", "@C4", "@C5"], "daily_limit_per_channel": 20},
            "budgets": {"transcription_daily_usd": 5.0}
        }
        mock_youtube.return_value = 10000  # Total planned: 5 * 20 = 100 videos = 10000 units (100% of quota, > 80%)
        mock_assemblyai.return_value = 200
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        self.assertTrue(len(data["warnings"]) > 0)
        self.assertIn("Estimated quota usage", data["warnings"][0])
        self.assertIn("approaching YouTube daily limit", data["warnings"][0])

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_assemblyai_limit_warning(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test warning generation for exceeding AssemblyAI limit (lines 112-113)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@C1", "@C2", "@C3", "@C4", "@C5"], "daily_limit_per_channel": 15},
            "budgets": {"transcription_daily_usd": 5.0}
        }
        mock_youtube.return_value = 10000
        mock_assemblyai.return_value = 50  # Total planned: 5 * 15 = 75 > 50
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        warning_found = False
        for warning in data["warnings"]:
            if "exceed AssemblyAI daily limit" in warning:
                warning_found = True
                break
        self.assertTrue(warning_found)

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_resource_limits_structure(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test resource_limits structure (lines 123-128)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@Test"], "daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 8.5}
        }
        mock_youtube.return_value = 15000
        mock_assemblyai.return_value = 75
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        resource_limits = data["resource_limits"]
        self.assertEqual(resource_limits["youtube_daily_quota"], 15000)
        self.assertEqual(resource_limits["assemblyai_daily_limit"], 75)
        self.assertEqual(resource_limits["transcription_budget_usd"], 8.5)

    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_base_delay')
    @patch('orchestrator_agent.tools.plan_daily_run.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_retry_policy_structure(self, mock_config, mock_youtube, mock_assemblyai, mock_max_attempts, mock_base_delay):
        """Test retry_policy structure (lines 129-133)."""
        mock_config.return_value = {
            "scraper": {"handles": ["@Test"], "daily_limit_per_channel": 10},
            "budgets": {"transcription_daily_usd": 5.0}
        }
        mock_youtube.return_value = 10000
        mock_assemblyai.return_value = 50
        mock_max_attempts.return_value = 5
        mock_base_delay.return_value = 120

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        retry_policy = data["retry_policy"]
        self.assertEqual(retry_policy["max_attempts"], 5)
        self.assertEqual(retry_policy["base_delay_sec"], 120)
        self.assertEqual(retry_policy["backoff_strategy"], "exponential")

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_exception_handling(self, mock_config):
        """Test exception handling in run method (lines 140-144)."""
        mock_config.side_effect = Exception("Config loading failed")

        tool = PlanDailyRun()
        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertIn("Failed to generate daily plan", data["error"])
        self.assertIsNone(data["plan"])


if __name__ == "__main__":
    unittest.main()