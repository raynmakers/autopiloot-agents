"""
Unit tests for DeduplicateEntities tool.
Tests deduplication strategies, key field handling, and merge operations.
"""

import unittest
import json
from unittest.mock import patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities


class TestDeduplicateEntities(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        # Test data with duplicates
        self.test_posts = [
            {
                "id": "post_123",
                "text": "Original post",
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 100, "comments": 10},
                "author": {"name": "John Doe", "headline": "CEO"}
            },
            {
                "id": "post_123",  # Duplicate ID
                "text": "Updated post content",
                "created_at": "2024-01-15T11:00:00Z",  # Later timestamp
                "metrics": {"likes": 150, "comments": 15},  # Updated metrics
                "author": {"name": "John Doe", "headline": "CEO"}
            },
            {
                "id": "post_456",
                "text": "Different post",
                "created_at": "2024-01-15T12:00:00Z",
                "metrics": {"likes": 50, "comments": 5},
                "author": {"name": "Jane Smith", "headline": "CTO"}
            }
        ]

        self.test_comments = [
            {
                "id": "comment_111",
                "parent_post_id": "post_123",
                "text": "Great comment",
                "created_at": "2024-01-15T10:30:00Z",
                "metrics": {"likes": 5, "is_reply": False}
            },
            {
                "id": "comment_111",  # Duplicate
                "parent_post_id": "post_123",
                "text": "Updated comment",
                "created_at": "2024-01-15T10:45:00Z",  # Later
                "metrics": {"likes": 8, "is_reply": False}
            },
            {
                "id": "comment_222",
                "parent_post_id": "post_456",
                "text": "Another comment",
                "created_at": "2024-01-15T11:00:00Z",
                "metrics": {"likes": 3, "is_reply": False}
            }
        ]

    def test_posts_deduplication_keep_latest(self):
        """Test post deduplication with keep_latest strategy."""
        tool = DeduplicateEntities(
            entities=self.test_posts,
            entity_type="posts",
            merge_strategy="keep_latest"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 3)
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 2)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 1)
        self.assertAlmostEqual(result_data["deduplication_stats"]["duplicate_rate"], 0.333, places=2)

        # Check that latest version was kept
        deduplicated = result_data["deduplicated_entities"]
        post_123 = next((p for p in deduplicated if p["id"] == "post_123"), None)
        self.assertIsNotNone(post_123)
        self.assertEqual(post_123["text"], "Updated post content")  # Latest version
        self.assertEqual(post_123["metrics"]["likes"], 150)  # Latest metrics
        self.assertEqual(post_123["created_at"], "2024-01-15T11:00:00Z")

        # Check unique post is preserved
        post_456 = next((p for p in deduplicated if p["id"] == "post_456"), None)
        self.assertIsNotNone(post_456)
        self.assertEqual(post_456["text"], "Different post")

        # Verify processing metadata
        metadata = result_data["processing_metadata"]
        self.assertEqual(metadata["entity_type"], "posts")
        self.assertEqual(metadata["key_fields_used"], ["id"])
        self.assertEqual(metadata["merge_strategy"], "keep_latest")

    def test_comments_deduplication_keep_first(self):
        """Test comment deduplication with keep_first strategy."""
        tool = DeduplicateEntities(
            entities=self.test_comments,
            entity_type="comments",
            merge_strategy="keep_first"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 3)
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 2)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 1)

        # Check that first version was kept
        deduplicated = result_data["deduplicated_entities"]
        comment_111 = next((c for c in deduplicated if c["id"] == "comment_111"), None)
        self.assertIsNotNone(comment_111)
        self.assertEqual(comment_111["text"], "Great comment")  # First version
        self.assertEqual(comment_111["metrics"]["likes"], 5)  # First metrics
        self.assertEqual(comment_111["created_at"], "2024-01-15T10:30:00Z")

        # Verify key fields for comments
        metadata = result_data["processing_metadata"]
        self.assertEqual(metadata["key_fields_used"], ["id", "parent_post_id"])

    def test_merge_data_strategy(self):
        """Test merge_data strategy for combining duplicate entities."""
        tool = DeduplicateEntities(
            entities=self.test_posts,
            entity_type="posts",
            merge_strategy="merge_data"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Find merged post
        deduplicated = result_data["deduplicated_entities"]
        post_123 = next((p for p in deduplicated if p["id"] == "post_123"), None)
        self.assertIsNotNone(post_123)

        # Should have latest content as base
        self.assertEqual(post_123["text"], "Updated post content")

        # Should have maximum metrics from all versions
        self.assertEqual(post_123["metrics"]["likes"], 150)  # Max of 100, 150
        self.assertEqual(post_123["metrics"]["comments"], 15)  # Max of 10, 15

        # Should have merge metadata
        self.assertIn("_merge_metadata", post_123)
        self.assertEqual(post_123["_merge_metadata"]["merged_from"], 2)
        self.assertEqual(post_123["_merge_metadata"]["merge_strategy"], "merge_data")

    def test_custom_key_fields(self):
        """Test custom key field specification."""
        # Create entities with custom keys
        entities = [
            {"custom_id": "abc", "name": "Item 1", "value": 10},
            {"custom_id": "abc", "name": "Item 1 Updated", "value": 20},
            {"custom_id": "def", "name": "Item 2", "value": 30}
        ]

        tool = DeduplicateEntities(
            entities=entities,
            entity_type="custom",
            key_fields=["custom_id"],
            merge_strategy="keep_latest"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should deduplicate based on custom_id
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 2)
        self.assertEqual(result_data["processing_metadata"]["key_fields_used"], ["custom_id"])

    def test_nested_field_keys(self):
        """Test deduplication with nested field keys."""
        entities = [
            {
                "id": "post_1",
                "author": {"id": "user_123", "name": "John"},
                "content": "Post 1"
            },
            {
                "id": "post_2",
                "author": {"id": "user_123", "name": "John Doe"},  # Same author.id
                "content": "Post 2"
            },
            {
                "id": "post_3",
                "author": {"id": "user_456", "name": "Jane"},
                "content": "Post 3"
            }
        ]

        tool = DeduplicateEntities(
            entities=entities,
            entity_type="posts_by_author",
            key_fields=["author.id"],
            merge_strategy="keep_first"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should deduplicate by author.id
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 2)

        # Check that first post by each author was kept
        deduplicated = result_data["deduplicated_entities"]
        user_123_post = next((p for p in deduplicated if p["author"]["id"] == "user_123"), None)
        self.assertEqual(user_123_post["id"], "post_1")  # First post by user_123

    def test_empty_entities_list(self):
        """Test handling of empty entities list."""
        tool = DeduplicateEntities(
            entities=[],
            entity_type="posts"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should handle empty list gracefully
        self.assertEqual(result_data["deduplicated_entities"], [])
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 0)
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 0)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 0)

    def test_no_duplicates(self):
        """Test handling when no duplicates exist."""
        unique_entities = [
            {"id": "post_1", "text": "Post 1"},
            {"id": "post_2", "text": "Post 2"},
            {"id": "post_3", "text": "Post 3"}
        ]

        tool = DeduplicateEntities(
            entities=unique_entities,
            entity_type="posts"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should preserve all entities
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 3)
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 3)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 0)
        self.assertEqual(result_data["deduplication_stats"]["duplicate_rate"], 0.0)

        # All entities should be preserved
        self.assertEqual(len(result_data["deduplicated_entities"]), 3)

    def test_duplicate_groups_tracking(self):
        """Test tracking of duplicate groups for analysis."""
        tool = DeduplicateEntities(
            entities=self.test_posts,
            entity_type="posts",
            merge_strategy="keep_latest"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should track duplicate groups
        duplicate_groups = result_data["deduplication_stats"]["duplicate_groups"]
        self.assertEqual(len(duplicate_groups), 1)  # One group with duplicates

        # Check duplicate group details
        group = duplicate_groups[0]
        self.assertEqual(group["count"], 2)  # Two duplicates
        self.assertEqual(len(group["entities"]), 2)  # Both entities summarized

        # Check entity summaries in group
        summaries = group["entities"]
        self.assertTrue(any("Original post" in s.get("text_preview", "") for s in summaries))
        self.assertTrue(any("Updated post" in s.get("text_preview", "") for s in summaries))

    def test_content_stats_for_posts(self):
        """Test content statistics calculation for posts."""
        tool = DeduplicateEntities(
            entities=self.test_posts,
            entity_type="posts"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should include content stats for posts
        self.assertIn("content_stats", result_data)
        stats = result_data["content_stats"]

        self.assertEqual(stats["total_posts"], 2)  # After deduplication
        self.assertGreater(stats["total_engagement"], 0)
        self.assertGreater(stats["average_likes"], 0)
        self.assertEqual(stats["unique_authors"], 2)  # John Doe and Jane Smith

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            DeduplicateEntities()  # Missing required fields

        with self.assertRaises(Exception):
            DeduplicateEntities(entities=self.test_posts)  # Missing entity_type

        # Test valid entity types and strategies
        tool = DeduplicateEntities(
            entities=self.test_posts,
            entity_type="posts",
            merge_strategy="keep_latest"
        )
        self.assertEqual(tool.entity_type, "posts")
        self.assertEqual(tool.merge_strategy, "keep_latest")

        # Test default values
        tool = DeduplicateEntities(
            entities=self.test_posts,
            entity_type="posts"
        )
        self.assertEqual(tool.merge_strategy, "keep_latest")  # Default


if __name__ == '__main__':
    unittest.main()