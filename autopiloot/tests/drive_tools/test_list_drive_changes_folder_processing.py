#!/usr/bin/env python3

import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import os
import importlib.util

class TestListDriveChangesFolderProcessing(unittest.TestCase):
    """Test folder content processing and pagination for list_drive_changes.py"""

    @classmethod
    def setUpClass(cls):
        """Set up class with comprehensive module mocking"""
        # Mock all external dependencies
        cls.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }

        # Set up BaseTool mock
        base_tool_mock = MagicMock()
        base_tool_mock.run = MagicMock(return_value='{"result": "success"}')
        cls.mock_modules['agency_swarm.tools'].BaseTool = base_tool_mock

        # Mock Pydantic Field
        field_mock = MagicMock()
        field_mock.return_value = "mocked_field"
        cls.mock_modules['pydantic'].Field = field_mock

        # Mock fnmatch to return True by default
        cls.mock_modules['fnmatch'].fnmatch.return_value = True

        # Load the actual module
        module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
        cls.module = cls._load_module_with_mocks(module_path)

    @classmethod
    def _load_module_with_mocks(cls, module_path):
        """Load module with comprehensive mocking"""
        with patch.dict('sys.modules', cls.mock_modules):
            spec = importlib.util.spec_from_file_location("list_drive_changes", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

    def setUp(self):
        """Set up each test with fresh mocks"""
        with patch.dict('sys.modules', self.mock_modules):
            self.tool = self.module.ListDriveChanges(
                start_page_token="12345",
                include_patterns=["*.pdf"],
                exclude_patterns=["*.tmp"]
            )

            # Mock environment variables
            self.env_patcher = patch.dict(os.environ, {
                'GCP_PROJECT_ID': 'test-project',
                'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
            })
            self.env_patcher.start()

    def tearDown(self):
        """Clean up after each test"""
        self.env_patcher.stop()

    def test_folder_content_processing_with_pagination(self):
        """Test folder content processing with pagination (lines 194-220)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock service with folder in changes
            mock_service = MagicMock()

            # Mock changes list with folder
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.return_value = {
                'changes': [{'fileId': 'folder_id'}],
                'newStartPageToken': '67890'
            }
            mock_service.changes.return_value = mock_changes

            # Mock folder metadata
            mock_files = MagicMock()
            folder_metadata = {
                'id': 'folder_id',
                'name': 'test_folder',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            # Mock folder contents with pagination
            folder_contents_page1 = {
                'files': [
                    {
                        'id': 'file1',
                        'name': 'doc1.pdf',
                        'mimeType': 'application/pdf',
                        'modifiedTime': '2025-01-15T10:30:00Z'
                    },
                    {
                        'id': 'file2',
                        'name': 'doc2.pdf',
                        'mimeType': 'application/pdf',
                        'modifiedTime': '2025-01-15T11:30:00Z'
                    }
                ],
                'nextPageToken': 'page2_token'
            }

            folder_contents_page2 = {
                'files': [
                    {
                        'id': 'file3',
                        'name': 'doc3.pdf',
                        'mimeType': 'application/pdf',
                        'modifiedTime': '2025-01-15T12:30:00Z'
                    }
                ]
                # No nextPageToken = last page
            }

            # Set up mock responses
            def mock_file_get(*args, **kwargs):
                if kwargs.get('fileId') == 'folder_id':
                    return MagicMock(execute=lambda: folder_metadata)
                else:
                    # For individual files
                    file_id = kwargs.get('fileId')
                    if file_id == 'file1':
                        return MagicMock(execute=lambda: folder_contents_page1['files'][0])
                    elif file_id == 'file2':
                        return MagicMock(execute=lambda: folder_contents_page1['files'][1])
                    elif file_id == 'file3':
                        return MagicMock(execute=lambda: folder_contents_page2['files'][0])

            def mock_files_list(*args, **kwargs):
                # Handle pagination
                page_token = kwargs.get('pageToken')
                if not page_token:
                    return MagicMock(execute=lambda: folder_contents_page1)
                elif page_token == 'page2_token':
                    return MagicMock(execute=lambda: folder_contents_page2)

            mock_files.get.side_effect = mock_file_get
            mock_files.list.side_effect = mock_files_list
            mock_service.files.return_value = mock_files

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should process all files from all pages
                self.assertIn('"changes":', result)
                self.assertIn('doc1.pdf', result)
                self.assertIn('doc2.pdf', result)
                self.assertIn('doc3.pdf', result)

    def test_folder_content_processing_error_handling(self):
        """Test error handling in folder content processing (lines 250-260)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock service with folder in changes
            mock_service = MagicMock()

            # Mock changes list with folder
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.return_value = {
                'changes': [{'fileId': 'folder_id'}],
                'newStartPageToken': '67890'
            }
            mock_service.changes.return_value = mock_changes

            # Mock folder metadata
            mock_files = MagicMock()
            mock_files.get.return_value.execute.return_value = {
                'id': 'folder_id',
                'name': 'test_folder',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            # Mock folder contents list that fails
            mock_files.list.return_value.execute.side_effect = Exception("Folder listing failed")
            mock_service.files.return_value = mock_files

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle folder listing errors gracefully
                self.assertIn('"error":', result)
                self.assertIn('folder', result.lower())

    def test_folder_pagination_edge_cases(self):
        """Test edge cases in folder pagination logic (lines 220-240)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock service with folder in changes
            mock_service = MagicMock()

            # Mock changes list with folder
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.return_value = {
                'changes': [{'fileId': 'folder_id'}],
                'newStartPageToken': '67890'
            }
            mock_service.changes.return_value = mock_changes

            # Mock folder metadata
            mock_files = MagicMock()
            mock_files.get.return_value.execute.return_value = {
                'id': 'folder_id',
                'name': 'test_folder',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            # Mock empty folder contents
            mock_files.list.return_value.execute.return_value = {
                'files': []
                # No nextPageToken = empty folder
            }
            mock_service.files.return_value = mock_files

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle empty folders gracefully
                self.assertIn('"changes":', result)
                # Should contain empty changes array
                self.assertIn('[]', result)

    def test_folder_mixed_content_processing(self):
        """Test processing folders with mixed content types (lines 200-240)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock service
            mock_service = MagicMock()

            # Mock changes list with folder
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.return_value = {
                'changes': [{'fileId': 'folder_id'}],
                'newStartPageToken': '67890'
            }
            mock_service.changes.return_value = mock_changes

            # Mock folder metadata
            mock_files = MagicMock()
            mock_files.get.return_value.execute.return_value = {
                'id': 'folder_id',
                'name': 'test_folder',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            # Mock folder contents with mixed types
            folder_contents = {
                'files': [
                    {
                        'id': 'file1',
                        'name': 'document.pdf',
                        'mimeType': 'application/pdf',
                        'modifiedTime': '2025-01-15T10:30:00Z'
                    },
                    {
                        'id': 'file2',
                        'name': 'temp.tmp',
                        'mimeType': 'text/plain',
                        'modifiedTime': '2025-01-15T11:30:00Z'
                    },
                    {
                        'id': 'subfolder',
                        'name': 'subfolder',
                        'mimeType': 'application/vnd.google-apps.folder',
                        'modifiedTime': '2025-01-15T12:30:00Z'
                    }
                ]
            }

            mock_files.list.return_value.execute.return_value = folder_contents
            mock_service.files.return_value = mock_files

            # Configure pattern matching
            def mock_fnmatch(filename, pattern):
                if pattern == "*.pdf":
                    return filename.endswith('.pdf')
                elif pattern == "*.tmp":
                    return filename.endswith('.tmp')
                return False

            self.mock_modules['fnmatch'].fnmatch.side_effect = mock_fnmatch

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should include PDF (matches include pattern)
                self.assertIn('document.pdf', result)
                # Should exclude TMP (matches exclude pattern)
                self.assertNotIn('temp.tmp', result)
                # Should include subfolder (folder type)
                self.assertIn('subfolder', result)

    def test_folder_deep_pagination(self):
        """Test deep pagination with multiple pages (lines 220-250)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock service
            mock_service = MagicMock()

            # Mock changes list with folder
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.return_value = {
                'changes': [{'fileId': 'folder_id'}],
                'newStartPageToken': '67890'
            }
            mock_service.changes.return_value = mock_changes

            # Mock folder metadata
            mock_files = MagicMock()
            mock_files.get.return_value.execute.return_value = {
                'id': 'folder_id',
                'name': 'test_folder',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            # Mock multiple pages of folder contents
            pages = [
                {
                    'files': [{'id': f'file{i}', 'name': f'doc{i}.pdf', 'mimeType': 'application/pdf'}
                             for i in range(1, 3)],
                    'nextPageToken': 'page2'
                },
                {
                    'files': [{'id': f'file{i}', 'name': f'doc{i}.pdf', 'mimeType': 'application/pdf'}
                             for i in range(3, 5)],
                    'nextPageToken': 'page3'
                },
                {
                    'files': [{'id': f'file{i}', 'name': f'doc{i}.pdf', 'mimeType': 'application/pdf'}
                             for i in range(5, 6)]
                    # No nextPageToken = last page
                }
            ]

            def mock_files_list(*args, **kwargs):
                page_token = kwargs.get('pageToken')
                if not page_token:
                    return MagicMock(execute=lambda: pages[0])
                elif page_token == 'page2':
                    return MagicMock(execute=lambda: pages[1])
                elif page_token == 'page3':
                    return MagicMock(execute=lambda: pages[2])

            mock_files.list.side_effect = mock_files_list
            mock_service.files.return_value = mock_files

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should process all files from all pages
                self.assertIn('"changes":', result)
                for i in range(1, 6):
                    self.assertIn(f'doc{i}.pdf', result)

if __name__ == '__main__':
    unittest.main()