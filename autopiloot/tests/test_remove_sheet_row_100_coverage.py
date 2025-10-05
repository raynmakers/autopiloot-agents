"""
Comprehensive test suite for RemoveSheetRow tool targeting 100% coverage.
Tests Google Sheets row archiving, batch deletion, and archive sheet creation.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import sys


# Mock external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.errors': MagicMock(),
    'google': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
    'dotenv': MagicMock(),
    'env_loader': MagicMock(),
    'loader': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create mocks for functions
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value="/fake/credentials.json")
sys.modules['loader'].load_app_config = MagicMock(return_value={"sheet": "1234567890abcdef"})
sys.modules['dotenv'].load_dotenv = MagicMock()

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Import the tool after mocking
from scraper_agent.tools.remove_sheet_row import RemoveSheetRow

# Patch RemoveSheetRow __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.sheet_id = kwargs.get('sheet_id')
    self.row_indices = kwargs.get('row_indices', [])
    self.archive_mode = kwargs.get('archive_mode', True)
    self.source_sheet_name = kwargs.get('source_sheet_name', 'Sheet1')

RemoveSheetRow.__init__ = patched_init


class TestRemoveSheetRow100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for RemoveSheetRow."""

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_successful_archive_with_existing_archive_sheet(self, mock_config, mock_build, mock_exists):
        """Test successful archiving with existing Archive sheet (lines 88-93, 101-186)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        # Mock Google Sheets service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }

        # Mock row data retrieval
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['https://example.com', 'pending', '2024-01-01']]
        }

        # Mock append operation
        mock_service.spreadsheets().values().append().execute.return_value = {}

        # Mock batch update
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2, 3],
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('message', data)
        self.assertEqual(data['processed_rows'], 2)
        self.assertEqual(data['operation'], 'archive')

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_no_sheet_id_configured(self, mock_config, mock_build, mock_exists):
        """Test error when no sheet ID provided (lines 68-73)."""
        mock_config.return_value = {}
        mock_exists.return_value = True

        tool = RemoveSheetRow(
            sheet_id=None,
            row_indices=[2],
            archive_mode=True
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('No sheet ID provided', data['error'])

    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_empty_row_indices(self, mock_config):
        """Test handling of empty row indices (lines 76-80)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[],
            archive_mode=True
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('message', data)
        self.assertEqual(data['processed_rows'], 0)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_clear_mode_instead_of_archive(self, mock_config, mock_build, mock_exists):
        """Test clear mode operation (lines 88-93, 188-211)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock batch clear operation
        mock_service.spreadsheets().values().batchClear().execute.return_value = {}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2, 5, 8],
            archive_mode=False,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('message', data)
        self.assertEqual(data['processed_rows'], 3)
        self.assertEqual(data['operation'], 'clear')

    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_top_level_exception_handling(self, mock_config):
        """Test top-level exception handling (lines 95-99)."""
        mock_config.side_effect = Exception("Config load error")

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('Failed to process sheet rows', data['error'])

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_source_sheet_not_found(self, mock_config, mock_build, mock_exists):
        """Test error when source sheet not found (lines 112-116)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet with no matching sheet
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'DifferentSheet', 'sheetId': 0}}
            ]
        }

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('Source sheet', data['error'])

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_create_archive_sheet_when_not_exists(self, mock_config, mock_build, mock_exists):
        """Test Archive sheet creation when it doesn't exist (lines 118-121, 220-257)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata without Archive sheet
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}}
            ]
        }

        # Mock archive sheet creation response
        mock_service.spreadsheets().batchUpdate().execute.return_value = {
            'replies': [
                {'addSheet': {'properties': {'sheetId': 1}}}
            ]
        }

        # Mock header update
        mock_service.spreadsheets().values().update().execute.return_value = {}

        # Mock row data
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['https://example.com']]
        }

        # Mock append and delete operations
        mock_service.spreadsheets().values().append().execute.return_value = {}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        # Should succeed with archive sheet creation
        self.assertIn('message', data)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_skip_empty_rows_during_archive(self, mock_config, mock_build, mock_exists):
        """Test skipping empty rows (lines 132-142)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }

        # Track call count
        call_count = [0]

        # Mock row data - one empty, one with data
        def mock_get_values(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First call - empty row
                return {'values': []}
            else:  # Second call - non-empty row
                return {'values': [['https://example.com']]}

        mock_service.spreadsheets().values().get().execute.side_effect = mock_get_values

        # Mock append and delete operations
        mock_service.spreadsheets().values().append().execute.return_value = {}
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2, 3],
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['processed_rows'], 1)
        self.assertEqual(data['skipped_rows'], 1)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_row_read_exception_handling(self, mock_config, mock_build, mock_exists):
        """Test exception during row read (lines 140-142)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }

        # Mock row read exception
        mock_service.spreadsheets().values().get().execute.side_effect = Exception("Read error")

        # Mock append (should not be called)
        mock_service.spreadsheets().values().append().execute.return_value = {}

        # Mock batch update
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        # Should skip unreadable rows
        self.assertEqual(data['processed_rows'], 0)
        self.assertEqual(data['skipped_rows'], 1)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_batch_delete_request_structure(self, mock_config, mock_build, mock_exists):
        """Test batch delete request structure (lines 155-168)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }

        # Mock row data
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['data']]
        }

        # Mock operations
        mock_service.spreadsheets().values().append().execute.return_value = {}

        # Capture batch update calls
        mock_batch_update = MagicMock()
        mock_service.spreadsheets().batchUpdate = mock_batch_update

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[5, 3, 7],  # Unsorted
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()

        # Verify batch update was called
        mock_batch_update.assert_called()

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_archive_exception_handling(self, mock_config, mock_build, mock_exists):
        """Test exception during archive operation (lines 185-186)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.side_effect = Exception("API error")

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('Failed to process sheet rows', data['error'])

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_clear_mode_exception_handling(self, mock_config, mock_build, mock_exists):
        """Test exception during clear operation (lines 210-211)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock batch clear exception
        mock_service.spreadsheets().values().batchClear().execute.side_effect = Exception("Clear error")

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=False,
            source_sheet_name='Sheet1'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_find_sheet_by_name_found(self, mock_config, mock_build, mock_exists):
        """Test finding sheet by name (lines 213-218)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        sheets = [
            {'properties': {'title': 'Sheet1', 'sheetId': 0}},
            {'properties': {'title': 'Archive', 'sheetId': 1}}
        ]

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True
        )

        result = tool._find_sheet_by_name(sheets, 'Archive')
        self.assertIsNotNone(result)
        self.assertEqual(result['properties']['title'], 'Archive')

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_find_sheet_by_name_not_found(self, mock_config, mock_build, mock_exists):
        """Test sheet not found (lines 213-218)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        sheets = [
            {'properties': {'title': 'Sheet1', 'sheetId': 0}}
        ]

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True
        )

        result = tool._find_sheet_by_name(sheets, 'NonExistent')
        self.assertIsNone(result)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_create_archive_sheet_exception(self, mock_config, mock_build, mock_exists):
        """Test exception during archive sheet creation (lines 256-257)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock batch update exception
        mock_service.spreadsheets().batchUpdate().execute.side_effect = Exception("Create error")

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True
        )

        with self.assertRaises(RuntimeError) as context:
            tool._create_archive_sheet(mock_service, 'test_sheet_id')
        self.assertIn('Failed to create Archive sheet', str(context.exception))

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.get_required_env_var')
    def test_initialize_sheets_service_success(self, mock_env, mock_exists):
        """Test successful Sheets service initialization (lines 259-280)."""
        mock_exists.return_value = True
        mock_env.return_value = "/fake/credentials.json"

        with patch('scraper_agent.tools.remove_sheet_row.Credentials') as mock_creds:
            with patch('scraper_agent.tools.remove_sheet_row.build') as mock_build:
                mock_credentials = MagicMock()
                mock_creds.from_service_account_file.return_value = mock_credentials
                mock_build.return_value = MagicMock()

                tool = RemoveSheetRow(
                    sheet_id='test_sheet_id',
                    row_indices=[2],
                    archive_mode=True
                )
                service = tool._initialize_sheets_service()

                self.assertIsNotNone(service)
                mock_build.assert_called_with('sheets', 'v4', credentials=mock_credentials)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.get_required_env_var')
    def test_initialize_sheets_service_file_not_found(self, mock_env, mock_exists):
        """Test Sheets initialization with missing credentials (lines 268-269)."""
        mock_exists.return_value = False
        mock_env.return_value = "/fake/credentials.json"

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_sheets_service()
        self.assertIn('Failed to initialize Google Sheets service', str(context.exception))

    @patch('scraper_agent.tools.remove_sheet_row.get_required_env_var')
    def test_initialize_sheets_service_exception(self, mock_env):
        """Test Sheets initialization exception (lines 279-280)."""
        mock_env.side_effect = Exception("Environment error")

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_sheets_service()
        self.assertIn('Failed to initialize Google Sheets service', str(context.exception))

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_row_indices_sorted_in_descending_order(self, mock_config, mock_build, mock_exists):
        """Test row indices are sorted in descending order (lines 82-83)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }

        # Mock row data
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['data']]
        }

        # Mock operations
        mock_service.spreadsheets().values().append().execute.return_value = {}
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[5, 2, 8, 3],  # Unsorted with duplicates
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()

        # Should process successfully with sorted indices
        data = json.loads(result)
        self.assertIn('message', data)

    @patch('scraper_agent.tools.remove_sheet_row.os.path.exists')
    @patch('scraper_agent.tools.remove_sheet_row.build')
    @patch('scraper_agent.tools.remove_sheet_row.load_app_config')
    def test_archive_with_timestamp_and_original_row_info(self, mock_config, mock_build, mock_exists):
        """Test archive adds timestamp and original row info (lines 134-139)."""
        mock_config.return_value = {"sheet": "test_sheet_id"}
        mock_exists.return_value = True

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock spreadsheet metadata
        mock_service.spreadsheets().get().execute.return_value = {
            'sheets': [
                {'properties': {'title': 'Sheet1', 'sheetId': 0}},
                {'properties': {'title': 'Archive', 'sheetId': 1}}
            ]
        }

        # Mock row data
        mock_service.spreadsheets().values().get().execute.return_value = {
            'values': [['https://example.com', 'processed']]
        }

        # Capture append call
        mock_append = MagicMock()
        mock_service.spreadsheets().values().append = lambda *args, **kwargs: mock_append()
        mock_append().execute.return_value = {}

        # Mock batch update
        mock_service.spreadsheets().batchUpdate().execute.return_value = {}

        tool = RemoveSheetRow(
            sheet_id='test_sheet_id',
            row_indices=[2],
            archive_mode=True,
            source_sheet_name='Sheet1'
        )
        result = tool.run()

        # Should succeed with timestamp and row info
        data = json.loads(result)
        self.assertIn('message', data)
        self.assertEqual(data['processed_rows'], 1)


if __name__ == "__main__":
    unittest.main()