#!/usr/bin/env python3
"""
Working coverage test for list_drive_changes.py
Uses proper import strategy to ensure actual source code execution for coverage measurement
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util
from datetime import datetime, timezone


class TestListDriveChangesCoverageWorking(unittest.TestCase):
    """Working tests for ListDriveChanges tool that properly measure coverage"""

    def _setup_mocks_and_import(self):
        """Set up mocks and import the real module for coverage measurement"""

        # Create proper nested module structure for Google APIs
        google_module = type('Module', (), {})
        google_oauth2_module = type('Module', (), {})
        google_oauth2_service_account_module = type('Module', (), {})
        googleapiclient_module = type('Module', (), {})
        googleapiclient_discovery_module = type('Module', (), {})
        googleapiclient_errors_module = type('Module', (), {})

        google_module.oauth2 = google_oauth2_module
        google_oauth2_module.service_account = google_oauth2_service_account_module
        googleapiclient_module.discovery = googleapiclient_discovery_module
        googleapiclient_module.errors = googleapiclient_errors_module

        # Create mock credentials and service
        mock_credentials = Mock()
        google_oauth2_service_account_module.Credentials = Mock()
        google_oauth2_service_account_module.Credentials.from_service_account_file = Mock(return_value=mock_credentials)

        # Create mock Drive service
        mock_service = Mock()
        googleapiclient_discovery_module.build = Mock(return_value=mock_service)

        # Create HttpError class
        class MockHttpError(Exception):
            def __init__(self, resp, content):
                self.resp = resp
                self.content = content
                super().__init__()

        googleapiclient_errors_module.HttpError = MockHttpError

        # Create Agency Swarm mocks
        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool

        # Create pydantic mock
        pydantic_module = type('Module', (), {})
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)
        pydantic_module.Field = mock_field

        # Set up environment loader mock
        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value='/fake/path/to/credentials.json')

        # Apply all mocks to sys.modules
        sys.modules['google'] = google_module
        sys.modules['google.oauth2'] = google_oauth2_module
        sys.modules['google.oauth2.service_account'] = google_oauth2_service_account_module
        sys.modules['googleapiclient'] = googleapiclient_module
        sys.modules['googleapiclient.discovery'] = googleapiclient_discovery_module
        sys.modules['googleapiclient.errors'] = googleapiclient_errors_module
        sys.modules['agency_swarm'] = agency_swarm_module
        sys.modules['agency_swarm.tools'] = agency_swarm_tools_module
        sys.modules['pydantic'] = pydantic_module
        sys.modules['env_loader'] = env_loader_module

        # Now import the actual module directly using importlib
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'drive_agent', 'tools', 'list_drive_changes.py')
        spec = importlib.util.spec_from_file_location("list_drive_changes", tool_path)
        module = importlib.util.module_from_spec(spec)

        # Execute module
        spec.loader.exec_module(module)

        return module.ListDriveChanges, mock_service, MockHttpError

    def test_successful_file_change_detection(self):
        """Test successful file change detection"""
        ListDriveChanges, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = ListDriveChanges(file_ids=['test_file_id'])

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Mock file metadata response
        mock_get.execute.return_value = {
            'id': 'test_file_id',
            'name': 'test_document.pdf',
            'mimeType': 'application/pdf',
            'size': '1024',
            'modifiedTime': '2023-01-02T10:00:00Z',
            'version': '1',
            'webViewLink': 'https://drive.google.com/file/d/test_file_id',
            'owners': [{'emailAddress': 'owner@example.com'}]
        }

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('changes', result_data)
        self.assertIn('summary', result_data)
        self.assertEqual(result_data['summary']['processed_files'], 1)

    def test_http_error_404_handling(self):
        """Test HTTP 404 error handling"""
        ListDriveChanges, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = ListDriveChanges(file_ids=['test_file_id'])

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Create 404 HTTP error
        mock_response = Mock()
        mock_response.status = 404
        http_error = MockHttpError(mock_response, b'{"error": "not found"}')
        mock_get.execute.side_effect = http_error

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify error handling
        self.assertIn('changes', result_data)
        changes = result_data['changes']
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['change_type'], 'error')

    def test_http_error_403_handling(self):
        """Test HTTP 403 error handling"""
        ListDriveChanges, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = ListDriveChanges(file_ids=['test_file_id'])

        # Mock the service calls with direct method access
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get

        # Create 403 HTTP error
        mock_response = Mock()
        mock_response.status = 403
        http_error = MockHttpError(mock_response, b'{"error": "forbidden"}')
        mock_get.execute.side_effect = http_error

        # Call _get_file_changes directly to test error handling
        result = tool._get_file_changes(mock_service, 'test_file_id')

        # Verify specific 403 error handling
        self.assertEqual(result['change_type'], 'access_denied')
        self.assertIn('Permission denied', result['error'])

    def test_http_error_500_handling(self):
        """Test HTTP 500 error handling"""
        ListDriveChanges, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = ListDriveChanges(file_ids=['test_file_id'])

        # Create 500 HTTP error
        mock_response = Mock()
        mock_response.status = 500
        http_error = MockHttpError(mock_response, b'{"error": "server error"}')

        # Call _get_file_changes directly with error
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_get = Mock()
        mock_files.get.return_value = mock_get
        mock_get.execute.side_effect = http_error

        result = tool._get_file_changes(mock_service, 'test_file_id')

        # Verify general API error handling
        self.assertEqual(result['change_type'], 'error')
        self.assertIn('API error', result['error'])

    def test_folder_contents_processing(self):
        """Test folder contents processing"""
        ListDriveChanges, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = ListDriveChanges(file_ids=['folder_id'], include_folders=True)

        # Mock folder contents listing
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list

        # Mock response with files
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1024',
                    'modifiedTime': '2023-01-02T10:00:00Z',
                    'version': '1',
                    'webViewLink': 'https://drive.google.com/file/d/file1',
                    'owners': [{'emailAddress': 'owner@example.com'}]
                }
            ]
        }

        # Call _check_folder_contents directly
        changes = tool._check_folder_contents(mock_service, 'folder_id')

        # Verify folder processing
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['file_id'], 'file1')
        self.assertEqual(changes[0]['type'], 'file')

    def test_pattern_matching(self):
        """Test pattern matching functionality"""
        ListDriveChanges, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool with patterns
        tool = ListDriveChanges(
            file_ids=['test_id'],
            include_patterns=['*.pdf', '*.docx'],
            exclude_patterns=['~*']
        )

        # Test various pattern matches
        test_cases = [
            ('document.pdf', True),
            ('document.txt', False),
            ('test.docx', True),
            ('~temp.pdf', False),  # Excluded
            ('', False),  # Empty name
        ]

        for filename, expected_match in test_cases:
            result = tool._matches_patterns(filename)
            self.assertEqual(result, expected_match,
                           f"Pattern matching failed for {filename}")

    def test_iso_timestamp_parsing(self):
        """Test ISO timestamp parsing"""
        ListDriveChanges, mock_service, MockHttpError = self._setup_mocks_and_import()

        tool = ListDriveChanges(file_ids=['test_id'])

        # Test various ISO formats
        test_timestamps = [
            '2023-01-01T00:00:00Z',
            '2023-01-01T00:00:00+00:00',
            '2023-01-01T00:00:00'
        ]

        for timestamp in test_timestamps:
            try:
                result = tool._parse_iso_timestamp(timestamp)
                self.assertIsInstance(result, datetime)
            except ValueError:
                self.fail(f"Failed to parse valid timestamp: {timestamp}")


if __name__ == "__main__":
    unittest.main()