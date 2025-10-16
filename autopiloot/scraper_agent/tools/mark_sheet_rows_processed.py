"""
MarkSheetRowsProcessed tool for automated cleanup of successfully processed sheet rows.
Queries Firestore for videos from sheets that reached 'summarized' status, then archives them.
"""

import os
import sys
import json
from typing import Dict, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone

# Add core and config directories to path
from config.env_loader import get_required_env_var
from scraper_agent.tools.remove_sheet_row import RemoveSheetRow
from firestore_client import get_firestore_client
from core.time_utils import now, to_iso8601_z



class MarkSheetRowsProcessed(BaseTool):
    """
    Identifies and archives successfully processed sheet rows based on video status.

    Queries Firestore for videos where:
    - source == "sheet"
    - status == "summarized" (fully processed)
    - sheet_metadata.processed_at is None (not yet cleaned up)

    Groups rows by sheet_id and calls RemoveSheetRow to archive them.
    Updates sheet_metadata.processed_at to prevent re-processing.
    """

    dry_run: bool = Field(
        False,
        description="If True, report what would be archived without actually doing it"
    )

    def run(self) -> str:
        """
        Find and archive successfully processed sheet rows.

        Returns:
            str: JSON string with summary of archived rows by sheet
        """
        try:
            # Initialize Firestore
            db = get_firestore_client()

            # Query for videos that are ready for cleanup
            videos_ref = db.collection('videos')
            query = videos_ref.where('source', '==', 'sheet') \
                             .where('status', '==', 'summarized')

            videos_to_process = []
            for doc in query.stream():
                video_data = doc.to_dict()
                video_id = doc.id

                # Check if sheet_metadata exists and not yet processed
                sheet_metadata = video_data.get('sheet_metadata')
                if sheet_metadata and sheet_metadata.get('processed_at') is None:
                    videos_to_process.append({
                        'video_id': video_id,
                        'sheet_id': sheet_metadata['sheet_id'],
                        'row_index': sheet_metadata['row_index'],
                        'title': video_data.get('title', 'Unknown')
                    })

            if not videos_to_process:
                return json.dumps({
                    "message": "No processed sheet rows found ready for archiving",
                    "videos_processed": 0,
                    "sheets_updated": 0
                }, indent=2)

            # Group by sheet_id
            sheets_to_update = self._group_by_sheet(videos_to_process)

            results = {
                "sheets_updated": 0,
                "total_rows_archived": 0,
                "by_sheet": {},
                "dry_run": self.dry_run
            }

            # Process each sheet
            for sheet_id, rows_info in sheets_to_update.items():
                row_indices = [info['row_index'] for info in rows_info]

                if self.dry_run:
                    results["by_sheet"][sheet_id] = {
                        "row_indices": row_indices,
                        "count": len(row_indices),
                        "action": "DRY RUN - would archive"
                    }
                    results["sheets_updated"] += 1
                    results["total_rows_archived"] += len(row_indices)
                else:
                    # Actually archive the rows
                    archive_result = self._archive_sheet_rows(sheet_id, row_indices)

                    if archive_result.get('success'):
                        # Mark videos as processed in Firestore
                        self._mark_videos_processed(db, rows_info)

                        results["by_sheet"][sheet_id] = {
                            "row_indices": row_indices,
                            "count": len(row_indices),
                            "action": "archived",
                            "details": archive_result
                        }
                        results["sheets_updated"] += 1
                        results["total_rows_archived"] += len(row_indices)
                    else:
                        results["by_sheet"][sheet_id] = {
                            "row_indices": row_indices,
                            "count": len(row_indices),
                            "action": "failed",
                            "error": archive_result.get('error')
                        }

            return json.dumps(results, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to mark sheet rows as processed: {str(e)}",
                "videos_processed": 0
            })

    def _group_by_sheet(self, videos: List[Dict]) -> Dict[str, List[Dict]]:
        """Group videos by sheet_id for batch processing."""
        grouped = {}
        for video in videos:
            sheet_id = video['sheet_id']
            if sheet_id not in grouped:
                grouped[sheet_id] = []
            grouped[sheet_id].append(video)
        return grouped

    def _archive_sheet_rows(self, sheet_id: str, row_indices: List[int]) -> Dict:
        """Archive rows using RemoveSheetRow tool."""
        try:
            # Sort in descending order to avoid index shifting issues
            sorted_indices = sorted(row_indices, reverse=True)

            remove_tool = RemoveSheetRow(
                sheet_id=sheet_id,
                row_indices=sorted_indices,
                archive_mode=True,
                source_sheet_name="Sheet1"
            )

            result_str = remove_tool.run()
            result = json.loads(result_str)

            if "error" in result:
                return {"success": False, "error": result["error"]}
            else:
                return {
                    "success": True,
                    "processed_rows": result.get("processed_rows", 0),
                    "message": result.get("message", "")
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _mark_videos_processed(self, db, rows_info: List[Dict]) -> None:
        """Update Firestore to mark videos as processed."""
        current_time = to_iso8601_z(now())

        for info in rows_info:
            try:
                doc_ref = db.collection('videos').document(info['video_id'])
                doc_ref.update({
                    'sheet_metadata.processed_at': current_time
                })
            except Exception as e:
                # Log but don't fail the whole operation
                print(f"Warning: Failed to mark video {info['video_id']} as processed: {str(e)}")


if __name__ == "__main__":
    print("=" * 80)
    print("MarkSheetRowsProcessed Tool Test")
    print("=" * 80)

    # Test 1: Dry run to see what would be archived
    print("\nTEST 1: Dry run mode")
    print("-" * 80)

    tool_dry_run = MarkSheetRowsProcessed(dry_run=True)

    try:
        result = tool_dry_run.run()
        print("Result:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['error']}")
        else:
            print(f"\n✅ Success: Found {data.get('total_rows_archived', 0)} rows ready for archiving")
            print(f"   Sheets affected: {data.get('sheets_updated', 0)}")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    # Test 2: Actual archiving (commented out for safety)
    print("\n" + "=" * 80)
    print("TEST 2: Actual archiving (COMMENTED OUT FOR SAFETY)")
    print("-" * 80)
    print("Uncomment to test actual archiving:")
    print("# tool = MarkSheetRowsProcessed(dry_run=False)")
    print("# result = tool.run()")
    print("=" * 80)
