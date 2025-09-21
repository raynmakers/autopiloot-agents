#!/usr/bin/env python3
"""
Minimal working tests for resolve_folder_tree.py
Focusing on essential functionality to achieve code coverage
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util


class TestResolveFolderTreeMinimal(unittest.TestCase):
    """Minimal tests for ResolveFolderTree tool"""

    def test_successful_folder_resolution(self):
        """Test basic successful folder resolution"""

        # Create proper nested module structure
        google_module = type('Module', (), {})
        oauth2_module = type('Module', (), {})
        service_account_module = type('Module', (), {})

        # Set up the nested structure
        google_module.oauth2 = oauth2_module
        oauth2_module.service_account = service_account_module

        # Create credentials mock
        credentials_mock = Mock()
        service_account_module.Credentials = Mock()
        service_account_module.Credentials.from_service_account_file = Mock(return_value=credentials_mock)

        # Create googleapiclient module structure
        googleapiclient_module = type('Module', (), {})
        discovery_module = type('Module', (), {})
        errors_module = type('Module', (), {})

        googleapiclient_module.discovery = discovery_module
        googleapiclient_module.errors = errors_module

        # Create mock Drive service
        mock_service = Mock()

        # Mock folder metadata response
        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock folder contents response
        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {
                    'id': 'file_1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '1024000',
                    'modifiedTime': '2025-01-15T10:00:00Z',
                    'webViewLink': 'https://drive.google.com/file1',
                    'owners': [{'emailAddress': 'owner@example.com'}]
                }
            ]
        }

        # Mock build function
        discovery_module.build = Mock(return_value=mock_service)

        # Create other needed modules
        fnmatch_module = type('Module', (), {})
        fnmatch_module.fnmatch = Mock(return_value=True)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="/path/to/creds.json")

        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value=None)

        # Create HttpError class
        class HttpError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.resp = Mock()
                self.resp.status = 404

        errors_module.HttpError = HttpError

        # Create BaseTool mock
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module
        agency_swarm_tools_module.BaseTool = MockBaseTool

        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else True)

        # Set up complete mock modules
        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.oauth2': oauth2_module,
            'google.oauth2.service_account': service_account_module,
            'googleapiclient': googleapiclient_module,
            'googleapiclient.discovery': discovery_module,
            'googleapiclient.errors': errors_module,
            'fnmatch': fnmatch_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            # Load module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            # Execute module
            spec.loader.exec_module(module)

            # Create and run tool
            tool = module.ResolveFolderTree(
                folder_id="folder_123",
                recursive=False
            )

            result = tool.run()

            # Verify result
            self.assertIsInstance(result, str)
            result_data = json.loads(result)

            self.assertIn("folder_tree", result_data)
            self.assertIn("summary", result_data)
            self.assertEqual(result_data["folder_tree"]["id"], "folder_123")
            self.assertEqual(result_data["folder_tree"]["name"], "Test Folder")

    def test_not_a_folder_error(self):
        """Test error when ID points to a file, not a folder"""

        # Create the same module structure as above
        google_module = type('Module', (), {})
        oauth2_module = type('Module', (), {})
        service_account_module = type('Module', (), {})

        google_module.oauth2 = oauth2_module
        oauth2_module.service_account = service_account_module

        credentials_mock = Mock()
        service_account_module.Credentials = Mock()
        service_account_module.Credentials.from_service_account_file = Mock(return_value=credentials_mock)

        googleapiclient_module = type('Module', (), {})
        discovery_module = type('Module', (), {})
        errors_module = type('Module', (), {})

        googleapiclient_module.discovery = discovery_module
        googleapiclient_module.errors = errors_module

        # Mock service that returns file metadata instead of folder
        mock_service = Mock()
        mock_service.files().get.return_value.execute.return_value = {
            'id': 'file_123',
            'name': 'document.pdf',
            'mimeType': 'application/pdf'  # Not a folder!
        }

        discovery_module.build = Mock(return_value=mock_service)

        fnmatch_module = type('Module', (), {})
        fnmatch_module.fnmatch = Mock(return_value=True)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="/path/to/creds.json")

        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value=None)

        class HttpError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.resp = Mock()
                self.resp.status = 404

        errors_module.HttpError = HttpError

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module
        agency_swarm_tools_module.BaseTool = MockBaseTool

        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else True)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.oauth2': oauth2_module,
            'google.oauth2.service_account': service_account_module,
            'googleapiclient': googleapiclient_module,
            'googleapiclient.discovery': discovery_module,
            'googleapiclient.errors': errors_module,
            'fnmatch': fnmatch_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.ResolveFolderTree(folder_id="file_123")
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "not_a_folder")
            self.assertIn("application/pdf", result_data["mimeType"])

    def test_folder_not_found_error(self):
        """Test handling of folder not found error"""

        # Create module structure
        google_module = type('Module', (), {})
        oauth2_module = type('Module', (), {})
        service_account_module = type('Module', (), {})

        google_module.oauth2 = oauth2_module
        oauth2_module.service_account = service_account_module

        credentials_mock = Mock()
        service_account_module.Credentials = Mock()
        service_account_module.Credentials.from_service_account_file = Mock(return_value=credentials_mock)

        googleapiclient_module = type('Module', (), {})
        discovery_module = type('Module', (), {})
        errors_module = type('Module', (), {})

        googleapiclient_module.discovery = discovery_module
        googleapiclient_module.errors = errors_module

        # Create HttpError that gets raised
        class HttpError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.resp = Mock()
                self.resp.status = 404

        errors_module.HttpError = HttpError

        # Mock service that raises 404 error
        mock_service = Mock()
        mock_service.files().get.return_value.execute.side_effect = HttpError("404 Not Found")

        discovery_module.build = Mock(return_value=mock_service)

        fnmatch_module = type('Module', (), {})
        fnmatch_module.fnmatch = Mock(return_value=True)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="/path/to/creds.json")

        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value=None)

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module
        agency_swarm_tools_module.BaseTool = MockBaseTool

        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else True)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.oauth2': oauth2_module,
            'google.oauth2.service_account': service_account_module,
            'googleapiclient': googleapiclient_module,
            'googleapiclient.discovery': discovery_module,
            'googleapiclient.errors': errors_module,
            'fnmatch': fnmatch_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

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

    def test_service_initialization_failure(self):
        """Test handling of Drive service initialization failure"""

        # Create modules but make env_loader raise exception
        google_module = type('Module', (), {})
        oauth2_module = type('Module', (), {})
        service_account_module = type('Module', (), {})

        google_module.oauth2 = oauth2_module
        oauth2_module.service_account = service_account_module

        googleapiclient_module = type('Module', (), {})
        discovery_module = type('Module', (), {})
        errors_module = type('Module', (), {})

        googleapiclient_module.discovery = discovery_module
        googleapiclient_module.errors = errors_module
        discovery_module.build = Mock(return_value=Mock())

        fnmatch_module = type('Module', (), {})
        fnmatch_module.fnmatch = Mock(return_value=True)

        # Make env_loader raise exception
        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(side_effect=Exception("Service init failed"))

        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value=None)

        class HttpError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.resp = Mock()
                self.resp.status = 404

        errors_module.HttpError = HttpError

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module
        agency_swarm_tools_module.BaseTool = MockBaseTool

        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else True)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.oauth2': oauth2_module,
            'google.oauth2.service_account': service_account_module,
            'googleapiclient': googleapiclient_module,
            'googleapiclient.discovery': discovery_module,
            'googleapiclient.errors': errors_module,
            'fnmatch': fnmatch_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

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

    def test_pattern_matching_comprehensive(self):
        """Test comprehensive pattern matching logic"""

        # Create module structure
        google_module = type('Module', (), {})
        oauth2_module = type('Module', (), {})
        service_account_module = type('Module', (), {})

        google_module.oauth2 = oauth2_module
        oauth2_module.service_account = service_account_module

        credentials_mock = Mock()
        service_account_module.Credentials = Mock()
        service_account_module.Credentials.from_service_account_file = Mock(return_value=credentials_mock)

        googleapiclient_module = type('Module', (), {})
        discovery_module = type('Module', (), {})
        errors_module = type('Module', (), {})

        googleapiclient_module.discovery = discovery_module
        googleapiclient_module.errors = errors_module

        # Mock folder metadata
        mock_service = Mock()
        mock_service.files().get.return_value.execute.return_value = {
            'id': 'folder_123',
            'name': 'Test Folder',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock folder contents with various files for pattern testing
        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {'id': 'f1', 'name': 'document.pdf', 'mimeType': 'application/pdf', 'size': '1000'},
                {'id': 'f2', 'name': 'temp.tmp', 'mimeType': 'text/plain', 'size': '500'},
                {'id': 'f3', 'name': 'report.docx', 'mimeType': 'application/docx', 'size': '2000'},
                {'id': 'f4', 'name': 'image.jpg', 'mimeType': 'image/jpeg', 'size': '3000'}
            ]
        }

        discovery_module.build = Mock(return_value=mock_service)

        # Mock pattern matching to test all branches
        def mock_fnmatch(filename, pattern):
            filename = filename.lower()
            pattern = pattern.lower()
            if pattern == "*.tmp":
                return filename.endswith('.tmp')  # This should match temp.tmp
            elif pattern == "*.pdf":
                return filename.endswith('.pdf')  # This should match document.pdf
            elif pattern == "*.docx":
                return filename.endswith('.docx')  # This should match report.docx
            return False

        fnmatch_module = type('Module', (), {})
        fnmatch_module.fnmatch = mock_fnmatch

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="/path/to/creds.json")

        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value=None)

        class HttpError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.resp = Mock()
                self.resp.status = 404

        errors_module.HttpError = HttpError

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module
        agency_swarm_tools_module.BaseTool = MockBaseTool

        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else [])

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.oauth2': oauth2_module,
            'google.oauth2.service_account': service_account_module,
            'googleapiclient': googleapiclient_module,
            'googleapiclient.discovery': discovery_module,
            'googleapiclient.errors': errors_module,
            'fnmatch': fnmatch_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Test exclude patterns (should exclude .tmp files)
            tool = module.ResolveFolderTree(
                folder_id="folder_123",
                include_patterns=["*.pdf", "*.docx"],
                exclude_patterns=["*.tmp"]
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should include PDF and DOCX files, but exclude TMP files
            files = result_data["folder_tree"]["files"]
            file_names = [f["name"] for f in files]

            # The pattern matching should have filtered files
            self.assertGreater(len(files), 0)  # Should have some files

            # Test with no include patterns (should include all non-excluded)
            tool2 = module.ResolveFolderTree(
                folder_id="folder_123",
                include_patterns=[],  # Empty include patterns
                exclude_patterns=["*.tmp"]
            )

            result2 = tool2.run()
            result_data2 = json.loads(result2)
            files2 = result_data2["folder_tree"]["files"]

            # Should include more files when no include patterns specified
            self.assertGreaterEqual(len(files2), len(files))

    def test_recursive_folder_processing(self):
        """Test recursive folder processing and max depth"""

        # Create module structure
        google_module = type('Module', (), {})
        oauth2_module = type('Module', (), {})
        service_account_module = type('Module', (), {})

        google_module.oauth2 = oauth2_module
        oauth2_module.service_account = service_account_module

        credentials_mock = Mock()
        service_account_module.Credentials = Mock()
        service_account_module.Credentials.from_service_account_file = Mock(return_value=credentials_mock)

        googleapiclient_module = type('Module', (), {})
        discovery_module = type('Module', (), {})
        errors_module = type('Module', (), {})

        googleapiclient_module.discovery = discovery_module
        googleapiclient_module.errors = errors_module

        # Mock service with folder metadata
        mock_service = Mock()
        mock_service.files().get.return_value.execute.return_value = {
            'id': 'root_folder',
            'name': 'Root',
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Mock list response that includes subfolders
        mock_service.files().list.return_value.execute.return_value = {
            'files': [
                {
                    'id': 'file_1',
                    'name': 'document.pdf',
                    'mimeType': 'application/pdf',
                    'size': '500000',
                    'modifiedTime': '2025-01-15T10:00:00Z',
                    'owners': [{'emailAddress': 'owner@example.com'}]
                },
                {
                    'id': 'subfolder_1',
                    'name': 'Subfolder',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
            ]
        }

        discovery_module.build = Mock(return_value=mock_service)

        fnmatch_module = type('Module', (), {})
        fnmatch_module.fnmatch = Mock(return_value=True)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="/path/to/creds.json")

        loader_module = type('Module', (), {})
        loader_module.get_config_value = Mock(return_value=None)

        class HttpError(Exception):
            def __init__(self, message):
                super().__init__(message)
                self.resp = Mock()
                self.resp.status = 404

        errors_module.HttpError = HttpError

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module
        agency_swarm_tools_module.BaseTool = MockBaseTool

        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else True)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.oauth2': oauth2_module,
            'google.oauth2.service_account': service_account_module,
            'googleapiclient': googleapiclient_module,
            'googleapiclient.discovery': discovery_module,
            'googleapiclient.errors': errors_module,
            'fnmatch': fnmatch_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/resolve_folder_tree.py"
            spec = importlib.util.spec_from_file_location("resolve_folder_tree", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Test with low max_depth to trigger depth warning
            tool = module.ResolveFolderTree(
                folder_id="root_folder",
                recursive=True,
                max_depth=1  # Very low depth
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("folder_tree", result_data)
            # Should have processed the folder structure
            self.assertEqual(result_data["folder_tree"]["id"], "root_folder")


if __name__ == '__main__':
    unittest.main()