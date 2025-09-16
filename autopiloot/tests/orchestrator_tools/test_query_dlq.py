"""
Tests for orchestrator_agent.tools.query_dlq module.

This module tests the QueryDLQ tool which queries and analyzes dead letter queue
entries with filtering, statistics, and pattern analysis capabilities.
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

from orchestrator_agent.tools.query_dlq import QueryDLQ


class TestQueryDLQ(unittest.TestCase):
    """Test cases for QueryDLQ orchestrator tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_query = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.where.return_value = self.mock_query
        self.mock_collection.order_by.return_value = self.mock_query
        self.mock_query.where.return_value = self.mock_query
        self.mock_query.order_by.return_value = self.mock_query
        self.mock_query.limit.return_value = self.mock_query

        # Sample DLQ entries for testing
        self.sample_dlq_entries = [
            self._create_mock_doc('entry1', {
                'job_type': 'single_video',
                'severity': 'high',
                'recovery_priority': 'urgent',
                'failure_context': {
                    'error_type': 'authorization_failed',
                    'original_inputs': {'video_id': 'vid123'}
                },
                'processing_attempts': 3,
                'dlq_created_at': datetime.now(timezone.utc)
            }),
            self._create_mock_doc('entry2', {
                'job_type': 'channel_scrape',
                'severity': 'medium',
                'recovery_priority': 'high',
                'failure_context': {
                    'error_type': 'quota_exceeded',
                    'original_inputs': {'channels': ['@test']}
                },
                'processing_attempts': 2,
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=2)
            }),
            self._create_mock_doc('entry3', {
                'job_type': 'single_video',
                'severity': 'low',
                'recovery_priority': 'medium',
                'failure_context': {
                    'error_type': 'network_timeout',
                    'original_inputs': {'video_id': 'vid456'}
                },
                'processing_attempts': 1,
                'video_id': 'vid456',
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=1)
            })
        ]

    def _create_mock_doc(self, doc_id, data):
        """Create a mock Firestore document."""
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.to_dict.return_value = data
        return mock_doc

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_successful_dlq_query_with_statistics(self, mock_env, mock_firestore):
        """Test successful DLQ query with statistics included."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query results
        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        # Create tool with default parameters
        tool = QueryDLQ(
            time_range_hours=24,
            include_statistics=True,
            limit=50
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful query
        self.assertIn('query_executed_at', result_data)
        self.assertEqual(result_data['entries_count'], 3)
        self.assertIn('entries', result_data)
        self.assertIn('statistics', result_data)

        # Verify statistics structure
        stats = result_data['statistics']
        self.assertEqual(stats['total_entries'], 3)
        self.assertIn('by_job_type', stats)
        self.assertIn('by_severity', stats)
        self.assertIn('by_error_type', stats)
        self.assertIn('recovery_priority_distribution', stats)
        self.assertIn('average_processing_attempts', stats)
        self.assertIn('top_error_patterns', stats)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called_with('jobs_deadletter')

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_query_with_job_type_filter(self, mock_env, mock_firestore):
        """Test DLQ query with job type filter."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Filter to only single_video entries
        filtered_entries = [entry for entry in self.sample_dlq_entries
                          if entry.to_dict()['job_type'] == 'single_video']
        self.mock_query.stream.return_value = iter(filtered_entries)

        tool = QueryDLQ(
            filter_job_type='single_video',
            time_range_hours=24,
            include_statistics=True
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert filter was applied
        self.assertEqual(result_data['filters_applied']['job_type'], 'single_video')
        self.assertEqual(result_data['entries_count'], 2)

        # Verify job type filter was called
        self.mock_query.where.assert_any_call('job_type', '==', 'single_video')

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_query_with_severity_filter(self, mock_env, mock_firestore):
        """Test DLQ query with severity filter."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Filter to only high severity entries
        filtered_entries = [entry for entry in self.sample_dlq_entries
                          if entry.to_dict()['severity'] == 'high']
        self.mock_query.stream.return_value = iter(filtered_entries)

        tool = QueryDLQ(
            filter_severity='high',
            time_range_hours=24,
            include_statistics=True
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert filter was applied
        self.assertEqual(result_data['filters_applied']['severity'], 'high')
        self.assertEqual(result_data['entries_count'], 1)

        # Verify severity filter was called
        self.mock_query.where.assert_any_call('severity', '==', 'high')

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_query_with_video_id_filter(self, mock_env, mock_firestore):
        """Test DLQ query with video ID filter."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Return all entries for video ID filtering (done post-query)
        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        tool = QueryDLQ(
            filter_video_id='vid456',
            time_range_hours=24,
            include_statistics=True
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert video ID filter was applied
        self.assertEqual(result_data['filters_applied']['video_id'], 'vid456')
        self.assertEqual(result_data['entries_count'], 1)  # Only entry3 has vid456

        # Verify the correct entry was matched
        entry = result_data['entries'][0]
        self.assertEqual(entry['video_id'], 'vid456')

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_query_with_time_range_filter(self, mock_env, mock_firestore):
        """Test DLQ query with time range filter."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        tool = QueryDLQ(
            time_range_hours=12,  # Last 12 hours
            include_statistics=False
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert time range filter was applied
        self.assertEqual(result_data['filters_applied']['time_range_hours'], 12)

        # Verify time range filter was called in Firestore query
        # The where call should have been made with a timestamp
        where_calls = self.mock_query.where.call_args_list
        time_filter_found = any(
            call[0][0] == 'dlq_created_at' and call[0][1] == '>='
            for call in where_calls
        )
        self.assertTrue(time_filter_found)

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_query_without_statistics(self, mock_env, mock_firestore):
        """Test DLQ query without statistics."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        tool = QueryDLQ(
            include_statistics=False,
            limit=10
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert no statistics included
        self.assertNotIn('statistics', result_data)
        self.assertIn('entries', result_data)
        self.assertEqual(result_data['entries_count'], 3)

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_empty_dlq_query_results(self, mock_env, mock_firestore):
        """Test DLQ query with no matching entries."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Return empty results
        self.mock_query.stream.return_value = iter([])

        tool = QueryDLQ(
            filter_job_type='nonexistent_type',
            include_statistics=True
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert empty results
        self.assertEqual(result_data['entries_count'], 0)
        self.assertEqual(len(result_data['entries']), 0)

        # Verify statistics for empty set
        stats = result_data['statistics']
        self.assertEqual(stats['total_entries'], 0)
        self.assertEqual(stats['average_processing_attempts'], 0)
        self.assertEqual(len(stats['top_error_patterns']), 0)

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_statistics_calculation_accuracy(self, mock_env, mock_firestore):
        """Test accuracy of statistics calculations."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        tool = QueryDLQ(include_statistics=True)

        result = tool.run()
        result_data = json.loads(result)

        stats = result_data['statistics']

        # Verify job type distribution
        expected_job_types = {'single_video': 2, 'channel_scrape': 1}
        self.assertEqual(stats['by_job_type'], expected_job_types)

        # Verify severity distribution
        expected_severities = {'high': 1, 'medium': 1, 'low': 1}
        self.assertEqual(stats['by_severity'], expected_severities)

        # Verify error type distribution
        expected_errors = {
            'authorization_failed': 1,
            'quota_exceeded': 1,
            'network_timeout': 1
        }
        self.assertEqual(stats['by_error_type'], expected_errors)

        # Verify average processing attempts: (3 + 2 + 1) / 3 = 2.0
        self.assertEqual(stats['average_processing_attempts'], 2.0)

        # Verify top error patterns (should be all 3 with count 1 each)
        self.assertEqual(len(stats['top_error_patterns']), 3)

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_firestore_query_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore query failures."""
        # Setup mocks to simulate query failure
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query failure
        self.mock_query.stream.side_effect = Exception("Query failed")

        tool = QueryDLQ()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Query failed', result_data['error'])
        self.assertEqual(result_data['entries'], [])

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = QueryDLQ()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    def test_invalid_filter_severity(self):
        """Test validation of invalid severity filter."""
        with self.assertRaises(Exception):
            tool = QueryDLQ(filter_severity='invalid_severity')
            tool.run()

    def test_invalid_filter_job_type(self):
        """Test validation of invalid job type filter."""
        with self.assertRaises(Exception):
            tool = QueryDLQ(filter_job_type='invalid_job_type')
            tool.run()

    def test_video_id_matching_logic(self):
        """Test video ID matching logic for different entry structures."""
        tool = QueryDLQ()

        # Test direct video_id match
        entry1 = {'video_id': 'vid123'}
        self.assertTrue(tool._matches_video_id(entry1, 'vid123'))
        self.assertFalse(tool._matches_video_id(entry1, 'vid456'))

        # Test video_ids list match
        entry2 = {'video_ids': ['vid123', 'vid456', 'vid789']}
        self.assertTrue(tool._matches_video_id(entry2, 'vid456'))
        self.assertFalse(tool._matches_video_id(entry2, 'vid999'))

        # Test original_inputs video_id match
        entry3 = {
            'failure_context': {
                'original_inputs': {'video_id': 'vid123'}
            }
        }
        self.assertTrue(tool._matches_video_id(entry3, 'vid123'))

        # Test original_inputs video_ids list match
        entry4 = {
            'failure_context': {
                'original_inputs': {'video_ids': ['vid123', 'vid456']}
            }
        }
        self.assertTrue(tool._matches_video_id(entry4, 'vid123'))

        # Test no match
        entry5 = {'some_other_field': 'value'}
        self.assertFalse(tool._matches_video_id(entry5, 'vid123'))

    def test_parameter_validation(self):
        """Test parameter validation and limits."""
        # Test valid parameters
        tool = QueryDLQ(
            filter_severity='high',
            time_range_hours=48,
            limit=100
        )
        self.assertEqual(tool.filter_severity, 'high')
        self.assertEqual(tool.time_range_hours, 48)
        self.assertEqual(tool.limit, 100)

        # Test default values
        tool_defaults = QueryDLQ()
        self.assertIsNone(tool_defaults.filter_job_type)
        self.assertIsNone(tool_defaults.filter_video_id)
        self.assertIsNone(tool_defaults.filter_severity)
        self.assertEqual(tool_defaults.time_range_hours, 24)
        self.assertTrue(tool_defaults.include_statistics)
        self.assertEqual(tool_defaults.limit, 50)

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_limit_enforcement(self, mock_env, mock_firestore):
        """Test that query limit is properly enforced."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_dlq_entries)

        tool = QueryDLQ(limit=2)

        result = tool.run()
        result_data = json.loads(result)

        # Verify limit was applied in Firestore query
        self.mock_query.limit.assert_called_with(2)

    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_timestamp_conversion(self, mock_env, mock_firestore):
        """Test that Firestore timestamps are converted to ISO strings."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create entry with timestamp
        timestamp = datetime.now(timezone.utc)
        mock_entry = self._create_mock_doc('timestamp_test', {
            'job_type': 'single_video',
            'dlq_created_at': timestamp
        })

        self.mock_query.stream.return_value = iter([mock_entry])

        tool = QueryDLQ(include_statistics=False)

        result = tool.run()
        result_data = json.loads(result)

        # Verify timestamp was converted to ISO string
        entry = result_data['entries'][0]
        self.assertEqual(entry['dlq_created_at'], timestamp.isoformat())

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = QueryDLQ(
            filter_job_type='single_video',
            filter_video_id='vid123',
            filter_severity='high'
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, QueryDLQ)

        # Test parameter values
        self.assertEqual(tool.filter_job_type, 'single_video')
        self.assertEqual(tool.filter_video_id, 'vid123')
        self.assertEqual(tool.filter_severity, 'high')


if __name__ == '__main__':
    unittest.main()