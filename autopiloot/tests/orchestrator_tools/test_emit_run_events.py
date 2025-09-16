"""
Tests for orchestrator_agent.tools.emit_run_events module.

This module tests the EmitRunEvents tool which publishes operational events
to Firestore for observability and monitoring.
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

from orchestrator_agent.tools.emit_run_events import EmitRunEvents


class TestEmitRunEvents(unittest.TestCase):
    """Test cases for EmitRunEvents orchestrator tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document

    @patch('orchestrator_agent.tools.emit_run_events.firestore.Client')
    @patch('orchestrator_agent.tools.emit_run_events.get_required_env_var')
    @patch('orchestrator_agent.tools.emit_run_events.audit_logger')
    def test_successful_event_emission(self, mock_audit, mock_env, mock_firestore):
        """Test successful emission of run events."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with event data
        tool = EmitRunEvents(
            event_type='run_started',
            metadata={'timestamp': '2025-09-16T10:00:00Z', 'plan_id': 'plan123'}
        )

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'event-id-123'

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful emission
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['event_type'], 'run_started')
        self.assertIn('event_id', result_data)
        self.assertIn('timestamp', result_data)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called_with('run_events')
        self.mock_document.set.assert_called_once()
        mock_audit.log_action.assert_called()

    @patch('orchestrator_agent.tools.emit_run_events.firestore.Client')
    @patch('orchestrator_agent.tools.emit_run_events.get_required_env_var')
    def test_run_completed_event(self, mock_env, mock_firestore):
        """Test emission of run completed events."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool for completion event
        tool = EmitRunEvents(
            event_type='run_completed',
            metadata={
                'duration_sec': 120,
                'videos_processed': 5,
                'summary': 'Daily run completed successfully'
            }
        )

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'completion-event-456'

        result = tool.run()
        result_data = json.loads(result)

        # Assert completion event details
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['event_type'], 'run_completed')
        self.assertIn('duration_sec', result_data['metadata'])
        self.assertIn('videos_processed', result_data['metadata'])

    @patch('orchestrator_agent.tools.emit_run_events.firestore.Client')
    @patch('orchestrator_agent.tools.emit_run_events.get_required_env_var')
    def test_run_failed_event(self, mock_env, mock_firestore):
        """Test emission of run failure events."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool for failure event
        tool = EmitRunEvents(
            event_type='run_failed',
            metadata={
                'error': 'API quota exceeded',
                'duration_sec': 45,
                'failed_at': 'scraper_dispatch'
            }
        )

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'failure-event-789'

        result = tool.run()
        result_data = json.loads(result)

        # Assert failure event details
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['event_type'], 'run_failed')
        self.assertIn('error', result_data['metadata'])
        self.assertIn('failed_at', result_data['metadata'])

    @patch('orchestrator_agent.tools.emit_run_events.firestore.Client')
    @patch('orchestrator_agent.tools.emit_run_events.get_required_env_var')
    def test_agent_dispatched_event(self, mock_env, mock_firestore):
        """Test emission of agent dispatch events."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool for agent dispatch event
        tool = EmitRunEvents(
            event_type='agent_dispatched',
            metadata={
                'agent': 'scraper',
                'job_id': 'job-abc-123',
                'channels': ['@AlexHormozi']
            }
        )

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'dispatch-event-101'

        result = tool.run()
        result_data = json.loads(result)

        # Assert dispatch event details
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(result_data['event_type'], 'agent_dispatched')
        self.assertEqual(result_data['metadata']['agent'], 'scraper')
        self.assertIn('job_id', result_data['metadata'])

    @patch('orchestrator_agent.tools.emit_run_events.firestore.Client')
    @patch('orchestrator_agent.tools.emit_run_events.get_required_env_var')
    def test_firestore_write_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore write failures."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock write failure
        self.mock_document.set.side_effect = Exception("Write failed")

        tool = EmitRunEvents(
            event_type='run_started',
            metadata={'test': 'data'}
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)
        self.assertIn('Write failed', result_data['error'])

    @patch('orchestrator_agent.tools.emit_run_events.firestore.Client')
    @patch('orchestrator_agent.tools.emit_run_events.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = EmitRunEvents(
            event_type='run_started',
            metadata={'test': 'data'}
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    def test_empty_metadata(self):
        """Test event emission with empty metadata."""
        tool = EmitRunEvents(
            event_type='heartbeat',
            metadata={}
        )

        # Should be valid - empty metadata is allowed
        self.assertEqual(tool.event_type, 'heartbeat')
        self.assertEqual(tool.metadata, {})

    def test_large_metadata(self):
        """Test event emission with large metadata."""
        large_metadata = {
            f'key_{i}': f'value_{i}' * 100
            for i in range(50)
        }

        tool = EmitRunEvents(
            event_type='large_event',
            metadata=large_metadata
        )

        # Should be valid
        self.assertEqual(tool.event_type, 'large_event')
        self.assertEqual(len(tool.metadata), 50)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = EmitRunEvents(
            event_type='test_event',
            metadata={'test': 'data'}
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, EmitRunEvents)

        # Test required parameters
        self.assertEqual(tool.event_type, 'test_event')
        self.assertIsInstance(tool.metadata, dict)
        self.assertIn('test', tool.metadata)

    @patch('orchestrator_agent.tools.emit_run_events.firestore.Client')
    @patch('orchestrator_agent.tools.emit_run_events.get_required_env_var')
    def test_event_document_structure(self, mock_env, mock_firestore):
        """Test that event documents have the correct structure."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        tool = EmitRunEvents(
            event_type='test_structure',
            metadata={'custom': 'field'}
        )

        # Capture the document data
        captured_data = None
        def capture_set_call(*args, **kwargs):
            nonlocal captured_data
            captured_data = args[0] if args else None

        self.mock_document.set.side_effect = capture_set_call
        self.mock_document.id = 'structure-test-id'

        result = tool.run()

        # Verify document structure
        self.assertIsNotNone(captured_data)
        self.assertIn('event_type', captured_data)
        self.assertIn('metadata', captured_data)
        self.assertIn('timestamp', captured_data)
        self.assertIn('source', captured_data)

        # Verify values
        self.assertEqual(captured_data['event_type'], 'test_structure')
        self.assertEqual(captured_data['source'], 'orchestrator')
        self.assertIn('custom', captured_data['metadata'])


if __name__ == '__main__':
    unittest.main()