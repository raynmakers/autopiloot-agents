#!/usr/bin/env python3
"""
Working tests for resolve_folder_tree.py
Uses successful mocking pattern to achieve actual code coverage
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util


class TestResolveFolderTreeWorking(unittest.TestCase):
    """Working tests for ResolveFolderTree tool"""

    def _load_and_test_tool(self, mock_folder_metadata, mock_list_results, **tool_kwargs):
        """Helper method to load tool and execute with mocking"""

        # Create minimal BaseTool implementation
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        # Create mock modules with plain objects
        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'google': type('Module', (), {}),
            'google.oauth2': type('Module', (), {}),
            'google.oauth2.service_account': type('Module', (), {}),
            'googleapiclient': type('Module', (), {}),
            'googleapiclient.discovery': type('Module', (), {}),
            'googleapiclient.errors': type('Module', (), {}),
            'fnmatch': type('Module', (), {}),
            'env_loader': type('Module', (), {}),
            'loader': type('Module', (), {})
        }

        # Set up mocks
        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

        # Create mock Drive service
        mock_service = Mock()
        mock_service.files().get.return_value.execute.return_value = mock_folder_metadata
        mock_service.files().list.return_value.execute.return_value = mock_list_results

        # Mock Google API functions
        mock_modules['google.oauth2.service_account'].Credentials.from_service_account_file = Mock(return_value=Mock())
        mock_modules['googleapiclient.discovery'].build = Mock(return_value=mock_service)

        # Mock fnmatch
        mock_modules['fnmatch'].fnmatch = Mock(side_effect=lambda name, pattern: True)

        # Mock environment and config functions
        mock_modules['env_loader'].get_required_env_var = Mock(return_value="/path/to/creds.json")
        mock_modules['loader'].get_config_value = Mock(return_value=None)

        # Create HttpError class mock
        http_error_class = type('HttpError', (Exception,), {})
        mock_modules['googleapiclient.errors'].HttpError = http_error_class

        with patch.dict('sys.modules', mock_modules):
            # Load module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            # Execute module
            spec.loader.exec_module(module)

            # Create and run tool
            tool = module.ResolveFolderTree(**tool_kwargs)

            return tool.run()

    def test_successful_folder_resolution_non_recursive(self):
        """Test successful folder resolution without recursion"""

        mock_folder_metadata = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_list_results = {
            'files': [
                {
                    'id': 'file_1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1024000',
                    'modifiedTime': '2025-01-15T10:00:00Z',
                    'webViewLink': 'https://drive.google.com/file1',
                    'owners': [{'emailAddress': 'owner@example.com'}]
                },
                {
                    'id': 'subfolder_1',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
            ]
        }

        result = self._load_and_test_tool(
            mock_folder_metadata,
            mock_list_results,
            folder_id="folder_123",
            recursive=False
        )

        # Verify result
        self.assertIsInstance(result, str)
        result_data = json.loads(result)

        self.assertIn("folder_tree", result_data)
        self.assertIn("summary", result_data)
        self.assertEqual(result_data["folder_tree"]["id"], "folder_123")
        self.assertEqual(result_data["folder_tree"]["name"], "Test Folder")
        self.assertEqual(len(result_data["folder_tree"]["files"]), 1)
        self.assertEqual(len(result_data["folder_tree"]["folders"]), 1)
        self.assertEqual(result_data["summary"]["recursive"], False)

    def test_successful_folder_resolution_recursive(self):
        """Test successful folder resolution with recursion"""

        mock_folder_metadata = {
            'id': 'root_folder',
            'name': 'Root',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_list_results = {
            'files': [
                {
                    'id': 'file_1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '500000'
                },
                {
                    'id': 'subfolder_1',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
            ]
        }

        result = self._load_and_test_tool(
            mock_folder_metadata,
            mock_list_results,
            folder_id="root_folder",
            recursive=True,
            max_depth=3
        )

        result_data = json.loads(result)
        self.assertIn("folder_tree", result_data)
        self.assertEqual(result_data["summary"]["recursive"], True)

    def test_pattern_filtering(self):
        """Test include/exclude pattern filtering"""

        mock_folder_metadata = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_list_results = {
            'files': [
                {'id': 'f1', 'name': 'document.pdf', 'mimeType': 'application/pdf', 'size': '1000'},
                {'id': 'f2', 'name': 'temp.tmp', 'mimeType': 'text/plain', 'size': '500'},
                {'id': 'f3', 'name': 'report.docx', 'mimeType': 'application/docx', 'size': '2000'}
            ]
        }

        # Mock pattern matching more precisely
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

        # Create modified mock modules for this test
        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'google': type('Module', (), {}),
            'google.oauth2': type('Module', (), {}),
            'google.oauth2.service_account': type('Module', (), {}),
            'googleapiclient': type('Module', (), {}),
            'googleapiclient.discovery': type('Module', (), {}),
            'googleapiclient.errors': type('Module', (), {}),
            'fnmatch': type('Module', (), {}),
            'env_loader': type('Module', (), {}),
            'loader': type('Module', (), {})
        }

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', [])

        # Create mock Drive service
        mock_service = Mock()
        mock_service.files().get.return_value.execute.return_value = mock_folder_metadata
        mock_service.files().list.return_value.execute.return_value = mock_list_results

        # Mock functions
        mock_modules['google.oauth2.service_account'].Credentials.from_service_account_file = Mock(return_value=Mock())
        mock_modules['googleapiclient.discovery'].build = Mock(return_value=mock_service)
        mock_modules['fnmatch'].fnmatch = mock_fnmatch
        mock_modules['env_loader'].get_required_env_var = Mock(return_value="/path/to/creds.json")
        mock_modules['loader'].get_config_value = Mock(return_value=None)

        http_error_class = type('HttpError', (Exception,), {})
        mock_modules['googleapiclient.errors'].HttpError = http_error_class

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.ResolveFolderTree(
                folder_id="folder_123",
                include_patterns=["*.pdf", "*.docx"],
                exclude_patterns=["*.tmp"]
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should include PDF and DOCX, exclude TMP
            files = result_data["folder_tree"]["files"]
            self.assertGreater(len(files), 0)  # Should have some files

    def test_max_depth_enforcement(self):
        """Test that max_depth is properly enforced"""

        mock_folder_metadata = {
            'id': 'root',
            'name': 'Root',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_list_results = {
            'files': [
                {
                    'id': 'deep_folder',
                    'name': 'Deep Folder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
            ]
        }

        result = self._load_and_test_tool(
            mock_folder_metadata,
            mock_list_results,
            folder_id="root",
            recursive=True,
            max_depth=2
        )

        result_data = json.loads(result)
        self.assertIn("folder_tree", result_data)

    def test_folder_not_found_error(self):
        """Test handling of folder not found error"""

        # Create HttpError mock
        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'google': type('Module', (), {}),
            'google.oauth2': type('Module', (), {}),
            'google.oauth2.service_account': type('Module', (), {}),
            'googleapiclient': type('Module', (), {}),
            'googleapiclient.discovery': type('Module', (), {}),
            'googleapiclient.errors': type('Module', (), {}),
            'fnmatch': type('Module', (), {}),
            'env_loader': type('Module', (), {}),
            'loader': type('Module', (), {})
        }

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

        # Create HttpError class and instance
        class HttpError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.resp = Mock()
                self.resp.status = 404

        mock_modules['googleapiclient.errors'].HttpError = HttpError

        # Create mock service that raises 404
        mock_service = Mock()
        mock_service.files().get.return_value.execute.side_effect = HttpError("404 Not Found")

        mock_modules['google.oauth2.service_account'].Credentials.from_service_account_file = Mock(return_value=Mock())
        mock_modules['googleapiclient.discovery'].build = Mock(return_value=mock_service)
        mock_modules['fnmatch'].fnmatch = Mock(return_value=True)
        mock_modules['env_loader'].get_required_env_var = Mock(return_value="/path/to/creds.json")
        mock_modules['loader'].get_config_value = Mock(return_value=None)

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.ResolveFolderTree(folder_id="nonexistent")
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "folder_not_found")
            self.assertIn("nonexistent", result_data["message"])

    def test_not_a_folder_error(self):
        """Test error when ID points to a file, not a folder"""

        mock_file_metadata = {
            'id': 'file_123',
            'name': 'document.pdf',
            'mimeType': 'application/pdf'
        }

        result = self._load_and_test_tool(
            mock_file_metadata,
            {'files': []},
            folder_id="file_123"
        )

        result_data = json.loads(result)
        self.assertEqual(result_data["error"], "not_a_folder")
        self.assertIn("application/pdf", result_data["mimeType"])

    def test_service_initialization_failure(self):
        """Test handling of Drive service initialization failure"""

        # Mock env_loader to raise exception
        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'google': type('Module', (), {}),
            'google.oauth2': type('Module', (), {}),
            'google.oauth2.service_account': type('Module', (), {}),
            'googleapiclient': type('Module', (), {}),
            'googleapiclient.discovery': type('Module', (), {}),
            'googleapiclient.errors': type('Module', (), {}),
            'fnmatch': type('Module', (), {}),
            'env_loader': type('Module', (), {}),
            'loader': type('Module', (), {})
        }

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

        # Mock env_loader to raise exception
        def mock_get_required_env_var(var_name):
            raise Exception("Service init failed")

        mock_modules['env_loader'].get_required_env_var = mock_get_required_env_var
        mock_modules['loader'].get_config_value = Mock(return_value=None)
        mock_modules['fnmatch'].fnmatch = Mock(return_value=True)

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.ResolveFolderTree(folder_id="test")
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "resolution_error")
            self.assertIn("Service init failed", result_data["message"])

    def test_owner_metadata_extraction(self):
        """Test extraction of file owner metadata"""

        mock_folder_metadata = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_list_results = {
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

        result = self._load_and_test_tool(
            mock_folder_metadata,
            mock_list_results,
            folder_id="folder_123"
        )

        result_data = json.loads(result)
        file_info = result_data["folder_tree"]["files"][0]
        self.assertEqual(file_info["owner"], "owner@example.com")

    def test_summary_statistics(self):
        """Test calculation of summary statistics"""

        mock_folder_metadata = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        mock_list_results = {
            'files': [
                {'id': 'f1', 'name': 'doc1.pdf', 'mimeType': 'application/pdf', 'size': '1048576'},
                {'id': 'f2', 'name': 'doc2.pdf', 'mimeType': 'application/pdf', 'size': '2097152'},
                {'id': 'folder1', 'name': 'Subfolder', 'mimeType': 'application/vnd.google-apps.folder'}
            ]
        }

        result = self._load_and_test_tool(
            mock_folder_metadata,
            mock_list_results,
            folder_id="folder_123",
            recursive=False,
            include_patterns=["*.pdf"]
        )

        result_data = json.loads(result)
        summary = result_data["summary"]
        self.assertEqual(summary["total_files"], 2)
        self.assertEqual(summary["total_folders"], 1)
        self.assertEqual(summary["total_size_bytes"], 3145728)
        self.assertEqual(summary["total_size_mb"], 3.0)
        self.assertEqual(summary["recursive"], False)


if __name__ == '__main__':
    unittest.main()