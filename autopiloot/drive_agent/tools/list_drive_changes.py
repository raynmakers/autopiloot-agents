"""
List Google Drive changes since checkpoint for incremental processing
Supports file-specific changes, time-based filtering, and pagination
"""

import os
import json
import sys
from typing import List, Dict, Any, Optional
from pydantic import Field
from agency_swarm.tools import BaseTool
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timezone
import fnmatch

# Add config directory to path
from env_loader import get_required_env_var
from core.time_utils import parse_iso8601_z


class ListDriveChanges(BaseTool):
    """
    List changes to specific Google Drive files since a given checkpoint.
    Supports time-based filtering and pattern matching for incremental processing.
    """

    file_ids: List[str] = Field(
        ...,
        description="List of Google Drive file/folder IDs to check for changes"
    )

    since_iso: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp to check changes since (e.g., '2025-01-01T00:00:00Z'). If None, returns all recent changes."
    )

    include_patterns: List[str] = Field(
        default=[],
        description="File name patterns to include (e.g., ['*.pdf', '*.docx']). Empty means include all."
    )

    exclude_patterns: List[str] = Field(
        default=[],
        description="File name patterns to exclude (e.g., ['~*', '*.tmp'])"
    )

    page_size: int = Field(
        default=100,
        description="Number of items to fetch per API call"
    )

    include_folders: bool = Field(
        default=False,
        description="Whether to include folder changes in results"
    )

    def _get_drive_service(self):
        """Initialize Google Drive API service."""
        try:
            # Get credentials path from environment
            creds_path = get_required_env_var("GOOGLE_APPLICATION_CREDENTIALS")

            # Create credentials from service account file
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )

            # Build Drive service
            service = build('drive', 'v3', credentials=credentials)
            return service
        except Exception as e:
            raise Exception(f"Failed to initialize Drive service: {str(e)}")

    def _matches_patterns(self, file_name: str) -> bool:
        """Check if file name matches include/exclude patterns."""
        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
                return False

        # If no include patterns specified, include all (that weren't excluded)
        if not self.include_patterns:
            return True

        # Check include patterns
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
                return True

        return False

    def _parse_iso_timestamp(self, iso_string: str) -> datetime:
        """Parse ISO 8601 timestamp string to datetime object using centralized helper."""
        return parse_iso8601_z(iso_string)

    def _get_file_changes(self, service, file_id: str) -> Dict[str, Any]:
        """Get changes for a specific file ID."""
        try:
            # Get file metadata
            file_metadata = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime, version, owners, webViewLink, parents"
            ).execute()

            # Check if file matches patterns (if it's not a folder)
            is_folder = file_metadata.get('mimeType') == 'application/vnd.google-apps.folder'

            if not is_folder and not self._matches_patterns(file_metadata.get('name', '')):
                return None

            # Skip folders if not requested
            if is_folder and not self.include_folders:
                return None

            # Parse modification time
            modified_time_str = file_metadata.get('modifiedTime')
            if not modified_time_str:
                return None

            modified_time = parse_iso8601_z(modified_time_str)

            # Check if file was modified since checkpoint
            if self.since_iso:
                since_time = self._parse_iso_timestamp(self.since_iso)
                if modified_time <= since_time:
                    return None

            # Build change record
            change_record = {
                "file_id": file_id,
                "name": file_metadata.get('name'),
                "mimeType": file_metadata.get('mimeType'),
                "size": int(file_metadata.get('size', 0)),
                "modifiedTime": modified_time_str,
                "version": file_metadata.get('version'),
                "webViewLink": file_metadata.get('webViewLink'),
                "type": "folder" if is_folder else "file",
                "change_type": "modified"  # We detect modifications, not creates/deletes
            }

            # Add parent folder info
            if 'parents' in file_metadata and file_metadata['parents']:
                change_record["parent_folder_id"] = file_metadata['parents'][0]

            # Add owner info if available
            if 'owners' in file_metadata and file_metadata['owners']:
                change_record["owner"] = file_metadata['owners'][0].get('emailAddress', 'unknown')

            return change_record

        except HttpError as e:
            if e.resp.status == 404:
                # File was deleted or access revoked
                return {
                    "file_id": file_id,
                    "change_type": "deleted_or_inaccessible",
                    "error": "File not found or access denied"
                }
            elif e.resp.status == 403:
                return {
                    "file_id": file_id,
                    "change_type": "access_denied",
                    "error": "Permission denied"
                }
            else:
                return {
                    "file_id": file_id,
                    "change_type": "error",
                    "error": f"API error: {str(e)}"
                }
        except Exception as e:
            return {
                "file_id": file_id,
                "change_type": "error",
                "error": f"Unexpected error: {str(e)}"
            }

    def _check_folder_contents(self, service, folder_id: str) -> List[Dict[str, Any]]:
        """Check for changes in folder contents."""
        changes = []
        page_token = None

        try:
            # Build query for folder contents
            query = f"'{folder_id}' in parents and trashed = false"

            # Add time filter if specified
            if self.since_iso:
                since_time = self._parse_iso_timestamp(self.since_iso)
                # Format for Drive API (RFC 3339)
                since_rfc3339 = since_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                query += f" and modifiedTime > '{since_rfc3339}'"

            while True:
                # List files in folder
                results = service.files().list(
                    q=query,
                    pageSize=self.page_size,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, version, owners, webViewLink, parents)",
                    pageToken=page_token
                ).execute()

                items = results.get('files', [])

                for item in items:
                    is_folder = item.get('mimeType') == 'application/vnd.google-apps.folder'

                    # Skip folders if not requested, skip files that don't match patterns
                    if is_folder and not self.include_folders:
                        continue
                    if not is_folder and not self._matches_patterns(item.get('name', '')):
                        continue

                    change_record = {
                        "file_id": item['id'],
                        "name": item.get('name'),
                        "mimeType": item.get('mimeType'),
                        "size": int(item.get('size', 0)),
                        "modifiedTime": item.get('modifiedTime'),
                        "version": item.get('version'),
                        "webViewLink": item.get('webViewLink'),
                        "type": "folder" if is_folder else "file",
                        "change_type": "modified",
                        "parent_folder_id": folder_id
                    }

                    # Add owner info if available
                    if 'owners' in item and item['owners']:
                        change_record["owner"] = item['owners'][0].get('emailAddress', 'unknown')

                    changes.append(change_record)

                # Check for more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break

        except HttpError as e:
            # Return error for the folder
            changes.append({
                "file_id": folder_id,
                "change_type": "folder_error",
                "error": f"Failed to check folder contents: {str(e)}"
            })

        return changes

    def run(self) -> str:
        """
        List changes to specified files since checkpoint.

        Returns:
            JSON string containing list of changed files with metadata
        """
        try:
            # Initialize Drive service
            service = self._get_drive_service()

            # Validate since_iso if provided
            since_time = None
            if self.since_iso:
                since_time = self._parse_iso_timestamp(self.since_iso)

            all_changes = []
            processed_count = 0
            error_count = 0

            # Process each file ID
            for file_id in self.file_ids:
                processed_count += 1

                # First, check if it's a folder
                try:
                    file_metadata = service.files().get(
                        fileId=file_id,
                        fields="id, mimeType"
                    ).execute()

                    is_folder = file_metadata.get('mimeType') == 'application/vnd.google-apps.folder'

                    if is_folder:
                        # Check folder contents for changes
                        folder_changes = self._check_folder_contents(service, file_id)
                        all_changes.extend(folder_changes)
                    else:
                        # Check individual file for changes
                        file_change = self._get_file_changes(service, file_id)
                        if file_change:
                            all_changes.append(file_change)

                except HttpError as e:
                    error_count += 1
                    all_changes.append({
                        "file_id": file_id,
                        "change_type": "error",
                        "error": f"Failed to process: {str(e)}"
                    })

            # Filter out None results and sort by modification time
            valid_changes = [change for change in all_changes if change is not None]
            valid_changes.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)

            # Build result
            result = {
                "changes": valid_changes,
                "summary": {
                    "total_changes": len(valid_changes),
                    "processed_files": processed_count,
                    "errors": error_count,
                    "since_timestamp": self.since_iso,
                    "patterns_applied": {
                        "include": self.include_patterns,
                        "exclude": self.exclude_patterns
                    },
                    "include_folders": self.include_folders
                }
            }

            # Add time range info if filtering by time
            if since_time:
                result["summary"]["filtered_since"] = since_time.isoformat()

            return json.dumps(result)

        except Exception as e:
            return json.dumps({
                "error": "changes_listing_error",
                "message": f"Failed to list Drive changes: {str(e)}",
                "details": {
                    "file_ids": self.file_ids,
                    "since_iso": self.since_iso,
                    "type": type(e).__name__
                }
            })


