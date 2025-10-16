"""
RemoveSheetRow tool for managing processed rows in Google Sheets.
Implements TASK-SCR-0015 with archive-first approach for auditability.
"""

import os
import sys
import json
from typing import List, Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

# Add core and config directories to path
from env_loader import get_required_env_var
from loader import load_app_config



class RemoveSheetRow(BaseTool):
    """
    Removes or archives successfully processed rows from Google Sheets.
    
    Implements archive-first approach by moving processed rows to an 'Archive' 
    tab for auditability, with fallback to row clearing. Handles batch operations
    for multiple rows while maintaining proper index management.
    """
    
    sheet_id: Optional[str] = Field(
        None,
        description="Google Sheet ID to process. If not provided, uses sheet ID from settings.yaml"
    )
    
    row_indices: List[int] = Field(
        ...,
        description="List of 1-based row indices to remove/archive (e.g., [2, 5, 8])"
    )
    
    archive_mode: bool = Field(
        True,
        description="If True, move rows to Archive tab; if False, clear row contents"
    )
    
    source_sheet_name: str = Field(
        "Sheet1",
        description="Name of the source sheet tab containing the rows to process"
    )
    
    def run(self) -> str:
        """
        Removes or archives the specified rows from the Google Sheet.
        
        Returns:
            str: JSON string containing operation results and summary
        """
        try:
            # Load configuration
            config = load_app_config()
            
            # Determine sheet ID
            sheet_id = self.sheet_id or config.get("sheet")
            if not sheet_id:
                return json.dumps({
                    "error": "No sheet ID provided or configured in settings.yaml",
                    "message": None
                })
            
            # Validate row indices
            if not self.row_indices:
                return json.dumps({
                    "message": "No row indices provided - nothing to process",
                    "processed_rows": 0
                })
            
            # Sort row indices in descending order to avoid index shifting issues
            sorted_indices = sorted(set(self.row_indices), reverse=True)
            
            # Initialize Google Sheets API
            service = self._initialize_sheets_service()
            
            if self.archive_mode:
                result = self._archive_rows(service, sheet_id, sorted_indices)
            else:
                result = self._clear_rows(service, sheet_id, sorted_indices)
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to process sheet rows: {str(e)}",
                "message": None
            })
    
    def _archive_rows(self, service, sheet_id: str, row_indices: List[int]) -> dict:
        """Archive rows by moving them to an Archive sheet."""
        try:
            # Get the spreadsheet metadata
            spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            
            # Find source and archive sheets
            source_sheet = self._find_sheet_by_name(sheets, self.source_sheet_name)
            archive_sheet = self._find_sheet_by_name(sheets, "Archive")
            
            if not source_sheet:
                return {
                    "error": f"Source sheet '{self.source_sheet_name}' not found",
                    "message": None
                }
            
            # Create Archive sheet if it doesn't exist
            if not archive_sheet:
                archive_sheet = self._create_archive_sheet(service, sheet_id)
            
            # Read rows to be archived
            rows_to_archive = []
            for row_index in row_indices:
                range_name = f"{self.source_sheet_name}!A{row_index}:Z{row_index}"
                try:
                    result = service.spreadsheets().values().get(
                        spreadsheetId=sheet_id,
                        range=range_name
                    ).execute()
                    
                    values = result.get('values', [])
                    if values and values[0]:  # Only archive non-empty rows
                        # Add timestamp and original row info
                        archived_row = values[0] + [
                            f"Archived on {datetime.now(timezone.utc).isoformat()}",
                            f"Original row: {row_index}"
                        ]
                        rows_to_archive.append(archived_row)
                except Exception as e:
                    # Skip rows that can't be read
                    continue
            
            # Append archived rows to Archive sheet
            if rows_to_archive:
                archive_range = "Archive!A:Z"
                service.spreadsheets().values().append(
                    spreadsheetId=sheet_id,
                    range=archive_range,
                    valueInputOption='RAW',
                    body={'values': rows_to_archive}
                ).execute()
            
            # Clear original rows (process in reverse order to maintain indices)
            requests = []
            for row_index in row_indices:
                requests.append({
                    'deleteRange': {
                        'range': {
                            'sheetId': source_sheet['properties']['sheetId'],
                            'startRowIndex': row_index - 1,  # Convert to 0-based
                            'endRowIndex': row_index,
                            'startColumnIndex': 0,
                            'endColumnIndex': 26  # Up to column Z
                        },
                        'shiftDimension': 'ROWS'
                    }
                })
            
            # Execute batch update
            if requests:
                service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={'requests': requests}
                ).execute()
            
            return {
                "message": f"Successfully archived {len(rows_to_archive)} rows to Archive tab",
                "processed_rows": len(rows_to_archive),
                "skipped_rows": len(row_indices) - len(rows_to_archive),
                "operation": "archive",
                "archive_sheet_id": archive_sheet['properties']['sheetId']
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to archive rows: {str(e)}")
    
    def _clear_rows(self, service, sheet_id: str, row_indices: List[int]) -> dict:
        """Clear row contents without deleting the rows."""
        try:
            # Build ranges to clear
            ranges = []
            for row_index in row_indices:
                ranges.append(f"{self.source_sheet_name}!A{row_index}:Z{row_index}")
            
            # Batch clear the ranges
            if ranges:
                service.spreadsheets().values().batchClear(
                    spreadsheetId=sheet_id,
                    body={'ranges': ranges}
                ).execute()
            
            return {
                "message": f"Successfully cleared {len(ranges)} rows",
                "processed_rows": len(ranges),
                "skipped_rows": 0,
                "operation": "clear"
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to clear rows: {str(e)}")
    
    def _find_sheet_by_name(self, sheets: List[dict], name: str) -> Optional[dict]:
        """Find a sheet by name in the spreadsheet."""
        for sheet in sheets:
            if sheet['properties']['title'] == name:
                return sheet
        return None
    
    def _create_archive_sheet(self, service, sheet_id: str) -> dict:
        """Create an Archive sheet with proper headers."""
        try:
            # Create the Archive sheet
            request = {
                'addSheet': {
                    'properties': {
                        'title': 'Archive',
                        'gridProperties': {
                            'rowCount': 1000,
                            'columnCount': 26
                        }
                    }
                }
            }
            
            response = service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={'requests': [request]}
            ).execute()
            
            # Add headers to the Archive sheet
            headers = [
                "URL", "Status", "Processing Date", "Video ID", "Title", 
                "Archive Timestamp", "Original Row"
            ]
            
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="Archive!A1:G1",
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            
            return response['replies'][0]['addSheet']
            
        except Exception as e:
            raise RuntimeError(f"Failed to create Archive sheet: {str(e)}")
    
    def _initialize_sheets_service(self):
        """Initialize Google Sheets API service."""
        try:
            # Get service account credentials
            credentials_path = get_required_env_var(
                "GOOGLE_APPLICATION_CREDENTIALS", 
                "Google service account credentials file path"
            )
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            service = build('sheets', 'v4', credentials=credentials)
            return service
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Sheets service: {str(e)}")


if __name__ == "__main__":
    # Test the tool with archive mode
    test_tool = RemoveSheetRow(
        row_indices=[2, 3, 5],  # Test with multiple rows
        archive_mode=True,
        source_sheet_name="Sheet1"
    )
    
    try:
        result = test_tool.run()
        print("RemoveSheetRow test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Success: {data['message']}")
            print(f"Processed {data.get('processed_rows', 0)} rows")
            if data.get('skipped_rows', 0) > 0:
                print(f"Skipped {data['skipped_rows']} empty rows")
                
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()