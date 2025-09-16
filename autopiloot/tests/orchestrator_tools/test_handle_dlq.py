"""
Tests for orchestrator_agent.tools.handle_dlq module.

This module tests the HandleDLQ tool which routes failed jobs to dead letter queue
with structured context preservation for debugging and manual recovery.
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

from orchestrator_agent.tools.handle_dlq import HandleDLQ


class TestHandleDLQ(unittest.TestCase):
    """Test cases for HandleDLQ orchestrator tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document

        # Base failure context for testing
        self.base_failure_context = {
            "error_type": "api_timeout",
            "error_message": "AssemblyAI API request timeout after 30 seconds",
            "retry_count": 3,
            "last_attempt_at": "2025-01-27T12:30:00Z",
            "original_inputs": {
                "video_id": "dQw4w9WgXcQ",
                "priority": "high"
            }
        }

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.handle_dlq.audit_logger')
    def test_successful_dlq_routing(self, mock_audit, mock_env, mock_firestore):
        """Test successful routing of failed job to DLQ."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock that DLQ entry doesn't exist yet
        self.mock_document.get.return_value.exists = False
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'single_video_test_job_123_20250127_123000'

        # Create tool
        tool = HandleDLQ(
            job_id="test_job_123",
            job_type="single_video",
            failure_context=self.base_failure_context,
            recovery_hints={
                "manual_action_required": True,
                "suggested_fix": "Check AssemblyAI API status"
            }
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful DLQ routing
        self.assertEqual(result_data['status'], 'routed_to_dlq')
        self.assertEqual(result_data['original_job_id'], 'test_job_123')
        self.assertEqual(result_data['job_type'], 'single_video')
        self.assertIn('dlq_id', result_data)
        self.assertIn('severity', result_data)
        self.assertIn('recovery_priority', result_data)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called_with('jobs_deadletter')
        self.mock_document.set.assert_called_once()

        # Verify audit logging
        mock_audit.log_job_dlq_routed.assert_called_once()

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_duplicate_dlq_entry_handling(self, mock_env, mock_firestore):
        """Test handling when DLQ entry already exists."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock that DLQ entry already exists
        self.mock_document.get.return_value.exists = True

        tool = HandleDLQ(
            job_id="existing_job",
            job_type="single_video",
            failure_context=self.base_failure_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert duplicate handling
        self.assertEqual(result_data['status'], 'already_exists')
        self.assertIn('Job already in dead letter queue', result_data['message'])

        # Verify no new document was created
        self.mock_document.set.assert_not_called()

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_high_severity_authorization_failure(self, mock_env, mock_firestore):
        """Test DLQ routing for high severity authorization failures."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        self.mock_document.get.return_value.exists = False

        # Authorization failure context
        auth_failure_context = {
            "error_type": "authorization_failed",
            "error_message": "YouTube API key invalid or quota exceeded",
            "retry_count": 0,
            "original_inputs": {
                "channels": ["@AlexHormozi"],
                "limit_per_channel": 10
            }
        }

        # Mock successful operations
        captured_payload = None
        def capture_set_call(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = args[0] if args else None

        self.mock_document.set.side_effect = capture_set_call
        self.mock_document.id = 'channel_scrape_auth_fail_123'

        tool = HandleDLQ(
            job_id="auth_fail_123",
            job_type="channel_scrape",
            failure_context=auth_failure_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert high severity assignment
        self.assertEqual(result_data['status'], 'routed_to_dlq')
        self.assertEqual(result_data['severity'], 'high')
        self.assertEqual(result_data['recovery_priority'], 'urgent')

        # Verify DLQ payload structure
        self.assertIsNotNone(captured_payload)
        self.assertEqual(captured_payload['severity'], 'high')
        self.assertEqual(captured_payload['recovery_priority'], 'urgent')
        self.assertIn('target_channels', captured_payload)

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_transcription_job_metadata(self, mock_env, mock_firestore):
        """Test DLQ routing with transcription job specific metadata."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        self.mock_document.get.return_value.exists = False

        # Transcription failure context
        transcription_context = {
            "error_type": "api_timeout",
            "error_message": "Transcription service timeout",
            "retry_count": 2,
            "original_inputs": {
                "video_id": "abc123",
                "audio_url": "https://example.com/audio.mp3"
            }
        }

        # Capture the DLQ payload
        captured_payload = None
        def capture_set_call(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = args[0] if args else None

        self.mock_document.set.side_effect = capture_set_call
        self.mock_document.id = 'transcription_dlq_id'

        tool = HandleDLQ(
            job_id="transcription_123",
            job_type="single_video",
            failure_context=transcription_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert job-specific metadata
        self.assertEqual(result_data['status'], 'routed_to_dlq')
        self.assertIsNotNone(captured_payload)
        self.assertEqual(captured_payload['video_id'], 'abc123')
        self.assertIn('estimated_cost_impact', captured_payload)

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_batch_job_metadata(self, mock_env, mock_firestore):
        """Test DLQ routing for batch jobs with multiple video IDs."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        self.mock_document.get.return_value.exists = False

        # Batch job failure context
        batch_context = {
            "error_type": "quota_exceeded",
            "error_message": "Batch processing quota exceeded",
            "retry_count": 1,
            "original_inputs": {
                "video_ids": ["vid1", "vid2", "vid3", "vid4", "vid5"],
                "summary_type": "coaching_insights"
            }
        }

        # Capture payload
        captured_payload = None
        def capture_set_call(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = args[0] if args else None

        self.mock_document.set.side_effect = capture_set_call

        tool = HandleDLQ(
            job_id="batch_123",
            job_type="batch_summarize",
            failure_context=batch_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert batch-specific metadata
        self.assertEqual(result_data['status'], 'routed_to_dlq')
        self.assertIsNotNone(captured_payload)
        self.assertEqual(captured_payload['video_ids'], ["vid1", "vid2", "vid3", "vid4", "vid5"])
        self.assertEqual(captured_payload['batch_size'], 5)
        self.assertIn('target_platforms', captured_payload)

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_medium_severity_with_high_retry_count(self, mock_env, mock_firestore):
        """Test that high retry counts result in medium severity."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        self.mock_document.get.return_value.exists = False

        # High retry count context
        high_retry_context = {
            "error_type": "network_error",  # Normally low severity
            "error_message": "Network connection failed",
            "retry_count": 6,  # >= 5 should elevate to medium
            "original_inputs": {"video_id": "test123"}
        }

        captured_payload = None
        def capture_set_call(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = args[0] if args else None

        self.mock_document.set.side_effect = capture_set_call

        tool = HandleDLQ(
            job_id="high_retry_job",
            job_type="single_video",
            failure_context=high_retry_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert medium severity due to high retry count
        self.assertEqual(result_data['severity'], 'medium')
        self.assertIsNotNone(captured_payload)
        self.assertEqual(captured_payload['severity'], 'medium')

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_active_job_cleanup(self, mock_env, mock_firestore):
        """Test cleanup of active job after DLQ routing."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        self.mock_document.get.return_value.exists = False

        # Mock active job collection
        mock_active_ref = MagicMock()
        mock_active_ref.get.return_value.exists = True
        mock_active_ref.delete = MagicMock()

        def mock_collection_path(*args):
            if args == ('jobs',):
                mock_jobs = MagicMock()
                mock_jobs.document.return_value.collection.return_value.document.return_value = mock_active_ref
                return mock_jobs
            return self.mock_collection

        self.mock_firestore_client.collection.side_effect = mock_collection_path

        tool = HandleDLQ(
            job_id="cleanup_test",
            job_type="single_video",
            failure_context=self.base_failure_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful DLQ routing
        self.assertEqual(result_data['status'], 'routed_to_dlq')

        # Verify cleanup was attempted
        mock_active_ref.delete.assert_called_once()

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_firestore_write_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore write failures."""
        # Setup mocks to simulate write failure
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'
        self.mock_document.get.return_value.exists = False

        # Mock write failure
        self.mock_document.set.side_effect = Exception("Write operation failed")

        tool = HandleDLQ(
            job_id="write_fail_test",
            job_type="single_video",
            failure_context=self.base_failure_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Write operation failed', result_data['error'])
        self.assertIsNone(result_data['dlq_ref'])

    @patch('orchestrator_agent.tools.handle_dlq.firestore.Client')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = HandleDLQ(
            job_id="connection_fail_test",
            job_type="single_video",
            failure_context=self.base_failure_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    def test_missing_required_failure_context_fields(self):
        """Test validation when required failure context fields are missing."""
        # Missing error_type
        invalid_context = {
            "error_message": "Some error occurred",
            "retry_count": 2
        }

        tool = HandleDLQ(
            job_id="invalid_test",
            job_type="single_video",
            failure_context=invalid_context
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Missing required failure_context field', result_data['error'])

    def test_invalid_failure_context_type(self):
        """Test validation when failure_context is not a dictionary."""
        tool = HandleDLQ(
            job_id="invalid_context_test",
            job_type="single_video",
            failure_context="invalid_context"  # Should be dict
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('failure_context must be a dictionary', result_data['error'])

    def test_severity_calculation_logic(self):
        """Test severity calculation for different error types."""
        tool = HandleDLQ(
            job_id="severity_test",
            job_type="single_video",
            failure_context=self.base_failure_context
        )

        # Test high severity errors
        high_severity_errors = [
            "authorization_failed",
            "data_corruption",
            "security_violation",
            "system_critical"
        ]

        for error_type in high_severity_errors:
            with self.subTest(error_type=error_type):
                tool.failure_context = {"error_type": error_type, "error_message": "test", "retry_count": 0}
                severity = tool._calculate_severity()
                self.assertEqual(severity, "high")

        # Test medium severity errors
        medium_severity_errors = [
            "quota_exceeded",
            "budget_exceeded",
            "invalid_configuration",
            "dependency_failure"
        ]

        for error_type in medium_severity_errors:
            with self.subTest(error_type=error_type):
                tool.failure_context = {"error_type": error_type, "error_message": "test", "retry_count": 0}
                severity = tool._calculate_severity()
                self.assertEqual(severity, "medium")

        # Test low severity (default)
        tool.failure_context = {"error_type": "network_timeout", "error_message": "test", "retry_count": 1}
        severity = tool._calculate_severity()
        self.assertEqual(severity, "low")

    def test_recovery_priority_calculation(self):
        """Test recovery priority calculation logic."""
        # High severity + realtime job = urgent
        tool = HandleDLQ(
            job_id="priority_test",
            job_type="single_video",  # realtime job
            failure_context={
                "error_type": "authorization_failed",  # high severity
                "error_message": "test",
                "retry_count": 0
            }
        )

        priority = tool._calculate_recovery_priority()
        self.assertEqual(priority, "urgent")

        # Medium severity + realtime job = high
        tool.failure_context = {
            "error_type": "quota_exceeded",  # medium severity
            "error_message": "test",
            "retry_count": 0
        }

        priority = tool._calculate_recovery_priority()
        self.assertEqual(priority, "high")

        # Low severity + batch job = low
        tool.job_type = "batch_summarize"  # not realtime
        tool.failure_context = {
            "error_type": "network_timeout",  # low severity
            "error_message": "test",
            "retry_count": 1
        }

        priority = tool._calculate_recovery_priority()
        self.assertEqual(priority, "low")

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = HandleDLQ(
            job_id="test_job",
            job_type="single_video",
            failure_context=self.base_failure_context
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, HandleDLQ)

        # Test required parameters
        self.assertEqual(tool.job_id, "test_job")
        self.assertEqual(tool.job_type, "single_video")
        self.assertIsInstance(tool.failure_context, dict)

        # Test optional parameters
        self.assertIsNone(tool.recovery_hints)


if __name__ == '__main__':
    unittest.main()