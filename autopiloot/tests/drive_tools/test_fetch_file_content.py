"""
Test suite for FetchFileContent tool.
Tests multi-format file fetching with Google Workspace export support and size limits.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock environment and dependencies before importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.errors': MagicMock(),
}):
    from unittest.mock import MagicMock
    mock_base_tool = MagicMock()
    mock_field = MagicMock()

    with patch('drive_agent.tools.fetch_file_content.BaseTool', mock_base_tool):
        with patch('drive_agent.tools.fetch_file_content.Field', mock_field):
            from drive_agent.tools.fetch_file_content import FetchFileContent


class TestFetchFileContent(unittest.TestCase):
    """Test cases for FetchFileContent tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_drive_service = MagicMock()

        # Sample file metadata
        self.sample_file_metadata = {
            'id': 'file_001',
            'name': 'document.pdf',
            'mimeType': 'application/pdf',
            'size': '1024',
            'modifiedTime': '2025-01-15T10:30:00Z',
            'createdTime': '2025-01-14T09:00:00Z',
            'owners': [{'displayName': 'John Doe', 'emailAddress': 'john@example.com'}],
            'parents': ['folder_123'],
            'webViewLink': 'https://drive.google.com/file/d/file_001/view'
        }

        self.sample_file_content = b"Sample PDF content here..."

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_successful_file_fetch(self, mock_build, mock_load_env):
        """Test successful file content fetching."""
        mock_build.return_value = self.mock_drive_service

        # Mock file metadata and content
        get_request = MagicMock()
        get_request.execute.return_value = self.sample_file_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        get_media_request = MagicMock()
        get_media_request.execute.return_value = self.sample_file_content
        self.mock_drive_service.files.return_value.get_media.return_value = get_media_request

        tool = FetchFileContent(file_id="file_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["file_id"], "file_001")
        self.assertEqual(result["name"], "document.pdf")
        self.assertEqual(result["mime_type"], "application/pdf")
        self.assertEqual(result["size"], 1024)
        self.assertIn("content", result)
        self.assertIn("metadata", result)

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_google_workspace_export(self, mock_build, mock_load_env):
        """Test Google Workspace document export."""
        mock_build.return_value = self.mock_drive_service

        # Google Docs file metadata
        gdoc_metadata = {
            'id': 'gdoc_001',
            'name': 'Google Document',
            'mimeType': 'application/vnd.google-apps.document',
            'modifiedTime': '2025-01-15T10:30:00Z',
            'parents': ['folder_123']
        }

        exported_content = b"Exported DOCX content"

        get_request = MagicMock()
        get_request.execute.return_value = gdoc_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        export_request = MagicMock()
        export_request.execute.return_value = exported_content
        self.mock_drive_service.files.return_value.export.return_value = export_request

        tool = FetchFileContent(file_id="gdoc_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["file_id"], "gdoc_001")
        self.assertEqual(result["export_format"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertIn("content", result)

        # Verify export was called with correct format
        export_call = self.mock_drive_service.files.return_value.export.call_args
        self.assertEqual(export_call[1]["mimeType"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_google_sheets_export(self, mock_build, mock_load_env):
        """Test Google Sheets export to CSV."""
        mock_build.return_value = self.mock_drive_service

        # Google Sheets file metadata
        gsheet_metadata = {
            'id': 'gsheet_001',
            'name': 'Google Spreadsheet',
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'modifiedTime': '2025-01-15T10:30:00Z',
            'parents': ['folder_123']
        }

        csv_content = b"Name,Age,City\nJohn,30,NYC\nJane,25,LA"

        get_request = MagicMock()
        get_request.execute.return_value = gsheet_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        export_request = MagicMock()
        export_request.execute.return_value = csv_content
        self.mock_drive_service.files.return_value.export.return_value = export_request

        tool = FetchFileContent(file_id="gsheet_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["export_format"], "text/csv")

        # Verify export was called with CSV format
        export_call = self.mock_drive_service.files.return_value.export.call_args
        self.assertEqual(export_call[1]["mimeType"], "text/csv")

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_file_size_limit_enforcement(self, mock_build, mock_load_env):
        """Test enforcement of file size limits."""
        mock_build.return_value = self.mock_drive_service

        # Large file metadata
        large_file_metadata = {
            'id': 'large_001',
            'name': 'large_file.pdf',
            'mimeType': 'application/pdf',
            'size': str(50 * 1024 * 1024),  # 50MB
            'modifiedTime': '2025-01-15T10:30:00Z',
            'parents': ['folder_123']
        }

        get_request = MagicMock()
        get_request.execute.return_value = large_file_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        tool = FetchFileContent(
            file_id="large_001",
            max_file_size_mb=25  # 25MB limit
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "file_too_large")
        self.assertIn("50.0 MB exceeds limit of 25 MB", result["message"])

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_file_not_found(self, mock_build, mock_load_env):
        """Test handling of file not found errors."""
        mock_build.return_value = self.mock_drive_service

        from googleapiclient.errors import HttpError
        mock_error = HttpError(
            resp=MagicMock(status=404),
            content=b'{"error": {"code": 404, "message": "File not found"}}'
        )

        get_request = MagicMock()
        get_request.execute.side_effect = mock_error
        self.mock_drive_service.files.return_value.get.return_value = get_request

        with patch('drive_agent.tools.fetch_file_content.HttpError', HttpError):
            tool = FetchFileContent(file_id="nonexistent_001")
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "file_not_found")
        self.assertIn("File not found", result["message"])

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_permission_denied(self, mock_build, mock_load_env):
        """Test handling of permission denied errors."""
        mock_build.return_value = self.mock_drive_service

        from googleapiclient.errors import HttpError
        mock_error = HttpError(
            resp=MagicMock(status=403),
            content=b'{"error": {"code": 403, "message": "Permission denied"}}'
        )

        get_request = MagicMock()
        get_request.execute.side_effect = mock_error
        self.mock_drive_service.files.return_value.get.return_value = get_request

        with patch('drive_agent.tools.fetch_file_content.HttpError', HttpError):
            tool = FetchFileContent(file_id="restricted_001")
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "permission_denied")
        self.assertIn("Permission denied", result["message"])

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_unsupported_google_workspace_type(self, mock_build, mock_load_env):
        """Test handling of unsupported Google Workspace types."""
        mock_build.return_value = self.mock_drive_service

        # Google Forms (unsupported for export)
        gform_metadata = {
            'id': 'gform_001',
            'name': 'Google Form',
            'mimeType': 'application/vnd.google-apps.form',
            'modifiedTime': '2025-01-15T10:30:00Z',
            'parents': ['folder_123']
        }

        get_request = MagicMock()
        get_request.execute.return_value = gform_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        tool = FetchFileContent(file_id="gform_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "unsupported_google_workspace_type")
        self.assertIn("Google Forms", result["message"])

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_content_download_error(self, mock_build, mock_load_env):
        """Test handling of content download errors."""
        mock_build.return_value = self.mock_drive_service

        get_request = MagicMock()
        get_request.execute.return_value = self.sample_file_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        get_media_request = MagicMock()
        get_media_request.execute.side_effect = Exception("Download failed")
        self.mock_drive_service.files.return_value.get_media.return_value = get_media_request

        tool = FetchFileContent(file_id="file_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "content_fetch_failed")
        self.assertIn("Download failed", result["message"])

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_metadata_extraction(self, mock_build, mock_load_env):
        """Test comprehensive metadata extraction."""
        mock_build.return_value = self.mock_drive_service

        get_request = MagicMock()
        get_request.execute.return_value = self.sample_file_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        get_media_request = MagicMock()
        get_media_request.execute.return_value = self.sample_file_content
        self.mock_drive_service.files.return_value.get_media.return_value = get_media_request

        tool = FetchFileContent(file_id="file_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")

        metadata = result["metadata"]
        self.assertEqual(metadata["file_id"], "file_001")
        self.assertEqual(metadata["name"], "document.pdf")
        self.assertEqual(metadata["mime_type"], "application/pdf")
        self.assertEqual(metadata["size"], 1024)
        self.assertIn("modified_time", metadata)
        self.assertIn("created_time", metadata)
        self.assertIn("owners", metadata)
        self.assertIn("parents", metadata)
        self.assertIn("web_view_link", metadata)

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    def test_authentication_error(self, mock_load_env):
        """Test handling of authentication errors."""
        with patch('drive_agent.tools.fetch_file_content.build') as mock_build:
            mock_build.side_effect = Exception("Authentication failed")

            tool = FetchFileContent(file_id="file_001")
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "authentication_failed")
        self.assertIn("Authentication failed", result["message"])

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_content_encoding_handling(self, mock_build, mock_load_env):
        """Test handling of different content encodings."""
        mock_build.return_value = self.mock_drive_service

        # Text file with UTF-8 content
        text_metadata = {
            'id': 'text_001',
            'name': 'unicode.txt',
            'mimeType': 'text/plain',
            'size': '100',
            'modifiedTime': '2025-01-15T10:30:00Z',
            'parents': ['folder_123']
        }

        utf8_content = "Hello 世界! Café résumé".encode('utf-8')

        get_request = MagicMock()
        get_request.execute.return_value = text_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        get_media_request = MagicMock()
        get_media_request.execute.return_value = utf8_content
        self.mock_drive_service.files.return_value.get_media.return_value = get_media_request

        tool = FetchFileContent(file_id="text_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertIn("content", result)

    @patch('drive_agent.tools.fetch_file_content.load_environment')
    @patch('drive_agent.tools.fetch_file_content.build')
    def test_empty_file_handling(self, mock_build, mock_load_env):
        """Test handling of empty files."""
        mock_build.return_value = self.mock_drive_service

        empty_metadata = {
            'id': 'empty_001',
            'name': 'empty.txt',
            'mimeType': 'text/plain',
            'size': '0',
            'modifiedTime': '2025-01-15T10:30:00Z',
            'parents': ['folder_123']
        }

        get_request = MagicMock()
        get_request.execute.return_value = empty_metadata
        self.mock_drive_service.files.return_value.get.return_value = get_request

        get_media_request = MagicMock()
        get_media_request.execute.return_value = b""
        self.mock_drive_service.files.return_value.get_media.return_value = get_media_request

        tool = FetchFileContent(file_id="empty_001")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["size"], 0)
        self.assertEqual(len(result["content"]), 0)


if __name__ == '__main__':
    unittest.main()