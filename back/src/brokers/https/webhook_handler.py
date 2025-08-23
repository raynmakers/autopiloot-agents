"""Webhook handler HTTP endpoint."""

import json
import hmac
import hashlib
from firebase_functions import https_fn, options
from src.models.function_types import WebhookPayload
from src.util.cors_response import handle_cors_preflight, create_cors_response
from src.util.logger import get_logger
import os

logger = get_logger(__name__)


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify webhook signature.
    
    Args:
        payload: Request payload as string
        signature: Signature from webhook header
        secret: Webhook secret
        
    Returns:
        True if signature is valid
    """
    expected_signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


@https_fn.on_request(
    ingress=options.IngressSetting.ALLOW_ALL,
    timeout_sec=60,
)
def webhook_handler(req: https_fn.Request):
    """Handle incoming webhooks.
    
    Args:
        req: Firebase HTTP request
        
    Returns:
        Webhook processing response
    """
    try:
        # Handle CORS preflight
        handle_cors_preflight(req, ["POST", "OPTIONS"])
        
        # Verify request method
        if req.method != "POST":
            return create_cors_response(
                {"error": "Method not allowed"},
                status=405
            )
        
        # Get webhook secret from environment
        webhook_secret = os.environ.get("WEBHOOK_SECRET")
        
        # Verify signature if secret is configured
        if webhook_secret:
            signature = req.headers.get("X-Webhook-Signature")
            if not signature:
                logger.warning("Webhook received without signature")
                return create_cors_response(
                    {"error": "Missing signature"},
                    status=401
                )
            
            raw_body = req.get_data(as_text=True)
            if not verify_webhook_signature(raw_body, signature, webhook_secret):
                logger.warning("Invalid webhook signature")
                return create_cors_response(
                    {"error": "Invalid signature"},
                    status=401
                )
        
        # Parse webhook payload
        try:
            data = req.get_json()
            webhook = WebhookPayload(**data)
        except Exception as e:
            logger.error(f"Invalid webhook payload: {e}")
            return create_cors_response(
                {"error": "Invalid payload"},
                status=400
            )
        
        # Process webhook based on event type
        logger.info(f"Processing webhook event: {webhook.event}")
        
        # Route to appropriate handler based on event type
        if webhook.event == "item.created":
            # Handle item created event
            pass
        elif webhook.event == "item.updated":
            # Handle item updated event
            pass
        elif webhook.event == "item.deleted":
            # Handle item deleted event
            pass
        else:
            logger.warning(f"Unknown webhook event: {webhook.event}")
            return create_cors_response(
                {"error": f"Unknown event: {webhook.event}"},
                status=400
            )
        
        # Return success response
        return create_cors_response(
            {
                "success": True,
                "event": webhook.event,
                "message": "Webhook processed successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return create_cors_response(
            {"error": "Internal server error"},
            status=500
        )