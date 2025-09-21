"""
Comprehensive tests for FetchFileContent tool.
Tests all file fetching functionality without external dependencies.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import base64
import sys
import os


class TestFetchFileContentComplete(unittest.TestCase):
    """Comprehensive test suite for FetchFileContent tool."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        # Mock environment loader
        self.mock_env_patcher = patch('drive_agent.tools.fetch_file_content.get_required_env_var')
        self.mock_env = self.mock_env_patcher.start()
        self.mock_env.return_value = "/fake/path/to/credentials.json"

        # Mock config loader
        self.mock_config_patcher = patch('drive_agent.tools.fetch_file_content.get_config_value')
        self.mock_config = self.mock_config_patcher.start()
        self.mock_config.return_value = {"tracking": {"max_file_size_mb": 10}}

        # Mock agency_swarm
        self.mock_agency_patcher = patch('drive_agent.tools.fetch_file_content.BaseTool')
        self.mock_base_tool = self.mock_agency_patcher.start()

        # Mock Google Cloud APIs
        self.mock_service_account_patcher = patch('drive_agent.tools.fetch_file_content.service_account')
        self.mock_service_account = self.mock_service_account_patcher.start()

        self.mock_build_patcher = patch('drive_agent.tools.fetch_file_content.build')
        self.mock_build = self.mock_build_patcher.start()

        self.mock_http_error_patcher = patch('drive_agent.tools.fetch_file_content.HttpError')
        self.mock_http_error = self.mock_http_error_patcher.start()

        # Mock optional dependencies
        self.mock_pypdf2_patcher = patch('drive_agent.tools.fetch_file_content.PyPDF2', create=True)
        self.mock_pypdf2 = self.mock_pypdf2_patcher.start()

        self.mock_docx_patcher = patch('drive_agent.tools.fetch_file_content.Document', create=True)
        self.mock_docx = self.mock_docx_patcher.start()

        # Import the tool after mocking
        from drive_agent.tools.fetch_file_content import FetchFileContent
        self.FetchFileContent = FetchFileContent

    def tearDown(self):
        """Clean up mocks."""
        self.mock_env_patcher.stop()
        self.mock_config_patcher.stop()
        self.mock_agency_patcher.stop()
        self.mock_service_account_patcher.stop()
        self.mock_build_patcher.stop()
        self.mock_http_error_patcher.stop()
        self.mock_pypdf2_patcher.stop()
        self.mock_docx_patcher.stop()

    def _create_mock_drive_service(self, file_metadata=None, file_content=b"test content"):
        """Create a mock Google Drive service."""
        mock_service = Mock()

        # Mock files().get() for metadata
        if file_metadata is None:
            file_metadata = {
                'id': 'test_file_id',
                'name': 'test_file.txt',
                'mimeType': 'text/plain',
                'size': '100',
                'modifiedTime': '2024-01-01T00:00:00Z',
                'version': '1',
                'webViewLink': 'https://drive.google.com/file/d/test_file_id/view',
                'parents': ['parent_folder_id'],
                'owners': [{'emailAddress': 'owner@example.com'}]
            }

        mock_get = Mock()
        mock_get.execute.return_value = file_metadata
        mock_service.files().get.return_value = mock_get

        # Mock files().get_media() for content download
        mock_media = Mock()
        mock_media.execute.return_value = file_content
        mock_service.files().get_media.return_value = mock_media

        # Mock files().export_media() for Google Workspace files
        mock_export = Mock()
        mock_export.execute.return_value = file_content
        mock_service.files().export_media.return_value = mock_export

        self.mock_build.return_value = mock_service
        return mock_service

    def test_successful_text_file_fetch(self):
        """Test successful fetching of plain text file."""
        self._create_mock_drive_service()

        tool = self.FetchFileContent(
            file_id="test_file_id",
            extract_text_only=True,
            include_metadata=True
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["file_id"], "test_file_id")
        self.assertEqual(result_data["content_type"], "text")
        self.assertIn("content", result_data)
        self.assertIn("metadata", result_data)

    def test_file_not_found_error(self):
        """Test handling of file not found error."""
        mock_service = self._create_mock_drive_service()

        # Mock 404 error
        error = Exception("404")
        error.resp = Mock()
        error.resp.status = 404
        mock_service.files().get.return_value.execute.side_effect = error
        self.mock_http_error.side_effect = error

        tool = self.FetchFileContent(file_id="nonexistent_file_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "file_not_found")

    def test_access_denied_error(self):
        """Test handling of access denied error."""
        mock_service = self._create_mock_drive_service()

        # Mock 403 error
        error = Exception("403")
        error.resp = Mock()
        error.resp.status = 403
        mock_service.files().get.return_value.execute.side_effect = error
        self.mock_http_error.side_effect = error

        tool = self.FetchFileContent(file_id="restricted_file_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "access_denied")

    def test_folder_type_rejection(self):
        """Test rejection of folder types."""
        folder_metadata = {
            'id': 'folder_id',
            'name': 'test_folder',
            'mimeType': 'application/vnd.google-apps.folder',
            'size': '0'
        }
        self._create_mock_drive_service(file_metadata=folder_metadata)

        tool = self.FetchFileContent(file_id="folder_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "unsupported_type")

    def test_file_size_limit_exceeded(self):
        """Test handling of files exceeding size limit."""
        large_file_metadata = {
            'id': 'large_file_id',
            'name': 'large_file.txt',
            'mimeType': 'text/plain',
            'size': str(20 * 1024 * 1024),  # 20MB
            'modifiedTime': '2024-01-01T00:00:00Z'
        }
        self._create_mock_drive_service(file_metadata=large_file_metadata)

        tool = self.FetchFileContent(
            file_id="large_file_id",
            max_size_mb=10.0
        )
        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "file_too_large")

    def test_google_workspace_file_export(self):
        """Test export of Google Workspace files."""
        gdoc_metadata = {
            'id': 'gdoc_id',
            'name': 'test_document',
            'mimeType': 'application/vnd.google-apps.document',
            'modifiedTime': '2024-01-01T00:00:00Z'
        }
        self._create_mock_drive_service(
            file_metadata=gdoc_metadata,
            file_content=b"Google Doc exported content"
        )

        tool = self.FetchFileContent(file_id="gdoc_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["mime_type"], "text/plain")
        self.assertEqual(result_data["original_mime_type"], "application/vnd.google-apps.document")

    def test_pdf_text_extraction_with_pypdf2(self):
        """Test PDF text extraction when PyPDF2 is available."""
        # Mock PDF reader
        mock_page = Mock()
        mock_page.extract_text.return_value = "PDF page content"

        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        self.mock_pypdf2.PdfReader.return_value = mock_reader

        pdf_metadata = {
            'id': 'pdf_id',
            'name': 'test.pdf',
            'mimeType': 'application/pdf',
            'size': '1000'
        }

        with patch('drive_agent.tools.fetch_file_content.PDF_AVAILABLE', True):
            self._create_mock_drive_service(
                file_metadata=pdf_metadata,
                file_content=b"fake pdf content"
            )

            tool = self.FetchFileContent(file_id="pdf_id")
            result = tool.run()
            result_data = json.loads(result)

            self.assertNotIn("error", result_data)
            self.assertIn("PDF page content", result_data["content"])

    def test_pdf_text_extraction_without_pypdf2(self):
        """Test PDF handling when PyPDF2 is not available."""
        pdf_metadata = {
            'id': 'pdf_id',
            'name': 'test.pdf',
            'mimeType': 'application/pdf',
            'size': '1000'
        }

        with patch('drive_agent.tools.fetch_file_content.PDF_AVAILABLE', False):
            self._create_mock_drive_service(
                file_metadata=pdf_metadata,
                file_content=b"fake pdf content"
            )

            tool = self.FetchFileContent(file_id="pdf_id")
            result = tool.run()
            result_data = json.loads(result)

            self.assertNotIn("error", result_data)
            self.assertIn("PDF text extraction not available", result_data["content"])

    def test_docx_text_extraction_with_python_docx(self):
        """Test DOCX text extraction when python-docx is available."""
        # Mock DOCX document
        mock_paragraph = Mock()
        mock_paragraph.text = "DOCX paragraph content"

        mock_doc = Mock()
        mock_doc.paragraphs = [mock_paragraph]
        self.mock_docx.return_value = mock_doc

        docx_metadata = {
            'id': 'docx_id',
            'name': 'test.docx',
            'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'size': '2000'
        }

        with patch('drive_agent.tools.fetch_file_content.DOCX_AVAILABLE', True):
            self._create_mock_drive_service(
                file_metadata=docx_metadata,
                file_content=b"fake docx content"
            )

            tool = self.FetchFileContent(file_id="docx_id")
            result = tool.run()
            result_data = json.loads(result)

            self.assertNotIn("error", result_data)
            self.assertIn("DOCX paragraph content", result_data["content"])

    def test_docx_text_extraction_without_python_docx(self):
        """Test DOCX handling when python-docx is not available."""
        docx_metadata = {
            'id': 'docx_id',
            'name': 'test.docx',
            'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'size': '2000'
        }

        with patch('drive_agent.tools.fetch_file_content.DOCX_AVAILABLE', False):
            self._create_mock_drive_service(
                file_metadata=docx_metadata,
                file_content=b"fake docx content"
            )

            tool = self.FetchFileContent(file_id="docx_id")
            result = tool.run()
            result_data = json.loads(result)

            self.assertNotIn("error", result_data)
            self.assertIn("DOCX text extraction not available", result_data["content"])

    def test_binary_content_base64_encoding(self):
        """Test binary content returned as base64."""
        binary_metadata = {
            'id': 'binary_id',
            'name': 'test.bin',
            'mimeType': 'application/octet-stream',
            'size': '500'
        }
        binary_content = b"binary file content"

        self._create_mock_drive_service(
            file_metadata=binary_metadata,
            file_content=binary_content
        )

        tool = self.FetchFileContent(
            file_id="binary_id",
            extract_text_only=False
        )
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["content_type"], "base64")
        # Verify base64 encoding
        decoded = base64.b64decode(result_data["content"])
        self.assertEqual(decoded, binary_content)

    def test_text_content_unicode_handling(self):
        """Test handling of various text encodings."""
        text_metadata = {
            'id': 'text_id',
            'name': 'unicode.txt',
            'mimeType': 'text/plain',
            'size': '100'
        }
        unicode_content = "Hello 世界 🌍".encode('utf-8')

        self._create_mock_drive_service(
            file_metadata=text_metadata,
            file_content=unicode_content
        )

        tool = self.FetchFileContent(file_id="text_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertIn("Hello 世界 🌍", result_data["content"])

    def test_csv_file_processing(self):
        """Test CSV file content processing."""
        csv_metadata = {
            'id': 'csv_id',
            'name': 'data.csv',
            'mimeType': 'text/csv',
            'size': '200'
        }
        csv_content = b"Name,Age,City\nJohn,25,NYC\nJane,30,LA"

        self._create_mock_drive_service(
            file_metadata=csv_metadata,
            file_content=csv_content
        )

        tool = self.FetchFileContent(file_id="csv_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertIn("Name,Age,City", result_data["content"])

    def test_metadata_inclusion_optional(self):
        """Test that metadata inclusion is optional."""
        self._create_mock_drive_service()

        tool = self.FetchFileContent(
            file_id="test_file_id",
            include_metadata=False
        )
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertNotIn("metadata", result_data)
        self.assertIn("content", result_data)

    def test_unsupported_mime_type_handling(self):
        """Test handling of unsupported MIME types."""
        unsupported_metadata = {
            'id': 'unsupported_id',
            'name': 'file.xyz',
            'mimeType': 'application/x-unknown',
            'size': '100'
        }

        self._create_mock_drive_service(
            file_metadata=unsupported_metadata,
            file_content=b"unknown format content"
        )

        tool = self.FetchFileContent(
            file_id="unsupported_id",
            extract_text_only=True
        )
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertIn("Text extraction not supported", result_data["content"])

    def test_download_error_handling(self):
        """Test handling of download errors."""
        mock_service = self._create_mock_drive_service()

        # Mock download error
        error = Exception("Download failed")
        error.resp = Mock()
        error.resp.status = 500
        mock_service.files().get_media.return_value.execute.side_effect = error
        self.mock_http_error.side_effect = error

        tool = self.FetchFileContent(file_id="error_file_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertIn("download_error", result_data["error"])

    def test_service_initialization_failure(self):
        """Test handling of Drive service initialization failure."""
        self.mock_service_account.Credentials.from_service_account_file.side_effect = Exception("Auth failed")

        tool = self.FetchFileContent(file_id="test_file_id")
        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "fetch_error")

    def test_custom_size_limit_configuration(self):
        """Test custom size limit configuration."""
        self._create_mock_drive_service()

        # Test with custom size limit
        tool = self.FetchFileContent(
            file_id="test_file_id",
            max_size_mb=5.0
        )

        # Access the private method to test size limit calculation
        size_limit = tool._get_size_limit()
        expected_limit = int(5.0 * 1024 * 1024)
        self.assertEqual(size_limit, expected_limit)

    def test_export_mime_type_mapping(self):
        """Test Google Workspace export MIME type mapping."""
        tool = self.FetchFileContent(file_id="test_id")

        # Test various Google Workspace types
        self.assertEqual(
            tool._get_export_mime_type('application/vnd.google-apps.document'),
            'text/plain'
        )
        self.assertEqual(
            tool._get_export_mime_type('application/vnd.google-apps.spreadsheet'),
            'text/csv'
        )
        self.assertEqual(
            tool._get_export_mime_type('application/vnd.google-apps.presentation'),
            'text/plain'
        )
        self.assertIsNone(
            tool._get_export_mime_type('text/plain')
        )


if __name__ == '__main__':
    unittest.main()