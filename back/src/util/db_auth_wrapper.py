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
        HttpsError: If authentication fails
    """
    if not req.auth:
        logger.warning("Unauthenticated request")
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            "The function must be called while authenticated."
        )
    
    db = Db.get_instance()
    
    # In production/development, verify App Check token
    if (db.is_production() or db.is_development()) and not req.app:
        logger.warning("Request without App Check verification")
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
            "The function must be called from an App Check verified app."
        )
    
    return req.auth.uid