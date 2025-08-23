"""CORS response utility for HTTP functions."""

from typing import Optional, Dict, Any
from flask import Response, jsonify
from firebase_functions import https_fn


def cors_response_on_call(raw_request) -> Optional[Dict[str, Any]]:
    """Handle CORS for callable functions.
    
    Args:
        raw_request: Raw HTTP request object
        
    Returns:
        CORS response for OPTIONS request, None otherwise
    """
    if raw_request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)
    return None


def handle_cors_preflight(req: https_fn.Request, allowed_methods: list = None):
    """Handle CORS preflight requests for HTTP functions.
    
    Args:
        req: Firebase HTTP request object
        allowed_methods: List of allowed HTTP methods
        
    Raises:
        Response: CORS preflight response for OPTIONS requests
    """
    if req.method == "OPTIONS":
        methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": ", ".join(methods),
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        response = Response("", status=204)
        for key, value in headers.items():
            response.headers[key] = value
        raise response


def add_cors_headers(response: Response) -> Response:
    """Add CORS headers to a response.
    
    Args:
        response: Flask response object
        
    Returns:
        Response with CORS headers added
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


def create_cors_response(data: Dict[str, Any], status: int = 200) -> Response:
    """Create a JSON response with CORS headers.
    
    Args:
        data: Response data dictionary
        status: HTTP status code
        
    Returns:
        Flask response with CORS headers
    """
    response = jsonify(data)
    response.status_code = status
    return add_cors_headers(response)