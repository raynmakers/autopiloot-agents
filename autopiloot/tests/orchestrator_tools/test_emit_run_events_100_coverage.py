"""
Comprehensive test suite for EmitRunEvents tool targeting 80%+ coverage.
Tests event emission, Slack formatting, audit logging, and health scoring.
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
from orchestrator_agent.tools.emit_run_events import EmitRunEvents

# Patch EmitRunEvents __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.run_summary = kwargs.get('run_summary', {})
    self.run_context = kwargs.get('run_context', {})
    self.operational_insights = kwargs.get('operational_insights', None)
    self.alert_level = kwargs.get('alert_level', 'info')

EmitRunEvents.__init__ = patched_init


class TestEmitRunEvents100Coverage(unittest.TestCase):
    """Test suite targeting 80%+ coverage for EmitRunEvents."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_run_summary = {
            "planned": 25,
            "succeeded": 23,
            "failed": 2,
            "dlq_count": 1,
            "quota_state": {"youtube": 0.75, "assemblyai": 0.45},
            "total_cost_usd": 2.35
        }

        self.valid_run_context = {
            "run_id": "daily_20250127",
            "run_type": "scheduled_daily",
            "started_at": "2025-01-27T01:00:00Z",
            "completed_at": "2025-01-27T03:45:00Z"
        }

    @patch('orchestrator_agent.tools.emit_run_events.audit_logger')
    @patch('orchestrator_agent.tools.emit_run_events.load_app_config')
    def test_successful_event_emission(self, mock_config, mock_audit):
        """Test successful event emission (lines 64-112)."""
        mock_config.return_value = {}

        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            alert_level="info"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "emitted")
        self.assertIn("event_id", data)
        self.assertIn("health_score", data)
        self.assertIn("run_metrics", data)

    @patch('orchestrator_agent.tools.emit_run_events.audit_logger')
    @patch('orchestrator_agent.tools.emit_run_events.load_app_config')
    def test_event_emission_with_insights(self, mock_config, mock_audit):
        """Test event emission with operational insights (lines 81)."""
        mock_config.return_value = {}

        insights = {
            "performance_trend": "improving",
            "bottlenecks": ["assemblyai_quota"],
            "recommendations": ["increase_batch_size"]
        }

        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            operational_insights=insights,
            alert_level="info"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "emitted")

    def test_validate_missing_run_summary_field(self):
        """Test validation for missing run_summary field (lines 124-125)."""
        invalid_summary = {"planned": 10, "succeeded": 8}  # Missing 'failed'

        tool = EmitRunEvents(
            run_summary=invalid_summary,
            run_context=self.valid_run_context
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Missing required run_summary field", str(context.exception))

    def test_validate_missing_run_context_field(self):
        """Test validation for missing run_context field (lines 129-130)."""
        invalid_context = {"run_id": "test", "run_type": "daily"}  # Missing 'started_at'

        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=invalid_context
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Missing required run_context field", str(context.exception))

    def test_validate_invalid_alert_level(self):
        """Test validation for invalid alert level (lines 133-134)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            alert_level="invalid"
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("alert_level must be one of", str(context.exception))

    def test_format_slack_message_basic(self):
        """Test Slack message formatting (lines 136-182)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            alert_level="info"
        )

        event_payload = {
            "event_id": "test_event",
            "event_type": "operational_run_report",
            "run_summary": self.valid_run_summary,
            "run_context": self.valid_run_context
        }

        slack_message = tool._format_slack_message(event_payload)

        self.assertIn("channel", slack_message)
        self.assertIn("title", slack_message)
        self.assertIn("summary_text", slack_message)
        self.assertIn("alert_level", slack_message)

    def test_format_slack_message_with_insights(self):
        """Test Slack message formatting with insights (lines 168-173)."""
        insights = {
            "bottlenecks": ["assemblyai_quota", "youtube_api"],
            "recommendations": ["increase_batch_size", "optimize_scheduling"]
        }

        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            operational_insights=insights,
            alert_level="warning"
        )

        event_payload = {
            "event_id": "test_event",
            "run_summary": self.valid_run_summary,
            "run_context": self.valid_run_context
        }

        slack_message = tool._format_slack_message(event_payload)

        self.assertIn("Bottlenecks", slack_message["insights_text"])
        self.assertIn("Recommendations", slack_message["insights_text"])

    def test_send_to_observability_agent(self):
        """Test sending message to ObservabilityAgent (lines 184-193)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context
        )

        slack_payload = {
            "channel": "ops-autopiloot",
            "title": "Test Title",
            "alert_level": "info"
        }

        result = tool._send_to_observability_agent(slack_payload)

        self.assertTrue(result["sent_to_slack"])
        self.assertEqual(result["channel"], "ops-autopiloot")

    @patch('orchestrator_agent.tools.emit_run_events.audit_logger')
    def test_create_audit_entry_success(self, mock_audit):
        """Test successful audit entry creation (lines 197-210)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context
        )

        event_payload = {}
        result = tool._create_audit_entry(event_payload)

        self.assertTrue(result["audit_logged"])
        mock_audit.log_operational_event.assert_called_once()

    @patch('orchestrator_agent.tools.emit_run_events.audit_logger')
    def test_create_audit_entry_exception(self, mock_audit):
        """Test audit entry creation exception handling (lines 212-216)."""
        mock_audit.log_operational_event.side_effect = Exception("Audit error")

        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context
        )

        event_payload = {}
        result = tool._create_audit_entry(event_payload)

        self.assertFalse(result["audit_logged"])
        self.assertIn("audit_error", result)

    def test_calculate_success_rate(self):
        """Test success rate calculation (lines 218-226)."""
        tool = EmitRunEvents(
            run_summary={"planned": 25, "succeeded": 20, "failed": 5},
            run_context=self.valid_run_context
        )

        success_rate = tool._calculate_success_rate()
        self.assertEqual(success_rate, 0.8)

    def test_calculate_success_rate_zero_planned(self):
        """Test success rate with zero planned (lines 223-224)."""
        tool = EmitRunEvents(
            run_summary={"planned": 0, "succeeded": 0, "failed": 0},
            run_context=self.valid_run_context
        )

        success_rate = tool._calculate_success_rate()
        self.assertEqual(success_rate, 0.0)

    def test_calculate_cost_efficiency(self):
        """Test cost efficiency calculation (lines 228-236)."""
        tool = EmitRunEvents(
            run_summary={"planned": 10, "succeeded": 10, "failed": 0, "total_cost_usd": 5.0},
            run_context=self.valid_run_context
        )

        cost_efficiency = tool._calculate_cost_efficiency()
        self.assertEqual(cost_efficiency, 0.5)

    def test_calculate_cost_efficiency_zero_succeeded(self):
        """Test cost efficiency with zero succeeded (lines 233-234)."""
        tool = EmitRunEvents(
            run_summary={"planned": 10, "succeeded": 0, "failed": 10, "total_cost_usd": 5.0},
            run_context=self.valid_run_context
        )

        cost_efficiency = tool._calculate_cost_efficiency()
        self.assertEqual(cost_efficiency, 0.0)

    def test_calculate_run_duration(self):
        """Test run duration calculation (lines 238-252)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context={
                "run_id": "test",
                "run_type": "daily",
                "started_at": "2025-01-27T01:00:00Z",
                "completed_at": "2025-01-27T03:45:00Z"
            }
        )

        duration = tool._calculate_run_duration()
        self.assertAlmostEqual(duration, 2.75, places=2)

    def test_calculate_run_duration_missing_times(self):
        """Test run duration with missing timestamps (lines 243-244)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context={"run_id": "test", "run_type": "daily", "started_at": "2025-01-27T01:00:00Z"}
        )

        duration = tool._calculate_run_duration()
        self.assertEqual(duration, 0.0)

    def test_calculate_run_duration_invalid_format(self):
        """Test run duration with invalid timestamp format (lines 251-252)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context={
                "run_id": "test",
                "run_type": "daily",
                "started_at": "invalid",
                "completed_at": "invalid"
            }
        )

        duration = tool._calculate_run_duration()
        self.assertEqual(duration, 0.0)

    def test_calculate_health_score_excellent(self):
        """Test health score calculation for excellent performance (lines 254-277)."""
        tool = EmitRunEvents(
            run_summary={
                "planned": 100,
                "succeeded": 100,
                "failed": 0,
                "dlq_count": 0,
                "quota_state": {"youtube": 0.75, "assemblyai": 0.75}
            },
            run_context=self.valid_run_context
        )

        health_score = tool._calculate_health_score()
        self.assertGreater(health_score, 90)

    def test_calculate_health_score_with_dlq(self):
        """Test health score with DLQ entries (lines 262-265)."""
        tool = EmitRunEvents(
            run_summary={
                "planned": 100,
                "succeeded": 95,
                "failed": 5,
                "dlq_count": 5,
                "quota_state": {"youtube": 0.5}
            },
            run_context=self.valid_run_context
        )

        health_score = tool._calculate_health_score()
        self.assertLess(health_score, 100)

    def test_calculate_health_score_optimal_quota(self):
        """Test health score with optimal quota usage (lines 272-273)."""
        tool = EmitRunEvents(
            run_summary={
                "planned": 100,
                "succeeded": 95,
                "failed": 5,
                "dlq_count": 1,
                "quota_state": {"youtube": 0.75}
            },
            run_context=self.valid_run_context
        )

        health_score = tool._calculate_health_score()
        # Should get bonus for optimal quota (70-80%)
        self.assertGreater(health_score, 80)

    def test_calculate_health_score_partial_quota(self):
        """Test health score with partial quota bonus (lines 274-275)."""
        tool = EmitRunEvents(
            run_summary={
                "planned": 100,
                "succeeded": 95,
                "failed": 5,
                "dlq_count": 1,
                "quota_state": {"youtube": 0.85}
            },
            run_context=self.valid_run_context
        )

        health_score = tool._calculate_health_score()
        self.assertGreater(health_score, 70)

    def test_get_status_emoji_critical(self):
        """Test emoji for critical alert level (lines 281-282)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            alert_level="critical"
        )

        emoji = tool._get_status_emoji(0.9, "critical")
        self.assertEqual(emoji, "🚨")

    def test_get_status_emoji_error(self):
        """Test emoji for error alert level (lines 283-284)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            alert_level="error"
        )

        emoji = tool._get_status_emoji(0.9, "error")
        self.assertEqual(emoji, "❌")

    def test_get_status_emoji_warning(self):
        """Test emoji for warning alert level (lines 285-286)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context,
            alert_level="warning"
        )

        emoji = tool._get_status_emoji(0.9, "warning")
        self.assertEqual(emoji, "⚠️")

    def test_get_status_emoji_high_success(self):
        """Test emoji for high success rate (lines 287-288)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context
        )

        emoji = tool._get_status_emoji(0.96, "info")
        self.assertEqual(emoji, "✅")

    def test_get_status_emoji_moderate_success(self):
        """Test emoji for moderate success rate (lines 289-290)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context
        )

        emoji = tool._get_status_emoji(0.85, "info")
        self.assertEqual(emoji, "🟡")

    def test_get_status_emoji_low_success(self):
        """Test emoji for low success rate (lines 291-292)."""
        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context
        )

        emoji = tool._get_status_emoji(0.6, "info")
        self.assertEqual(emoji, "🔴")

    @patch('orchestrator_agent.tools.emit_run_events.load_app_config')
    def test_exception_handling(self, mock_config):
        """Test exception handling in run method (lines 114-118)."""
        mock_config.side_effect = Exception("Config error")

        tool = EmitRunEvents(
            run_summary=self.valid_run_summary,
            run_context=self.valid_run_context
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertIsNone(data["event_id"])


if __name__ == "__main__":
    unittest.main()