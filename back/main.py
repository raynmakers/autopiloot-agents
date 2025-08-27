"""
Firebase Functions entry point.
All functions must be exported from this file for deployment.
"""

import logging
from firebase_admin import initialize_app
from firebase_admin import credentials
import os

# Set emulator environment variables if running in emulators
if os.getenv('FUNCTIONS_EMULATOR') == 'true':
    # These are typically already set by the test runner, but ensure they're set
    if not os.getenv('FIRESTORE_EMULATOR_HOST'):
        os.environ['FIRESTORE_EMULATOR_HOST'] = 'localhost:8080'
    if not os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
        os.environ['FIREBASE_AUTH_EMULATOR_HOST'] = 'localhost:9099'
    if not os.getenv('FIREBASE_STORAGE_EMULATOR_HOST'):
        os.environ['FIREBASE_STORAGE_EMULATOR_HOST'] = 'localhost:9199'

# Initialize Firebase Admin SDK
# The SDK automatically detects emulator environment variables
# No credentials needed when running in emulators
try:
    import firebase_admin
    # Only initialize if no app exists yet
    if not firebase_admin._apps:
        initialize_app()
except ValueError:
    # App already initialized (can happen in tests)
    pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import callable functions
from src.brokers.callable.example_callable import example_callable
from src.brokers.callable.create_item import create_item_callable
from src.brokers.callable.get_item import get_item_callable

# Import HTTPS functions
from src.brokers.https.health_check import health_check
from src.brokers.https.webhook_handler import webhook_handler

# Import triggered functions
from src.brokers.triggered.on_item_created import on_item_created
from src.brokers.triggered.on_item_updated import on_item_updated
from src.brokers.triggered.on_item_deleted import on_item_deleted

# Export all functions for Firebase deployment
__all__ = [
    # Callable functions
    'example_callable',
    'create_item_callable',
    'get_item_callable',
    
    # HTTPS functions
    'health_check',
    'webhook_handler',
    
    # Triggered functions
    'on_item_created',
    'on_item_updated',
    'on_item_deleted',
]

logger.info("Firebase Functions initialized successfully")