"""Pytest configuration and fixtures."""

import pytest
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env.local first, then .env
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv('.env')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Add root to path for main.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set emulator environment variables before any Firebase imports
os.environ["GCLOUD_PROJECT"] = "test-project" 
os.environ["FUNCTIONS_EMULATOR"] = "true"
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099" 
os.environ["FIREBASE_STORAGE_EMULATOR_HOST"] = "localhost:9199"

# Service account credentials will be read from GOOGLE_APPLICATION_CREDENTIALS environment variable
# Note: Ideally this shouldn't be needed per Google docs, but required for Db class operations

# Import main to ensure Firebase app is initialized properly
import main

# Import utilities and fixtures
from tests.util.firebase_emulator import firebase_emulator, setup_emulators  # noqa: F401
from tests.util.item_flow_setup import item_flow_setup, ItemFlowSetup  # noqa: F401


@pytest.fixture(scope="session")
def firebase_app():
    """Initialize Firebase app for testing."""
    import firebase_admin
    from firebase_admin import credentials
    import os
    
    # Set the project ID from .firebaserc
    os.environ["GCLOUD_PROJECT"] = "test-project"
    
    # Check if running in the emulator and set environment variables
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        # Set emulator environment variables
        os.environ['FIRESTORE_EMULATOR_HOST'] = 'localhost:8080'
        os.environ['FIREBASE_AUTH_EMULATOR_HOST'] = 'localhost:9099'
        os.environ['FIREBASE_STORAGE_EMULATOR_HOST'] = 'localhost:9199'
        
        # Initialize without credentials for emulator
        if not firebase_admin._apps:
            app = firebase_admin.initialize_app()
        else:
            app = firebase_admin.get_app()
    else:
        # Use the service account file from GOOGLE_APPLICATION_CREDENTIALS environment variable
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not service_account_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        
        # Use certificate credentials for production testing
        cred = credentials.Certificate(service_account_path)
        if not firebase_admin._apps:
            app = firebase_admin.initialize_app(cred)
        else:
            app = firebase_admin.get_app()
    
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


