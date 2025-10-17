"""
Simple test for send_error_alert.py that achieves actual coverage
Using minimal mocking and direct module execution
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json
import os


class TestSendErrorAlertFirstTime(unittest.TestCase):
    """Simple test that should achieve actual coverage"""

    def test_successful_error_alert_first_time(self):
        """Test successful error alert execution with minimal setup."""
        # Add path setup
        # Mock only the essential external dependencies
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google.cloud.firestore': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'audit_logger': MagicMock()
        }):
            # Configure the mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
            sys.modules['env_loader'].get_required_env_var = MagicMock(return_value='test-project')
            sys.modules['loader'].load_app_config = MagicMock(return_value={'slack': {'channel': 'test'}})
            sys.modules['loader'].get_config_value = MagicMock(return_value='test')
            sys.modules['audit_logger'].audit_logger = MagicMock()

            # Mock Firestore
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_doc_ref = MagicMock()
            mock_doc = MagicMock()

            mock_doc.exists = False  # No throttling
            mock_doc_ref.get.return_value = mock_doc
            mock_collection.document.return_value = mock_doc_ref
            mock_client.collection.return_value = mock_collection
            sys.modules['google.cloud.firestore'].Client.return_value = mock_client

            # Mock the internal tools
            with patch('format_slack_blocks.FormatSlackBlocks') as mock_format, \
                 patch('send_slack_message.SendSlackMessage') as mock_send:

                mock_format_instance = MagicMock()
                mock_format_instance.run.return_value = '{"blocks": []}'
                mock_format.return_value = mock_format_instance

                mock_send_instance = MagicMock()
                mock_send_instance.run.return_value = '{"status": "success"}'
                mock_send.return_value = mock_send_instance

                # Now import and test
                from send_error_alert import SendErrorAlert

                tool = SendErrorAlert(
                    message="Test error",
                    context={"type": "error", "component": "test"}
                )

                self.assertIsNotNone(tool)

                # Test run method
                result = tool.run()
                self.assertIsInstance(result, str)

                # Parse result
                data = json.loads(result)
                self.assertIn('status', data)


if __name__ == "__main__":
    unittest.main()