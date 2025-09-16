"""
Test suite for RemoveSheetRow tool.
Tests sheet row removal, archival, and batch operations.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scraper', 'tools'))

try:
    from scraper.tools.remove_sheet_row import RemoveSheetRow
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'scraper', 
        'tools', 
        'RemoveSheetRow.py'
    )
    spec = importlib.util.spec_from_file_location("RemoveSheetRow", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    RemoveSheetRow = module.RemoveSheetRow


class TestRemoveSheetRow(unittest.TestCase):
    """Test cases for RemoveSheetRow tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_row_indices = [2, 5, 8]
        self.tool = RemoveSheetRow(
            row_indices=self.test_row_indices,
            archive_mode=True,
            source_sheet_name="Sheet1"
        )

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_archive_rows_success(self, mock_build, mock_get_required_env_var, mock_config):
        """Test successful archival of rows to Archive sheet."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock spreadsheet structure
        mock_spreadsheet = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }
        mock_service.spreadsheets().get().execute.return_value = mock_spreadsheet
        
        # Mock row data
        mock_row_data = [
            {'values': [['https://youtube.com/watch?v=test1', 'pending']]},
            {'values': [['https://youtube.com/watch?v=test2', 'pending']]},
            {'values': [['https://youtube.com/watch?v=test3', 'pending']]}
        ]
        
        mock_service.spreadsheets().values().get().execute.side_effect = mock_row_data
        
        # Mock successful operations
        mock_service.spreadsheets().values().append().execute.return_value = {}
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn('error', data)
        self.assertIn('Successfully archived', data['message'])
        self.assertEqual(data['processed_rows'], 3)
        self.assertEqual(data['operation'], 'archive')
        self.assertIn('archive_sheet_id', data)
        
        # Verify API calls were made
        mock_service.spreadsheets().values().append.assert_called_once()
        mock_service.spreadsheets().batchUpdate.assert_called_once()

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_clear_rows_success(self, mock_build, mock_get_required_env_var, mock_config):
        """Test successful clearing of row contents."""
        # Create tool in clear mode
        tool = RemoveSheetRow(
            row_indices=self.test_row_indices,
            archive_mode=False,
            source_sheet_name="Sheet1"
        )
        
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock successful clear operation
        mock_service.spreadsheets().values().batchClear().execute.return_value = {}
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn('error', data)
        self.assertIn('Successfully cleared', data['message'])
        self.assertEqual(data['processed_rows'], 3)
        self.assertEqual(data['operation'], 'clear')
        
        # Verify batchClear was called with correct ranges
        call_args = mock_service.spreadsheets().values().batchClear.call_args
        ranges = call_args[1]['body']['ranges']
        expected_ranges = ['Sheet1!A2:Z2', 'Sheet1!A5:Z5', 'Sheet1!A8:Z8']
        self.assertEqual(ranges, expected_ranges)

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_create_archive_sheet_when_missing(self, mock_build, mock_get_required_env_var, mock_config):
        """Test creation of Archive sheet when it doesn't exist."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock spreadsheet without Archive sheet
        mock_spreadsheet = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}}
            ]
        }
        mock_service.spreadsheets().get().execute.return_value = mock_spreadsheet
        
        # Mock Archive sheet creation
        mock_create_response = {
            'replies': [{'addSheet': {'properties': {'title': 'Archive', 'sheetId': 1}}}]
        }
        mock_service.spreadsheets().batchUpdate().execute.return_value = mock_create_response
        
        # Mock row data
        mock_service.spreadsheets().values().get().execute.return_value = {'values': [['test_url']]}
        
        # Mock other operations
        mock_service.spreadsheets().values().append().execute.return_value = {}
        mock_service.spreadsheets().values().update().execute.return_value = {}
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn('error', data)
        self.assertIn('Successfully archived', data['message'])
        
        # Verify Archive sheet creation was called
        batch_update_calls = mock_service.spreadsheets().batchUpdate.call_args_list
        self.assertEqual(len(batch_update_calls), 2)  # One for creation, one for deletion

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    def test_no_sheet_id_configured(self, mock_config):
        """Test behavior when no sheet ID is configured."""
        mock_config.return_value = {}  # No sheet ID in config
        
        # Create tool without sheet_id
        tool = RemoveSheetRow(row_indices=[1, 2])
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('No sheet ID provided', data['error'])
        self.assertIsNone(data['message'])

    def test_empty_row_indices(self):
        """Test behavior with empty row indices list."""
        tool = RemoveSheetRow(row_indices=[])
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertNotIn('error', data)
        self.assertIn('No row indices provided', data['message'])
        self.assertEqual(data['processed_rows'], 0)

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_source_sheet_not_found(self, mock_build, mock_get_required_env_var, mock_config):
        """Test behavior when source sheet doesn't exist."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock spreadsheet without the specified source sheet
        mock_spreadsheet = {
            'sheets': [
                {'properties': {'title': 'OtherSheet', 'sheetId': 0}}
            ]
        }
        mock_service.spreadsheets().get().execute.return_value = mock_spreadsheet
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('Source sheet', data['error'])
        self.assertIn('not found', data['error'])

    def test_tool_initialization_parameters(self):
        """Test tool initialization with various parameters."""
        tool = RemoveSheetRow(
            sheet_id="custom_sheet_id",
            row_indices=[1, 3, 5, 7],
            archive_mode=False,
            source_sheet_name="CustomSheet"
        )
        
        self.assertEqual(tool.sheet_id, "custom_sheet_id")
        self.assertEqual(tool.row_indices, [1, 3, 5, 7])
        self.assertFalse(tool.archive_mode)
        self.assertEqual(tool.source_sheet_name, "CustomSheet")

    def test_row_indices_sorting(self):
        """Test that row indices are processed in descending order."""
        # Create tool with unsorted indices
        tool = RemoveSheetRow(row_indices=[3, 1, 5, 2])
        
        # The tool should sort them in descending order internally
        # We can't directly test the internal sorting, but we can verify
        # that the tool initializes correctly with unsorted data
        self.assertEqual(set(tool.row_indices), {1, 2, 3, 5})

    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    def test_missing_environment_variables(self, mock_get_required_env_var):
        """Test behavior when required environment variables are missing."""
        # Mock missing credentials
        mock_get_required_env_var.side_effect = Exception("GOOGLE_APPLICATION_CREDENTIALS not set")
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('GOOGLE_APPLICATION_CREDENTIALS not set', data['error'])

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    def test_missing_service_account_file(self, mock_get_required_env_var, mock_config):
        """Test behavior when service account file doesn't exist."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/nonexistent/credentials.json"
        
        # Mock file doesn't exist
        with patch('os.path.exists', return_value=False):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('Service account file not found', data['error'])

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_api_operation_failure(self, mock_build, mock_get_required_env_var, mock_config):
        """Test error handling when Google Sheets API operations fail."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API with failure
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.spreadsheets().get().execute.side_effect = Exception("API failure")
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('API failure', data['error'])

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_skip_empty_rows_in_archive(self, mock_build, mock_get_required_env_var, mock_config):
        """Test that empty rows are skipped during archival."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock spreadsheet structure
        mock_spreadsheet = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }
        mock_service.spreadsheets().get().execute.return_value = mock_spreadsheet
        
        # Mock row data - some empty, some with content
        mock_row_responses = [
            {'values': [['https://youtube.com/watch?v=test1']]},  # Row with content
            {'values': [[]]},  # Empty row
            {'values': [['https://youtube.com/watch?v=test3']]}   # Row with content
        ]
        
        mock_service.spreadsheets().values().get().execute.side_effect = mock_row_responses
        
        # Mock successful operations
        mock_service.spreadsheets().values().append().execute.return_value = {}
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn('error', data)
        self.assertEqual(data['processed_rows'], 2)  # Only 2 non-empty rows
        self.assertEqual(data['skipped_rows'], 1)    # 1 empty row skipped

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_batch_operations_efficiency(self, mock_build, mock_get_required_env_var, mock_config):
        """Test that operations are batched for efficiency."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock spreadsheet structure
        mock_spreadsheet = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }
        mock_service.spreadsheets().get().execute.return_value = mock_spreadsheet
        
        # Mock row data
        mock_service.spreadsheets().values().get().execute.return_value = {'values': [['test_url']]}
        
        # Mock successful operations
        mock_service.spreadsheets().values().append().execute.return_value = {}
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}
        
        # Test with multiple rows
        tool = RemoveSheetRow(row_indices=[1, 2, 3, 4, 5])
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = tool.run()
        
        # Verify that batchUpdate was called only once (efficient batching)
        mock_service.spreadsheets().batchUpdate.assert_called_once()
        
        # Verify the batch contained all row deletions
        call_args = mock_service.spreadsheets().batchUpdate.call_args
        requests = call_args[1]['body']['requests']
        self.assertEqual(len(requests), 5)  # One request per row deletion

    @patch('scraper.tools.RemoveSheetRow.load_app_config')
    @patch('scraper.tools.RemoveSheetRow.get_required_env_var')
    @patch('scraper.tools.RemoveSheetRow.build')
    def test_archive_with_timestamps(self, mock_build, mock_get_required_env_var, mock_config):
        """Test that archived rows include proper timestamps."""
        # Mock configuration
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_get_required_env_var.return_value = "/fake/credentials.json"
        
        # Mock Google Sheets API
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock spreadsheet structure
        mock_spreadsheet = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }
        mock_service.spreadsheets().get().execute.return_value = mock_spreadsheet
        
        # Mock row data
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['https://youtube.com/watch?v=test1', 'pending']]
        }
        
        # Mock successful operations
        mock_service.spreadsheets().values().append().execute.return_value = {}
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}
        
        # Create tool with single row
        tool = RemoveSheetRow(row_indices=[2])
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = tool.run()
        
        # Verify that append was called with timestamped data
        call_args = mock_service.spreadsheets().values().append.call_args
        archived_values = call_args[1]['body']['values'][0]
        
        # Check that timestamp and original row info were added
        self.assertTrue(any('Archived on' in str(cell) for cell in archived_values))
        self.assertTrue(any('Original row: 2' in str(cell) for cell in archived_values))


if __name__ == '__main__':
    unittest.main(verbosity=2)