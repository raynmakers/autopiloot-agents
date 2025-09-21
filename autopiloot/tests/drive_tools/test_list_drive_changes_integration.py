#!/usr/bin/env python3
"""
Integration tests for ListDriveChanges tool
Tests complete workflow, folder content processing, and pagination
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestListDriveChangesIntegration(unittest.TestCase):
    """Integration tests for ListDriveChanges tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'list_drive_changes' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_successful_file_changes_listing(self):
        """Test successful listing of file changes."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment and Google services
            sys.modules['env_loader'].get_required_env_var.return_value = "/path/to/credentials.json"
            mock_credentials = MagicMock()
            mock_service = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials
            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            # Mock fnmatch to always match
            sys.modules['fnmatch'].fnmatch = lambda name, pattern: True

            # Mock file metadata responses
            mock_file_metadata = {
                'id': 'test_file_id',
                'name': 'test_document.pdf',
                'mimeType': 'application/pdf',
                'size': '1024000',
                'modifiedTime': '2025-01-15T10:30:00Z',
                'version': '123',
                'webViewLink': 'https://drive.google.com/file/d/test_file_id/view',
                'owners': [{'emailAddress': 'owner@example.com'}],
                'parents': ['parent_folder_id']
            }

            # Mock API calls
            mock_service.files().get().execute.return_value = mock_file_metadata

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create and run tool
            tool = ListDriveChanges(
                file_ids=["test_file_id"],
                since_iso="2025-01-01T00:00:00Z",
                include_patterns=["*.pdf"],
                include_folders=False
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify result structure
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)

            # Verify summary
            summary = result_data['summary']
            self.assertEqual(summary['total_changes'], 1)
            self.assertEqual(summary['processed_files'], 1)
            self.assertEqual(summary['errors'], 0)
            self.assertEqual(summary['since_timestamp'], "2025-01-01T00:00:00Z")
            self.assertEqual(summary['patterns_applied']['include'], ["*.pdf"])
            self.assertFalse(summary['include_folders'])

            # Verify change record
            changes = result_data['changes']
            self.assertEqual(len(changes), 1)
            change = changes[0]
            self.assertEqual(change['file_id'], 'test_file_id')
            self.assertEqual(change['name'], 'test_document.pdf')
            self.assertEqual(change['type'], 'file')
            self.assertEqual(change['change_type'], 'modified')

    def test_folder_content_processing(self):
        """Test folder content processing with pagination."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment and Google services
            sys.modules['env_loader'].get_required_env_var.return_value = "/path/to/credentials.json"
            mock_credentials = MagicMock()
            mock_service = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials
            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            # Mock fnmatch to always match
            sys.modules['fnmatch'].fnmatch = lambda name, pattern: True

            # Mock folder metadata for file type check
            mock_folder_metadata = {
                'id': 'test_folder_id',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            # Mock folder contents (two pages)
            mock_page1_response = {
                'nextPageToken': 'page2_token',
                'files': [
                    {
                        'id': 'file1_id',
                        'name': 'document1.pdf',
                        'mimeType': 'application/pdf',
                        'size': '1024',
                        'modifiedTime': '2025-01-15T10:30:00Z',
                        'version': '123',
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    },
                    {
                        'id': 'file2_id',
                        'name': 'document2.pdf',
                        'mimeType': 'application/pdf',
                        'size': '2048',
                        'modifiedTime': '2025-01-15T11:00:00Z',
                        'version': '124',
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    }
                ]
            }

            mock_page2_response = {
                'files': [
                    {
                        'id': 'file3_id',
                        'name': 'document3.pdf',
                        'mimeType': 'application/pdf',
                        'size': '3072',
                        'modifiedTime': '2025-01-15T11:30:00Z',
                        'version': '125',
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    }
                ]
            }

            # Setup mock call sequence
            def mock_get_execute(*args, **kwargs):
                return mock_folder_metadata

            def mock_list_execute(*args, **kwargs):
                # Check if this is the first page or second page based on pageToken
                if 'pageToken' not in kwargs or kwargs.get('pageToken') is None:
                    return mock_page1_response
                else:
                    return mock_page2_response

            mock_service.files().get.return_value.execute = mock_get_execute
            mock_service.files().list.return_value.execute = mock_list_execute

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create and run tool
            tool = ListDriveChanges(
                file_ids=["test_folder_id"],
                page_size=2,
                include_folders=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify result structure
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)

            # Verify we got all files from both pages
            changes = result_data['changes']
            self.assertEqual(len(changes), 3)  # 3 files from 2 pages

            # Verify summary
            summary = result_data['summary']
            self.assertEqual(summary['total_changes'], 3)
            self.assertEqual(summary['processed_files'], 1)  # 1 folder processed
            self.assertEqual(summary['errors'], 0)

    def test_mixed_file_and_folder_processing(self):
        """Test processing both files and folders."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment and Google services
            sys.modules['env_loader'].get_required_env_var.return_value = "/path/to/credentials.json"
            mock_credentials = MagicMock()
            mock_service = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials
            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            # Mock fnmatch to always match
            sys.modules['fnmatch'].fnmatch = lambda name, pattern: True

            # Mock responses for different file types
            def mock_get_execute(*args, **kwargs):
                call_args = args[0] if args else kwargs
                file_id = call_args.get('fileId', '')

                if file_id == 'test_file_id':
                    return {
                        'id': 'test_file_id',
                        'name': 'test_document.pdf',
                        'mimeType': 'application/pdf',
                        'size': '1024000',
                        'modifiedTime': '2025-01-15T10:30:00Z',
                        'version': '123',
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    }
                elif file_id == 'test_folder_id':
                    return {
                        'id': 'test_folder_id',
                        'mimeType': 'application/vnd.google-apps.folder'
                    }

            def mock_list_execute(*args, **kwargs):
                return {
                    'files': [
                        {
                            'id': 'folder_file_id',
                            'name': 'folder_document.pdf',
                            'mimeType': 'application/pdf',
                            'size': '2048',
                            'modifiedTime': '2025-01-15T11:00:00Z',
                            'version': '124',
                            'owners': [{'emailAddress': 'owner@example.com'}]
                        }
                    ]
                }

            mock_service.files().get.return_value.execute = mock_get_execute
            mock_service.files().list.return_value.execute = mock_list_execute

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create and run tool
            tool = ListDriveChanges(
                file_ids=["test_file_id", "test_folder_id"],
                include_folders=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify result structure
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)

            # Should have changes from both file and folder
            changes = result_data['changes']
            self.assertEqual(len(changes), 2)  # 1 file + 1 file from folder

            # Verify summary
            summary = result_data['summary']
            self.assertEqual(summary['total_changes'], 2)
            self.assertEqual(summary['processed_files'], 2)  # 1 file + 1 folder processed
            self.assertEqual(summary['errors'], 0)

    def test_error_handling_in_processing(self):
        """Test error handling during file processing."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock HttpError
            class MockHttpError(Exception):
                def __init__(self, status):
                    self.resp = MagicMock()
                    self.resp.status = status

            sys.modules['googleapiclient.errors'].HttpError = MockHttpError

            # Mock environment and Google services
            sys.modules['env_loader'].get_required_env_var.return_value = "/path/to/credentials.json"
            mock_credentials = MagicMock()
            mock_service = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials
            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            # Mock API to raise error for file type check
            mock_service.files().get().execute.side_effect = MockHttpError(404)

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create and run tool
            tool = ListDriveChanges(file_ids=["nonexistent_file_id"])

            result = tool.run()
            result_data = json.loads(result)

            # Verify error handling
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)

            # Should have error record
            changes = result_data['changes']
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0]['change_type'], 'error')
            self.assertEqual(changes[0]['file_id'], 'nonexistent_file_id')

            # Verify summary reflects error
            summary = result_data['summary']
            self.assertEqual(summary['errors'], 1)

    def test_general_exception_handling(self):
        """Test general exception handling in run method."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment variable failure
            sys.modules['env_loader'].get_required_env_var.side_effect = Exception("Environment error")

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create and run tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            result = tool.run()
            result_data = json.loads(result)

            # Verify error response
            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'changes_listing_error')
            self.assertIn('Failed to list Drive changes', result_data['message'])
            self.assertIn('Environment error', result_data['message'])
            self.assertIn('details', result_data)
            self.assertEqual(result_data['details']['file_ids'], ["test_file_id"])

    def test_empty_file_list(self):
        """Test handling of empty file list."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment and Google services
            sys.modules['env_loader'].get_required_env_var.return_value = "/path/to/credentials.json"
            mock_credentials = MagicMock()
            mock_service = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials
            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create and run tool with empty file list
            tool = ListDriveChanges(file_ids=[])

            result = tool.run()
            result_data = json.loads(result)

            # Verify empty result
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)
            self.assertEqual(len(result_data['changes']), 0)
            self.assertEqual(result_data['summary']['total_changes'], 0)
            self.assertEqual(result_data['summary']['processed_files'], 0)
            self.assertEqual(result_data['summary']['errors'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)