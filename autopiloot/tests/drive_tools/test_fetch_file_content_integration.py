#!/usr/bin/env python3
"""
Integration tests for FetchFileContent tool
Tests the complete run() method workflow with mocked Google Drive API
"""

import unittest
import json
import sys
import os
import base64
from unittest.mock import patch, MagicMock, Mock
import importlib.util

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestFetchFileContentIntegration(unittest.TestCase):
    """Integration tests for FetchFileContent tool run() method."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'fetch_file_content' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_successful_text_file_fetch(self):
        """Test successful fetching of a plain text file."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
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

            # Mock environment
            mock_env_loader = MagicMock()
            mock_env_loader.get_required_env_var.return_value = "/path/to/credentials.json"
            sys.modules['env_loader'] = mock_env_loader

            # Mock Google APIs
            mock_credentials = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials

            # Mock Drive service and API responses
            mock_service = MagicMock()

            # Mock file metadata response
            mock_metadata = {
                'id': 'test_file_id',
                'name': 'test_document.txt',
                'mimeType': 'text/plain',
                'size': '1024',
                'modifiedTime': '2025-09-20T10:00:00.000Z',
                'createdTime': '2025-09-20T09:00:00.000Z'
            }
            mock_service.files().get().execute.return_value = mock_metadata

            # Mock file content download
            test_content = "This is the content of the test file."
            mock_service.files().get_media().execute.return_value = test_content.encode('utf-8')

            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    extract_text_only=True,
                    include_metadata=True,
                    max_size_mb=5.0
                )

                # Execute tool
                result = tool.run()
                result_data = json.loads(result)

                # Verify successful result
                self.assertEqual(result_data['content'], test_content)
                self.assertEqual(result_data['content_type'], 'text')
                self.assertEqual(result_data['mime_type'], 'text/plain')
                self.assertEqual(result_data['content_length'], len(test_content))
                self.assertEqual(result_data['raw_size_bytes'], len(test_content.encode('utf-8')))

                # Verify metadata
                self.assertIn('metadata', result_data)
                metadata = result_data['metadata']
                self.assertEqual(metadata['name'], 'test_document.txt')
                self.assertIn('size', metadata)
                self.assertEqual(metadata['size'], 1024)  # Uses size from file metadata

    def test_successful_google_docs_export(self):
        """Test successful export of a Google Docs file."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
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

            # Mock environment
            mock_env_loader = MagicMock()
            mock_env_loader.get_required_env_var.return_value = "/path/to/credentials.json"
            sys.modules['env_loader'] = mock_env_loader

            # Mock Google APIs
            mock_credentials = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials

            # Mock Drive service and API responses
            mock_service = MagicMock()

            # Mock file metadata response for Google Docs
            mock_metadata = {
                'id': 'google_doc_id',
                'name': 'My Google Document',
                'mimeType': 'application/vnd.google-apps.document',
                'size': '2048',
                'modifiedTime': '2025-09-20T11:00:00.000Z',
                'createdTime': '2025-09-20T10:00:00.000Z'
            }
            mock_service.files().get().execute.return_value = mock_metadata

            # Mock file export (Google Docs to plain text)
            exported_content = "This is the exported content from Google Docs."
            mock_service.files().export_media().execute.return_value = exported_content.encode('utf-8')

            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="google_doc_id",
                    extract_text_only=True,
                    include_metadata=True,
                    max_size_mb=5.0
                )

                # Execute tool
                result = tool.run()
                result_data = json.loads(result)

                # Verify successful result
                self.assertEqual(result_data['content'], exported_content)
                self.assertEqual(result_data['content_type'], 'text')
                self.assertEqual(result_data['mime_type'], 'text/plain')  # Export MIME type

                # Verify export was called instead of direct download
                mock_service.files().export_media.assert_called_with(
                    fileId="google_doc_id",
                    mimeType="text/plain"
                )

    def test_file_too_large_error(self):
        """Test error handling when file exceeds size limit."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
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

            # Mock environment
            mock_env_loader = MagicMock()
            mock_env_loader.get_required_env_var.return_value = "/path/to/credentials.json"
            sys.modules['env_loader'] = mock_env_loader

            # Mock Google APIs
            mock_credentials = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials

            # Mock Drive service
            mock_service = MagicMock()

            # Mock file metadata response with large size
            mock_metadata = {
                'id': 'large_file_id',
                'name': 'large_file.pdf',
                'mimeType': 'application/pdf',
                'size': str(10 * 1024 * 1024),  # 10 MB
                'modifiedTime': '2025-09-20T11:00:00.000Z'
            }
            mock_service.files().get().execute.return_value = mock_metadata

            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool with 5MB limit (file is 10MB)
                tool = FetchFileContent(
                    file_id="large_file_id",
                    max_size_mb=5.0  # File exceeds this limit
                )

                # Execute tool
                result = tool.run()
                result_data = json.loads(result)

                # Verify error response
                self.assertIn('error', result_data)
                self.assertEqual(result_data['error'], 'file_too_large')
                self.assertIn('exceeds limit', result_data['message'])

    def test_google_api_error_handling(self):
        """Test error handling for Google API errors."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
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

            # Mock environment
            mock_env_loader = MagicMock()
            mock_env_loader.get_required_env_var.return_value = "/path/to/credentials.json"
            sys.modules['env_loader'] = mock_env_loader

            # Mock Google APIs
            mock_credentials = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials

            # Mock HttpError
            class MockHttpError(Exception):
                def __init__(self, resp, content):
                    self.resp = Mock()
                    self.resp.status = resp
                    super().__init__(content)

            sys.modules['googleapiclient.errors'].HttpError = MockHttpError

            # Mock Drive service
            mock_service = MagicMock()

            # Mock API error (file not found)
            mock_service.files().get().execute.side_effect = MockHttpError(404, "File not found")

            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="nonexistent_file_id",
                    max_size_mb=5.0
                )

                # Execute tool
                result = tool.run()
                result_data = json.loads(result)

                # Verify error response
                self.assertIn('error', result_data)
                self.assertEqual(result_data['error'], 'file_not_found')
                self.assertIn('not found', result_data['message'])

    def test_binary_content_fetch(self):
        """Test fetching binary content (extract_text_only=False)."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
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

            # Mock environment
            mock_env_loader = MagicMock()
            mock_env_loader.get_required_env_var.return_value = "/path/to/credentials.json"
            sys.modules['env_loader'] = mock_env_loader

            # Mock Google APIs
            mock_credentials = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials

            # Mock Drive service
            mock_service = MagicMock()

            # Mock file metadata response
            mock_metadata = {
                'id': 'binary_file_id',
                'name': 'image.png',
                'mimeType': 'image/png',
                'size': '1024',
                'modifiedTime': '2025-09-20T10:00:00.000Z'
            }
            mock_service.files().get().execute.return_value = mock_metadata

            # Mock binary file content
            binary_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'  # PNG header
            mock_service.files().get_media().execute.return_value = binary_content

            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool for binary content
                tool = FetchFileContent(
                    file_id="binary_file_id",
                    extract_text_only=False,  # Binary mode
                    include_metadata=False,
                    max_size_mb=5.0
                )

                # Execute tool
                result = tool.run()
                result_data = json.loads(result)

                # Verify binary result
                self.assertEqual(result_data['content_type'], 'base64')
                self.assertEqual(result_data['mime_type'], 'image/png')

                # Verify content is base64 encoded
                expected_b64 = base64.b64encode(binary_content).decode('utf-8')
                self.assertEqual(result_data['content'], expected_b64)


if __name__ == '__main__':
    unittest.main(verbosity=2)