"""
Resolve Google Drive folder tree recursively
Fetches all files and subfolders with metadata and pattern filtering
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
import fnmatch

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var
from loader import get_config_value


class ResolveFolderTree(BaseTool):
    """
    Recursively resolve Google Drive folder structure to get all files and subfolders.
    Supports pagination, pattern filtering, and metadata collection.
    """

    folder_id: str = Field(
        ...,
        description="Google Drive folder ID to resolve"
    )

    recursive: bool = Field(
        default=True,
        description="Whether to traverse subfolders recursively"
    )

    include_patterns: List[str] = Field(
        default=[],
        description="File name patterns to include (e.g., ['*.pdf', '*.docx']). Empty means include all."
    )

    exclude_patterns: List[str] = Field(
        default=[],
        description="File name patterns to exclude (e.g., ['~*', '*.tmp'])"
    )

    max_depth: int = Field(
        default=10,
        description="Maximum recursion depth to prevent infinite loops"
    )

    page_size: int = Field(
        default=100,
        description="Number of items to fetch per API call"
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

    def _resolve_folder(self, service, folder_id: str, folder_name: str = "root",
                       depth: int = 0, parent_path: str = "") -> Dict[str, Any]:
        """Recursively resolve folder contents."""

        folder_data = {
            "id": folder_id,
            "name": folder_name,
            "type": "folder",
            "path": f"{parent_path}/{folder_name}" if parent_path else folder_name,
            "files": [],
            "folders": [],
            "total_files": 0,
            "total_size_bytes": 0
        }

        # Check max depth
        if depth >= self.max_depth:
            folder_data["warning"] = f"Max depth {self.max_depth} reached"
            return folder_data

        try:
            # Query for all items in this folder
            query = f"'{folder_id}' in parents and trashed = false"
            page_token = None

            while True:
                # List files and folders
                results = service.files().list(
                    q=query,
                    pageSize=self.page_size,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, owners, webViewLink)",
                    pageToken=page_token
                ).execute()

                items = results.get('files', [])

                for item in items:
                    # Check if it's a folder
                    if item.get('mimeType') == 'application/vnd.google-apps.folder':
                        # Process subfolder recursively if enabled
                        if self.recursive:
                            subfolder_data = self._resolve_folder(
                                service,
                                item['id'],
                                item['name'],
                                depth + 1,
                                folder_data["path"]
                            )
                            folder_data["folders"].append(subfolder_data)
                            # Aggregate stats from subfolder
                            folder_data["total_files"] += subfolder_data["total_files"]
                            folder_data["total_size_bytes"] += subfolder_data["total_size_bytes"]
                        else:
                            # Just add folder metadata without recursing
                            folder_data["folders"].append({
                                "id": item['id'],
                                "name": item['name'],
                                "type": "folder",
                                "path": f"{folder_data['path']}/{item['name']}"
                            })
                    else:
                        # It's a file - check pattern matching
                        if self._matches_patterns(item['name']):
                            file_info = {
                                "id": item['id'],
                                "name": item['name'],
                                "mimeType": item.get('mimeType', 'unknown'),
                                "size": int(item.get('size', 0)),
                                "modifiedTime": item.get('modifiedTime'),
                                "path": f"{folder_data['path']}/{item['name']}",
                                "webViewLink": item.get('webViewLink')
                            }

                            # Add owner info if available
                            if 'owners' in item and item['owners']:
                                file_info["owner"] = item['owners'][0].get('emailAddress', 'unknown')

                            folder_data["files"].append(file_info)
                            folder_data["total_files"] += 1
                            folder_data["total_size_bytes"] += int(item.get('size', 0))

                # Check for more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break

        except HttpError as e:
            if e.resp.status == 404:
                folder_data["error"] = f"Folder not found: {folder_id}"
            elif e.resp.status == 403:
                folder_data["error"] = f"Permission denied for folder: {folder_id}"
            else:
                folder_data["error"] = f"API error: {str(e)}"
        except Exception as e:
            folder_data["error"] = f"Unexpected error: {str(e)}"

        return folder_data

    def run(self) -> str:
        """
        Resolve the Drive folder tree structure.

        Returns:
            JSON string containing folder tree with files and metadata
        """
        try:
            # Initialize Drive service
            service = self._get_drive_service()

            # Get folder metadata first
            try:
                folder_metadata = service.files().get(
                    fileId=self.folder_id,
                    fields="id, name, mimeType"
                ).execute()

                # Verify it's actually a folder
                if folder_metadata.get('mimeType') != 'application/vnd.google-apps.folder':
                    return json.dumps({
                        "error": "not_a_folder",
                        "message": f"ID {self.folder_id} is not a folder",
                        "mimeType": folder_metadata.get('mimeType')
                    })

                folder_name = folder_metadata.get('name', 'Unknown Folder')

            except HttpError as e:
                if e.resp.status == 404:
                    return json.dumps({
                        "error": "folder_not_found",
                        "message": f"Folder with ID {self.folder_id} not found"
                    })
                raise

            # Resolve folder tree
            tree_data = self._resolve_folder(
                service,
                self.folder_id,
                folder_name,
                depth=0,
                parent_path=""
            )

            # Add summary statistics
            result = {
                "folder_tree": tree_data,
                "summary": {
                    "total_files": tree_data["total_files"],
                    "total_folders": len(tree_data["folders"]),
                    "total_size_bytes": tree_data["total_size_bytes"],
                    "total_size_mb": round(tree_data["total_size_bytes"] / (1024 * 1024), 2),
                    "recursive": self.recursive,
                    "patterns_applied": {
                        "include": self.include_patterns,
                        "exclude": self.exclude_patterns
                    }
                }
            }

            return json.dumps(result)

        except Exception as e:
            return json.dumps({
                "error": "resolution_error",
                "message": f"Failed to resolve folder tree: {str(e)}",
                "details": {
                    "folder_id": self.folder_id,
                    "type": type(e).__name__
                }
            })


if __name__ == "__main__":
    # Test the tool
    print("Testing ResolveFolderTree tool...")

    # Note: Replace with a valid folder ID for testing
    test_folder_id = os.environ.get("TEST_DRIVE_FOLDER_ID", "example_folder_id_here")

    # Test basic folder resolution
    print(f"\n1. Testing basic folder resolution for ID: {test_folder_id}")
    tool = ResolveFolderTree(
        folder_id=test_folder_id,
        recursive=False
    )
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))

    # Test recursive with patterns
    print("\n2. Testing recursive resolution with patterns...")
    tool = ResolveFolderTree(
        folder_id=test_folder_id,
        recursive=True,
        include_patterns=["*.pdf", "*.docx", "*.txt"],
        exclude_patterns=["~*", "*.tmp"],
        max_depth=3
    )
    result = tool.run()
    result_json = json.loads(result)

    # Only print summary for recursive test
    if "summary" in result_json:
        print("Summary:")
        print(json.dumps(result_json["summary"], indent=2))
    else:
        print(json.dumps(result_json, indent=2))