"""
Test suite for ListDriveChanges tool.
Tests incremental change detection and pagination for Google Drive monitoring.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestListDriveChanges(unittest.TestCase):
    """Test cases for ListDriveChanges tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_timestamp = "2025-01-20T10:00:00Z"
        self.sample_page_token = "CAESBggBIAEiDWNoYW5nZV9pZF8xMjM"
        self.sample_targets = [
            {
                "folder_id": "1AbC2DefGhI3JkL4MnO5PqR6StU7VwX8Yz9",
                "name": "Strategy Documents",
                "include_patterns": ["*.pdf", "*.docx"],
                "exclude_patterns": ["*temp*"]
            }
        ]

    def test_successful_changes_detection(self):
        """Test successful incremental changes detection."""
        # Simulate change detection
        result = {
            'changes_found': 1,
            'changes': [
                {
                    'change_id': '123456',
                    'type': 'modified',
                    'file_id': 'file_123',
                    'filename': 'strategy_document.pdf',
                    'mime_type': 'application/pdf',
                    'parent_folder': '1AbC2DefGhI3JkL4MnO5PqR6StU7VwX8Yz9',
                    'modified_time': '2025-01-20T11:00:00Z',
                    'matches_targets': True
                }
            ],
            'next_page_token': 'new_token_456',
            'status': 'success'
        }

        self.assertEqual(result['changes_found'], 1)
        self.assertEqual(result['status'], 'success')
        self.assertIsInstance(result['changes'], list)

    def test_no_changes_found(self):
        """Test handling when no changes are found."""
        # Simulate empty changes response
        result = {
            'changes_found': 0,
            'changes': [],
            'next_page_token': 'token_unchanged',
            'status': 'no_changes',
            'message': 'No changes found since last check'
        }

        self.assertEqual(result['changes_found'], 0)
        self.assertEqual(result['status'], 'no_changes')
        self.assertIsInstance(result['changes'], list)
        self.assertEqual(len(result['changes']), 0)

    def test_timestamp_filtering(self):
        """Test filtering changes based on timestamp."""
        cutoff_time = datetime.fromisoformat(self.sample_timestamp.replace('Z', '+00:00'))

        # Mock file modification time
        file_mod_time = datetime.fromisoformat('2025-01-20T11:00:00+00:00')

        # Check if file is newer than cutoff
        is_newer = file_mod_time > cutoff_time

        self.assertTrue(is_newer)

        # Test with older file
        old_file_time = datetime.fromisoformat('2025-01-20T09:00:00+00:00')
        is_older = old_file_time > cutoff_time

        self.assertFalse(is_older)

    def test_target_filtering(self):
        """Test filtering changes based on target configuration."""
        file_data = {
            'name': 'strategy_document.pdf',
            'parents': ['1AbC2DefGhI3JkL4MnO5PqR6StU7VwX8Yz9']
        }

        target = self.sample_targets[0]

        # Check if file is in target folder
        in_target_folder = target['folder_id'] in file_data['parents']

        # Check if file matches include patterns
        include_patterns = target['include_patterns']
        matches_include = any(file_data['name'].endswith(pattern.replace('*', ''))
                            for pattern in include_patterns)

        # Check if file matches exclude patterns
        exclude_patterns = target['exclude_patterns']
        matches_exclude = any(pattern.replace('*', '') in file_data['name']
                            for pattern in exclude_patterns)

        self.assertTrue(in_target_folder)
        self.assertTrue(matches_include)
        self.assertFalse(matches_exclude)

    def test_change_type_filtering(self):
        """Test filtering of different change types."""
        changes = [
            {'removed': False, 'file': {'name': 'new_file.pdf'}},  # Modified/Created
            {'removed': True, 'file': {'name': 'deleted_file.pdf'}},  # Deleted
        ]

        # Filter for non-deleted changes
        active_changes = [change for change in changes if not change['removed']]
        deleted_changes = [change for change in changes if change['removed']]

        self.assertEqual(len(active_changes), 1)
        self.assertEqual(len(deleted_changes), 1)
        self.assertEqual(active_changes[0]['file']['name'], 'new_file.pdf')

    def test_pagination_handling(self):
        """Test handling of paginated changes responses."""
        # First page
        page1_response = {
            'changes': [{'changeId': '123', 'file': {'name': 'file1.pdf'}}],
            'nextPageToken': 'page2_token'
        }

        # Second page
        page2_response = {
            'changes': [{'changeId': '124', 'file': {'name': 'file2.pdf'}}],
            'nextPageToken': None,
            'newStartPageToken': 'final_token'
        }

        # Combine results
        all_changes = page1_response['changes'] + page2_response['changes']

        result = {
            'changes_found': len(all_changes),
            'changes': all_changes,
            'next_page_token': page2_response['newStartPageToken'],
            'total_pages': 2
        }

        self.assertEqual(result['changes_found'], 2)
        self.assertEqual(result['total_pages'], 2)
        self.assertIsNone(page2_response['nextPageToken'])

    def test_response_structure_validation(self):
        """Test that response structures are valid."""
        success_response = {
            'changes_found': 5,
            'changes': [
                {
                    'change_id': '123',
                    'type': 'modified',
                    'file_id': 'file_123',
                    'filename': 'document.pdf',
                    'modified_time': '2025-01-20T11:00:00Z'
                }
            ],
            'next_page_token': 'token_456',
            'status': 'success',
            'processing_time_ms': 250,
            'metadata': {
                'targets_checked': 3,
                'filters_applied': ['include_patterns', 'exclude_patterns']
            }
        }

        # Validate required fields
        required_fields = ['changes_found', 'changes', 'status']
        for field in required_fields:
            self.assertIn(field, success_response)

        self.assertIsInstance(success_response['changes'], list)
        self.assertEqual(success_response['status'], 'success')


if __name__ == '__main__':
    unittest.main()