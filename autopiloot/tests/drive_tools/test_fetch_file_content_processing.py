#!/usr/bin/env python3
"""
Content processing tests for FetchFileContent tool
Tests content processing paths, MIME type handling, and export logic
"""

import unittest
import json
import sys
import os
import base64
import io
from unittest.mock import patch, MagicMock, mock_open
import importlib.util

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestFetchFileContentProcessing(unittest.TestCase):
    """Content processing tests for FetchFileContent tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'fetch_file_content' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_get_export_mime_type_for_google_docs(self):
        """Test export MIME type mapping for Google Workspace files."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0
                )

                # Test Google Docs export
                export_type = tool._get_export_mime_type("application/vnd.google-apps.document")
                self.assertEqual(export_type, "text/plain")

                # Test Google Sheets export
                export_type = tool._get_export_mime_type("application/vnd.google-apps.spreadsheet")
                self.assertEqual(export_type, "text/csv")

                # Test Google Slides export
                export_type = tool._get_export_mime_type("application/vnd.google-apps.presentation")
                self.assertEqual(export_type, "text/plain")

                # Test non-Google file
                export_type = tool._get_export_mime_type("application/pdf")
                self.assertIsNone(export_type)

    def test_process_content_binary_mode(self):
        """Test content processing in binary mode (extract_text_only=False)."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool with extract_text_only=False
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=False,  # Binary mode
                    max_size_mb=5.0
                )

                # Test binary content processing
                test_bytes = b"Binary file content"
                result = tool._process_content(test_bytes, "application/pdf")

                # Should return base64 encoded content
                expected_b64 = base64.b64encode(test_bytes).decode('utf-8')
                self.assertEqual(result, expected_b64)

    def test_process_content_text_mode_plain_text(self):
        """Test content processing for plain text files."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool with extract_text_only=True
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=True,
                    max_size_mb=5.0
                )

                # Test plain text processing
                test_text = "This is plain text content"
                test_bytes = test_text.encode('utf-8')
                result = tool._process_content(test_bytes, "text/plain")

                self.assertEqual(result, test_text)

    def test_process_content_text_encoding_fallback(self):
        """Test text content processing with encoding fallback."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=True,
                    max_size_mb=5.0
                )

                # Test with latin-1 encoded text that would fail UTF-8
                test_text = "Café with special chars: ñáéíóú"
                test_bytes = test_text.encode('latin-1')
                result = tool._process_content(test_bytes, "text/plain")

                # Should successfully decode with latin-1 fallback
                self.assertEqual(result, test_text)

    def test_process_content_pdf(self):
        """Test content processing for PDF files."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=True,
                    max_size_mb=5.0
                )

                # Mock the _extract_text_from_pdf method
                def mock_extract_pdf(pdf_bytes):
                    return "Extracted PDF text content"

                tool._extract_text_from_pdf = mock_extract_pdf

                # Test PDF content processing
                test_bytes = b"fake_pdf_content"
                result = tool._process_content(test_bytes, "application/pdf")

                self.assertEqual(result, "Extracted PDF text content")

    def test_process_content_docx(self):
        """Test content processing for DOCX files."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=True,
                    max_size_mb=5.0
                )

                # Mock the _extract_text_from_docx method
                def mock_extract_docx(docx_bytes):
                    return "Extracted DOCX text content"

                tool._extract_text_from_docx = mock_extract_docx

                # Test DOCX content processing
                test_bytes = b"fake_docx_content"
                result = tool._process_content(test_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

                self.assertEqual(result, "Extracted DOCX text content")

    def test_process_content_google_workspace(self):
        """Test content processing for Google Workspace files."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=True,
                    max_size_mb=5.0
                )

                # Test Google Workspace content processing
                test_text = "Google Docs exported content"
                test_bytes = test_text.encode('utf-8')
                result = tool._process_content(test_bytes, "application/vnd.google-apps.document")

                self.assertEqual(result, test_text)

    def test_process_content_unsupported_type_text_mode(self):
        """Test content processing for unsupported MIME types in text extraction mode."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool with extract_text_only=True
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=True,  # Text extraction mode
                    max_size_mb=5.0
                )

                # Test unsupported MIME type content processing
                test_bytes = b"unsupported_binary_content"
                result = tool._process_content(test_bytes, "application/octet-stream")

                # Should return error message for unsupported MIME type in text mode
                expected = "[Text extraction not supported for MIME type: application/octet-stream]"
                self.assertEqual(result, expected)

    def test_process_content_unsupported_type_binary_mode(self):
        """Test content processing for unsupported MIME types in binary mode."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
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
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool with extract_text_only=False
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=False,  # Binary mode
                    max_size_mb=5.0
                )

                # Test unsupported MIME type content processing
                test_bytes = b"unsupported_binary_content"
                result = tool._process_content(test_bytes, "application/octet-stream")

                # Should return base64 encoded content for binary mode
                expected_b64 = base64.b64encode(test_bytes).decode('utf-8')
                self.assertEqual(result, expected_b64)


if __name__ == '__main__':
    unittest.main(verbosity=2)