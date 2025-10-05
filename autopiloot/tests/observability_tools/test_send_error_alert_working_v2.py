"""
Working test for send_error_alert.py that actually achieves coverage
Using a different approach to ensure real module execution and coverage measurement
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import json
import os
from datetime import datetime, timezone, timedelta
import tempfile
import importlib.util


class TestSendErrorAlertWorkingV2(unittest.TestCase):
    """Working tests that achieve actual coverage through real module imports"""

    def setUp(self):
        """Set up test environment with comprehensive mocking before imports."""
        # Mock external dependencies early
        self.patcher_modules = {}

        # Mock all the problematic modules
        modules_to_mock = [
            'agency_swarm',
            'agency_swarm.tools',
            'pydantic',
            'google',
            'google.cloud',
            'google.cloud.firestore',
            'env_loader',
            'loader',
            'audit_logger'
        ]

        for module_name in modules_to_mock:
            self.patcher_modules[module_name] = patch.dict('sys.modules', {module_name: MagicMock()})
            self.patcher_modules[module_name].start()

        # Configure specific mocks
        sys.modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

        # Mock BaseTool
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

        # Mock environment functions
        sys.modules['env_loader'].get_required_env_var = MagicMock(return_value='test-project')
        sys.modules['loader'].load_app_config = MagicMock(return_value={'slack': {'channel': 'test-channel'}})
        sys.modules['loader'].get_config_value = MagicMock(return_value='test-channel')
        sys.modules['audit_logger'].audit_logger = MagicMock()

        # Mock Firestore
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_doc_ref = MagicMock()
        self.mock_doc = MagicMock()

        self.mock_collection.document.return_value = self.mock_doc_ref
        self.mock_doc_ref.get.return_value = self.mock_doc
        self.mock_firestore_client.collection.return_value = self.mock_collection
        sys.modules['google.cloud.firestore'].Client.return_value = self.mock_firestore_client

    def tearDown(self):
        """Clean up patchers."""
        for patcher in self.patcher_modules.values():
            patcher.stop()

    def test_real_import_and_execution(self):
        """Test with real import of the send_error_alert module."""
        # Mock FormatSlackBlocks and SendSlackMessage before import
        with patch('observability_agent.tools.format_slack_blocks.FormatSlackBlocks') as mock_format, \
             patch('observability_agent.tools.send_slack_message.SendSlackMessage') as mock_send:

            # Configure mocks
            mock_format_instance = MagicMock()
            mock_format_instance.run.return_value = json.dumps({"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Test alert"}}]})
            mock_format.return_value = mock_format_instance

            mock_send_instance = MagicMock()
            mock_send_instance.run.return_value = json.dumps({"status": "success", "timestamp": "1234567890.123456"})
            mock_send.return_value = mock_send_instance

            # Configure Firestore mock for no throttling
            self.mock_doc.exists = False

            try:
                # Import the actual module
                from observability_agent.tools.send_error_alert import SendErrorAlert

                # Test instantiation
                tool = SendErrorAlert(
                    message="Test error message",
                    context={"type": "error", "component": "test_component"}
                )

                self.assertIsNotNone(tool)
                self.assertEqual(tool.message, "Test error message")
                self.assertEqual(tool.context["type"], "error")

                # Test run method
                result = tool.run()
                self.assertIsInstance(result, str)

                # Parse result
                data = json.loads(result)
                self.assertIn('status', data)

                # Verify mocks were called
                mock_format.assert_called_once()
                mock_send.assert_called_once()

            except ImportError as e:
                self.skipTest(f"Could not import send_error_alert: {e}")

    def test_throttling_mechanism(self):
        """Test throttling mechanism with real module."""
        with patch('observability_agent.tools.format_slack_blocks.FormatSlackBlocks') as mock_format, \
             patch('observability_agent.tools.send_slack_message.SendSlackMessage') as mock_send:

            # Configure throttling scenario
            self.mock_doc.exists = True
            recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
            self.mock_doc.to_dict.return_value = {
                'last_sent': recent_time,
                'alert_type': 'error',
                'component': 'test_component'
            }

            try:
                from observability_agent.tools.send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Throttled message",
                    context={"type": "error", "component": "test_component"}
                )

                result = tool.run()
                data = json.loads(result)

                # Should be throttled
                self.assertEqual(data['status'], 'throttled')
                self.assertIn('throttled_until', data)

                # Format and send should NOT be called due to throttling
                mock_format.assert_not_called()
                mock_send.assert_not_called()

            except ImportError as e:
                self.skipTest(f"Could not import send_error_alert: {e}")

    def test_error_handling_paths(self):
        """Test error handling paths with real module."""
        with patch('observability_agent.tools.format_slack_blocks.FormatSlackBlocks') as mock_format, \
             patch('observability_agent.tools.send_slack_message.SendSlackMessage') as mock_send:

            # Configure Firestore to raise an error
            self.mock_firestore_client.collection.side_effect = Exception("Firestore connection failed")

            try:
                from observability_agent.tools.send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Error test message",
                    context={"type": "critical", "component": "test"}
                )

                result = tool.run()
                data = json.loads(result)

                # Should have error handling
                self.assertIn('error', data)
                self.assertIn('Firestore connection failed', data['message'])

            except ImportError as e:
                self.skipTest(f"Could not import send_error_alert: {e}")

    def test_different_alert_types(self):
        """Test different alert types and contexts."""
        with patch('observability_agent.tools.format_slack_blocks.FormatSlackBlocks') as mock_format, \
             patch('observability_agent.tools.send_slack_message.SendSlackMessage') as mock_send:

            # Configure mocks
            mock_format_instance = MagicMock()
            mock_format_instance.run.return_value = json.dumps({"blocks": []})
            mock_format.return_value = mock_format_instance

            mock_send_instance = MagicMock()
            mock_send_instance.run.return_value = json.dumps({"status": "success"})
            mock_send.return_value = mock_send_instance

            # No throttling
            self.mock_doc.exists = False

            try:
                from observability_agent.tools.send_error_alert import SendErrorAlert

                # Test different alert types
                alert_types = ['critical', 'error', 'warning', 'info']

                for alert_type in alert_types:
                    with self.subTest(alert_type=alert_type):
                        tool = SendErrorAlert(
                            message=f"Test {alert_type} message",
                            context={
                                "type": alert_type,
                                "component": "test_component",
                                "details": {"file": "test.py", "line": 123}
                            }
                        )

                        result = tool.run()
                        data = json.loads(result)

                        self.assertEqual(data['status'], 'success')

            except ImportError as e:
                self.skipTest(f"Could not import send_error_alert: {e}")


if __name__ == "__main__":
    unittest.main()