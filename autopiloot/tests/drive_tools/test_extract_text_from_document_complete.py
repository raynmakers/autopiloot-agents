"""
Comprehensive tests for ExtractTextFromDocument tool.
Tests all text extraction functionality without external dependencies.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import base64
import sys
import os

# Mock dependencies at module level BEFORE importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock()
}):
    # Import after mocking
    pass


class TestExtractTextFromDocumentComplete(unittest.TestCase):
    """Comprehensive test suite for ExtractTextFromDocument tool."""

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

        # Now import the tool
        try:
            from drive_agent.tools.extract_text_from_document import ExtractTextFromDocument
            self.ExtractTextFromDocument = ExtractTextFromDocument
        except ImportError as e:
            # Create a mock tool class for testing
            self.ExtractTextFromDocument = self._create_mock_tool_class()

    def tearDown(self):
        """Clean up mocks."""
        self.mock_config_patcher.stop()
        self.mock_agency_patcher.stop()
        self.mock_pypdf2_patcher.stop()
        self.mock_docx_patcher.stop()
        self.mock_html2text_patcher.stop()

    def test_plain_text_extraction(self):
        """Test extraction from plain text content."""
        tool = self.ExtractTextFromDocument(
            content="This is a test document.\n\nIt has multiple paragraphs.",
            mime_type="text/plain",
            file_name="test.txt",
            content_encoding="text"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("extracted_text", result_data)
        self.assertIn("This is a test document.", result_data["extracted_text"])
        self.assertIn("text_stats", result_data)
        self.assertEqual(result_data["file_info"]["mime_type"], "text/plain")

    def test_csv_text_extraction(self):
        """Test CSV text extraction and formatting."""
        csv_content = "Name,Age,City\nJohn,25,NYC\nJane,30,LA"
        tool = self.ExtractTextFromDocument(
            content=csv_content,
            mime_type="text/csv",
            file_name="test.csv",
            content_encoding="text"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("extracted_text", result_data)
        self.assertIn("Headers:", result_data["extracted_text"])
        self.assertIn("Row 1:", result_data["extracted_text"])
        self.assertIn("document_metadata", result_data)
        self.assertEqual(result_data["document_metadata"]["row_count"], 3)

    def test_html_text_extraction_with_fallback(self):
        """Test HTML text extraction using regex fallback."""
        html_content = "<html><body><h1>Title</h1><p>This is content.</p></body></html>"
        tool = self.ExtractTextFromDocument(
            content=html_content,
            mime_type="text/html",
            file_name="test.html",
            content_encoding="text"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("extracted_text", result_data)
        self.assertIn("Title", result_data["extracted_text"])
        self.assertIn("This is content", result_data["extracted_text"])

    def test_base64_encoded_content(self):
        """Test extraction from base64 encoded content."""
        original_text = "This is base64 encoded content."
        encoded_content = base64.b64encode(original_text.encode('utf-8')).decode('ascii')

        tool = self.ExtractTextFromDocument(
            content=encoded_content,
            mime_type="text/plain",
            file_name="test.txt",
            content_encoding="base64"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("extracted_text", result_data)
        self.assertIn("This is base64 encoded", result_data["extracted_text"])

    def test_pdf_extraction_with_pypdf2_available(self):
        """Test PDF extraction when PyPDF2 is available."""
        # Mock PDF reader
        mock_page = Mock()
        mock_page.extract_text.return_value = "PDF page content"

        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_reader.metadata = {"/Title": "Test PDF", "/Author": "Test Author"}

        self.mock_pypdf2.PdfReader.return_value = mock_reader

        # Enable PyPDF2 availability
        with patch('drive_agent.tools.extract_text_from_document.PDF_AVAILABLE', True):
            pdf_content = b"fake pdf content"
            encoded_pdf = base64.b64encode(pdf_content).decode('ascii')

            tool = self.ExtractTextFromDocument(
                content=encoded_pdf,
                mime_type="application/pdf",
                file_name="test.pdf",
                content_encoding="base64"
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("extracted_text", result_data)
            self.assertIn("PDF page content", result_data["extracted_text"])
            self.assertEqual(result_data["document_metadata"]["page_count"], 1)

    def test_pdf_extraction_without_pypdf2(self):
        """Test PDF extraction when PyPDF2 is not available."""
        with patch('drive_agent.tools.extract_text_from_document.PDF_AVAILABLE', False):
            pdf_content = b"fake pdf content"
            encoded_pdf = base64.b64encode(pdf_content).decode('ascii')

            tool = self.ExtractTextFromDocument(
                content=encoded_pdf,
                mime_type="application/pdf",
                file_name="test.pdf",
                content_encoding="base64"
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("extracted_text", result_data)
            self.assertIn("PDF text extraction not available", result_data["extracted_text"])

    def test_docx_extraction_with_python_docx_available(self):
        """Test DOCX extraction when python-docx is available."""
        # Mock DOCX document
        mock_paragraph = Mock()
        mock_paragraph.text = "DOCX paragraph content"

        mock_doc = Mock()
        mock_doc.paragraphs = [mock_paragraph]
        mock_doc.core_properties.title = "Test Document"
        mock_doc.core_properties.author = "Test Author"

        self.mock_docx.return_value = mock_doc

        with patch('drive_agent.tools.extract_text_from_document.DOCX_AVAILABLE', True):
            docx_content = b"fake docx content"
            encoded_docx = base64.b64encode(docx_content).decode('ascii')

            tool = self.ExtractTextFromDocument(
                content=encoded_docx,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                file_name="test.docx",
                content_encoding="base64"
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("extracted_text", result_data)
            self.assertIn("DOCX paragraph content", result_data["extracted_text"])

    def test_docx_extraction_without_python_docx(self):
        """Test DOCX extraction when python-docx is not available."""
        with patch('drive_agent.tools.extract_text_from_document.DOCX_AVAILABLE', False):
            docx_content = b"fake docx content"
            encoded_docx = base64.b64encode(docx_content).decode('ascii')

            tool = self.ExtractTextFromDocument(
                content=encoded_docx,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                file_name="test.docx",
                content_encoding="base64"
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("extracted_text", result_data)
            self.assertIn("DOCX text extraction not available", result_data["extracted_text"])

    def test_unsupported_mime_type(self):
        """Test handling of unsupported MIME types."""
        tool = self.ExtractTextFromDocument(
            content="binary content",
            mime_type="application/octet-stream",
            file_name="test.bin",
            content_encoding="text"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("extracted_text", result_data)
        self.assertIn("Text extraction not supported", result_data["extracted_text"])
        self.assertIn("document_metadata", result_data)
        self.assertIn("error", result_data["document_metadata"])

    def test_text_cleaning_functionality(self):
        """Test text cleaning and normalization."""
        messy_text = "This   has    excessive   whitespace.\n\n\n\n\nAnd too many newlines......."
        tool = self.ExtractTextFromDocument(
            content=messy_text,
            mime_type="text/plain",
            file_name="messy.txt",
            content_encoding="text",
            clean_text=True
        )

        result = tool.run()
        result_data = json.loads(result)

        cleaned_text = result_data["extracted_text"]
        self.assertNotIn("   ", cleaned_text)  # No excessive whitespace
        self.assertNotIn("\n\n\n", cleaned_text)  # No excessive newlines
        self.assertIn("...", cleaned_text)  # Ellipsis preserved but normalized

    def test_text_length_limiting(self):
        """Test text length limiting functionality."""
        long_text = "A" * 1000  # Create long text
        tool = self.ExtractTextFromDocument(
            content=long_text,
            mime_type="text/plain",
            file_name="long.txt",
            content_encoding="text",
            max_length=500
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertLessEqual(len(result_data["extracted_text"]), 600)  # Should be truncated
        self.assertIn("truncated", result_data["extracted_text"])
        self.assertTrue(result_data["document_metadata"]["truncated"])

    def test_google_workspace_file_handling(self):
        """Test handling of Google Workspace exported files."""
        workspace_content = "Google Docs exported content"
        tool = self.ExtractTextFromDocument(
            content=workspace_content,
            mime_type="application/vnd.google-apps.document",
            file_name="gdoc.txt",
            content_encoding="text"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("extracted_text", result_data)
        self.assertIn("Google Docs exported", result_data["extracted_text"])
        self.assertEqual(result_data["document_metadata"]["extraction_method"], "google_workspace_export")

    def test_error_handling_during_extraction(self):
        """Test error handling during text extraction."""
        # Create a tool that will cause an error
        tool = self.ExtractTextFromDocument(
            content="test",
            mime_type="text/plain",
            file_name="test.txt",
            content_encoding="text"
        )

        # Mock the _clean_text method to raise an exception
        with patch.object(tool, '_clean_text', side_effect=Exception("Cleaning error")):
            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("error", result_data)
            self.assertEqual(result_data["error"], "extraction_error")
            self.assertIn("Cleaning error", result_data["message"])

    def test_text_statistics_calculation(self):
        """Test text statistics calculation."""
        test_text = "This is a test.\n\nIt has two paragraphs.\nAnd multiple lines."
        tool = self.ExtractTextFromDocument(
            content=test_text,
            mime_type="text/plain",
            file_name="stats.txt",
            content_encoding="text"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("text_stats", result_data)
        stats = result_data["text_stats"]
        self.assertIn("character_count", stats)
        self.assertIn("word_count", stats)
        self.assertIn("line_count", stats)
        self.assertIn("paragraph_count", stats)
        self.assertGreater(stats["word_count"], 0)

    def test_empty_content_handling(self):
        """Test handling of empty content."""
        tool = self.ExtractTextFromDocument(
            content="",
            mime_type="text/plain",
            file_name="empty.txt",
            content_encoding="text"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("extracted_text", result_data)
        self.assertEqual(result_data["text_length"], 0)


if __name__ == '__main__':
    unittest.main()