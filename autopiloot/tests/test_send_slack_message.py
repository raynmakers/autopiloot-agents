"""
Test suite for SendSlackMessage tool.
Tests TASK-AST-0040 implementation including Slack API integration, block formatting, and configuration loading.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from observability_agent.tools.send_slack_message import SendSlackMessage
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'observability_agent', 
        'tools', 
        'send_slack_message.py'
    )
    spec = importlib.util.spec_from_file_location("SendSlackMessage", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SendSlackMessage = module.SendSlackMessage


class TestSendSlackMessage(unittest.TestCase):
    """Test cases for SendSlackMessage tool TASK-AST-0040."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_blocks = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "💰 Budget Alert"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Daily transcription budget has reached 85% usage."
                    }
                }
            ]
        }

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    @patch('observability_agent.tools.send_slack_message.WebClient')
    def test_successful_message_sending(self, mock_webclient, mock_config, mock_env):
        """Test successful Slack message sending with blocks."""
        # Mock environment and configuration
        mock_env.return_value = "test-slack-token"
        mock_config.return_value = {"notifications": {"slack": {"channel": "ops-autopiloot"}}}
        
        # Mock Slack client and response
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client
        mock_response = {"ok": True, "ts": "1234567890.123"}
        mock_client.chat_postMessage.return_value = mock_response
        
        tool = SendSlackMessage(
            channel="#test-channel",
            blocks=self.test_blocks
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify successful response structure
        self.assertIn("ts", data)
        self.assertIn("channel", data)
        self.assertEqual(data["ts"], "1234567890.123")
        self.assertEqual(data["channel"], "#test-channel")
        
        # Verify Slack API was called correctly
        mock_client.chat_postMessage.assert_called_once()
        call_args = mock_client.chat_postMessage.call_args
        self.assertEqual(call_args.kwargs["channel"], "#test-channel")
        self.assertEqual(call_args.kwargs["blocks"], self.test_blocks["blocks"])
        
        print("✅ Successful message sending test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    @patch('observability_agent.tools.send_slack_message.WebClient')
    def test_configuration_channel_fallback(self, mock_webclient, mock_config, mock_env):
        """Test fallback to configured channel when no channel provided."""
        # Mock environment and configuration
        mock_env.return_value = "test-slack-token"
        mock_config.return_value = {"notifications": {"slack": {"channel": "ops-autopiloot"}}}
        
        # Mock Slack client and response
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client
        mock_response = {"ok": True, "ts": "1234567890.123"}
        mock_client.chat_postMessage.return_value = mock_response
        
        tool = SendSlackMessage(
            channel="",  # Empty channel to trigger fallback
            blocks=self.test_blocks
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should use configured channel with # prefix
        self.assertEqual(data["channel"], "#ops-autopiloot")
        
        # Verify API call used configured channel
        call_args = mock_client.chat_postMessage.call_args
        self.assertEqual(call_args.kwargs["channel"], "#ops-autopiloot")
        
        print("✅ Configuration channel fallback test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    def test_missing_slack_token_error(self, mock_config, mock_env):
        """Test error handling when Slack token is missing."""
        # Mock missing environment variable
        mock_env.side_effect = ValueError("SLACK_BOT_TOKEN environment variable is required")
        mock_config.return_value = {}
        
        tool = SendSlackMessage(
            channel="#test",
            blocks=self.test_blocks
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should return error response
        self.assertIn("error", data)
        self.assertIn("SLACK_BOT_TOKEN", data["error"])
        
        print("✅ Missing Slack token error test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    @patch('observability_agent.tools.send_slack_message.WebClient')
    def test_slack_api_error_handling(self, mock_webclient, mock_config, mock_env):
        """Test handling of Slack API errors."""
        # Mock environment and configuration
        mock_env.return_value = "test-slack-token"
        mock_config.return_value = {}
        
        # Mock Slack client with API error
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client
        mock_response = {"ok": False, "error": "channel_not_found"}
        mock_client.chat_postMessage.return_value = mock_response
        
        tool = SendSlackMessage(
            channel="#nonexistent",
            blocks=self.test_blocks
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should return error response
        self.assertIn("error", data)
        self.assertIn("channel_not_found", data["error"])
        
        print("✅ Slack API error handling test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    @patch('observability_agent.tools.send_slack_message.WebClient')
    def test_fallback_text_extraction(self, mock_webclient, mock_config, mock_env):
        """Test extraction of fallback text from blocks."""
        # Mock environment and configuration
        mock_env.return_value = "test-slack-token"
        mock_config.return_value = {}
        
        # Mock Slack client
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client
        mock_response = {"ok": True, "ts": "1234567890.123"}
        mock_client.chat_postMessage.return_value = mock_response
        
        tool = SendSlackMessage(
            channel="#test",
            blocks=self.test_blocks
        )
        
        tool.run()
        
        # Verify fallback text was included
        call_args = mock_client.chat_postMessage.call_args
        self.assertIn("text", call_args.kwargs)
        self.assertIn("Budget Alert", call_args.kwargs["text"])
        
        print("✅ Fallback text extraction test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    @patch('observability_agent.tools.send_slack_message.WebClient')
    def test_empty_blocks_handling(self, mock_webclient, mock_config, mock_env):
        """Test handling of empty blocks array."""
        # Mock environment and configuration
        mock_env.return_value = "test-slack-token"
        mock_config.return_value = {}
        
        # Mock Slack client
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client
        mock_response = {"ok": True, "ts": "1234567890.123"}
        mock_client.chat_postMessage.return_value = mock_response
        
        tool = SendSlackMessage(
            channel="#test",
            blocks={"blocks": []}
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should still succeed with empty blocks
        self.assertIn("ts", data)
        
        print("✅ Empty blocks handling test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    @patch('observability_agent.tools.send_slack_message.WebClient')
    def test_network_error_handling(self, mock_webclient, mock_config, mock_env):
        """Test handling of network errors during API call."""
        # Mock environment and configuration
        mock_env.return_value = "test-slack-token"
        mock_config.return_value = {}
        
        # Mock Slack client with network error
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client
        mock_client.chat_postMessage.side_effect = Exception("Network timeout")
        
        tool = SendSlackMessage(
            channel="#test",
            blocks=self.test_blocks
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should return error response
        self.assertIn("error", data)
        self.assertIn("Network timeout", data["error"])
        
        print("✅ Network error handling test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    def test_configuration_loading_failure(self, mock_config, mock_env):
        """Test graceful handling of configuration loading failures."""
        # Mock environment and configuration failure
        mock_env.return_value = "test-slack-token"
        mock_config.side_effect = Exception("Config file not found")
        
        with patch('observability_agent.tools.send_slack_message.WebClient') as mock_webclient:
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_response = {"ok": True, "ts": "1234567890.123"}
            mock_client.chat_postMessage.return_value = mock_response
            
            tool = SendSlackMessage(
                channel="#test",
                blocks=self.test_blocks
            )
            
            result = tool.run()
            data = json.loads(result)
            
            # Should still work with default fallback
            self.assertIn("ts", data)
        
        print("✅ Configuration loading failure test passed")

    @patch('observability_agent.tools.send_slack_message.get_required_env_var')
    @patch('observability_agent.tools.send_slack_message.load_app_config')
    @patch('observability_agent.tools.send_slack_message.WebClient')
    def test_channel_prefix_handling(self, mock_webclient, mock_config, mock_env):
        """Test proper handling of channel prefixes."""
        # Mock environment and configuration
        mock_env.return_value = "test-slack-token"
        mock_config.return_value = {"notifications": {"slack": {"channel": "ops-autopiloot"}}}
        
        # Mock Slack client
        mock_client = MagicMock()
        mock_webclient.return_value = mock_client
        mock_response = {"ok": True, "ts": "1234567890.123"}
        mock_client.chat_postMessage.return_value = mock_response
        
        # Test with channel that needs # prefix
        tool = SendSlackMessage(
            channel="test-channel",  # No # prefix
            blocks=self.test_blocks
        )
        
        tool.run()
        
        # Should use the channel as provided (no automatic # addition since it's provided)
        call_args = mock_client.chat_postMessage.call_args
        self.assertEqual(call_args.kwargs["channel"], "test-channel")
        
        print("✅ Channel prefix handling test passed")

    def test_response_structure_compliance(self):
        """Test that response structure matches SendSlackMessageResponse TypedDict."""
        with patch('observability_agent.tools.send_slack_message.get_required_env_var') as mock_env, \
             patch('observability_agent.tools.send_slack_message.load_app_config') as mock_config, \
             patch('observability_agent.tools.send_slack_message.WebClient') as mock_webclient:
            
            # Mock successful response
            mock_env.return_value = "test-token"
            mock_config.return_value = {}
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_response = {"ok": True, "ts": "1234567890.123"}
            mock_client.chat_postMessage.return_value = mock_response
            
            tool = SendSlackMessage(
                channel="#test",
                blocks=self.test_blocks
            )
            
            result = tool.run()
            data = json.loads(result)
            
            # Verify required fields from SendSlackMessageResponse TypedDict
            self.assertIn("ts", data)
            self.assertIn("channel", data)
            self.assertIsInstance(data["ts"], str)
            self.assertIsInstance(data["channel"], str)
            
        print("✅ Response structure compliance test passed")


if __name__ == '__main__':
    unittest.main()