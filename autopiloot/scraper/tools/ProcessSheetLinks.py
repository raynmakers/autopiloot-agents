"""
ProcessSheetLinks tool for the complete Google Sheet processing workflow.
Orchestrates reading, processing, and archiving sheet rows according to daily limits.
"""

import os
import sys
import json
from typing import List, Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from sheets import extract_youtube_urls_from_text
from idempotency import extract_video_id_from_url
from loader import load_app_config, get_sheets_daily_limit
from env_loader import get_google_credentials_path

# Google Sheets API
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# Import other tools
from ReadSheetLinks import ReadSheetLinks
from ArchiveSheetRow import ArchiveSheetRow
from UpdateSheetStatus import UpdateSheetStatus

load_dotenv()


class ProcessSheetLinks(BaseTool):
    """
    Complete workflow for processing Google Sheet links with daily limits.
    
    This tool:
    1. Reads pending rows from the configured Google Sheet
    2. Extracts YouTube URLs from each row
    3. Processes up to the configured daily limit
    4. Archives successful rows or marks errors
    5. Returns a summary of processing results
    """
    
    dry_run: bool = Field(
        False,
        description="If True, processes data but doesn't update the sheet (for testing)"
    )

    def run(self) -> str:
        """
        Process sheet links according to configured daily limits.
        
        Returns:
            JSON string with processing summary and results
        """
        try:
            # Load configuration
            config = load_app_config()
            sheet_id = config.get("sheet")
            daily_limit = get_sheets_daily_limit(config)
            
            if not sheet_id:
                return '{"error": "No sheet ID configured"}'
            
            # Step 1: Read sheet links
            reader = ReadSheetLinks()
            read_result = reader.run()
            read_data = json.loads(read_result)
            
            if "error" in read_data:
                return read_result
            
            sheet_links = read_data.get("items", [])
            summary = read_data.get("summary", {})
            
            # Step 2: Process each row up to the daily limit
            processed_rows = []
            archived_count = 0
            error_count = 0
            video_ids_processed = []
            
            # Group links by source URL to process rows
            rows_by_source = {}
            for link in sheet_links:
                source_url = link["source_page_url"]
                if source_url not in rows_by_source:
                    rows_by_source[source_url] = []
                rows_by_source[source_url].append(link["video_url"])
            
            # Process rows up to daily limit
            row_index = 2  # Start from row 2 (skip header)
            for source_url, video_urls in rows_by_source.items():
                if len(processed_rows) >= daily_limit:
                    break
                
                try:
                    # Extract video IDs
                    video_ids = []
                    for video_url in video_urls:
                        video_id = extract_video_id_from_url(video_url)
                        if video_id and video_id not in video_ids:
                            video_ids.append(video_id)
                    
                    if video_ids:
                        # Success - archive the row
                        if not self.dry_run:
                            archiver = ArchiveSheetRow(
                                sheet_id=sheet_id,
                                row_index=row_index,
                                video_ids=video_ids,
                                source_url=source_url
                            )
                            archive_result = archiver.run()
                            archive_data = json.loads(archive_result)
                            
                            if archive_data.get("success"):
                                archived_count += 1
                                video_ids_processed.extend(video_ids)
                            else:
                                error_count += 1
                                processed_rows.append({
                                    "source_url": source_url,
                                    "status": "archive_failed",
                                    "error": archive_data.get("error", "Unknown error")
                                })
                        else:
                            # Dry run - just count
                            archived_count += 1
                            video_ids_processed.extend(video_ids)
                        
                        processed_rows.append({
                            "source_url": source_url,
                            "status": "success",
                            "video_ids": video_ids,
                            "video_count": len(video_ids)
                        })
                    else:
                        # No valid video IDs found - mark as error
                        error_message = "No valid YouTube video IDs found"
                        
                        if not self.dry_run:
                            updater = UpdateSheetStatus(
                                sheet_id=sheet_id,
                                row_index=row_index,
                                error_message=error_message,
                                source_url=source_url
                            )
                            update_result = updater.run()
                            update_data = json.loads(update_result)
                            
                            if update_data.get("success"):
                                error_count += 1
                            
                        processed_rows.append({
                            "source_url": source_url,
                            "status": "error",
                            "error": error_message
                        })
                
                except Exception as e:
                    # Processing error - mark as error
                    error_message = f"Processing error: {str(e)}"
                    
                    if not self.dry_run:
                        try:
                            updater = UpdateSheetStatus(
                                sheet_id=sheet_id,
                                row_index=row_index,
                                error_message=error_message,
                                source_url=source_url
                            )
                            updater.run()
                            error_count += 1
                        except:
                            pass  # Don't fail the entire process
                    
                    processed_rows.append({
                        "source_url": source_url,
                        "status": "error",
                        "error": error_message
                    })
                
                row_index += 1
            
            # Step 3: Prepare final summary
            final_summary = {
                "success": True,
                "dry_run": self.dry_run,
                "processing_summary": {
                    "total_rows_available": summary.get("pending_rows", 0),
                    "daily_limit": daily_limit,
                    "rows_processed": len(processed_rows),
                    "archived_count": archived_count,
                    "error_count": error_count,
                    "total_videos_found": len(video_ids_processed),
                    "unique_video_ids": list(set(video_ids_processed))
                },
                "sheet_info": {
                    "sheet_id": sheet_id,
                    "total_sheet_rows": summary.get("total_rows", 0),
                    "youtube_urls_found": summary.get("youtube_urls_found", 0)
                },
                "processed_rows": processed_rows
            }
            
            return json.dumps(final_summary, indent=2)
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": f"Failed to process sheet links: {str(e)}",
                "dry_run": self.dry_run
            }
            return json.dumps(error_result, indent=2)


if __name__ == "__main__":
    # Test the tool in dry run mode
    tool = ProcessSheetLinks(dry_run=True)
    result = tool.run()
    print("ProcessSheetLinks result:")
    print(result)
