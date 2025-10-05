"""
Comprehensive test suite for dispatch_transcriber.py targeting 100% coverage.
Missing lines: 61-140, 147-162, 166-199, 210, 214-221, 225-235
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone

# Mock external dependencies before imports
mock_modules = {
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'dotenv': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Mock SERVER_TIMESTAMP
sys.modules['google.cloud.firestore'].SERVER_TIMESTAMP = 'SERVER_TIMESTAMP'

# Import the tool after mocking
from orchestrator_agent.tools.dispatch_transcriber import DispatchTranscriber

# Patch DispatchTranscriber __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.job_type = kwargs.get('job_type')
    self.inputs = kwargs.get('inputs', {})
    self.policy_overrides = kwargs.get('policy_overrides', None)

DispatchTranscriber.__init__ = patched_init


class TestDispatchTranscriber100Coverage(unittest.TestCase):
    """Test DispatchTranscriber to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_firestore_client = MagicMock()

    @patch('orchestrator_agent.tools.dispatch_transcriber.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_transcriber.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_successful_single_video_dispatch(self, mock_get_env, mock_config, mock_audit):
        """Test successful single_video job dispatch (lines 61-137)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"
        }.get(var)
        mock_config.return_value = {
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_video_123", "priority": "high"}
        )

        # Mock Firestore operations
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_collection = MagicMock()
        mock_collection.document.return_value.get.return_value = mock_doc
        mock_collection.document.return_value.set = MagicMock()

        self.mock_db.collection.return_value.document.return_value.collection.return_value = mock_collection

        with patch.object(tool, '_initialize_firestore', return_value=self.mock_db):
            with patch('os.path.exists', return_value=True):
                result = tool.run()

        data = json.loads(result)

        # Verify successful dispatch (lines 129-137)
        self.assertEqual(data['status'], 'dispatched')
        self.assertEqual(data['job_type'], 'single_video')
        self.assertIn('job_id', data)
        self.assertIn('job_ref', data)
        self.assertIn('priority', data)
        self.assertEqual(data['priority'], 'high')
        self.assertIn('budget_allocated_usd', data)

        # Verify audit logging (lines 122-127)
        mock_audit.log_job_dispatched.assert_called_once()

    @patch('orchestrator_agent.tools.dispatch_transcriber.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_transcriber.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_successful_batch_transcribe_dispatch(self, mock_get_env, mock_config, mock_audit):
        """Test successful batch_transcribe job dispatch (lines 112-115)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"
        }.get(var)
        mock_config.return_value = {
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={"video_ids": ["vid1", "vid2", "vid3"], "batch_size": 2}
        )

        # Mock Firestore operations
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_collection = MagicMock()
        mock_collection.document.return_value.get.return_value = mock_doc
        mock_collection.document.return_value.set = MagicMock()

        self.mock_db.collection.return_value.document.return_value.collection.return_value = mock_collection

        with patch.object(tool, '_initialize_firestore', return_value=self.mock_db):
            with patch('os.path.exists', return_value=True):
                result = tool.run()

        data = json.loads(result)

        # Verify batch dispatch (lines 112-116)
        self.assertEqual(data['status'], 'dispatched')
        self.assertEqual(data['job_type'], 'batch_transcribe')
        self.assertEqual(data['estimated_videos'], 3)

    @patch('orchestrator_agent.tools.dispatch_transcriber.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_existing_job_detection(self, mock_get_env, mock_config):
        """Test detection of existing job (lines 85-92)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"
        }.get(var)
        mock_config.return_value = {
            "budgets": {"transcription_daily_usd": 5.0}
        }

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_video_123"}
        )

        # Mock existing job
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_collection = MagicMock()
        mock_collection.document.return_value.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value.collection.return_value = mock_collection

        with patch.object(tool, '_initialize_firestore', return_value=self.mock_db):
            with patch('os.path.exists', return_value=True):
                result = tool.run()

        data = json.loads(result)

        # Verify already_exists response (lines 88-92)
        self.assertEqual(data['status'], 'already_exists')
        self.assertIn('Job already dispatched', data['message'])
        self.assertIn('job_ref', data)

    @patch('orchestrator_agent.tools.dispatch_transcriber.load_app_config')
    def test_budget_constraint_violation(self, mock_config):
        """Test budget constraint violation (lines 69-75)."""
        mock_config.return_value = {
            "budgets": {"transcription_daily_usd": 0.1}  # Very low budget
        }

        tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={"video_ids": ["vid1", "vid2", "vid3", "vid4", "vid5"]}  # Would cost $2.50
        )

        result = tool.run()
        data = json.loads(result)

        # Verify budget constraint error (lines 71-75)
        self.assertIn('error', data)
        self.assertIn('Budget constraint violation', data['error'])
        self.assertIsNone(data['job_ref'])
        self.assertIn('budget_status', data)

    def test_validate_inputs_single_video(self):
        """Test input validation for single_video (lines 147-151)."""
        # Missing video_id
        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("single_video requires 'video_id'", str(context.exception))

        # Invalid video_id type
        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": 123}  # Should be string
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("video_id must be a string", str(context.exception))

    def test_validate_inputs_batch_transcribe(self):
        """Test input validation for batch_transcribe (lines 153-159)."""
        # Missing video_ids
        tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("batch_transcribe requires 'video_ids'", str(context.exception))

        # Invalid video_ids type
        tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={"video_ids": "not_a_list"}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("video_ids must be a list", str(context.exception))

        # Empty video_ids list
        tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={"video_ids": []}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("video_ids list cannot be empty", str(context.exception))

    def test_validate_inputs_invalid_job_type(self):
        """Test input validation for invalid job_type (lines 161-162)."""
        tool = DispatchTranscriber(
            job_type="invalid_type",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Invalid job_type", str(context.exception))

    def test_check_budget_constraints_single_video(self):
        """Test budget constraint checking for single_video (lines 169-171)."""
        config = {"budgets": {"transcription_daily_usd": 5.0}}

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )

        result = tool._check_budget_constraints(config)

        # Verify single video cost estimation (lines 169-171)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['estimated_cost'], 0.5)
        self.assertEqual(result['video_count'], 1)

    def test_check_budget_constraints_batch(self):
        """Test budget constraint checking for batch_transcribe (lines 172-174)."""
        config = {"budgets": {"transcription_daily_usd": 5.0}}

        tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={"video_ids": ["vid1", "vid2", "vid3"]}
        )

        result = tool._check_budget_constraints(config)

        # Verify batch cost estimation (lines 172-174)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['estimated_cost'], 1.5)  # 3 videos * 0.5
        self.assertEqual(result['video_count'], 3)

    def test_check_budget_constraints_with_policy_override(self):
        """Test budget constraints with policy overrides (lines 180-183)."""
        config = {"budgets": {"transcription_daily_usd": 5.0}}

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"},
            policy_overrides={"budget_limit_usd": 2.0}
        )

        result = tool._check_budget_constraints(config)

        # Verify override is applied (lines 180-183)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['available_budget'], 2.0)  # Override wins

    def test_check_budget_constraints_exceeded(self):
        """Test budget constraint exceeded scenario (lines 190-197)."""
        config = {"budgets": {"transcription_daily_usd": 0.2}}  # Very low

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )

        result = tool._check_budget_constraints(config)

        # Verify budget exceeded (lines 191-197)
        self.assertFalse(result['allowed'])
        self.assertIn('exceeds available budget', result['reason'])
        self.assertEqual(result['estimated_cost'], 0.5)
        self.assertEqual(result['available_budget'], 0.2)

    def test_check_budget_constraints_satisfied(self):
        """Test budget constraints satisfied (lines 199-205)."""
        config = {"budgets": {"transcription_daily_usd": 10.0}}

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )

        result = tool._check_budget_constraints(config)

        # Verify satisfied response (lines 199-205)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['reason'], 'Budget constraints satisfied')

    def test_estimate_duration(self):
        """Test duration estimation (lines 207-210)."""
        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )

        duration = tool._estimate_duration("test_video_id")

        # Verify default duration (line 210)
        self.assertEqual(duration, 1800)  # 30 minutes

    def test_calculate_priority_single_video(self):
        """Test priority calculation for single_video (lines 214-218)."""
        # Test high priority
        tool_high = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123", "priority": "high"}
        )
        self.assertEqual(tool_high._calculate_priority(), "high")

        # Test medium priority
        tool_medium = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123", "priority": "medium"}
        )
        self.assertEqual(tool_medium._calculate_priority(), "medium")

        # Test low priority
        tool_low = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123", "priority": "low"}
        )
        self.assertEqual(tool_low._calculate_priority(), "low")

        # Test invalid priority defaults to medium
        tool_invalid = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123", "priority": "urgent"}
        )
        self.assertEqual(tool_invalid._calculate_priority(), "medium")

        # Test missing priority defaults to medium
        tool_missing = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )
        self.assertEqual(tool_missing._calculate_priority(), "medium")

    def test_calculate_priority_batch(self):
        """Test priority calculation for batch_transcribe (lines 219-221)."""
        tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={"video_ids": ["vid1", "vid2"]}
        )

        # Batch jobs are always low priority (line 220)
        self.assertEqual(tool._calculate_priority(), "low")

    def test_calculate_priority_unknown_job_type(self):
        """Test priority calculation for unknown job type (line 221)."""
        tool = DispatchTranscriber(
            job_type="unknown_type",
            inputs={}
        )

        # Unknown job types default to low priority (line 221)
        self.assertEqual(tool._calculate_priority(), "low")

    def test_check_budget_constraints_unknown_job_type(self):
        """Test budget constraints for unknown job type (lines 176-177)."""
        config = {"budgets": {"transcription_daily_usd": 5.0}}

        tool = DispatchTranscriber(
            job_type="unknown_type",
            inputs={}
        )

        result = tool._check_budget_constraints(config)

        # Unknown job types have zero cost (lines 176-177)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['estimated_cost'], 0.0)
        self.assertEqual(result['video_count'], 0)

    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_transcriber.firestore')
    def test_initialize_firestore_success(self, mock_firestore_module, mock_get_env):
        """Test successful Firestore initialization (lines 225-232)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"
        }.get(var)

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )

        mock_client = MagicMock()
        mock_firestore_module.Client.return_value = mock_client

        with patch('os.path.exists', return_value=True):
            result = tool._initialize_firestore()

        # Verify Firestore client created (line 232)
        mock_firestore_module.Client.assert_called_once_with(project="test-project")
        self.assertEqual(result, mock_client)

    @patch('orchestrator_agent.tools.dispatch_transcriber.get_required_env_var')
    def test_initialize_firestore_missing_credentials(self, mock_get_env):
        """Test Firestore initialization with missing credentials (lines 229-230)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/creds.json"
        }.get(var)

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )

        with patch('os.path.exists', return_value=False):
            with self.assertRaises(RuntimeError) as context:
                tool._initialize_firestore()

            self.assertIn("Failed to initialize Firestore", str(context.exception))

    @patch('orchestrator_agent.tools.dispatch_transcriber.load_app_config')
    def test_run_exception_handling(self, mock_config):
        """Test exception handling in run method (lines 139-143)."""
        mock_config.side_effect = Exception("Config load failed")

        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test_123"}
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error response (lines 140-143)
        self.assertIn('error', data)
        self.assertIn('Failed to dispatch transcriber job', data['error'])
        self.assertIsNone(data['job_ref'])


if __name__ == '__main__':
    unittest.main()