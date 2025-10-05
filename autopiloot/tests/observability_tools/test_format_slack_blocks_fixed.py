"""
Comprehensive test for format_slack_blocks.py - targeting 100% coverage
Generated automatically by Claude when coverage < 75%

Current coverage: 94% (33 lines, 2 missing)
Missing lines: 107-108 (exception handling)

Target: 100% coverage through comprehensive testing including error paths
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json

class TestFormatSlackBlocksFixed(unittest.TestCase):
    """Comprehensive tests for 100% coverage of format_slack_blocks.py"""

    def setUp(self):
        """Set up test environment with comprehensive mocking."""
        # Mock Agency Swarm v1.0.0 components
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock()
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

    def test_successful_budget_alert_formatting(self):
        """Test successful formatting of budget alert blocks."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={
                    "title": "Budget Alert",
                    "message": "Transcription budget threshold reached",
                    "fields": {
                        "Daily Budget": "$5.00",
                        "Amount Spent": "$4.10",
                        "Usage": "82%",
                        "Remaining": "$0.90"
                    },
                    "timestamp": "2025-09-15T14:30:00Z",
                    "component": "MonitorTranscriptionBudget"
                },
                alert_type="budget"
            )

            result = tool.run()
            data = json.loads(result)

            # Verify block structure
            self.assertIn("blocks", data)
            blocks = data["blocks"]

            # Verify header block
            self.assertEqual(blocks[0]["type"], "header")
            self.assertIn("💰", blocks[0]["text"]["text"])
            self.assertIn("Budget Alert", blocks[0]["text"]["text"])

            # Verify message section
            self.assertEqual(blocks[1]["type"], "section")
            self.assertEqual(blocks[1]["text"]["text"], "Transcription budget threshold reached")

            # Verify fields section
            self.assertEqual(blocks[2]["type"], "section")
            self.assertEqual(len(blocks[2]["fields"]), 4)

            # Verify divider
            self.assertEqual(blocks[3]["type"], "divider")

            # Verify context footer
            self.assertEqual(blocks[4]["type"], "context")
            self.assertEqual(len(blocks[4]["elements"]), 2)

    def test_error_alert_formatting(self):
        """Test error alert formatting with all alert types."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={
                    "title": "Critical Error",
                    "message": "System failure detected",
                    "fields": {
                        "Error Code": "500",
                        "Component": "API Gateway",
                        "Severity": "CRITICAL"
                    },
                    "timestamp": "2025-09-15T14:45:00Z",
                    "component": "TranscriberAgent"
                },
                alert_type="error"
            )

            result = tool.run()
            data = json.loads(result)

            # Verify error alert styling
            blocks = data["blocks"]
            self.assertIn("🚨", blocks[0]["text"]["text"])
            self.assertIn("Critical Error", blocks[0]["text"]["text"])

    def test_all_alert_types(self):
        """Test all supported alert types."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            alert_types = ["info", "warning", "error", "budget", "success"]
            expected_emojis = ["ℹ️", "⚠️", "🚨", "💰", "✅"]

            for alert_type, expected_emoji in zip(alert_types, expected_emojis):
                tool = FormatSlackBlocks(
                    items={"title": f"Test {alert_type}", "message": "Test message"},
                    alert_type=alert_type
                )

                result = tool.run()
                data = json.loads(result)

                # Verify correct emoji for alert type
                header_text = data["blocks"][0]["text"]["text"]
                self.assertIn(expected_emoji, header_text)

    def test_unknown_alert_type_defaults_to_info(self):
        """Test that unknown alert types default to info styling."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={"title": "Unknown Alert", "message": "Test message"},
                alert_type="unknown_type"
            )

            result = tool.run()
            data = json.loads(result)

            # Should default to info styling
            header_text = data["blocks"][0]["text"]["text"]
            self.assertIn("ℹ️", header_text)

    def test_minimal_items_no_optional_fields(self):
        """Test formatting with minimal items (no fields, timestamp, component)."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={"message": "Simple message"},
                alert_type="info"
            )

            result = tool.run()
            data = json.loads(result)

            blocks = data["blocks"]
            # Should have: header, message, divider (no fields or context)
            self.assertEqual(len(blocks), 3)
            self.assertEqual(blocks[0]["type"], "header")
            self.assertEqual(blocks[1]["type"], "section")
            self.assertEqual(blocks[2]["type"], "divider")

    def test_no_message_field(self):
        """Test formatting without message field."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={"title": "No Message Test"},
                alert_type="info"
            )

            result = tool.run()
            data = json.loads(result)

            blocks = data["blocks"]
            # Should have: header, divider (no message section)
            self.assertEqual(len(blocks), 2)
            self.assertEqual(blocks[0]["type"], "header")
            self.assertEqual(blocks[1]["type"], "divider")

    def test_empty_fields_not_included(self):
        """Test that empty fields are not included in blocks."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={
                    "title": "Empty Fields Test",
                    "message": "Test message",
                    "fields": {}  # Empty fields
                },
                alert_type="info"
            )

            result = tool.run()
            data = json.loads(result)

            blocks = data["blocks"]
            # Should not include fields section when fields is empty
            block_types = [block["type"] for block in blocks]
            self.assertNotIn("fields", str(blocks))
            self.assertEqual(len(blocks), 3)  # header, message, divider

    def test_context_with_only_timestamp(self):
        """Test context section with only timestamp."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={
                    "message": "Test message",
                    "timestamp": "2025-09-15T14:30:00Z"
                    # No component
                },
                alert_type="info"
            )

            result = tool.run()
            data = json.loads(result)

            blocks = data["blocks"]
            # Should have context with only timestamp
            context_block = blocks[-1]
            self.assertEqual(context_block["type"], "context")
            self.assertEqual(len(context_block["elements"]), 1)
            self.assertIn("🕒", context_block["elements"][0]["text"])

    def test_context_with_only_component(self):
        """Test context section with only component."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={
                    "message": "Test message",
                    "component": "TestAgent"
                    # No timestamp
                },
                alert_type="info"
            )

            result = tool.run()
            data = json.loads(result)

            blocks = data["blocks"]
            # Should have context with only component
            context_block = blocks[-1]
            self.assertEqual(context_block["type"], "context")
            self.assertEqual(len(context_block["elements"]), 1)
            self.assertIn("📍", context_block["elements"][0]["text"])

    def test_exception_handling_lines_107_108(self):
        """Test exception handling in run method (lines 107-108)."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={"message": "Test message"},
                alert_type="info"
            )

            # Mock json.dumps to raise an exception
            with patch('observability_agent.tools.format_slack_blocks.json.dumps') as mock_dumps:
                mock_dumps.side_effect = Exception("JSON serialization failed")

                # Test that exception is caught and re-raised as RuntimeError
                with self.assertRaises(RuntimeError) as context:
                    tool.run()

                # Verify exception message format (lines 107-108)
                self.assertIn("Failed to format Slack blocks", str(context.exception))
                self.assertIn("JSON serialization failed", str(context.exception))

    def test_complex_field_formatting(self):
        """Test complex field formatting with special characters."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            tool = FormatSlackBlocks(
                items={
                    "title": "Complex Field Test",
                    "message": "Testing special characters",
                    "fields": {
                        "Field with spaces": "Value with spaces",
                        "Field_with_underscore": "Value_with_underscore",
                        "Field-with-dash": "Value-with-dash",
                        "Number Field": 12345,
                        "Boolean Field": True
                    }
                },
                alert_type="info"
            )

            result = tool.run()
            data = json.loads(result)

            # Verify all fields are properly formatted
            fields_block = data["blocks"][2]
            self.assertEqual(len(fields_block["fields"]), 5)

            # Check that each field has proper markdown formatting
            for field in fields_block["fields"]:
                self.assertIn("*", field["text"])  # Should have bold formatting
                self.assertIn(":", field["text"])   # Should have colon separator

    def test_default_field_behavior(self):
        """Test default alert_type field behavior."""
        with patch.dict('sys.modules', self.mock_modules):
            from observability_agent.tools.format_slack_blocks import FormatSlackBlocks

            # Test with no alert_type specified (should default to "info")
            tool = FormatSlackBlocks(items={"message": "Default test"})

            result = tool.run()
            data = json.loads(result)

            # Should use info styling by default
            header_text = data["blocks"][0]["text"]["text"]
            self.assertIn("ℹ️", header_text)
            self.assertIn("Information", header_text)


if __name__ == "__main__":
    unittest.main()