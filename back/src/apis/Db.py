"""Project database class with Firebase operations."""

import os
import json
import logging
import firebase_admin
from firebase_admin import firestore, storage
from firebase_admin.exceptions import FirebaseError
from google.cloud import secretmanager
from typing import Type, Dict, Any
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from abc import ABC


class Db(ABC):
    """Database operations base class.

    This class provides the base singleton pattern and common database functionality.
    Subclasses should initialize their specific collections in _init_collections method.
    """
    _instances: Dict[str, Any] = {}  # Class registry for singleton instances
    _gcp_secret_client = None
    _project_id = None
    _app_config = None  # Class-level AppConfiguration instance
    server_timestamp = firestore.firestore.SERVER_TIMESTAMP

    collections: Dict[str, Any] = {}

    def __new__(cls, *args, **kwargs):
        """Ensure only one instance per class exists"""
        if cls.__name__ not in cls._instances:
            cls._instances[cls.__name__] = super().__new__(cls)
        return cls._instances[cls.__name__]

    def __init__(self):
        """Initialize the database - only runs once per class due to singleton"""
        # Skip initialization if already done for this instance
        if hasattr(self, "_initialized"):
            return

        self._init_firestore()
        self._init_collections()
        self._initialized = True

    def _init_firestore(self):
        """Initialize Firestore client and base configuration."""
        self.firestore = firestore.client()
        self.logger = logging.getLogger("firebase-functions")
        self.logger.info("Firestore initialized")

    def _init_collections(self):
        """Initialize collection references."""
        self.collections = {
            # Base collection that all projects need
            "users": self.firestore.collection("users"),
            
            # Project-specific collections
            "items": self.firestore.collection("items"),
            "categories": self.firestore.collection("categories"),
            "itemActivities": lambda item_id: self.firestore.collection(f"items/{item_id}/activities"),
            
            # Add more collections as needed
            # "collection_name": self.firestore.collection("collection_name"),
            # "subcollection": lambda parent_id: self.firestore.collection(f"parent/{parent_id}/subcollection"),
        }

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance for this class"""
        return cls()

    # Storage functions
    def _get_signed_url_credentials(self):
        signer_json = os.environ["SIGNED_URL_SERVICE_ACCOUNT_JSON"]
        info = json.loads(signer_json)
        return service_account.Credentials.from_service_account_info(info)

    def get_file_url(self, file_path: str):
        if file_path.startswith("/"):
            file_path = file_path[1:]
        bucket = storage.bucket()
        blob = bucket.blob(file_path)

        # type: ignore
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="GET",
            credentials=self._get_signed_url_credentials(),
        )

    def get_folder_files_urls_dict(self, folder_path: str) -> dict:
        if folder_path.startswith("/"):
            folder_path = folder_path[1:]

        if not folder_path.endswith("/"):
            folder_path += "/"

        bucket = storage.bucket()
        blobs = bucket.list_blobs(prefix=folder_path)

        return {
            blob.name[len(folder_path):]: self.get_file_url(blob.name)
            for blob in blobs
            if not blob.name.endswith("/")
        }

    def remove_folder_files(self, folder_path: str):
        if folder_path.startswith("/"):
            folder_path = folder_path[1:]

        if not folder_path.endswith("/"):
            folder_path += "/"

        bucket = storage.bucket()
        blobs = list(bucket.list_blobs(prefix=folder_path))

        if blobs:
            # Delete by Blob objects to satisfy google-cloud-storage API
            bucket.delete_blobs(blobs)

        # Best-effort: remove potential directory placeholder objects
        try:
            placeholder_names = {folder_path, folder_path.rstrip('/')}
            for name in placeholder_names:
                if not name:
                    continue
                ph_blob = bucket.blob(name)
                if ph_blob.exists():  # type: ignore[attr-defined]
                    ph_blob.delete()
        except Exception:
            # Ignore placeholder deletion errors in test/CI
            pass

    async def upload_file(self, local_path: str, destination: str):
        bucket = storage.bucket()
        bucket.blob(destination).upload_from_filename(local_path)

    async def upload_file_buffer(self, buffer: bytes, destination: str):
        bucket = storage.bucket()
        blob = bucket.blob(destination)
        blob.upload_from_string(buffer)
        return blob

    async def list_files(self, folder_path: str):
        bucket = storage.bucket()
        blobs = bucket.list_blobs(prefix=folder_path)
        return [blob.name for blob in blobs]

    async def download_file(self, file_path: str, destination: str):
        if file_path.startswith("/"):
            file_path = file_path[1:]
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        blob.download_to_filename(destination)

    async def download_all_files(self, folder_path: str, destination: str):
        bucket = storage.bucket()
        blobs = bucket.list_blobs(prefix=folder_path)
        for blob in blobs:
            blob.download_to_filename(
                os.path.join(destination, os.path.basename(blob.name))
            )

    async def get_file_stream(self, file_path: str):
        if file_path.startswith("/"):
            file_path = file_path[1:]
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        return blob.open("rb")

    async def get_file_buffer(self, file_path: str):
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        return blob.download_as_bytes()

    async def delete_file(self, file_path: str):
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        blob.delete()

    async def delete_folder(self, folder_path: str):
        bucket = storage.bucket()
        blobs = bucket.list_blobs(prefix=folder_path)
        for blob in blobs:
            blob.delete()

    # Utility functions
    def converter(self, cls: Type[object]):
        return {
            "toFirestore": lambda doc: doc.__dict__,
            "fromFirestore": lambda snapshot, options: cls(**snapshot.to_dict()),
        }

    @staticmethod
    def is_production():
        """Check if running in production environment using AppConfiguration"""
        return os.getenv("ENV") == "production"

    @staticmethod
    def is_development():
        """Check if running in development environment using AppConfiguration"""
        return os.getenv("ENV") == "development"

    @staticmethod
    def get_project_num():
        """Get GCP project number for secrets management.
        
        Update these with your actual GCP project numbers.
        You can find them in the GCP Console or by running:
        gcloud projects describe PROJECT_ID --format="value(projectNumber)"
        """
        return os.environ.get("GCLOUD_PROJECT_NUMBER")

    def get_app_name(self):
        return firebase_admin.get_app().name

    # Secrets functions
    @staticmethod
    async def create_secret(name: str, value: str):
        if not Db._gcp_secret_client:
            Db._gcp_secret_client = secretmanager.SecretManagerServiceClient()

        parent = f"projects/{Db.get_project_num()}"
        secret = Db._gcp_secret_client.create_secret(
            request={
                "parent": parent,
                "secret_id": name,
                "secret": {"replication": {"automatic": {}}},
            }
        )

        version = Db._gcp_secret_client.add_secret_version(
            request={"parent": secret.name, "payload": {
                "data": value.encode("utf-8")}}
        )

        return version.name

    @staticmethod
    async def update_secret(id: str, new_value: str):
        if not Db._gcp_secret_client:
            Db._gcp_secret_client = secretmanager.SecretManagerServiceClient()

        parent = f"projects/{Db.get_project_num()}/secrets/{id}"
        version = Db._gcp_secret_client.add_secret_version(
            request={"parent": parent, "payload": {
                "data": new_value.encode("utf-8")}}
        )

        return version.name

    @staticmethod
    async def get_secret(id: str):
        if not Db._gcp_secret_client:
            Db._gcp_secret_client = secretmanager.SecretManagerServiceClient()

        version = Db._gcp_secret_client.access_secret_version(
            request={
                "name": f"projects/{Db.get_project_num()}/secrets/{id}/versions/latest"
            }
        )

        return version.payload.data.decode("utf-8")

    @staticmethod
    async def delete_secret(id: str):
        if not Db._gcp_secret_client:
            Db._gcp_secret_client = secretmanager.SecretManagerServiceClient()

        name = f"projects/{Db.get_project_num()}/secrets/{id}"
        Db._gcp_secret_client.delete_secret(request={"name": name})

    # Timestamp functions
    @staticmethod
    def get_expires_at(days=0, hours=0, minutes=0, seconds=0):
        created_at = Db.get_created_at()
        expires_at_date = created_at.to_pydatetime()  # type: ignore
        expires_at_date += timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds
        )
        return firestore.firestore.SERVER_TIMESTAMP

    @staticmethod
    def timestamp_now():
        return datetime.now(timezone.utc)

    @staticmethod
    def get_timestamp_from_date(date):
        return date

    @staticmethod
    def get_date_from_timestamp(timestamp):
        return timestamp.to_pydatetime()

    @staticmethod
    def get_created_at():
        return datetime.now(timezone.utc)

    # Auth functions
    @staticmethod
    def check_auth(request):
        if not request.auth:
            raise FirebaseError(
                "unauthenticated", "The function must be called while authenticated."
            )

        if (Db.is_production()) and not request.app:
            raise FirebaseError(
                "failed-precondition",
                "The function must be called from an App Check verified app.",
            )

        return request.auth.uid


