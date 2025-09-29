"""
Comprehensive test suite for handle_dlq.py targeting 100% coverage.
Missing lines: 66-133, 140-146, 150-176, 180-193, 197-220, 224-228, 233-253, 257-267
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

# Mock BaseTool and Field
class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    return kwargs.get('default', None)

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'].Field = mock_field
sys.modules['google.cloud.firestore'].SERVER_TIMESTAMP = 'SERVER_TIMESTAMP'

# Now import the tool
from orchestrator_agent.tools.handle_dlq import HandleDLQ


class TestHandleDLQ100Coverage(unittest.TestCase):
    """Test HandleDLQ to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()

        self.valid_failure_context = {
            "error_type": "api_timeout",
            "error_message": "Request timeout after 30s",
            "retry_count": 3,
            "last_attempt_at": "2025-01-27T12:00:00Z",
            "original_inputs": {"video_id": "test_video_123"}
        }

    @patch('orchestrator_agent.tools.handle_dlq.audit_logger')
    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_successful_dlq_routing(self, mock_get_env, mock_audit):
        """Test successful DLQ routing (lines 66-130)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"
        }.get(var)

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context,
            recovery_hints={"manual_action_required": True}
        )

        # Mock Firestore operations
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_dlq_ref = MagicMock()
        mock_dlq_ref.get.return_value = mock_doc
        mock_dlq_ref.set = MagicMock()

        self.mock_db.collection.return_value.document.return_value = mock_dlq_ref

        with patch.object(tool, '_initialize_firestore', return_value=self.mock_db):
            with patch.object(tool, '_cleanup_active_job') as mock_cleanup:
                with patch('os.path.exists', return_value=True):
                    result = tool.run()

        data = json.loads(result)

        # Verify successful DLQ routing (lines 121-130)
        self.assertEqual(data['status'], 'routed_to_dlq')
        self.assertIn('dlq_id', data)
        self.assertIn('dlq_ref', data)
        self.assertEqual(data['original_job_id'], 'test_job_001')
        self.assertEqual(data['job_type'], 'single_video')
        self.assertIn('severity', data)
        self.assertIn('recovery_priority', data)
        self.assertIn('processing_attempts', data)

        # Verify audit logging (lines 113-119)
        mock_audit.log_job_dlq_routed.assert_called_once()

        # Verify cleanup called (line 110)
        mock_cleanup.assert_called_once()

    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_existing_dlq_entry(self, mock_get_env):
        """Test detection of existing DLQ entry (lines 78-85)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"
        }.get(var)

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        # Mock existing DLQ entry
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_dlq_ref = MagicMock()
        mock_dlq_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_dlq_ref

        with patch.object(tool, '_initialize_firestore', return_value=self.mock_db):
            with patch('os.path.exists', return_value=True):
                result = tool.run()

        data = json.loads(result)

        # Verify already_exists response (lines 81-85)
        self.assertEqual(data['status'], 'already_exists')
        self.assertIn('Job already in dead letter queue', data['message'])
        self.assertIn('dlq_ref', data)

    def test_validate_inputs_missing_error_type(self):
        """Test validation for missing error_type (lines 140-143)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context={"error_message": "Some error"}  # Missing error_type
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Missing required failure_context field: error_type", str(context.exception))

    def test_validate_inputs_missing_error_message(self):
        """Test validation for missing error_message (lines 140-143)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context={"error_type": "timeout"}  # Missing error_message
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Missing required failure_context field: error_message", str(context.exception))

    def test_validate_inputs_reaches_dict_check(self):
        """Test that validation reaches the dict type check (lines 145-146)."""
        # The isinstance check is defensive - it's reached when the field checks pass
        # but the type is wrong. This can happen with certain mock scenarios.
        # Since the field checks use 'in' operator which works on non-dicts,
        # we need a special object that has __contains__ but isn't a dict

        class FakeDict:
            def __contains__(self, key):
                return True  # Always says it has the key

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context={"error_type": "test", "error_message": "test"}  # Valid initially
        )

        # Replace with fake dict after init
        tool.failure_context = FakeDict()

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("failure_context must be a dictionary", str(context.exception))

    def test_calculate_severity_high(self):
        """Test severity calculation for high severity errors (lines 169-170)."""
        high_severity_errors = ["authorization_failed", "data_corruption", "security_violation", "system_critical"]

        for error_type in high_severity_errors:
            failure_context = self.valid_failure_context.copy()
            failure_context['error_type'] = error_type

            tool = HandleDLQ(
                job_id="test_job_001",
                job_type="single_video",
                failure_context=failure_context
            )

            severity = tool._calculate_severity()
            self.assertEqual(severity, "high", f"Expected high severity for {error_type}")

    def test_calculate_severity_medium(self):
        """Test severity calculation for medium severity errors (lines 171-172)."""
        medium_severity_errors = ["quota_exceeded", "budget_exceeded", "invalid_configuration", "dependency_failure"]

        for error_type in medium_severity_errors:
            failure_context = self.valid_failure_context.copy()
            failure_context['error_type'] = error_type

            tool = HandleDLQ(
                job_id="test_job_001",
                job_type="single_video",
                failure_context=failure_context
            )

            severity = tool._calculate_severity()
            self.assertEqual(severity, "medium", f"Expected medium severity for {error_type}")

    def test_calculate_severity_high_retry_count(self):
        """Test severity calculation for high retry count (lines 173-174)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['error_type'] = "network_error"  # Low severity error
        failure_context['retry_count'] = 5  # But many retries

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=failure_context
        )

        severity = tool._calculate_severity()
        self.assertEqual(severity, "medium")  # Elevated to medium

    def test_calculate_severity_low(self):
        """Test severity calculation for low severity errors (lines 175-176)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['error_type'] = "network_error"
        failure_context['retry_count'] = 2  # Below threshold

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=failure_context
        )

        severity = tool._calculate_severity()
        self.assertEqual(severity, "low")

    def test_calculate_recovery_priority_urgent(self):
        """Test recovery priority calculation for urgent (lines 186-187)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['error_type'] = "authorization_failed"  # High severity

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=failure_context
        )

        priority = tool._calculate_recovery_priority()
        self.assertEqual(priority, "urgent")

    def test_calculate_recovery_priority_high(self):
        """Test recovery priority calculation for high (lines 188-189)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['error_type'] = "quota_exceeded"  # Medium severity

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="channel_scrape",  # Realtime job
            failure_context=failure_context
        )

        priority = tool._calculate_recovery_priority()
        self.assertEqual(priority, "high")

    def test_calculate_recovery_priority_medium(self):
        """Test recovery priority calculation for medium (lines 190-191)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['error_type'] = "network_error"  # Low severity

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",  # Realtime job
            failure_context=failure_context
        )

        priority = tool._calculate_recovery_priority()
        self.assertEqual(priority, "medium")

    def test_calculate_recovery_priority_low(self):
        """Test recovery priority calculation for low (lines 192-193)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['error_type'] = "network_error"  # Low severity

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="batch_summarize",  # Non-realtime job
            failure_context=failure_context
        )

        priority = tool._calculate_recovery_priority()
        self.assertEqual(priority, "low")

    def test_build_job_specific_metadata_channel_scrape(self):
        """Test metadata building for channel_scrape (lines 201-203)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['original_inputs'] = {
            "channels": ["@Channel1", "@Channel2", "@Channel3"],
            "limit_per_channel": 10
        }

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="channel_scrape",
            failure_context=failure_context
        )

        metadata = tool._build_job_specific_metadata()

        self.assertEqual(metadata['target_channels'], ["@Channel1", "@Channel2", "@Channel3"])
        self.assertEqual(metadata['estimated_quota_impact'], 300)  # 3 channels * 100

    def test_build_job_specific_metadata_single_video(self):
        """Test metadata building for single_video (lines 205-211)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['original_inputs'] = {"video_id": "abc123"}

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=failure_context
        )

        metadata = tool._build_job_specific_metadata()

        self.assertEqual(metadata['video_id'], "abc123")
        self.assertIn('estimated_cost_impact', metadata)
        self.assertEqual(metadata['estimated_cost_impact'], 0.5)

    def test_build_job_specific_metadata_batch_transcribe(self):
        """Test metadata building for batch_transcribe (lines 208-211)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['original_inputs'] = {"video_ids": ["vid1", "vid2", "vid3"]}

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="batch_transcribe",
            failure_context=failure_context
        )

        metadata = tool._build_job_specific_metadata()

        self.assertEqual(metadata['video_ids'], ["vid1", "vid2", "vid3"])
        self.assertEqual(metadata['batch_size'], 3)
        self.assertEqual(metadata['estimated_cost_impact'], 1.5)  # 3 * 0.5

    def test_build_job_specific_metadata_single_summary(self):
        """Test metadata building for single_summary (lines 213-218)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['original_inputs'] = {
            "video_id": "abc123",
            "platforms": ["drive", "zep"]
        }

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_summary",
            failure_context=failure_context
        )

        metadata = tool._build_job_specific_metadata()

        self.assertEqual(metadata['video_id'], "abc123")
        self.assertEqual(metadata['target_platforms'], ["drive", "zep"])

    def test_build_job_specific_metadata_batch_summarize(self):
        """Test metadata building for batch_summarize (lines 216-218)."""
        failure_context = self.valid_failure_context.copy()
        failure_context['original_inputs'] = {"video_ids": ["vid1", "vid2"]}

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="batch_summarize",
            failure_context=failure_context
        )

        metadata = tool._build_job_specific_metadata()

        self.assertEqual(metadata['video_ids'], ["vid1", "vid2"])
        self.assertEqual(metadata['target_platforms'], ["drive"])  # Default

    def test_estimate_transcription_cost_single(self):
        """Test cost estimation for single video (lines 224-225)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        cost = tool._estimate_transcription_cost({"video_id": "abc123"})
        self.assertEqual(cost, 0.5)

    def test_estimate_transcription_cost_batch(self):
        """Test cost estimation for batch (lines 226-227)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="batch_transcribe",
            failure_context=self.valid_failure_context
        )

        cost = tool._estimate_transcription_cost({"video_ids": ["vid1", "vid2", "vid3", "vid4"]})
        self.assertEqual(cost, 2.0)  # 4 * 0.5

    def test_estimate_transcription_cost_no_inputs(self):
        """Test cost estimation with no inputs (line 228)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        cost = tool._estimate_transcription_cost({})
        self.assertEqual(cost, 0.0)

    def test_cleanup_active_job_scraper(self):
        """Test cleanup for scraper jobs (lines 233-250)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="channel_scrape",
            failure_context=self.valid_failure_context
        )

        # Mock existing active job
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_active_ref = MagicMock()
        mock_active_ref.get.return_value = mock_doc
        mock_active_ref.delete = MagicMock()

        self.mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_active_ref

        tool._cleanup_active_job(self.mock_db)

        # Verify delete was called
        mock_active_ref.delete.assert_called_once()

    def test_cleanup_active_job_transcriber(self):
        """Test cleanup for transcriber jobs (lines 236-237)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_active_ref = MagicMock()
        mock_active_ref.get.return_value = mock_doc
        mock_active_ref.delete = MagicMock()

        self.mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_active_ref

        tool._cleanup_active_job(self.mock_db)

        mock_active_ref.delete.assert_called_once()

    def test_cleanup_active_job_summarizer(self):
        """Test cleanup for summarizer jobs (lines 238-239)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_summary",
            failure_context=self.valid_failure_context
        )

        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_active_ref = MagicMock()
        mock_active_ref.get.return_value = mock_doc
        mock_active_ref.delete = MagicMock()

        self.mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_active_ref

        tool._cleanup_active_job(self.mock_db)

        mock_active_ref.delete.assert_called_once()

    def test_cleanup_active_job_unknown_type(self):
        """Test cleanup for unknown job type (lines 243-244)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="unknown_type",
            failure_context=self.valid_failure_context
        )

        # Should return early without errors
        tool._cleanup_active_job(self.mock_db)

    def test_cleanup_active_job_not_exists(self):
        """Test cleanup when job doesn't exist (lines 249-250)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_active_ref = MagicMock()
        mock_active_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_active_ref

        # Should complete without error
        tool._cleanup_active_job(self.mock_db)

    def test_cleanup_active_job_exception(self):
        """Test cleanup exception handling (lines 251-253)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        # Mock exception during cleanup
        self.mock_db.collection.side_effect = Exception("Firestore error")

        # Should not raise exception
        tool._cleanup_active_job(self.mock_db)

    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.handle_dlq.firestore')
    def test_initialize_firestore_success(self, mock_firestore_module, mock_get_env):
        """Test successful Firestore initialization (lines 257-264)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json"
        }.get(var)

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        mock_client = MagicMock()
        mock_firestore_module.Client.return_value = mock_client

        with patch('os.path.exists', return_value=True):
            result = tool._initialize_firestore()

        mock_firestore_module.Client.assert_called_once_with(project="test-project")
        self.assertEqual(result, mock_client)

    @patch('orchestrator_agent.tools.handle_dlq.get_required_env_var')
    def test_initialize_firestore_missing_credentials(self, mock_get_env):
        """Test Firestore initialization with missing credentials (lines 261-262)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/creds.json"
        }.get(var)

        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        with patch('os.path.exists', return_value=False):
            with self.assertRaises(RuntimeError) as context:
                tool._initialize_firestore()

            self.assertIn("Failed to initialize Firestore", str(context.exception))

    def test_run_exception_handling(self):
        """Test exception handling in run method (lines 132-136)."""
        tool = HandleDLQ(
            job_id="test_job_001",
            job_type="single_video",
            failure_context=self.valid_failure_context
        )

        # Force exception during validation
        with patch.object(tool, '_validate_inputs', side_effect=Exception("Validation failed")):
            result = tool.run()

        data = json.loads(result)

        # Verify error response (lines 133-136)
        self.assertIn('error', data)
        self.assertIn('Failed to route job to DLQ', data['error'])
        self.assertIsNone(data['dlq_ref'])


if __name__ == '__main__':
    unittest.main()