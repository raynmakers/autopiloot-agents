"""Example callable function."""

from firebase_functions import https_fn, options
from src.util.db_auth_wrapper import db_auth_wrapper
from src.util.cors_response import cors_response_on_call
from src.util.logger import get_logger

logger = get_logger(__name__)


@https_fn.on_call(
    cors=options.CorsOptions(cors_origins=["*"]),
    ingress=options.IngressSetting.ALLOW_ALL,
)
def example_callable(req: https_fn.CallableRequest):
    """Example callable function.
    
    Args:
        req: Firebase callable request
        
    Returns:
        Response dictionary
    """
    # Handle CORS preflight
    options_response = cors_response_on_call(req.raw_request)
    if options_response:
        return options_response
    
    try:
        # Authenticate user
        uid = db_auth_wrapper(req)
        
        # Get request data
        message = req.data.get("message", "Hello")
        
        logger.info(f"Example callable invoked by user {uid} with message: {message}")
        
        return {
            "success": True,
            "echo": message,
            "userId": uid,
            "timestamp": https_fn.firestore.SERVER_TIMESTAMP
        }
        
    except https_fn.HttpsError:
        raise
    except Exception as e:
        logger.error(f"Example callable failed: {e}")
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.INTERNAL,
            "An error occurred processing your request"
        )