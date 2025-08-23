"""Custom exception classes for the project."""

from typing import Optional, Dict, Any


class ProjectError(Exception):
    """Base exception class for project-specific errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize ProjectError.
        
        Args:
            message: Error message
            code: Optional error code
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.code = code or "PROJECT_ERROR"
        self.details = details or {}


class ValidationError(ProjectError):
    """Raised when validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """Initialize ValidationError.
        
        Args:
            message: Error message
            field: Optional field that failed validation
            details: Optional additional error details
        """
        if field:
            details = details or {}
            details["field"] = field
        
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class PermissionError(ProjectError):
    """Raised when permission check fails."""
    
    def __init__(self, message: str = "Permission denied", resource: Optional[str] = None):
        """Initialize PermissionError.
        
        Args:
            message: Error message
            resource: Optional resource that was denied
        """
        details = {"resource": resource} if resource else {}
        super().__init__(message, code="PERMISSION_DENIED", details=details)


class NotFoundError(ProjectError):
    """Raised when a resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str):
        """Initialize NotFoundError.
        
        Args:
            resource_type: Type of resource not found
            resource_id: ID of resource not found
        """
        message = f"{resource_type} with ID '{resource_id}' not found"
        details = {
            "resource_type": resource_type,
            "resource_id": resource_id
        }
        super().__init__(message, code="NOT_FOUND", details=details)


class DuplicateError(ProjectError):
    """Raised when attempting to create a duplicate resource."""
    
    def __init__(self, resource_type: str, identifier: str):
        """Initialize DuplicateError.
        
        Args:
            resource_type: Type of resource
            identifier: Identifier that already exists
        """
        message = f"{resource_type} with identifier '{identifier}' already exists"
        details = {
            "resource_type": resource_type,
            "identifier": identifier
        }
        super().__init__(message, code="DUPLICATE", details=details)


class LimitExceededError(ProjectError):
    """Raised when a limit is exceeded."""
    
    def __init__(self, limit_type: str, current: int, maximum: int):
        """Initialize LimitExceededError.
        
        Args:
            limit_type: Type of limit exceeded
            current: Current value
            maximum: Maximum allowed value
        """
        message = f"{limit_type} limit exceeded: {current}/{maximum}"
        details = {
            "limit_type": limit_type,
            "current": current,
            "maximum": maximum
        }
        super().__init__(message, code="LIMIT_EXCEEDED", details=details)


class ExternalServiceError(ProjectError):
    """Raised when an external service fails."""
    
    def __init__(self, service: str, message: str, status_code: Optional[int] = None):
        """Initialize ExternalServiceError.
        
        Args:
            service: Name of the external service
            message: Error message
            status_code: Optional HTTP status code
        """
        details = {
            "service": service,
            "status_code": status_code
        }
        super().__init__(message, code="EXTERNAL_SERVICE_ERROR", details=details)