#!/usr/bin/env python3
"""
Working coverage test for fetch_file_content.py
Uses proper import strategy to ensure actual source code execution for coverage measurement
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util
from datetime import datetime, timezone


class TestFetchFileContentCoverageWorking(unittest.TestCase):
    """Working tests for FetchFileContent tool that properly measure coverage"""

    def _setup_mocks_and_import(self):
        """Set up mocks and import the real module for coverage measurement"""

        # Create proper nested module structure for Google APIs
        google_module = type('Module', (), {})
        google_oauth2_module = type('Module', (), {})
        google_oauth2_service_account_module = type('Module', (), {})
        googleapiclient_module = type('Module', (), {})
        googleapiclient_discovery_module = type('Module', (), {})
        googleapiclient_errors_module = type('Module', (), {})

        google_module.oauth2 = google_oauth2_module
        google_oauth2_module.service_account = google_oauth2_service_account_module
        googleapiclient_module.discovery = googleapiclient_discovery_module
        googleapiclient_module.errors = googleapiclient_errors_module

        # Create mock credentials and service
        mock_credentials = Mock()
        google_oauth2_service_account_module.Credentials = Mock()
        google_oauth2_service_account_module.Credentials.from_service_account_file = Mock(return_value=mock_credentials)

        # Create mock Drive service
        mock_service = Mock()
        googleapiclient_discovery_module.build = Mock(return_value=mock_service)

        # Create HttpError class
        class MockHttpError(Exception):
            def __init__(self, resp, content):
                self.resp = resp
                self.content = content
                super().__init__()

        googleapiclient_errors_module.HttpError = MockHttpError

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

        # Mock PdfReader
        class MockPdfReader:
            def __init__(self, *args, **kwargs):
                self.pages = [Mock()]
                self.pages[0].extract_text = Mock(return_value="Mock PDF text content")

        pypdf2_module.PdfReader = MockPdfReader

        # Mock Document
        class MockDocument:
            def __init__(self, *args, **kwargs):
                self.paragraphs = [Mock()]
                self.paragraphs[0].text = "Mock DOCX text content"

        docx_module.Document = MockDocument

        # Set up environment loader mock
        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value='/fake/path/to/credentials.json')

        # Apply all mocks to sys.modules
        sys.modules['google'] = google_module
        sys.modules['google.oauth2'] = google_oauth2_module
        sys.modules['google.oauth2.service_account'] = google_oauth2_service_account_module
        sys.modules['googleapiclient'] = googleapiclient_module
        sys.modules['googleapiclient.discovery'] = googleapiclient_discovery_module
        sys.modules['googleapiclient.errors'] = googleapiclient_errors_module
        sys.modules['agency_swarm'] = agency_swarm_module
        sys.modules['agency_swarm.tools'] = agency_swarm_tools_module
        sys.modules['pydantic'] = pydantic_module
        sys.modules['env_loader'] = env_loader_module
        sys.modules['PyPDF2'] = pypdf2_module
        sys.modules['docx'] = docx_module

        # Now import the actual module directly using importlib
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'drive_agent', 'tools', 'fetch_file_content.py')
        spec = importlib.util.spec_from_file_location("fetch_file_content", tool_path)
        module = importlib.util.module_from_spec(spec)

        # Execute module
        spec.loader.exec_module(module)

        return module.FetchFileContent, mock_service, MockHttpError

    def test_successful_pdf_content_fetch(self):
        """Test successful PDF content fetching"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='test_pdf_file', extract_text_only=True)

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Mock file metadata response for PDF
        mock_get.execute.return_value = {
            'id': 'test_pdf_file',
            'name': 'test_document.pdf',
            'mimeType': 'application/pdf',
            'size': '1024'
        }

        # Mock media download - need separate mock for get_media
        mock_get_media = Mock()
        mock_files.get_media.return_value = mock_get_media
        mock_get_media.execute.return_value = b'fake pdf content'

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('file_id', result_data)
        self.assertIn('content', result_data)
        self.assertEqual(result_data['file_id'], 'test_pdf_file')
        self.assertIn('Mock PDF text content', result_data['content'])

    def test_successful_docx_content_fetch(self):
        """Test successful DOCX content fetching"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='test_docx_file', extract_text_only=True)

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Mock file metadata response for DOCX
        mock_get.execute.return_value = {
            'id': 'test_docx_file',
            'name': 'test_document.docx',
            'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'size': '2048'
        }

        # Mock media download - need separate mock for get_media
        mock_get_media = Mock()
        mock_files.get_media.return_value = mock_get_media
        mock_get_media.execute.return_value = b'fake docx content'

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('file_id', result_data)
        self.assertIn('content', result_data)
        self.assertEqual(result_data['file_id'], 'test_docx_file')
        self.assertIn('Mock DOCX text content', result_data['content'])

    def test_text_file_content_fetch(self):
        """Test text file content fetching"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='test_txt_file', extract_text_only=True)

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Mock file metadata response for text file
        mock_get.execute.return_value = {
            'id': 'test_txt_file',
            'name': 'test_document.txt',
            'mimeType': 'text/plain',
            'size': '512'
        }

        # Mock media download - need separate mock for get_media
        mock_get_media = Mock()
        mock_files.get_media.return_value = mock_get_media
        mock_get_media.execute.return_value = b'This is test text content'

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('file_id', result_data)
        self.assertIn('content', result_data)
        self.assertEqual(result_data['file_id'], 'test_txt_file')
        self.assertIn('This is test text content', result_data['content'])

    def test_http_error_404_handling(self):
        """Test HTTP 404 error handling"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='nonexistent_file', extract_text_only=True)

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Create 404 HTTP error
        mock_response = Mock()
        mock_response.status = 404
        http_error = MockHttpError(mock_response, b'{"error": "not found"}')
        mock_get.execute.side_effect = http_error

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify error handling
        self.assertIn('error', result_data)
        self.assertEqual(result_data['error'], 'file_not_found')

    def test_http_error_403_handling(self):
        """Test HTTP 403 error handling"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='restricted_file', extract_text_only=True)

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Create 403 HTTP error
        mock_response = Mock()
        mock_response.status = 403
        http_error = MockHttpError(mock_response, b'{"error": "forbidden"}')
        mock_get.execute.side_effect = http_error

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify error handling
        self.assertIn('error', result_data)
        self.assertEqual(result_data['error'], 'access_denied')

    def test_unsupported_mime_type(self):
        """Test unsupported MIME type handling"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='test_file', extract_text_only=True)

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Mock file metadata response for unsupported type
        mock_get.execute.return_value = {
            'id': 'test_file',
            'name': 'test_image.jpg',
            'mimeType': 'image/jpeg',
            'size': '3072'
        }

        # Mock media download - need separate mock for get_media
        mock_get_media = Mock()
        mock_files.get_media.return_value = mock_get_media
        mock_get_media.execute.return_value = b'fake image content'

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify handling of unsupported type
        self.assertIn('file_id', result_data)
        self.assertEqual(result_data['file_id'], 'test_file')

    def test_pdf_extraction_error_handling(self):
        """Test PDF extraction error handling"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='test_pdf_file', extract_text_only=True)

        # Test the _extract_text_from_pdf method directly
        pdf_bytes = b'fake corrupted pdf content'

        # Mock PDF reader to throw exception
        with patch('PyPDF2.PdfReader') as mock_pdf_reader:
            mock_pdf_reader.side_effect = Exception("PDF extraction error")

            result = tool._extract_text_from_pdf(pdf_bytes)

            # Should handle error gracefully
            self.assertIsInstance(result, str)

    def test_docx_extraction_error_handling(self):
        """Test DOCX extraction error handling"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='test_docx_file', extract_text_only=True)

        # Test the _extract_text_from_docx method directly
        docx_bytes = b'fake corrupted docx content'

        # Mock Document to throw exception
        with patch('docx.Document') as mock_document:
            mock_document.side_effect = Exception("DOCX extraction error")

            result = tool._extract_text_from_docx(docx_bytes)

            # Should handle error gracefully
            self.assertIsInstance(result, str)

    def test_text_extraction_with_encoding_issues(self):
        """Test text extraction with encoding issues"""
        FetchFileContent, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = FetchFileContent(file_id='test_file', extract_text_only=True)

        # Test with problematic encoding
        problematic_bytes = b'\xff\xfe\x00\x00invalid'
        result = tool._process_content(problematic_bytes, 'text/plain')

        # Should handle encoding issues gracefully
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()