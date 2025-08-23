"""Item service for complex item operations."""

from typing import List, Optional, Dict, Any
from src.documents.items.Item import Item
from src.documents.categories.Category import Category
from src.models.firestore_types import ItemDoc
from src.apis.Db import Db
from src.util.logger import get_logger

logger = get_logger(__name__)


class ItemService:
    """Service for orchestrating complex item operations."""
    
    def __init__(self, item_id: Optional[str] = None):
        """Initialize ItemService.
        
        Args:
            item_id: Optional item ID to work with
        """
        self.item_id = item_id
        self.db = Db.get_instance()
    
    def bulk_update_category(self, old_category_id: str, new_category_id: str, user_id: str) -> int:
        """Move all items from one category to another.
        
        Args:
            old_category_id: Source category ID
            new_category_id: Target category ID
            user_id: User performing the operation
            
        Returns:
            Number of items moved
        """
        # Verify categories exist and user has permissions
        old_category = Category(old_category_id)
        new_category = Category(new_category_id)
        
        if not old_category.validate_permissions(user_id):
            raise PermissionError("No permission for source category")
        
        if not new_category.validate_permissions(user_id):
            raise PermissionError("No permission for target category")
        
        # Get all items in old category
        items_query = (
            self.db.collections["items"]
            .where("categoryId", "==", old_category_id)
            .where("ownerUid", "==", user_id)
        )
        
        items = items_query.get()
        count = 0
        
        # Update each item
        for item_doc in items:
            item = Item(item_doc.id, item_doc.to_dict())
            item.update_doc({"categoryId": new_category_id})
            item.log_activity(
                "category_changed",
                user_id,
                {
                    "old_category": old_category_id,
                    "new_category": new_category_id,
                    "bulk_operation": True
                }
            )
            count += 1
        
        logger.info(f"Moved {count} items from {old_category_id} to {new_category_id}")
        return count
    
    def duplicate_item(self, item_id: str, user_id: str, new_name: Optional[str] = None) -> str:
        """Create a duplicate of an existing item.
        
        Args:
            item_id: ID of item to duplicate
            user_id: User performing the operation
            new_name: Optional name for the duplicate
            
        Returns:
            ID of the duplicated item
        """
        # Get original item
        original = Item(item_id)
        
        if not original.validate_permissions(user_id):
            raise PermissionError("No permission to duplicate this item")
        
        # Create duplicate
        new_doc = self.db.collections["items"].document()
        
        duplicate_data = ItemDoc(
            id=new_doc.id,
            name=new_name or f"{original.doc.name} (Copy)",
            description=original.doc.description,
            categoryId=original.doc.categoryId,
            ownerUid=user_id,
            status="active",
            tags=original.doc.tags.copy() if original.doc.tags else [],
            metadata={
                **original.doc.metadata,
                "duplicated_from": item_id,
                "duplicated_at": self.db.timestamp_now().isoformat()
            },
            createdAt=self.db.get_created_at(),
            lastUpdatedAt=self.db.get_created_at(),
        )
        
        new_doc.set(duplicate_data.model_dump())
        
        # Log activity for both items
        duplicate = Item(new_doc.id, duplicate_data.model_dump())
        duplicate.log_activity("duplicated", user_id, {"source_item": item_id})
        original.log_activity("was_duplicated", user_id, {"duplicate_item": new_doc.id})
        
        logger.info(f"Duplicated item {item_id} to {new_doc.id}")
        return new_doc.id
    
    def batch_archive(self, item_ids: List[str], user_id: str) -> Dict[str, bool]:
        """Archive multiple items at once.
        
        Args:
            item_ids: List of item IDs to archive
            user_id: User performing the operation
            
        Returns:
            Dictionary mapping item IDs to success status
        """
        results = {}
        
        for item_id in item_ids:
            try:
                item = Item(item_id)
                
                if not item.validate_permissions(user_id):
                    results[item_id] = False
                    logger.warning(f"No permission to archive item {item_id}")
                    continue
                
                item.archive()
                item.log_activity("batch_archived", user_id, {"batch_size": len(item_ids)})
                results[item_id] = True
                
            except Exception as e:
                logger.error(f"Failed to archive item {item_id}: {e}")
                results[item_id] = False
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Archived {success_count}/{len(item_ids)} items")
        
        return results
    
    def search_items(
        self,
        user_id: str,
        query: Optional[str] = None,
        category_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[ItemDoc]:
        """Search for items based on various criteria.
        
        Args:
            user_id: User performing the search
            query: Text query to search in name/description
            category_id: Filter by category
            tags: Filter by tags
            status: Filter by status
            limit: Maximum number of results
            
        Returns:
            List of matching ItemDoc objects
        """
        # Start with base query
        items_query = self.db.collections["items"].where("ownerUid", "==", user_id)
        
        # Apply filters
        if category_id:
            items_query = items_query.where("categoryId", "==", category_id)
        
        if status:
            items_query = items_query.where("status", "==", status)
        
        if tags:
            # Firestore limitation: can only use array-contains for one value
            items_query = items_query.where("tags", "array_contains", tags[0])
        
        # Execute query
        items = items_query.limit(limit).get()
        
        results = []
        for item_doc in items:
            item_data = ItemDoc(**item_doc.to_dict())
            
            # Additional filtering for multiple tags
            if tags and len(tags) > 1:
                if not all(tag in (item_data.tags or []) for tag in tags):
                    continue
            
            # Text search in name/description (basic implementation)
            if query:
                query_lower = query.lower()
                name_match = query_lower in item_data.name.lower()
                desc_match = (
                    item_data.description and 
                    query_lower in item_data.description.lower()
                )
                if not (name_match or desc_match):
                    continue
            
            results.append(item_data)
        
        logger.info(f"Search returned {len(results)} items for user {user_id}")
        return results