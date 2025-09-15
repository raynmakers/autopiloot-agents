"""
Test suite for AuditLogger utility.
Tests TASK-AUDIT-0041 implementation including audit log creation, structured data, and Firestore integration.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone
import sys

# Add the parent directories to sys.path to import the utility
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))

try:
    from core.audit_logger import AuditLogger, audit_logger, write_audit_log
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'core', 
        'audit_logger.py'
    )
    spec = importlib.util.spec_from_file_location("audit_logger", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    AuditLogger = module.AuditLogger
    audit_logger = module.audit_logger
    write_audit_log = module.write_audit_log


class TestAuditLogger(unittest.TestCase):
    """Test cases for AuditLogger utility TASK-AUDIT-0041."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset audit logger state for each test
        self.test_logger = AuditLogger()

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_basic_audit_log_creation(self, mock_firestore, mock_env):
        """Test basic audit log entry creation with all required fields."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test basic audit log creation
        success = self.test_logger.write_audit_log(
            actor="TestActor",
            action="test_action",
            entity="test_entity",
            entity_id="test_123",
            details={"test_field": "test_value"}
        )
        
        # Verify success
        self.assertTrue(success)
        
        # Verify Firestore calls
        mock_db.collection.assert_called_once_with("audit_logs")
        mock_doc_ref.set.assert_called_once()
        
        # Verify audit entry structure
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "TestActor")
        self.assertEqual(set_call_args["action"], "test_action")
        self.assertEqual(set_call_args["entity"], "test_entity")
        self.assertEqual(set_call_args["entity_id"], "test_123")
        self.assertIn("timestamp", set_call_args)
        self.assertEqual(set_call_args["details"], {"test_field": "test_value"})
        
        print("✅ Basic audit log creation test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_transcript_creation_logging(self, mock_firestore, mock_env):
        """Test transcript creation audit logging."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test transcript creation logging
        success = self.test_logger.log_transcript_created(
            video_id="video_123",
            transcript_doc_ref="transcripts/video_123"
        )
        
        self.assertTrue(success)
        
        # Verify audit entry
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "TranscriberAgent")
        self.assertEqual(set_call_args["action"], "transcript_created")
        self.assertEqual(set_call_args["entity"], "transcript")
        self.assertEqual(set_call_args["entity_id"], "video_123")
        self.assertEqual(set_call_args["details"]["transcript_doc_ref"], "transcripts/video_123")
        self.assertEqual(set_call_args["details"]["event_type"], "transcription_completed")
        
        print("✅ Transcript creation logging test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_summary_creation_logging(self, mock_firestore, mock_env):
        """Test summary creation audit logging."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test summary creation logging
        success = self.test_logger.log_summary_created(
            video_id="video_456",
            summary_doc_ref="summaries/video_456"
        )
        
        self.assertTrue(success)
        
        # Verify audit entry
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "SummarizerAgent")
        self.assertEqual(set_call_args["action"], "summary_created")
        self.assertEqual(set_call_args["entity"], "summary")
        self.assertEqual(set_call_args["entity_id"], "video_456")
        self.assertEqual(set_call_args["details"]["summary_doc_ref"], "summaries/video_456")
        
        print("✅ Summary creation logging test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_slack_alert_logging(self, mock_firestore, mock_env):
        """Test Slack alert audit logging."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test Slack alert logging
        success = self.test_logger.log_slack_alert_sent(
            alert_type="budget_threshold",
            channel="#ops-autopiloot",
            message_ts="1234567890.123"
        )
        
        self.assertTrue(success)
        
        # Verify audit entry
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "AssistantAgent")
        self.assertEqual(set_call_args["action"], "alert_sent")
        self.assertEqual(set_call_args["entity"], "slack_message")
        self.assertEqual(set_call_args["entity_id"], "1234567890.123")
        self.assertEqual(set_call_args["details"]["alert_type"], "budget_threshold")
        self.assertEqual(set_call_args["details"]["channel"], "#ops-autopiloot")
        
        print("✅ Slack alert logging test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_budget_alert_logging(self, mock_firestore, mock_env):
        """Test budget alert audit logging."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test budget alert logging
        success = self.test_logger.log_budget_alert(
            date="2025-09-15",
            amount_spent=4.25,
            threshold_percentage=85.0
        )
        
        self.assertTrue(success)
        
        # Verify audit entry
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "AssistantAgent")
        self.assertEqual(set_call_args["action"], "budget_alert_sent")
        self.assertEqual(set_call_args["entity"], "budget_threshold")
        self.assertEqual(set_call_args["entity_id"], "2025-09-15")
        self.assertEqual(set_call_args["details"]["amount_spent_usd"], 4.25)
        self.assertEqual(set_call_args["details"]["threshold_percentage"], 85.0)
        
        print("✅ Budget alert logging test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_cost_update_logging(self, mock_firestore, mock_env):
        """Test cost update audit logging."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test cost update logging
        success = self.test_logger.log_cost_updated(
            date="2025-09-15",
            cost_usd=0.75,
            cost_type="transcription"
        )
        
        self.assertTrue(success)
        
        # Verify audit entry
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "TranscriberAgent")
        self.assertEqual(set_call_args["action"], "cost_updated")
        self.assertEqual(set_call_args["entity"], "daily_costs")
        self.assertEqual(set_call_args["entity_id"], "2025-09-15")
        self.assertEqual(set_call_args["details"]["cost_usd"], 0.75)
        self.assertEqual(set_call_args["details"]["cost_type"], "transcription")
        
        print("✅ Cost update logging test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_video_discovery_logging(self, mock_firestore, mock_env):
        """Test video discovery audit logging."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test video discovery logging
        success = self.test_logger.log_video_discovered(
            video_id="video_789",
            source="youtube_api"
        )
        
        self.assertTrue(success)
        
        # Verify audit entry
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "ScraperAgent")
        self.assertEqual(set_call_args["action"], "video_discovered")
        self.assertEqual(set_call_args["entity"], "video")
        self.assertEqual(set_call_args["entity_id"], "video_789")
        self.assertEqual(set_call_args["details"]["source"], "youtube_api")
        
        print("✅ Video discovery logging test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_job_failure_logging(self, mock_firestore, mock_env):
        """Test job failure audit logging."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test job failure logging
        success = self.test_logger.log_job_failed(
            job_id="job_abc123",
            job_type="transcription",
            error_message="API timeout after 3 retries"
        )
        
        self.assertTrue(success)
        
        # Verify audit entry
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["actor"], "System")
        self.assertEqual(set_call_args["action"], "job_failed")
        self.assertEqual(set_call_args["entity"], "job")
        self.assertEqual(set_call_args["entity_id"], "job_abc123")
        self.assertEqual(set_call_args["details"]["job_type"], "transcription")
        self.assertEqual(set_call_args["details"]["error_message"], "API timeout after 3 retries")
        
        print("✅ Job failure logging test passed")

    @patch('core.audit_logger.get_required_env_var')
    def test_firestore_initialization_failure(self, mock_env):
        """Test graceful handling of Firestore initialization failure."""
        # Mock environment variable failure
        mock_env.side_effect = ValueError("GCP_PROJECT_ID not found")
        
        # Test audit log creation with Firestore failure
        success = self.test_logger.write_audit_log(
            actor="TestActor",
            action="test_action",
            entity="test_entity",
            entity_id="test_123"
        )
        
        # Should fail gracefully without raising exception
        self.assertFalse(success)
        
        print("✅ Firestore initialization failure test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_firestore_write_failure(self, mock_firestore, mock_env):
        """Test graceful handling of Firestore write failure."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock Firestore write failure
        mock_doc_ref = MagicMock()
        mock_doc_ref.set.side_effect = Exception("Firestore write failed")
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test audit log creation with write failure
        with patch('builtins.print') as mock_print:
            success = self.test_logger.write_audit_log(
                actor="TestActor",
                action="test_action", 
                entity="test_entity",
                entity_id="test_123"
            )
            
            # Should fail gracefully and print warning
            self.assertFalse(success)
            mock_print.assert_called()
            warning_call = mock_print.call_args[0][0]
            self.assertIn("Warning: Failed to write audit log entry", warning_call)
        
        print("✅ Firestore write failure test passed")

    def test_convenience_function(self):
        """Test the convenience write_audit_log function."""
        with patch.object(audit_logger, 'write_audit_log', return_value=True) as mock_write:
            # Test convenience function
            success = write_audit_log(
                actor="TestActor",
                action="test_action",
                entity="test_entity", 
                entity_id="test_123",
                details={"key": "value"}
            )
            
            self.assertTrue(success)
            mock_write.assert_called_once_with(
                "TestActor", "test_action", "test_entity", "test_123", {"key": "value"}
            )
        
        print("✅ Convenience function test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_lazy_firestore_initialization(self, mock_firestore, mock_env):
        """Test lazy initialization of Firestore client."""
        # Mock environment
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Create new logger instance
        test_logger = AuditLogger()
        
        # Verify Firestore client not initialized yet
        self.assertIsNone(test_logger._db)
        
        # Make first audit log call
        test_logger.write_audit_log("Actor1", "action1", "entity1", "id1")
        
        # Verify Firestore client was initialized
        mock_firestore.assert_called_once_with(project="test-project")
        
        # Make second audit log call
        test_logger.write_audit_log("Actor2", "action2", "entity2", "id2")
        
        # Verify Firestore client was not re-initialized
        mock_firestore.assert_called_once()  # Still only called once
        
        print("✅ Lazy Firestore initialization test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_timestamp_format(self, mock_firestore, mock_env):
        """Test that timestamps are in proper UTC ISO format."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test audit log creation
        self.test_logger.write_audit_log(
            actor="TestActor",
            action="test_action",
            entity="test_entity",
            entity_id="test_123"
        )
        
        # Verify timestamp format
        set_call_args = mock_doc_ref.set.call_args[0][0]
        timestamp = set_call_args["timestamp"]
        
        # Should be valid ISO format timestamp
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        self.assertTrue(timestamp.endswith('+00:00') or timestamp.endswith('Z'))
        
        print("✅ Timestamp format test passed")

    @patch('core.audit_logger.get_required_env_var')
    @patch('core.audit_logger.firestore.Client')
    def test_empty_details_handling(self, mock_firestore, mock_env):
        """Test handling of empty details parameter."""
        # Mock environment and Firestore
        mock_env.return_value = "test-project"
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        # Test audit log creation without details
        success = self.test_logger.write_audit_log(
            actor="TestActor",
            action="test_action",
            entity="test_entity",
            entity_id="test_123"
            # No details parameter
        )
        
        self.assertTrue(success)
        
        # Verify empty details dictionary
        set_call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(set_call_args["details"], {})
        
        print("✅ Empty details handling test passed")

    def test_audit_entry_interface_compliance(self):
        """Test that audit entries match AuditLogEntry TypedDict interface."""
        with patch('core.audit_logger.get_required_env_var') as mock_env, \
             patch('core.audit_logger.firestore.Client') as mock_firestore:
            
            # Mock environment and Firestore
            mock_env.return_value = "test-project"
            mock_db = MagicMock()
            mock_firestore.return_value = mock_db
            mock_doc_ref = MagicMock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref
            
            # Test audit log creation
            self.test_logger.write_audit_log(
                actor="TestActor",
                action="test_action",
                entity="test_entity",
                entity_id="test_123",
                details={"key": "value"}
            )
            
            # Verify all required fields from AuditLogEntry TypedDict
            set_call_args = mock_doc_ref.set.call_args[0][0]
            required_fields = ["actor", "action", "entity", "entity_id", "timestamp", "details"]
            
            for field in required_fields:
                self.assertIn(field, set_call_args, f"Missing required field: {field}")
            
            # Verify field types
            self.assertIsInstance(set_call_args["actor"], str)
            self.assertIsInstance(set_call_args["action"], str)
            self.assertIsInstance(set_call_args["entity"], str)
            self.assertIsInstance(set_call_args["entity_id"], str)
            self.assertIsInstance(set_call_args["timestamp"], str)
            self.assertIsInstance(set_call_args["details"], dict)
        
        print("✅ Audit entry interface compliance test passed")


if __name__ == '__main__':
    unittest.main()