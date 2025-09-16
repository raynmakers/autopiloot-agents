"""
Tests for orchestrator_agent.tools.enforce_policies module.

This module tests the EnforcePolicies tool which evaluates job context against
reliability policies and returns actionable decisions for retries, backoff, and DLQ routing.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

# Add the parent directories to sys.path for imports
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from orchestrator_agent.tools.enforce_policies import EnforcePolicies


class TestEnforcePolicies(unittest.TestCase):
    """Test cases for EnforcePolicies orchestrator tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Base job context for testing
        self.base_job_context = {
            "job_id": "test_job_123",
            "job_type": "single_video",
            "retry_count": 1,
            "last_attempt_at": "2025-01-27T12:00:00Z",
            "error_type": "api_timeout"
        }

        # Base current state for testing
        self.base_current_state = {
            "quota_usage": {
                "youtube": 5000,
                "assemblyai": 25
            },
            "daily_costs": {
                "transcription_usd": 2.50
            },
            "checkpoint_data": {}
        }

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_successful_policy_enforcement_proceed(self, mock_load_config):
        """Test successful policy evaluation that allows proceeding."""
        # Setup mock config
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            },
            'quotas': {
                'youtube_daily_limit': 10000,
                'assemblyai_daily_limit_usd': 5.0
            }
        }
        mock_load_config.return_value = mock_config

        # Create tool with normal retry scenario
        tool = EnforcePolicies(
            job_context=self.base_job_context,
            current_state=self.base_current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful proceed decision
        self.assertEqual(result_data['action'], 'proceed')
        self.assertEqual(result_data['job_id'], 'test_job_123')
        self.assertIn('policy_checks', result_data)
        self.assertEqual(result_data['policy_checks']['retry_policy'], 'passed')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_retry_limit_exceeded_dlq(self, mock_load_config):
        """Test that jobs exceeding retry limits are sent to DLQ."""
        # Setup mock config
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        # Job with retry count exceeding limit
        job_context = self.base_job_context.copy()
        job_context['retry_count'] = 4

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.base_current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert DLQ decision
        self.assertEqual(result_data['action'], 'dlq')
        self.assertIn('Maximum retry attempts exceeded', result_data['reason'])
        self.assertEqual(result_data['retry_count'], 4)
        self.assertEqual(result_data['max_attempts'], 3)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_terminal_error_dlq(self, mock_load_config):
        """Test that terminal errors are immediately sent to DLQ."""
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        # Job with terminal error
        job_context = self.base_job_context.copy()
        job_context['error_type'] = 'authorization_failed'
        job_context['retry_count'] = 0

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.base_current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert DLQ decision for terminal error
        self.assertEqual(result_data['action'], 'dlq')
        self.assertIn('Terminal error type', result_data['reason'])
        self.assertIn('authorization_failed', result_data['reason'])

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_youtube_quota_threshold_exceeded(self, mock_load_config):
        """Test throttling when YouTube quota threshold is exceeded."""
        mock_config = {
            'quotas': {
                'youtube_daily_limit': 10000
            },
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        # High YouTube quota usage
        current_state = self.base_current_state.copy()
        current_state['quota_usage']['youtube'] = 9500  # 95% of 10k limit

        job_context = self.base_job_context.copy()
        job_context['job_type'] = 'channel_scrape'

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert throttle decision
        self.assertEqual(result_data['action'], 'retry_in')
        self.assertIn('YouTube API quota threshold exceeded', result_data['reason'])
        self.assertIn('quota_status', result_data)
        self.assertGreater(result_data['delay_sec'], 0)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_assemblyai_quota_threshold_exceeded(self, mock_load_config):
        """Test throttling when AssemblyAI quota threshold is exceeded."""
        mock_config = {
            'quotas': {
                'assemblyai_daily_limit_usd': 5.0
            },
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        # High AssemblyAI quota usage
        current_state = self.base_current_state.copy()
        current_state['quota_usage']['assemblyai'] = 4.7  # 94% of $5 limit

        job_context = self.base_job_context.copy()
        job_context['job_type'] = 'single_video'

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert throttle decision
        self.assertEqual(result_data['action'], 'retry_in')
        self.assertIn('AssemblyAI quota threshold exceeded', result_data['reason'])
        self.assertIn('quota_status', result_data)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_backoff_delay_not_satisfied(self, mock_load_config):
        """Test that jobs are delayed when backoff time hasn't elapsed."""
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        # Recent last attempt (30 seconds ago)
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)

        job_context = self.base_job_context.copy()
        job_context['retry_count'] = 2
        job_context['last_attempt_at'] = recent_time.isoformat().replace('+00:00', 'Z')

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.base_current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert retry delay decision
        self.assertEqual(result_data['action'], 'retry_in')
        self.assertIn('Backoff delay not yet satisfied', result_data['reason'])
        self.assertGreater(result_data['delay_sec'], 0)
        self.assertEqual(result_data['backoff_strategy'], 'exponential')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_policy_overrides(self, mock_load_config):
        """Test that policy overrides are respected."""
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        # Override with higher max attempts
        policy_overrides = {
            'max_attempts': 5,
            'base_delay_sec': 120,
            'quota_threshold': 0.95
        }

        job_context = self.base_job_context.copy()
        job_context['retry_count'] = 4  # Would exceed default, but not override

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.base_current_state,
            policy_overrides=policy_overrides
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should proceed since override allows 5 attempts
        self.assertEqual(result_data['action'], 'proceed')

    def test_missing_required_job_context_fields(self):
        """Test validation when required job context fields are missing."""
        # Missing job_id
        invalid_context = {
            "job_type": "single_video",
            "retry_count": 1
        }

        tool = EnforcePolicies(
            job_context=invalid_context,
            current_state=self.base_current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['action'], 'error')
        self.assertIn('error', result_data)

    def test_invalid_current_state(self):
        """Test validation when current_state is invalid."""
        tool = EnforcePolicies(
            job_context=self.base_job_context,
            current_state="invalid_state"  # Should be dict
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['action'], 'error')
        self.assertIn('error', result_data)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_exponential_backoff_calculation(self, mock_load_config):
        """Test that exponential backoff is calculated correctly."""
        mock_config = {
            'policies': {
                'retry_max_attempts': 5,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        tool = EnforcePolicies(
            job_context=self.base_job_context,
            current_state=self.base_current_state
        )

        # Test backoff calculation directly
        delay_1 = tool._calculate_backoff_delay(1, 60)  # 60 * 2^1 = 120
        delay_2 = tool._calculate_backoff_delay(2, 60)  # 60 * 2^2 = 240
        delay_3 = tool._calculate_backoff_delay(3, 60)  # 60 * 2^3 = 480

        self.assertEqual(delay_1, 120)
        self.assertEqual(delay_2, 240)
        self.assertEqual(delay_3, 480)

        # Test cap at 24 hours
        delay_large = tool._calculate_backoff_delay(20, 60)
        self.assertEqual(delay_large, 86400)  # 24 hours max

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_all_terminal_error_types(self, mock_load_config):
        """Test all terminal error types result in DLQ."""
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        terminal_errors = [
            "invalid_video_id",
            "video_too_long",
            "unsupported_format",
            "authorization_failed"
        ]

        for error_type in terminal_errors:
            with self.subTest(error_type=error_type):
                job_context = self.base_job_context.copy()
                job_context['error_type'] = error_type
                job_context['retry_count'] = 0

                tool = EnforcePolicies(
                    job_context=job_context,
                    current_state=self.base_current_state
                )

                result = tool.run()
                result_data = json.loads(result)

                self.assertEqual(result_data['action'], 'dlq')
                self.assertIn('Terminal error type', result_data['reason'])

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = EnforcePolicies(
            job_context=self.base_job_context,
            current_state=self.base_current_state
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, EnforcePolicies)

        # Test required parameters
        self.assertIsInstance(tool.job_context, dict)
        self.assertIsInstance(tool.current_state, dict)
        self.assertIn('job_id', tool.job_context)
        self.assertIn('job_type', tool.job_context)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_empty_current_state_handling(self, mock_load_config):
        """Test handling of empty current state."""
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            },
            'quotas': {
                'youtube_daily_limit': 10000,
                'assemblyai_daily_limit_usd': 5.0
            }
        }
        mock_load_config.return_value = mock_config

        # Empty current state
        empty_state = {}

        tool = EnforcePolicies(
            job_context=self.base_job_context,
            current_state=empty_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should still work with empty state (no quotas to check)
        self.assertEqual(result_data['action'], 'proceed')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_invalid_timestamp_handling(self, mock_load_config):
        """Test handling of invalid last_attempt_at timestamp."""
        mock_config = {
            'policies': {
                'retry_max_attempts': 3,
                'retry_base_delay_sec': 60
            }
        }
        mock_load_config.return_value = mock_config

        job_context = self.base_job_context.copy()
        job_context['last_attempt_at'] = 'invalid-timestamp'
        job_context['retry_count'] = 1

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.base_current_state
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should handle invalid timestamp gracefully
        self.assertIn(result_data['action'], ['proceed', 'retry_in'])


if __name__ == '__main__':
    unittest.main()