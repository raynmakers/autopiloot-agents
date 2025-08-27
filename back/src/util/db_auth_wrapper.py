"""Database authentication wrapper utility."""

from firebase_functions import https_fn
from src.apis.Db import Db
from src.util.logger import get_logger

logger = get_logger(__name__)


def db_auth_wrapper(req: https_fn.CallableRequest) -> str:
    """Wrapper for authenticating Firebase callable requests.
    
    Args:
        req: Firebase callable request object
        
    Returns:
        Authenticated user ID
        
    Raises:
        HttpsError: If authentication fails (not in emulator/dev mode)
    """
    db = Db.get_instance()
    
    # Skip authentication when running in development/emulator
    if db.is_development():
        # For tests, check if a User-Id header is provided (for test identification)
        # The header is accessible via req.raw_request.headers
        if hasattr(req, 'raw_request') and req.raw_request.headers:
            user_id = req.raw_request.headers.get('User-Id')
            if user_id:
                return user_id
        return "test-user-id"
    
    if not req.auth:
        logger.warning("Unauthenticated request")
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            "The function must be called while authenticated."
        )
    
    return req.auth.uid