"""Trigger function for item creation."""

from firebase_functions import firestore_fn
from src.documents.items.Item import Item
from src.util.logger import get_logger

logger = get_logger(__name__)


def handle_item_created(item_id: str, item_data: dict):
    """Handle item creation business logic.
    
    Args:
        item_id: ID of the created item
        item_data: Item document data
    """
    logger.info(f"Processing created item: {item_id}")
    
    # Initialize item document
    item = Item(item_id, item_data)
    
    # Perform post-creation tasks
    # Example: Send notification, update counters, etc.
    
    # Update category item count
    from src.apis.Db import Db
    db = Db.get_instance()
    
    category_path = f"categories/{item.doc.categoryId}"
    db.increment_counter(category_path, "itemCount", 1)
    
    # Log system activity
    item.log_activity(
        action="system_processed",
        user_id="system",
        details={
            "trigger": "on_item_created",
            "category_updated": item.doc.categoryId
        }
    )
    
    logger.info(f"Successfully processed created item: {item_id}")


@firestore_fn.on_document_created(
    document="items/{itemId}",
    timeout_sec=60,
)
def on_item_created(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]):
    """Handle item creation events.
    
    Args:
        event: Firestore document creation event
    """
    try:
        # Get document data
        item_id = event.params["itemId"]
        item_data = event.data.to_dict()
        
        # Call the handler function
        handle_item_created(item_id, item_data)
        
    except Exception as e:
        logger.error(f"Error processing created item: {e}")
        raise