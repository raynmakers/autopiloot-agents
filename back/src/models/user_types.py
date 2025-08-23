"""User-related types."""

from typing import Optional, Dict, Any
from pydantic import BaseModel
from src.models.firestore_types import BaseDoc


class UserDoc(BaseDoc):
    """User document type."""
    
    id: str
    email: Optional[str] = None
    displayName: Optional[str] = None
    isPaid: bool = False
    subscriptionStatus: str = "free"
    metadata: Dict[str, Any] = {}


class User:
    """Simple User class for the template."""
    
    def __init__(self, uid: str):
        """Initialize User.
        
        Args:
            uid: User ID
        """
        self.uid = uid
        self.doc = UserDoc(
            id=uid,
            createdAt=None,  # Will be set properly in real implementation
            lastUpdatedAt=None,
        )
    
    def is_paid(self) -> bool:
        """Check if user has paid subscription.
        
        Returns:
            True if user has paid subscription
        """
        return self.doc.isPaid or self.doc.subscriptionStatus in ["premium", "pro"]