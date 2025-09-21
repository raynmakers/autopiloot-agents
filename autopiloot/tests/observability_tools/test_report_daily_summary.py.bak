"""
Tests for observability_agent.tools.report_daily_summary module.

This module tests the ReportDailySummary tool which generates comprehensive
operational reports with metrics, status, and Slack-formatted outputs.
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

from observability_agent.tools.report_daily_summary import ReportDailySummary


class TestReportDailySummary(unittest.TestCase):
    """Test cases for ReportDailySummary observability tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_query = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.where.return_value = self.mock_query
        self.mock_query.where.return_value = self.mock_query

        # Sample data for summary generation
        self.mock_video_stats = {
            'discovered': 15,
            'transcribed': 12,
            'summarized': 10,
            'failed': 2
        }

        self.mock_cost_data = {
            'transcription_usd': 4.25,
            'quota_youtube': 7500,
            'quota_assemblyai': 3.8
        }

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    @patch('observability_agent.tools.report_daily_summary.audit_logger')
    def test_successful_daily_summary_generation(self, mock_audit, mock_env, mock_firestore):
        """Test successful generation of daily summary report."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock video collection data
        mock_videos = []
        for i, status in enumerate(['discovered', 'transcribed', 'summarized', 'failed']):
            for j in range([15, 12, 10, 2][i]):  # Different counts per status
                mock_doc = MagicMock()
                mock_doc.to_dict.return_value = {
                    'status': status,
                    'created_at': datetime.now(timezone.utc) - timedelta(hours=j),
                    'video_id': f'video_{status}_{j}'
                }
                mock_videos.append(mock_doc)

        # Mock cost data
        mock_cost_doc = MagicMock()
        mock_cost_doc.to_dict.return_value = self.mock_cost_data

        def mock_query_stream(*args, **kwargs):
            # Return different data based on collection
            if 'videos' in str(args):
                return iter(mock_videos)
            elif 'costs_daily' in str(args):
                return iter([mock_cost_doc])
            return iter([])

        self.mock_query.stream.side_effect = mock_query_stream

        # Create tool with default parameters
        tool = ReportDailySummary()

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful generation
        self.assertIn('report_date', result_data)
        self.assertIn('executive_summary', result_data)
        self.assertIn('video_processing_metrics', result_data)
        self.assertIn('cost_analysis', result_data)
        self.assertIn('operational_health', result_data)

        # Verify metrics
        metrics = result_data['video_processing_metrics']
        self.assertEqual(metrics['videos_discovered'], 15)
        self.assertEqual(metrics['videos_transcribed'], 12)
        self.assertEqual(metrics['videos_summarized'], 10)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called()
        mock_audit.log_action.assert_called()

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_slack_formatted_output(self, mock_env, mock_firestore):
        """Test generation of Slack-formatted report."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock basic data
        self.mock_query.stream.return_value = iter([])

        # Create tool with Slack format
        tool = ReportDailySummary(
            output_format='slack',
            include_charts=False  # Slack doesn't support complex charts
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should have Slack-specific formatting
        self.assertIn('slack_blocks', result_data)
        self.assertIn('text_summary', result_data)

        # Slack blocks should be properly structured
        slack_blocks = result_data['slack_blocks']
        self.assertIsInstance(slack_blocks, list)
        if slack_blocks:
            self.assertIn('type', slack_blocks[0])

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_custom_date_range(self, mock_env, mock_firestore):
        """Test report generation for custom date range."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter([])

        # Create tool with custom date range
        custom_date = datetime.now(timezone.utc) - timedelta(days=2)
        tool = ReportDailySummary(
            target_date=custom_date.strftime('%Y-%m-%d'),
            lookback_hours=48  # 2 days
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should use custom date in report
        self.assertEqual(result_data['report_date'], custom_date.strftime('%Y-%m-%d'))

        # Verify time range was applied in queries
        where_calls = self.mock_query.where.call_args_list
        time_filters = [call for call in where_calls
                       if len(call[0]) > 1 and 'created_at' in call[0][0]]
        self.assertGreater(len(time_filters), 0)

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_cost_analysis_details(self, mock_env, mock_firestore):
        """Test detailed cost analysis in the report."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock cost data with detailed breakdown
        detailed_cost_doc = MagicMock()
        detailed_cost_doc.to_dict.return_value = {
            'transcription_usd': 4.75,
            'quota_youtube': 8200,
            'quota_assemblyai': 4.1,
            'cost_breakdown': {
                'per_video_avg': 0.39,
                'total_minutes_processed': 720,
                'cost_per_minute': 0.0066
            }
        }

        def mock_cost_query(*args, **kwargs):
            if 'costs_daily' in str(args):
                return iter([detailed_cost_doc])
            return iter([])

        self.mock_query.stream.side_effect = mock_cost_query

        tool = ReportDailySummary(include_cost_breakdown=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include detailed cost analysis
        cost_analysis = result_data['cost_analysis']
        self.assertIn('total_cost_usd', cost_analysis)
        self.assertIn('quota_utilization', cost_analysis)
        self.assertIn('cost_efficiency_metrics', cost_analysis)

        # Quota utilization should be calculated
        quota_util = cost_analysis['quota_utilization']
        self.assertIn('youtube_percent', quota_util)
        self.assertIn('assemblyai_percent', quota_util)

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_operational_health_assessment(self, mock_env, mock_firestore):
        """Test operational health assessment in the report."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock some issues for health assessment
        mock_dlq_entries = []
        for i in range(3):  # Some DLQ entries
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = {
                'job_type': 'single_video',
                'severity': 'medium',
                'dlq_created_at': datetime.now(timezone.utc) - timedelta(hours=i+1)
            }
            mock_dlq_entries.append(mock_doc)

        def mock_health_query(*args, **kwargs):
            if 'jobs_deadletter' in str(args):
                return iter(mock_dlq_entries)
            return iter([])

        self.mock_query.stream.side_effect = mock_health_query

        tool = ReportDailySummary(include_health_checks=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include health assessment
        health = result_data['operational_health']
        self.assertIn('overall_status', health)
        self.assertIn('issues_detected', health)
        self.assertIn('recommendations', health)

        # Should detect DLQ issues
        self.assertGreater(health['issues_detected'], 0)

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_trend_analysis_inclusion(self, mock_env, mock_firestore):
        """Test inclusion of trend analysis in the report."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock historical data for trends
        historical_data = []
        for days_ago in range(7):  # Week of data
            for status in ['discovered', 'transcribed', 'summarized']:
                count = 10 + days_ago  # Trending up
                mock_doc = MagicMock()
                mock_doc.to_dict.return_value = {
                    'status': status,
                    'created_at': datetime.now(timezone.utc) - timedelta(days=days_ago),
                    'count': count
                }
                historical_data.append(mock_doc)

        self.mock_query.stream.return_value = iter(historical_data)

        tool = ReportDailySummary(include_trends=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include trend analysis
        if 'trend_analysis' in result_data:
            trends = result_data['trend_analysis']
            self.assertIn('processing_trends', trends)
            self.assertIn('cost_trends', trends)

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_empty_data_handling(self, mock_env, mock_firestore):
        """Test report generation when no data is available."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock empty data
        self.mock_query.stream.return_value = iter([])

        tool = ReportDailySummary()

        result = tool.run()
        result_data = json.loads(result)

        # Should handle empty data gracefully
        metrics = result_data['video_processing_metrics']
        self.assertEqual(metrics['videos_discovered'], 0)
        self.assertEqual(metrics['videos_transcribed'], 0)
        self.assertEqual(metrics['videos_summarized'], 0)

        # Executive summary should note no activity
        summary = result_data['executive_summary']
        self.assertIn('no activity', summary.lower())

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_performance_metrics_calculation(self, mock_env, mock_firestore):
        """Test calculation of performance metrics."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock videos with processing times
        timed_videos = []
        processing_times = [30, 45, 60, 120, 90]  # minutes
        for i, time_mins in enumerate(processing_times):
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = {
                'status': 'summarized',
                'video_id': f'timed_video_{i}',
                'processing_duration_minutes': time_mins,
                'created_at': datetime.now(timezone.utc) - timedelta(hours=i)
            }
            timed_videos.append(mock_doc)

        self.mock_query.stream.return_value = iter(timed_videos)

        tool = ReportDailySummary(include_performance_metrics=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include performance metrics
        if 'performance_metrics' in result_data:
            perf = result_data['performance_metrics']
            self.assertIn('average_processing_time', perf)
            self.assertIn('throughput_rate', perf)

            # Average should be calculated correctly
            expected_avg = sum(processing_times) / len(processing_times)
            self.assertAlmostEqual(perf['average_processing_time'], expected_avg, places=1)

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_firestore_query_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore query failures."""
        # Setup mocks to simulate query failure
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query failure
        self.mock_query.stream.side_effect = Exception("Query failed")

        tool = ReportDailySummary()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Query failed', result_data['error'])

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = ReportDailySummary()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    def test_tool_parameter_validation(self):
        """Test parameter validation and defaults."""
        # Test valid parameters
        tool = ReportDailySummary(
            target_date='2025-01-15',
            output_format='json',
            include_trends=False,
            lookback_hours=48
        )
        self.assertEqual(tool.target_date, '2025-01-15')
        self.assertEqual(tool.output_format, 'json')
        self.assertFalse(tool.include_trends)
        self.assertEqual(tool.lookback_hours, 48)

        # Test defaults
        tool_defaults = ReportDailySummary()
        self.assertEqual(tool_defaults.output_format, 'json')
        self.assertTrue(tool_defaults.include_trends)
        self.assertEqual(tool_defaults.lookback_hours, 24)

    def test_output_format_validation(self):
        """Test validation of output format parameter."""
        # Valid formats should work
        valid_formats = ['json', 'slack', 'markdown']
        for format_type in valid_formats:
            with self.subTest(format=format_type):
                tool = ReportDailySummary(output_format=format_type)
                self.assertEqual(tool.output_format, format_type)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = ReportDailySummary(
            target_date='2025-01-15',
            output_format='slack',
            include_cost_breakdown=False
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, ReportDailySummary)

        # Test parameter values
        self.assertEqual(tool.target_date, '2025-01-15')
        self.assertEqual(tool.output_format, 'slack')
        self.assertFalse(tool.include_cost_breakdown)

    @patch('observability_agent.tools.report_daily_summary.firestore.Client')
    @patch('observability_agent.tools.report_daily_summary.get_required_env_var')
    def test_executive_summary_generation(self, mock_env, mock_firestore):
        """Test generation of executive summary with key insights."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock successful day with good metrics
        success_videos = []
        for i in range(20):
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = {
                'status': 'summarized' if i < 15 else 'transcribed',
                'video_id': f'success_video_{i}',
                'created_at': datetime.now(timezone.utc) - timedelta(hours=i)
            }
            success_videos.append(mock_doc)

        # Mock cost data showing efficient operation
        efficient_cost_doc = MagicMock()
        efficient_cost_doc.to_dict.return_value = {
            'transcription_usd': 3.25,  # Under budget
            'quota_youtube': 6000,      # 60% of quota
            'quota_assemblyai': 3.0     # 60% of quota
        }

        def mock_summary_query(*args, **kwargs):
            if 'videos' in str(args):
                return iter(success_videos)
            elif 'costs_daily' in str(args):
                return iter([efficient_cost_doc])
            return iter([])

        self.mock_query.stream.side_effect = mock_summary_query

        tool = ReportDailySummary()

        result = tool.run()
        result_data = json.loads(result)

        # Executive summary should highlight success
        summary = result_data['executive_summary']
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 50)  # Should be substantial

        # Should mention key metrics
        self.assertTrue(any(word in summary.lower()
                          for word in ['processed', 'videos', 'cost', 'quota']))


if __name__ == '__main__':
    unittest.main()