"""Test environment utilities."""

import os
from typing import Dict, Any


def setup_test_environment():
    """Set up test environment variables."""
    test_env = {
        "GCLOUD_PROJECT": "test-project",
        "FIRESTORE_EMULATOR_HOST": "localhost:8080",
        "FIREBASE_STORAGE_EMULATOR_HOST": "localhost:9199",
        "FIREBASE_AUTH_EMULATOR_HOST": "localhost:9099",
        "FUNCTIONS_EMULATOR": "true",
    }
    
    for key, value in test_env.items():
        os.environ[key] = value


def get_test_config() -> Dict[str, Any]:
    """Get test configuration."""
    return {
        "project_id": "test-project",
        "emulators": {
            "firestore": {
                "host": "localhost",
                "port": 8080,
            },
            "storage": {
                "host": "localhost",
                "port": 9199,
            },
            "auth": {
                "host": "localhost",
                "port": 9099,
            },
        },
        "test_users": {
            "admin": "test-admin-uid",
            "regular": "test-user-uid",
            "premium": "test-premium-uid",
        },
    }


def is_emulator_running() -> bool:
    """Check if Firebase emulators are running."""
    import requests
    
    try:
        # Check Firestore emulator
        response = requests.get("http://localhost:8080")
        return response.status_code == 200
    except:
        return False