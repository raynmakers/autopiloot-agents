"""
Tests for observability_agent.tools.alert_engine module.

This module tests the AlertEngine tool which provides centralized alert throttling,
deduplication, and escalation orchestration with Slack integration.
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

from observability_agent.tools.alert_engine import AlertEngine


class TestAlertEngine(unittest.TestCase):
    """Test cases for AlertEngine observability tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document = MagicMock()
        self.mock_query = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document
        self.mock_collection.where.return_value = self.mock_query

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    @patch('observability_agent.tools.alert_engine.audit_logger')
    def test_successful_alert_processing(self, mock_audit, mock_env, mock_firestore):
        """Test successful alert processing without throttling."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock no existing throttling record
        self.mock_document.get.return_value.exists = False
        self.mock_document.set = MagicMock()

        # Create alert engine tool
        tool = AlertEngine(
            alert_type='quota_threshold',
            severity='warning',
            message='YouTube API quota approaching limit (85%)',
            details={'quota_used': 8500, 'quota_limit': 10000},
            source_component='quota_monitor'
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful processing
        self.assertIn('alert_id', result_data)
        self.assertEqual(result_data['status'], 'delivered')
        self.assertTrue(result_data['delivery_attempted'])

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called()
        mock_audit.log_action.assert_called()

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_alert_throttling_applied(self, mock_env, mock_firestore):
        """Test that alerts are properly throttled when rate limits exceeded."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock existing throttling record (recent alert of same type)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_throttle_doc = MagicMock()
        mock_throttle_doc.exists = True
        mock_throttle_doc.to_dict.return_value = {
            'last_alert_time': recent_time,
            'alert_count': 3,
            'throttle_until': datetime.now(timezone.utc) + timedelta(minutes=10)
        }
        self.mock_document.get.return_value = mock_throttle_doc

        tool = AlertEngine(
            alert_type='quota_threshold',
            severity='warning',
            message='YouTube API quota still high',
            source_component='quota_monitor'
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert throttling applied
        self.assertEqual(result_data['status'], 'throttled')
        self.assertFalse(result_data['delivery_attempted'])
        self.assertIn('reason', result_data)
        self.assertIn('next_eligible_time', result_data)

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_override_throttling_for_critical_alerts(self, mock_env, mock_firestore):
        """Test that critical alerts can override throttling."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock existing throttling (should be bypassed)
        self.mock_document.get.return_value.exists = True
        self.mock_document.set = MagicMock()

        tool = AlertEngine(
            alert_type='system_error',
            severity='critical',
            message='Critical system failure detected',
            override_throttling=True,  # Override throttling
            source_component='system_monitor'
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert alert delivered despite throttling
        self.assertEqual(result_data['status'], 'delivered')
        self.assertTrue(result_data['delivery_attempted'])

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_alert_deduplication(self, mock_env, mock_firestore):
        """Test that duplicate alerts are properly deduplicated."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create multiple identical alerts
        alert_details = {
            'alert_type': 'dlq_spike',
            'severity': 'error',
            'message': 'Dead letter queue showing unusual spike',
            'source_component': 'dlq_monitor'
        }

        tool1 = AlertEngine(**alert_details)
        tool2 = AlertEngine(**alert_details)

        # Both should have same fingerprint
        fingerprint1 = tool1._generate_alert_fingerprint()
        fingerprint2 = tool2._generate_alert_fingerprint()

        self.assertEqual(fingerprint1, fingerprint2)

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_severity_escalation_chains(self, mock_env, mock_firestore):
        """Test alert severity escalation logic."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_document.get.return_value.exists = False
        self.mock_document.set = MagicMock()

        # Test different severity levels
        severity_levels = ['info', 'warning', 'error', 'critical']

        for severity in severity_levels:
            with self.subTest(severity=severity):
                tool = AlertEngine(
                    alert_type='performance_degradation',
                    severity=severity,
                    message=f'Performance issue - {severity} level',
                    source_component='performance_monitor'
                )

                result = tool.run()
                result_data = json.loads(result)

                # All should be delivered but with different escalation
                self.assertEqual(result_data['status'], 'delivered')
                self.assertIn('escalation_level', result_data)

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_alert_enrichment(self, mock_env, mock_firestore):
        """Test alert enrichment with additional context."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_document.get.return_value.exists = False
        self.mock_document.set = MagicMock()

        # Test with rich alert details
        rich_details = {
            'quota_used': 9500,
            'quota_limit': 10000,
            'affected_operations': ['scraping', 'discovery'],
            'estimated_reset_time': '2025-09-16T00:00:00Z',
            'recent_activity': {
                'last_hour_usage': 500,
                'trend': 'increasing'
            }
        }

        tool = AlertEngine(
            alert_type='quota_threshold',
            severity='critical',
            message='YouTube API quota critically high',
            details=rich_details,
            source_component='quota_monitor'
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert enrichment was applied
        self.assertEqual(result_data['status'], 'delivered')
        self.assertIn('enriched_context', result_data)

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = AlertEngine(
            alert_type='system_error',
            severity='error',
            message='Test error alert'
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_invalid_alert_types(self, mock_env, mock_firestore):
        """Test validation of alert types."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Test invalid alert type (should still process but may affect routing)
        tool = AlertEngine(
            alert_type='invalid_alert_type',
            severity='warning',
            message='Test invalid alert type'
        )

        # Should not raise exception (flexible alert types)
        result = tool.run()
        result_data = json.loads(result)

        # Should handle gracefully
        self.assertIn('status', result_data)

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_invalid_severity_levels(self, mock_env, mock_firestore):
        """Test validation of severity levels."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Test invalid severity (should normalize or handle gracefully)
        tool = AlertEngine(
            alert_type='system_error',
            severity='invalid_severity',
            message='Test invalid severity'
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should handle gracefully or normalize
        self.assertIn('status', result_data)

    def test_alert_fingerprint_generation(self):
        """Test alert fingerprint generation for deduplication."""
        # Create identical alerts
        tool1 = AlertEngine(
            alert_type='quota_threshold',
            severity='warning',
            message='Quota high',
            source_component='monitor'
        )

        tool2 = AlertEngine(
            alert_type='quota_threshold',
            severity='warning',
            message='Quota high',
            source_component='monitor'
        )

        # Different alerts
        tool3 = AlertEngine(
            alert_type='dlq_spike',
            severity='warning',
            message='DLQ spike detected',
            source_component='dlq_monitor'
        )

        # Test fingerprint generation
        fp1 = tool1._generate_alert_fingerprint()
        fp2 = tool2._generate_alert_fingerprint()
        fp3 = tool3._generate_alert_fingerprint()

        # Identical alerts should have same fingerprint
        self.assertEqual(fp1, fp2)

        # Different alerts should have different fingerprints
        self.assertNotEqual(fp1, fp3)

        # Fingerprints should be consistent
        self.assertEqual(fp1, tool1._generate_alert_fingerprint())

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = AlertEngine(
            alert_type='test_alert',
            severity='info',
            message='Test message',
            details={'key': 'value'},
            source_component='test_component'
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, AlertEngine)

        # Test required parameters
        self.assertEqual(tool.alert_type, 'test_alert')
        self.assertEqual(tool.severity, 'info')
        self.assertEqual(tool.message, 'Test message')
        self.assertEqual(tool.source_component, 'test_component')
        self.assertFalse(tool.override_throttling)

    @patch('observability_agent.tools.alert_engine.firestore.Client')
    @patch('observability_agent.tools.alert_engine.get_required_env_var')
    def test_multiple_alert_types_coverage(self, mock_env, mock_firestore):
        """Test coverage of different alert types."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_document.get.return_value.exists = False
        self.mock_document.set = MagicMock()

        alert_types = [
            'quota_threshold',
            'dlq_spike',
            'stuck_jobs',
            'cost_budget',
            'system_error',
            'performance_degradation'
        ]

        for alert_type in alert_types:
            with self.subTest(alert_type=alert_type):
                tool = AlertEngine(
                    alert_type=alert_type,
                    severity='warning',
                    message=f'Test {alert_type} alert',
                    source_component='test_monitor'
                )

                result = tool.run()
                result_data = json.loads(result)

                # All alert types should be processable
                self.assertIn('status', result_data)
                self.assertIn('alert_id', result_data)


if __name__ == '__main__':
    unittest.main()