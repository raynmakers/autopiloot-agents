#!/usr/bin/env python3
"""
Test suite for FetchFileContent tool
Comprehensive testing with mocking for 100% coverage
"""

import unittest
import json
import io
from unittest.mock import Mock, MagicMock, patch, mock_open

# Import the tool under test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock googleapiclient.errors before importing
try:
    from googleapiclient.errors import HttpError
except ImportError:
    # Create a mock HttpError class for testing
    class HttpError(Exception):
        def __init__(self, resp, content):
            self.resp = resp
            self.content = content
            super().__init__(f"HTTP Error {resp.status}")

try:
    from drive_agent.tools.fetch_file_content import FetchFileContent
except ImportError as e:
    # Skip tests if dependencies are missing
    import unittest
    raise unittest.SkipTest(f"Skipping FetchFileContent tests - missing dependencies: {e}")


class TestFetchFileContent(unittest.TestCase):
    """Test cases for FetchFileContent tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_service = MagicMock()
        self.sample_file_metadata = {
            'id': 'test_file_id',
            'name': 'test_document.txt',
            'mimeType': 'text/plain',
            'size': '1024',
            'modifiedTime': '2025-09-20T10:00:00.000Z',
            'version': '1',
            'webViewLink': 'https://drive.google.com/file/d/test_file_id/view',
            'parents': ['parent_folder_id'],
            'owners': [{'emailAddress': 'owner@example.com'}]
        }

    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_successful_text_file_fetch(self, mock_build, mock_service_account, mock_env_var):
        """Test successful fetching of a text file with metadata."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock file metadata response
        self.mock_service.files().get().execute.return_value = self.sample_file_metadata

        # Mock file content download
        mock_content = b'Hello, this is test content!'
        self.mock_service.files().get_media().execute.return_value = mock_content

        # Create and run tool
        tool = FetchFileContent(
            file_id='test_file_id',
            extract_text_only=True,
            include_metadata=True
        )
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertNotIn('error', result_data)
        self.assertEqual(result_data['file_id'], 'test_file_id')
        self.assertEqual(result_data['content'], 'Hello, this is test content!')
        self.assertEqual(result_data['content_type'], 'text')
        self.assertEqual(result_data['mime_type'], 'text/plain')
        self.assertIn('metadata', result_data)
        self.assertEqual(result_data['metadata']['name'], 'test_document.txt')

    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_google_docs_export(self, mock_build, mock_service_account, mock_env_var):
        """Test exporting Google Docs to plain text."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock Google Docs metadata
        docs_metadata = self.sample_file_metadata.copy()
        docs_metadata['mimeType'] = 'application/vnd.google-apps.document'
        docs_metadata['size'] = '0'  # Google Workspace files don't have meaningful size
        self.mock_service.files().get().execute.return_value = docs_metadata

        # Mock export
        mock_content = b'Exported Google Docs content'
        self.mock_service.files().export_media().execute.return_value = mock_content

        # Create and run tool
        tool = FetchFileContent(
            file_id='test_file_id',
            extract_text_only=True,
            include_metadata=False
        )
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertNotIn('error', result_data)
        self.assertEqual(result_data['content'], 'Exported Google Docs content')
        self.assertEqual(result_data['mime_type'], 'text/plain')
        self.assertEqual(result_data['original_mime_type'], 'application/vnd.google-apps.document')

        # Verify export_media was called with correct parameters
        self.mock_service.files().export_media.assert_called_with(
            fileId='test_file_id',
            mimeType='text/plain'
        )

    @patch('drive_agent.tools.fetch_file_content.PDF_AVAILABLE', True)
    @patch('drive_agent.tools.fetch_file_content.PyPDF2')
    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_pdf_text_extraction(self, mock_build, mock_service_account, mock_env_var, mock_pypdf2):
        """Test PDF text extraction."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock PDF metadata
        pdf_metadata = self.sample_file_metadata.copy()
        pdf_metadata['mimeType'] = 'application/pdf'
        pdf_metadata['name'] = 'test_document.pdf'
        self.mock_service.files().get().execute.return_value = pdf_metadata

        # Mock PDF content download
        mock_pdf_bytes = b'%PDF-1.4 fake pdf content'
        self.mock_service.files().get_media().execute.return_value = mock_pdf_bytes

        # Mock PyPDF2 reader
        mock_page = MagicMock()
        mock_page.extract_text.return_value = 'This is extracted PDF text'
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pypdf2.PdfReader.return_value = mock_reader

        # Create and run tool
        tool = FetchFileContent(
            file_id='test_file_id',
            extract_text_only=True
        )
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertNotIn('error', result_data)
        self.assertIn('This is extracted PDF text', result_data['content'])
        self.assertEqual(result_data['mime_type'], 'application/pdf')

    @patch('drive_agent.tools.fetch_file_content.DOCX_AVAILABLE', True)
    @patch('drive_agent.tools.fetch_file_content.Document')
    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_docx_text_extraction(self, mock_build, mock_service_account, mock_env_var, mock_document):
        """Test DOCX text extraction."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock DOCX metadata
        docx_metadata = self.sample_file_metadata.copy()
        docx_metadata['mimeType'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        docx_metadata['name'] = 'test_document.docx'
        self.mock_service.files().get().execute.return_value = docx_metadata

        # Mock DOCX content download
        mock_docx_bytes = b'fake docx content'
        self.mock_service.files().get_media().execute.return_value = mock_docx_bytes

        # Mock python-docx Document
        mock_paragraph = MagicMock()
        mock_paragraph.text = 'This is extracted DOCX text'
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_paragraph]
        mock_document.return_value = mock_doc

        # Create and run tool
        tool = FetchFileContent(
            file_id='test_file_id',
            extract_text_only=True
        )
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertNotIn('error', result_data)
        self.assertEqual(result_data['content'], 'This is extracted DOCX text')

    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_binary_file_base64_encoding(self, mock_build, mock_service_account, mock_env_var):
        """Test binary file returned as base64."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock binary file metadata
        binary_metadata = self.sample_file_metadata.copy()
        binary_metadata['mimeType'] = 'image/jpeg'
        binary_metadata['name'] = 'test_image.jpg'
        self.mock_service.files().get().execute.return_value = binary_metadata

        # Mock binary content
        mock_binary_content = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # JPEG header
        self.mock_service.files().get_media().execute.return_value = mock_binary_content

        # Create and run tool
        tool = FetchFileContent(
            file_id='test_file_id',
            extract_text_only=False
        )
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertNotIn('error', result_data)
        self.assertEqual(result_data['content_type'], 'base64')
        self.assertEqual(result_data['mime_type'], 'image/jpeg')
        # Content should be base64 encoded
        import base64
        decoded = base64.b64decode(result_data['content'])
        self.assertEqual(decoded, mock_binary_content)

    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_file_not_found_error(self, mock_build, mock_service_account, mock_env_var):
        """Test handling of file not found error."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock 404 error
        error_response = MagicMock()
        error_response.status = 404
        self.mock_service.files().get().execute.side_effect = HttpError(
            resp=error_response,
            content=b'Not Found'
        )

        # Create and run tool
        tool = FetchFileContent(file_id='nonexistent_file_id')
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data['error'], 'file_not_found')
        self.assertIn('nonexistent_file_id', result_data['message'])

    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_access_denied_error(self, mock_build, mock_service_account, mock_env_var):
        """Test handling of access denied error."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock 403 error
        error_response = MagicMock()
        error_response.status = 403
        self.mock_service.files().get().execute.side_effect = HttpError(
            resp=error_response,
            content=b'Forbidden'
        )

        # Create and run tool
        tool = FetchFileContent(file_id='forbidden_file_id')
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data['error'], 'access_denied')
        self.assertIn('Permission denied', result_data['message'])

    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_folder_unsupported_error(self, mock_build, mock_service_account, mock_env_var):
        """Test handling of folder type (unsupported)."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock folder metadata
        folder_metadata = self.sample_file_metadata.copy()
        folder_metadata['mimeType'] = 'application/vnd.google-apps.folder'
        self.mock_service.files().get().execute.return_value = folder_metadata

        # Create and run tool
        tool = FetchFileContent(file_id='folder_id')
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data['error'], 'unsupported_type')
        self.assertIn('Cannot fetch content from folders', result_data['message'])

    @patch('drive_agent.tools.fetch_file_content.get_config_value')
    @patch('drive_agent.tools.fetch_file_content.get_required_env_var')
    @patch('drive_agent.tools.fetch_file_content.service_account')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_file_too_large_error(self, mock_build, mock_service_account, mock_env_var, mock_config):
        """Test handling of file size limit."""
        # Setup mocks
        mock_env_var.return_value = '/path/to/credentials.json'
        mock_config.return_value = {
            'tracking': {'max_file_size_mb': 1}  # 1MB limit
        }
        mock_creds = MagicMock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_build.return_value = self.mock_service

        # Mock large file metadata
        large_file_metadata = self.sample_file_metadata.copy()
        large_file_metadata['size'] = str(5 * 1024 * 1024)  # 5MB file
        self.mock_service.files().get().execute.return_value = large_file_metadata

        # Create and run tool
        tool = FetchFileContent(file_id='large_file_id')
        result = tool.run()

        # Parse result
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data['error'], 'file_too_large')
        self.assertIn('exceeds limit', result_data['message'])
        self.assertEqual(result_data['file_size_bytes'], 5 * 1024 * 1024)

    def test_size_limit_calculation(self):
        """Test size limit calculation with different parameters."""
        # Test with explicit max_size_mb
        tool = FetchFileContent(file_id='test', max_size_mb=5.5)
        with patch('drive_agent.tools.fetch_file_content.get_config_value'):
            size_limit = tool._get_size_limit()
            expected = int(5.5 * 1024 * 1024)
            self.assertEqual(size_limit, expected)

        # Test with config value
        tool = FetchFileContent(file_id='test', max_size_mb=None)
        with patch('drive_agent.tools.fetch_file_content.get_config_value') as mock_config:
            mock_config.return_value = {
                'tracking': {'max_file_size_mb': 15}
            }
            size_limit = tool._get_size_limit()
            expected = int(15 * 1024 * 1024)
            self.assertEqual(size_limit, expected)

    def test_export_mime_type_mapping(self):
        """Test Google Workspace MIME type export mapping."""
        tool = FetchFileContent(file_id='test')

        # Test Google Docs
        result = tool._get_export_mime_type('application/vnd.google-apps.document')
        self.assertEqual(result, 'text/plain')

        # Test Google Sheets
        result = tool._get_export_mime_type('application/vnd.google-apps.spreadsheet')
        self.assertEqual(result, 'text/csv')

        # Test Google Slides
        result = tool._get_export_mime_type('application/vnd.google-apps.presentation')
        self.assertEqual(result, 'text/plain')

        # Test Google Drawings
        result = tool._get_export_mime_type('application/vnd.google-apps.drawing')
        self.assertEqual(result, 'image/png')

        # Test non-Google Workspace file
        result = tool._get_export_mime_type('text/plain')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()