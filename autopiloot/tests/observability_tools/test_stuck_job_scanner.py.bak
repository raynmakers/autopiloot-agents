"""
Tests for observability_agent.tools.stuck_job_scanner module.

This module tests the StuckJobScanner tool which detects and reports
jobs that are stuck in processing states across all agent collections.
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

from observability_agent.tools.stuck_job_scanner import StuckJobScanner


class TestStuckJobScanner(unittest.TestCase):
    """Test cases for StuckJobScanner observability tool."""

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

        # Sample stuck jobs for testing
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        very_old_time = datetime.now(timezone.utc) - timedelta(hours=25)

        self.sample_stuck_jobs = [
            self._create_mock_doc('stuck_scraper_1', {
                'job_type': 'channel_scrape',
                'status': 'in_progress',
                'created_at': very_old_time,
                'updated_at': old_time,
                'agent': 'scraper',
                'inputs': {'channels': ['@TestChannel']}
            }),
            self._create_mock_doc('stuck_transcriber_1', {
                'job_type': 'single_video',
                'status': 'queued',
                'created_at': old_time,
                'updated_at': old_time,
                'agent': 'transcriber',
                'inputs': {'video_id': 'vid123'}
            }),
            self._create_mock_doc('stuck_summarizer_1', {
                'job_type': 'batch_summarize',
                'status': 'processing',
                'created_at': very_old_time,
                'updated_at': very_old_time,
                'agent': 'summarizer',
                'inputs': {'video_ids': ['vid1', 'vid2']}
            })
        ]

    def _create_mock_doc(self, doc_id, data):
        """Create a mock Firestore document."""
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.to_dict.return_value = data
        return mock_doc

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    @patch('observability_agent.tools.stuck_job_scanner.audit_logger')
    def test_successful_stuck_job_detection(self, mock_audit, mock_env, mock_firestore):
        """Test successful detection of stuck jobs across agents."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock stuck jobs found in different collections
        def mock_query_stream(*args, **kwargs):
            if 'scraper' in str(args) or any('scraper' in str(arg) for arg in args):
                return iter([self.sample_stuck_jobs[0]])  # scraper job
            elif 'transcriber' in str(args) or any('transcriber' in str(arg) for arg in args):
                return iter([self.sample_stuck_jobs[1]])  # transcriber job
            elif 'summarizer' in str(args) or any('summarizer' in str(arg) for arg in args):
                return iter([self.sample_stuck_jobs[2]])  # summarizer job
            return iter([])

        self.mock_query.stream.side_effect = mock_query_stream

        # Create tool with default parameters
        tool = StuckJobScanner()

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful detection
        self.assertIn('scan_timestamp', result_data)
        self.assertIn('stuck_jobs_found', result_data)
        self.assertIn('agent_summary', result_data)
        self.assertIn('recommendations', result_data)

        # Should find stuck jobs
        self.assertGreater(result_data['stuck_jobs_found'], 0)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called()
        mock_audit.log_action.assert_called()

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_stuck_job_age_thresholds(self, mock_env, mock_firestore):
        """Test detection based on different age thresholds."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create jobs with different ages
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)

        jobs_by_age = [
            self._create_mock_doc('recent_job', {
                'job_type': 'single_video',
                'status': 'in_progress',
                'created_at': recent_time,
                'updated_at': recent_time,
                'agent': 'transcriber'
            }),
            self._create_mock_doc('old_job', {
                'job_type': 'channel_scrape',
                'status': 'in_progress',
                'created_at': old_time,
                'updated_at': old_time,
                'agent': 'scraper'
            })
        ]

        self.mock_query.stream.return_value = iter(jobs_by_age)

        # Test with 2-hour threshold (should find only old job)
        tool_2h = StuckJobScanner(stuck_threshold_hours=2)
        result = tool_2h.run()
        result_data = json.loads(result)

        # Should find only the 3-hour old job
        self.assertEqual(result_data['stuck_jobs_found'], 1)

        # Test with 24-hour threshold (should find both jobs)
        tool_24h = StuckJobScanner(stuck_threshold_hours=24)
        result = tool_24h.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['stuck_jobs_found'], 2)

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_agent_specific_scanning(self, mock_env, mock_firestore):
        """Test scanning specific agents vs all agents."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        scraper_jobs = [self.sample_stuck_jobs[0]]  # Only scraper job
        self.mock_query.stream.return_value = iter(scraper_jobs)

        # Test scanning only scraper agent
        tool_scraper = StuckJobScanner(target_agents=['scraper'])
        result = tool_scraper.run()
        result_data = json.loads(result)

        # Should only scan scraper agent
        agent_summary = result_data['agent_summary']
        self.assertIn('scraper', agent_summary)
        self.assertEqual(len(agent_summary), 1)

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_stuck_job_status_filtering(self, mock_env, mock_firestore):
        """Test filtering by job status (in_progress, queued, processing)."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create jobs with different statuses
        old_time = datetime.now(timezone.utc) - timedelta(hours=3)
        status_jobs = [
            self._create_mock_doc('queued_job', {
                'job_type': 'single_video',
                'status': 'queued',
                'created_at': old_time,
                'agent': 'transcriber'
            }),
            self._create_mock_doc('processing_job', {
                'job_type': 'channel_scrape',
                'status': 'in_progress',
                'created_at': old_time,
                'agent': 'scraper'
            }),
            self._create_mock_doc('completed_job', {
                'job_type': 'batch_summarize',
                'status': 'completed',
                'created_at': old_time,
                'agent': 'summarizer'
            })
        ]

        self.mock_query.stream.return_value = iter(status_jobs)

        tool = StuckJobScanner()
        result = tool.run()
        result_data = json.loads(result)

        # Should find only non-completed jobs (queued and in_progress)
        # Completed jobs should be filtered out as they're not stuck
        stuck_jobs = result_data['stuck_job_details']
        statuses = [job['status'] for job in stuck_jobs]
        self.assertNotIn('completed', statuses)

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_no_stuck_jobs_found(self, mock_env, mock_firestore):
        """Test behavior when no stuck jobs are found."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock empty results
        self.mock_query.stream.return_value = iter([])

        tool = StuckJobScanner()

        result = tool.run()
        result_data = json.loads(result)

        # Should handle gracefully
        self.assertEqual(result_data['stuck_jobs_found'], 0)
        self.assertEqual(len(result_data['stuck_job_details']), 0)

        # Should have positive recommendations
        recommendations = result_data['recommendations']
        self.assertGreater(len(recommendations), 0)
        healthy_rec = next((rec for rec in recommendations
                           if 'healthy' in rec['description'].lower()), None)
        self.assertIsNotNone(healthy_rec)

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_critical_stuck_job_detection(self, mock_env, mock_firestore):
        """Test detection of critically stuck jobs (very old)."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create very old stuck job
        very_old_time = datetime.now(timezone.utc) - timedelta(days=2)
        critical_job = self._create_mock_doc('critical_stuck', {
            'job_type': 'channel_scrape',
            'status': 'in_progress',
            'created_at': very_old_time,
            'updated_at': very_old_time,
            'agent': 'scraper',
            'retry_count': 5
        })

        self.mock_query.stream.return_value = iter([critical_job])

        tool = StuckJobScanner(stuck_threshold_hours=1)  # Low threshold

        result = tool.run()
        result_data = json.loads(result)

        # Should classify as critical
        stuck_job = result_data['stuck_job_details'][0]
        self.assertEqual(stuck_job['severity'], 'critical')
        self.assertGreater(stuck_job['hours_stuck'], 24)

        # Should have urgent recommendations
        recommendations = result_data['recommendations']
        urgent_recs = [rec for rec in recommendations if rec.get('priority') == 'urgent']
        self.assertGreater(len(urgent_recs), 0)

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_stuck_job_remediation_hints(self, mock_env, mock_firestore):
        """Test generation of remediation hints for stuck jobs."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create stuck job with specific characteristics
        stuck_with_retries = self._create_mock_doc('retry_stuck', {
            'job_type': 'single_video',
            'status': 'in_progress',
            'created_at': datetime.now(timezone.utc) - timedelta(hours=5),
            'updated_at': datetime.now(timezone.utc) - timedelta(hours=3),
            'agent': 'transcriber',
            'retry_count': 3,
            'last_error': 'API timeout'
        })

        self.mock_query.stream.return_value = iter([stuck_with_retries])

        tool = StuckJobScanner(include_remediation_hints=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include remediation hints
        stuck_job = result_data['stuck_job_details'][0]
        self.assertIn('remediation_hints', stuck_job)

        remediation = stuck_job['remediation_hints']
        self.assertIn('suggested_actions', remediation)
        self.assertIn('investigation_steps', remediation)

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_firestore_query_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore query failures."""
        # Setup mocks to simulate query failure
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query failure
        self.mock_query.stream.side_effect = Exception("Query failed")

        tool = StuckJobScanner()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Query failed', result_data['error'])

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = StuckJobScanner()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    def test_tool_parameter_validation(self):
        """Test parameter validation and defaults."""
        # Test valid parameters
        tool = StuckJobScanner(
            stuck_threshold_hours=6,
            target_agents=['scraper', 'transcriber'],
            include_remediation_hints=False
        )
        self.assertEqual(tool.stuck_threshold_hours, 6)
        self.assertEqual(tool.target_agents, ['scraper', 'transcriber'])
        self.assertFalse(tool.include_remediation_hints)

        # Test defaults
        tool_defaults = StuckJobScanner()
        self.assertEqual(tool_defaults.stuck_threshold_hours, 2)
        self.assertIsNone(tool_defaults.target_agents)  # Scan all agents
        self.assertTrue(tool_defaults.include_remediation_hints)

    def test_severity_classification(self):
        """Test classification of stuck job severity based on age."""
        tool = StuckJobScanner()

        # Test different ages and expected severity
        test_cases = [
            (1.5, 'medium'),    # 1.5 hours -> medium
            (6, 'high'),        # 6 hours -> high
            (25, 'critical'),   # 25 hours -> critical
        ]

        for hours_stuck, expected_severity in test_cases:
            with self.subTest(hours=hours_stuck):
                severity = tool._classify_severity(hours_stuck)
                self.assertEqual(severity, expected_severity)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = StuckJobScanner(
            stuck_threshold_hours=4,
            target_agents=['scraper']
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, StuckJobScanner)

        # Test parameter values
        self.assertEqual(tool.stuck_threshold_hours, 4)
        self.assertEqual(tool.target_agents, ['scraper'])

    @patch('observability_agent.tools.stuck_job_scanner.firestore.Client')
    @patch('observability_agent.tools.stuck_job_scanner.get_required_env_var')
    def test_agent_summary_statistics(self, mock_env, mock_firestore):
        """Test generation of per-agent summary statistics."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock mixed results for different agents
        def mock_query_by_agent(*args, **kwargs):
            # Simulate different stuck job counts per agent
            query_str = str(args)
            if 'scraper' in query_str:
                return iter(self.sample_stuck_jobs[:1])  # 1 scraper job
            elif 'transcriber' in query_str:
                return iter(self.sample_stuck_jobs[1:2])  # 1 transcriber job
            elif 'summarizer' in query_str:
                return iter(self.sample_stuck_jobs[2:])  # 1 summarizer job
            return iter([])

        self.mock_query.stream.side_effect = mock_query_by_agent

        tool = StuckJobScanner()
        result = tool.run()
        result_data = json.loads(result)

        # Verify agent summary
        agent_summary = result_data['agent_summary']
        self.assertIn('scraper', agent_summary)
        self.assertIn('transcriber', agent_summary)
        self.assertIn('summarizer', agent_summary)

        # Each agent should have stuck job counts
        for agent_name, agent_data in agent_summary.items():
            self.assertIn('stuck_jobs_count', agent_data)
            self.assertIn('severity_breakdown', agent_data)


if __name__ == '__main__':
    unittest.main()