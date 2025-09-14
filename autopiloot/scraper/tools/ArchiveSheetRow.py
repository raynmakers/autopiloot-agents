"""
ArchiveSheetRow tool for moving processed rows to the Archive sheet.
Moves successfully processed rows from the main sheet to an Archive tab.
"""

import os
import sys
from typing import List, Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from sheets import SheetRow, create_archive_row_values, get_archive_range
from loader import load_app_config
from env_loader import get_google_credentials_path

# Google Sheets API
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

load_dotenv()


class ArchiveSheetRow(BaseTool):
    """
    Archives a successfully processed sheet row by moving it to the Archive tab.
    
    This tool:
    1. Adds the row to the Archive sheet with updated status and processed_at timestamp
    2. Removes the row from the main sheet
    3. Handles the case where the Archive sheet doesn't exist by creating it
    """
    
    sheet_id: str = Field(
        ..., 
        description="Google Sheet ID containing the row to archive"
    )
    
    row_index: int = Field(
        ...,
        description="1-based row index in the main sheet to archive"
    )
    
    video_ids: List[str] = Field(
        ...,
        description="List of video IDs that were successfully processed from this row"
    )
    
    source_url: str = Field(
        ...,
        description="Original URL from the sheet row"
    )

    def run(self) -> str:
        """
        Archive a processed sheet row to the Archive tab.
        
        Returns:
            JSON string with success status and details
        """
        try:
            # Set up Google Sheets API
            credentials_path = get_google_credentials_path()
            credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            service = build('sheets', 'v4', credentials=credentials)
            sheet = service.spreadsheets()
            
            # Create SheetRow object for archive values
            sheet_row = SheetRow(
                url=self.source_url,
                status="pending",  # Original status, will be changed to "completed"
                notes=None,
                processed_at=None
            )
            
            # Get archive values
            archive_values = create_archive_row_values(sheet_row, self.video_ids)
            
            # Check if Archive sheet exists, create if not
            try:
                archive_result = sheet.values().get(
                    spreadsheetId=self.sheet_id,
                    range="Archive!A:A"
                ).execute()
                archive_rows = len(archive_result.get('values', []))
            except Exception:
                # Archive sheet doesn't exist, create it
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': 'Archive',
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 4
                            }
                        }
                    }
                }]
                
                sheet.batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={'requests': requests}
                ).execute()
                
                # Add header row
                header_values = [['URL', 'Status', 'Notes', 'Processed At']]
                sheet.values().update(
                    spreadsheetId=self.sheet_id,
                    range="Archive!A1:D1",
                    valueInputOption='RAW',
                    body={'values': header_values}
                ).execute()
                
                archive_rows = 1  # Just the header
            
            # Add to Archive sheet
            archive_range = get_archive_range(archive_rows)
            sheet.values().update(
                spreadsheetId=self.sheet_id,
                range=archive_range,
                valueInputOption='RAW',
                body={'values': [archive_values]}
            ).execute()
            
            # Remove from main sheet by deleting the row
            requests = [{
                'deleteDimension': {
                    'range': {
                        'sheetId': 0,  # Assuming main sheet is the first sheet
                        'dimension': 'ROWS',
                        'startIndex': self.row_index - 1,  # Convert to 0-based
                        'endIndex': self.row_index
                    }
                }
            }]
            
            sheet.batchUpdate(
                spreadsheetId=self.sheet_id,
                body={'requests': requests}
            ).execute()
            
            result = {
                "success": True,
                "archived_row": {
                    "original_row_index": self.row_index,
                    "archive_range": archive_range,
                    "video_ids": self.video_ids,
                    "processed_at": archive_values[3]
                },
                "message": f"Successfully archived row {self.row_index} with {len(self.video_ids)} video(s)"
            }
            
            return str(result).replace("'", '"')
            
        except Exception as e:
            error_msg = f"Failed to archive sheet row: {str(e)}"
            result = {
                "success": False,
                "error": error_msg,
                "row_index": self.row_index
            }
            return str(result).replace("'", '"')


if __name__ == "__main__":
    # Test the tool (with dummy data)
    tool = ArchiveSheetRow(
        sheet_id="test_sheet_id",
        row_index=2,
        video_ids=["dQw4w9WgXcQ"],
        source_url="https://example.com/page"
    )
    print("ArchiveSheetRow tool created successfully")
    print("Note: Run with valid credentials and sheet ID to test fully")
