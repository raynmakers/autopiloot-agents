"""Category document class."""

from typing import Optional, List
from src.documents.DocumentBase import DocumentBase
from src.apis.Db import Db
from src.models.firestore_types import CategoryDoc
from src.util.logger import get_logger

logger = get_logger(__name__)


class Category(DocumentBase[CategoryDoc]):
    """Category document class for managing categories in Firestore."""
    
    pydantic_model = CategoryDoc
    
    def __init__(self, id: str, doc: Optional[dict] = None):
        """Initialize Category document.
        
        Args:
            id: Document ID
            doc: Optional document data dictionary
        """
        # Override db property to use Db
        self._db = Db.get_instance()
        self.collection_ref = self.db.collections["categories"]
        super().__init__(id, doc)
    
    @property
    def db(self) -> Db:
        """Get Db instance."""
        if self._db is None:
            self._db = Db.get_instance()
        return self._db
    
    @property
    def doc(self) -> CategoryDoc:
        """Get the typed document."""
        return super().doc
    
    def toggle_active(self):
        """Toggle the active status of the category."""
        new_status = not self.doc.isActive
        self.update_doc({"isActive": new_status})
        logger.info(f"Toggled category {self.id} active status to {new_status}")
    
    def update_display_order(self, new_order: int):
        """Update the display order of the category.
        
        Args:
            new_order: New display order value
        """
        self.update_doc({"displayOrder": new_order})
    
    def get_subcategories(self) -> List[CategoryDoc]:
        """Get all subcategories of this category.
        
        Returns:
            List of CategoryDoc objects
        """
        subcategories = (
            self.collection_ref
            .where("parentId", "==", self.id)
            .order_by("displayOrder")
            .get()
        )
        
        return [
            CategoryDoc(**subcategory.to_dict())
            for subcategory in subcategories
        ]
    
    def get_items_count(self) -> int:
        """Get the count of items in this category.
        
        Returns:
            Number of items in the category
        """
        items_count = (
            self.db.collections["items"]
            .where("categoryId", "==", self.id)
            .where("status", "==", "active")
            .count()
            .get()
        )
        
        return items_count[0][0].value if items_count else 0
    
    def validate_permissions(self, user_id: str) -> bool:
        """Check if user has permissions for this category.
        
        Args:
            user_id: ID of the user to check
            
        Returns:
            True if user has permissions, False otherwise
        """
        return self.doc.ownerUid == user_id