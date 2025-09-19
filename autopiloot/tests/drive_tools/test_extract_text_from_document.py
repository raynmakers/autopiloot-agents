"""
Test suite for ExtractTextFromDocument tool.
Tests text extraction pipeline supporting PDF, DOCX, HTML, CSV with robust error handling.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock, mock_open

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock environment and dependencies before importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'PyPDF2': MagicMock(),
    'docx': MagicMock(),
    'bs4': MagicMock(),
    'pandas': MagicMock(),
}):
    from unittest.mock import MagicMock
    mock_base_tool = MagicMock()
    mock_field = MagicMock()

    with patch('drive_agent.tools.extract_text_from_document.BaseTool', mock_base_tool):
        with patch('drive_agent.tools.extract_text_from_document.Field', mock_field):
            from drive_agent.tools.extract_text_from_document import ExtractTextFromDocument


class TestExtractTextFromDocument(unittest.TestCase):
    """Test cases for ExtractTextFromDocument tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_file_info = {
            "file_id": "doc_001",
            "name": "Sample Document.pdf",
            "mime_type": "application/pdf",
            "size": 1024,
            "content": b"PDF content here..."
        }

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_plain_text_extraction(self, mock_load_env):
        """Test extraction from plain text files."""
        file_info = {
            "file_id": "text_001",
            "name": "sample.txt",
            "mime_type": "text/plain",
            "size": 100,
            "content": b"This is plain text content for testing."
        }

        tool = ExtractTextFromDocument(
            file_id="text_001",
            file_name="sample.txt",
            mime_type="text/plain",
            file_content=file_info["content"]
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["extraction_method"], "plain_text")
        self.assertEqual(result["text"], "This is plain text content for testing.")
        self.assertEqual(result["character_count"], len("This is plain text content for testing."))

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_pdf_extraction_success(self, mock_load_env):
        """Test successful PDF text extraction."""
        # Mock PyPDF2 for PDF extraction
        mock_pdf_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Extracted PDF text content"
        mock_pdf_reader.pages = [mock_page]

        with patch('drive_agent.tools.extract_text_from_document.PyPDF2.PdfReader', return_value=mock_pdf_reader):
            tool = ExtractTextFromDocument(
                file_id="pdf_001",
                file_name="document.pdf",
                mime_type="application/pdf",
                file_content=b"PDF binary content"
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["extraction_method"], "PyPDF2")
        self.assertEqual(result["text"], "Extracted PDF text content")

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_docx_extraction_success(self, mock_load_env):
        """Test successful DOCX text extraction."""
        # Mock python-docx for DOCX extraction
        mock_doc = MagicMock()
        mock_paragraph1 = MagicMock()
        mock_paragraph1.text = "First paragraph"
        mock_paragraph2 = MagicMock()
        mock_paragraph2.text = "Second paragraph"
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]

        with patch('drive_agent.tools.extract_text_from_document.Document', return_value=mock_doc):
            tool = ExtractTextFromDocument(
                file_id="docx_001",
                file_name="document.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                file_content=b"DOCX binary content"
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["extraction_method"], "python-docx")
        self.assertEqual(result["text"], "First paragraph\nSecond paragraph")

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_html_extraction_success(self, mock_load_env):
        """Test successful HTML text extraction."""
        html_content = b"<html><body><h1>Title</h1><p>Paragraph text</p></body></html>"

        # Mock BeautifulSoup for HTML extraction
        mock_soup = MagicMock()
        mock_soup.get_text.return_value = "Title\nParagraph text"

        with patch('drive_agent.tools.extract_text_from_document.BeautifulSoup', return_value=mock_soup):
            tool = ExtractTextFromDocument(
                file_id="html_001",
                file_name="document.html",
                mime_type="text/html",
                file_content=html_content
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["extraction_method"], "BeautifulSoup")
        self.assertEqual(result["text"], "Title\nParagraph text")

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_csv_extraction_success(self, mock_load_env):
        """Test successful CSV text extraction."""
        csv_content = b"Name,Age,City\nJohn,30,NYC\nJane,25,LA"

        # Mock pandas for CSV extraction
        mock_df = MagicMock()
        mock_df.to_string.return_value = "  Name Age City\n0 John  30  NYC\n1 Jane  25   LA"

        with patch('drive_agent.tools.extract_text_from_document.pd.read_csv', return_value=mock_df):
            tool = ExtractTextFromDocument(
                file_id="csv_001",
                file_name="data.csv",
                mime_type="text/csv",
                file_content=csv_content
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["extraction_method"], "pandas")
        self.assertIn("Name Age City", result["text"])

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_unsupported_format(self, mock_load_env):
        """Test handling of unsupported file formats."""
        tool = ExtractTextFromDocument(
            file_id="img_001",
            file_name="image.jpg",
            mime_type="image/jpeg",
            file_content=b"JPEG binary data"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "unsupported_format")
        self.assertIn("image/jpeg", result["message"])

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_empty_file_content(self, mock_load_env):
        """Test handling of empty file content."""
        tool = ExtractTextFromDocument(
            file_id="empty_001",
            file_name="empty.txt",
            mime_type="text/plain",
            file_content=b""
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["text"], "")
        self.assertEqual(result["character_count"], 0)

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_text_length_limiting(self, mock_load_env):
        """Test text length limiting for large documents."""
        large_text = "A" * 200000  # 200k characters

        tool = ExtractTextFromDocument(
            file_id="large_001",
            file_name="large.txt",
            mime_type="text/plain",
            file_content=large_text.encode(),
            max_text_length=100000
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["text"]), 100000)
        self.assertTrue(result["text_truncated"])

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_pdf_extraction_error(self, mock_load_env):
        """Test handling of PDF extraction errors."""
        with patch('drive_agent.tools.extract_text_from_document.PyPDF2.PdfReader') as mock_pdf:
            mock_pdf.side_effect = Exception("Corrupted PDF file")

            tool = ExtractTextFromDocument(
                file_id="bad_pdf_001",
                file_name="corrupted.pdf",
                mime_type="application/pdf",
                file_content=b"Invalid PDF data"
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "extraction_failed")
        self.assertIn("Corrupted PDF file", result["message"])

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_docx_extraction_error(self, mock_load_env):
        """Test handling of DOCX extraction errors."""
        with patch('drive_agent.tools.extract_text_from_document.Document') as mock_doc:
            mock_doc.side_effect = Exception("Invalid DOCX format")

            tool = ExtractTextFromDocument(
                file_id="bad_docx_001",
                file_name="corrupted.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                file_content=b"Invalid DOCX data"
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "extraction_failed")
        self.assertIn("Invalid DOCX format", result["message"])

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_text_cleaning(self, mock_load_env):
        """Test text cleaning functionality."""
        messy_text = "  \n\n  This   is   messy    text  \n\n  with   extra   spaces  \n\n  "

        tool = ExtractTextFromDocument(
            file_id="messy_001",
            file_name="messy.txt",
            mime_type="text/plain",
            file_content=messy_text.encode()
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        # Text should be cleaned of extra whitespace
        cleaned_text = result["text"]
        self.assertNotIn("  This", cleaned_text)  # Extra spaces removed
        self.assertNotIn("\n\n", cleaned_text)    # Extra newlines removed

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_encoding_detection(self, mock_load_env):
        """Test handling of different text encodings."""
        # Test UTF-8 content
        utf8_text = "Hello 世界! Café résumé"

        tool = ExtractTextFromDocument(
            file_id="utf8_001",
            file_name="unicode.txt",
            mime_type="text/plain",
            file_content=utf8_text.encode('utf-8')
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertIn("世界", result["text"])
        self.assertIn("Café", result["text"])

    @patch('drive_agent.tools.extract_text_from_document.load_environment')
    def test_metadata_extraction(self, mock_load_env):
        """Test extraction of document metadata."""
        tool = ExtractTextFromDocument(
            file_id="meta_001",
            file_name="document.txt",
            mime_type="text/plain",
            file_content=b"Sample content for metadata testing"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertIn("metadata", result)

        metadata = result["metadata"]
        self.assertEqual(metadata["file_id"], "meta_001")
        self.assertEqual(metadata["original_name"], "document.txt")
        self.assertEqual(metadata["mime_type"], "text/plain")
        self.assertIn("extraction_timestamp", metadata)


if __name__ == '__main__':
    unittest.main()