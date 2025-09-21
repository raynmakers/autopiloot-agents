#!/usr/bin/env python3
"""
Comprehensive coverage tests for ExtractTextFromDocument tool
Targets remaining uncovered lines to achieve 85%+ coverage
Focuses on edge cases, error handling, and Google Workspace documents
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


class TestExtractTextComprehensiveCoverage(unittest.TestCase):
    """Comprehensive coverage tests for remaining uncovered lines."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'extract_text_from_document' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_empty_csv_handling(self):
        """Test lines 293 - empty CSV file handling."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool with empty CSV content
                tool = ExtractTextFromDocument(
                    content="",  # Empty content to trigger empty CSV path
                    mime_type="text/csv",
                    file_name="empty.csv",
                    content_encoding="text"
                )

                # Call _extract_text_from_csv to test line 293
                result = tool._extract_text_from_csv("")

                # Verify empty CSV handling
                self.assertEqual(result["text"], "[Empty CSV file]")
                self.assertEqual(result["metadata"]["row_count"], 0)
                self.assertEqual(result["metadata"]["extraction_method"], "csv")

    def test_large_csv_truncation(self):
        """Test lines 313-314 - CSV truncation for large files."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create large CSV with more than 100 rows
                rows = ["Name,Age,City"]  # Header
                for i in range(105):  # 105 data rows (> 100)
                    rows.append(f"Person{i},25,City{i}")
                large_csv = "\n".join(rows)

                tool = ExtractTextFromDocument(
                    content=large_csv,
                    mime_type="text/csv",
                    file_name="large.csv",
                    content_encoding="text"
                )

                # Call _extract_text_from_csv to test lines 313-314
                result = tool._extract_text_from_csv(large_csv)

                # Verify truncation occurred
                self.assertIn("... and 5 more rows", result["text"])  # 106 total - 101 shown = 5 more
                self.assertTrue(result["metadata"]["truncated"])
                self.assertEqual(result["metadata"]["row_count"], 106)  # Header + 105 data rows

    def test_csv_error_handling(self):
        """Test lines 328-329 - CSV error handling."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                tool = ExtractTextFromDocument(
                    content="test",
                    mime_type="text/csv",
                    file_name="test.csv",
                    content_encoding="text"
                )

                # Mock csv module to raise an exception
                with patch('csv.reader') as mock_reader:
                    mock_reader.side_effect = Exception("CSV parsing failed")

                    # Call _extract_text_from_csv to test lines 328-329
                    result = tool._extract_text_from_csv("malformed,csv\ndata")

                    # Verify error handling
                    self.assertIn("Error processing CSV", result["text"])
                    self.assertEqual(result["metadata"]["error"], "CSV parsing failed")

    def test_text_encoding_error_path(self):
        """Test lines 363-368 - text encoding error handling and fallback."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create invalid base64 content that will trigger encoding error
                invalid_base64 = "invalid_base64_content_that_cannot_decode"

                tool = ExtractTextFromDocument(
                    content=invalid_base64,
                    mime_type="text/plain",
                    file_name="test.txt",
                    content_encoding="base64"  # This will trigger base64 decode error
                )

                # Run the tool to trigger lines 363-368
                result = tool.run()
                result_data = json.loads(result)

                # Should trigger encoding error path (may be in error message or extracted_text)
                self.assertTrue(
                    "Error decoding text" in result_data.get("extracted_text", "") or
                    "Error" in result_data.get("message", "") or
                    "error" in result_data.keys()
                )

    def test_google_workspace_document_handling(self):
        """Test lines 406-420 - Google Workspace document handling."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Test Google Docs MIME type with text content
                tool = ExtractTextFromDocument(
                    content="Google Docs exported text content",
                    mime_type="application/vnd.google-apps.document",
                    file_name="test_doc",
                    content_encoding="text",
                    max_length=50000  # Explicit max_length to avoid config comparison issues
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify Google Workspace handling
                self.assertEqual(result_data["extracted_text"], "Google Docs exported text content")
                if "document_metadata" in result_data:
                    self.assertEqual(result_data["document_metadata"]["extraction_method"], "google_workspace_export")
                    self.assertEqual(result_data["document_metadata"]["original_mime_type"], "application/vnd.google-apps.document")

    def test_google_workspace_base64_handling(self):
        """Test lines 408-410 - Google Workspace base64 content handling."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Test Google Sheets MIME type with base64 content
                original_text = "Google Sheets exported CSV data"
                base64_content = base64.b64encode(original_text.encode('utf-8')).decode('ascii')

                tool = ExtractTextFromDocument(
                    content=base64_content,
                    mime_type="application/vnd.google-apps.spreadsheet",
                    file_name="test_sheet",
                    content_encoding="base64",  # This triggers lines 408-410
                    max_length=50000  # Explicit max_length to avoid config comparison issues
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify Google Workspace base64 handling
                self.assertEqual(result_data["extracted_text"], original_text)
                if "document_metadata" in result_data:
                    self.assertEqual(result_data["document_metadata"]["extraction_method"], "google_workspace_export")

    def test_unsupported_mime_type_handling(self):
        """Test lines 422-424 + 439-441 - unsupported MIME type handling."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Test unsupported MIME type
                tool = ExtractTextFromDocument(
                    content="binary_data",
                    mime_type="application/octet-stream",  # Unsupported type
                    file_name="test.bin",
                    content_encoding="text",
                    max_length=50000  # Explicit max_length to avoid config comparison issues
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify unsupported MIME type handling
                self.assertIn("Text extraction not supported", result_data["extracted_text"])
                if "document_metadata" in result_data:
                    self.assertIn("Unsupported MIME type", result_data["document_metadata"]["error"])

    def test_pdf_extraction_error_path(self):
        """Test lines 173-174 - PDF extraction error handling."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock(),
            'PyPDF2': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock PyPDF2 to raise an exception
            sys.modules['PyPDF2'].PdfReader.side_effect = Exception("PDF parsing failed")

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_text_length": 50000}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force PDF_AVAILABLE to True
                module.PDF_AVAILABLE = True

                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool
                tool = ExtractTextFromDocument(
                    content="fake_pdf_bytes",
                    mime_type="application/pdf",
                    file_name="test.pdf",
                    content_encoding="base64"
                )

                # Call _extract_text_from_pdf to test lines 173-174
                result = tool._extract_text_from_pdf(b"fake_pdf_bytes")

                # Verify error handling
                self.assertIn("Error processing PDF", result["text"])
                self.assertEqual(result["metadata"]["error"], "PDF parsing failed")

    def test_docx_extraction_error_path(self):
        """Test lines 226-227 - DOCX extraction error handling."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock(),
            'docx': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock docx to raise an exception
            sys.modules['docx'].Document.side_effect = Exception("DOCX parsing failed")

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_text_length": 50000}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force DOCX_AVAILABLE to True
                module.DOCX_AVAILABLE = True

                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool
                tool = ExtractTextFromDocument(
                    content="fake_docx_bytes",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    file_name="test.docx",
                    content_encoding="base64"
                )

                # Call _extract_text_from_docx to test lines 226-227
                result = tool._extract_text_from_docx(b"fake_docx_bytes")

                # Verify error handling
                self.assertIn("Error processing DOCX", result["text"])
                self.assertEqual(result["metadata"]["error"], "DOCX parsing failed")

    def test_html_extraction_error_path(self):
        """Test lines 275-276 - HTML extraction error handling."""
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

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force HTML2TEXT_AVAILABLE to False to use fallback
                module.HTML2TEXT_AVAILABLE = False

                ExtractTextFromDocument = module.ExtractTextFromDocument

                tool = ExtractTextFromDocument(
                    content="<html><body>Test</body></html>",
                    mime_type="text/html",
                    file_name="test.html",
                    content_encoding="text"
                )

                # Mock html.unescape to raise an exception to test lines 275-276
                with patch('html.unescape') as mock_unescape:
                    mock_unescape.side_effect = Exception("HTML processing failed")

                    # Call _extract_text_from_html to test lines 275-276
                    result = tool._extract_text_from_html("<html><body>Test</body></html>")

                    # Verify error handling
                    self.assertIn("Error processing HTML", result["text"])


if __name__ == '__main__':
    unittest.main(verbosity=2)