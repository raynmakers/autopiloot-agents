"""
Test for format_slack_blocks.py targeting 100% coverage
Specifically covers lines 107-108 (exception handling)
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json


class TestFormatSlackBlocks100Coverage(unittest.TestCase):
    """Tests to achieve 100% coverage for format_slack_blocks.py"""

    def test_exception_handling_lines_107_108(self):
        """Test exception handling in run method to cover lines 107-108."""
        # Add path setup
        sys.path.insert(0, '.')
        sys.path.insert(0, 'observability_agent/tools')

        # Mock only the essential external dependencies
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock()
        }):
            # Configure the mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import the tool
            from format_slack_blocks import FormatSlackBlocks

            # Create a tool instance
            tool = FormatSlackBlocks(
                items={"message": "Test message"},
                alert_type="error"
            )

            # Mock json.dumps to raise an exception
            with patch('json.dumps', side_effect=Exception("JSON serialization failed")):
                # This should trigger the exception handler on lines 107-108
                with self.assertRaises(RuntimeError) as context:
                    tool.run()

                # Verify the exception message
                self.assertIn("Failed to format Slack blocks", str(context.exception))
                self.assertIn("JSON serialization failed", str(context.exception))

    def test_successful_execution_with_all_fields(self):
        """Test successful execution with all possible fields to ensure full coverage."""
        # Add path setup
        sys.path.insert(0, '.')
        sys.path.insert(0, 'observability_agent/tools')

        # Mock dependencies
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock()
        }):
            # Configure mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import the tool
            from format_slack_blocks import FormatSlackBlocks

            # Create a tool instance with all fields
            tool = FormatSlackBlocks(
                items={
                    "message": "Test message",
                    "details": "Test details",
                    "error_code": "E001",
                    "stack_trace": "Test stack trace"
                },
                alert_type="critical",
                fields=["Field 1", "Field 2"],
                timestamp="2024-01-01T12:00:00Z",
                component="test_component"
            )

            # Run the tool
            result = tool.run()

            # Verify it returns valid JSON
            data = json.loads(result)
            self.assertIn("blocks", data)
            self.assertIsInstance(data["blocks"], list)
            self.assertGreater(len(data["blocks"]), 0)

    def test_minimal_execution_with_defaults(self):
        """Test minimal execution path with default values."""
        # Add path setup
        sys.path.insert(0, '.')
        sys.path.insert(0, 'observability_agent/tools')

        # Mock dependencies
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock()
        }):
            # Configure mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import the tool
            from format_slack_blocks import FormatSlackBlocks

            # Create a tool instance with minimal required fields
            tool = FormatSlackBlocks(
                items={"message": "Minimal test"}
            )

            # Run the tool
            result = tool.run()

            # Verify it returns valid JSON
            data = json.loads(result)
            self.assertIn("blocks", data)


if __name__ == "__main__":
    unittest.main()