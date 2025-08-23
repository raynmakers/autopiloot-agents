"""Test setup utilities for item flow tests."""

import pytest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.apis.Db import Db


class ItemFlowSetup:
    """Setup class for item flow tests."""

    def __init__(self, db: "Db", user_id: str, category_id: str):
        self.db = db
        self.user_id = user_id
        self.category_id = category_id


@pytest.fixture(scope="function")
def item_flow_setup(firebase_app) -> ItemFlowSetup:
    """Set up the environment and create test documents for item flow tests."""
    from src.apis.Db import Db
    from src.models.firestore_types import UserDoc, CategoryDoc
    
    db = Db.get_instance()
    
    # Create test user
    user_ref = db.collections["users"].document()
    user_data = UserDoc(
        id=user_ref.id,
        email="test@example.com",
        isPaid=False,
        subscriptionStatus="free",
        createdAt=db.get_created_at(),
        lastUpdatedAt=db.get_created_at(),
    )
    user_ref.set(user_data.model_dump())
    
    # Create test category
    category_ref = db.collections["categories"].document()
    category_data = CategoryDoc(
        id=category_ref.id,
        name="Test Category",
        description="Test category for items",
        ownerUid=user_ref.id,
        displayOrder=0,
        isActive=True,
        createdAt=db.get_created_at(),
        lastUpdatedAt=db.get_created_at(),
    )
    category_ref.set(category_data.model_dump())
    
    yield ItemFlowSetup(db, user_ref.id, category_ref.id)
    
    # Cleanup
    try:
        user_ref.delete()
        category_ref.delete()
        # Clean up any items created during tests
        items = db.collections["items"].where("ownerUid", "==", user_ref.id).get()
        for item in items:
            item.reference.delete()
    except:
        pass

