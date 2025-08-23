"""Factory for creating Category documents."""

from typing import List, Dict, Any, Optional
from src.models.firestore_types import CategoryDoc
from src.apis.Db import Db
from src.util.logger import get_logger

logger = get_logger(__name__)


class CategoryFactory:
    """Factory for creating Category documents from various sources."""
    
    def __init__(self, user_id: str):
        """Initialize CategoryFactory.
        
        Args:
            user_id: Owner user ID for created categories
        """
        self.user_id = user_id
        self.db = Db.get_instance()
    
    def create_hierarchy(self, hierarchy_data: List[Dict[str, Any]]) -> List[CategoryDoc]:
        """Create a hierarchy of categories.
        
        Args:
            hierarchy_data: List of category definitions with hierarchy info
            
        Returns:
            List of created CategoryDoc objects
        """
        categories = []
        parent_map = {}
        
        # Sort by hierarchy level (root categories first)
        sorted_data = sorted(
            hierarchy_data, 
            key=lambda x: x.get("level", 0)
        )
        
        for category_info in sorted_data:
            # Handle parent relationship
            parent_id = None
            parent_name = category_info.get("parent")
            if parent_name and parent_name in parent_map:
                parent_id = parent_map[parent_name]["id"]
            
            category = self._create_category(
                name=category_info.get("name", "Unnamed Category"),
                description=category_info.get("description"),
                parent_id=parent_id,
                display_order=category_info.get("order", len(categories))
            )
            
            categories.append(category)
            parent_map[category.name] = {"id": category.id}
        
        logger.info(f"Created category hierarchy with {len(categories)} categories")
        return categories
    
    def create_default_categories(self) -> List[CategoryDoc]:
        """Create a set of default categories.
        
        Returns:
            List of default CategoryDoc objects
        """
        default_categories = [
            {"name": "General", "description": "General items", "order": 0},
            {"name": "Important", "description": "Important items", "order": 1},
            {"name": "Archive", "description": "Archived items", "order": 2},
        ]
        
        categories = []
        for category_info in default_categories:
            category = self._create_category(
                name=category_info["name"],
                description=category_info["description"],
                display_order=category_info["order"]
            )
            categories.append(category)
        
        logger.info(f"Created {len(categories)} default categories")
        return categories
    
    def duplicate_category_structure(self, source_user_id: str) -> List[CategoryDoc]:
        """Duplicate category structure from another user.
        
        Args:
            source_user_id: User ID to copy structure from
            
        Returns:
            List of duplicated CategoryDoc objects
        """
        # Get source categories
        source_categories = (
            self.db.collections["categories"]
            .where("ownerUid", "==", source_user_id)
            .order_by("displayOrder")
            .get()
        )
        
        categories = []
        id_mapping = {}  # Map old IDs to new IDs
        
        for source_doc in source_categories:
            source_data = source_doc.to_dict()
            
            # Map parent ID if exists
            parent_id = None
            if source_data.get("parentId") and source_data["parentId"] in id_mapping:
                parent_id = id_mapping[source_data["parentId"]]
            
            category = self._create_category(
                name=source_data.get("name", "Unnamed Category"),
                description=source_data.get("description"),
                parent_id=parent_id,
                display_order=source_data.get("displayOrder", 0),
                is_active=source_data.get("isActive", True)
            )
            
            categories.append(category)
            id_mapping[source_doc.id] = category.id
        
        logger.info(f"Duplicated {len(categories)} categories from user {source_user_id}")
        return categories
    
    def _create_category(
        self,
        name: str,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
        display_order: int = 0,
        is_active: bool = True
    ) -> CategoryDoc:
        """Create a single CategoryDoc.
        
        Args:
            name: Category name
            description: Category description
            parent_id: Parent category ID
            display_order: Display order
            is_active: Whether category is active
            
        Returns:
            Created CategoryDoc object
        """
        doc_ref = self.db.collections["categories"].document()
        
        category = CategoryDoc(
            id=doc_ref.id,
            name=name,
            description=description,
            parentId=parent_id,
            ownerUid=self.user_id,
            displayOrder=display_order,
            isActive=is_active,
            createdAt=self.db.get_created_at(),
            lastUpdatedAt=self.db.get_created_at(),
        )
        
        # Save to Firestore
        doc_ref.set(category.model_dump())
        
        return category