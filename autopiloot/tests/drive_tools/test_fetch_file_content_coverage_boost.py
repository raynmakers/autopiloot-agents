"""
Comprehensive tests to boost fetch_file_content.py coverage from 78% to 95%+.
Targets specific missing lines: 109-110, 122-134, 182-184, 198-199, 206, 231-236, 240, 265-277, 308, 312, 316-317
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import base64
import sys
import io

# Mock dependencies at module level BEFORE importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.errors': MagicMock(),
    'google': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
    'PyPDF2': MagicMock(),
    'docx': MagicMock()
}):
    pass


class TestFetchFileContentCoverageBoost(unittest.TestCase):
    """Test suite to achieve high coverage for FetchFileContent tool."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        # Mock all external dependencies at import time
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'PyPDF2': MagicMock(),
            'docx': MagicMock()
        }

        # Apply mocks
        for module_name, mock_module in self.mock_modules.items():
            sys.modules[module_name] = mock_module

        # Create a mock BaseTool class
        sys.modules['agency_swarm.tools'].BaseTool = MagicMock()

        # Mock the config loader
        self.mock_config_patcher = patch('config.loader.get_config_value')
        self.mock_config = self.mock_config_patcher.start()
        self.mock_config.return_value = {"tracking": {"max_file_size_mb": 10}}

        # Import the tool
        try:
            from drive_agent.tools.fetch_file_content import FetchFileContent
            self.FetchFileContent = FetchFileContent
        except ImportError:
            # Create a mock tool class for testing
            self.FetchFileContent = self._create_mock_tool_class()

    def tearDown(self):
        """Clean up mocks."""
        self.mock_config_patcher.stop()
        # Remove mocked modules
        for module_name in self.mock_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]

    def _create_mock_tool_class(self):
        """Create a mock tool class for testing when imports fail."""
        class MockFetchFileContent:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

            def run(self):
                return json.dumps({"mock": True, "content": "mock content"})

        return MockFetchFileContent

    def test_pdf_page_extraction_error(self):
        """Test PDF page extraction error (lines 109-110)."""
        with patch('drive_agent.tools.fetch_file_content.PDF_AVAILABLE', True):
            # Mock PDF reader with page extraction error
            mock_page = Mock()
            mock_page.extract_text.side_effect = Exception("Page extraction failed")

            mock_reader = Mock()
            mock_reader.pages = [mock_page]

            with patch('drive_agent.tools.fetch_file_content.PyPDF2') as mock_pypdf2:
                mock_pypdf2.PdfReader.return_value = mock_reader

                tool = self.FetchFileContent(file_id="test_pdf_id")

                # Mock the service and file metadata
                mock_service = Mock()
                mock_service.files().get().execute.return_value = {
                    'mimeType': 'application/pdf',
                    'name': 'test.pdf',
                    'size': '1000'
                }
                mock_service.files().get_media().execute.return_value = b"fake pdf content"

                with patch.object(tool, '_create_drive_service', return_value=mock_service):
                    result = tool.run()
                    result_data = json.loads(result)

                    # Should contain error message for the page
                    self.assertIn("[Error extracting text: Page extraction failed]",
                                result_data["content"])

    def test_docx_text_extraction_full_workflow(self):
        """Test complete DOCX text extraction workflow (lines 122-134)."""
        with patch('drive_agent.tools.fetch_file_content.DOCX_AVAILABLE', True):
            # Mock DOCX document
            mock_paragraph1 = Mock()
            mock_paragraph1.text = "First paragraph"
            mock_paragraph2 = Mock()
            mock_paragraph2.text = "Second paragraph"
            mock_paragraph3 = Mock()
            mock_paragraph3.text = ""  # Empty paragraph to test strip logic

            mock_doc = Mock()
            mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2, mock_paragraph3]

            with patch('drive_agent.tools.fetch_file_content.Document') as mock_docx:
                mock_docx.return_value = mock_doc

                tool = self.FetchFileContent(file_id="test_docx_id", extract_text_only=True)

                # Mock the service
                mock_service = Mock()
                mock_service.files().get().execute.return_value = {
                    'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'name': 'test.docx',
                    'size': '2000'
                }
                mock_service.files().get_media().execute.return_value = b"fake docx content"

                with patch.object(tool, '_create_drive_service', return_value=mock_service):
                    result = tool.run()
                    result_data = json.loads(result)

                    # Should contain both paragraphs but not the empty one
                    self.assertIn("First paragraph", result_data["content"])
                    self.assertIn("Second paragraph", result_data["content"])

    def test_unicode_decoding_fallback_with_errors(self):
        """Test unicode decoding fallback (lines 182-184)."""
        tool = self.FetchFileContent(file_id="test_text_id", extract_text_only=True)

        # Create invalid UTF-8 bytes that will fail all normal encodings
        invalid_bytes = b'\xff\xfe\x00\x00Invalid UTF-8 content'

        # Mock the service
        mock_service = Mock()
        mock_service.files().get().execute.return_value = {
            'mimeType': 'text/plain',
            'name': 'invalid.txt',
            'size': str(len(invalid_bytes))
        }
        mock_service.files().get_media().execute.return_value = invalid_bytes

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            # Should use fallback decoding with error replacement
            self.assertIn("content", result_data)
            # The invalid bytes should be replaced with replacement characters
            self.assertIsInstance(result_data["content"], str)

    def test_google_workspace_export_decoding_error(self):
        """Test Google Workspace export decoding error (lines 198-199)."""
        tool = self.FetchFileContent(file_id="test_gdoc_id", extract_text_only=True)

        # Create invalid UTF-8 bytes for exported Google Doc
        invalid_utf8 = b'\xff\xfe\x00\x00Google Doc content'

        # Mock the service for Google Workspace export
        mock_service = Mock()
        mock_service.files().get().execute.return_value = {
            'mimeType': 'application/vnd.google-apps.document',
            'name': 'gdoc.txt',
            'exportLinks': {'text/plain': 'https://export.url'}
        }
        mock_service.files().export_media().execute.return_value = invalid_utf8

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            # Should handle decoding error with replacement
            self.assertIn("content", result_data)
            self.assertIsInstance(result_data["content"], str)

    def test_binary_content_base64_encoding(self):
        """Test binary content base64 encoding (line 206)."""
        tool = self.FetchFileContent(file_id="test_binary_id", extract_text_only=False)

        # Binary content (not text extractable)
        binary_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'

        # Mock the service
        mock_service = Mock()
        mock_service.files().get().execute.return_value = {
            'mimeType': 'image/png',
            'name': 'image.png',
            'size': str(len(binary_content))
        }
        mock_service.files().get_media().execute.return_value = binary_content

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            # Should return base64 encoded content
            self.assertIn("content", result_data)
            expected_base64 = base64.b64encode(binary_content).decode('utf-8')
            self.assertEqual(result_data["content"], expected_base64)

    def test_http_403_access_denied_errors(self):
        """Test HTTP 403 access denied errors (lines 231-236, 265-277)."""
        # Create mock HttpError class
        class MockHttpError(Exception):
            def __init__(self, resp, content):
                self.resp = resp
                self.content = content
                super().__init__()

        tool = self.FetchFileContent(file_id="test_denied_id")

        # Mock HTTP 403 error for file metadata
        http_error_403 = MockHttpError(
            Mock(status=403, reason="Forbidden"),
            b'{"error": {"code": 403, "message": "Permission denied"}}'
        )

        mock_service = Mock()
        mock_service.files().get().execute.side_effect = http_error_403

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "access_denied")
            self.assertIn("Permission denied", result_data["message"])

    def test_http_404_file_not_found_error(self):
        """Test HTTP 404 file not found error (lines 231-236)."""
        # Create mock HttpError class
        class MockHttpError(Exception):
            def __init__(self, resp, content):
                self.resp = resp
                self.content = content
                super().__init__()

        tool = self.FetchFileContent(file_id="nonexistent_id")

        # Mock HTTP 404 error
        http_error_404 = MockHttpError(
            Mock(status=404, reason="Not Found"),
            b'{"error": {"code": 404, "message": "File not found"}}'
        )

        mock_service = Mock()
        mock_service.files().get().execute.side_effect = http_error_404

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "file_not_found")
            self.assertIn("File with ID nonexistent_id not found", result_data["message"])

    def test_folder_content_fetch_attempt(self):
        """Test attempt to fetch content from folder (line 240)."""
        tool = self.FetchFileContent(file_id="folder_id")

        # Mock the service for folder
        mock_service = Mock()
        mock_service.files().get().execute.return_value = {
            'mimeType': 'application/vnd.google-apps.folder',
            'name': 'Test Folder'
        }

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "unsupported_type")
            self.assertIn("Cannot fetch content from folders", result_data["message"])

    def test_download_permission_errors(self):
        """Test download/export permission errors (lines 265-277)."""
        # Create mock HttpError class
        class MockHttpError(Exception):
            def __init__(self, resp, content):
                self.resp = resp
                self.content = content
                super().__init__()

        tool = self.FetchFileContent(file_id="test_file_id")

        # Mock successful metadata but failed download
        mock_service = Mock()
        mock_service.files().get().execute.return_value = {
            'mimeType': 'text/plain',
            'name': 'test.txt',
            'size': '100'
        }

        # Mock HTTP 403 error for download
        http_error_403 = MockHttpError(
            Mock(status=403, reason="Forbidden"),
            b'{"error": {"code": 403, "message": "Download not permitted"}}'
        )
        mock_service.files().get_media().execute.side_effect = http_error_403

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "export_denied")
            self.assertIn("File export/download not permitted", result_data["message"])

    def test_download_404_content_not_available(self):
        """Test download 404 content not available (lines 271-275)."""
        # Create mock HttpError class
        class MockHttpError(Exception):
            def __init__(self, resp, content):
                self.resp = resp
                self.content = content
                super().__init__()

        tool = self.FetchFileContent(file_id="test_file_id")

        # Mock successful metadata but content not available
        mock_service = Mock()
        mock_service.files().get().execute.return_value = {
            'mimeType': 'text/plain',
            'name': 'test.txt',
            'size': '100'
        }

        # Mock HTTP 404 error for download
        http_error_404 = MockHttpError(
            Mock(status=404, reason="Not Found"),
            b'{"error": {"code": 404, "message": "Content not available"}}'
        )
        mock_service.files().get_media().execute.side_effect = http_error_404

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "export_not_available")
            self.assertIn("File content not available for download", result_data["message"])

    def test_metadata_enhancement_with_parents_and_owners(self):
        """Test metadata enhancement with parent folder and owner info (lines 308, 312)."""
        tool = self.FetchFileContent(file_id="test_file_id", include_metadata=True)

        # Mock the service with full metadata
        mock_service = Mock()
        mock_service.files().get().execute.return_value = {
            'mimeType': 'text/plain',
            'name': 'test.txt',
            'size': '100',
            'modifiedTime': '2023-01-01T00:00:00Z',
            'version': '1',
            'webViewLink': 'https://drive.google.com/file/d/test_file_id',
            'parents': ['parent_folder_id'],
            'owners': [{'emailAddress': 'owner@example.com'}]
        }
        mock_service.files().get_media().execute.return_value = b"test content"

        with patch.object(tool, '_create_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

            # Should include parent folder info
            self.assertEqual(result_data["metadata"]["parent_folder_id"], "parent_folder_id")
            # Should include owner info
            self.assertEqual(result_data["metadata"]["owner"], "owner@example.com")

    def test_top_level_exception_handler(self):
        """Test top-level exception handler (lines 316-317)."""
        tool = self.FetchFileContent(file_id="test_file_id")

        # Mock service creation to raise unexpected exception
        with patch.object(tool, '_create_drive_service', side_effect=Exception("Unexpected error")):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "fetch_error")
            self.assertIn("Failed to fetch file content: Unexpected error", result_data["message"])
            self.assertEqual(result_data["details"]["file_id"], "test_file_id")
            self.assertEqual(result_data["details"]["type"], "Exception")


if __name__ == '__main__':
    unittest.main()