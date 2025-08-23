"""Trigger function for item deletion."""

from firebase_functions import firestore_fn
from src.util.logger import get_logger

logger = get_logger(__name__)


@firestore_fn.on_document_deleted(
    document="items/{itemId}",
    timeout_sec=60,
)
def on_item_deleted(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]):
    """Handle item deletion events.
    
    Args:
        event: Firestore document deletion event
    """
    try:
        # Get document data
        item_id = event.params["itemId"]
        item_data = event.data.to_dict()
        
        logger.info(f"Processing deleted item: {item_id}")
        
        # Clean up related data
        from src.apis.Db import Db
        db = Db.get_instance()
        
        # Delete all activities for this item
        activities_collection = db.collections["itemActivities"](item_id)
        activities = activities_collection.get()
        
        for activity in activities:
            activity.reference.delete()
            
        logger.info(f"Deleted {len(activities)} activities for item {item_id}")
        
        # Update category counter
        category_id = item_data.get("categoryId")
        if category_id:
            category_path = f"categories/{category_id}"
            db.increment_counter(category_path, "itemCount", -1)
            
            if item_data.get("status") == "active":
                db.increment_counter(category_path, "activeItemCount", -1)
        
        # Clean up any storage files associated with this item
        if item_data.get("files"):
            try:
                folder_path = f"items/{item_id}/"
                db.remove_folder_files(folder_path)
                logger.info(f"Cleaned up storage files for item {item_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up storage for item {item_id}: {e}")
        
        logger.info(f"Successfully processed deleted item: {item_id}")
        
    except Exception as e:
        logger.error(f"Error processing deleted item: {e}")
        raise