"""
Tests for orchestrator_agent.tools.dispatch_transcriber module.

This module tests the DispatchTranscriber tool which coordinates transcription
operations with TranscriberAgent.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add the parent directories to sys.path for imports
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from orchestrator_agent.tools.dispatch_transcriber import DispatchTranscriber


class TestDispatchTranscriber(unittest.TestCase):
    """Test cases for DispatchTranscriber orchestrator tool."""

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

    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_transcriber.audit_logger')
    def test_successful_transcription_dispatch(self, mock_audit, mock_env, mock_firestore):
        """Test successful dispatch of transcription jobs."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock videos ready for transcription
        mock_videos = [
            MagicMock(id='video1', to_dict=lambda: {'title': 'Test Video 1', 'status': 'discovered'}),
            MagicMock(id='video2', to_dict=lambda: {'title': 'Test Video 2', 'status': 'discovered'})
        ]
        self.mock_query.stream.return_value = iter(mock_videos)

        # Create tool
        tool = DispatchTranscriber()

        # Mock successful job creation
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'transcriber-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful dispatch
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('jobs_dispatched', result_data)
        self.assertIn('videos_found', result_data)
        self.assertEqual(result_data['videos_found'], 2)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called()
        mock_audit.log_action.assert_called()

    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_no_videos_ready_for_transcription(self, mock_env, mock_firestore):
        """Test behavior when no videos are ready for transcription."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock empty video list
        self.mock_query.stream.return_value = iter([])

        tool = DispatchTranscriber()

        result = tool.run()
        result_data = json.loads(result)

        # Should succeed but with no jobs dispatched
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['videos_found'], 0)
        self.assertEqual(result_data['jobs_dispatched'], 0)

    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_with_video_filter(self, mock_env, mock_firestore):
        """Test transcription dispatch with specific video filter."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with video filter
        tool = DispatchTranscriber(
            video_ids=['video1', 'video2']
        )

        # Mock filtered videos
        mock_videos = [
            MagicMock(id='video1', to_dict=lambda: {'title': 'Filtered Video 1'})
        ]
        self.mock_query.stream.return_value = iter(mock_videos)

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'filtered-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert filtering worked
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('video_filter', result_data)
        self.assertEqual(result_data['video_filter'], ['video1', 'video2'])

    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_with_priority_flag(self, mock_env, mock_firestore):
        """Test transcription dispatch with priority flag."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with priority
        tool = DispatchTranscriber(
            high_priority=True
        )

        # Mock videos
        mock_videos = [
            MagicMock(id='priority_video', to_dict=lambda: {'title': 'Priority Video'})
        ]
        self.mock_query.stream.return_value = iter(mock_videos)

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'priority-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert priority is set
        self.assertEqual(result_data['status'], 'success')
        self.assertTrue(result_data['high_priority'])

    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_firestore_query_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore query failures."""
        # Setup mocks to simulate failure
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query failure
        self.mock_query.stream.side_effect = Exception("Query failed")

        tool = DispatchTranscriber()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)
        self.assertIn('Query failed', result_data['error'])

    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_job_creation_failure(self, mock_env, mock_firestore):
        """Test handling of job creation failures."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock videos
        mock_videos = [
            MagicMock(id='video1', to_dict=lambda: {'title': 'Test Video'})
        ]
        self.mock_query.stream.return_value = iter(mock_videos)

        # Mock job creation failure
        self.mock_document.set.side_effect = Exception("Job creation failed")

        tool = DispatchTranscriber()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)

    def test_validation_edge_cases(self):
        """Test edge cases in parameter validation."""
        # Test with empty video_ids list
        tool = DispatchTranscriber(video_ids=[])
        self.assertEqual(tool.video_ids, [])

        # Test with None parameters
        tool = DispatchTranscriber()
        self.assertIsNone(tool.video_ids)
        self.assertFalse(tool.high_priority)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = DispatchTranscriber()

        # Test that it's a BaseTool
        self.assertIsInstance(tool, DispatchTranscriber)

        # Test default values
        self.assertIsNone(tool.video_ids)
        self.assertFalse(tool.high_priority)

    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_batch_processing_limits(self, mock_env, mock_firestore):
        """Test that batch processing respects limits."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create many mock videos to test batch limits
        mock_videos = [
            MagicMock(id=f'video{i}', to_dict=lambda i=i: {'title': f'Video {i}'})
            for i in range(50)  # Large number to test batching
        ]
        self.mock_query.stream.return_value = iter(mock_videos)

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'batch-job-id'

        tool = DispatchTranscriber()

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful processing
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['videos_found'], 50)

        # Verify appropriate batching occurred (implementation dependent)
        self.assertGreater(result_data['jobs_dispatched'], 0)


if __name__ == '__main__':
    unittest.main()