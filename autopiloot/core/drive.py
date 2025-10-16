"""
Google Drive client factory for centralized authentication and service creation.
Provides consistent Drive API access across all agent tools.
"""

import sys
import os
from typing import List, Optional

# Add config directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))

from google.oauth2 import service_account
from googleapiclient.discovery import build
from env_loader import get_required_env_var


# Default scopes for Drive operations
DEFAULT_SCOPES = ['https://www.googleapis.com/auth/drive']
READONLY_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def get_drive_service(scopes: Optional[List[str]] = None, readonly: bool = False):
    """
    Get authenticated Google Drive API service.

    Creates a Drive service client with service account credentials from environment.
    Centralizes authentication logic to eliminate duplication across tools.

    Args:
        scopes: List of OAuth scopes for Drive access. If None, uses defaults.
        readonly: If True, uses read-only scope (ignored if scopes provided).
                 Default: False (full Drive access).

    Returns:
        googleapiclient.discovery.Resource: Authenticated Drive v3 service client

    Raises:
        Exception: If credentials are missing or service initialization fails

    Example:
        >>> # Get Drive service with default scopes (full access)
        >>> service = get_drive_service()
        >>>
        >>> # Get read-only Drive service
        >>> service = get_drive_service(readonly=True)
        >>>
        >>> # Get service with custom scopes
        >>> service = get_drive_service(scopes=['https://www.googleapis.com/auth/drive.file'])
    """
    try:
        # Get credentials path from environment
        creds_path = get_required_env_var(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "Google service account credentials path for Drive API access"
        )

        # Determine scopes to use
        if scopes is None:
            scopes = READONLY_SCOPES if readonly else DEFAULT_SCOPES

        # Create credentials from service account file
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=scopes
        )

        # Build and return Drive service
        service = build('drive', 'v3', credentials=credentials)
        return service

    except Exception as e:
        raise Exception(f"Failed to initialize Google Drive service: {str(e)}")


if __name__ == "__main__":
    """Test the Drive service factory."""
    import json

    print("=" * 80)
    print("TEST: Google Drive Service Factory")
    print("=" * 80)

    try:
        # Test 1: Get service with default scopes
        print("\n1. Testing default Drive service (full access)...")
        service = get_drive_service()
        print("   ✓ Service created successfully")
        print(f"   Service type: {type(service).__name__}")

        # Test basic API call
        about = service.about().get(fields="user(emailAddress)").execute()
        print(f"   Service account: {about.get('user', {}).get('emailAddress', 'unknown')}")

    except Exception as e:
        print(f"   ✗ Error: {str(e)}")

    try:
        # Test 2: Get read-only service
        print("\n2. Testing read-only Drive service...")
        service_readonly = get_drive_service(readonly=True)
        print("   ✓ Read-only service created successfully")

        # Test basic API call
        about = service_readonly.about().get(fields="user(emailAddress)").execute()
        print(f"   Service account: {about.get('user', {}).get('emailAddress', 'unknown')}")

    except Exception as e:
        print(f"   ✗ Error: {str(e)}")

    try:
        # Test 3: Get service with custom scopes
        print("\n3. Testing custom scopes...")
        custom_scopes = [
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.metadata.readonly'
        ]
        service_custom = get_drive_service(scopes=custom_scopes)
        print("   ✓ Service with custom scopes created successfully")
        print(f"   Scopes: {custom_scopes}")

    except Exception as e:
        print(f"   ✗ Error: {str(e)}")

    try:
        # Test 4: Verify service can list files
        print("\n4. Testing file listing capability...")
        results = service.files().list(
            pageSize=5,
            fields="files(id, name)"
        ).execute()
        files = results.get('files', [])
        print(f"   ✓ Listed {len(files)} files")
        if files:
            print(f"   First file: {files[0].get('name')} (ID: {files[0].get('id')})")

    except Exception as e:
        print(f"   ✗ Error: {str(e)}")

    print("\n" + "=" * 80)
    print("✅ Drive service factory test completed")
    print("=" * 80)
