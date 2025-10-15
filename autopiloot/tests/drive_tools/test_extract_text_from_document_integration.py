#!/usr/bin/env python3
"""
Integration test for ExtractTextFromDocument tool
Uses the same mocking pattern as successful drive_agent tests
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports

class TestExtractTextFromDocumentIntegration(unittest.TestCase):
    """Integration test cases for ExtractTextFromDocument tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'extract_text_from_document' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_extract_text_tool_import_and_execution(self):
        """Test that the extract text tool can be imported and executed."""
        # Use the same pattern as test_drive_agent_init.py - patch.dict approach
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            # Mock pydantic.Field
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            # Mock BaseTool
            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock config loader
            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_text_length": 50000}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import using direct file loading to avoid __init__.py issues
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Test tool creation
                tool = ExtractTextFromDocument(
                    content="Sample plain text content",
                    mime_type="text/plain",
                    file_name="test.txt",
                    content_encoding="text",
                    max_length=10000
                )

                # Verify tool was created correctly
                self.assertEqual(tool.content, "Sample plain text content")
                self.assertEqual(tool.mime_type, "text/plain")
                self.assertEqual(tool.file_name, "test.txt")

                # Test execution
                result = tool.run()
                result_data = json.loads(result)

                # Verify result structure
                self.assertIn('extracted_text', result_data)
                self.assertIn('text_length', result_data)
                self.assertIn('file_info', result_data)

    def test_extract_text_with_csv_content(self):
        """Test CSV content extraction."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_text_length": 50000}}
                    return default
                mock_config.side_effect = mock_get_config

                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Test CSV content
                csv_content = "Name,Age,City\nJohn,30,NYC\nJane,25,LA"
                tool = ExtractTextFromDocument(
                    content=csv_content,
                    mime_type="text/csv",
                    file_name="test.csv",
                    content_encoding="text",
                    max_length=10000
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify CSV was processed
                self.assertIn('extracted_text', result_data)
                self.assertIn('text_length', result_data)

    def test_extract_text_with_base64_content(self):
        """Test base64 content extraction."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_text_length": 50000}}
                    return default
                mock_config.side_effect = mock_get_config

                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Test base64 content
                import base64
                original_text = "Hello, base64 world!"
                encoded_content = base64.b64encode(original_text.encode('utf-8')).decode('utf-8')

                tool = ExtractTextFromDocument(
                    content=encoded_content,
                    mime_type="text/plain",
                    file_name="test.txt",
                    content_encoding="base64",
                    max_length=10000
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify base64 was processed
                self.assertIn('extracted_text', result_data)
                self.assertIn('text_length', result_data)


if __name__ == '__main__':
    unittest.main()