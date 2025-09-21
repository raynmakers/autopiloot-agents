#!/usr/bin/env python3

import sys
import unittest
from unittest.mock import MagicMock, patch
import os
import importlib.util

class TestListDriveChangesCoverageBoost(unittest.TestCase):
    """Additional tests to boost coverage for list_drive_changes.py"""

    def test_error_handling_and_folder_processing(self):
        """Test error handling and folder processing in one comprehensive test"""
        # Use the proven mocking pattern from working tests
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
                tool = module.ListDriveChanges(
                    start_page_token="12345",
                    include_patterns=["*.pdf"],
                    exclude_patterns=["*.tmp"]
                )

                # Test 1: HTTP 404 error handling (covers lines 165-170)
                mock_service = MagicMock()
                http_error = Exception("HTTP 404")
                http_error.status_code = 404
                mock_service.changes.return_value.list.return_value.execute.side_effect = http_error

                with patch.object(tool, '_get_drive_service', return_value=mock_service):
                    result = tool.run()
                    self.assertIn('"changes":', result)

                # Test 2: HTTP 403 error handling (covers lines 171-175)
                http_error.status_code = 403
                with patch.object(tool, '_get_drive_service', return_value=mock_service):
                    result = tool.run()
                    self.assertIn('"error":', result)

                # Test 3: General HTTP error handling (covers lines 176-180)
                http_error.status_code = 500
                with patch.object(tool, '_get_drive_service', return_value=mock_service):
                    result = tool.run()
                    self.assertIn('"error":', result)

                # Test 4: Unexpected exception handling (covers lines 181-186)
                mock_service.changes.return_value.list.return_value.execute.side_effect = ValueError("Unexpected")
                with patch.object(tool, '_get_drive_service', return_value=mock_service):
                    result = tool.run()
                    self.assertIn('"error":', result)

    def test_folder_content_processing_comprehensive(self):
        """Test folder content processing with pagination (covers lines 194-260)"""
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
                tool = module.ListDriveChanges(
                    start_page_token="12345",
                    include_patterns=["*.pdf"]
                )

                # Test folder processing with pagination
                mock_service = MagicMock()

                # Mock changes list with folder
                mock_service.changes.return_value.list.return_value.execute.return_value = {
                    'changes': [{'fileId': 'folder_id'}],
                    'newStartPageToken': '67890'
                }

                # Mock folder metadata
                folder_metadata = {
                    'id': 'folder_id',
                    'name': 'test_folder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }

                # Mock paginated folder contents
                page1_response = {
                    'files': [
                        {
                            'id': 'file1',
                            'name': 'doc1.pdf',
                            'mimeType': 'application/pdf',
                            'modifiedTime': '2025-01-15T10:30:00Z'
                        }
                    ],
                    'nextPageToken': 'page2'
                }

                page2_response = {
                    'files': [
                        {
                            'id': 'file2',
                            'name': 'doc2.pdf',
                            'mimeType': 'application/pdf',
                            'modifiedTime': '2025-01-15T11:30:00Z'
                        }
                    ]
                    # No nextPageToken = last page
                }

                # Set up mock responses
                def mock_file_get(*args, **kwargs):
                    return MagicMock(execute=lambda: folder_metadata)

                def mock_files_list(*args, **kwargs):
                    page_token = kwargs.get('pageToken')
                    if not page_token:
                        return MagicMock(execute=lambda: page1_response)
                    elif page_token == 'page2':
                        return MagicMock(execute=lambda: page2_response)

                mock_service.files.return_value.get.side_effect = mock_file_get
                mock_service.files.return_value.list.side_effect = mock_files_list

                with patch.object(tool, '_get_drive_service', return_value=mock_service):
                    result = tool.run()
                    self.assertIn('"changes":', result)
                    self.assertIn('doc1.pdf', result)
                    self.assertIn('doc2.pdf', result)

    def test_workflow_integration_edge_cases(self):
        """Test workflow integration edge cases (covers lines 297-298, 305-307)"""
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

                # Test with malformed timestamp (edge case)
                tool = module.ListDriveChanges(
                    start_page_token="12345",
                    modified_after="invalid-timestamp"
                )

                result = tool.run()
                self.assertIn('"error":', result)

                # Test successful workflow with complex filtering
                tool2 = module.ListDriveChanges(
                    start_page_token="12345",
                    include_patterns=["*.pdf", "*.doc"],
                    exclude_patterns=["*.tmp", "*backup*"],
                    modified_after="2025-01-15T10:00:00Z"
                )

                mock_service = MagicMock()
                mock_service.changes.return_value.list.return_value.execute.return_value = {
                    'changes': [
                        {'fileId': 'file1'},
                        {'fileId': 'file2'}
                    ],
                    'newStartPageToken': '67890'
                }

                # Mock file metadata with different types
                def mock_file_get(*args, **kwargs):
                    file_id = kwargs.get('fileId')
                    if file_id == 'file1':
                        return MagicMock(execute=lambda: {
                            'id': 'file1',
                            'name': 'document.pdf',
                            'mimeType': 'application/pdf',
                            'modifiedTime': '2025-01-15T11:00:00Z'
                        })
                    elif file_id == 'file2':
                        return MagicMock(execute=lambda: {
                            'id': 'file2',
                            'name': 'backup.tmp',
                            'mimeType': 'text/plain',
                            'modifiedTime': '2025-01-15T12:00:00Z'
                        })

                mock_service.files.return_value.get.side_effect = mock_file_get

                # Configure pattern matching
                def mock_fnmatch(filename, pattern):
                    if pattern == "*.pdf":
                        return filename.endswith('.pdf')
                    elif pattern == "*.doc":
                        return filename.endswith('.doc')
                    elif pattern == "*.tmp":
                        return filename.endswith('.tmp')
                    elif pattern == "*backup*":
                        return 'backup' in filename
                    return False

                sys.modules['fnmatch'].fnmatch.side_effect = mock_fnmatch

                with patch.object(tool2, '_get_drive_service', return_value=mock_service):
                    result = tool2.run()
                    # Should include PDF (matches include, not exclude)
                    self.assertIn('document.pdf', result)
                    # Should exclude backup.tmp (matches exclude)
                    self.assertNotIn('backup.tmp', result)

if __name__ == '__main__':
    unittest.main()