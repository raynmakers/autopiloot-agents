import os
import json
from typing import Dict, Any, List
from googleapiclient.discovery import build
from google.oauth2 import service_account
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class RemoveSheetRow(BaseTool):
    def __init__(self):
        super().__init__()
        self.sheets = self._initialize_sheets_client()
    
    def _validate_env_vars(self):
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH")
    
    def _initialize_sheets_client(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=credentials)
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        sheet_id = request.get('sheet_id', '')
        row_indices = request.get('row_indices', [])
        
        if not sheet_id:
            raise ValueError("sheet_id is required")
        if not row_indices:
            raise ValueError("row_indices is required and must not be empty")
        
        try:
            spreadsheet = self.sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
            sheet_name = spreadsheet['sheets'][0]['properties']['title']
            sheet_grid_id = spreadsheet['sheets'][0]['properties']['sheetId']
            
            row_indices_sorted = sorted(row_indices, reverse=True)
            
            requests = []
            for row_index in row_indices_sorted:
                requests.append({
                    'deleteDimension': {
                        'range': {
                            'sheetId': sheet_grid_id,
                            'dimension': 'ROWS',
                            'startIndex': row_index,
                            'endIndex': row_index + 1
                        }
                    }
                })
            
            if requests:
                body = {'requests': requests}
                response = self.sheets.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body=body
                ).execute()
                
                return {"result": f"Successfully removed {len(row_indices)} rows"}
            else:
                return {"result": "No rows to remove"}
            
        except Exception as e:
            raise RuntimeError(f"Failed to remove sheet rows: {str(e)}")


if __name__ == "__main__":
    tool = RemoveSheetRow()
    
    test_request = {
        "sheet_id": os.getenv("TEST_SHEET_ID", "placeholder_sheet_id"),
        "row_indices": [2, 4, 6]
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {result['result']}")
    except Exception as e:
        print(f"Error: {str(e)}")