"""Pytest configuration and fixtures."""

import pytest
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import utilities and fixtures
from tests.util.firebase_emulator import firebase_emulator, setup_emulators  # noqa: F401
from tests.util.item_flow_setup import item_flow_setup, ItemFlowSetup  # noqa: F401

# Configure test environment
os.environ["GCLOUD_PROJECT"] = "test-project"
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
os.environ["FIREBASE_STORAGE_EMULATOR_HOST"] = "localhost:9199"


@pytest.fixture(scope="session")
def firebase_app():
    """Initialize Firebase app for testing."""
    import firebase_admin
    from firebase_admin import credentials
    import os
    
    # Use the test service account file
    service_account_filename = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH", 
        "blank-test-project-firebase-adminsdk-k2n85-7570e24581.json"
    )
    service_account_path = os.path.join(
        os.path.dirname(__file__), "..", 
        service_account_filename
    )
    
    # Use certificate credentials for testing
    cred = credentials.Certificate(service_account_path)
    app = firebase_admin.initialize_app(cred)  # No name = default app
    
    yield app
    
    # Cleanup
    try:
        firebase_admin.delete_app(app)
    except Exception:
        pass


@pytest.fixture
def db(firebase_app):
    """Get test database instance."""
    from src.apis.Db import Db
    return Db.get_instance()


@pytest.fixture
def test_user_id():
    """Get a test user ID."""
    return "test-user-123"


