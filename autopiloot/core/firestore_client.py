"""
Centralized Firestore client factory for Autopiloot Agency.

Provides a single, validated Firestore client used across all agents and tools
to eliminate duplicated initialization code and ensure consistent environment
validation and error handling.

Usage:
    from core.firestore_client import get_firestore_client

    db = get_firestore_client()
    doc_ref = db.collection('videos').document('abc123')
"""

import os
from typing import Optional
from google.cloud import firestore

from config.env_loader import get_required_env_var, get_optional_env_var


# Singleton instance for the Firestore client
_firestore_client: Optional[firestore.Client] = None


def get_firestore_client() -> firestore.Client:
    """
    Get or create a singleton Firestore client with validated credentials.

    This function initializes a Firestore client using environment variables
    and caches it for reuse. It validates that required credentials are
    properly configured before attempting to connect.

    Returns:
        firestore.Client: Initialized Firestore client

    Raises:
        RuntimeError: If GCP_PROJECT_ID is not set or credentials are invalid

    Environment Variables Required:
        - GCP_PROJECT_ID: Google Cloud Project ID
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON (optional)
    """
    global _firestore_client

    # Return cached instance if available
    if _firestore_client is not None:
        return _firestore_client

    try:
        # Get required project ID
        project_id = get_required_env_var(
            "GCP_PROJECT_ID",
            "Google Cloud Project ID for Firestore access"
        )

        # Get optional service account credentials path
        credentials_path = get_optional_env_var(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "",
            "Path to Google service account JSON file"
        )

        # Validate credentials file exists if specified
        if credentials_path and not os.path.exists(credentials_path):
            raise RuntimeError(
                f"GOOGLE_APPLICATION_CREDENTIALS path does not exist: {credentials_path}\n"
                f"Please ensure the service account JSON file is present at this location."
            )

        # Initialize Firestore client
        _firestore_client = firestore.Client(project=project_id)

        return _firestore_client

    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize Firestore client: {str(e)}\n"
            f"Ensure GCP_PROJECT_ID is set and credentials are valid."
        ) from e


def get_collection(collection_name: str) -> firestore.CollectionReference:
    """
    Get a Firestore collection reference using the singleton client.

    Convenience function that combines client retrieval and collection access.

    Args:
        collection_name: Name of the Firestore collection

    Returns:
        firestore.CollectionReference: Reference to the collection

    Example:
        videos_ref = get_collection('videos')
        doc = videos_ref.document('abc123').get()
    """
    client = get_firestore_client()
    return client.collection(collection_name)


def reset_client() -> None:
    """
    Reset the singleton Firestore client instance.

    This is primarily useful for testing to force re-initialization
    with different credentials or for cleanup between test runs.

    Warning:
        This should not be used in production code. It's intended for
        test isolation only.
    """
    global _firestore_client
    _firestore_client = None


if __name__ == "__main__":
    # Test the Firestore client initialization
    print("Testing Firestore client initialization...")

    try:
        client = get_firestore_client()
        print(f"✅ Firestore client initialized successfully")
        print(f"   Project: {client.project}")

        # Test singleton behavior
        client2 = get_firestore_client()
        if client is client2:
            print("✅ Singleton behavior verified (same instance returned)")
        else:
            print("❌ Singleton behavior failed (different instances)")

        # Test collection helper
        videos_ref = get_collection('videos')
        print(f"✅ Collection reference created: {videos_ref.id}")

        print("\n🎉 All Firestore client tests passed!")

    except Exception as e:
        print(f"❌ Firestore client initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
