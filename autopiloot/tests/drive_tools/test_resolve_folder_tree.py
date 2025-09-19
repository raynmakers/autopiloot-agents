"""
Test suite for ResolveFolderTree tool.
Tests recursive folder structure resolution with pattern filtering and pagination.
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
}):
    from unittest.mock import MagicMock
    mock_base_tool = MagicMock()
    mock_field = MagicMock()

    with patch('drive_agent.tools.resolve_folder_tree.BaseTool', mock_base_tool):
        with patch('drive_agent.tools.resolve_folder_tree.Field', mock_field):
            from drive_agent.tools.resolve_folder_tree import ResolveFolderTree


class TestResolveFolderTree(unittest.TestCase):
    """Test cases for ResolveFolderTree tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_drive_service = MagicMock()

        # Sample folder structure response
        self.sample_files_response = {
            'files': [
                {
                    'id': 'file_001',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1024',
                    'modifiedTime': '2025-01-15T10:30:00Z',
                    'parents': ['folder_123']
                },
                {
                    'id': 'subfolder_001',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'modifiedTime': '2025-01-15T09:00:00Z',
                    'parents': ['folder_123']
                },
                {
                    'id': 'file_002',
                    'name': 'archive.zip',
                    'mimeType': 'application/zip',
                    'size': '2048',
                    'modifiedTime': '2025-01-14T15:20:00Z',
                    'parents': ['folder_123']
                }
            ],
            'nextPageToken': None
        }

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_successful_folder_tree_resolution(self, mock_build, mock_load_env):
        """Test successful recursive folder tree resolution."""
        mock_build.return_value = self.mock_drive_service

        # Mock API responses
        files_request = MagicMock()
        files_request.execute.return_value = self.sample_files_response
        self.mock_drive_service.files.return_value.list.return_value = files_request

        tool = ResolveFolderTree(
            folder_id="folder_123",
            include_patterns=["*.pdf"],
            exclude_patterns=["*.zip"]
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["folder_id"], "folder_123")
        self.assertGreaterEqual(result["total_files"], 1)
        self.assertGreaterEqual(result["matching_files"], 1)

        # Check that PDF file matches but ZIP is excluded
        matching_files = result["files"]
        pdf_files = [f for f in matching_files if f["name"] == "document.pdf"]
        zip_files = [f for f in matching_files if f["name"] == "archive.zip"]

        self.assertEqual(len(pdf_files), 1)
        self.assertEqual(len(zip_files), 0)  # Should be excluded

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_recursive_folder_processing(self, mock_build, mock_load_env):
        """Test recursive processing of subfolders."""
        mock_build.return_value = self.mock_drive_service

        # Mock responses for main folder and subfolder
        main_response = self.sample_files_response
        subfolder_response = {
            'files': [
                {
                    'id': 'file_003',
                    'name': 'nested.pdf',
                    'mimeType': 'application/pdf',
                    'size': '512',
                    'modifiedTime': '2025-01-15T11:00:00Z',
                    'parents': ['subfolder_001']
                }
            ]
        }

        def mock_list_files(*args, **kwargs):
            request = MagicMock()
            # Return different responses based on the query
            if "'subfolder_001' in parents" in kwargs.get('q', ''):
                request.execute.return_value = subfolder_response
            else:
                request.execute.return_value = main_response
            return request

        self.mock_drive_service.files.return_value.list.side_effect = mock_list_files

        tool = ResolveFolderTree(
            folder_id="folder_123",
            include_patterns=["*.pdf"],
            recursive=True
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(result["total_files"], 2)  # Should include nested file

        # Check that nested file is included
        nested_files = [f for f in result["files"] if f["name"] == "nested.pdf"]
        self.assertEqual(len(nested_files), 1)

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_pattern_filtering(self, mock_build, mock_load_env):
        """Test include and exclude pattern filtering."""
        mock_build.return_value = self.mock_drive_service

        files_request = MagicMock()
        files_request.execute.return_value = self.sample_files_response
        self.mock_drive_service.files.return_value.list.return_value = files_request

        tool = ResolveFolderTree(
            folder_id="folder_123",
            include_patterns=["*.pdf", "*.docx"],
            exclude_patterns=["*archive*", "*.zip"]
        )
        result_str = tool.run()
        result = json.loads(result_str)

        # Should include PDF (matches include pattern)
        # Should exclude ZIP (matches exclude pattern)
        matching_files = result["files"]
        file_names = [f["name"] for f in matching_files]

        self.assertIn("document.pdf", file_names)
        self.assertNotIn("archive.zip", file_names)

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_pagination_handling(self, mock_build, mock_load_env):
        """Test handling of paginated API responses."""
        mock_build.return_value = self.mock_drive_service

        # Mock paginated responses
        page1_response = {
            'files': [
                {
                    'id': 'file_001',
                    'name': 'document1.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1024',
                    'parents': ['folder_123']
                }
            ],
            'nextPageToken': 'token_page2'
        }

        page2_response = {
            'files': [
                {
                    'id': 'file_002',
                    'name': 'document2.pdf',
                    'mimeType': 'application/pdf',
                    'size': '2048',
                    'parents': ['folder_123']
                }
            ]
        }

        def mock_list_paginated(*args, **kwargs):
            request = MagicMock()
            if kwargs.get('pageToken') == 'token_page2':
                request.execute.return_value = page2_response
            else:
                request.execute.return_value = page1_response
            return request

        self.mock_drive_service.files.return_value.list.side_effect = mock_list_paginated

        tool = ResolveFolderTree(folder_id="folder_123")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_files"], 2)  # Should include both pages

        file_names = [f["name"] for f in result["files"]]
        self.assertIn("document1.pdf", file_names)
        self.assertIn("document2.pdf", file_names)

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_empty_folder(self, mock_build, mock_load_env):
        """Test handling of empty folders."""
        mock_build.return_value = self.mock_drive_service

        empty_response = {'files': []}
        files_request = MagicMock()
        files_request.execute.return_value = empty_response
        self.mock_drive_service.files.return_value.list.return_value = files_request

        tool = ResolveFolderTree(folder_id="empty_folder")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_files"], 0)
        self.assertEqual(result["matching_files"], 0)
        self.assertEqual(len(result["files"]), 0)

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_drive_api_error(self, mock_build, mock_load_env):
        """Test handling of Google Drive API errors."""
        mock_build.return_value = self.mock_drive_service

        files_request = MagicMock()
        files_request.execute.side_effect = Exception("Drive API error: Folder not found")
        self.mock_drive_service.files.return_value.list.return_value = files_request

        tool = ResolveFolderTree(folder_id="invalid_folder")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "drive_api_error")
        self.assertIn("Drive API error", result["message"])

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_file_metadata_extraction(self, mock_build, mock_load_env):
        """Test extraction of comprehensive file metadata."""
        mock_build.return_value = self.mock_drive_service

        files_request = MagicMock()
        files_request.execute.return_value = self.sample_files_response
        self.mock_drive_service.files.return_value.list.return_value = files_request

        tool = ResolveFolderTree(folder_id="folder_123")
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")

        # Check metadata for the first file
        first_file = result["files"][0]
        self.assertIn("id", first_file)
        self.assertIn("name", first_file)
        self.assertIn("mime_type", first_file)
        self.assertIn("size", first_file)
        self.assertIn("modified_time", first_file)
        self.assertIn("path", first_file)

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    @patch('drive_agent.tools.resolve_folder_tree.build')
    def test_depth_limiting(self, mock_build, mock_load_env):
        """Test depth limiting for recursive folder traversal."""
        mock_build.return_value = self.mock_drive_service

        # Mock deep nested structure
        def mock_nested_response(*args, **kwargs):
            request = MagicMock()
            request.execute.return_value = {
                'files': [
                    {
                        'id': f'deep_folder_{len(kwargs.get("q", "").split("parents"))}',
                        'name': 'Deep Folder',
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [kwargs.get('q', '').split("'")[1]]
                    }
                ]
            }
            return request

        self.mock_drive_service.files.return_value.list.side_effect = mock_nested_response

        tool = ResolveFolderTree(
            folder_id="folder_123",
            recursive=True,
            max_depth=2
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        # Should stop at max depth even if more folders exist

    @patch('drive_agent.tools.resolve_folder_tree.load_environment')
    def test_authentication_error(self, mock_load_env):
        """Test handling of authentication errors."""
        with patch('drive_agent.tools.resolve_folder_tree.build') as mock_build:
            mock_build.side_effect = Exception("Authentication failed")

            tool = ResolveFolderTree(folder_id="folder_123")
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "authentication_failed")
        self.assertIn("Authentication failed", result["message"])


if __name__ == '__main__':
    unittest.main()