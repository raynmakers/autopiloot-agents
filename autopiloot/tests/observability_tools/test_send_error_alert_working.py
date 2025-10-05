"""
Working test for send_error_alert.py - achieves actual code coverage
Targets 80%+ coverage through comprehensive real code execution
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json
import os
from datetime import datetime, timezone, timedelta


class TestSendErrorAlertWorking(unittest.TestCase):
    """Working tests that achieve actual coverage of send_error_alert.py"""

    def setUp(self):
        """Set up comprehensive mocking before any imports."""
        # Mock all external dependencies at module level
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.cloud': MagicMock(),
            'google.cloud.firestore': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'audit_logger': MagicMock()
        }

        # Mock pydantic Field
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)

        self.mock_modules['pydantic'].Field = mock_field

        # Mock BaseTool
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool

        # Mock Firestore
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_doc_ref = MagicMock()
        self.mock_doc = MagicMock()

        self.mock_collection.document.return_value = self.mock_doc_ref
        self.mock_doc_ref.get.return_value = self.mock_doc
        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_modules['google.cloud.firestore'].Client.return_value = self.mock_firestore_client

        # Mock environment functions
        self.mock_modules['env_loader'].get_required_env_var = MagicMock(return_value='test-project')
        self.mock_modules['loader'].load_app_config = MagicMock(return_value={'slack': {'channel': 'test-channel'}})
        self.mock_modules['loader'].get_config_value = MagicMock(return_value='test-channel')
        self.mock_modules['audit_logger'].audit_logger = MagicMock()

    def test_successful_error_alert_with_throttling_disabled(self):
        """Test successful error alert when throttling allows sending."""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock throttling check to return False (not throttled)
            self.mock_doc.exists = False  # No previous alert

            # Mock the internal tool classes
            mock_format_tool = MagicMock()
            mock_format_tool.return_value.run.return_value = '{"blocks": [{"type": "section"}]}'

            mock_send_tool = MagicMock()
            mock_send_tool.return_value.run.return_value = '{"status": "success", "timestamp": "123456789"}'

            with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks', mock_format_tool), \
                 patch('observability_agent.tools.send_error_alert.SendSlackMessage', mock_send_tool):

                # Now import and test the actual tool
                from observability_agent.tools.send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Test error message",
                    context={"type": "critical", "component": "test", "error_code": "500"}
                )

                result = tool.run()
                data = json.loads(result)

                # Verify successful execution
                self.assertEqual(data['status'], 'success')
                self.assertIn('alert_sent', data)

                # Verify internal tools were called
                mock_format_tool.assert_called_once()
                mock_send_tool.assert_called_once()

    def test_throttling_mechanism_blocks_alert(self):
        """Test throttling mechanism when alert was sent recently."""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock throttling check to return True (throttled)
            self.mock_doc.exists = True
            recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)  # 30 minutes ago
            self.mock_doc.to_dict.return_value = {
                'last_sent': recent_time,
                'alert_type': 'critical',
                'component': 'test'
            }

            with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks') as mock_format, \
                 patch('observability_agent.tools.send_error_alert.SendSlackMessage') as mock_send:

                from observability_agent.tools.send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Test error message",
                    context={"type": "critical", "component": "test"}
                )

                result = tool.run()
                data = json.loads(result)

                # Verify throttling worked
                self.assertEqual(data['status'], 'throttled')
                self.assertIn('throttled_until', data)

                # Verify tools were NOT called due to throttling
                mock_format.assert_not_called()
                mock_send.assert_not_called()

    def test_firestore_error_handling(self):
        """Test error handling when Firestore operations fail."""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock Firestore to raise an error
            self.mock_firestore_client.collection.side_effect = Exception("Firestore connection failed")

            with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks'), \
                 patch('observability_agent.tools.send_error_alert.SendSlackMessage'):

                from observability_agent.tools.send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Test error message",
                    context={"type": "error", "component": "test"}
                )

                result = tool.run()
                data = json.loads(result)

                # Verify error handling
                self.assertIn('error', data)
                self.assertIn('Firestore connection failed', data['message'])

    def test_slack_sending_error_handling(self):
        """Test error handling when Slack sending fails."""
        with patch.dict('sys.modules', self.mock_modules):
            self.mock_doc.exists = False  # No throttling

            mock_format_tool = MagicMock()
            mock_format_tool.return_value.run.return_value = '{"blocks": [{"type": "section"}]}'

            mock_send_tool = MagicMock()
            mock_send_tool.return_value.run.side_effect = Exception("Slack API error")

            with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks', mock_format_tool), \
                 patch('observability_agent.tools.send_error_alert.SendSlackMessage', mock_send_tool):

                from observability_agent.tools.send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Test error message",
                    context={"type": "warning", "component": "test"}
                )

                result = tool.run()
                data = json.loads(result)

                # Verify Slack error handling
                self.assertIn('error', data)
                self.assertIn('Slack API error', data['message'])

    def test_severity_mapping_and_alert_types(self):
        """Test different severity levels and alert type mapping."""
        with patch.dict('sys.modules', self.mock_modules):
            self.mock_doc.exists = False  # No throttling

            mock_format_tool = MagicMock()
            mock_format_tool.return_value.run.return_value = '{"blocks": [{"type": "section"}]}'

            mock_send_tool = MagicMock()
            mock_send_tool.return_value.run.return_value = '{"status": "success"}'

            with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks', mock_format_tool), \
                 patch('observability_agent.tools.send_error_alert.SendSlackMessage', mock_send_tool):

                from observability_agent.tools.send_error_alert import SendErrorAlert

                # Test different severity levels
                severities = ['critical', 'high', 'medium', 'low', 'info']

                for severity in severities:
                    with self.subTest(severity=severity):
                        tool = SendErrorAlert(
                            message=f"Test {severity} message",
                            context={"type": severity, "component": "test"}
                        )

                        result = tool.run()
                        data = json.loads(result)

                        self.assertEqual(data['status'], 'success')

    def test_context_processing_and_formatting(self):
        """Test context processing and formatting with various inputs."""
        with patch.dict('sys.modules', self.mock_modules):
            self.mock_doc.exists = False

            mock_format_tool = MagicMock()
            mock_format_tool.return_value.run.return_value = '{"blocks": [{"type": "section"}]}'

            mock_send_tool = MagicMock()
            mock_send_tool.return_value.run.return_value = '{"status": "success"}'

            with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks', mock_format_tool), \
                 patch('observability_agent.tools.send_error_alert.SendSlackMessage', mock_send_tool):

                from observability_agent.tools.send_error_alert import SendErrorAlert

                # Test with complex context
                complex_context = {
                    "type": "error",
                    "component": "transcriber_agent",
                    "error_code": "E001",
                    "details": {"file": "test.mp4", "duration": 1800},
                    "timestamp": "2025-09-15T14:30:00Z",
                    "user_id": "user123"
                }

                tool = SendErrorAlert(
                    message="Complex error scenario",
                    context=complex_context
                )

                result = tool.run()
                data = json.loads(result)

                self.assertEqual(data['status'], 'success')

                # Verify format tool was called with proper context
                format_call_args = mock_format_tool.call_args[1]
                self.assertIn('items', format_call_args)
                self.assertIn('alert_type', format_call_args)

    def test_audit_logging_integration(self):
        """Test audit logging integration."""
        with patch.dict('sys.modules', self.mock_modules):
            self.mock_doc.exists = False

            mock_format_tool = MagicMock()
            mock_format_tool.return_value.run.return_value = '{"blocks": [{"type": "section"}]}'

            mock_send_tool = MagicMock()
            mock_send_tool.return_value.run.return_value = '{"status": "success"}'

            with patch('observability_agent.tools.send_error_alert.FormatSlackBlocks', mock_format_tool), \
                 patch('observability_agent.tools.send_error_alert.SendSlackMessage', mock_send_tool):

                from observability_agent.tools.send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Test audit logging",
                    context={"type": "info", "component": "test_component"}
                )

                result = tool.run()

                # Verify audit logger was called
                self.mock_modules['audit_logger'].audit_logger.log_action.assert_called()


if __name__ == "__main__":
    unittest.main()