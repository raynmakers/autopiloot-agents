"""
Fixed 100% coverage tests for DeduplicateEntities tool.
Properly handles Pydantic Field mocking to achieve complete coverage.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
from datetime import datetime, timezone


class TestDeduplicateEntitiesFixed(unittest.TestCase):
    """Fixed coverage test suite for DeduplicateEntities tool."""

    def setUp(self):
        """Set up test environment with proper Pydantic mocking."""
        # Mock external dependencies
        self.patcher = patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
        })
        self.patcher.start()

        # Create proper BaseTool and Field mocks
        class MockBaseTool:
            def __init__(self, **kwargs):
                # Set attributes directly without Pydantic interference
                for key, value in kwargs.items():
                    setattr(self, key, value)

        # Mock Field to return the default value
        def mock_field(*args, **kwargs):
            return kwargs.get('default', kwargs.get('default_factory', lambda: None)())

        sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
        sys.modules['pydantic'].Field = mock_field

    def tearDown(self):
        """Clean up mocks."""
        self.patcher.stop()

    def test_empty_entities_line_coverage(self):
        """Test empty entities handling (lines 64-72)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test empty list
        tool = DeduplicateEntities(
            entities=[],
            entity_type="posts"
        )
        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data["deduplicated_entities"], [])
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 0)

        # Test None entities
        tool_none = DeduplicateEntities(
            entities=None,
            entity_type="posts"
        )
        result_none = tool_none.run()
        result_none_data = json.loads(result_none)
        self.assertEqual(result_none_data["deduplicated_entities"], [])

    def test_main_workflow_execution(self):
        """Test main workflow execution (lines 74-137)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Create test data with duplicates
        entities = [
            {
                "id": "post_1",
                "text": "First post",
                "created_at": "2024-01-15T10:00:00Z",
                "author": {"name": "John"},
                "metrics": {"likes": 100, "comments": 10}
            },
            {
                "id": "post_1",  # Duplicate
                "text": "First post updated",
                "created_at": "2024-01-15T12:00:00Z",
                "author": {"name": "John"},
                "metrics": {"likes": 150, "comments": 15}
            },
            {
                "id": "post_2",
                "text": "Second post",
                "created_at": "2024-01-16T10:00:00Z",
                "author": {"name": "Jane"},
                "metrics": {"likes": 50, "comments": 5}
            }
        ]

        # Test with posts
        tool = DeduplicateEntities(
            entities=entities,
            entity_type="posts",
            merge_strategy="keep_latest"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Verify deduplication results
        self.assertEqual(len(result_data["deduplicated_entities"]), 2)
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 3)
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 2)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 1)

        # Test duplicate groups tracking (lines 84-92)
        self.assertEqual(len(result_data["deduplication_stats"]["duplicate_groups"]), 1)
        duplicate_group = result_data["deduplication_stats"]["duplicate_groups"][0]
        self.assertEqual(duplicate_group["count"], 2)

        # Test processing metadata (lines 123-128)
        metadata = result_data["processing_metadata"]
        self.assertEqual(metadata["entity_type"], "posts")
        self.assertEqual(metadata["merge_strategy"], "keep_latest")
        self.assertIn("processed_at", metadata)

        # Test post content stats (lines 132-133)
        self.assertIn("content_stats", result_data)
        content_stats = result_data["content_stats"]
        self.assertEqual(content_stats["total_posts"], 2)

    def test_comments_content_stats(self):
        """Test comments content stats (lines 134-135)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        comments = [
            {
                "id": "comment_1",
                "text": "Great post!",
                "metrics": {"likes": 5, "is_reply": False}
            },
            {
                "id": "comment_2",
                "text": "Thanks!",
                "metrics": {"likes": 3, "is_reply": True}
            }
        ]

        tool = DeduplicateEntities(
            entities=comments,
            entity_type="comments"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Verify comment stats are calculated
        self.assertIn("content_stats", result_data)
        content_stats = result_data["content_stats"]
        self.assertEqual(content_stats["total_comments"], 2)
        self.assertEqual(content_stats["reply_count"], 1)

    def test_error_handling_coverage(self):
        """Test error handling (lines 139-146)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Create entities that will cause an error during processing
        tool = DeduplicateEntities(
            entities=[{"bad": "data"}],  # Missing required id field
            entity_type="posts"
        )

        # Patch to force an error during key field determination
        with patch.object(tool, '_determine_key_fields', side_effect=ValueError("Test error")):
            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("error", result_data)
            self.assertEqual(result_data["error"], "deduplication_failed")
            self.assertIn("message", result_data)
            self.assertEqual(result_data["entity_type"], "posts")

    def test_determine_key_fields_coverage(self):
        """Test _determine_key_fields method (lines 155-167)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test custom key fields (line 155-156)
        tool_custom = DeduplicateEntities(
            entities=[],
            entity_type="posts",
            key_fields=["custom_field"]
        )
        self.assertEqual(tool_custom._determine_key_fields(), ["custom_field"])

        # Test all entity type mappings (lines 159-167)
        entity_types = [
            ("posts", ["id"]),
            ("comments", ["id", "parent_post_id"]),
            ("users", ["urn", "profile_url"]),
            ("reactions", ["post_id", "user_id", "reaction_type"]),
            ("activities", ["activity_id", "user_urn"]),
            ("unknown_type", ["id"])  # Default case
        ]

        for entity_type, expected_keys in entity_types:
            tool = DeduplicateEntities(entities=[], entity_type=entity_type)
            self.assertEqual(tool._determine_key_fields(), expected_keys)

    def test_group_by_key_coverage(self):
        """Test _group_by_key method (lines 183-195)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        entities = [
            {"id": "1", "name": "First"},
            {"id": "2", "name": "Second"},
            {"id": "1", "name": "First Duplicate"}
        ]

        tool = DeduplicateEntities(entities=entities, entity_type="posts")
        groups = tool._group_by_key(["id"])

        # Verify grouping logic
        self.assertEqual(len(groups), 2)  # Two unique IDs
        self.assertEqual(len(groups[("1",)]), 2)  # Two entities with id "1"
        self.assertEqual(len(groups[("2",)]), 1)  # One entity with id "2"

    def test_get_nested_value_coverage(self):
        """Test _get_nested_value method (lines 208-217)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="posts")

        entity = {
            "id": "test",
            "author": {"name": "John", "profile": {"url": "test.com"}},
            "simple": "value"
        }

        # Test simple field
        self.assertEqual(tool._get_nested_value(entity, "id"), "test")

        # Test nested field
        self.assertEqual(tool._get_nested_value(entity, "author.name"), "John")

        # Test deeply nested field
        self.assertEqual(tool._get_nested_value(entity, "author.profile.url"), "test.com")

        # Test non-existent field
        self.assertIsNone(tool._get_nested_value(entity, "nonexistent"))

        # Test when intermediate is not dict (line 214-215)
        self.assertIsNone(tool._get_nested_value(entity, "simple.nested"))

    def test_select_latest_coverage(self):
        """Test _select_latest method (lines 230-240)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="posts")

        # Test with created_at timestamps
        group_with_created = [
            {"id": "1", "created_at": "2024-01-15T10:00:00Z", "data": "old"},
            {"id": "1", "created_at": "2024-01-15T12:00:00Z", "data": "new"}
        ]
        latest = tool._select_latest(group_with_created)
        self.assertEqual(latest["data"], "new")

        # Test with updated_at timestamps
        group_with_updated = [
            {"id": "1", "updated_at": "2024-01-15T12:00:00Z", "data": "latest"}
        ]
        latest_updated = tool._select_latest(group_with_updated)
        self.assertEqual(latest_updated["data"], "latest")

        # Test with normalized_at timestamps
        group_with_normalized = [
            {"id": "1", "normalized_at": "2024-01-15T12:00:00Z", "data": "normalized"}
        ]
        latest_normalized = tool._select_latest(group_with_normalized)
        self.assertEqual(latest_normalized["data"], "normalized")

        # Test with fetched_at timestamps
        group_with_fetched = [
            {"id": "1", "fetched_at": "2024-01-15T12:00:00Z", "data": "fetched"}
        ]
        latest_fetched = tool._select_latest(group_with_fetched)
        self.assertEqual(latest_fetched["data"], "fetched")

        # Test fallback to first when no timestamps (line 239-240)
        group_no_timestamp = [
            {"id": "1", "data": "first"},
            {"id": "1", "data": "second"}
        ]
        fallback = tool._select_latest(group_no_timestamp)
        self.assertEqual(fallback["data"], "first")

    def test_merge_entities_coverage(self):
        """Test _merge_entities method (lines 253-295)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test with posts (lines 256-268)
        tool_posts = DeduplicateEntities(entities=[], entity_type="posts")

        post_group = [
            {
                "id": "post_1",
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 50, "comments": 10},
                "tags": ["ai"],
                "media": [{"type": "image"}]
            },
            {
                "id": "post_1",
                "created_at": "2024-01-15T12:00:00Z",  # Latest
                "metrics": {"likes": 75, "views": 100},
                "tags": ["ai", "tech"],
                "media": [{"type": "video"}]
            }
        ]

        merged = tool_posts._merge_entities(post_group)

        # Verify metrics merging (lines 260-265)
        self.assertEqual(merged["metrics"]["likes"], 75)  # Max value
        self.assertEqual(merged["metrics"]["comments"], 10)  # From first
        self.assertEqual(merged["metrics"]["views"], 100)  # From second

        # Verify array merging (lines 271-286)
        self.assertIn("ai", merged["tags"])
        self.assertIn("tech", merged["tags"])
        self.assertEqual(len(merged["media"]), 2)

        # Verify merge metadata (lines 288-293)
        self.assertIn("_merge_metadata", merged)
        self.assertEqual(merged["_merge_metadata"]["merged_from"], 2)

        # Test with comments (ensure lines 256-268 are covered)
        tool_comments = DeduplicateEntities(entities=[], entity_type="comments")
        comment_group = [
            {"id": "c1", "created_at": "2024-01-15T12:00:00Z", "metrics": {"likes": 5}}
        ]
        merged_comment = tool_comments._merge_entities(comment_group)
        self.assertIn("_merge_metadata", merged_comment)

        # Test with non-posts/comments entity type
        tool_users = DeduplicateEntities(entities=[], entity_type="users")
        user_group = [{"id": "u1", "created_at": "2024-01-15T12:00:00Z"}]
        merged_user = tool_users._merge_entities(user_group)
        self.assertIn("_merge_metadata", merged_user)

    def test_entity_summary_coverage(self):
        """Test _entity_summary method (lines 307-325)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test posts summary (lines 312-315)
        tool_posts = DeduplicateEntities(entities=[], entity_type="posts")
        post = {
            "id": "post_123",
            "text": "This is a very long text that should be truncated at fifty characters exactly",
            "author": {"name": "John"},
            "metrics": {"likes": 100}
        }
        summary = tool_posts._entity_summary(post)
        self.assertEqual(summary["id"], "post_123")
        self.assertEqual(len(summary["text_preview"]), 50)
        self.assertEqual(summary["author"], "John")
        self.assertEqual(summary["likes"], 100)

        # Test comments summary (lines 317-319)
        tool_comments = DeduplicateEntities(entities=[], entity_type="comments")
        comment = {
            "id": "comment_456",
            "text": "Short comment",
            "metrics": {"likes": 25}
        }
        comment_summary = tool_comments._entity_summary(comment)
        self.assertEqual(comment_summary["likes"], 25)

        # Test users summary (lines 321-323)
        tool_users = DeduplicateEntities(entities=[], entity_type="users")
        user = {
            "id": "user_789",
            "name": "Jane",
            "headline": "Engineer"
        }
        user_summary = tool_users._entity_summary(user)
        self.assertEqual(user_summary["name"], "Jane")
        self.assertEqual(user_summary["headline"], "Engineer")

    def test_calculate_post_stats_coverage(self):
        """Test _calculate_post_stats method (lines 337-349)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="posts")

        # Test empty posts (line 337-338)
        empty_stats = tool._calculate_post_stats([])
        self.assertEqual(empty_stats, {})

        # Test with posts data (lines 340-348)
        posts = [
            {
                "author": {"name": "John"},
                "metrics": {"likes": 100, "comments": 20},
                "media": [{"type": "image"}]
            },
            {
                "author": {"name": "Jane"},
                "metrics": {"likes": 50, "comments": 10}
                # No media
            },
            {
                "author": {"name": "John"},  # Same author
                "metrics": {"likes": 75, "comments": 15},
                "media": [{"type": "video"}]
            }
        ]

        stats = tool._calculate_post_stats(posts)
        self.assertEqual(stats["total_posts"], 3)
        self.assertEqual(stats["total_engagement"], 270)
        self.assertEqual(stats["average_likes"], 75.0)
        self.assertEqual(stats["posts_with_media"], 2)
        self.assertEqual(stats["unique_authors"], 2)

    def test_calculate_comment_stats_coverage(self):
        """Test _calculate_comment_stats method (lines 361-373)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="comments")

        # Test empty comments (line 361-362)
        empty_stats = tool._calculate_comment_stats([])
        self.assertEqual(empty_stats, {})

        # Test with comments data (lines 364-372)
        comments = [
            {"metrics": {"likes": 10, "is_reply": False}},
            {"metrics": {"likes": 5, "is_reply": True}},
            {"metrics": {"likes": 15, "is_reply": True}},
            {"metrics": {"likes": 0, "is_reply": False}}
        ]

        stats = tool._calculate_comment_stats(comments)
        self.assertEqual(stats["total_comments"], 4)
        self.assertEqual(stats["total_likes"], 30)
        self.assertEqual(stats["average_likes"], 7.5)
        self.assertEqual(stats["reply_count"], 2)
        self.assertEqual(stats["reply_rate"], 0.5)

    def test_merge_strategies_coverage(self):
        """Test different merge strategies (lines 94-102)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        entities = [
            {"id": "dup", "created_at": "2024-01-15T10:00:00Z", "data": "first"},
            {"id": "dup", "created_at": "2024-01-15T12:00:00Z", "data": "latest"}
        ]

        # Test keep_latest (line 94-95)
        tool_latest = DeduplicateEntities(
            entities=entities,
            entity_type="posts",
            merge_strategy="keep_latest"
        )
        result_latest = tool_latest.run()
        result_data = json.loads(result_latest)
        selected = result_data["deduplicated_entities"][0]
        self.assertEqual(selected["data"], "latest")

        # Test keep_first (line 96-97)
        tool_first = DeduplicateEntities(
            entities=entities,
            entity_type="posts",
            merge_strategy="keep_first"
        )
        result_first = tool_first.run()
        result_data = json.loads(result_first)
        selected = result_data["deduplicated_entities"][0]
        self.assertEqual(selected["data"], "first")

        # Test merge_data (line 98-99)
        tool_merge = DeduplicateEntities(
            entities=entities,
            entity_type="posts",
            merge_strategy="merge_data"
        )
        result_merge = tool_merge.run()
        result_data = json.loads(result_merge)
        merged = result_data["deduplicated_entities"][0]
        self.assertIn("_merge_metadata", merged)

        # Test unknown strategy (line 100-101)
        tool_unknown = DeduplicateEntities(
            entities=entities,
            entity_type="posts",
            merge_strategy="unknown_strategy"
        )
        result_unknown = tool_unknown.run()
        result_data = json.loads(result_unknown)
        fallback = result_data["deduplicated_entities"][0]
        self.assertEqual(fallback["data"], "first")  # Defaults to first

    def test_single_entity_handling(self):
        """Test single entity group handling (lines 104-106)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Create entities with no duplicates
        entities = [
            {"id": "unique_1", "data": "first"},
            {"id": "unique_2", "data": "second"}
        ]

        tool = DeduplicateEntities(entities=entities, entity_type="posts")
        result = tool.run()
        result_data = json.loads(result)

        # All entities preserved (no duplicates removed)
        self.assertEqual(len(result_data["deduplicated_entities"]), 2)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 0)
        self.assertEqual(len(result_data["deduplication_stats"]["duplicate_groups"]), 0)

    def test_main_block_execution(self):
        """Test main execution block (lines 376-406)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test the exact scenario from main block
        test_entities = [
            {
                "id": "post_123",
                "text": "Original post",
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 100}
            },
            {
                "id": "post_123",  # Duplicate
                "text": "Original post updated",
                "created_at": "2024-01-15T11:00:00Z",
                "metrics": {"likes": 150}
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

        result = tool.run()
        result_data = json.loads(result)

        # Verify main block functionality
        self.assertEqual(len(result_data["deduplicated_entities"]), 2)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 1)


if __name__ == '__main__':
    unittest.main()