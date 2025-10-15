#!/usr/bin/env python3
"""
Advanced coverage tests for ExtractTextFromDocument tool
Targets specific uncovered lines to improve coverage from 47% to 80%+
Focuses on optional imports, PDF/DOCX/HTML processing, and error handling
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

class TestExtractTextAdvancedCoverage(unittest.TestCase):
    """Advanced coverage tests for ExtractTextFromDocument tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'extract_text_from_document' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_optional_imports_missing_all_libraries(self):
        """Test lines 24, 30, 36 - when optional libraries are missing."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock(),
            # Force ImportError for optional libraries
            'PyPDF2': None,
            'docx': None,
            'html2text': None
        }):
            # Setup basic mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock config
            with patch('loader.get_config_value') as mock_config:
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

                # Force ImportError by patching __import__
                import builtins
                original_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name in ['PyPDF2', 'docx', 'html2text']:
                        raise ImportError(f"No module named '{name}'")
                    return original_import(name, *args, **kwargs)

                with patch('builtins.__import__', side_effect=mock_import):
                    # Import using direct file loading
                    spec = importlib.util.spec_from_file_location(
                        "extract_text_from_document",
                        "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Verify the module loaded and flags are set correctly
                    self.assertFalse(module.PDF_AVAILABLE)     # Line 24
                    self.assertFalse(module.DOCX_AVAILABLE)    # Line 30
                    self.assertFalse(module.HTML2TEXT_AVAILABLE)  # Line 36

    def test_max_length_from_config_path(self):
        """Test lines 88-92 - _get_max_length() when max_length is None."""
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
                # Return nested config structure to test lines 88-92
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {
                            "tracking": {
                                "max_text_length": 75000  # Custom value to test config path
                            }
                        }
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

                # Create tool with max_length=None to trigger config path
                tool = ExtractTextFromDocument(
                    content="test",
                    mime_type="text/plain",
                    file_name="test.txt",
                    content_encoding="text",
                    max_length=None  # This will trigger _get_max_length() config path
                )

                # Call _get_max_length to cover lines 88-92
                max_length = tool._get_max_length()
                self.assertEqual(max_length, 75000)  # From config

    def test_clean_text_disabled_path(self):
        """Test line 97 - _clean_text() when clean_text is False."""
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
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool with clean_text=False
                tool = ExtractTextFromDocument(
                    content="  messy   text   with    spaces  ",
                    mime_type="text/plain",
                    file_name="test.txt",
                    content_encoding="text",
                    clean_text=False  # This will trigger line 97 return path
                )

                # Call _clean_text to test line 97
                original_text = "  messy   text   with    spaces  "
                cleaned = tool._clean_text(original_text)
                self.assertEqual(cleaned, original_text)  # Should return unchanged

    def test_pdf_extraction_when_pypdf2_unavailable(self):
        """Test lines 123-127 - PDF extraction when PyPDF2 is not available."""
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
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

                # Import tool but manually set PDF_AVAILABLE to False
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force PDF_AVAILABLE to False to test lines 123-127
                module.PDF_AVAILABLE = False

                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool
                tool = ExtractTextFromDocument(
                    content="fake_pdf_bytes",
                    mime_type="application/pdf",
                    file_name="test.pdf",
                    content_encoding="base64"
                )

                # Call _extract_text_from_pdf to test lines 123-127
                result = tool._extract_text_from_pdf(b"fake_pdf_bytes")

                # Verify the error path was taken
                self.assertIn("PyPDF2 not installed", result["text"])
                self.assertEqual(result["metadata"]["error"], "PyPDF2 not available")

    def test_pdf_extraction_with_mocked_pypdf2(self):
        """Test lines 129-177 - PDF extraction with successful PyPDF2."""
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

            # Mock PyPDF2 components
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample PDF page text"

            mock_reader = MagicMock()
            mock_reader.pages = [mock_page, mock_page]  # Two pages
            mock_reader.metadata = {
                "/Title": "Test Document",
                "/Author": "Test Author",
                "/Subject": "Test Subject",
                "/Creator": "Test Creator"
            }

            sys.modules['PyPDF2'].PdfReader.return_value = mock_reader

            with patch('loader.get_config_value') as mock_config:
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

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

                # Call _extract_text_from_pdf to test lines 129-177
                result = tool._extract_text_from_pdf(b"fake_pdf_bytes")

                # Verify successful extraction
                self.assertIn("Sample PDF page text", result["text"])
                self.assertEqual(result["metadata"]["page_count"], 2)
                self.assertEqual(result["metadata"]["extraction_method"], "PyPDF2")
                self.assertEqual(result["metadata"]["title"], "Test Document")

    def test_docx_extraction_when_python_docx_unavailable(self):
        """Test lines 181-185 - DOCX extraction when python-docx is not available."""
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
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force DOCX_AVAILABLE to False to test lines 181-185
                module.DOCX_AVAILABLE = False

                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool
                tool = ExtractTextFromDocument(
                    content="fake_docx_bytes",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    file_name="test.docx",
                    content_encoding="base64"
                )

                # Call _extract_text_from_docx to test lines 181-185
                result = tool._extract_text_from_docx(b"fake_docx_bytes")

                # Verify the error path was taken
                self.assertIn("python-docx not installed", result["text"])
                self.assertEqual(result["metadata"]["error"], "python-docx not available")

    def test_docx_extraction_with_mocked_python_docx(self):
        """Test lines 187-230 - DOCX extraction with successful python-docx."""
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

            # Mock python-docx components
            mock_paragraph1 = MagicMock()
            mock_paragraph1.text = "First paragraph text"
            mock_paragraph2 = MagicMock()
            mock_paragraph2.text = "Second paragraph text"

            mock_core_props = MagicMock()
            mock_core_props.title = "Test DOCX Document"
            mock_core_props.author = "Test Author"
            mock_core_props.subject = "Test Subject"
            mock_core_props.created = None
            mock_core_props.modified = None

            mock_doc = MagicMock()
            mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
            mock_doc.core_properties = mock_core_props

            sys.modules['docx'].Document.return_value = mock_doc

            with patch('loader.get_config_value') as mock_config:
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

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

                # Call _extract_text_from_docx to test lines 187-230
                result = tool._extract_text_from_docx(b"fake_docx_bytes")

                # Verify successful extraction
                self.assertIn("First paragraph text", result["text"])
                self.assertIn("Second paragraph text", result["text"])
                self.assertEqual(result["metadata"]["paragraph_count"], 2)
                self.assertEqual(result["metadata"]["extraction_method"], "python-docx")
                self.assertEqual(result["metadata"]["title"], "Test DOCX Document")

    def test_html_extraction_with_html2text_available(self):
        """Test lines 234-252 - HTML extraction when html2text is available."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock(),
            'html2text': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock html2text
            mock_html2text_instance = MagicMock()
            mock_html2text_instance.handle.return_value = "Converted HTML text content"
            sys.modules['html2text'].HTML2Text.return_value = mock_html2text_instance

            with patch('loader.get_config_value') as mock_config:
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force HTML2TEXT_AVAILABLE to True
                module.HTML2TEXT_AVAILABLE = True

                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool
                tool = ExtractTextFromDocument(
                    content="<html><body><h1>Test</h1><p>Content</p></body></html>",
                    mime_type="text/html",
                    file_name="test.html",
                    content_encoding="text"
                )

                # Call _extract_text_from_html to test lines 234-252
                html_content = "<html><body><h1>Test</h1><p>Content</p></body></html>"
                result = tool._extract_text_from_html(html_content)

                # Verify html2text path was taken
                self.assertEqual(result["text"], "Converted HTML text content")
                self.assertEqual(result["metadata"]["extraction_method"], "html2text")

    def test_html_extraction_fallback_regex_method(self):
        """Test lines 254-276 - HTML extraction fallback when html2text fails."""
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
                mock_config.return_value = {"tracking": {"max_text_length": 50000}}

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "extract_text_from_document",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/extract_text_from_document.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force HTML2TEXT_AVAILABLE to False to test fallback
                module.HTML2TEXT_AVAILABLE = False

                ExtractTextFromDocument = module.ExtractTextFromDocument

                # Create tool
                tool = ExtractTextFromDocument(
                    content="<html><head><script>alert('test');</script></head><body><h1>Test Title</h1><p>Content &amp; text</p></body></html>",
                    mime_type="text/html",
                    file_name="test.html",
                    content_encoding="text"
                )

                # Call _extract_text_from_html to test lines 254-276
                html_content = "<html><head><script>alert('test');</script></head><body><h1>Test Title</h1><p>Content &amp; text</p></body></html>"
                result = tool._extract_text_from_html(html_content)

                # Verify fallback regex method was used
                self.assertEqual(result["metadata"]["extraction_method"], "regex_fallback")
                # Should remove script tags and decode entities
                self.assertNotIn("alert('test')", result["text"])
                self.assertIn("Test Title", result["text"])
                self.assertIn("Content & text", result["text"])  # HTML entity decoded


if __name__ == '__main__':
    unittest.main(verbosity=2)