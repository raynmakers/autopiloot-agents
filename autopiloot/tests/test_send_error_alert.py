"""
Test suite for SendErrorAlert tool.
Tests TASK-AST-0040 implementation including throttling policy, Slack notifications, and error context handling.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone, timedelta
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from observability_agent.tools.send_error_alert import SendErrorAlert
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'observability_agent', 
        'tools', 
        'send_error_alert.py'
    )
    spec = importlib.util.spec_from_file_location("SendErrorAlert", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SendErrorAlert = module.SendErrorAlert


class TestSendErrorAlert(unittest.TestCase):
    """Test cases for SendErrorAlert tool TASK-AST-0040."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_config = {
            "notifications": {"slack": {"channel": "ops-autopiloot"}}
        }
        
        self.test_context = {
            "type": "api_quota",
            "component": "ScraperAgent",
            "severity": "HIGH",
            "quota_used": 10000,
            "time_occurred": "2025-09-15T14:30:00Z"
        }

    @patch('observability_agent.tools.send_error_alert.get_required_env_var')
    @patch('observability_agent.tools.send_error_alert.load_app_config')
    @patch('observability_agent.tools.send_error_alert.firestore.Client')
    def test_successful_error_alert_first_time(self, mock_firestore, mock_config, mock_env):
        """Test successful error alert sending when no previous alert exists."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client - no previous alert
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_throttle_doc = MagicMock()
        mock_throttle_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
        
        # Mock successful Slack alert sending
        with patch.object(SendErrorAlert, '_send_slack_alert', return_value=True):
            tool = SendErrorAlert(
                message="YouTube API quota exceeded",
                context=self.test_context
            )
            
            result = tool.run()
            data = json.loads(result)
        
        # Verify successful response
        self.assertEqual(data["status"], "SENT")
        self.assertEqual(data["alert_type"], "api_quota")
        self.assertEqual(data["component"], "ScraperAgent")
        self.assertIn("successfully", data["message"])
        
        # Verify throttle record was created
        mock_db.collection.return_value.document.return_value.set.assert_called_once()
        
        print("✅ Successful error alert first time test passed")

    @patch('observability_agent.tools.send_error_alert.get_required_env_var')
    @patch('observability_agent.tools.send_error_alert.load_app_config')
    @patch('observability_agent.tools.send_error_alert.firestore.Client')
    def test_throttling_within_hour(self, mock_firestore, mock_config, mock_env):
        """Test alert throttling when same type was sent within last hour."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client - recent alert exists
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_throttle_doc = MagicMock()
        mock_throttle_doc.exists = True
        
        # Alert sent 30 minutes ago (should be throttled)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_throttle_doc.to_dict.return_value = {
            "last_sent": recent_time
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
        
        tool = SendErrorAlert(
            message="Another API quota error",
            context=self.test_context
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify throttled response
        self.assertEqual(data["status"], "THROTTLED")
        self.assertEqual(data["alert_type"], "api_quota")
        self.assertIn("throttled", data["message"])
        
        print("✅ Throttling within hour test passed")

    @patch('observability_agent.tools.send_error_alert.get_required_env_var')
    @patch('observability_agent.tools.send_error_alert.load_app_config')
    @patch('observability_agent.tools.send_error_alert.firestore.Client')
    def test_throttling_expired_after_hour(self, mock_firestore, mock_config, mock_env):
        """Test that throttling expires after 1 hour."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client - old alert exists
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_throttle_doc = MagicMock()
        mock_throttle_doc.exists = True
        
        # Alert sent 2 hours ago (should not be throttled)
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_throttle_doc.to_dict.return_value = {
            "last_sent": old_time
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
        
        # Mock successful Slack alert sending
        with patch.object(SendErrorAlert, '_send_slack_alert', return_value=True):
            tool = SendErrorAlert(
                message="API quota error after throttle expiry",
                context=self.test_context
            )
            
            result = tool.run()
            data = json.loads(result)
        
        # Verify alert was sent (not throttled)
        self.assertEqual(data["status"], "SENT")
        
        print("✅ Throttling expired after hour test passed")

    @patch('observability_agent.tools.send_error_alert.get_required_env_var')
    @patch('observability_agent.tools.send_error_alert.load_app_config')
    @patch('observability_agent.tools.send_error_alert.firestore.Client')
    def test_different_alert_types_not_throttled(self, mock_firestore, mock_config, mock_env):
        """Test that different alert types are not throttled against each other."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        def mock_get_document(alert_type):
            mock_doc = MagicMock()
            if alert_type == "api_quota":
                # api_quota alert sent recently
                mock_doc.exists = True
                mock_doc.to_dict.return_value = {
                    "last_sent": datetime.now(timezone.utc) - timedelta(minutes=30)
                }
            else:
                # transcription_failure alert never sent
                mock_doc.exists = False
            return mock_doc
        
        mock_db.collection.return_value.document.side_effect = lambda alert_type: MagicMock(
            get=MagicMock(return_value=mock_get_document(alert_type))
        )
        
        # Test different alert type (transcription_failure instead of api_quota)
        different_context = {
            "type": "transcription_failure",
            "component": "TranscriberAgent",
            "severity": "CRITICAL"
        }
        
        with patch.object(SendErrorAlert, '_send_slack_alert', return_value=True):
            tool = SendErrorAlert(
                message="Transcription job failed",
                context=different_context
            )
            
            result = tool.run()
            data = json.loads(result)
        
        # Different alert type should not be throttled
        self.assertEqual(data["status"], "SENT")
        self.assertEqual(data["alert_type"], "transcription_failure")
        
        print("✅ Different alert types not throttled test passed")

    @patch('observability_agent.tools.send_error_alert.get_required_env_var')
    @patch('observability_agent.tools.send_error_alert.load_app_config')
    @patch('observability_agent.tools.send_error_alert.firestore.Client')
    def test_slack_alert_failure(self, mock_firestore, mock_config, mock_env):
        """Test handling when Slack alert sending fails."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client - no previous alert
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_throttle_doc = MagicMock()
        mock_throttle_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
        
        # Mock failed Slack alert sending
        with patch.object(SendErrorAlert, '_send_slack_alert', return_value=False):
            tool = SendErrorAlert(
                message="Test error message",
                context=self.test_context
            )
            
            result = tool.run()
            data = json.loads(result)
        
        # Verify failed response
        self.assertEqual(data["status"], "FAILED")
        self.assertIn("Failed to send", data["message"])
        
        print("✅ Slack alert failure test passed")

    @patch('observability_agent.tools.send_error_alert.get_required_env_var')
    @patch('observability_agent.tools.send_error_alert.load_app_config')
    def test_firestore_error_fallback(self, mock_config, mock_env):
        """Test graceful handling when Firestore operations fail."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore failure
        with patch('observability_agent.tools.send_error_alert.firestore.Client', side_effect=Exception("Firestore error")):
            with patch.object(SendErrorAlert, '_send_slack_alert', return_value=True):
                tool = SendErrorAlert(
                    message="Test error",
                    context=self.test_context
                )
                
                result = tool.run()
                data = json.loads(result)
        
        # Should still send alert (throttling check failed but allows alert)
        self.assertEqual(data["status"], "SENT")
        
        print("✅ Firestore error fallback test passed")

    def test_context_field_extraction(self):
        """Test proper extraction of alert fields from context."""
        extended_context = {
            "type": "transcription_failure",
            "component": "TranscriberAgent",
            "severity": "CRITICAL",
            "video_id": "abc123",
            "retry_attempts": 3,
            "error_code": "timeout"
        }
        
        with patch('observability_agent.tools.send_error_alert.get_required_env_var') as mock_env, \
             patch('observability_agent.tools.send_error_alert.load_app_config') as mock_config, \
             patch('observability_agent.tools.send_error_alert.firestore.Client') as mock_firestore:
            
            # Mock successful setup
            mock_env.return_value = "test-project"
            mock_config.return_value = self.mock_config
            
            mock_db = MagicMock()
            mock_firestore.return_value = mock_db
            mock_throttle_doc = MagicMock()
            mock_throttle_doc.exists = False
            mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
            
            with patch.object(SendErrorAlert, '_send_slack_alert', return_value=True) as mock_slack:
                tool = SendErrorAlert(
                    message="Transcription failed",
                    context=extended_context
                )
                
                tool.run()
                
                # Verify alert items include all context fields
                call_args = mock_slack.call_args[0]
                alert_items = call_args[1]  # Second argument is alert_items
                
                self.assertIn("Video Id", alert_items["fields"])
                self.assertIn("Retry Attempts", alert_items["fields"])
                self.assertIn("Error Code", alert_items["fields"])
        
        print("✅ Context field extraction test passed")

    def test_severity_to_alert_type_mapping(self):
        """Test proper mapping of severity levels to alert types."""
        severity_mappings = [
            ("LOW", "warning"),
            ("MEDIUM", "warning"),
            ("HIGH", "error"),
            ("CRITICAL", "error")
        ]
        
        for severity, expected_alert_type in severity_mappings:
            with patch('observability_agent.tools.send_error_alert.get_required_env_var') as mock_env, \
                 patch('observability_agent.tools.send_error_alert.load_app_config') as mock_config, \
                 patch('observability_agent.tools.send_error_alert.firestore.Client') as mock_firestore:
                
                # Mock setup
                mock_env.return_value = "test-project"
                mock_config.return_value = self.mock_config
                
                mock_db = MagicMock()
                mock_firestore.return_value = mock_db
                mock_throttle_doc = MagicMock()
                mock_throttle_doc.exists = False
                mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
                
                # Mock FormatSlackBlocks to capture alert_type
                with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks') as mock_formatter, \
                     patch('observability_agent.tools.send_error_alert.SendSlackMessage') as mock_messenger:
                    
                    mock_formatter.return_value.run.return_value = json.dumps({"blocks": []})
                    mock_messenger.return_value.run.return_value = json.dumps({"ts": "123", "channel": "#test"})
                    
                    tool = SendErrorAlert(
                        message="Test error",
                        context={"type": "test", "component": "Test", "severity": severity}
                    )
                    
                    tool.run()
                    
                    # Verify correct alert type was used
                    formatter_call_args = mock_formatter.call_args
                    self.assertEqual(formatter_call_args.kwargs["alert_type"], expected_alert_type)
        
        print("✅ Severity to alert type mapping test passed")

    @patch('observability_agent.tools.send_error_alert.get_required_env_var')
    def test_missing_environment_variable(self, mock_env):
        """Test error handling when environment variable is missing."""
        mock_env.side_effect = ValueError("GCP_PROJECT_ID environment variable is required")
        
        tool = SendErrorAlert(
            message="Test error",
            context=self.test_context
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should return error response
        self.assertIn("error", data)
        self.assertEqual(data["status"], "ERROR")
        
        print("✅ Missing environment variable test passed")

    def test_throttle_record_creation(self):
        """Test that throttle records are properly created in Firestore."""
        with patch('observability_agent.tools.send_error_alert.get_required_env_var') as mock_env, \
             patch('observability_agent.tools.send_error_alert.load_app_config') as mock_config, \
             patch('observability_agent.tools.send_error_alert.firestore.Client') as mock_firestore:
            
            # Mock setup
            mock_env.return_value = "test-project"
            mock_config.return_value = self.mock_config
            
            mock_db = MagicMock()
            mock_firestore.return_value = mock_db
            mock_throttle_doc = MagicMock()
            mock_throttle_doc.exists = False
            mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
            
            with patch.object(SendErrorAlert, '_send_slack_alert', return_value=True):
                tool = SendErrorAlert(
                    message="Test error",
                    context=self.test_context
                )
                
                tool.run()
                
                # Verify throttle record was created
                mock_db.collection.assert_called_with('alert_throttling')
                mock_db.collection.return_value.document.assert_called_with('api_quota')
                mock_db.collection.return_value.document.return_value.set.assert_called_once()
                
                # Verify record structure
                set_call_args = mock_db.collection.return_value.document.return_value.set.call_args
                record_data = set_call_args[0][0]
                self.assertEqual(record_data['alert_type'], 'api_quota')
                self.assertIn('last_sent', record_data)
        
        print("✅ Throttle record creation test passed")

    def test_default_context_values(self):
        """Test proper handling of missing context values with defaults."""
        minimal_context = {}  # No context values
        
        with patch('observability_agent.tools.send_error_alert.get_required_env_var') as mock_env, \
             patch('observability_agent.tools.send_error_alert.load_app_config') as mock_config, \
             patch('observability_agent.tools.send_error_alert.firestore.Client') as mock_firestore:
            
            # Mock setup
            mock_env.return_value = "test-project"
            mock_config.return_value = self.mock_config
            
            mock_db = MagicMock()
            mock_firestore.return_value = mock_db
            mock_throttle_doc = MagicMock()
            mock_throttle_doc.exists = False
            mock_db.collection.return_value.document.return_value.get.return_value = mock_throttle_doc
            
            with patch.object(SendErrorAlert, '_send_slack_alert', return_value=True):
                tool = SendErrorAlert(
                    message="Test error with minimal context",
                    context=minimal_context
                )
                
                result = tool.run()
                data = json.loads(result)
        
        # Should use default values
        self.assertEqual(data["status"], "SENT")
        self.assertEqual(data["alert_type"], "error")  # Default type
        self.assertEqual(data["component"], "Unknown")  # Default component
        
        print("✅ Default context values test passed")


if __name__ == '__main__':
    unittest.main()