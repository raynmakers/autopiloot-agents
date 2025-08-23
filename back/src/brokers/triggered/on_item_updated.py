"""Trigger function for item updates."""

from firebase_functions import firestore_fn
from src.documents.items.Item import Item
from src.util.logger import get_logger

logger = get_logger(__name__)


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
        
        logger.info(f"Processing updated item: {item_id}")
        
        # Check what changed
        status_changed = before_data.get("status") != after_data.get("status")
        category_changed = before_data.get("categoryId") != after_data.get("categoryId")
        
        # Handle status change
        if status_changed:
            old_status = before_data.get("status")
            new_status = after_data.get("status")
            
            logger.info(f"Item {item_id} status changed from {old_status} to {new_status}")
            
            # Update counters based on status change
            if old_status == "active" and new_status != "active":
                # Item became inactive
                from src.apis.Db import Db
                db = Db.get_instance()
                category_path = f"categories/{after_data.get('categoryId')}"
                db.increment_counter(category_path, "activeItemCount", -1)
                
            elif old_status != "active" and new_status == "active":
                # Item became active
                from src.apis.Db import Db
                db = Db.get_instance()
                category_path = f"categories/{after_data.get('categoryId')}"
                db.increment_counter(category_path, "activeItemCount", 1)
        
        # Handle category change
        if category_changed:
            old_category = before_data.get("categoryId")
            new_category = after_data.get("categoryId")
            
            logger.info(f"Item {item_id} moved from category {old_category} to {new_category}")
            
            # Update counters for both categories
            from src.apis.Db import Db
            db = Db.get_instance()
            
            if old_category:
                old_category_path = f"categories/{old_category}"
                db.increment_counter(old_category_path, "itemCount", -1)
            
            if new_category:
                new_category_path = f"categories/{new_category}"
                db.increment_counter(new_category_path, "itemCount", 1)
        
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
        
    except Exception as e:
        logger.error(f"Error processing updated item: {e}")
        raise