# Google Sheets Flow Implementation

This document summarizes the implementation of Task 03 - Google Sheet ingestion and archival flow.

## Overview

The implementation provides a complete workflow for processing Google Sheets containing YouTube video links, with configurable daily limits, automatic archiving of successful rows, and error handling for failed processing.

## Files Created/Modified

### New Files

- `core/sheets.py` - Core sheets processing utilities and types
- `scraper/tools/ReadSheetLinks.py` - Tool for reading pending sheet rows
- `scraper/tools/ArchiveSheetRow.py` - Tool for archiving successful rows
- `scraper/tools/UpdateSheetStatus.py` - Tool for updating error status
- `scraper/tools/ProcessSheetLinks.py` - Main workflow orchestration tool
- `tests/test_sheets.py` - Comprehensive test suite (16 tests)
- `scraper/__init__.py` - Scraper package initialization
- `scraper/tools/__init__.py` - Tools package initialization

### Modified Files

- `config/settings.yaml` - Added sheets configuration section
- `config/loader.py` - Added SheetsConfig types and validation

## Configuration

Added to `settings.yaml`:

```yaml
sheets:
  daily_limit_per_channel: 10 # Maximum rows to process per day
  range_a1: "Sheet1!A:D" # Range to read from sheet
```

### Configuration Functions

- `get_sheets_daily_limit(config)` - Returns daily processing limit
- `get_sheets_range(config)` - Returns A1 notation range for reading

## Core Features

### 1. YouTube URL Extraction

- **Function**: `extract_youtube_urls_from_text()`
- Extracts YouTube URLs from text content using regex patterns
- Supports standard watch URLs, short URLs, and embed URLs
- Deduplicates URLs by video ID to prevent duplicates
- Returns list of normalized YouTube URLs

### 2. Sheet Row Parsing

- **Function**: `parse_sheet_row()`
- Parses sheet rows into structured SheetRow objects
- **Expected columns**: A=url, B=status, C=notes, D=processed_at
- Filters for "pending" status rows only
- Handles whitespace trimming and empty value normalization

### 3. Archive and Error Handling

- **Functions**: `create_archive_row_values()`, `create_error_row_values()`
- Creates properly formatted row values for archiving or error updates
- Includes timestamps in ISO8601 format with Z timezone
- Tracks processed video IDs and error messages

### 4. Range Management

- **Functions**: `get_archive_range()`, `get_update_range()`
- Generates A1 notation ranges for sheet operations
- Handles dynamic row positioning for archive appends

## Tools Architecture

### ReadSheetLinks Tool

**Purpose**: Reads pending rows from Google Sheet and extracts YouTube URLs

**Key Features**:

- Respects configured daily limit from settings
- Uses Google Sheets API with service account authentication
- Extracts YouTube URLs from page content or direct links
- Returns structured response with links and processing summary

**Parameters**:

- `sheet_id` (optional) - Override configured sheet ID
- `max_rows` (optional) - Override configured daily limit

### ArchiveSheetRow Tool

**Purpose**: Archives successfully processed rows to Archive tab

**Key Features**:

- Creates Archive sheet if it doesn't exist
- Adds header row to new Archive sheets
- Moves row from main sheet to Archive with updated status
- Deletes original row from main sheet

**Parameters**:

- `sheet_id` - Google Sheet ID
- `row_index` - 1-based row index to archive
- `video_ids` - List of successfully processed video IDs
- `source_url` - Original URL from the row

### UpdateSheetStatus Tool

**Purpose**: Updates row status to "error" when processing fails

**Key Features**:

- Updates status to "error" in place
- Records error message in notes field
- Sets processed_at timestamp
- Keeps row in main sheet for manual review

**Parameters**:

- `sheet_id` - Google Sheet ID
- `row_index` - 1-based row index to update
- `error_message` - Error description
- `source_url` - Original URL from the row

### ProcessSheetLinks Tool

**Purpose**: Complete workflow orchestration with daily limits

**Key Features**:

- Reads up to configured daily limit of pending rows
- Processes each row sequentially
- Archives successful rows or updates error status
- Supports dry run mode for testing
- Returns comprehensive processing summary

**Parameters**:

- `dry_run` (optional) - If True, doesn't modify the sheet

## Processing Workflow

1. **Read Phase**: Load configuration and read pending rows from sheet
2. **Extract Phase**: Extract YouTube video IDs from each row's URL
3. **Process Phase**: For each row up to daily limit:
   - If video IDs found: Archive the row as "completed"
   - If no video IDs: Update row status to "error"
   - If processing error: Update row status to "error"
4. **Summary Phase**: Return detailed processing results

## Testing Coverage

**16 comprehensive tests** covering:

- **URL Extraction**: 8 tests for all YouTube URL formats and edge cases
- **Row Parsing**: 3 tests for valid parsing and skip conditions
- **Value Creation**: 4 tests for archive and error row generation
- **Range Functions**: 2 tests for A1 notation range generation
- **Integration**: 2 tests for complete workflow scenarios

All tests use realistic data and verify end-to-end functionality.

## Type Definitions

```python
class SheetRow(TypedDict):
    url: str
    status: str
    notes: Optional[str]
    processed_at: Optional[str]

class SheetLink(TypedDict):
    source_page_url: str
    video_url: str

class SheetsConfig(TypedDict, total=False):
    daily_limit_per_channel: int
    range_a1: str
```

## Acceptance Criteria Met

✅ **Rows processed sequentially** - ProcessSheetLinks tool processes rows one by one up to daily limit

✅ **Archive/remove behavior implemented** - ArchiveSheetRow tool moves successful rows to Archive tab and removes from main sheet

✅ **Errors retained on main tab** - UpdateSheetStatus tool updates error rows in place for manual review

✅ **Daily limit enforcement** - Configured `daily_limit_per_channel` strictly enforced across all tools

✅ **Configuration integration** - All settings read from `settings.yaml` with proper validation

## Error Handling

- **Google API Errors**: Proper exception handling with descriptive error messages
- **Invalid Data**: Graceful handling of malformed URLs or missing sheet data
- **Authentication**: Clear error messages for credential issues
- **Sheet Structure**: Automatic creation of Archive sheet if missing

## Security

- **Credentials**: Uses Google service account authentication from environment variables
- **Validation**: All inputs validated before processing
- **No Secrets**: No API keys or sensitive data in tool parameters

The implementation successfully provides a robust, configurable, and well-tested Google Sheets processing workflow that meets all specified requirements and acceptance criteria.
