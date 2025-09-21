#!/usr/bin/env python3
"""
Processing logic tests for ListDriveChanges tool
Tests file change detection, filtering, and folder content processing
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


class TestListDriveChangesProcessing(unittest.TestCase):
    """Processing logic tests for ListDriveChanges tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'list_drive_changes' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_get_file_changes_successful_file(self):
        """Test successful file change detection."""
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
            sys.modules['fnmatch'].fnmatch = lambda name, pattern: True

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
                file_ids=["test_file_id"],
                since_iso="2025-01-01T00:00:00Z"
            )

            # Mock Drive service and API response
            mock_service = MagicMock()
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
            mock_service.files().get().execute.return_value = mock_file_metadata

            # Test file change detection
            result = tool._get_file_changes(mock_service, "test_file_id")

            # Verify result structure
            self.assertIsNotNone(result)
            self.assertEqual(result['file_id'], 'test_file_id')
            self.assertEqual(result['name'], 'test_document.pdf')
            self.assertEqual(result['mimeType'], 'application/pdf')
            self.assertEqual(result['size'], 1024000)
            self.assertEqual(result['modifiedTime'], '2025-01-15T10:30:00Z')
            self.assertEqual(result['type'], 'file')
            self.assertEqual(result['change_type'], 'modified')
            self.assertEqual(result['owner'], 'owner@example.com')
            self.assertEqual(result['parent_folder_id'], 'parent_folder_id')

    def test_get_file_changes_folder_file(self):
        """Test folder file change detection."""
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

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool with include_folders=True
            tool = ListDriveChanges(
                file_ids=["test_folder_id"],
                include_folders=True
            )

            # Mock Drive service and API response for folder
            mock_service = MagicMock()
            mock_folder_metadata = {
                'id': 'test_folder_id',
                'name': 'Test Folder',
                'mimeType': 'application/vnd.google-apps.folder',
                'modifiedTime': '2025-01-15T10:30:00Z',
                'version': '123',
                'webViewLink': 'https://drive.google.com/drive/folders/test_folder_id',
                'owners': [{'emailAddress': 'owner@example.com'}]
            }
            mock_service.files().get().execute.return_value = mock_folder_metadata

            # Test folder change detection
            result = tool._get_file_changes(mock_service, "test_folder_id")

            # Verify result structure
            self.assertIsNotNone(result)
            self.assertEqual(result['file_id'], 'test_folder_id')
            self.assertEqual(result['name'], 'Test Folder')
            self.assertEqual(result['mimeType'], 'application/vnd.google-apps.folder')
            self.assertEqual(result['type'], 'folder')
            self.assertEqual(result['change_type'], 'modified')

    def test_get_file_changes_folder_excluded(self):
        """Test folder change detection when folders are excluded."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool with include_folders=False
            tool = ListDriveChanges(
                file_ids=["test_folder_id"],
                include_folders=False
            )

            # Mock Drive service and API response for folder
            mock_service = MagicMock()
            mock_folder_metadata = {
                'id': 'test_folder_id',
                'name': 'Test Folder',
                'mimeType': 'application/vnd.google-apps.folder',
                'modifiedTime': '2025-01-15T10:30:00Z'
            }
            mock_service.files().get().execute.return_value = mock_folder_metadata

            # Test folder change detection with exclusion
            result = tool._get_file_changes(mock_service, "test_folder_id")

            # Should return None for excluded folders
            self.assertIsNone(result)

    def test_get_file_changes_pattern_mismatch(self):
        """Test file change detection with pattern mismatch."""
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

            # Mock fnmatch to return False (no match)
            sys.modules['fnmatch'].fnmatch = lambda name, pattern: False

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool with include patterns
            tool = ListDriveChanges(
                file_ids=["test_file_id"],
                include_patterns=["*.pdf"]
            )

            # Mock Drive service and API response
            mock_service = MagicMock()
            mock_file_metadata = {
                'id': 'test_file_id',
                'name': 'test_document.txt',  # Won't match *.pdf pattern
                'mimeType': 'text/plain',
                'modifiedTime': '2025-01-15T10:30:00Z'
            }
            mock_service.files().get().execute.return_value = mock_file_metadata

            # Test file change detection with pattern mismatch
            result = tool._get_file_changes(mock_service, "test_file_id")

            # Should return None for non-matching files
            self.assertIsNone(result)

    def test_get_file_changes_no_modified_time(self):
        """Test file change detection without modified time."""
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
            sys.modules['fnmatch'].fnmatch = lambda name, pattern: True

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Mock Drive service and API response without modifiedTime
            mock_service = MagicMock()
            mock_file_metadata = {
                'id': 'test_file_id',
                'name': 'test_document.pdf',
                'mimeType': 'application/pdf'
                # No modifiedTime field
            }
            mock_service.files().get().execute.return_value = mock_file_metadata

            # Test file change detection without modified time
            result = tool._get_file_changes(mock_service, "test_file_id")

            # Should return None for files without modification time
            self.assertIsNone(result)

    def test_get_file_changes_time_filter_excluded(self):
        """Test file change detection with time filter exclusion."""
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
            sys.modules['fnmatch'].fnmatch = lambda name, pattern: True

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool with since_iso filtering
            tool = ListDriveChanges(
                file_ids=["test_file_id"],
                since_iso="2025-01-15T00:00:00Z"  # File modified before this
            )

            # Mock Drive service and API response
            mock_service = MagicMock()
            mock_file_metadata = {
                'id': 'test_file_id',
                'name': 'test_document.pdf',
                'mimeType': 'application/pdf',
                'modifiedTime': '2025-01-01T10:30:00Z'  # Before since_iso
            }
            mock_service.files().get().execute.return_value = mock_file_metadata

            # Test file change detection with time exclusion
            result = tool._get_file_changes(mock_service, "test_file_id")

            # Should return None for files modified before since_iso
            self.assertIsNone(result)

    def test_get_file_changes_http_error_404(self):
        """Test file change detection with 404 HTTP error."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
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

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Mock Drive service to raise 404 error
            mock_service = MagicMock()
            mock_service.files().get().execute.side_effect = MockHttpError(404)

            # Test file change detection with 404 error
            result = tool._get_file_changes(mock_service, "test_file_id")

            # Should return error record for 404
            self.assertIsNotNone(result)
            self.assertEqual(result['file_id'], 'test_file_id')
            self.assertEqual(result['change_type'], 'deleted_or_inaccessible')
            self.assertIn('not found', result['error'])

    def test_get_file_changes_http_error_403(self):
        """Test file change detection with 403 HTTP error."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
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

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Mock Drive service to raise 403 error
            mock_service = MagicMock()
            mock_service.files().get().execute.side_effect = MockHttpError(403)

            # Test file change detection with 403 error
            result = tool._get_file_changes(mock_service, "test_file_id")

            # Should return error record for 403
            self.assertIsNotNone(result)
            self.assertEqual(result['file_id'], 'test_file_id')
            self.assertEqual(result['change_type'], 'access_denied')
            self.assertIn('Permission denied', result['error'])

    def test_get_file_changes_general_exception(self):
        """Test file change detection with general exception."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Mock Drive service to raise general exception
            mock_service = MagicMock()
            mock_service.files().get().execute.side_effect = Exception("Network error")

            # Test file change detection with general exception
            result = tool._get_file_changes(mock_service, "test_file_id")

            # Should return error record for general exception
            self.assertIsNotNone(result)
            self.assertEqual(result['file_id'], 'test_file_id')
            self.assertEqual(result['change_type'], 'error')
            self.assertIn('Unexpected error', result['error'])
            self.assertIn('Network error', result['error'])


if __name__ == '__main__':
    unittest.main(verbosity=2)