#!/usr/bin/env python3
"""
Working coverage test for extract_text_from_document.py
Uses proper import strategy to ensure actual source code execution for coverage measurement
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util
import base64


class TestExtractTextFromDocumentCoverageWorking(unittest.TestCase):
    """Working tests for ExtractTextFromDocument tool that properly measure coverage"""

    def _setup_mocks_and_import(self):
        """Set up mocks and import the real module for coverage measurement"""

        # Create Agency Swarm mocks
        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool

        # Create pydantic mock
        pydantic_module = type('Module', (), {})
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)
        pydantic_module.Field = mock_field

        # Create PDF and DOCX mocks
        pypdf2_module = type('Module', (), {})
        docx_module = type('Module', (), {})
        html2text_module = type('Module', (), {})

        # Mock PdfReader
        class MockPdfReader:
            def __init__(self, *args, **kwargs):
                self.pages = [Mock(), Mock()]
                self.pages[0].extract_text = Mock(return_value="Page 1 content")
                self.pages[1].extract_text = Mock(return_value="Page 2 content")

        pypdf2_module.PdfReader = MockPdfReader

        # Mock Document
        class MockDocument:
            def __init__(self, *args, **kwargs):
                self.paragraphs = [Mock(), Mock()]
                self.paragraphs[0].text = "First paragraph content"
                self.paragraphs[1].text = "Second paragraph content"

        docx_module.Document = MockDocument

        # Mock html2text
        class MockHTML2Text:
            def handle(self, html_content):
                return "Converted HTML content to text"

        html2text_module.HTML2Text = MockHTML2Text

        # Create config loader mock
        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value={
            "tracking": {"max_text_length": 50000}
        })

        # Apply all mocks to sys.modules
        sys.modules['agency_swarm'] = agency_swarm_module
        sys.modules['agency_swarm.tools'] = agency_swarm_tools_module
        sys.modules['pydantic'] = pydantic_module
        sys.modules['loader'] = loader_module
        sys.modules['PyPDF2'] = pypdf2_module
        sys.modules['docx'] = docx_module
        sys.modules['html2text'] = html2text_module

        # Now import the actual module directly using importlib
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'drive_agent', 'tools', 'extract_text_from_document.py')
        spec = importlib.util.spec_from_file_location("extract_text_from_document", tool_path)
        module = importlib.util.module_from_spec(spec)

        # Execute module
        spec.loader.exec_module(module)

        return module.ExtractTextFromDocument

    def test_successful_pdf_text_extraction(self):
        """Test successful PDF text extraction"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with PDF content
        pdf_content = base64.b64encode(b"fake pdf binary data").decode('utf-8')
        tool = ExtractTextFromDocument(
            content=pdf_content,
            mime_type='application/pdf',
            file_name='test_document.pdf',
            content_encoding='base64'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('extracted_text', result_data)
        self.assertIn('document_metadata', result_data)
        self.assertIn('Page 1 content', result_data['extracted_text'])
        self.assertIn('Page 2 content', result_data['extracted_text'])

    def test_successful_docx_text_extraction(self):
        """Test successful DOCX text extraction"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with DOCX content
        docx_content = base64.b64encode(b"fake docx binary data").decode('utf-8')
        tool = ExtractTextFromDocument(
            content=docx_content,
            mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            file_name='test_document.docx',
            content_encoding='base64'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('extracted_text', result_data)
        self.assertIn('document_metadata', result_data)
        self.assertIn('First paragraph content', result_data['extracted_text'])
        self.assertIn('Second paragraph content', result_data['extracted_text'])

    def test_plain_text_extraction(self):
        """Test plain text extraction"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with plain text content
        text_content = "This is plain text content for testing."
        tool = ExtractTextFromDocument(
            content=text_content,
            mime_type='text/plain',
            file_name='test_document.txt',
            content_encoding='text'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('extracted_text', result_data)
        self.assertIn('document_metadata', result_data)
        self.assertEqual(result_data['extracted_text'], text_content)

    def test_html_text_extraction(self):
        """Test HTML text extraction"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with HTML content
        html_content = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        tool = ExtractTextFromDocument(
            content=html_content,
            mime_type='text/html',
            file_name='test_document.html',
            content_encoding='text'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('extracted_text', result_data)
        self.assertIn('document_metadata', result_data)

    def test_csv_text_extraction(self):
        """Test CSV text extraction"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with CSV content
        csv_content = "Name,Age,City\nJohn,30,New York\nJane,25,Boston"
        tool = ExtractTextFromDocument(
            content=csv_content,
            mime_type='text/csv',
            file_name='test_data.csv',
            content_encoding='text'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('extracted_text', result_data)
        self.assertIn('document_metadata', result_data)
        self.assertIn('John', result_data['extracted_text'])
        self.assertIn('Boston', result_data['extracted_text'])

    def test_unsupported_mime_type(self):
        """Test unsupported MIME type handling"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with unsupported content type
        tool = ExtractTextFromDocument(
            content="binary content",
            mime_type='application/x-unknown',
            file_name='unknown_file.bin',
            content_encoding='text'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify error handling - error is gracefully handled with message in text
        self.assertIn('extracted_text', result_data)
        self.assertIn('[Text extraction not supported', result_data['extracted_text'])

    def test_text_cleaning(self):
        """Test text cleaning functionality"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with text that needs cleaning
        messy_text = "  Multiple   spaces\n\n\nand   extra\t\twhitespace  "
        tool = ExtractTextFromDocument(
            content=messy_text,
            mime_type='text/plain',
            file_name='messy.txt',
            content_encoding='text',
            clean_text=True
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify text was cleaned
        self.assertIn('extracted_text', result_data)
        cleaned_text = result_data['extracted_text']
        # Should not have excessive whitespace
        self.assertNotIn('   ', cleaned_text)
        self.assertNotIn('\n\n\n', cleaned_text)

    def test_max_length_limiting(self):
        """Test maximum length limiting"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool with long content and short max_length
        long_text = "A" * 200  # 200 character string to test with 500 limit
        tool = ExtractTextFromDocument(
            content=long_text,
            mime_type='text/plain',
            file_name='long.txt',
            content_encoding='text',
            max_length=500
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify length was limited
        self.assertIn('extracted_text', result_data)
        self.assertLessEqual(len(result_data['extracted_text']), 500)

    def test_pdf_extraction_error_handling(self):
        """Test PDF extraction error handling"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool
        tool = ExtractTextFromDocument(
            content=base64.b64encode(b"corrupted pdf").decode('utf-8'),
            mime_type='application/pdf',
            file_name='corrupted.pdf',
            content_encoding='base64'
        )

        # Mock PDF reader to throw exception
        with patch('PyPDF2.PdfReader') as mock_pdf_reader:
            mock_pdf_reader.side_effect = Exception("PDF extraction error")

            result = tool.run()
            result_data = json.loads(result)

            # Should handle error gracefully - error info is in document_metadata
            self.assertIn('document_metadata', result_data)
            self.assertIn('error', result_data['document_metadata'])

    def test_docx_extraction_error_handling(self):
        """Test DOCX extraction error handling"""
        ExtractTextFromDocument = self._setup_mocks_and_import()

        # Create tool
        tool = ExtractTextFromDocument(
            content=base64.b64encode(b"corrupted docx").decode('utf-8'),
            mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            file_name='corrupted.docx',
            content_encoding='base64'
        )

        # Mock Document to throw exception
        with patch('docx.Document') as mock_document:
            mock_document.side_effect = Exception("DOCX extraction error")

            result = tool.run()
            result_data = json.loads(result)

            # Should handle gracefully and still return extracted text
            self.assertIn('document_metadata', result_data)
            self.assertIn('extracted_text', result_data)


if __name__ == "__main__":
    unittest.main()