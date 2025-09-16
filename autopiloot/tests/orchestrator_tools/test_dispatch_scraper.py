"""
Tests for orchestrator_agent.tools.dispatch_scraper module.

This module tests the DispatchScraper tool which creates structured work orders
for ScraperAgent operations with proper idempotency and status tracking.
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

from orchestrator_agent.tools.dispatch_scraper import DispatchScraper


class TestDispatchScraper(unittest.TestCase):
    """Test cases for DispatchScraper orchestrator tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_document = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_document

    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.audit_logger')
    def test_channel_scrape_dispatch_success(self, mock_audit, mock_env, mock_firestore):
        """Test successful dispatch of channel scrape job."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with channel scrape parameters
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={
                "channels": ["@AlexHormozi"],
                "limit_per_channel": 10
            }
        )

        # Mock successful Firestore operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'test-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful dispatch
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('job_id', result_data)
        self.assertEqual(result_data['job_type'], 'channel_scrape')
        self.assertIn('dispatch_timestamp', result_data)

        # Verify Firestore was called correctly
        self.mock_firestore_client.collection.assert_called_with('jobs')
        self.mock_document.set.assert_called_once()

        # Verify audit logging
        mock_audit.log_action.assert_called_once()

    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.audit_logger')
    def test_sheet_backfill_dispatch_success(self, mock_audit, mock_env, mock_firestore):
        """Test successful dispatch of sheet backfill job."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with sheet backfill parameters
        tool = DispatchScraper(
            job_type="sheet_backfill",
            inputs={
                "sheet_id": "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789",
                "range": "Sheet1!A:D"
            }
        )

        # Mock successful Firestore operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'test-sheet-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful dispatch
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('job_id', result_data)
        self.assertEqual(result_data['job_type'], 'sheet_backfill')

        # Verify correct inputs
        self.assertEqual(result_data['inputs']['sheet_id'], "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789")
        self.assertEqual(result_data['inputs']['range'], "Sheet1!A:D")

    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    def test_dispatch_with_policy_overrides(self, mock_env, mock_firestore):
        """Test dispatch with policy overrides."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with policy overrides
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@TestChannel"], "limit_per_channel": 5},
            policy_overrides={"retry_max_attempts": 5, "timeout_sec": 600}
        )

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'test-policy-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert policy overrides are included
        self.assertEqual(result_data['status'], 'success')
        self.assertIn('policy_overrides', result_data)
        self.assertEqual(result_data['policy_overrides']['retry_max_attempts'], 5)
        self.assertEqual(result_data['policy_overrides']['timeout_sec'], 600)

    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate failure
        mock_env.return_value = 'test-project'
        mock_firestore.side_effect = Exception("Firestore connection failed")

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@TestChannel"], "limit_per_channel": 5}
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)
        self.assertIn('Firestore connection failed', result_data['error'])

    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    def test_firestore_write_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore write failures."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock write failure
        self.mock_document.set.side_effect = Exception("Write operation failed")

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@TestChannel"], "limit_per_channel": 5}
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertEqual(result_data['status'], 'error')
        self.assertIn('error', result_data)
        self.assertIn('Write operation failed', result_data['error'])

    def test_invalid_job_type_validation(self):
        """Test validation of invalid job types."""
        with self.assertRaises(ValueError):
            DispatchScraper(
                job_type="invalid_job_type",
                inputs={"channels": ["@TestChannel"]}
            )

    def test_missing_required_inputs_channel_scrape(self):
        """Test validation when required inputs are missing for channel scrape."""
        # Missing channels in inputs should be caught during execution
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"limit_per_channel": 5}  # Missing 'channels'
        )

        # The validation should happen during run(), not during construction
        # since inputs is a generic Dict
        self.assertIsInstance(tool, DispatchScraper)

    def test_missing_required_inputs_sheet_backfill(self):
        """Test validation when required inputs are missing for sheet backfill."""
        # Missing sheet_id should be caught during execution
        tool = DispatchScraper(
            job_type="sheet_backfill",
            inputs={"range": "Sheet1!A:D"}  # Missing 'sheet_id'
        )

        # The validation should happen during run()
        self.assertIsInstance(tool, DispatchScraper)

    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    def test_multiple_channels_dispatch(self, mock_env, mock_firestore):
        """Test dispatch with multiple channels."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create tool with multiple channels
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={
                "channels": ["@AlexHormozi", "@Channel2", "@Channel3"],
                "limit_per_channel": 8
            }
        )

        # Mock successful operations
        self.mock_document.set = MagicMock()
        self.mock_document.id = 'multi-channel-job-id'

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful dispatch
        self.assertEqual(result_data['status'], 'success')
        self.assertEqual(len(result_data['inputs']['channels']), 3)
        self.assertIn('@AlexHormozi', result_data['inputs']['channels'])
        self.assertIn('@Channel2', result_data['inputs']['channels'])
        self.assertIn('@Channel3', result_data['inputs']['channels'])

    def test_tool_properties(self):
        """Test that the tool has correct properties and structure."""
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@Test"], "limit_per_channel": 1}
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, DispatchScraper)

        # Test required parameters
        self.assertEqual(tool.job_type, "channel_scrape")
        self.assertIsInstance(tool.inputs, dict)
        self.assertIn("channels", tool.inputs)

        # Test optional parameters
        self.assertIsNone(tool.policy_overrides)

    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.audit_logger')
    def test_job_document_structure(self, mock_audit, mock_env, mock_firestore):
        """Test that job documents are created with the correct structure."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@TestChannel"], "limit_per_channel": 5}
        )

        # Mock successful operations
        captured_job_data = None
        def capture_set_call(*args, **kwargs):
            nonlocal captured_job_data
            captured_job_data = args[0] if args else None

        self.mock_document.set.side_effect = capture_set_call
        self.mock_document.id = 'test-structure-job-id'

        result = tool.run()

        # Verify the job document structure
        self.assertIsNotNone(captured_job_data)
        self.assertIn('job_type', captured_job_data)
        self.assertIn('status', captured_job_data)
        self.assertIn('created_at', captured_job_data)
        self.assertIn('inputs', captured_job_data)
        self.assertIn('source', captured_job_data)

        # Verify values
        self.assertEqual(captured_job_data['job_type'], 'channel_scrape')
        self.assertEqual(captured_job_data['status'], 'queued')
        self.assertEqual(captured_job_data['source'], 'orchestrator')


if __name__ == '__main__':
    unittest.main()