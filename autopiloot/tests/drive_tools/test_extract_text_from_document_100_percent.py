"""
Comprehensive tests for ExtractTextFromDocument to achieve 100% coverage.
Targets all missing lines including error paths and edge cases.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import base64
import sys
import io


class TestExtractTextFromDocument100Percent(unittest.TestCase):
    """Test suite to achieve 100% coverage for ExtractTextFromDocument."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        # Mock the config loader
        self.mock_config_patcher = patch('config.loader.get_config_value')
        self.mock_config = self.mock_config_patcher.start()
        self.mock_config.return_value = {"tracking": {"max_text_length": 50000}}

        # Mock agency_swarm at import time
        sys.modules['agency_swarm'] = MagicMock()
        sys.modules['agency_swarm.tools'] = MagicMock()

        # Create a mock BaseTool class
        mock_base_tool = MagicMock()
        sys.modules['agency_swarm.tools'].BaseTool = mock_base_tool

        # Mock optional dependencies
        self.mock_pypdf2_patcher = patch.dict('sys.modules', {'PyPDF2': MagicMock()})
        self.mock_pypdf2_patcher.start()

        self.mock_docx_patcher = patch.dict('sys.modules', {'docx': MagicMock()})
        self.mock_docx_patcher.start()

        self.mock_html2text_patcher = patch.dict('sys.modules', {'html2text': MagicMock()})
        self.mock_html2text_patcher.start()

        # Import the tool
        from drive_agent.tools.extract_text_from_document import ExtractTextFromDocument
        self.ExtractTextFromDocument = ExtractTextFromDocument

    def tearDown(self):
        """Clean up mocks."""
        self.mock_config_patcher.stop()
        self.mock_pypdf2_patcher.stop()
        self.mock_docx_patcher.stop()
        self.mock_html2text_patcher.stop()

    def test_pdf_page_extraction_error(self):
        """Test PDF page extraction error (lines 142-143)."""
        with patch('drive_agent.tools.extract_text_from_document.PDF_AVAILABLE', True):
            # Mock PDF reader with page extraction error
            mock_page = Mock()
            mock_page.extract_text.side_effect = Exception("Page extraction failed")

            mock_reader = Mock()
            mock_reader.pages = [mock_page]
            mock_reader.metadata = {}

            with patch('drive_agent.tools.extract_text_from_document.PyPDF2') as mock_pypdf2:
                mock_pypdf2.PdfReader.return_value = mock_reader

                tool = self.ExtractTextFromDocument(
                    content=base64.b64encode(b"fake pdf").decode(),
                    mime_type="application/pdf",
                    file_name="test.pdf",
                    content_encoding="base64"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should contain error message for the page
                self.assertIn("Error extracting page", result_data["extracted_text"])

    def test_docx_core_properties_exception(self):
        """Test DOCX core properties exception (lines 218-219)."""
        with patch('drive_agent.tools.extract_text_from_document.DOCX_AVAILABLE', True):
            # Mock DOCX document with core properties exception
            mock_paragraph = Mock()
            mock_paragraph.text = "Test content"

            mock_doc = Mock()
            mock_doc.paragraphs = [mock_paragraph]
            # Mock core_properties to raise exception
            mock_doc.core_properties = Mock()
            mock_doc.core_properties.title = Mock(side_effect=Exception("Properties error"))

            with patch('drive_agent.tools.extract_text_from_document.Document') as mock_docx:
                mock_docx.return_value = mock_doc

                tool = self.ExtractTextFromDocument(
                    content=base64.b64encode(b"fake docx").decode(),
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    file_name="test.docx",
                    content_encoding="base64"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should still succeed despite properties error
                self.assertIn("Test content", result_data["extracted_text"])

    def test_html2text_exception_fallback(self):
        """Test HTML2Text exception fallback (lines 251-252)."""
        with patch('drive_agent.tools.extract_text_from_document.HTML2TEXT_AVAILABLE', True):
            with patch('drive_agent.tools.extract_text_from_document.html2text') as mock_html2text:
                # Mock html2text to raise exception
                mock_converter = Mock()
                mock_converter.handle.side_effect = Exception("HTML2Text error")
                mock_html2text.HTML2Text.return_value = mock_converter

                tool = self.ExtractTextFromDocument(
                    content="<html><body>Test content</body></html>",
                    mime_type="text/html",
                    file_name="test.html",
                    content_encoding="text"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should fall back to regex removal
                self.assertIn("Test content", result_data["extracted_text"])

    def test_get_content_bytes_text_encoding(self):
        """Test _get_content_bytes with text encoding (line 340)."""
        tool = self.ExtractTextFromDocument(
            content="Test content",
            mime_type="text/plain",
            file_name="test.txt",
            content_encoding="text"  # Not base64
        )

        content_bytes = tool._get_content_bytes()
        self.assertEqual(content_bytes, b"Test content")

    def test_base64_text_decoding_with_errors(self):
        """Test base64 text decoding with multiple encoding attempts (lines 366-368)."""
        # Create invalid UTF-8 bytes that will fail initial decoding
        invalid_utf8 = b'\xff\xfe\x00\x00Invalid UTF-8'
        encoded_content = base64.b64encode(invalid_utf8).decode()

        tool = self.ExtractTextFromDocument(
            content=encoded_content,
            mime_type="text/plain",
            file_name="test.txt",
            content_encoding="base64"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should handle encoding errors gracefully
        self.assertIn("extracted_text", result_data)

    def test_base64_text_decoding_exception(self):
        """Test base64 text decoding exception (line 367-368)."""
        with patch('drive_agent.tools.extract_text_from_document.base64.b64decode') as mock_decode:
            mock_decode.side_effect = Exception("Decode error")

            tool = self.ExtractTextFromDocument(
                content="invalid_base64",
                mime_type="text/plain",
                file_name="test.txt",
                content_encoding="base64"
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should contain error message
            self.assertIn("Error decoding text", result_data["extracted_text"])

    def test_pdf_extraction_direct_path(self):
        """Test PDF extraction direct path (lines 386-387)."""
        with patch('drive_agent.tools.extract_text_from_document.PDF_AVAILABLE', True):
            with patch('drive_agent.tools.extract_text_from_document.PyPDF2') as mock_pypdf2:
                mock_page = Mock()
                mock_page.extract_text.return_value = "PDF content"

                mock_reader = Mock()
                mock_reader.pages = [mock_page]
                mock_reader.metadata = {}
                mock_pypdf2.PdfReader.return_value = mock_reader

                tool = self.ExtractTextFromDocument(
                    content=base64.b64encode(b"fake pdf").decode(),
                    mime_type="application/pdf",
                    file_name="test.pdf",
                    content_encoding="base64"
                )

                result = tool.run()
                result_data = json.loads(result)

                self.assertIn("PDF content", result_data["extracted_text"])

    def test_docx_extraction_direct_path(self):
        """Test DOCX extraction direct path (lines 393-394)."""
        with patch('drive_agent.tools.extract_text_from_document.DOCX_AVAILABLE', True):
            with patch('drive_agent.tools.extract_text_from_document.Document') as mock_docx:
                mock_paragraph = Mock()
                mock_paragraph.text = "DOCX content"

                mock_doc = Mock()
                mock_doc.paragraphs = [mock_paragraph]
                mock_doc.core_properties = Mock()
                mock_docx.return_value = mock_doc

                tool = self.ExtractTextFromDocument(
                    content=base64.b64encode(b"fake docx").decode(),
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    file_name="test.docx",
                    content_encoding="base64"
                )

                result = tool.run()
                result_data = json.loads(result)

                self.assertIn("DOCX content", result_data["extracted_text"])

    def test_html_base64_decoding(self):
        """Test HTML base64 decoding (lines 398-404)."""
        html_content = "<html><body>HTML content</body></html>"
        encoded_html = base64.b64encode(html_content.encode()).decode()

        tool = self.ExtractTextFromDocument(
            content=encoded_html,
            mime_type="text/html",
            file_name="test.html",
            content_encoding="base64"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("HTML content", result_data["extracted_text"])

    def test_google_workspace_base64_handling(self):
        """Test Google Workspace base64 handling (lines 398-404 equivalent path)."""
        workspace_content = "Google Docs content"
        encoded_content = base64.b64encode(workspace_content.encode()).decode()

        tool = self.ExtractTextFromDocument(
            content=encoded_content,
            mime_type="application/vnd.google-apps.document",
            file_name="gdoc.txt",
            content_encoding="base64"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("Google Docs content", result_data["extracted_text"])

    def test_text_truncation_with_metadata(self):
        """Test text truncation with metadata (lines 439-441)."""
        long_text = "A" * 1000

        tool = self.ExtractTextFromDocument(
            content=long_text,
            mime_type="text/plain",
            file_name="long.txt",
            content_encoding="text",
            max_length=500
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should be truncated
        self.assertLess(len(result_data["extracted_text"]), 600)
        self.assertIn("truncated", result_data["extracted_text"])
        self.assertTrue(result_data["document_metadata"]["truncated"])
        self.assertEqual(result_data["document_metadata"]["truncated_at"], 500)

    def test_pdf_metadata_extraction_with_values(self):
        """Test PDF metadata extraction when values exist (lines 165-166)."""
        with patch('drive_agent.tools.extract_text_from_document.PDF_AVAILABLE', True):
            with patch('drive_agent.tools.extract_text_from_document.PyPDF2') as mock_pypdf2:
                mock_page = Mock()
                mock_page.extract_text.return_value = "PDF content"

                mock_reader = Mock()
                mock_reader.pages = [mock_page]
                # Mock metadata with actual values
                mock_reader.metadata = {
                    "/Title": "Test PDF Title",
                    "/Author": "Test Author",
                    "/Subject": "Test Subject",
                    "/Creator": "Test Creator"
                }
                mock_pypdf2.PdfReader.return_value = mock_reader

                tool = self.ExtractTextFromDocument(
                    content=base64.b64encode(b"fake pdf").decode(),
                    mime_type="application/pdf",
                    file_name="test.pdf",
                    content_encoding="base64"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Check metadata was extracted
                metadata = result_data["document_metadata"]
                self.assertEqual(metadata["title"], "Test PDF Title")
                self.assertEqual(metadata["author"], "Test Author")


if __name__ == '__main__':
    unittest.main()