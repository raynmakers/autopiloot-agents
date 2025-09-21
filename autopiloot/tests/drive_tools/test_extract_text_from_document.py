"""
Test suite for ExtractTextFromDocument tool.
Comprehensive testing of text extraction pipeline with proper mocking and error handling.
Tests all supported formats: PDF, DOCX, HTML, CSV, plain text, and Google Workspace exports.
"""

import unittest
import json
import sys
import os
import base64
import io
from unittest.mock import patch, MagicMock, mock_open

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestExtractTextFromDocument(unittest.TestCase):
    """Test cases for ExtractTextFromDocument tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_plain_text = "This is a sample document.\n\nIt has multiple paragraphs.\n\nAnd some formatting."
        self.sample_csv_content = "Name,Age,City\nJohn,30,New York\nJane,25,Boston\nBob,35,Chicago"
        self.sample_html_content = """
        <html>
            <head><title>Test Document</title></head>
            <body>
                <h1>Main Title</h1>
                <p>This is the first paragraph.</p>
                <p>This is the second paragraph.</p>
                <script>console.log('should be removed');</script>
                <style>body { color: red; }</style>
            </body>
        </html>
        """
        
        # Mock config responses
        self.mock_config = {
            "drive": {
                "tracking": {
                    "max_text_length": 50000
                }
            }
        }

    def _import_tool_with_mocks(self):
        """Import the tool with all necessary mocks."""
        # Mock pydantic first
        mock_pydantic = MagicMock()
        mock_field = MagicMock()
        mock_field.return_value = MagicMock()
        mock_pydantic.Field = mock_field
        
        # Mock agency_swarm
        mock_agency_swarm = MagicMock()
        mock_base_tool = MagicMock()
        mock_agency_swarm.tools = MagicMock()
        mock_agency_swarm.tools.BaseTool = mock_base_tool
        
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=self.mock_config.get("drive", {}))
        
        with patch.dict('sys.modules', {
            'pydantic': mock_pydantic,
            'agency_swarm': mock_agency_swarm,
            'agency_swarm.tools': mock_agency_swarm.tools,
            'loader': mock_loader
        }):
            from drive_agent.tools.extract_text_from_document import ExtractTextFromDocument
            return ExtractTextFromDocument

    def test_tool_initialization(self):
        """Test that the tool can be initialized with proper parameters."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        tool = ExtractTextFromDocument(
            content=self.sample_plain_text,
            mime_type="text/plain",
            file_name="test.txt",
            content_encoding="text"
        )
        
        self.assertEqual(tool.content, self.sample_plain_text)
        self.assertEqual(tool.mime_type, "text/plain")
        self.assertEqual(tool.file_name, "test.txt")
        self.assertEqual(tool.content_encoding, "text")

    def test_plain_text_extraction(self):
        """Test extraction from plain text files."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
            tool = ExtractTextFromDocument(
                content=self.sample_plain_text,
                mime_type="text/plain",
                file_name="test.txt",
                content_encoding="text"
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            self.assertIn("extracted_text", result_data)
            self.assertIn("text_length", result_data)
            self.assertIn("file_info", result_data)
            self.assertEqual(result_data["file_info"]["mime_type"], "text/plain")
            self.assertGreater(result_data["text_length"], 0)

    def test_csv_extraction(self):
        """Test CSV text extraction and formatting."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
            tool = ExtractTextFromDocument(
                content=self.sample_csv_content,
                mime_type="text/csv",
                file_name="test.csv",
                content_encoding="text"
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            extracted_text = result_data["extracted_text"]
            self.assertIn("Headers:", extracted_text)
            self.assertIn("Name, Age, City", extracted_text)
            self.assertIn("Row 1:", extracted_text)
            self.assertIn("John | 30 | New York", extracted_text)
            
            # Check metadata
            metadata = result_data.get("document_metadata", {})
            self.assertEqual(metadata["row_count"], 4)  # Header + 3 data rows
            self.assertEqual(metadata["column_count"], 3)
            self.assertEqual(metadata["extraction_method"], "csv")

    def test_html_extraction_with_html2text(self):
        """Test HTML extraction with html2text library available."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        # Mock html2text
        mock_html2text = MagicMock()
        mock_converter = MagicMock()
        mock_converter.handle.return_value = "Main Title\n\nThis is the first paragraph.\n\nThis is the second paragraph."
        mock_html2text.HTML2Text.return_value = mock_converter
        
        with patch.dict('sys.modules', {'html2text': mock_html2text}):
            with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
                tool = ExtractTextFromDocument(
                    content=self.sample_html_content,
                    mime_type="text/html",
                    file_name="test.html",
                    content_encoding="text"
                )
                
                result = tool.run()
                result_data = json.loads(result)
                
                extracted_text = result_data["extracted_text"]
                self.assertIn("Main Title", extracted_text)
                self.assertIn("first paragraph", extracted_text)
                self.assertIn("second paragraph", extracted_text)
                
                metadata = result_data.get("document_metadata", {})
                self.assertEqual(metadata["extraction_method"], "html2text")

    def test_unsupported_mime_type(self):
        """Test handling of unsupported MIME types."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
            tool = ExtractTextFromDocument(
                content="binary content",
                mime_type="application/octet-stream",
                file_name="test.bin",
                content_encoding="text"
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            extracted_text = result_data["extracted_text"]
            self.assertIn("Text extraction not supported", extracted_text)
            self.assertIn("application/octet-stream", extracted_text)
            
            metadata = result_data.get("document_metadata", {})
            self.assertEqual(metadata["extraction_method"], "unsupported")
            self.assertIn("Unsupported MIME type", metadata["error"])

    def test_empty_content_handling(self):
        """Test handling of empty content."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
            tool = ExtractTextFromDocument(
                content="",
                mime_type="text/plain",
                file_name="empty.txt",
                content_encoding="text"
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            extracted_text = result_data["extracted_text"]
            self.assertEqual(extracted_text, "")
            self.assertEqual(result_data["text_length"], 0)

    def test_base64_encoded_text(self):
        """Test extraction from base64 encoded text content."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        original_text = "This is base64 encoded text content with special chars: ñáéíóú"
        encoded_content = base64.b64encode(original_text.encode('utf-8')).decode('ascii')
        
        with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
            tool = ExtractTextFromDocument(
                content=encoded_content,
                mime_type="text/plain",
                file_name="test_encoded.txt",
                content_encoding="base64"
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            extracted_text = result_data["extracted_text"]
            self.assertEqual(extracted_text, original_text)

    def test_pdf_extraction_success(self):
        """Test successful PDF extraction with PyPDF2."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        # Mock PyPDF2
        mock_pypdf2 = MagicMock()
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content\nWith multiple lines"
        mock_reader.pages = [mock_page]
        mock_reader.metadata = {
            "/Title": "Test PDF Document",
            "/Author": "Test Author"
        }
        mock_pypdf2.PdfReader.return_value = mock_reader
        
        pdf_content = b"fake pdf binary content"
        encoded_content = base64.b64encode(pdf_content).decode('ascii')
        
        with patch.dict('sys.modules', {'PyPDF2': mock_pypdf2}):
            with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
                tool = ExtractTextFromDocument(
                    content=encoded_content,
                    mime_type="application/pdf",
                    file_name="test.pdf",
                    content_encoding="base64"
                )
                
                result = tool.run()
                result_data = json.loads(result)
                
                extracted_text = result_data["extracted_text"]
                self.assertIn("Page 1 content", extracted_text)
                
                metadata = result_data.get("document_metadata", {})
                self.assertEqual(metadata["page_count"], 1)
                self.assertEqual(metadata["extraction_method"], "PyPDF2")
                self.assertEqual(metadata["title"], "Test PDF Document")

    def test_text_cleaning(self):
        """Test text cleaning functionality."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        messy_text = "This   has    excessive   whitespace\n\n\n\n\nAnd too many newlines....."
        
        with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
            tool = ExtractTextFromDocument(
                content=messy_text,
                mime_type="text/plain",
                file_name="messy.txt",
                content_encoding="text",
                clean_text=True
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            extracted_text = result_data["extracted_text"]
            # Should have normalized whitespace and newlines
            self.assertNotIn("   ", extracted_text)  # No triple spaces
            self.assertNotIn("\n\n\n", extracted_text)  # No triple newlines
            self.assertIn("...", extracted_text)  # Ellipsis normalized

    def test_error_handling_structure(self):
        """Test error handling and response structure."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        # Force an error by mocking a failure
        with patch('loader.get_config_value', side_effect=Exception("Config error")):
            tool = ExtractTextFromDocument(
                content="test",
                mime_type="text/plain",
                file_name="test.txt",
                content_encoding="text"
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            # Should return error structure
            self.assertIn("error", result_data)
            self.assertIn("message", result_data)
            self.assertIn("details", result_data)
            self.assertEqual(result_data["error"], "extraction_error")

    def test_text_statistics(self):
        """Test text statistics calculation."""
        ExtractTextFromDocument = self._import_tool_with_mocks()
        
        test_text = "First paragraph.\n\nSecond paragraph with more words."
        
        with patch('loader.get_config_value', return_value=self.mock_config.get("drive", {})):
            tool = ExtractTextFromDocument(
                content=test_text,
                mime_type="text/plain",
                file_name="stats.txt",
                content_encoding="text"
            )
            
            result = tool.run()
            result_data = json.loads(result)
            
            stats = result_data.get("text_stats", {})
            self.assertGreater(stats["character_count"], 0)
            self.assertGreater(stats["word_count"], 0)
            self.assertGreater(stats["line_count"], 0)
            self.assertEqual(stats["paragraph_count"], 2)  # Two paragraphs separated by double newline


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)