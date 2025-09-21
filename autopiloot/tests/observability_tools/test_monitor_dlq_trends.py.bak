"""
Tests for observability_agent.tools.monitor_dlq_trends module.

This module tests the MonitorDLQTrends tool which analyzes dead letter queue
patterns, detects anomalies, and provides operational insights.
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

from observability_agent.tools.monitor_dlq_trends import MonitorDLQTrends


class TestMonitorDLQTrends(unittest.TestCase):
    """Test cases for MonitorDLQTrends observability tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_query = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.where.return_value = self.mock_query
        self.mock_query.where.return_value = self.mock_query
        self.mock_query.order_by.return_value = self.mock_query

        # Sample DLQ entries for testing
        self.sample_dlq_entries = [
            self._create_mock_doc('entry1', {
                'job_type': 'single_video',
                'severity': 'high',
                'failure_context': {'error_type': 'authorization_failed'},
                'processing_attempts': 3,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=1)
            }),
            self._create_mock_doc('entry2', {
                'job_type': 'channel_scrape',
                'severity': 'medium',
                'failure_context': {'error_type': 'quota_exceeded'},
                'processing_attempts': 2,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=2)
            }),
            self._create_mock_doc('entry3', {
                'job_type': 'single_video',
                'severity': 'low',
                'failure_context': {'error_type': 'network_timeout'},
                'processing_attempts': 1,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=3)
            })
        ]

    def _create_mock_doc(self, doc_id, data):
        """Create a mock Firestore document."""
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.to_dict.return_value = data
        return mock_doc

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    @patch('observability_agent.tools.monitor_dlq_trends.audit_logger')
    def test_successful_dlq_trend_analysis(self, mock_audit, mock_env, mock_firestore):
        """Test successful DLQ trend analysis with normal patterns."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock DLQ entries
        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        # Create tool with default parameters
        tool = MonitorDLQTrends()

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful analysis
        self.assertIn('analysis_timestamp', result_data)
        self.assertIn('dlq_statistics', result_data)
        self.assertIn('trend_analysis', result_data)
        self.assertIn('anomaly_detection', result_data)
        self.assertIn('recommendations', result_data)

        # Verify statistics
        stats = result_data['dlq_statistics']
        self.assertEqual(stats['total_entries'], 3)
        self.assertIn('by_job_type', stats)
        self.assertIn('by_severity', stats)
        self.assertIn('by_error_type', stats)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called_with('jobs_deadletter')
        mock_audit.log_action.assert_called()

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_dlq_spike_detection(self, mock_env, mock_firestore):
        """Test detection of DLQ spikes indicating system issues."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create many recent DLQ entries to simulate spike
        spike_entries = []
        for i in range(20):
            spike_entries.append(self._create_mock_doc(f'spike_{i}', {
                'job_type': 'single_video',
                'severity': 'high',
                'failure_context': {'error_type': 'api_timeout'},
                'processing_attempts': 3,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(minutes=10 + i)
            }))

        self.mock_query.stream.return_value = iter(spike_entries)

        tool = MonitorDLQTrends(
            analysis_window_hours=24,
            spike_threshold=10  # Lower threshold to trigger spike detection
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert spike detection
        anomalies = result_data['anomaly_detection']
        self.assertIn('spike_detected', anomalies)
        self.assertTrue(anomalies['spike_detected'])
        self.assertGreater(anomalies['spike_severity'], 0)

        # Should have urgent recommendations
        recommendations = result_data['recommendations']
        urgent_recs = [rec for rec in recommendations if rec.get('priority') == 'urgent']
        self.assertGreater(len(urgent_recs), 0)

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_error_pattern_analysis(self, mock_env, mock_firestore):
        """Test analysis of error patterns and clustering."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create entries with specific error patterns
        pattern_entries = [
            self._create_mock_doc('pattern1', {
                'job_type': 'single_video',
                'failure_context': {'error_type': 'authorization_failed'},
                'processing_attempts': 1,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=1)
            }),
            self._create_mock_doc('pattern2', {
                'job_type': 'single_video',
                'failure_context': {'error_type': 'authorization_failed'},
                'processing_attempts': 2,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=1, minutes=30)
            }),
            self._create_mock_doc('pattern3', {
                'job_type': 'channel_scrape',
                'failure_context': {'error_type': 'quota_exceeded'},
                'processing_attempts': 1,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=2)
            })
        ]

        self.mock_query.stream.return_value = iter(pattern_entries)

        tool = MonitorDLQTrends(include_pattern_analysis=True)

        result = tool.run()
        result_data = json.loads(result)

        # Assert pattern analysis
        self.assertIn('error_patterns', result_data)
        patterns = result_data['error_patterns']

        # Should identify authorization_failed as dominant pattern
        auth_pattern = next((p for p in patterns
                           if p['error_type'] == 'authorization_failed'), None)
        self.assertIsNotNone(auth_pattern)
        self.assertEqual(auth_pattern['count'], 2)
        self.assertGreater(auth_pattern['frequency_score'], 0)

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_trend_window_analysis(self, mock_env, mock_firestore):
        """Test trend analysis across different time windows."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create time-distributed entries
        time_entries = []
        base_time = datetime.now(timezone.utc)

        # Recent entries (last 6 hours)
        for i in range(5):
            time_entries.append(self._create_mock_doc(f'recent_{i}', {
                'job_type': 'single_video',
                'failure_context': {'error_type': 'network_timeout'},
                'dlq_created_at': base_time - timedelta(hours=i)
            }))

        # Older entries (6-24 hours ago)
        for i in range(2):
            time_entries.append(self._create_mock_doc(f'older_{i}', {
                'job_type': 'channel_scrape',
                'failure_context': {'error_type': 'quota_exceeded'},
                'dlq_created_at': base_time - timedelta(hours=12 + i)
            }))

        self.mock_query.stream.return_value = iter(time_entries)

        tool = MonitorDLQTrends(analysis_window_hours=24)

        result = tool.run()
        result_data = json.loads(result)

        # Assert trend analysis
        trend = result_data['trend_analysis']
        self.assertIn('recent_vs_historical', trend)
        self.assertIn('hourly_distribution', trend)
        self.assertIn('trend_direction', trend)

        # Should detect increase in recent period
        self.assertIn(trend['trend_direction'], ['increasing', 'stable', 'decreasing'])

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_custom_analysis_window(self, mock_env, mock_firestore):
        """Test DLQ analysis with custom time window."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        # Test with 12-hour window
        tool_12h = MonitorDLQTrends(analysis_window_hours=12)
        result = tool_12h.run()
        result_data = json.loads(result)

        # Should include window info
        self.assertEqual(result_data['analysis_window_hours'], 12)

        # Verify time filter was applied in Firestore query
        where_calls = self.mock_query.where.call_args_list
        time_filter_found = any(
            call[0][0] == 'dlq_created_at' and call[0][1] == '>='
            for call in where_calls
        )
        self.assertTrue(time_filter_found)

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_empty_dlq_analysis(self, mock_env, mock_firestore):
        """Test analysis when DLQ is empty."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock empty DLQ
        self.mock_query.stream.return_value = iter([])

        tool = MonitorDLQTrends()

        result = tool.run()
        result_data = json.loads(result)

        # Should handle empty DLQ gracefully
        stats = result_data['dlq_statistics']
        self.assertEqual(stats['total_entries'], 0)
        self.assertEqual(len(stats['by_job_type']), 0)

        # No anomalies should be detected
        anomalies = result_data['anomaly_detection']
        self.assertFalse(anomalies['spike_detected'])

        # Should have positive recommendations about DLQ health
        recommendations = result_data['recommendations']
        self.assertGreater(len(recommendations), 0)

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_high_severity_clustering(self, mock_env, mock_firestore):
        """Test detection of high-severity error clustering."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create multiple high-severity entries
        high_severity_entries = []
        for i in range(8):
            high_severity_entries.append(self._create_mock_doc(f'high_sev_{i}', {
                'job_type': 'single_video',
                'severity': 'critical' if i < 3 else 'high',
                'failure_context': {'error_type': 'system_critical'},
                'processing_attempts': 4,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(minutes=30 + i * 5)
            }))

        self.mock_query.stream.return_value = iter(high_severity_entries)

        tool = MonitorDLQTrends()

        result = tool.run()
        result_data = json.loads(result)

        # Should detect high severity clustering
        anomalies = result_data['anomaly_detection']
        self.assertIn('high_severity_cluster', anomalies)

        # Should have critical recommendations
        recommendations = result_data['recommendations']
        critical_recs = [rec for rec in recommendations if rec.get('priority') == 'critical']
        self.assertGreater(len(critical_recs), 0)

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_firestore_query_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore query failures."""
        # Setup mocks to simulate query failure
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query failure
        self.mock_query.stream.side_effect = Exception("Query failed")

        tool = MonitorDLQTrends()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Query failed', result_data['error'])

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = MonitorDLQTrends()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    def test_tool_parameter_validation(self):
        """Test parameter validation and defaults."""
        # Test valid parameters
        tool = MonitorDLQTrends(
            analysis_window_hours=48,
            spike_threshold=20,
            include_pattern_analysis=False
        )
        self.assertEqual(tool.analysis_window_hours, 48)
        self.assertEqual(tool.spike_threshold, 20)
        self.assertFalse(tool.include_pattern_analysis)

        # Test defaults
        tool_defaults = MonitorDLQTrends()
        self.assertEqual(tool_defaults.analysis_window_hours, 24)
        self.assertEqual(tool_defaults.spike_threshold, 15)
        self.assertTrue(tool_defaults.include_pattern_analysis)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = MonitorDLQTrends(
            analysis_window_hours=12,
            spike_threshold=10
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, MonitorDLQTrends)

        # Test parameter values
        self.assertEqual(tool.analysis_window_hours, 12)
        self.assertEqual(tool.spike_threshold, 10)

    @patch('observability_agent.tools.monitor_dlq_trends.firestore.Client')
    @patch('observability_agent.tools.monitor_dlq_trends.get_required_env_var')
    def test_recommendation_generation(self, mock_env, mock_firestore):
        """Test generation of actionable recommendations based on trends."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create pattern indicating specific issues
        problematic_entries = [
            self._create_mock_doc('prob1', {
                'job_type': 'channel_scrape',
                'failure_context': {'error_type': 'quota_exceeded'},
                'processing_attempts': 1,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(minutes=10)
            }),
            self._create_mock_doc('prob2', {
                'job_type': 'channel_scrape',
                'failure_context': {'error_type': 'quota_exceeded'},
                'processing_attempts': 1,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(minutes=20)
            }),
            self._create_mock_doc('prob3', {
                'job_type': 'single_video',
                'failure_context': {'error_type': 'authorization_failed'},
                'processing_attempts': 3,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(minutes=30)
            })
        ]

        self.mock_query.stream.return_value = iter(problematic_entries)

        tool = MonitorDLQTrends()

        result = tool.run()
        result_data = json.loads(result)

        # Assert recommendations exist
        recommendations = result_data['recommendations']
        self.assertGreater(len(recommendations), 0)

        # Recommendations should have required fields
        for rec in recommendations:
            self.assertIn('category', rec)
            self.assertIn('description', rec)
            self.assertIn('priority', rec)
            self.assertIn('action_required', rec)

        # Should have quota-related recommendations
        quota_recs = [rec for rec in recommendations
                     if 'quota' in rec['description'].lower()]
        self.assertGreater(len(quota_recs), 0)


if __name__ == '__main__':
    unittest.main()