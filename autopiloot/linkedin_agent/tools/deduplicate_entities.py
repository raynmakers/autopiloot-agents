"""
DeduplicateEntities tool for removing duplicate LinkedIn content based on unique identifiers.
Ensures clean data for storage and prevents duplicate processing.
"""

import json
from typing import List, Dict, Any, Set, Tuple, Optional
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field


class DeduplicateEntities(BaseTool):
    """
    Deduplicates LinkedIn entities (posts, comments, users) based on natural keys.

    Uses URN/ID combinations to identify and remove duplicates, keeping the most
    recent or highest quality version of each entity.
    """

    entities: List[Dict] = Field(
        ...,
        description="List of entities (posts, comments, or users) to deduplicate"
    )

    entity_type: str = Field(
        ...,
        description="Type of entities being deduplicated (posts, comments, users, reactions)"
    )

    key_fields: Optional[List[str]] = Field(
        None,
        description="Custom fields to use as deduplication keys (default: auto-detect based on entity_type)"
    )

    merge_strategy: str = Field(
        "keep_latest",
        description="Strategy for handling duplicates: keep_latest, keep_first, merge_data (default: keep_latest)"
    )

    def run(self) -> str:
        """
        Deduplicates the provided entities based on natural keys.

        Returns:
            str: JSON string containing deduplicated entities and statistics
                 Format: {
                     "deduplicated_entities": [...],
                     "deduplication_stats": {
                         "original_count": 100,
                         "unique_count": 85,
                         "duplicates_removed": 15,
                         "duplicate_groups": [...]
                     },
                     "processing_metadata": {
                         "entity_type": "posts",
                         "key_fields_used": ["id"],
                         "merge_strategy": "keep_latest",
                         "processed_at": "2024-01-15T10:30:00Z"
                     }
                 }
        """
        try:
            if not self.entities:
                return json.dumps({
                    "deduplicated_entities": [],
                    "deduplication_stats": {
                        "original_count": 0,
                        "unique_count": 0,
                        "duplicates_removed": 0
                    }
                })

            # Determine key fields based on entity type
            key_fields = self._determine_key_fields()

            # Group entities by key
            entity_groups = self._group_by_key(key_fields)

            # Apply deduplication strategy
            deduplicated = []
            duplicate_groups = []

            for key, group in entity_groups.items():
                if len(group) > 1:
                    # Track duplicate groups
                    duplicate_groups.append({
                        "key": str(key),
                        "count": len(group),
                        "entities": [self._entity_summary(e) for e in group]
                    })

                    # Apply merge strategy
                    if self.merge_strategy == "keep_latest":
                        selected = self._select_latest(group)
                    elif self.merge_strategy == "keep_first":
                        selected = group[0]
                    elif self.merge_strategy == "merge_data":
                        selected = self._merge_entities(group)
                    else:
                        selected = group[0]  # Default to first

                    deduplicated.append(selected)
                else:
                    # Single entity, no deduplication needed
                    deduplicated.append(group[0])

            # Calculate statistics
            original_count = len(self.entities)
            unique_count = len(deduplicated)
            duplicates_removed = original_count - unique_count

            # Prepare result
            result = {
                "deduplicated_entities": deduplicated,
                "deduplication_stats": {
                    "original_count": original_count,
                    "unique_count": unique_count,
                    "duplicates_removed": duplicates_removed,
                    "duplicate_rate": round(duplicates_removed / original_count, 3) if original_count > 0 else 0,
                    "duplicate_groups": duplicate_groups[:10]  # Limit to top 10 groups
                },
                "processing_metadata": {
                    "entity_type": self.entity_type,
                    "key_fields_used": key_fields,
                    "merge_strategy": self.merge_strategy,
                    "processed_at": datetime.now(timezone.utc).isoformat()
                }
            }

            # Add entity-specific statistics
            if self.entity_type == "posts":
                result["content_stats"] = self._calculate_post_stats(deduplicated)
            elif self.entity_type == "comments":
                result["content_stats"] = self._calculate_comment_stats(deduplicated)

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "deduplication_failed",
                "message": str(e),
                "entity_type": self.entity_type,
                "entity_count": len(self.entities) if self.entities else 0
            }
            return json.dumps(error_result)

    def _determine_key_fields(self) -> List[str]:
        """
        Determine the appropriate key fields based on entity type.

        Returns:
            List[str]: Fields to use as deduplication keys
        """
        if self.key_fields:
            return self.key_fields

        # Default key fields by entity type
        key_field_mapping = {
            "posts": ["id"],  # Post URN/ID is unique
            "comments": ["id", "parent_post_id"],  # Comment ID within a post
            "users": ["urn", "profile_url"],  # User URN or profile URL
            "reactions": ["post_id", "user_id", "reaction_type"],  # Unique reaction
            "activities": ["activity_id", "user_urn"]  # Activity by user
        }

        return key_field_mapping.get(self.entity_type, ["id"])

    def _group_by_key(self, key_fields: List[str]) -> Dict[Tuple, List[Dict]]:
        """
        Group entities by their key fields.

        Args:
            key_fields: Fields to use as grouping keys

        Returns:
            Dict mapping keys to entity groups
        """
        groups = {}

        for entity in self.entities:
            # Extract key values
            key_values = []
            for field in key_fields:
                # Handle nested fields with dot notation
                value = self._get_nested_value(entity, field)
                key_values.append(value)

            key = tuple(key_values)

            if key not in groups:
                groups[key] = []
            groups[key].append(entity)

        return groups

    def _get_nested_value(self, entity: Dict, field_path: str) -> Any:
        """
        Get value from potentially nested field.

        Args:
            entity: Entity dictionary
            field_path: Dot-notation field path (e.g., "author.name")

        Returns:
            Field value or None
        """
        parts = field_path.split(".")
        value = entity

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value

    def _select_latest(self, group: List[Dict]) -> Dict:
        """
        Select the most recent entity from a group.

        Args:
            group: List of duplicate entities

        Returns:
            Dict: The most recent entity
        """
        # Try different timestamp fields
        timestamp_fields = ["created_at", "updated_at", "normalized_at", "fetched_at"]

        for field in timestamp_fields:
            # Find entities with this timestamp field
            with_timestamp = [e for e in group if field in e and e[field]]
            if with_timestamp:
                # Sort by timestamp and return latest
                return max(with_timestamp, key=lambda e: e[field])

        # No timestamp found, return first
        return group[0]

    def _merge_entities(self, group: List[Dict]) -> Dict:
        """
        Merge data from duplicate entities.

        Args:
            group: List of duplicate entities

        Returns:
            Dict: Merged entity with combined data
        """
        # Start with the latest entity as base
        merged = self._select_latest(group).copy()

        # Merge metrics and engagement data
        if self.entity_type in ["posts", "comments"]:
            merged_metrics = {}

            for entity in group:
                if "metrics" in entity:
                    for metric, value in entity["metrics"].items():
                        if isinstance(value, (int, float)):
                            # Take the maximum value for numeric metrics
                            current = merged_metrics.get(metric, 0)
                            merged_metrics[metric] = max(current, value)

            if merged_metrics:
                merged["metrics"] = merged_metrics

        # Merge arrays (tags, mentions, etc.)
        array_fields = ["tags", "mentions", "media", "reactions"]
        for field in array_fields:
            merged_array = []
            seen = set()

            for entity in group:
                if field in entity and isinstance(entity[field], list):
                    for item in entity[field]:
                        # Simple deduplication for array items
                        item_key = str(item) if not isinstance(item, dict) else json.dumps(item, sort_keys=True)
                        if item_key not in seen:
                            merged_array.append(item)
                            seen.add(item_key)

            if merged_array:
                merged[field] = merged_array

        # Add merge metadata
        merged["_merge_metadata"] = {
            "merged_from": len(group),
            "merge_strategy": self.merge_strategy,
            "merged_at": datetime.now(timezone.utc).isoformat()
        }

        return merged

    def _entity_summary(self, entity: Dict) -> Dict:
        """
        Create a summary of an entity for duplicate reporting.

        Args:
            entity: Entity to summarize

        Returns:
            Dict: Summary information
        """
        summary = {
            "id": entity.get("id", "unknown")
        }

        # Add entity-specific summary fields
        if self.entity_type == "posts":
            summary["text_preview"] = entity.get("text", "")[:50]
            summary["author"] = entity.get("author", {}).get("name", "")
            summary["likes"] = entity.get("metrics", {}).get("likes", 0)

        elif self.entity_type == "comments":
            summary["text_preview"] = entity.get("text", "")[:50]
            summary["likes"] = entity.get("metrics", {}).get("likes", 0)

        elif self.entity_type == "users":
            summary["name"] = entity.get("name", "")
            summary["headline"] = entity.get("headline", "")

        return summary

    def _calculate_post_stats(self, posts: List[Dict]) -> Dict:
        """
        Calculate statistics for deduplicated posts.

        Args:
            posts: Deduplicated posts

        Returns:
            Dict: Post statistics
        """
        if not posts:
            return {}

        total_likes = sum(p.get("metrics", {}).get("likes", 0) for p in posts)
        total_comments = sum(p.get("metrics", {}).get("comments", 0) for p in posts)

        return {
            "total_posts": len(posts),
            "total_engagement": total_likes + total_comments,
            "average_likes": round(total_likes / len(posts), 2) if posts else 0,
            "posts_with_media": sum(1 for p in posts if p.get("media")),
            "unique_authors": len(set(p.get("author", {}).get("name", "") for p in posts))
        }

    def _calculate_comment_stats(self, comments: List[Dict]) -> Dict:
        """
        Calculate statistics for deduplicated comments.

        Args:
            comments: Deduplicated comments

        Returns:
            Dict: Comment statistics
        """
        if not comments:
            return {}

        total_likes = sum(c.get("metrics", {}).get("likes", 0) for c in comments)
        replies = [c for c in comments if c.get("metrics", {}).get("is_reply", False)]

        return {
            "total_comments": len(comments),
            "total_likes": total_likes,
            "average_likes": round(total_likes / len(comments), 2) if comments else 0,
            "reply_count": len(replies),
            "reply_rate": round(len(replies) / len(comments), 3) if comments else 0
        }


if __name__ == "__main__":
    # Test the tool with duplicate posts
    test_entities = [
        {
            "id": "post_123",
            "text": "Original post",
            "created_at": "2024-01-15T10:00:00Z",
            "metrics": {"likes": 100}
        },
        {
            "id": "post_123",  # Duplicate ID
            "text": "Original post updated",
            "created_at": "2024-01-15T11:00:00Z",  # Later timestamp
            "metrics": {"likes": 150}  # More likes
        },
        {
            "id": "post_456",
            "text": "Different post",
            "created_at": "2024-01-15T12:00:00Z",
            "metrics": {"likes": 50}
        }
    ]

    tool = DeduplicateEntities(
        entities=test_entities,
        entity_type="posts",
        merge_strategy="keep_latest"
    )
    print("Testing DeduplicateEntities tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))