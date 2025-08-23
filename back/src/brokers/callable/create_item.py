"""Create item callable function."""

from typing import Optional
from firebase_functions import https_fn, options
from src.apis.Db import Db
from src.documents.items.Item import Item
from src.documents.categories.Category import Category
from src.models.function_types import CreateItemRequest, CreateItemResponse
from src.models.firestore_types import ItemDoc
from src.util.db_auth_wrapper import db_auth_wrapper
from src.util.cors_response import cors_response_on_call
from src.util.logger import get_logger
from src.models.user_types import User

logger = get_logger(__name__)


@https_fn.on_call(
    cors=options.CorsOptions(cors_origins=["*"]),
    ingress=options.IngressSetting.ALLOW_ALL,
)
def create_item_callable(req: https_fn.CallableRequest) -> CreateItemResponse:
    """Create a new item.
    
    Args:
        req: Firebase callable request containing CreateItemRequest data
        
    Returns:
        CreateItemResponse with success status and item ID
    """
    # Handle CORS preflight
    options_response = cors_response_on_call(req.raw_request)
    if options_response:
        return options_response
    
    try:
        # Authenticate user
        uid = db_auth_wrapper(req)
        
        # Validate request data
        name = req.data.get("name")
        category_id = req.data.get("categoryId")
        
        if not name:
            raise https_fn.HttpsError(
                https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                "Item name is required"
            )
        
        if not category_id:
            raise https_fn.HttpsError(
                https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                "Category ID is required"
            )
        
        # Verify category exists and user has permission
        try:
            category = Category(category_id)
            if not category.validate_permissions(uid):
                raise https_fn.HttpsError(
                    https_fn.FunctionsErrorCode.PERMISSION_DENIED,
                    "You don't have permission to add items to this category"
                )
        except Exception as e:
            logger.error(f"Category validation failed: {e}")
            raise https_fn.HttpsError(
                https_fn.FunctionsErrorCode.NOT_FOUND,
                "Category not found"
            )
        
        # Check user limits (example with free tier limitation)
        user = User(uid)
        if not user.is_paid():
            db = Db.get_instance()
            items_count = (
                db.collections["items"]
                .where("ownerUid", "==", uid)
                .where("status", "==", "active")
                .count()
                .get()
            )
            
            if items_count and items_count[0][0].value >= 10:
                raise https_fn.HttpsError(
                    https_fn.FunctionsErrorCode.RESOURCE_EXHAUSTED,
                    "Free tier limit reached. Please upgrade to create more items."
                )
        
        # Create new item document
        db = Db.get_instance()
        new_doc = db.collections["items"].document()
        
        item_data = ItemDoc(
            id=new_doc.id,
            name=name,
            description=req.data.get("description"),
            categoryId=category_id,
            ownerUid=uid,
            status="active",
            tags=req.data.get("tags", []),
            metadata=req.data.get("metadata", {}),
            createdAt=db.get_created_at(),
            lastUpdatedAt=db.get_created_at(),
        )
        
        # Save to Firestore
        new_doc.set(item_data.model_dump())
        
        # Log activity
        item = Item(new_doc.id, item_data.model_dump())
        item.log_activity("created", uid, {"source": "callable_function"})
        
        logger.info(f"Created new item {new_doc.id} for user {uid}")
        
        return CreateItemResponse(
            success=True,
            itemId=new_doc.id,
            message="Item created successfully"
        )
        
    except https_fn.HttpsError:
        raise
    except Exception as e:
        logger.error(f"Failed to create item: {e}")
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INTERNAL,
            "Failed to create item. Please try again later."
        )