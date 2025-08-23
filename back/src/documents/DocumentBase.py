"""Document base class for Firestore operations."""

from datetime import datetime, timezone
from typing import Type, Optional, TypeVar, Generic
from google.cloud.firestore_v1.collection import CollectionReference
from firebase_admin.exceptions import FirebaseError
import logging
from src.apis.Db import Db
from src.models.firestore_types import BaseDoc

DocLike = TypeVar('DocLike', bound=BaseDoc)


def remove_none_values(d):
    """Recursively remove None values from dictionaries."""
    if isinstance(d, dict):
        return {k: remove_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [remove_none_values(v) for v in d if v is not None]
    else:
        return d


def ignore_none(func):
    """Decorator to remove None values from the data argument."""

    def wrapper(*args, **kwargs):
        if 'data' in kwargs:
            kwargs['data'] = remove_none_values(kwargs['data'])
        return func(*args, **kwargs)

    return wrapper


class DocumentBase(Generic[DocLike]):
    collection_ref: CollectionReference = None  # type: ignore
    _doc: Optional[DocLike] = None
    _db: Optional[Db] = None
    pydantic_model: Type[DocLike] = None  # type: ignore

    @property
    def db(self) -> Db:
        if self._db is None:
            self._db = Db.get_instance()
        return self._db

    def __init__(self, id: str, doc: dict | None = None):
        """
        Initialize the document.
        :param id: Id of the document, if id and doc are Falsy, the id will be created.
        """
        self.id = id
        self.debug = Db.is_development()
        i = self.collection_ref
        self.default_error = FirebaseError(
            "internal", "Error. Please contact support.")

        if not doc:
            self._init_doc()  # fetches the document from FB with provided ID
        else:
            self._doc = self.pydantic_model(**doc)

    def _init_doc(self):
        if not self.pydantic_model:
            raise FirebaseError(
                "internal", "You forgot to set pydantic_model.")
        if not self.collection_ref:
            raise FirebaseError(
                "internal", "You forgot to set collection_ref.")
        if not self.id:
            self.id = self.collection_ref.document().id
        doc_ref = self.collection_ref.document(self.id)
        doc = doc_ref.get()

        if not doc.exists:
            raise FirebaseError(
                "not-found", f"Doc not found for entity: {self.id}")

        doc_dict = doc.to_dict()

        if "lastUpdatedAt" not in doc_dict:
            doc_dict["lastUpdatedAt"] = doc_dict.get(
                "createdAt", datetime.now(timezone.utc))

        self._doc = self.pydantic_model(**doc.to_dict())

    @property
    def doc(self) -> DocLike:
        if self._doc:
            return self._doc
        else:
            raise FirebaseError("internal", "Document is None")

    def create_doc(self, data: dict, ref=None):
        now = self.db.server_timestamp
        self._doc = self.pydantic_model(**data)

        self._doc.createdAt = now
        self._doc.lastUpdatedAt = now
        
        new_data = {
            **data,
            "createdAt": now,
            "lastUpdatedAt": now,
        }
        
        if ref:
            ref.set(data)
        else:
            self.collection_ref.document(self.id).set(new_data)

    def save_doc(self):
        now = datetime.now(tz=timezone.utc)
        self._doc.lastUpdatedAt = now
        self.collection_ref.document(self.id).set(
            self.doc.model_dump(exclude_none=True), merge=True)  # type: ignore

    @ignore_none
    def merge_doc(self, data):
        now = datetime.now(tz=timezone.utc)
        self._doc.lastUpdatedAt = now
        data["lastUpdatedAt"] = now
        self.collection_ref.document(self.id).set(data, merge=True)

    @ignore_none
    def update_doc(self, data):
        now = datetime.now(tz=timezone.utc)
        try:
            self._doc.lastUpdatedAt = now
        except ValueError:
            pass
        data["lastUpdatedAt"] = now
        self.collection_ref.document(self.id).update(data)

    def update_doc_with_retry(self, data: dict, max_retries: int = 5):
        db = self.db.firestore
        doc_ref = self.get_doc_ref()

        def _update_in_transaction(transaction):
            now = datetime.now(tz=timezone.utc)
            update_data = data.copy()
            update_data["lastUpdatedAt"] = now
            transaction.update(doc_ref, update_data)
            try:
                if self._doc:
                    self._doc.lastUpdatedAt = now
            except (ValueError, AttributeError):
                pass

        try:
            db.run_transaction(_update_in_transaction,
                               max_attempts=max_retries)
            return True
        except Exception as e:
            logging.error(
                f"Transaction failed for document {self.id} after {max_retries} retries: {e}")
            return False

    def delete(self):
        if self.collection_ref:
            self.collection_ref.document(self.id).delete()
            self._doc = None

    def get_doc_path(self):
        return self.collection_ref.document(self.id).path

    def get_doc_ref(self):
        return self.collection_ref.document(self.id)

    def get_doc_snap(self):
        return self.collection_ref.document(self.id).get()