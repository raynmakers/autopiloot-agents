"""Firestore document type definitions using Pydantic."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BaseDoc(BaseModel):
    """Base document type for all Firestore documents."""
    
    createdAt: datetime
    lastUpdatedAt: datetime


class ItemDoc(BaseDoc):
    """Example item document type."""
    
    id: str
    name: str
    description: Optional[str] = None
    categoryId: str
    ownerUid: str
    status: str = "active"  # active, archived, deleted
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # Timestamps are inherited from BaseDoc
    # createdAt: datetime
    # lastUpdatedAt: datetime


class CategoryDoc(BaseDoc):
    """Example category document type."""
    
    id: str
    name: str
    description: Optional[str] = None
    parentId: Optional[str] = None
    ownerUid: str
    displayOrder: int = 0
    isActive: bool = True
    itemCount: int = 0


class ItemActivityDoc(BaseDoc):
    """Example activity log document type."""
    
    id: str
    itemId: str
    action: str  # created, updated, deleted, viewed, shared
    userId: str
    details: Optional[Dict[str, Any]] = None
    ipAddress: Optional[str] = None
    userAgent: Optional[str] = None


class UserDoc(BaseDoc):
    """User document type."""
    
    id: str
    email: Optional[str] = None
    displayName: Optional[str] = None
    isPaid: bool = False
    subscriptionStatus: str = "free"
    metadata: Dict[str, Any] = Field(default_factory=dict)