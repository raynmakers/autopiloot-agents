"""Get item callable function."""

from firebase_functions import https_fn, options
from src.documents.items.Item import Item
from src.models.function_types import GetItemRequest, GetItemResponse
from src.util.db_auth_wrapper import db_auth_wrapper
from src.util.cors_response import cors_response_on_call
from src.util.logger import get_logger

logger = get_logger(__name__)


@https_fn.on_call(
    cors=options.CorsOptions(cors_origins=["*"]),
    ingress=options.IngressSetting.ALLOW_ALL,
)
def get_item_callable(req: https_fn.CallableRequest) -> GetItemResponse:
    """Get an item by ID.
    
    Args:
        req: Firebase callable request containing GetItemRequest data
        
    Returns:
        GetItemResponse with item data
    """
    # Handle CORS preflight
    options_response = cors_response_on_call(req.raw_request)
    if options_response:
        return options_response
    
    try:
        # Authenticate user
        uid = db_auth_wrapper(req)
        
        # Validate request data
        item_id = req.data.get("itemId")
        include_activities = req.data.get("includeActivities", False)
        
        if not item_id:
            raise https_fn.HttpsError(
                https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                "Item ID is required"
            )
        
        # Get item
        try:
            item = Item(item_id)
        except Exception as e:
            logger.error(f"Item not found: {e}")
            raise https_fn.HttpsError(
                https_fn.FunctionsErrorCode.NOT_FOUND,
                "Item not found"
            )
        
        # Check permissions
        if not item.validate_permissions(uid):
            raise https_fn.HttpsError(
                https_fn.FunctionsErrorCode.PERMISSION_DENIED,
                "You don't have permission to view this item"
            )
        
        # Log view activity
        item.log_activity("viewed", uid, {"source": "callable_function"})
        
        # Prepare response
        response_data = GetItemResponse(
            success=True,
            item=item.doc.model_dump(),
            message="Item retrieved successfully"
        )
        
        # Include activities if requested
        if include_activities:
            activities = item.get_activities(limit=20)
            response_data["activities"] = [
                activity.model_dump() for activity in activities
            ]
        
        logger.info(f"Retrieved item {item_id} for user {uid}")
        
        return response_data
        
    except https_fn.HttpsError:
        raise
    except Exception as e:
        logger.error(f"Failed to get item: {e}")
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INTERNAL,
            "Failed to retrieve item. Please try again later."
        )