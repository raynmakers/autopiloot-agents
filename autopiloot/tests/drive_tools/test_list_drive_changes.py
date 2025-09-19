"""
Test suite for ListDriveChanges tool.
Tests incremental change detection since last checkpoint with comprehensive error handling.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock environment and dependencies before importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
}):
    from unittest.mock import MagicMock
    mock_base_tool = MagicMock()
    mock_field = MagicMock()

    with patch('drive_agent.tools.list_drive_changes.BaseTool', mock_base_tool):
        with patch('drive_agent.tools.list_drive_changes.Field', mock_field):
            from drive_agent.tools.list_drive_changes import ListDriveChanges


class TestListDriveChanges(unittest.TestCase):
    """Test cases for ListDriveChanges tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_drive_service = MagicMock()

        # Sample changes API response
        self.sample_changes_response = {
            'changes': [
                {
                    'time': '2025-01-15T11:00:00Z',
                    'file': {
                        'id': 'file_001',
                        'name': 'document.pdf',
                        'mimeType': 'application/pdf',
                        'size': '1024',
                        'modifiedTime': '2025-01-15T10:30:00Z',
                        'parents': ['folder_123']
                    },
                    'changeType': 'file'
                },
                {
                    'time': '2025-01-15T11:15:00Z',
                    'file': {
                        'id': 'file_002',
                        'name': 'spreadsheet.xlsx',
                        'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'size': '2048',
                        'modifiedTime': '2025-01-15T11:10:00Z',
                        'parents': ['folder_456']
                    },
                    'changeType': 'file'
                }
            ],
            'newStartPageToken': 'new_token_123'
        }

        self.sample_targets = [
            {
                "id": "folder_123",
                "type": "folder",
                "include_patterns": ["*.pdf"],
                "exclude_patterns": ["**/archive/**"]
            },
            {
                "id": "file_789",
                "type": "file",
                "include_patterns": ["*"],
                "exclude_patterns": []
            }
        ]

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_successful_changes_detection(self, mock_build, mock_load_env):
        """Test successful incremental changes detection."""
        mock_build.return_value = self.mock_drive_service

        # Mock changes API response
        changes_request = MagicMock()
        changes_request.execute.return_value = self.sample_changes_response
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        tool = ListDriveChanges(
            targets=self.sample_targets,
            since_timestamp="2025-01-15T10:00:00Z"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(result["total_changes"], 1)
        self.assertGreaterEqual(result["relevant_changes"], 1)
        self.assertIn("new_checkpoint_token", result)

        # Check that changes are properly formatted
        self.assertIn("changes", result)
        changes = result["changes"]
        self.assertGreater(len(changes), 0)

        first_change = changes[0]
        self.assertIn("file_id", first_change)
        self.assertIn("name", first_change)
        self.assertIn("change_time", first_change)
        self.assertIn("change_type", first_change)

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_target_filtering(self, mock_build, mock_load_env):
        """Test filtering changes based on target configuration."""
        mock_build.return_value = self.mock_drive_service

        changes_request = MagicMock()
        changes_request.execute.return_value = self.sample_changes_response
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        # Configure targets to only include PDFs from folder_123
        filtered_targets = [
            {
                "id": "folder_123",
                "type": "folder",
                "include_patterns": ["*.pdf"],
                "exclude_patterns": ["*.xlsx"]
            }
        ]

        tool = ListDriveChanges(
            targets=filtered_targets,
            since_timestamp="2025-01-15T10:00:00Z"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")

        # Should include PDF but exclude XLSX
        changes = result["changes"]
        pdf_changes = [c for c in changes if c["name"] == "document.pdf"]
        xlsx_changes = [c for c in changes if c["name"] == "spreadsheet.xlsx"]

        self.assertGreater(len(pdf_changes), 0)
        self.assertEqual(len(xlsx_changes), 0)

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_timestamp_filtering(self, mock_build, mock_load_env):
        """Test filtering changes based on timestamp."""
        mock_build.return_value = self.mock_drive_service

        changes_request = MagicMock()
        changes_request.execute.return_value = self.sample_changes_response
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        # Use timestamp that's after the first change
        tool = ListDriveChanges(
            targets=self.sample_targets,
            since_timestamp="2025-01-15T11:10:00Z"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")

        # Should only include changes after the timestamp
        changes = result["changes"]
        for change in changes:
            self.assertGreaterEqual(change["change_time"], "2025-01-15T11:10:00Z")

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_page_token_usage(self, mock_build, mock_load_env):
        """Test using page token instead of timestamp."""
        mock_build.return_value = self.mock_drive_service

        changes_request = MagicMock()
        changes_request.execute.return_value = self.sample_changes_response
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        tool = ListDriveChanges(
            targets=self.sample_targets,
            page_token="existing_token_456"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["new_checkpoint_token"], "new_token_123")

        # Verify that page token was used in API call
        call_args = self.mock_drive_service.changes.return_value.list.call_args
        self.assertIn("pageToken", call_args[1])
        self.assertEqual(call_args[1]["pageToken"], "existing_token_456")

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_no_changes_found(self, mock_build, mock_load_env):
        """Test handling when no changes are found."""
        mock_build.return_value = self.mock_drive_service

        empty_response = {
            'changes': [],
            'newStartPageToken': 'same_token_123'
        }

        changes_request = MagicMock()
        changes_request.execute.return_value = empty_response
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        tool = ListDriveChanges(
            targets=self.sample_targets,
            since_timestamp="2025-01-15T12:00:00Z"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_changes"], 0)
        self.assertEqual(result["relevant_changes"], 0)
        self.assertEqual(len(result["changes"]), 0)

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_pagination_handling(self, mock_build, mock_load_env):
        """Test handling of paginated changes responses."""
        mock_build.return_value = self.mock_drive_service

        # Mock paginated responses
        page1_response = {
            'changes': [self.sample_changes_response['changes'][0]],
            'nextPageToken': 'page2_token',
            'newStartPageToken': 'final_token'
        }

        page2_response = {
            'changes': [self.sample_changes_response['changes'][1]],
            'newStartPageToken': 'final_token'
        }

        def mock_changes_paginated(*args, **kwargs):
            request = MagicMock()
            if kwargs.get('pageToken') == 'page2_token':
                request.execute.return_value = page2_response
            else:
                request.execute.return_value = page1_response
            return request

        self.mock_drive_service.changes.return_value.list.side_effect = mock_changes_paginated

        tool = ListDriveChanges(
            targets=self.sample_targets,
            since_timestamp="2025-01-15T10:00:00Z"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_changes"], 2)  # Should include both pages

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_drive_api_error(self, mock_build, mock_load_env):
        """Test handling of Google Drive API errors."""
        mock_build.return_value = self.mock_drive_service

        changes_request = MagicMock()
        changes_request.execute.side_effect = Exception("Changes API error: Invalid token")
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        tool = ListDriveChanges(
            targets=self.sample_targets,
            page_token="invalid_token"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "drive_api_error")
        self.assertIn("Changes API error", result["message"])

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    def test_authentication_error(self, mock_load_env):
        """Test handling of authentication errors."""
        with patch('drive_agent.tools.list_drive_changes.build') as mock_build:
            mock_build.side_effect = Exception("Authentication failed")

            tool = ListDriveChanges(
                targets=self.sample_targets,
                since_timestamp="2025-01-15T10:00:00Z"
            )
            result_str = tool.run()
            result = json.loads(result_str)

        self.assertEqual(result["error"], "authentication_failed")
        self.assertIn("Authentication failed", result["message"])

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_invalid_timestamp_format(self, mock_build, mock_load_env):
        """Test handling of invalid timestamp format."""
        mock_build.return_value = self.mock_drive_service

        tool = ListDriveChanges(
            targets=self.sample_targets,
            since_timestamp="invalid-timestamp"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "invalid_timestamp")
        self.assertIn("Invalid timestamp format", result["message"])

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_change_type_filtering(self, mock_build, mock_load_env):
        """Test filtering of different change types."""
        mock_build.return_value = self.mock_drive_service

        # Mock response with different change types
        mixed_changes_response = {
            'changes': [
                {
                    'time': '2025-01-15T11:00:00Z',
                    'file': {
                        'id': 'file_001',
                        'name': 'document.pdf',
                        'mimeType': 'application/pdf'
                    },
                    'changeType': 'file'
                },
                {
                    'time': '2025-01-15T11:05:00Z',
                    'removed': True,
                    'fileId': 'file_002',
                    'changeType': 'file'
                }
            ],
            'newStartPageToken': 'new_token'
        }

        changes_request = MagicMock()
        changes_request.execute.return_value = mixed_changes_response
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        tool = ListDriveChanges(
            targets=self.sample_targets,
            since_timestamp="2025-01-15T10:00:00Z"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")

        # Check that both additions and removals are handled
        changes = result["changes"]
        self.assertGreater(len(changes), 0)

        # Should have proper change type classification
        for change in changes:
            self.assertIn("change_type", change)
            self.assertIn(change["change_type"], ["file", "removed"])

    @patch('drive_agent.tools.list_drive_changes.load_environment')
    @patch('drive_agent.tools.list_drive_changes.build')
    def test_empty_targets_list(self, mock_build, mock_load_env):
        """Test handling of empty targets list."""
        mock_build.return_value = self.mock_drive_service

        changes_request = MagicMock()
        changes_request.execute.return_value = self.sample_changes_response
        self.mock_drive_service.changes.return_value.list.return_value = changes_request

        tool = ListDriveChanges(
            targets=[],  # Empty targets
            since_timestamp="2025-01-15T10:00:00Z"
        )
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["relevant_changes"], 0)  # No targets to match
        self.assertEqual(len(result["changes"]), 0)


if __name__ == '__main__':
    unittest.main()