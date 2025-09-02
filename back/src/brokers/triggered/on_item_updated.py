"""Trigger function for item updates."""

from firebase_functions import firestore_fn
from src.documents.items.Item import Item
from src.util.logger import get_logger
from src.documents.categories.Category import Category

logger = get_logger(__name__)


def handle_item_updated(item_id: str, before_data: dict, after_data: dict):
    """Handle item update business logic.
    
    Args:
        item_id: ID of the updated item
        before_data: Item data before update
        after_data: Item data after update
    """
    logger.info(f"Processing updated item: {item_id}")
    
    # Check what changed
    status_changed = before_data.get("status") != after_data.get("status")
    category_changed = before_data.get("categoryId") != after_data.get("categoryId")
    
    # Handle status change
    if status_changed:
        old_status = before_data.get("status")
        new_status = after_data.get("status")
        
        logger.info(f"Item {item_id} status changed from {old_status} to {new_status}")
        
        # Update counters based on status change using proper Category class
        category = Category(after_data.get('categoryId'))
        
        if old_status == "active" and new_status != "active":
            # Item became inactive - decrement active count
            # Note: activeItemCount is not implemented in Category class yet
            # This would need to be added to the Category class if needed
            pass
            
        elif old_status != "active" and new_status == "active":
            # Item became active - increment active count  
            # Note: activeItemCount is not implemented in Category class yet
            # This would need to be added to the Category class if needed
            pass
    
    # Handle category change
    if category_changed:
        old_category = before_data.get("categoryId")
        new_category = after_data.get("categoryId")
        
        logger.info(f"Item {item_id} moved from category {old_category} to {new_category}")
        
        # Update counters for both categories using proper Category class
        from src.documents.categories.Category import Category
        
        if old_category:
            old_cat = Category(old_category)
            old_cat.decrement_item_count(1)
        
        if new_category:
            new_cat = Category(new_category)
            new_cat.increment_item_count(1)
    
    # Log update activity
    item = Item(item_id, after_data)
    item.log_activity(
        action="system_updated",
        user_id="system",
        details={
            "trigger": "on_item_updated",
            "status_changed": status_changed,
            "category_changed": category_changed
        }
    )
    
    logger.info(f"Successfully processed updated item: {item_id}")


@firestore_fn.on_document_updated(
    document="items/{itemId}",
    timeout_sec=60,
)
def on_item_updated(event: firestore_fn.Event[firestore_fn.Change[firestore_fn.DocumentSnapshot]]):
    """Handle item update events.
    
    Args:
        event: Firestore document update event
    """
    try:
        # Get document data
        item_id = event.params["itemId"]
        before_data = event.data.before.to_dict()
        after_data = event.data.after.to_dict()
        
        # Call the handler function
        handle_item_updated(item_id, before_data, after_data)
        
    except Exception as e:
        logger.error(f"Error processing updated item: {e}")
        raise