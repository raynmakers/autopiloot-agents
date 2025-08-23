"""
Firebase Functions entry point.
All functions must be exported from this file for deployment.
"""

import logging
from firebase_admin import initialize_app
from firebase_admin import credentials
import os

# Initialize Firebase Admin SDK
if os.getenv("ENV") == "production":
    initialize_app()
else:
    # For development/testing with service account
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if service_account_path and os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        initialize_app(cred)
    else:
        # Use default credentials if no service account specified
        initialize_app()

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