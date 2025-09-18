"""
Edge case and boundary tests for orchestrator_agent.tools.enforce_policies module.

This module tests boundary conditions, negative paths, and edge cases for the
EnforcePolicies tool including invalid inputs, extreme values, and edge scenarios.
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


class TestEnforcePoliciesBoundaries(unittest.TestCase):
    """Edge case and boundary tests for EnforcePolicies orchestrator tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Minimal valid job context
        self.minimal_job_context = {
            "job_id": "test_job_123",
            "job_type": "single_video",
            "retry_count": 0,
            "last_attempt_at": "2025-01-27T12:00:00Z",
            "error_type": "api_timeout"
        }

        # Minimal valid current state
        self.minimal_current_state = {
            "quota_usage": {"youtube": 0, "assemblyai": 0},
            "daily_costs": {"transcription_usd": 0.0},
            "checkpoint_data": {}
        }

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_empty_job_context_error(self, mock_load_config):
        """Test that empty job context raises appropriate error."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        tool = EnforcePolicies(
            job_context={},  # Empty context
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "invalid_job_context")
        self.assertIn("missing required fields", result["message"])

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_missing_required_fields_in_job_context(self, mock_load_config):
        """Test job context missing critical fields."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        # Missing job_id and job_type
        incomplete_job_context = {
            "retry_count": 1,
            "last_attempt_at": "2025-01-27T12:00:00Z",
            "error_type": "api_timeout"
        }

        tool = EnforcePolicies(
            job_context=incomplete_job_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "invalid_job_context")

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_extreme_retry_count_boundary(self, mock_load_config):
        """Test behavior with extremely high retry counts."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        # Retry count far exceeding max attempts
        extreme_job_context = self.minimal_job_context.copy()
        extreme_job_context["retry_count"] = 999

        tool = EnforcePolicies(
            job_context=extreme_job_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["decision"], "dead_letter_queue")
        self.assertIn("max retry attempts exceeded", result["reason"])

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_negative_retry_count(self, mock_load_config):
        """Test handling of negative retry count."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        negative_job_context = self.minimal_job_context.copy()
        negative_job_context["retry_count"] = -1

        tool = EnforcePolicies(
            job_context=negative_job_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        # Should normalize negative count to 0
        self.assertEqual(result["decision"], "proceed")

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_quota_exceeded_boundary_conditions(self, mock_load_config):
        """Test various quota boundary conditions."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        # Test exact quota limit
        exact_limit_state = {
            "quota_usage": {"youtube": 10000, "assemblyai": 100},  # Exactly at limits
            "daily_costs": {"transcription_usd": 0.0},
            "checkpoint_data": {}
        }

        tool = EnforcePolicies(
            job_context=self.minimal_job_context,
            current_state=exact_limit_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["decision"], "dead_letter_queue")
        self.assertIn("quota", result["reason"].lower())

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_quota_over_limit_boundary(self, mock_load_config):
        """Test quota usage exceeding limits."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        over_limit_state = {
            "quota_usage": {"youtube": 15000, "assemblyai": 150},  # Over limits
            "daily_costs": {"transcription_usd": 0.0},
            "checkpoint_data": {}
        }

        tool = EnforcePolicies(
            job_context=self.minimal_job_context,
            current_state=over_limit_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["decision"], "dead_letter_queue")

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_invalid_timestamp_format(self, mock_load_config):
        """Test handling of invalid timestamp formats."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        invalid_timestamp_context = self.minimal_job_context.copy()
        invalid_timestamp_context["last_attempt_at"] = "invalid-timestamp"

        tool = EnforcePolicies(
            job_context=invalid_timestamp_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle gracefully and proceed with default delay
        self.assertIn(result["decision"], ["proceed", "retry_with_delay"])

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_missing_config_fallback(self, mock_load_config):
        """Test behavior when configuration is missing or malformed."""
        # Return minimal/empty config
        mock_load_config.return_value = {}

        tool = EnforcePolicies(
            job_context=self.minimal_job_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        # Should fall back to hardcoded defaults
        self.assertIn(result["decision"], ["proceed", "retry_with_delay", "dead_letter_queue"])

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_extreme_delay_calculation(self, mock_load_config):
        """Test exponential backoff with extreme values."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 10, "base_delay_sec": 1000},  # Large base delay
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        high_retry_context = self.minimal_job_context.copy()
        high_retry_context["retry_count"] = 8  # Will cause exponential growth

        tool = EnforcePolicies(
            job_context=high_retry_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        if result["decision"] == "retry_with_delay":
            # Delay should be capped to reasonable maximum
            self.assertLessEqual(result["delay_sec"], 86400)  # 24 hours max

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_zero_base_delay_edge_case(self, mock_load_config):
        """Test handling of zero base delay configuration."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 0},  # Zero delay
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        retry_context = self.minimal_job_context.copy()
        retry_context["retry_count"] = 1

        tool = EnforcePolicies(
            job_context=retry_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        if result["decision"] == "retry_with_delay":
            # Should have some minimal delay even with zero base
            self.assertGreaterEqual(result["delay_sec"], 1)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_malformed_current_state(self, mock_load_config):
        """Test handling of malformed current state data."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        # Malformed state with missing fields
        malformed_state = {
            "quota_usage": {"youtube": "invalid"},  # String instead of int
            "daily_costs": {},  # Missing transcription_usd
            # Missing checkpoint_data
        }

        tool = EnforcePolicies(
            job_context=self.minimal_job_context,
            current_state=malformed_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle gracefully without crashing
        self.assertIn("decision", result)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_policy_overrides_extreme_values(self, mock_load_config):
        """Test policy overrides with extreme values."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        extreme_overrides = {
            "max_attempts": 0,  # Zero max attempts
            "base_delay_sec": -100,  # Negative delay
            "quota_threshold": 2.0  # Over 100% threshold
        }

        tool = EnforcePolicies(
            job_context=self.minimal_job_context,
            current_state=self.minimal_current_state,
            policy_overrides=extreme_overrides
        )

        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle extreme overrides gracefully
        self.assertIn("decision", result)

    @patch('orchestrator_agent.tools.enforce_policies.load_app_config')
    def test_unknown_error_types(self, mock_load_config):
        """Test handling of unknown or novel error types."""
        mock_load_config.return_value = {
            "reliability": {
                "retry": {"max_attempts": 3, "base_delay_sec": 60},
                "quotas": {"youtube_daily_limit": 10000, "assemblyai_daily_limit": 100}
            }
        }

        unknown_error_context = self.minimal_job_context.copy()
        unknown_error_context["error_type"] = "completely_unknown_error_type_xyz_2025"

        tool = EnforcePolicies(
            job_context=unknown_error_context,
            current_state=self.minimal_current_state
        )

        result_str = tool.run()
        result = json.loads(result_str)

        # Should handle unknown error types with default behavior
        self.assertIn("decision", result)


if __name__ == "__main__":
    unittest.main()