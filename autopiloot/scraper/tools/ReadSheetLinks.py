"""
ReadSheetLinks tool for reading and parsing Google Sheet rows.
Reads pending rows from a Google Sheet and extracts YouTube URLs.
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

from sheets import (
    SheetRow, SheetLink, ReadSheetLinksResponse, 
    parse_sheet_row, extract_youtube_urls_from_text
)
from loader import load_app_config, get_sheets_daily_limit, get_sheets_range
from env_loader import get_google_credentials_path

# Google Sheets API
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

load_dotenv()


class ReadSheetLinks(BaseTool):
    """
    Reads pending rows from a Google Sheet and extracts YouTube URLs from them.
    
    This tool:
    1. Reads up to the configured daily limit of pending rows from the sheet
    2. Extracts YouTube URLs from the content of each row
    3. Returns structured data for further processing
    """
    
    sheet_id: Optional[str] = Field(
        None, 
        description="Google Sheet ID to read from. If not provided, uses the configured sheet ID."
    )
    
    max_rows: Optional[int] = Field(
        None,
        description="Maximum number of rows to process. If not provided, uses the configured daily limit."
    )

    def run(self) -> str:
        """
        Read pending sheet rows and extract YouTube URLs.
        
        Returns:
            JSON string containing the extracted sheet links and processing summary
        """
        try:
            # Load configuration
            config = load_app_config()
            
            # Use provided values or defaults from config
            sheet_id = self.sheet_id or config.get("sheet")
            max_rows = self.max_rows or get_sheets_daily_limit(config)
            range_a1 = get_sheets_range(config)
            
            if not sheet_id:
                return '{"error": "No sheet ID configured or provided"}'
            
            # Set up Google Sheets API
            credentials_path = get_google_credentials_path()
            credentials = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            service = build('sheets', 'v4', credentials=credentials)
            sheet = service.spreadsheets()
            
            # Read sheet data
            result = sheet.values().get(
                spreadsheetId=sheet_id,
                range=range_a1
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return '{"items": [], "summary": {"total_rows": 0, "processed_rows": 0, "pending_rows": 0}}'
            
            # Process rows
            sheet_links = []
            processed_count = 0
            pending_count = 0
            
            for i, row_values in enumerate(values):
                row_index = i + 1  # 1-based index
                
                # Parse the row
                sheet_row = parse_sheet_row(row_values, row_index)
                if not sheet_row:
                    continue
                
                pending_count += 1
                
                # Check if we've reached the limit
                if processed_count >= max_rows:
                    break
                
                # Extract YouTube URLs from the URL content
                source_url = sheet_row["url"]
                
                # If the URL itself is a YouTube URL, use it directly
                if "youtube.com" in source_url or "youtu.be" in source_url:
                    youtube_urls = [source_url]
                else:
                    # TODO: In a full implementation, we would fetch the page content
                    # and extract YouTube URLs from it. For now, we'll just check if
                    # the URL contains obvious YouTube links in the text
                    youtube_urls = extract_youtube_urls_from_text(source_url)
                
                # Create sheet links for each YouTube URL found
                for video_url in youtube_urls:
                    sheet_link = SheetLink(
                        source_page_url=source_url,
                        video_url=video_url
                    )
                    sheet_links.append(sheet_link)
                
                processed_count += 1
            
            # Prepare response
            response = ReadSheetLinksResponse(items=sheet_links)
            
            # Add summary information
            summary = {
                "total_rows": len(values),
                "processed_rows": processed_count, 
                "pending_rows": pending_count,
                "youtube_urls_found": len(sheet_links),
                "max_rows_limit": max_rows,
                "sheet_id": sheet_id,
                "range": range_a1
            }
            
            return f'{{"items": {response["items"]}, "summary": {summary}}}'
            
        except Exception as e:
            error_msg = f"Failed to read sheet links: {str(e)}"
            return f'{{"error": "{error_msg}"}}'


if __name__ == "__main__":
    # Test the tool
    tool = ReadSheetLinks()
    result = tool.run()
    print("ReadSheetLinks result:")
    print(result)