if __name__ == "__main__":
    # Test the tool
    print("Testing ListDriveChanges tool...")

    # Test file IDs (replace with valid IDs for testing)
    test_file_ids = [
        os.environ.get("TEST_DRIVE_FILE_ID", "example_file_id_here"),
        os.environ.get("TEST_DRIVE_FOLDER_ID", "example_folder_id_here")
    ]

    # Test 1: List all recent changes
    print(f"\n1. Testing recent changes for IDs: {test_file_ids}")
    tool = ListDriveChanges(
        file_ids=test_file_ids,
        include_folders=True
    )
    result = tool.run()
    result_json = json.loads(result)
    print("Summary:")
    print(json.dumps(result_json.get("summary", {}), indent=2))

    # Test 2: List changes since specific time
    print("\n2. Testing changes since 2025-01-01...")
    tool = ListDriveChanges(
        file_ids=test_file_ids,
        since_iso="2025-01-01T00:00:00Z",
        include_patterns=["*.pdf", "*.docx", "*.txt"],
        exclude_patterns=["~*", "*.tmp"],
        include_folders=False
    )
    result = tool.run()
    result_json = json.loads(result)
    print("Summary:")
    print(json.dumps(result_json.get("summary", {}), indent=2))

    # Show first few changes if any
    if "changes" in result_json and result_json["changes"]:
        print("\nFirst change:")
        print(json.dumps(result_json["changes"][0], indent=2))
    else:
        print("\nNo changes found or error occurred.")
        if "error" in result_json:
            print(f"Error: {result_json['error']}")
            print(f"Message: {result_json['message']}")