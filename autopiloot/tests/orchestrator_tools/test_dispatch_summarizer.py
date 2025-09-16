"""
Tests for orchestrator_agent.tools.dispatch_summarizer module.

This module tests the DispatchSummarizer tool which coordinates summarization
operations with SummarizerAgent.
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

from orchestrator_agent.tools.dispatch_summarizer import DispatchSummarizer


class TestDispatchSummarizer(unittest.TestCase):
    """Test cases for DispatchSummarizer orchestrator tool."""

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

    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_summarizer.audit_logger')
    def test_successful_summarization_dispatch(self, mock_audit, mock_env, mock_firestore):
        """Test successful dispatch of summarization jobs."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock transcripts ready for summarization
        mock_transcripts = [
            MagicMock(id='transcript1', to_dict=lambda: {'video_id': 'video1', 'status': 'completed'}),
            MagicMock(id='transcript2', to_dict=lambda: {'video_id': 'video2', 'status': 'completed'})
        ]
        self.mock_query.stream.return_value = iter(mock_transcripts)

        # Create tool
        tool = DispatchSummarizer()

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'summarizer-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful dispatch
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('jobs_dispatched', result_data)
        self.assertIn('transcripts_found', result_data)

        # Verify operations
        mock_audit.log_action.assert_called()

    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    def test_no_transcripts_ready(self, mock_env, mock_firestore):
        """Test behavior when no transcripts are ready for summarization."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock empty transcript list
        self.mock_query.stream.return_value = iter([])

        tool = DispatchSummarizer()

        result = tool.run()
        result_data = json.loads(result)

        # Should succeed but with no jobs dispatched
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['transcripts_found'], 0)
        self.assertEqual(result_data['jobs_dispatched'], 0)

    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    def test_with_video_filter(self, mock_env, mock_firestore):
        """Test summarization dispatch with specific video filter."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with video filter
        tool = DispatchSummarizer(
            video_ids=['video1', 'video2']
        )

        # Mock filtered transcripts
        mock_transcripts = [
            MagicMock(id='transcript1', to_dict=lambda: {'video_id': 'video1'})
        ]
        self.mock_query.stream.return_value = iter(mock_transcripts)

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'filtered-summarizer-job'

        result = tool.run()
        result_data = json.loads(result)

        # Assert filtering worked
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('video_filter', result_data)

    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    def test_with_summary_type(self, mock_env, mock_firestore):
        """Test summarization dispatch with specific summary type."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with summary type
        tool = DispatchSummarizer(
            summary_type='coaching_insights'
        )

        # Mock transcripts
        mock_transcripts = [
            MagicMock(id='transcript1', to_dict=lambda: {'video_id': 'video1'})
        ]
        self.mock_query.stream.return_value = iter(mock_transcripts)

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'coaching-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert summary type is set
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['summary_type'], 'coaching_insights')

    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    def test_error_handling(self, mock_env, mock_firestore):
        """Test error handling in summarization dispatch."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query failure
        self.mock_query.stream.side_effect = Exception("Database error")

        tool = DispatchSummarizer()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = DispatchSummarizer()

        # Test that it's a BaseTool
        self.assertIsInstance(tool, DispatchSummarizer)

        # Test default values
        self.assertIsNone(tool.video_ids)
        self.assertEqual(tool.summary_type, 'short')
        self.assertFalse(tool.force_regenerate)


if __name__ == '__main__':
    unittest.main()