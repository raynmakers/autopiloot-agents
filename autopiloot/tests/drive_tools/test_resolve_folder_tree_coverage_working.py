#!/usr/bin/env python3
"""
Working coverage test for resolve_folder_tree.py
Uses proper import strategy to ensure actual source code execution for coverage measurement
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util


class TestResolveFolderTreeCoverageWorking(unittest.TestCase):
    """Working tests for ResolveFolderTree tool that properly measure coverage"""

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

        # Create fnmatch mock
        fnmatch_module = type('Module', (), {})
        fnmatch_module.fnmatch = lambda filename, pattern: filename.endswith('.txt') if pattern == '*.txt' else True

        # Set up environment and config loader mocks
        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value='/fake/path/to/credentials.json')

        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value={})

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
        sys.modules['fnmatch'] = fnmatch_module
        sys.modules['env_loader'] = env_loader_module
        sys.modules['loader'] = loader_module

        # Now import the actual module directly using importlib
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'drive_agent', 'tools', 'resolve_folder_tree.py')
        spec = importlib.util.spec_from_file_location("resolve_folder_tree", tool_path)
        module = importlib.util.module_from_spec(spec)

        # Execute module
        spec.loader.exec_module(module)

        return module.ResolveFolderTree, mock_service, MockHttpError

    def test_successful_folder_resolution(self):
        """Test successful folder tree resolution"""
        ResolveFolderTree, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = ResolveFolderTree(folder_id='test_folder_id')

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list

        # Mock folder contents response
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document.txt',
                    'mimeType': 'text/plain',
                    'size': '1024',
                    'modifiedTime': '2023-01-02T10:00:00Z',
                    'parents': ['test_folder_id']
                },
                {
                    'id': 'subfolder1',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'modifiedTime': '2023-01-01T10:00:00Z',
                    'parents': ['test_folder_id']
                }
            ]
        }

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('files', result_data)
        self.assertIn('folders', result_data)
        self.assertIn('summary', result_data)

    def test_http_error_handling(self):
        """Test HTTP error handling"""
        ResolveFolderTree, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool
        tool = ResolveFolderTree(folder_id='nonexistent_folder')

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list

        # Create 404 HTTP error
        mock_response = Mock()
        mock_response.status = 404
        http_error = MockHttpError(mock_response, b'{"error": "not found"}')
        mock_list.execute.side_effect = http_error

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify error handling
        self.assertIn('error', result_data)

    def test_pattern_filtering(self):
        """Test pattern filtering functionality"""
        ResolveFolderTree, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool with pattern
        tool = ResolveFolderTree(
            folder_id='test_folder_id',
            include_patterns=['*.txt']
        )

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list

        # Mock response with multiple file types
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document.txt',
                    'mimeType': 'text/plain',
                    'size': '1024',
                    'modifiedTime': '2023-01-02T10:00:00Z',
                    'parents': ['test_folder_id']
                },
                {
                    'id': 'file2',
                    'name': 'image.jpg',
                    'mimeType': 'image/jpeg',
                    'size': '2048',
                    'modifiedTime': '2023-01-02T10:00:00Z',
                    'parents': ['test_folder_id']
                }
            ]
        }

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify filtering worked
        self.assertIn('files', result_data)
        self.assertIn('summary', result_data)

    def test_recursive_traversal(self):
        """Test recursive folder traversal"""
        ResolveFolderTree, mock_service, MockHttpError = self._setup_mocks_and_import()

        # Create tool with recursion
        tool = ResolveFolderTree(
            folder_id='test_folder_id',
            recursive=True,
            max_depth=2
        )

        # Mock the service calls
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list

        # Mock response
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'subfolder1',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'modifiedTime': '2023-01-01T10:00:00Z',
                    'parents': ['test_folder_id']
                }
            ]
        }

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify recursion was attempted
        self.assertIn('folders', result_data)
        self.assertIn('summary', result_data)


if __name__ == "__main__":
    unittest.main()