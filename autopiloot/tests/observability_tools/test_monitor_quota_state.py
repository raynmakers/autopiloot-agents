"""
Tests for observability_agent.tools.monitor_quota_state module.

This module tests the MonitorQuotaState tool which tracks YouTube and AssemblyAI
quota usage with threshold alerting and reset window calculations.
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

from observability_agent.tools.monitor_quota_state import MonitorQuotaState


class TestMonitorQuotaState(unittest.TestCase):
    """Test cases for MonitorQuotaState observability tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document

        # Mock config data
        self.mock_config = {
            'quotas': {
                'youtube_daily_limit': 10000,
                'assemblyai_daily_limit_usd': 5.0
            }
        }

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    @patch('observability_agent.tools.monitor_quota_state.audit_logger')
    def test_successful_quota_monitoring_below_threshold(self, mock_audit, mock_config, mock_env, mock_firestore):
        """Test successful quota monitoring when usage is below alert threshold."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock current quota usage (below threshold)
        mock_quota_doc = MagicMock()
        mock_quota_doc.to_dict.return_value = {
            'youtube': 3000,    # 30% of 10k limit
            'assemblyai': 2.0   # 40% of $5 limit
        }
        self.mock_collection.limit.return_value.stream.return_value = [mock_quota_doc]

        # Create tool with default threshold (80%)
        tool = MonitorQuotaState()

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful monitoring
        self.assertIn('youtube_state', result_data)
        self.assertIn('assemblyai_state', result_data)
        self.assertEqual(len(result_data['alerts']), 0)  # No alerts below threshold

        # Verify quota calculations
        self.assertLess(result_data['youtube_state']['utilization'], 0.8)
        self.assertLess(result_data['assemblyai_state']['utilization'], 0.8)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called()
        mock_audit.log_action.assert_called()

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_quota_threshold_exceeded_generates_alerts(self, mock_config, mock_env, mock_firestore):
        """Test that quota threshold violations generate appropriate alerts."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock high quota usage (above threshold)
        mock_quota_doc = MagicMock()
        mock_quota_doc.to_dict.return_value = {
            'youtube': 8500,    # 85% of 10k limit (above 80% threshold)
            'assemblyai': 4.5   # 90% of $5 limit
        }
        self.mock_collection.limit.return_value.stream.return_value = [mock_quota_doc]

        # Create tool with default threshold
        tool = MonitorQuotaState(alert_threshold=0.8)

        result = tool.run()
        result_data = json.loads(result)

        # Assert alerts were generated
        self.assertGreater(len(result_data['alerts']), 0)

        # Check for YouTube alert
        youtube_alert = next((alert for alert in result_data['alerts']
                            if alert['service'] == 'youtube'), None)
        self.assertIsNotNone(youtube_alert)
        self.assertEqual(youtube_alert['severity'], 'warning')  # 85% < 95%

        # Check for AssemblyAI alert
        assemblyai_alert = next((alert for alert in result_data['alerts']
                               if alert['service'] == 'assemblyai'), None)
        self.assertIsNotNone(assemblyai_alert)
        self.assertEqual(assemblyai_alert['severity'], 'critical')  # 90% >= 95%

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_critical_quota_threshold(self, mock_config, mock_env, mock_firestore):
        """Test critical alert generation when quota exceeds 95%."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock critical quota usage
        mock_quota_doc = MagicMock()
        mock_quota_doc.to_dict.return_value = {
            'youtube': 9800,    # 98% of 10k limit
            'assemblyai': 4.8   # 96% of $5 limit
        }
        self.mock_collection.limit.return_value.stream.return_value = [mock_quota_doc]

        tool = MonitorQuotaState(alert_threshold=0.8)

        result = tool.run()
        result_data = json.loads(result)

        # Both services should have critical alerts
        critical_alerts = [alert for alert in result_data['alerts']
                          if alert['severity'] == 'critical']
        self.assertGreaterEqual(len(critical_alerts), 2)

        # Check recommended actions for critical alerts
        for alert in critical_alerts:
            if alert['service'] == 'youtube':
                self.assertIn('Halt all YouTube API calls', alert['recommended_action'])
            elif alert['service'] == 'assemblyai':
                self.assertIn('Stop all transcription', alert['recommended_action'])

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_custom_alert_threshold(self, mock_config, mock_env, mock_firestore):
        """Test quota monitoring with custom alert threshold."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock quota usage at 70%
        mock_quota_doc = MagicMock()
        mock_quota_doc.to_dict.return_value = {
            'youtube': 7000,    # 70% of 10k limit
            'assemblyai': 3.5   # 70% of $5 limit
        }
        self.mock_collection.limit.return_value.stream.return_value = [mock_quota_doc]

        # Test with 60% threshold (should alert)
        tool_low_threshold = MonitorQuotaState(alert_threshold=0.6)
        result = tool_low_threshold.run()
        result_data = json.loads(result)
        self.assertGreater(len(result_data['alerts']), 0)

        # Test with 90% threshold (should not alert)
        tool_high_threshold = MonitorQuotaState(alert_threshold=0.9)
        result = tool_high_threshold.run()
        result_data = json.loads(result)
        self.assertEqual(len(result_data['alerts']), 0)

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_quota_predictions(self, mock_config, mock_env, mock_firestore):
        """Test quota usage predictions based on current rate."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock quota usage with historical data for rate calculation
        mock_quota_doc = MagicMock()
        mock_quota_doc.to_dict.return_value = {
            'youtube': 5000,
            'assemblyai': 2.5
        }
        self.mock_collection.limit.return_value.stream.return_value = [mock_quota_doc]

        # Test with predictions enabled
        tool_with_predictions = MonitorQuotaState(include_predictions=True)
        result = tool_with_predictions.run()
        result_data = json.loads(result)

        # Should include prediction fields
        self.assertIn('predictions', result_data)

        # Test with predictions disabled
        tool_without_predictions = MonitorQuotaState(include_predictions=False)
        result = tool_without_predictions.run()
        result_data = json.loads(result)

        # Should not include prediction fields
        self.assertNotIn('predictions', result_data)

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_reset_window_calculations(self, mock_config, mock_env, mock_firestore):
        """Test quota reset window time calculations."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock current quota usage
        mock_quota_doc = MagicMock()
        mock_quota_doc.to_dict.return_value = {
            'youtube': 8000,
            'assemblyai': 4.0
        }
        self.mock_collection.limit.return_value.stream.return_value = [mock_quota_doc]

        tool = MonitorQuotaState(alert_threshold=0.7)  # Generate alerts

        result = tool.run()
        result_data = json.loads(result)

        # Check that reset timing is included in alerts
        for alert in result_data['alerts']:
            self.assertIn('time_to_reset', alert)
            self.assertIsInstance(alert['time_to_reset'], (int, float))
            self.assertGreaterEqual(alert['time_to_reset'], 0)
            self.assertLessEqual(alert['time_to_reset'], 24)  # Should be within 24 hours

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_no_quota_data_available(self, mock_config, mock_env, mock_firestore):
        """Test handling when no quota data is available."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock empty quota data
        self.mock_collection.limit.return_value.stream.return_value = []

        tool = MonitorQuotaState()

        result = tool.run()
        result_data = json.loads(result)

        # Should handle gracefully with zero usage
        self.assertIn('youtube_state', result_data)
        self.assertIn('assemblyai_state', result_data)
        self.assertEqual(result_data['youtube_state']['current_usage'], 0)
        self.assertEqual(result_data['assemblyai_state']['current_usage'], 0)

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = MonitorQuotaState()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_config_loading_failure(self, mock_config, mock_env, mock_firestore):
        """Test handling of configuration loading failures."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.side_effect = Exception("Config load failed")

        tool = MonitorQuotaState()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)

    def test_alert_threshold_validation(self):
        """Test validation of alert threshold parameter."""
        # Valid thresholds should work
        tool_valid = MonitorQuotaState(alert_threshold=0.8)
        self.assertEqual(tool_valid.alert_threshold, 0.8)

        # Test edge cases
        tool_min = MonitorQuotaState(alert_threshold=0.0)
        self.assertEqual(tool_min.alert_threshold, 0.0)

        tool_max = MonitorQuotaState(alert_threshold=1.0)
        self.assertEqual(tool_max.alert_threshold, 1.0)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = MonitorQuotaState(
            alert_threshold=0.9,
            include_predictions=False
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, MonitorQuotaState)

        # Test parameter values
        self.assertEqual(tool.alert_threshold, 0.9)
        self.assertFalse(tool.include_predictions)

        # Test defaults
        tool_defaults = MonitorQuotaState()
        self.assertEqual(tool_defaults.alert_threshold, 0.8)
        self.assertTrue(tool_defaults.include_predictions)

    @patch('observability_agent.tools.monitor_quota_state.firestore.Client')
    @patch('observability_agent.tools.monitor_quota_state.get_required_env_var')
    @patch('observability_agent.tools.monitor_quota_state.load_app_config')
    def test_quota_state_structure(self, mock_config, mock_env, mock_firestore):
        """Test the structure of quota state information returned."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        mock_config.return_value = self.mock_config

        # Mock quota usage
        mock_quota_doc = MagicMock()
        mock_quota_doc.to_dict.return_value = {
            'youtube': 6000,
            'assemblyai': 3.0
        }
        self.mock_collection.limit.return_value.stream.return_value = [mock_quota_doc]

        tool = MonitorQuotaState()

        result = tool.run()
        result_data = json.loads(result)

        # Verify structure of quota states
        for service in ['youtube', 'assemblyai']:
            state_key = f'{service}_state'
            self.assertIn(state_key, result_data)

            state = result_data[state_key]
            self.assertIn('service', state)
            self.assertIn('current_usage', state)
            self.assertIn('daily_limit', state)
            self.assertIn('utilization', state)
            self.assertIn('remaining', state)
            self.assertIn('time_to_reset_hours', state)
            self.assertIn('status', state)

            # Verify data types
            self.assertIsInstance(state['current_usage'], (int, float))
            self.assertIsInstance(state['utilization'], float)
            self.assertGreaterEqual(state['utilization'], 0.0)
            self.assertLessEqual(state['utilization'], 1.0)


if __name__ == '__main__':
    unittest.main()