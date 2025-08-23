"""Exceptions package initialization."""

from .CustomError import (
    ProjectError,
    ValidationError,
    PermissionError,
    NotFoundError,
    DuplicateError,
    LimitExceededError,
    ExternalServiceError,
)

__all__ = [
    "ProjectError",
    "ValidationError",
    "PermissionError",
    "NotFoundError",
    "DuplicateError",
    "LimitExceededError",
    "ExternalServiceError",
]