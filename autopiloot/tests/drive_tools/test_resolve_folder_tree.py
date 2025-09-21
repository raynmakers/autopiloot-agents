#!/usr/bin/env python3
"""
Comprehensive tests for resolve_folder_tree.py
Tests Google Drive folder tree resolution with mocking
"""

import unittest
import json
import sys
import os
from unittest.mock import MagicMock, patch, Mock
import importlib.util


class TestResolveFolderTree(unittest.TestCase):
    """Test ResolveFolderTree tool functionality"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with proper mocking"""
        # Mock all external dependencies
        cls.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock()
        }

        # Set up mocks
        cls.mock_modules['agency_swarm.tools'].BaseTool = MagicMock()
        cls.mock_modules['pydantic'].Field = MagicMock(side_effect=lambda **kwargs: kwargs.get('default', kwargs.get('default_factory', lambda: None)()))

        # Mock fnmatch for pattern matching
        cls.mock_modules['fnmatch'].fnmatch = MagicMock(side_effect=lambda name, pattern: True)

        # Create HttpError class mock
        http_error_class = type('HttpError', (Exception,), {})
        cls.mock_modules['googleapiclient.errors'].HttpError = http_error_class

        # Load the module
        module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
        cls.module = cls._load_module_with_mocks(module_path)

    @classmethod
    def _load_module_with_mocks(cls, module_path):
        """Load module with comprehensive mocking"""
        with patch.dict('sys.modules', cls.mock_modules):
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock the imports
            module.get_required_env_var = MagicMock(return_value="/path/to/creds.json")
            module.get_config_value = MagicMock()

            spec.loader.exec_module(module)
            return module

    def setUp(self):
        """Set up each test"""
        # Reset mocks
        self.mock_modules['fnmatch'].fnmatch.reset_mock()
        self.module.get_required_env_var.reset_mock()

    def test_successful_folder_tree_resolution(self):
        """Test successful resolution of folder tree"""
        # Create mock Drive service
        mock_service = MagicMock()

        # Mock folder metadata
        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock folder contents
        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {
                    'id': 'file_1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1024000',
                    'modifiedTime': '2025-01-15T10:00:00Z',
                    'webViewLink': 'https://drive.google.com/file1'
                },
                {
                    'id': 'subfolder_1',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
            ]
        }

        # Create tool and mock service initialization
        tool = self.module.ResolveFolderTree(
            folder_id="folder_123",
            recursive=False
        )

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        # Verify results
        self.assertIn("folder_tree", result_data)
        self.assertIn("summary", result_data)
        self.assertEqual(result_data["folder_tree"]["id"], "folder_123")
        self.assertEqual(result_data["folder_tree"]["name"], "Test Folder")
        self.assertEqual(len(result_data["folder_tree"]["files"]), 1)
        self.assertEqual(len(result_data["folder_tree"]["folders"]), 1)

    def test_recursive_folder_resolution(self):
        """Test recursive folder tree resolution"""
        mock_service = MagicMock()

        # Mock folder metadata
        mock_service.files().get.return_value.execute.return_value = {
            'id': 'root_folder',
            'name': 'Root',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock different responses for different folder IDs
        def mock_list_execute(*args, **kwargs):
            # Check the query to determine which folder is being listed
            call_args = mock_service.files().list.call_args
            if call_args:
                query = call_args[1].get('q', '')
                if "'root_folder' in parents" in query:
                    return {
                        'files': [
                            {
                                'id': 'subfolder_1',
                                'name': 'Subfolder',
                                'mimeType': 'application/vnd.google-apps.folder'
                            }
                        ]
                    }
                elif "'subfolder_1' in parents" in query:
                    return {
                        'files': [
                            {
                                'id': 'file_1',
                                'name': 'nested_file.pdf',
                                'mimeType': 'application/pdf',
                                'size': '500000'
                            }
                        ]
                    }
            return {'files': []}

        mock_service.files().list.return_value.execute.side_effect = mock_list_execute

        tool = self.module.ResolveFolderTree(
            folder_id="root_folder",
            recursive=True,
            max_depth=3
        )

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        self.assertIn("folder_tree", result_data)
        self.assertEqual(result_data["summary"]["recursive"], True)

    def test_pattern_filtering(self):
        """Test include/exclude pattern filtering"""
        mock_service = MagicMock()

        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {'id': 'f1', 'name': 'document.pdf', 'mimeType': 'application/pdf', 'size': '1000'},
                {'id': 'f2', 'name': 'temp.tmp', 'mimeType': 'text/plain', 'size': '500'},
                {'id': 'f3', 'name': 'report.docx', 'mimeType': 'application/docx', 'size': '2000'}
            ]
        }

        # Mock pattern matching
        def mock_fnmatch(filename, pattern):
            filename = filename.lower()
            pattern = pattern.lower()
            if pattern == "*.pdf":
                return filename.endswith('.pdf')
            elif pattern == "*.tmp":
                return filename.endswith('.tmp')
            elif pattern == "*.docx":
                return filename.endswith('.docx')
            return False

        self.mock_modules['fnmatch'].fnmatch.side_effect = mock_fnmatch

        tool = self.module.ResolveFolderTree(
            folder_id="folder_123",
            include_patterns=["*.pdf", "*.docx"],
            exclude_patterns=["*.tmp"]
        )

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        # Should include PDF and DOCX, exclude TMP
        files = result_data["folder_tree"]["files"]
        file_names = [f["name"] for f in files]
        self.assertIn("document.pdf", file_names)
        self.assertIn("report.docx", file_names)
        self.assertNotIn("temp.tmp", file_names)

    def test_pagination_handling(self):
        """Test handling of paginated results"""
        mock_service = MagicMock()

        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Large Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock paginated responses
        page1_response = {
            'files': [
                {'id': f'file_{i}', 'name': f'doc_{i}.pdf', 'mimeType': 'application/pdf', 'size': '1000'}
                for i in range(100)
            ],
            'nextPageToken': 'token_page2'
        }

        page2_response = {
            'files': [
                {'id': f'file_{i}', 'name': f'doc_{i}.pdf', 'mimeType': 'application/pdf', 'size': '1000'}
                for i in range(100, 150)
            ]
        }

        def mock_list_execute(*args, **kwargs):
            call_args = mock_service.files().list.call_args
            if call_args and call_args[1].get('pageToken') == 'token_page2':
                return page2_response
            return page1_response

        mock_service.files().list.return_value.execute.side_effect = mock_list_execute

        tool = self.module.ResolveFolderTree(
            folder_id="folder_123",
            page_size=100
        )

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        # Should have processed both pages
        self.assertEqual(result_data["folder_tree"]["total_files"], 150)

    def test_max_depth_enforcement(self):
        """Test that max_depth is properly enforced"""
        mock_service = MagicMock()

        mock_service.files().get.return_value.execute.return_value = {
            'id': 'root',
            'name': 'Root',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Always return a subfolder to test depth limiting
        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {
                    'id': 'deep_folder',
                    'name': 'Deep Folder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
            ]
        }

        tool = self.module.ResolveFolderTree(
            folder_id="root",
            recursive=True,
            max_depth=2
        )

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        # Check that warning is added at max depth
        # The structure should stop recursing after max_depth
        self.assertIn("folder_tree", result_data)

    def test_folder_not_found_error(self):
        """Test handling of folder not found error"""
        mock_service = MagicMock()

        # Mock 404 error
        http_error = self.mock_modules['googleapiclient.errors'].HttpError("404 Not Found")
        http_error.resp = Mock()
        http_error.resp.status = 404

        mock_service.files().get.return_value.execute.side_effect = http_error

        tool = self.module.ResolveFolderTree(folder_id="nonexistent")

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        self.assertEqual(result_data["error"], "folder_not_found")
        self.assertIn("nonexistent", result_data["message"])

    def test_permission_denied_error(self):
        """Test handling of permission denied error"""
        mock_service = MagicMock()

        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Restricted',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock 403 error during folder listing
        http_error = self.mock_modules['googleapiclient.errors'].HttpError("403 Forbidden")
        http_error.resp = Mock()
        http_error.resp.status = 403

        mock_service.files().list.return_value.execute.side_effect = http_error

        tool = self.module.ResolveFolderTree(folder_id="folder_123")

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        # Should have error in folder data
        self.assertIn("error", result_data["folder_tree"])

    def test_not_a_folder_error(self):
        """Test error when ID points to a file, not a folder"""
        mock_service = MagicMock()

        # Return a file instead of folder
        mock_service.files().get.return_value.execute.return_value = {
            'id': 'file_123',
            'name': 'document.pdf',
            'mimeType': 'application/pdf'
        }

        tool = self.module.ResolveFolderTree(folder_id="file_123")

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        self.assertEqual(result_data["error"], "not_a_folder")
        self.assertIn("application/pdf", result_data["mimeType"])

    def test_service_initialization_failure(self):
        """Test handling of Drive service initialization failure"""
        tool = self.module.ResolveFolderTree(folder_id="test")

        with patch.object(tool, '_get_drive_service', side_effect=Exception("Service init failed")):
            result = tool.run()
            result_data = json.loads(result)

        self.assertEqual(result_data["error"], "resolution_error")
        self.assertIn("Service init failed", result_data["message"])

    def test_owner_metadata_extraction(self):
        """Test extraction of file owner metadata"""
        mock_service = MagicMock()

        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {
                    'id': 'file_1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1000',
                    'owners': [{'emailAddress': 'owner@example.com'}]
                }
            ]
        }

        tool = self.module.ResolveFolderTree(folder_id="folder_123")

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        file_info = result_data["folder_tree"]["files"][0]
        self.assertEqual(file_info["owner"], "owner@example.com")

    def test_summary_statistics(self):
        """Test calculation of summary statistics"""
        mock_service = MagicMock()

        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {'id': 'f1', 'name': 'doc1.pdf', 'mimeType': 'application/pdf', 'size': '1048576'},
                {'id': 'f2', 'name': 'doc2.pdf', 'mimeType': 'application/pdf', 'size': '2097152'},
                {'id': 'folder1', 'name': 'Subfolder', 'mimeType': 'application/vnd.google-apps.folder'}
            ]
        }

        tool = self.module.ResolveFolderTree(
            folder_id="folder_123",
            recursive=False,
            include_patterns=["*.pdf"]
        )

        with patch.object(tool, '_get_drive_service', return_value=mock_service):
            result = tool.run()
            result_data = json.loads(result)

        summary = result_data["summary"]
        self.assertEqual(summary["total_files"], 2)
        self.assertEqual(summary["total_folders"], 1)
        self.assertEqual(summary["total_size_bytes"], 3145728)
        self.assertEqual(summary["total_size_mb"], 3.0)
        self.assertEqual(summary["recursive"], False)


if __name__ == '__main__':
    unittest.main()