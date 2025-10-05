"""
Comprehensive test suite for enforce_policies.py targeting 100% coverage.
Missing lines: 64-162, 169-175, 179-199, 206-257, 266-267, 271-275
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone, timedelta

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
from orchestrator_agent.tools.enforce_policies import EnforcePolicies

# Patch EnforcePolicies __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.job_context = kwargs.get('job_context', {})
    self.current_state = kwargs.get('current_state', {})
    self.policy_overrides = kwargs.get('policy_overrides', None)

EnforcePolicies.__init__ = patched_init


class TestEnforcePolicies100Coverage(unittest.TestCase):
    """Test EnforcePolicies to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_job_context = {
            "job_id": "test_job_001",
            "job_type": "single_video",
            "retry_count": 0,
            "error_type": "api_timeout"
        }

        self.valid_current_state = {
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
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_successful_proceed_action(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test successful policy evaluation resulting in proceed action (lines 64-159)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = EnforcePolicies(
            job_context=self.valid_job_context,
            current_state=self.valid_current_state
        )

        result = tool.run()
        data = json.loads(result)

        # Verify proceed action (lines 148-159)
        self.assertEqual(data['action'], 'proceed')
        self.assertEqual(data['reason'], 'All policy constraints satisfied')
        self.assertEqual(data['job_id'], 'test_job_001')
        self.assertIn('policy_checks', data)
        self.assertEqual(data['policy_checks']['retry_policy'], 'passed')
        self.assertEqual(data['policy_checks']['quota_constraints'], 'passed')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_max_retries_exceeded_dlq_action(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test DLQ routing when max retries exceeded (lines 96-105, 179-183)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        job_context = self.valid_job_context.copy()
        job_context['retry_count'] = 3  # Exceeds max

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.valid_current_state
        )

        result = tool.run()
        data = json.loads(result)

        # Verify DLQ action (lines 98-105)
        self.assertEqual(data['action'], 'dlq')
        self.assertIn('Maximum retry attempts exceeded', data['reason'])
        self.assertEqual(data['retry_count'], 3)
        self.assertEqual(data['max_attempts'], 3)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_terminal_error_dlq_action(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test DLQ routing for terminal errors (lines 186-197)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        terminal_errors = ['invalid_video_id', 'video_too_long', 'unsupported_format', 'authorization_failed']

        for error_type in terminal_errors:
            job_context = self.valid_job_context.copy()
            job_context['error_type'] = error_type
            job_context['retry_count'] = 1

            tool = EnforcePolicies(
                job_context=job_context,
                current_state=self.valid_current_state
            )

            result = tool.run()
            data = json.loads(result)

            # Verify DLQ action for terminal errors (lines 193-197)
            self.assertEqual(data['action'], 'dlq')
            self.assertIn(f'Terminal error type: {error_type}', data['reason'])

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    @patch('orchestrator_agent.tools.enforce_policies.get_youtube_daily_limit')
    def test_youtube_quota_throttle(self, mock_youtube_limit, mock_base_delay, mock_max_attempts, mock_config):
        """Test YouTube quota throttling (lines 212-232)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60
        mock_youtube_limit.return_value = 10000

        job_context = self.valid_job_context.copy()
        job_context['job_type'] = 'channel_scrape'

        current_state = self.valid_current_state.copy()
        current_state['quota_usage']['youtube'] = 9500  # 95% utilization

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=current_state
        )

        result = tool.run()
        data = json.loads(result)

        # Verify throttle action (lines 110-117)
        self.assertEqual(data['action'], 'retry_in')
        self.assertIn('YouTube API quota threshold exceeded', data['reason'])
        self.assertIn('delay_sec', data)
        self.assertIn('quota_status', data)
        self.assertEqual(data['quota_status']['used'], 9500)
        self.assertEqual(data['quota_status']['limit'], 10000)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    @patch('orchestrator_agent.tools.enforce_policies.get_assemblyai_daily_limit')
    def test_assemblyai_quota_throttle(self, mock_assemblyai_limit, mock_base_delay, mock_max_attempts, mock_config):
        """Test AssemblyAI quota throttling (lines 235-255)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60
        mock_assemblyai_limit.return_value = 100

        job_context = self.valid_job_context.copy()
        job_context['job_type'] = 'single_video'

        current_state = self.valid_current_state.copy()
        current_state['quota_usage']['assemblyai'] = 95  # 95% utilization

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=current_state
        )

        result = tool.run()
        data = json.loads(result)

        # Verify throttle action (lines 246-255)
        self.assertEqual(data['action'], 'retry_in')
        self.assertIn('AssemblyAI quota threshold exceeded', data['reason'])
        self.assertIn('delay_sec', data)
        self.assertIn('quota_status', data)
        self.assertEqual(data['quota_status']['used'], 95)
        self.assertEqual(data['quota_status']['limit'], 100)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_backoff_delay_calculation(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test exponential backoff delay calculation (lines 120-134, 262-267)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 5
        mock_base_delay.return_value = 60

        # Test with recent attempt that hasn't satisfied backoff
        recent_time = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()

        job_context = self.valid_job_context.copy()
        job_context['retry_count'] = 2
        job_context['last_attempt_at'] = recent_time

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.valid_current_state
        )

        result = tool.run()
        data = json.loads(result)

        # Verify backoff delay (lines 128-134)
        self.assertEqual(data['action'], 'retry_in')
        self.assertIn('Backoff delay not yet satisfied', data['reason'])
        self.assertIn('delay_sec', data)
        self.assertEqual(data['backoff_strategy'], 'exponential')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_backoff_delay_edge_cases(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test backoff delay calculation edge cases (lines 266-267)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 10
        mock_base_delay.return_value = 60

        tool = EnforcePolicies(
            job_context=self.valid_job_context,
            current_state=self.valid_current_state
        )

        # Test capping at 24 hours (line 267)
        delay_high = tool._calculate_backoff_delay(20, 60)  # Would be huge
        self.assertEqual(delay_high, 86400)  # Capped at 24 hours

        # Test normal exponential growth
        delay_1 = tool._calculate_backoff_delay(1, 60)
        self.assertEqual(delay_1, 120)  # 60 * 2^1

        delay_2 = tool._calculate_backoff_delay(2, 60)
        self.assertEqual(delay_2, 240)  # 60 * 2^2

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_last_attempt_parsing(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test last_attempt_at timestamp parsing (lines 79-84)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        # Test valid ISO format with Z
        job_context = self.valid_job_context.copy()
        job_context['last_attempt_at'] = '2025-01-27T12:00:00Z'
        job_context['retry_count'] = 0

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.valid_current_state
        )

        result = tool.run()
        data = json.loads(result)
        self.assertEqual(data['action'], 'proceed')

        # Test invalid format fallback (lines 83-84)
        job_context['last_attempt_at'] = 'invalid-timestamp'
        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.valid_current_state
        )

        result = tool.run()
        data = json.loads(result)
        # Should still proceed with fallback timestamp
        self.assertEqual(data['action'], 'proceed')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_policy_overrides(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test policy overrides (lines 87-93)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        # Test with policy overrides
        policy_overrides = {
            'max_attempts': 10,
            'base_delay_sec': 120,
            'quota_threshold': 0.95
        }

        job_context = self.valid_job_context.copy()
        job_context['retry_count'] = 5  # Would exceed default, but not override

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.valid_current_state,
            policy_overrides=policy_overrides
        )

        result = tool.run()
        data = json.loads(result)

        # Should proceed because override allows 10 attempts
        self.assertEqual(data['action'], 'proceed')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_checkpoint_constraints(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test checkpoint constraint evaluation (lines 137-145, 269-279)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        current_state = self.valid_current_state.copy()
        current_state['checkpoint_data'] = {
            'lastPublishedAt': '2025-01-27T00:00:00Z'
        }

        tool = EnforcePolicies(
            job_context=self.valid_job_context,
            current_state=current_state
        )

        result = tool.run()
        data = json.loads(result)

        # Currently checkpoints always pass (lines 275-278)
        self.assertEqual(data['action'], 'proceed')
        self.assertIn('policy_checks', data)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_checkpoint_skip_scenario(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test checkpoint constraint returning skip action (lines 139-145)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60

        tool = EnforcePolicies(
            job_context=self.valid_job_context,
            current_state=self.valid_current_state
        )

        # Mock _evaluate_checkpoint_constraints to return skip
        with patch.object(tool, '_evaluate_checkpoint_constraints', return_value={
            'action': 'skip',
            'reason': 'Checkpoint window closed',
            'checkpoint_status': {'window': 'closed'}
        }):
            result = tool.run()
            data = json.loads(result)

            # Verify skip action (lines 140-145)
            self.assertEqual(data['action'], 'skip')
            self.assertEqual(data['reason'], 'Checkpoint window closed')
            self.assertIn('checkpoint_status', data)
            self.assertEqual(data['checkpoint_status']['window'], 'closed')

    def test_input_validation_missing_fields(self):
        """Test input validation for missing required fields (lines 169-175)."""
        # Missing job_id
        invalid_context = {
            "job_type": "single_video"
        }

        with self.assertRaises(ValueError) as context:
            tool = EnforcePolicies(
                job_context=invalid_context,
                current_state=self.valid_current_state
            )
            tool._validate_inputs()

        self.assertIn('Missing required job_context field: job_id', str(context.exception))

        # Missing job_type
        invalid_context = {
            "job_id": "test_001"
        }

        with self.assertRaises(ValueError) as context:
            tool = EnforcePolicies(
                job_context=invalid_context,
                current_state=self.valid_current_state
            )
            tool._validate_inputs()

        self.assertIn('Missing required job_context field: job_type', str(context.exception))

        # Invalid current_state type
        with self.assertRaises(ValueError) as context:
            tool = EnforcePolicies(
                job_context=self.valid_job_context,
                current_state="not a dict"
            )
            tool._validate_inputs()

        self.assertIn('current_state must be a dictionary', str(context.exception))

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_run_exception_handling(self, mock_config):
        """Test exception handling in run method (lines 161-165)."""
        mock_config.side_effect = Exception("Config load failed")

        tool = EnforcePolicies(
            job_context=self.valid_job_context,
            current_state=self.valid_current_state
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error response (lines 162-165)
        self.assertIn('error', data)
        self.assertEqual(data['action'], 'error')
        self.assertIn('Policy enforcement failed', data['error'])

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    def test_retry_policy_returns_retry(self, mock_base_delay, mock_max_attempts, mock_config):
        """Test retry policy returns retry action (lines 199-202)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 5
        mock_base_delay.return_value = 60

        tool = EnforcePolicies(
            job_context=self.valid_job_context,
            current_state=self.valid_current_state
        )

        # Test _evaluate_retry_policy directly
        decision = tool._evaluate_retry_policy(1, 5, 'network_error')

        self.assertEqual(decision['action'], 'retry')
        self.assertEqual(decision['reason'], 'Retry policy allows continuation')

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_max_attempts')
    @patch('orchestrator_agent.tools.enforce_policies.get_retry_base_delay')
    @patch('orchestrator_agent.tools.enforce_policies.get_youtube_daily_limit')
    def test_quota_constraints_proceed(self, mock_youtube_limit, mock_base_delay, mock_max_attempts, mock_config):
        """Test quota constraints returning proceed (lines 257-260)."""
        mock_config.return_value = {}
        mock_max_attempts.return_value = 3
        mock_base_delay.return_value = 60
        mock_youtube_limit.return_value = 10000

        job_context = self.valid_job_context.copy()
        job_context['job_type'] = 'channel_scrape'

        tool = EnforcePolicies(
            job_context=job_context,
            current_state=self.valid_current_state
        )

        # Test _evaluate_quota_constraints directly
        decision = tool._evaluate_quota_constraints('channel_scrape', {})

        self.assertEqual(decision['action'], 'proceed')
        self.assertEqual(decision['reason'], 'Quota constraints satisfied')


if __name__ == '__main__':
    unittest.main()