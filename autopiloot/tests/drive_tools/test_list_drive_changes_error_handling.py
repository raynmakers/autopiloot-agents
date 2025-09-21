#!/usr/bin/env python3

import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import os
import importlib.util

class TestListDriveChangesErrorHandling(unittest.TestCase):
    """Test error handling scenarios for list_drive_changes.py"""

    @classmethod
    def setUpClass(cls):
        """Set up class with comprehensive module mocking"""
        # Mock all external dependencies
        cls.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock(),
            'json': MagicMock(),
            'os': MagicMock(),
            'datetime': MagicMock()
        }

        # Set up BaseTool mock
        base_tool_mock = MagicMock()
        base_tool_mock.run = MagicMock(return_value='{"result": "success"}')
        cls.mock_modules['agency_swarm.tools'].BaseTool = base_tool_mock

        # Mock Pydantic Field
        field_mock = MagicMock()
        field_mock.return_value = "mocked_field"
        cls.mock_modules['pydantic'].Field = field_mock

        # Load the actual module
        module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
        cls.module = cls._load_module_with_mocks(module_path)

    @classmethod
    def _load_module_with_mocks(cls, module_path):
        """Load module with comprehensive mocking"""
        with patch.dict('sys.modules', cls.mock_modules):
            spec = importlib.util.spec_from_file_location("list_drive_changes", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

    def setUp(self):
        """Set up each test with fresh mocks"""
        with patch.dict('sys.modules', self.mock_modules):
            self.tool = self.module.ListDriveChanges(
                start_page_token="12345",
                include_patterns=["*.pdf"],
                exclude_patterns=["*.tmp"]
            )

            # Mock environment variables
            self.env_patcher = patch.dict(os.environ, {
                'GCP_PROJECT_ID': 'test-project',
                'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
            })
            self.env_patcher.start()

    def tearDown(self):
        """Clean up after each test"""
        self.env_patcher.stop()

    def test_http_404_error_handling(self):
        """Test HTTP 404 error handling in file change detection (lines 165-170)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock HTTP 404 error
            http_error = Exception("HTTP 404: File not found")
            http_error.status_code = 404

            # Mock service that raises 404 error
            mock_service = MagicMock()
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.side_effect = http_error
            mock_service.changes.return_value = mock_changes

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle 404 gracefully
                self.assertIn('"changes":', result)
                # Should return empty changes list for 404
                self.assertIn('[]', result)

    def test_http_403_error_handling(self):
        """Test HTTP 403 error handling in file change detection (lines 171-175)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock HTTP 403 error (permission denied)
            http_error = Exception("HTTP 403: Permission denied")
            http_error.status_code = 403

            # Mock service that raises 403 error
            mock_service = MagicMock()
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.side_effect = http_error
            mock_service.changes.return_value = mock_changes

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle 403 as error
                self.assertIn('"error":', result)
                self.assertIn('permission', result.lower())

    def test_general_http_error_handling(self):
        """Test general HTTP error handling (lines 176-180)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock general HTTP error
            http_error = Exception("HTTP 500: Internal server error")
            http_error.status_code = 500

            # Mock service that raises general error
            mock_service = MagicMock()
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.side_effect = http_error
            mock_service.changes.return_value = mock_changes

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle general HTTP errors
                self.assertIn('"error":', result)
                self.assertIn('500', result)

    def test_unexpected_exception_handling(self):
        """Test unexpected exception handling (lines 181-186)"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock unexpected exception
            unexpected_error = ValueError("Unexpected error occurred")

            # Mock service that raises unexpected error
            mock_service = MagicMock()
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.side_effect = unexpected_error
            mock_service.changes.return_value = mock_changes

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle unexpected errors gracefully
                self.assertIn('"error":', result)
                self.assertIn('unexpected', result.lower())

    def test_file_metadata_retrieval_error(self):
        """Test error handling in file metadata retrieval"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock service with changes but file get fails
            mock_service = MagicMock()

            # Mock successful changes list
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.return_value = {
                'changes': [{'fileId': 'test_file_id'}],
                'newStartPageToken': '67890'
            }
            mock_service.changes.return_value = mock_changes

            # Mock file get that fails
            mock_files = MagicMock()
            mock_files.get.return_value.execute.side_effect = Exception("File access error")
            mock_service.files.return_value = mock_files

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle file retrieval errors
                self.assertIn('"error":', result)

    def test_pattern_matching_error_recovery(self):
        """Test error recovery when pattern matching fails"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock fnmatch to raise error
            self.mock_modules['fnmatch'].fnmatch.side_effect = Exception("Pattern error")

            # Mock successful service and file data
            mock_service = MagicMock()
            mock_changes = MagicMock()
            mock_changes.list.return_value.execute.return_value = {
                'changes': [{'fileId': 'test_file_id'}],
                'newStartPageToken': '67890'
            }
            mock_service.changes.return_value = mock_changes

            mock_files = MagicMock()
            mock_files.get.return_value.execute.return_value = {
                'id': 'test_file_id',
                'name': 'test.pdf',
                'mimeType': 'application/pdf'
            }
            mock_service.files.return_value = mock_files

            with patch.object(self.tool, '_get_drive_service', return_value=mock_service):
                result = self.tool.run()

                # Should handle pattern matching errors
                self.assertIn('"error":', result)

    def test_service_initialization_error(self):
        """Test error handling when Drive service initialization fails"""
        with patch.dict('sys.modules', self.mock_modules):
            # Mock service initialization failure
            with patch.object(self.tool, '_get_drive_service', side_effect=Exception("Service init failed")):
                result = self.tool.run()

                # Should handle service initialization errors
                self.assertIn('"error":', result)
                self.assertIn('service', result.lower())

    def test_malformed_timestamp_error(self):
        """Test handling of malformed ISO timestamps"""
        with patch.dict('sys.modules', self.mock_modules):
            # Create tool with malformed timestamp
            tool_with_bad_time = self.module.ListDriveChanges(
                start_page_token="12345",
                modified_after="invalid-timestamp-format"
            )

            result = tool_with_bad_time.run()

            # Should handle malformed timestamp gracefully
            self.assertIn('"error":', result)
            self.assertIn('timestamp', result.lower())

if __name__ == '__main__':
    unittest.main()