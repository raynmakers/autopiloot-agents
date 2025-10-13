"""
Comprehensive test suite for SendRagErrorAlert tool.
Tests Slack alert formatting, error type classification, and integration with alert engine.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestSendRagErrorAlert(unittest.TestCase):
    """Test suite for SendRagErrorAlert tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'observability_agent',
            'tools',
            'send_rag_error_alert.py'
        )
        spec = importlib.util.spec_from_file_location("send_rag_error_alert", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.SendRagErrorAlert

        # Sample test data
        self.video_id = "test_video_123"
        self.operation = "zep_upsert"
        self.storage_system = "zep"
        self.error_message = "Connection timeout to Zep API"
        self.error_type = "connection"

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_successful_alert_sending(self, mock_import):
        """Test successful RAG error alert with Slack formatting (lines 71-171)."""
        # Mock loader module for config
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock FormatSlackBlocks and SendSlackMessage tools
        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            # Mock FormatSlackBlocks return value
            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            # Mock SendSlackMessage return value
            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            # Create tool instance
            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type
            )

            # Run tool
            result = tool.run()
            data = json.loads(result)

            # Assertions
            self.assertEqual(data['status'], 'sent')
            self.assertIn('ts', data)
            mock_format_blocks.assert_called_once()
            mock_send_message.assert_called_once()

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_alert_with_video_title(self, mock_import):
        """Test alert includes video title when provided (lines 95-100)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            # Create tool with video_title
            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type,
                video_title="How to Build a SaaS Business"
            )

            result = tool.run()
            data = json.loads(result)

            # Verify alert was sent
            self.assertEqual(data['status'], 'sent')

            # Check that FormatSlackBlocks was called with video title in fields
            call_args = mock_format_blocks.call_args
            items = call_args[1]['items']
            self.assertIn('Video Title', items['fields'])

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_alert_with_channel_id(self, mock_import):
        """Test alert includes channel_id when provided (lines 101-105)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            # Create tool with channel_id
            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type,
                channel_id="UCtest123"
            )

            result = tool.run()

            # Check that FormatSlackBlocks was called with channel_id in fields
            call_args = mock_format_blocks.call_args
            items = call_args[1]['items']
            self.assertIn('Channel ID', items['fields'])

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_alert_with_additional_context(self, mock_import):
        """Test alert includes additional context when provided (lines 106-113)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            # Create tool with additional_context
            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type,
                additional_context={"host": "api.getzep.com", "timeout": "30s"}
            )

            result = tool.run()

            # Check that FormatSlackBlocks was called with additional context
            call_args = mock_format_blocks.call_args
            items = call_args[1]['items']
            self.assertIn('Additional Context', items['fields'])

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_error_type_classification(self, mock_import):
        """Test different error types are properly classified (lines 88-93)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            # Test different error types
            error_types = ["connection", "authentication", "quota", "timeout", "unknown"]

            for error_type in error_types:
                tool = self.ToolClass(
                    video_id=self.video_id,
                    operation=self.operation,
                    storage_system=self.storage_system,
                    error_message=f"Test {error_type} error",
                    error_type=error_type
                )

                result = tool.run()
                data = json.loads(result)

                self.assertEqual(data['status'], 'sent')

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_storage_system_labels(self, mock_import):
        """Test different storage systems are properly labeled (lines 90)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            # Test different storage systems
            storage_systems = ["zep", "opensearch", "bigquery"]

            for storage_system in storage_systems:
                tool = self.ToolClass(
                    video_id=self.video_id,
                    operation=f"{storage_system}_operation",
                    storage_system=storage_system,
                    error_message=f"Test {storage_system} error",
                    error_type="connection"
                )

                result = tool.run()
                data = json.loads(result)

                self.assertEqual(data['status'], 'sent')

                # Verify storage system is uppercase in alert title
                call_args = mock_format_blocks.call_args
                items = call_args[1]['items']
                self.assertIn(storage_system.upper(), items['title'])

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_alert_severity_is_high(self, mock_import):
        """Test that RAG alerts are marked as high severity (lines 115)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type
            )

            result = tool.run()

            # Check severity in FormatSlackBlocks call
            call_args = mock_format_blocks.call_args
            items = call_args[1]['items']
            self.assertEqual(items['severity'], 'high')

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_alert_component_label(self, mock_import):
        """Test that component is labeled as RAG Ingestion Pipeline (lines 114)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type
            )

            result = tool.run()

            # Check component in FormatSlackBlocks call
            call_args = mock_format_blocks.call_args
            items = call_args[1]['items']
            self.assertEqual(items['component'], 'RAG Ingestion Pipeline')

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_slack_sending_error_handling(self, mock_import):
        """Test error handling when Slack message sending fails (lines 173-178)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            # Mock SendSlackMessage to raise exception
            mock_send_message.side_effect = Exception("Slack API error")

            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type
            )

            result = tool.run()
            data = json.loads(result)

            self.assertIn('error', data)
            self.assertIn('alert_failed', data['error'])

    @patch.dict(os.environ, {})
    def test_missing_slack_token(self):
        """Test graceful handling when SLACK_BOT_TOKEN is missing."""
        with patch('importlib.import_module') as mock_import:
            # Mock loader module
            mock_loader = MagicMock()
            mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
                'notifications.slack.channel': 'ops-autopiloot'
            }.get(key, default))

            mock_import.return_value = mock_loader

            with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
                 patch.object(self.module, 'SendSlackMessage') as mock_send_message:

                # Mock SendSlackMessage to fail due to missing token
                mock_send_message.side_effect = Exception("SLACK_BOT_TOKEN not configured")

                tool = self.ToolClass(
                    video_id=self.video_id,
                    operation=self.operation,
                    storage_system=self.storage_system,
                    error_message=self.error_message,
                    error_type=self.error_type
                )

                result = tool.run()
                data = json.loads(result)

                self.assertIn('error', data)

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_minimal_required_fields(self, mock_import):
        """Test alert with only required fields (no optional fields)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            # Create tool with only required fields
            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type
                # No video_title, channel_id, or additional_context
            )

            result = tool.run()
            data = json.loads(result)

            self.assertEqual(data['status'], 'sent')

    @patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'xoxb-test-token'
    })
    @patch('importlib.import_module')
    def test_alert_type_is_error(self, mock_import):
        """Test that alert_type is set to 'error' (lines 119)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default))

        mock_import.return_value = mock_loader

        with patch.object(self.module, 'FormatSlackBlocks') as mock_format_blocks, \
             patch.object(self.module, 'SendSlackMessage') as mock_send_message:

            mock_formatter = MagicMock()
            mock_formatter.run.return_value = json.dumps({'blocks': []})
            mock_format_blocks.return_value = mock_formatter

            mock_messenger = MagicMock()
            mock_messenger.run.return_value = json.dumps({'status': 'sent', 'ts': '1234567890.123'})
            mock_send_message.return_value = mock_messenger

            tool = self.ToolClass(
                video_id=self.video_id,
                operation=self.operation,
                storage_system=self.storage_system,
                error_message=self.error_message,
                error_type=self.error_type
            )

            result = tool.run()

            # Check alert_type in FormatSlackBlocks call
            call_args = mock_format_blocks.call_args
            alert_type = call_args[1]['alert_type']
            self.assertEqual(alert_type, 'error')


if __name__ == '__main__':
    unittest.main()
