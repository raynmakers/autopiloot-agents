"""
Comprehensive tests for ListDriveChanges tool.
Tests all change detection functionality without external dependencies.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os
from datetime import datetime, timezone


class TestListDriveChangesComplete(unittest.TestCase):
    """Comprehensive test suite for ListDriveChanges tool."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        # Mock environment loader
        self.mock_env_patcher = patch('drive_agent.tools.list_drive_changes.get_required_env_var')
        self.mock_env = self.mock_env_patcher.start()
        self.mock_env.return_value = "/fake/path/to/credentials.json"

        # Mock agency_swarm
        self.mock_agency_patcher = patch('drive_agent.tools.list_drive_changes.BaseTool')
        self.mock_base_tool = self.mock_agency_patcher.start()

        # Mock Google Cloud APIs
        self.mock_service_account_patcher = patch('drive_agent.tools.list_drive_changes.service_account')
        self.mock_service_account = self.mock_service_account_patcher.start()

        self.mock_build_patcher = patch('drive_agent.tools.list_drive_changes.build')
        self.mock_build = self.mock_build_patcher.start()

        self.mock_http_error_patcher = patch('drive_agent.tools.list_drive_changes.HttpError')
        self.mock_http_error = self.mock_http_error_patcher.start()

        # Import the tool after mocking
        from drive_agent.tools.list_drive_changes import ListDriveChanges
        self.ListDriveChanges = ListDriveChanges

    def tearDown(self):
        """Clean up mocks."""
        self.mock_env_patcher.stop()
        self.mock_agency_patcher.stop()
        self.mock_service_account_patcher.stop()
        self.mock_build_patcher.stop()
        self.mock_http_error_patcher.stop()

    def _create_mock_drive_service(self, file_metadata=None, list_results=None):
        """Create a mock Google Drive service."""
        mock_service = Mock()

        # Mock files().get() for single file metadata
        if file_metadata is None:
            file_metadata = {
                'id': 'test_file_id',
                'name': 'test_file.txt',
                'mimeType': 'text/plain',
                'size': '100',
                'modifiedTime': '2025-01-15T10:00:00Z',
                'version': '1',
                'webViewLink': 'https://drive.google.com/file/d/test_file_id/view',
                'parents': ['parent_folder_id'],
                'owners': [{'emailAddress': 'owner@example.com'}]
            }

        mock_get = Mock()
        mock_get.execute.return_value = file_metadata
        mock_service.files().get.return_value = mock_get

        # Mock files().list() for folder contents
        if list_results is None:
            list_results = {
                'files': [
                    {
                        'id': 'child_file_1',
                        'name': 'document.pdf',
                        'mimeType': 'application/pdf',
                        'size': '200',
                        'modifiedTime': '2025-01-15T11:00:00Z',
                        'version': '2',
                        'webViewLink': 'https://drive.google.com/file/d/child_file_1/view',
                        'parents': ['test_folder_id'],
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    }
                ],
                'nextPageToken': None
            }

        mock_list = Mock()
        mock_list.execute.return_value = list_results
        mock_service.files().list.return_value = mock_list

        self.mock_build.return_value = mock_service
        return mock_service

    def test_successful_file_changes_detection(self):
        """Test successful detection of file changes."""
        # Create mock service with recent file
        recent_metadata = {
            'id': 'recent_file',
            'name': 'recent_document.pdf',
            'mimeType': 'application/pdf',
            'size': '500',
            'modifiedTime': '2025-01-15T12:00:00Z',
            'version': '3',
            'webViewLink': 'https://drive.google.com/file/d/recent_file/view',
            'parents': ['parent_id'],
            'owners': [{'emailAddress': 'user@example.com'}]
        }
        self._create_mock_drive_service(file_metadata=recent_metadata)

        tool = self.ListDriveChanges(
            file_ids=["recent_file"],
            since_iso="2025-01-01T00:00:00Z"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertIn("changes", result_data)
        self.assertIn("summary", result_data)
        self.assertEqual(result_data["summary"]["total_changes"], 1)
        self.assertEqual(result_data["changes"][0]["file_id"], "recent_file")

    def test_file_not_found_handling(self):
        """Test handling of file not found errors."""
        mock_service = self._create_mock_drive_service()

        # Mock 404 error
        error = Exception("404")
        error.resp = Mock()
        error.resp.status = 404
        mock_service.files().get.return_value.execute.side_effect = error
        self.mock_http_error.side_effect = error

        tool = self.ListDriveChanges(file_ids=["nonexistent_file"])
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertIn("changes", result_data)
        # Should have error record for the file
        self.assertTrue(any(
            change.get("change_type") == "deleted_or_inaccessible"
            for change in result_data["changes"]
        ))

    def test_access_denied_handling(self):
        """Test handling of access denied errors."""
        mock_service = self._create_mock_drive_service()

        # Mock 403 error
        error = Exception("403")
        error.resp = Mock()
        error.resp.status = 403
        mock_service.files().get.return_value.execute.side_effect = error
        self.mock_http_error.side_effect = error

        tool = self.ListDriveChanges(file_ids=["restricted_file"])
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertIn("changes", result_data)
        # Should have access denied record
        self.assertTrue(any(
            change.get("change_type") == "access_denied"
            for change in result_data["changes"]
        ))

    def test_folder_contents_processing(self):
        """Test processing of folder contents."""
        # Mock folder metadata
        folder_metadata = {
            'id': 'test_folder',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock folder contents
        folder_contents = {
            'files': [
                {
                    'id': 'file_in_folder',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '300',
                    'modifiedTime': '2025-01-15T13:00:00Z',
                    'version': '1',
                    'webViewLink': 'https://drive.google.com/file/d/file_in_folder/view',
                    'parents': ['test_folder'],
                    'owners': [{'emailAddress': 'owner@example.com'}]
                }
            ],
            'nextPageToken': None
        }

        self._create_mock_drive_service(
            file_metadata=folder_metadata,
            list_results=folder_contents
        )

        tool = self.ListDriveChanges(
            file_ids=["test_folder"],
            include_folders=True
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertIn("changes", result_data)
        # Should find the file in the folder
        self.assertTrue(any(
            change.get("file_id") == "file_in_folder"
            for change in result_data["changes"]
        ))

    def test_pattern_matching_include_patterns(self):
        """Test file name pattern matching with include patterns."""
        # Mock service to return PDF file
        pdf_metadata = {
            'id': 'pdf_file',
            'name': 'document.pdf',
            'mimeType': 'application/pdf',
            'size': '400',
            'modifiedTime': '2025-01-15T14:00:00Z',
            'version': '1'
        }
        self._create_mock_drive_service(file_metadata=pdf_metadata)

        tool = self.ListDriveChanges(
            file_ids=["pdf_file"],
            include_patterns=["*.pdf", "*.docx"]
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["summary"]["total_changes"], 1)

    def test_pattern_matching_exclude_patterns(self):
        """Test file name pattern matching with exclude patterns."""
        # Mock service to return temp file
        temp_metadata = {
            'id': 'temp_file',
            'name': '~temp_file.tmp',
            'mimeType': 'text/plain',
            'size': '50',
            'modifiedTime': '2025-01-15T15:00:00Z',
            'version': '1'
        }
        self._create_mock_drive_service(file_metadata=temp_metadata)

        tool = self.ListDriveChanges(
            file_ids=["temp_file"],
            exclude_patterns=["~*", "*.tmp"]
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        # File should be excluded due to patterns
        self.assertEqual(result_data["summary"]["total_changes"], 0)

    def test_time_based_filtering(self):
        """Test filtering changes based on modification time."""
        # Mock service to return old file
        old_metadata = {
            'id': 'old_file',
            'name': 'old_document.txt',
            'mimeType': 'text/plain',
            'size': '100',
            'modifiedTime': '2024-12-01T10:00:00Z',  # Before our filter
            'version': '1'
        }
        self._create_mock_drive_service(file_metadata=old_metadata)

        tool = self.ListDriveChanges(
            file_ids=["old_file"],
            since_iso="2025-01-01T00:00:00Z"
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        # Old file should be filtered out
        self.assertEqual(result_data["summary"]["total_changes"], 0)

    def test_iso_timestamp_parsing(self):
        """Test parsing of various ISO timestamp formats."""
        tool = self.ListDriveChanges(file_ids=["test"])

        # Test various formats
        test_cases = [
            "2025-01-01T00:00:00Z",
            "2025-01-01T00:00:00+00:00",
            "2025-01-01T00:00:00.000Z",
            "2025-01-01T00:00:00"
        ]

        for timestamp in test_cases:
            try:
                parsed = tool._parse_iso_timestamp(timestamp)
                self.assertIsInstance(parsed, datetime)
            except ValueError:
                self.fail(f"Failed to parse valid timestamp: {timestamp}")

    def test_invalid_iso_timestamp_handling(self):
        """Test handling of invalid ISO timestamps."""
        tool = self.ListDriveChanges(file_ids=["test"])

        with self.assertRaises(ValueError):
            tool._parse_iso_timestamp("invalid-timestamp")

    def test_pagination_handling(self):
        """Test handling of paginated folder results."""
        folder_metadata = {
            'id': 'large_folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock paginated results
        page1_results = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document1.pdf',
                    'mimeType': 'application/pdf',
                    'size': '100',
                    'modifiedTime': '2025-01-15T10:00:00Z',
                    'version': '1'
                }
            ],
            'nextPageToken': 'page2_token'
        }

        page2_results = {
            'files': [
                {
                    'id': 'file2',
                    'name': 'document2.pdf',
                    'mimeType': 'application/pdf',
                    'size': '200',
                    'modifiedTime': '2025-01-15T11:00:00Z',
                    'version': '1'
                }
            ],
            'nextPageToken': None
        }

        mock_service = self._create_mock_drive_service(file_metadata=folder_metadata)

        # Set up pagination
        mock_service.files().list.return_value.execute.side_effect = [page1_results, page2_results]

        tool = self.ListDriveChanges(
            file_ids=["large_folder"],
            page_size=1
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        # Should find both files across pages
        self.assertEqual(result_data["summary"]["total_changes"], 2)

    def test_folder_inclusion_toggle(self):
        """Test include_folders parameter functionality."""
        folder_metadata = {
            'id': 'test_folder',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder',
            'modifiedTime': '2025-01-15T16:00:00Z'
        }
        self._create_mock_drive_service(file_metadata=folder_metadata)

        # Test with folders included
        tool_with_folders = self.ListDriveChanges(
            file_ids=["test_folder"],
            include_folders=True
        )
        result_with = tool_with_folders.run()
        data_with = json.loads(result_with)

        # Test with folders excluded
        tool_without_folders = self.ListDriveChanges(
            file_ids=["test_folder"],
            include_folders=False
        )
        result_without = tool_without_folders.run()
        data_without = json.loads(result_without)

        # Both should succeed but with different results
        self.assertNotIn("error", data_with)
        self.assertNotIn("error", data_without)

    def test_service_initialization_failure(self):
        """Test handling of Drive service initialization failure."""
        self.mock_service_account.Credentials.from_service_account_file.side_effect = Exception("Auth failed")

        tool = self.ListDriveChanges(file_ids=["test_file"])
        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "changes_listing_error")

    def test_empty_file_list_handling(self):
        """Test handling of empty file ID list."""
        self._create_mock_drive_service()

        tool = self.ListDriveChanges(file_ids=[])
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["summary"]["total_changes"], 0)
        self.assertEqual(result_data["summary"]["processed_files"], 0)

    def test_mixed_file_and_folder_processing(self):
        """Test processing mix of files and folders."""
        # Mock service to handle different types
        def side_effect_get(*args, **kwargs):
            file_id = kwargs.get('fileId', '')
            if file_id == 'file_id':
                return Mock(execute=Mock(return_value={
                    'id': 'file_id',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '100',
                    'modifiedTime': '2025-01-15T10:00:00Z'
                }))
            elif file_id == 'folder_id':
                return Mock(execute=Mock(return_value={
                    'id': 'folder_id',
                    'mimeType': 'application/vnd.google-apps.folder'
                }))

        mock_service = self._create_mock_drive_service()
        mock_service.files().get.side_effect = side_effect_get

        tool = self.ListDriveChanges(
            file_ids=["file_id", "folder_id"],
            include_folders=True
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["summary"]["processed_files"], 2)

    def test_change_record_structure_validation(self):
        """Test that change records have the expected structure."""
        complete_metadata = {
            'id': 'complete_file',
            'name': 'complete_document.pdf',
            'mimeType': 'application/pdf',
            'size': '500',
            'modifiedTime': '2025-01-15T17:00:00Z',
            'version': '3',
            'webViewLink': 'https://drive.google.com/file/d/complete_file/view',
            'parents': ['parent_folder_id'],
            'owners': [{'emailAddress': 'owner@example.com'}]
        }
        self._create_mock_drive_service(file_metadata=complete_metadata)

        tool = self.ListDriveChanges(file_ids=["complete_file"])
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(len(result_data["changes"]), 1)

        change = result_data["changes"][0]
        required_fields = [
            "file_id", "name", "mimeType", "size", "modifiedTime",
            "version", "webViewLink", "type", "change_type"
        ]

        for field in required_fields:
            self.assertIn(field, change, f"Missing required field: {field}")

    def test_error_counting_and_reporting(self):
        """Test error counting in summary."""
        mock_service = self._create_mock_drive_service()

        # Mock error for first file
        error = Exception("500")
        error.resp = Mock()
        error.resp.status = 500
        mock_service.files().get.return_value.execute.side_effect = error
        self.mock_http_error.side_effect = error

        tool = self.ListDriveChanges(file_ids=["error_file1", "error_file2"])
        result = tool.run()
        result_data = json.loads(result)

        self.assertNotIn("error", result_data)
        self.assertEqual(result_data["summary"]["processed_files"], 2)
        self.assertGreater(result_data["summary"]["errors"], 0)


if __name__ == '__main__':
    unittest.main()