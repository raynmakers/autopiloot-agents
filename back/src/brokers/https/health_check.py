"""Health check HTTP endpoint."""

from firebase_functions import https_fn, options
from src.apis.Db import Db
from src.util.cors_response import handle_cors_preflight, create_cors_response
from src.util.logger import get_logger

logger = get_logger(__name__)


@https_fn.on_request(
    ingress=options.IngressSetting.ALLOW_ALL,
    timeout_sec=30,
)
def health_check(req: https_fn.Request):
    """Health check endpoint for monitoring.
    
    Args:
        req: Firebase HTTP request
        
    Returns:
        Health status response
    """
    try:
        # Handle CORS preflight
        handle_cors_preflight(req, ["GET", "OPTIONS"])
        
        # Check database connection
        db = Db.get_instance()
        db_status = "healthy"
        
        try:
            # Perform a simple query to verify database connectivity
            test_collection = db.firestore.collection("_health_check")
            test_collection.limit(1).get()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = "unhealthy"
        
        # Prepare response
        response_data = {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "timestamp": db.timestamp_now().isoformat(),
            "environment": "production" if db.is_production() else "development",
            "services": {
                "database": db_status,
                "functions": "healthy"
            }
        }
        
        status_code = 200 if db_status == "healthy" else 503
        
        logger.info(f"Health check: {response_data['status']}")
        
        return create_cors_response(response_data, status_code)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return create_cors_response(
            {
                "status": "unhealthy",
                "error": str(e)
            },
            status=503
        )