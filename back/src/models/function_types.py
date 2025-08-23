"""Function request and response type definitions."""

from typing import Optional, List, Dict, Any, TypedDict
from pydantic import BaseModel


class CreateItemRequest(TypedDict):
    """Request structure for create_item_callable."""
    name: str
    description: Optional[str]
    categoryId: str
    tags: Optional[List[str]]
    metadata: Optional[Dict[str, Any]]


class CreateItemResponse(TypedDict):
    """Response structure for create_item_callable."""
    success: bool
    itemId: Optional[str]
    message: Optional[str]


class GetItemRequest(TypedDict):
    """Request structure for get_item_callable."""
    itemId: str
    includeActivities: Optional[bool]


class GetItemResponse(TypedDict):
    """Response structure for get_item_callable."""
    success: bool
    item: Optional[Dict[str, Any]]
    activities: Optional[List[Dict[str, Any]]]
    message: Optional[str]


class WebhookPayload(BaseModel):
    """Webhook payload structure."""
    event: str
    data: Dict[str, Any]
    timestamp: str
    signature: Optional[str] = None