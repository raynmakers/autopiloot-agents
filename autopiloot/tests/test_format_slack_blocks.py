"""
Test suite for FormatSlackBlocks tool.
Tests TASK-AST-0040 implementation including block formatting, alert types, and message structure.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from observability_agent.tools.format_slack_blocks import FormatSlackBlocks
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'observability_agent', 
        'tools', 
        'format_slack_blocks.py'
    )
    spec = importlib.util.spec_from_file_location("FormatSlackBlocks", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    FormatSlackBlocks = module.FormatSlackBlocks


class TestFormatSlackBlocks(unittest.TestCase):
    """Test cases for FormatSlackBlocks tool TASK-AST-0040."""

    def test_budget_alert_formatting(self):
        """Test that budget alerts are properly formatted with correct structure."""
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
        
        # Verify structure
        self.assertIn("blocks", data)
        blocks = data["blocks"]
        
        # Check header block
        header_block = blocks[0]
        self.assertEqual(header_block["type"], "header")
        self.assertIn("💰 Budget Alert", header_block["text"]["text"])
        
        # Check message block
        message_block = blocks[1]
        self.assertEqual(message_block["type"], "section")
        self.assertIn("threshold reached", message_block["text"]["text"])
        
        # Check fields block
        fields_block = blocks[2]
        self.assertEqual(fields_block["type"], "section")
        self.assertEqual(len(fields_block["fields"]), 4)
        
        print("✅ Budget alert formatting test passed")

    def test_error_alert_formatting(self):
        """Test that error alerts are properly formatted with correct styling."""
        tool = FormatSlackBlocks(
            items={
                "title": "Transcription Failed",
                "message": "AssemblyAI job failed after 3 retry attempts",
                "fields": {
                    "Video ID": "xyz123",
                    "Error": "API timeout",
                    "Attempts": "3/3"
                },
                "timestamp": "2025-09-15T14:45:00Z",
                "component": "TranscriberAgent"
            },
            alert_type="error"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        blocks = data["blocks"]
        
        # Check error emoji in header
        header_block = blocks[0]
        self.assertIn("🚨", header_block["text"]["text"])
        self.assertIn("Error Alert", header_block["text"]["text"])
        
        # Check fields are present
        fields_block = blocks[2]
        self.assertEqual(len(fields_block["fields"]), 3)
        
        # Verify field content
        field_texts = [field["text"] for field in fields_block["fields"]]
        self.assertTrue(any("xyz123" in text for text in field_texts))
        self.assertTrue(any("API timeout" in text for text in field_texts))
        
        print("✅ Error alert formatting test passed")

    def test_info_alert_formatting(self):
        """Test that info alerts use correct styling and structure."""
        tool = FormatSlackBlocks(
            items={
                "title": "System Status",
                "message": "All systems operational",
                "fields": {
                    "Status": "OK",
                    "Uptime": "99.9%"
                }
            },
            alert_type="info"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        blocks = data["blocks"]
        header_block = blocks[0]
        self.assertIn("ℹ️", header_block["text"]["text"])
        
        print("✅ Info alert formatting test passed")

    def test_warning_alert_formatting(self):
        """Test that warning alerts use correct styling."""
        tool = FormatSlackBlocks(
            items={
                "title": "Resource Warning",
                "message": "High resource usage detected"
            },
            alert_type="warning"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        blocks = data["blocks"]
        header_block = blocks[0]
        self.assertIn("⚠️", header_block["text"]["text"])
        
        print("✅ Warning alert formatting test passed")

    def test_success_alert_formatting(self):
        """Test that success alerts use correct styling."""
        tool = FormatSlackBlocks(
            items={
                "title": "Processing Complete",
                "message": "All tasks completed successfully"
            },
            alert_type="success"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        blocks = data["blocks"]
        header_block = blocks[0]
        self.assertIn("✅", header_block["text"]["text"])
        
        print("✅ Success alert formatting test passed")

    def test_context_footer_with_timestamp_and_component(self):
        """Test that context footer includes timestamp and component when provided."""
        tool = FormatSlackBlocks(
            items={
                "title": "Test Alert",
                "message": "Test message",
                "timestamp": "2025-09-15T15:30:00Z",
                "component": "TestComponent"
            },
            alert_type="info"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        blocks = data["blocks"]
        
        # Find context block
        context_block = None
        for block in blocks:
            if block.get("type") == "context":
                context_block = block
                break
        
        self.assertIsNotNone(context_block)
        elements = context_block["elements"]
        
        # Check timestamp and component are in elements
        element_texts = [elem["text"] for elem in elements]
        self.assertTrue(any("🕒 2025-09-15T15:30:00Z" in text for text in element_texts))
        self.assertTrue(any("📍 TestComponent" in text for text in element_texts))
        
        print("✅ Context footer test passed")

    def test_divider_block_present(self):
        """Test that divider block is included in formatted output."""
        tool = FormatSlackBlocks(
            items={"title": "Test", "message": "Test"},
            alert_type="info"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        blocks = data["blocks"]
        divider_blocks = [block for block in blocks if block.get("type") == "divider"]
        self.assertEqual(len(divider_blocks), 1)
        
        print("✅ Divider block test passed")

    def test_minimal_items_structure(self):
        """Test formatting with minimal required items."""
        tool = FormatSlackBlocks(
            items={"title": "Minimal Test"},
            alert_type="info"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should still have proper structure
        self.assertIn("blocks", data)
        blocks = data["blocks"]
        self.assertGreater(len(blocks), 0)
        
        # Header should be present
        header_block = blocks[0]
        self.assertEqual(header_block["type"], "header")
        
        print("✅ Minimal items test passed")

    def test_empty_fields_handling(self):
        """Test handling of empty fields dictionary."""
        tool = FormatSlackBlocks(
            items={
                "title": "Test",
                "message": "Test message",
                "fields": {}
            },
            alert_type="info"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should not crash with empty fields
        self.assertIn("blocks", data)
        
        print("✅ Empty fields handling test passed")

    def test_error_handling_invalid_items(self):
        """Test error handling with invalid items structure."""
        tool = FormatSlackBlocks(
            items=None,  # Invalid items
            alert_type="info"
        )
        
        with self.assertRaises(RuntimeError):
            tool.run()
        
        print("✅ Error handling test passed")

    def test_unknown_alert_type_fallback(self):
        """Test fallback behavior for unknown alert types."""
        tool = FormatSlackBlocks(
            items={"title": "Test"},
            alert_type="unknown_type"
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Should fallback to info styling
        blocks = data["blocks"]
        header_block = blocks[0]
        self.assertIn("ℹ️", header_block["text"]["text"])
        
        print("✅ Unknown alert type fallback test passed")

    def test_json_output_structure(self):
        """Test that output is valid JSON with correct structure."""
        tool = FormatSlackBlocks(
            items={
                "title": "JSON Test",
                "message": "Testing JSON structure"
            },
            alert_type="info"
        )
        
        result = tool.run()
        
        # Should be valid JSON
        data = json.loads(result)
        
        # Should have blocks key
        self.assertIn("blocks", data)
        self.assertIsInstance(data["blocks"], list)
        
        # Each block should have type
        for block in data["blocks"]:
            self.assertIn("type", block)
        
        print("✅ JSON output structure test passed")


if __name__ == '__main__':
    unittest.main()