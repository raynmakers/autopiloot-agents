"""Utility type definitions."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel


class Status(str, Enum):
    """Status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ErrorResponse(BaseModel):
    """Standard error response structure."""
    error: bool = True
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Standard success response structure."""
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = 1
    limit: int = 20
    orderBy: str = "createdAt"
    orderDirection: str = "desc"