#!/usr/bin/env python3
"""
Advanced coverage tests for ListDriveChanges tool
Focus on maximum coverage with working tests
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestListDriveChangesAdvanced(unittest.TestCase):
    """Advanced coverage tests for ListDriveChanges tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'list_drive_changes' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_complete_workflow_successful(self):
        """Test complete workflow with successful file processing."""
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
            sys.modules['fnmatch'].fnmatch.return_value = True

            # Mock file metadata for type checking and file processing
            mock_file_metadata = {
                'id': 'test_file_id',
                'mimeType': 'application/pdf',  # Not a folder
                'name': 'test_document.pdf',
                'size': '1024000',
                'modifiedTime': '2025-01-15T10:30:00Z',
                'version': '123',
                'webViewLink': 'https://drive.google.com/file/d/test_file_id/view',
                'owners': [{'emailAddress': 'owner@example.com'}],
                'parents': ['parent_folder_id']
            }

            # Setup mock call sequence for multiple get() calls
            mock_service.files().get.return_value.execute.return_value = mock_file_metadata

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
                exclude_patterns=[],
                include_folders=False
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify successful result structure
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)

            # Verify summary has expected structure
            summary = result_data['summary']
            self.assertIn('total_changes', summary)
            self.assertIn('processed_files', summary)
            self.assertIn('errors', summary)
            self.assertEqual(summary['processed_files'], 1)

    def test_folder_processing_workflow(self):
        """Test folder processing with content listing."""
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
            sys.modules['fnmatch'].fnmatch.return_value = True

            # Mock folder metadata
            mock_folder_metadata = {
                'id': 'test_folder_id',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            # Mock folder contents
            mock_folder_contents = {
                'files': [
                    {
                        'id': 'file1_id',
                        'name': 'document1.pdf',
                        'mimeType': 'application/pdf',
                        'size': '1024',
                        'modifiedTime': '2025-01-15T10:30:00Z',
                        'version': '123',
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    }
                ]
            }

            # Setup mock call sequence
            mock_service.files().get.return_value.execute.return_value = mock_folder_metadata
            mock_service.files().list.return_value.execute.return_value = mock_folder_contents

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
                include_folders=True,
                page_size=10
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify successful folder processing
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)

            # Verify folder was processed
            summary = result_data['summary']
            self.assertEqual(summary['processed_files'], 1)

    def test_iso_timestamp_parsing_comprehensive(self):
        """Test comprehensive ISO timestamp parsing scenarios."""
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

            # Import and test the timestamp parsing directly
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            tool = ListDriveChanges(file_ids=["test"])

            # Test various timestamp formats
            test_cases = [
                ("2025-01-01T12:00:00Z", True),
                ("2025-01-01T12:00:00+02:00", True),
                ("2025-01-01T12:00:00", True),
                ("invalid-timestamp", False)
            ]

            for timestamp, should_succeed in test_cases:
                if should_succeed:
                    result = tool._parse_iso_timestamp(timestamp)
                    self.assertIsInstance(result, datetime)
                else:
                    with self.assertRaises(ValueError):
                        tool._parse_iso_timestamp(timestamp)

    def test_file_changes_with_patterns_and_filters(self):
        """Test file change detection with patterns and time filters."""
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

            # Mock fnmatch with specific pattern matching
            def mock_fnmatch(name, pattern):
                if pattern == "*.pdf" and name.lower().endswith('.pdf'):
                    return True
                elif pattern == "~*" and name.lower().startswith('~'):
                    return True
                return False

            sys.modules['fnmatch'].fnmatch.side_effect = mock_fnmatch

            # Mock file metadata that should match include but not exclude
            mock_file_metadata = {
                'id': 'test_file_id',
                'mimeType': 'application/pdf',
                'name': 'document.pdf',  # Should match *.pdf pattern
                'size': '1024000',
                'modifiedTime': '2025-01-15T10:30:00Z',  # After since_iso
                'version': '123',
                'owners': [{'emailAddress': 'owner@example.com'}]
            }

            mock_service.files().get.return_value.execute.return_value = mock_file_metadata

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create and run tool with patterns and filters
            tool = ListDriveChanges(
                file_ids=["test_file_id"],
                since_iso="2025-01-01T00:00:00Z",
                include_patterns=["*.pdf"],
                exclude_patterns=["~*"],
                include_folders=False
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify filtering worked
            self.assertIn('changes', result_data)
            self.assertIn('summary', result_data)

            summary = result_data['summary']
            self.assertEqual(summary['patterns_applied']['include'], ["*.pdf"])
            self.assertEqual(summary['patterns_applied']['exclude'], ["~*"])

    def test_error_handling_scenarios(self):
        """Test various error handling scenarios."""
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

            # Mock service to raise 404 error
            mock_service.files().get.return_value.execute.side_effect = MockHttpError(404)

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

            # Should have processed the file and recorded the error
            summary = result_data['summary']
            self.assertEqual(summary['processed_files'], 1)
            self.assertEqual(summary['errors'], 1)

    def test_check_folder_contents_pagination(self):
        """Test folder content checking with pagination."""
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

            # Mock fnmatch to always match
            sys.modules['fnmatch'].fnmatch.return_value = True

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(
                file_ids=["test_folder_id"],
                page_size=2,
                include_folders=True
            )

            # Mock Google service with pagination
            mock_service = MagicMock()

            # Mock page 1 response
            page1_response = {
                'nextPageToken': 'page2_token',
                'files': [
                    {
                        'id': 'file1_id',
                        'name': 'doc1.pdf',
                        'mimeType': 'application/pdf',
                        'size': '1024',
                        'modifiedTime': '2025-01-15T10:30:00Z',
                        'version': '123',
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    }
                ]
            }

            # Mock page 2 response (no more pages)
            page2_response = {
                'files': [
                    {
                        'id': 'file2_id',
                        'name': 'doc2.pdf',
                        'mimeType': 'application/pdf',
                        'size': '2048',
                        'modifiedTime': '2025-01-15T11:00:00Z',
                        'version': '124',
                        'owners': [{'emailAddress': 'owner@example.com'}]
                    }
                ]
            }

            # Setup call sequence for pagination
            call_count = [0]
            def mock_list_execute(*args, **kwargs):
                if call_count[0] == 0:
                    call_count[0] += 1
                    return page1_response
                else:
                    return page2_response

            mock_service.files().list.return_value.execute.side_effect = mock_list_execute

            # Test folder content checking directly
            changes = tool._check_folder_contents(mock_service, "test_folder_id")

            # Verify pagination worked and got both files
            self.assertEqual(len(changes), 2)
            self.assertEqual(changes[0]['file_id'], 'file1_id')
            self.assertEqual(changes[1]['file_id'], 'file2_id')


if __name__ == '__main__':
    unittest.main(verbosity=2)