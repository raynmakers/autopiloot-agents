"""Item document class."""

from typing import Optional, List
from src.documents.DocumentBase import DocumentBase
from src.apis.Db import Db
from src.models.firestore_types import ItemDoc, ItemActivityDoc
from src.util.logger import get_logger

logger = get_logger(__name__)


class Item(DocumentBase[ItemDoc]):
    """Item document class for managing items in Firestore."""
    
    pydantic_model = ItemDoc
    
    def __init__(self, id: str, doc: Optional[dict] = None):
        """Initialize Item document.
        
        Args:
            id: Document ID
            doc: Optional document data dictionary
        """
        # Override db property to use Db
        self._db = Db.get_instance()
        self.collection_ref = self.db.collections["items"]
        super().__init__(id, doc)
    
    @property
    def db(self) -> Db:
        """Get Db instance."""
        if self._db is None:
            self._db = Db.get_instance()
        return self._db
    
    @property
    def doc(self) -> ItemDoc:
        """Get the typed document."""
        return super().doc
    
    def update_status(self, status: str):
        """Update item status.
        
        Args:
            status: New status value
        """
        self.update_doc({"status": status})
        logger.info(f"Updated item {self.id} status to {status}")
    
    def add_tags(self, tags: List[str]):
        """Add tags to the item.
        
        Args:
            tags: List of tags to add
        """
        current_tags = self.doc.tags or []
        new_tags = list(set(current_tags + tags))
        self.update_doc({"tags": new_tags})
    
    def remove_tags(self, tags: List[str]):
        """Remove tags from the item.
        
        Args:
            tags: List of tags to remove
        """
        current_tags = self.doc.tags or []
        updated_tags = [tag for tag in current_tags if tag not in tags]
        self.update_doc({"tags": updated_tags})
    
    def archive(self):
        """Archive the item."""
        self.update_status("archived")
    
    def activate(self):
        """Activate the item."""
        self.update_status("active")
    
    def log_activity(self, action: str, user_id: str, details: Optional[dict] = None):
        """Log an activity for this item.
        
        Args:
            action: Action performed
            user_id: ID of the user performing the action
            details: Optional additional details
        """
        activities_collection = self.db.collections["itemActivities"](self.id)
        activity_doc = activities_collection.document()
        
        activity = ItemActivityDoc(
            id=activity_doc.id,
            itemId=self.id,
            action=action,
            userId=user_id,
            details=details,
            createdAt=self.db.get_created_at(),
            lastUpdatedAt=self.db.get_created_at(),
        )
        
        activity_doc.set(activity.model_dump())
        logger.info(f"Logged activity {action} for item {self.id}")
    
    def get_activities(self, limit: int = 10) -> List[ItemActivityDoc]:
        """Get recent activities for this item.
        
        Args:
            limit: Maximum number of activities to return
            
        Returns:
            List of ItemActivityDoc objects
        """
        activities_collection = self.db.collections["itemActivities"](self.id)
        activities = (
            activities_collection
            .order_by("createdAt", direction="DESCENDING")
            .limit(limit)
            .get()
        )
        
        return [
            ItemActivityDoc(**activity.to_dict())
            for activity in activities
        ]
    
    def validate_permissions(self, user_id: str) -> bool:
        """Check if user has permissions for this item.
        
        Args:
            user_id: ID of the user to check
            
        Returns:
            True if user has permissions, False otherwise
        """
        return self.doc.ownerUid == user_id
    
    def delete(self):
        """Delete the item and all associated data."""
        try:
            # Delete all activities
            activities_collection = self.db.collections["itemActivities"](self.id)
            activities = activities_collection.get()
            
            for activity in activities:
                activity.reference.delete()
            
            # Delete the item document
            super().delete()
            logger.info(f"Deleted item {self.id} and all associated data")
            
        except Exception as e:
            logger.error(f"Error deleting item {self.id}: {e}")
            raise