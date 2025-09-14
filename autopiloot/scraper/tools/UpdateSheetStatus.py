"""
UpdateSheetStatus tool for updating sheet row status on errors.
Updates the status and notes of a sheet row when processing fails.
"""

import os
import sys
from typing import Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from sheets import SheetRow, create_error_row_values, get_update_range
from loader import load_app_config
from env_loader import get_google_credentials_path

# Google Sheets API
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

load_dotenv()


class UpdateSheetStatus(BaseTool):
    """
    Updates the status and notes of a sheet row when processing fails.
    
    This tool:
    1. Updates the row status to "error"
    2. Sets the notes field with the error message
    3. Sets the processed_at timestamp
    4. Keeps the row in the main sheet for manual review
    """
    
    sheet_id: str = Field(
        ..., 
        description="Google Sheet ID containing the row to update"
    )
    
    row_index: int = Field(
        ...,
        description="1-based row index in the main sheet to update"
    )
    
    error_message: str = Field(
        ...,
        description="Error message to record in the notes field"
    )
    
    source_url: str = Field(
        ...,
        description="Original URL from the sheet row"
    )

    def run(self) -> str:
        """
        Update a sheet row with error status and message.
        
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
            
            # Create SheetRow object for error values
            sheet_row = SheetRow(
                url=self.source_url,
                status="pending",  # Original status, will be changed to "error"
                notes=None,
                processed_at=None
            )
            
            # Get error values
            error_values = create_error_row_values(sheet_row, self.error_message)
            
            # Update the row in the main sheet
            update_range = get_update_range(self.row_index)
            sheet.values().update(
                spreadsheetId=self.sheet_id,
                range=update_range,
                valueInputOption='RAW',
                body={'values': [error_values]}
            ).execute()
            
            result = {
                "success": True,
                "updated_row": {
                    "row_index": self.row_index,
                    "update_range": update_range,
                    "new_status": "error",
                    "error_message": self.error_message,
                    "processed_at": error_values[3]
                },
                "message": f"Successfully updated row {self.row_index} with error status"
            }
            
            return str(result).replace("'", '"')
            
        except Exception as e:
            error_msg = f"Failed to update sheet row status: {str(e)}"
            result = {
                "success": False,
                "error": error_msg,
                "row_index": self.row_index
            }
            return str(result).replace("'", '"')


if __name__ == "__main__":
    # Test the tool (with dummy data)
    tool = UpdateSheetStatus(
        sheet_id="test_sheet_id",
        row_index=2,
        error_message="Failed to extract video URLs",
        source_url="https://example.com/page"
    )
    print("UpdateSheetStatus tool created successfully")
    print("Note: Run with valid credentials and sheet ID to test fully")
