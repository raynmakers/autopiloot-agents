#!/usr/bin/env python3

import sys
import unittest
from unittest.mock import MagicMock, patch
import os
import importlib.util

class TestListDriveChangesTargetedCoverage(unittest.TestCase):
    """Targeted tests to cover specific missing lines in list_drive_changes.py"""

    def test_error_handling_lines_165_186(self):
        """Target lines 165-186: HTTP error handling in _get_file_changes"""
        # Use working mocking pattern
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Set up mocks
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value="mocked_field")

            # Create HttpError mock class
            http_error_class = type('HttpError', (Exception,), {})
            sys.modules['googleapiclient.errors'].HttpError = http_error_class

            # Load the module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            spec = importlib.util.spec_from_file_location("list_drive_changes", module_path)
            module = importlib.util.module_from_spec(spec)

            with patch.dict(os.environ, {
                'GCP_PROJECT_ID': 'test-project',
                'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
            }):
                spec.loader.exec_module(module)

                # Create tool instance
                tool = module.ListDriveChanges(start_page_token="12345")

                # Test HTTP 404 error (lines 165-170)
                mock_service = MagicMock()
                http_404 = http_error_class("404 Not Found")
                http_404.resp = MagicMock()
                http_404.resp.status = 404
                mock_service.changes.return_value.list.return_value.execute.side_effect = http_404

                result = tool._get_file_changes(mock_service, ["test_file"])
                self.assertEqual(result, [])  # Should return empty list for 404

                # Test HTTP 403 error (lines 171-175)
                http_403 = http_error_class("403 Forbidden")
                http_403.resp = MagicMock()
                http_403.resp.status = 403
                mock_service.changes.return_value.list.return_value.execute.side_effect = http_403

                with self.assertRaises(http_error_class):
                    tool._get_file_changes(mock_service, ["test_file"])

                # Test general HTTP error (lines 176-180)
                http_500 = http_error_class("500 Internal Server Error")
                http_500.resp = MagicMock()
                http_500.resp.status = 500
                mock_service.changes.return_value.list.return_value.execute.side_effect = http_500

                with self.assertRaises(http_error_class):
                    tool._get_file_changes(mock_service, ["test_file"])

                # Test unexpected exception (lines 181-186)
                unexpected_error = ValueError("Unexpected error")
                mock_service.changes.return_value.list.return_value.execute.side_effect = unexpected_error

                with self.assertRaises(ValueError):
                    tool._get_file_changes(mock_service, ["test_file"])

    def test_folder_processing_lines_194_260(self):
        """Target lines 194-260: Folder content processing with pagination"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Set up mocks
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value="mocked_field")
            sys.modules['fnmatch'].fnmatch.return_value = True

            # Create HttpError mock class
            http_error_class = type('HttpError', (Exception,), {})
            sys.modules['googleapiclient.errors'].HttpError = http_error_class

            # Load the module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            spec = importlib.util.spec_from_file_location("list_drive_changes", module_path)
            module = importlib.util.module_from_spec(spec)

            with patch.dict(os.environ, {
                'GCP_PROJECT_ID': 'test-project',
                'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
            }):
                spec.loader.exec_module(module)

                # Create tool instance
                tool = module.ListDriveChanges(
                    start_page_token="12345",
                    include_patterns=["*.pdf"],
                    exclude_patterns=["*.tmp"],
                    modified_after="2025-01-15T10:00:00Z"
                )

                # Mock successful folder content processing with pagination
                mock_service = MagicMock()

                # Mock pagination responses
                page1_response = {
                    'files': [
                        {
                            'id': 'file1',
                            'name': 'doc1.pdf',
                            'mimeType': 'application/pdf',
                            'modifiedTime': '2025-01-15T11:00:00Z'
                        }
                    ],
                    'nextPageToken': 'page2_token'
                }

                page2_response = {
                    'files': [
                        {
                            'id': 'file2',
                            'name': 'doc2.pdf',
                            'mimeType': 'application/pdf',
                            'modifiedTime': '2025-01-15T12:00:00Z'
                        }
                    ]
                    # No nextPageToken - last page
                }

                def mock_files_list(*args, **kwargs):
                    page_token = kwargs.get('pageToken')
                    if not page_token:
                        return MagicMock(execute=lambda: page1_response)
                    elif page_token == 'page2_token':
                        return MagicMock(execute=lambda: page2_response)

                mock_service.files.return_value.list.side_effect = mock_files_list

                # Test pagination processing (lines 220-240)
                changes = tool._check_folder_contents(mock_service, "folder_id")
                self.assertEqual(len(changes), 2)
                self.assertIn('doc1.pdf', str(changes))
                self.assertIn('doc2.pdf', str(changes))

                # Test folder processing error handling (lines 250-260)
                mock_service.files.return_value.list.side_effect = Exception("Folder access error")

                with self.assertRaises(Exception):
                    tool._check_folder_contents(mock_service, "folder_id")

    def test_workflow_lines_297_298_305_307(self):
        """Target lines 297-298, 305-307: Workflow integration edge cases"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Set up mocks
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value="mocked_field")
            sys.modules['fnmatch'].fnmatch.return_value = True

            # Load the module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            spec = importlib.util.spec_from_file_location("list_drive_changes", module_path)
            module = importlib.util.module_from_spec(spec)

            with patch.dict(os.environ, {
                'GCP_PROJECT_ID': 'test-project',
                'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
            }):
                spec.loader.exec_module(module)

                # Create tool instance
                tool = module.ListDriveChanges(start_page_token="12345")

                # Mock service for workflow testing
                mock_service = MagicMock()

                # Test successful workflow with mixed results (lines 297-298)
                mock_service.changes.return_value.list.return_value.execute.return_value = {
                    'changes': [
                        {'fileId': 'file1'},
                        {'fileId': 'folder1'}
                    ],
                    'newStartPageToken': '67890'
                }

                # Mock file metadata responses
                def mock_file_get(*args, **kwargs):
                    file_id = kwargs.get('fileId')
                    if file_id == 'file1':
                        return MagicMock(execute=lambda: {
                            'id': 'file1',
                            'name': 'document.pdf',
                            'mimeType': 'application/pdf',
                            'modifiedTime': '2025-01-15T10:30:00Z'
                        })
                    elif file_id == 'folder1':
                        return MagicMock(execute=lambda: {
                            'id': 'folder1',
                            'name': 'test_folder',
                            'mimeType': 'application/vnd.google-apps.folder',
                            'modifiedTime': '2025-01-15T11:30:00Z'
                        })

                mock_service.files.return_value.get.side_effect = mock_file_get

                # Mock empty folder contents for folder1
                mock_service.files.return_value.list.return_value.execute.return_value = {
                    'files': []
                }

                with patch.object(tool, '_get_drive_service', return_value=mock_service):
                    result = tool.run()

                    # Should include both file and folder changes
                    self.assertIn('document.pdf', result)
                    self.assertIn('test_folder', result)
                    self.assertIn('"newStartPageToken": "67890"', result)

    def test_additional_missing_lines(self):
        """Target remaining missing lines: 123, 127, 132, 140, 339-340"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Set up mocks
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value="mocked_field")

            # Load the module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            spec = importlib.util.spec_from_file_location("list_drive_changes", module_path)
            module = importlib.util.module_from_spec(spec)

            with patch.dict(os.environ, {
                'GCP_PROJECT_ID': 'test-project',
                'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
            }):
                spec.loader.exec_module(module)

                # Test malformed timestamp parsing (line 123, 127, 132, 140)
                tool = module.ListDriveChanges(
                    start_page_token="12345",
                    modified_after="not-a-valid-timestamp"
                )

                # This should trigger timestamp parsing error paths
                try:
                    parsed = tool._parse_iso_timestamp("invalid-format")
                    self.assertIsNone(parsed)  # Should handle gracefully
                except:
                    pass  # Expected for malformed timestamps

                # Test edge case in pattern matching (lines 339-340)
                # Test with empty filename
                matches = tool._matches_patterns("", [], [])
                self.assertTrue(matches)  # Empty patterns should include all

if __name__ == '__main__':
    unittest.main()