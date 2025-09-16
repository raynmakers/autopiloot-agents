"""
Tests for orchestrator_agent.tools.plan_daily_run module.

This module tests the PlanDailyRun tool which computes actionable plans
for daily content processing runs with quota-aware planning.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock, mock_open

# Add the parent directories to sys.path for imports
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from orchestrator_agent.tools.plan_daily_run import PlanDailyRun


class TestPlanDailyRun(unittest.TestCase):
    """Test cases for PlanDailyRun orchestrator tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool = PlanDailyRun()

        # Mock configuration data
        self.mock_config = {
            'scraper': {
                'handles': ['@AlexHormozi'],
                'daily_limit_per_channel': 10
            },
            'budgets': {
                'transcription_daily_usd': 5.0
            },
            'reliability': {
                'quotas': {
                    'youtube_daily_limit': 10000,
                    'assemblyai_daily_limit': 100
                },
                'retry': {
                    'base_delay_sec': 60,
                    'max_attempts': 3
                }
            }
        }

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_successful_planning_default_config(self, mock_load_config):
        """Test successful daily run planning with default configuration."""
        mock_load_config.return_value = self.mock_config

        result = self.tool.run()

        # Parse JSON result
        result_data = json.loads(result)

        # Assert result structure
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('daily_plan', result_data)
        self.assertIn('channels', result_data['daily_plan'])
        self.assertIn('quotas', result_data['daily_plan'])
        self.assertIn('budget', result_data['daily_plan'])
        self.assertIn('checkpoint', result_data['daily_plan'])

        # Assert channel planning
        channels = result_data['daily_plan']['channels']
        self.assertGreater(len(channels), 0)
        self.assertIn('@AlexHormozi', [ch['handle'] for ch in channels])

        # Assert quota information
        quotas = result_data['daily_plan']['quotas']
        self.assertEqual(quotas['youtube_daily_limit'], 10000)
        self.assertEqual(quotas['assemblyai_daily_limit'], 100)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_planning_with_overrides(self, mock_load_config):
        """Test daily run planning with parameter overrides."""
        mock_load_config.return_value = self.mock_config

        # Set override parameters
        self.tool.target_channels = ['@TestChannel']
        self.tool.max_videos_per_channel = 5

        result = self.tool.run()
        result_data = json.loads(result)

        # Assert overrides are applied
        self.assertEqual(result_data['status'], 'success')
        channels = result_data['daily_plan']['channels']
        self.assertIn('@TestChannel', [ch['handle'] for ch in channels])

        # Find the channel and check limit
        test_channel = next(ch for ch in channels if ch['handle'] == '@TestChannel')
        self.assertEqual(test_channel['daily_limit'], 5)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_planning_with_empty_channels(self, mock_load_config):
        """Test planning behavior with empty channel configuration."""
        empty_config = self.mock_config.copy()
        empty_config['scraper']['handles'] = []
        mock_load_config.return_value = empty_config

        result = self.tool.run()
        result_data = json.loads(result)

        # Should still succeed but with empty channel list
        self.assertEqual(result_data['status'], 'success')
        channels = result_data['daily_plan']['channels']
        self.assertEqual(len(channels), 0)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_planning_configuration_error(self, mock_load_config):
        """Test planning behavior when configuration loading fails."""
        mock_load_config.side_effect = Exception("Configuration load failed")

        result = self.tool.run()
        result_data = json.loads(result)

        # Should return error status
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)
        self.assertIn('Configuration load failed', result_data['error'])

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_planning_with_invalid_override_values(self, mock_load_config):
        """Test planning with invalid override values."""
        mock_load_config.return_value = self.mock_config

        # Set invalid override (should be handled by pydantic validation)
        with self.assertRaises(ValueError):
            invalid_tool = PlanDailyRun(max_videos_per_channel=-1)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    @patch('orchestrator_agent.tools.plan_daily_run.get_youtube_daily_limit')
    @patch('orchestrator_agent.tools.plan_daily_run.get_assemblyai_daily_limit')
    def test_quota_integration(self, mock_assemblyai_quota, mock_youtube_quota, mock_load_config):
        """Test integration with quota management functions."""
        mock_load_config.return_value = self.mock_config
        mock_youtube_quota.return_value = 8000  # Reduced quota
        mock_assemblyai_quota.return_value = 75   # Reduced quota

        result = self.tool.run()
        result_data = json.loads(result)

        # Assert quota values are properly retrieved
        quotas = result_data['daily_plan']['quotas']
        self.assertEqual(quotas['youtube_daily_limit'], 8000)
        self.assertEqual(quotas['assemblyai_daily_limit'], 75)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_planning_result_structure(self, mock_load_config):
        """Test that the planning result has the expected structure."""
        mock_load_config.return_value = self.mock_config

        result = self.tool.run()
        result_data = json.loads(result)

        # Validate required top-level fields
        required_fields = ['status', 'daily_plan', 'timestamp']
        for field in required_fields:
            self.assertIn(field, result_data)

        # Validate daily_plan structure
        plan = result_data['daily_plan']
        plan_required_fields = ['channels', 'quotas', 'budget', 'checkpoint']
        for field in plan_required_fields:
            self.assertIn(field, plan)

        # Validate budget structure
        budget = plan['budget']
        self.assertIn('transcription_daily_usd', budget)
        self.assertEqual(budget['transcription_daily_usd'], 5.0)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_planning_multiple_channels(self, mock_load_config):
        """Test planning with multiple channels configured."""
        multi_channel_config = self.mock_config.copy()
        multi_channel_config['scraper']['handles'] = ['@AlexHormozi', '@Channel2', '@Channel3']
        mock_load_config.return_value = multi_channel_config

        result = self.tool.run()
        result_data = json.loads(result)

        # Should plan for all channels
        channels = result_data['daily_plan']['channels']
        self.assertEqual(len(channels), 3)

        channel_handles = [ch['handle'] for ch in channels]
        self.assertIn('@AlexHormozi', channel_handles)
        self.assertIn('@Channel2', channel_handles)
        self.assertIn('@Channel3', channel_handles)

    @patch('orchestrator_agent.tools.plan_daily_run.load_app_config')
    def test_checkpoint_information(self, mock_load_config):
        """Test that checkpoint information is included in the plan."""
        mock_load_config.return_value = self.mock_config

        result = self.tool.run()
        result_data = json.loads(result)

        # Assert checkpoint section exists
        checkpoint = result_data['daily_plan']['checkpoint']
        self.assertIsInstance(checkpoint, dict)

        # Should contain resumption info
        expected_checkpoint_fields = ['resumption_enabled', 'last_processed_timestamps']
        for field in expected_checkpoint_fields:
            self.assertIn(field, checkpoint)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        # Test that it's a BaseTool
        self.assertIsInstance(self.tool, PlanDailyRun)

        # Test optional parameters have correct defaults
        self.assertIsNone(self.tool.target_channels)
        self.assertIsNone(self.tool.max_videos_per_channel)


if __name__ == '__main__':
    unittest.main()