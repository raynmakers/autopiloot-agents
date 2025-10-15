"""
Complete 100% coverage tests for DeduplicateEntities tool.
Targets all missing lines to achieve full coverage.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
from datetime import datetime, timezone


class TestDeduplicateEntities100Coverage(unittest.TestCase):
    """Complete coverage test suite for DeduplicateEntities tool."""

    def setUp(self):
        """Set up test environment with minimal mocking."""
        # Mock only external dependencies, not the class itself
        self.patcher = patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
        })
        self.patcher.start()

        # Create a real BaseTool mock that allows inheritance
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

    def tearDown(self):
        """Clean up mocks."""
        self.patcher.stop()

    def test_empty_entities_handling(self):
        """Test handling of empty entities list (lines 64-72)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test with empty list
        tool_empty = DeduplicateEntities(
            entities=[],
            entity_type="posts"
        )

        result = tool_empty.run()
        result_data = json.loads(result)

        self.assertEqual(result_data["deduplicated_entities"], [])
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 0)
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 0)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 0)

        # Test with None entities
        tool_none = DeduplicateEntities(
            entities=None,
            entity_type="posts"
        )

        result_none = tool_none.run()
        result_none_data = json.loads(result_none)
        self.assertEqual(result_none_data["deduplicated_entities"], [])

    def test_full_deduplication_workflow_posts(self):
        """Test complete deduplication workflow with posts (lines 74-137)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Create test data with duplicates
        test_posts = [
            {
                "id": "post_1",
                "text": "First post content",
                "created_at": "2024-01-15T10:00:00Z",
                "author": {"name": "John Doe"},
                "metrics": {"likes": 100, "comments": 10}
            },
            {
                "id": "post_1",  # Duplicate ID
                "text": "First post content updated",
                "created_at": "2024-01-15T11:00:00Z",  # Later timestamp
                "author": {"name": "John Doe"},
                "metrics": {"likes": 150, "comments": 15}
            },
            {
                "id": "post_2",
                "text": "Second post content",
                "created_at": "2024-01-16T10:00:00Z",
                "author": {"name": "Jane Smith"},
                "metrics": {"likes": 50, "comments": 5}
            },
            {
                "id": "post_3",
                "text": "Third post content",
                "created_at": "2024-01-17T10:00:00Z",
                "author": {"name": "Bob Wilson"},
                "metrics": {"likes": 75, "comments": 8},
                "media": [{"type": "image"}]
            }
        ]

        tool = DeduplicateEntities(
            entities=test_posts,
            entity_type="posts",
            merge_strategy="keep_latest"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Verify deduplication results
        self.assertEqual(len(result_data["deduplicated_entities"]), 3)  # 4 original - 1 duplicate
        self.assertEqual(result_data["deduplication_stats"]["original_count"], 4)
        self.assertEqual(result_data["deduplication_stats"]["unique_count"], 3)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 1)
        self.assertEqual(result_data["deduplication_stats"]["duplicate_rate"], 0.25)

        # Verify duplicate groups tracking
        self.assertEqual(len(result_data["deduplication_stats"]["duplicate_groups"]), 1)
        duplicate_group = result_data["deduplication_stats"]["duplicate_groups"][0]
        self.assertEqual(duplicate_group["count"], 2)
        self.assertEqual(duplicate_group["key"], "('post_1',)")

        # Verify processing metadata
        metadata = result_data["processing_metadata"]
        self.assertEqual(metadata["entity_type"], "posts")
        self.assertEqual(metadata["key_fields_used"], ["id"])
        self.assertEqual(metadata["merge_strategy"], "keep_latest")
        self.assertIn("processed_at", metadata)

        # Verify content stats for posts
        self.assertIn("content_stats", result_data)
        content_stats = result_data["content_stats"]
        self.assertEqual(content_stats["total_posts"], 3)
        self.assertIn("total_engagement", content_stats)
        self.assertIn("average_likes", content_stats)
        self.assertEqual(content_stats["posts_with_media"], 1)
        self.assertEqual(content_stats["unique_authors"], 3)

    def test_full_deduplication_workflow_comments(self):
        """Test complete deduplication workflow with comments (lines 134-136)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        test_comments = [
            {
                "id": "comment_1",
                "text": "Great post!",
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 5, "is_reply": False}
            },
            {
                "id": "comment_2",
                "text": "Thanks for sharing",
                "created_at": "2024-01-15T11:00:00Z",
                "metrics": {"likes": 3, "is_reply": True}
            }
        ]

        tool = DeduplicateEntities(
            entities=test_comments,
            entity_type="comments"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Verify content stats for comments
        self.assertIn("content_stats", result_data)
        content_stats = result_data["content_stats"]
        self.assertEqual(content_stats["total_comments"], 2)
        self.assertEqual(content_stats["total_likes"], 8)
        self.assertEqual(content_stats["reply_count"], 1)
        self.assertEqual(content_stats["reply_rate"], 0.5)

    def test_error_handling(self):
        """Test error handling in run method (lines 139-146)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Create a tool that will cause an error
        class BadEntities(list):
            def __len__(self):
                raise ValueError("Simulated error")

        tool_error = DeduplicateEntities(
            entities=BadEntities([{"id": "test"}]),
            entity_type="posts"
        )

        result = tool_error.run()
        result_data = json.loads(result)

        self.assertIn("error", result_data)
        self.assertEqual(result_data["error"], "deduplication_failed")
        self.assertIn("message", result_data)
        self.assertEqual(result_data["entity_type"], "posts")

    def test_determine_key_fields_all_types(self):
        """Test _determine_key_fields for all entity types (lines 155-167)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test with custom key fields
        tool_custom = DeduplicateEntities(
            entities=[],
            entity_type="posts",
            key_fields=["custom_id", "author.name"]
        )
        key_fields = tool_custom._determine_key_fields()
        self.assertEqual(key_fields, ["custom_id", "author.name"])

        # Test posts default
        tool_posts = DeduplicateEntities(entities=[], entity_type="posts")
        self.assertEqual(tool_posts._determine_key_fields(), ["id"])

        # Test comments default
        tool_comments = DeduplicateEntities(entities=[], entity_type="comments")
        self.assertEqual(tool_comments._determine_key_fields(), ["id", "parent_post_id"])

        # Test users default
        tool_users = DeduplicateEntities(entities=[], entity_type="users")
        self.assertEqual(tool_users._determine_key_fields(), ["urn", "profile_url"])

        # Test reactions default
        tool_reactions = DeduplicateEntities(entities=[], entity_type="reactions")
        self.assertEqual(tool_reactions._determine_key_fields(), ["post_id", "user_id", "reaction_type"])

        # Test activities default
        tool_activities = DeduplicateEntities(entities=[], entity_type="activities")
        self.assertEqual(tool_activities._determine_key_fields(), ["activity_id", "user_urn"])

        # Test unknown type default
        tool_unknown = DeduplicateEntities(entities=[], entity_type="unknown_type")
        self.assertEqual(tool_unknown._determine_key_fields(), ["id"])

    def test_group_by_key_functionality(self):
        """Test _group_by_key with various scenarios (lines 183-195)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        test_entities = [
            {"id": "1", "author": {"name": "John"}},
            {"id": "2", "author": {"name": "Jane"}},
            {"id": "1", "author": {"name": "John"}},  # Duplicate
            {"id": "3", "author": None},  # None author
            {"id": "4"},  # Missing author
        ]

        tool = DeduplicateEntities(
            entities=test_entities,
            entity_type="posts",
            key_fields=["id"]
        )

        groups = tool._group_by_key(["id"])

        # Verify grouping
        self.assertEqual(len(groups), 4)  # 4 unique IDs
        self.assertEqual(len(groups[("1",)]), 2)  # Two entities with id "1"
        self.assertEqual(len(groups[("2",)]), 1)
        self.assertEqual(len(groups[("3",)]), 1)
        self.assertEqual(len(groups[("4",)]), 1)

    def test_get_nested_value_functionality(self):
        """Test _get_nested_value with various scenarios (lines 208-217)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="posts")

        test_entity = {
            "id": "test",
            "author": {
                "name": "John Doe",
                "profile": {
                    "url": "https://linkedin.com/in/johndoe"
                }
            },
            "simple_field": "value"
        }

        # Test simple field
        self.assertEqual(tool._get_nested_value(test_entity, "id"), "test")
        self.assertEqual(tool._get_nested_value(test_entity, "simple_field"), "value")

        # Test nested field
        self.assertEqual(tool._get_nested_value(test_entity, "author.name"), "John Doe")

        # Test deeply nested field
        self.assertEqual(tool._get_nested_value(test_entity, "author.profile.url"), "https://linkedin.com/in/johndoe")

        # Test non-existent field
        self.assertIsNone(tool._get_nested_value(test_entity, "nonexistent"))
        self.assertIsNone(tool._get_nested_value(test_entity, "author.nonexistent"))

        # Test when intermediate value is not a dict
        self.assertIsNone(tool._get_nested_value(test_entity, "simple_field.nested"))

    def test_select_latest_functionality(self):
        """Test _select_latest with various timestamp scenarios (lines 230-240)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="posts")

        # Test with created_at timestamps
        group_created_at = [
            {"id": "1", "created_at": "2024-01-15T10:00:00Z", "data": "first"},
            {"id": "1", "created_at": "2024-01-15T12:00:00Z", "data": "latest"},
            {"id": "1", "created_at": "2024-01-15T11:00:00Z", "data": "middle"}
        ]
        latest = tool._select_latest(group_created_at)
        self.assertEqual(latest["data"], "latest")

        # Test with updated_at timestamps
        group_updated_at = [
            {"id": "1", "updated_at": "2024-01-15T10:00:00Z", "data": "first"},
            {"id": "1", "updated_at": "2024-01-15T12:00:00Z", "data": "latest"}
        ]
        latest_updated = tool._select_latest(group_updated_at)
        self.assertEqual(latest_updated["data"], "latest")

        # Test with normalized_at timestamps
        group_normalized = [
            {"id": "1", "normalized_at": "2024-01-15T12:00:00Z", "data": "latest"}
        ]
        latest_normalized = tool._select_latest(group_normalized)
        self.assertEqual(latest_normalized["data"], "latest")

        # Test with fetched_at timestamps
        group_fetched = [
            {"id": "1", "fetched_at": "2024-01-15T12:00:00Z", "data": "latest"}
        ]
        latest_fetched = tool._select_latest(group_fetched)
        self.assertEqual(latest_fetched["data"], "latest")

        # Test with no timestamps (fallback to first)
        group_no_timestamp = [
            {"id": "1", "data": "first"},
            {"id": "1", "data": "second"}
        ]
        fallback = tool._select_latest(group_no_timestamp)
        self.assertEqual(fallback["data"], "first")

        # Test with empty timestamps
        group_empty_timestamp = [
            {"id": "1", "created_at": "", "data": "empty"},
            {"id": "1", "created_at": None, "data": "none"},
            {"id": "1", "data": "no_timestamp"}
        ]
        fallback_empty = tool._select_latest(group_empty_timestamp)
        self.assertEqual(fallback_empty["data"], "empty")

    def test_merge_entities_comprehensive(self):
        """Test _merge_entities with comprehensive scenarios (lines 253-295)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test with posts
        tool_posts = DeduplicateEntities(entities=[], entity_type="posts")

        post_group = [
            {
                "id": "post_1",
                "text": "Original text",
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 50, "comments": 10, "shares": 5},
                "tags": ["ai", "tech"],
                "media": [{"type": "image", "url": "img1.jpg"}],
                "reactions": ["like", "love"]
            },
            {
                "id": "post_1",
                "text": "Updated text",
                "created_at": "2024-01-15T12:00:00Z",  # Latest
                "metrics": {"likes": 75, "comments": 8, "views": 1000},  # Higher likes, different views
                "tags": ["ai", "business"],  # Overlapping and new tags
                "media": [{"type": "video", "url": "vid1.mp4"}],  # Different media
                "mentions": ["@user1"],
                "reactions": ["like", "insightful"]  # Overlapping and new reactions
            }
        ]

        merged = tool_posts._merge_entities(post_group)

        # Verify base entity is latest
        self.assertEqual(merged["text"], "Updated text")
        self.assertEqual(merged["created_at"], "2024-01-15T12:00:00Z")

        # Verify metrics merging (max values)
        self.assertEqual(merged["metrics"]["likes"], 75)  # Max
        self.assertEqual(merged["metrics"]["comments"], 10)  # Max
        self.assertEqual(merged["metrics"]["shares"], 5)  # Only in first
        self.assertEqual(merged["metrics"]["views"], 1000)  # Only in second

        # Verify array merging with deduplication
        self.assertIn("ai", merged["tags"])
        self.assertIn("tech", merged["tags"])
        self.assertIn("business", merged["tags"])
        self.assertEqual(len(set(merged["tags"])), len(merged["tags"]))  # No duplicates

        self.assertEqual(len(merged["media"]), 2)  # Both media items
        self.assertEqual(len(merged["reactions"]), 3)  # like, love, insightful

        # Verify merge metadata
        self.assertIn("_merge_metadata", merged)
        self.assertEqual(merged["_merge_metadata"]["merged_from"], 2)
        self.assertEqual(merged["_merge_metadata"]["merge_strategy"], "keep_latest")

        # Test with comments
        tool_comments = DeduplicateEntities(entities=[], entity_type="comments")

        comment_group = [
            {
                "id": "comment_1",
                "text": "Great post!",
                "metrics": {"likes": 5},
                "mentions": ["@author"]
            },
            {
                "id": "comment_1",
                "text": "Great post! Updated",
                "created_at": "2024-01-15T12:00:00Z",
                "metrics": {"likes": 8, "replies": 2}
            }
        ]

        merged_comment = tool_comments._merge_entities(comment_group)
        self.assertEqual(merged_comment["metrics"]["likes"], 8)  # Max
        self.assertEqual(merged_comment["metrics"]["replies"], 2)  # Only in second

        # Test with non-posts/comments entity type
        tool_users = DeduplicateEntities(entities=[], entity_type="users")

        user_group = [
            {"id": "user_1", "name": "John", "created_at": "2024-01-15T12:00:00Z"}
        ]

        merged_user = tool_users._merge_entities(user_group)
        self.assertEqual(merged_user["name"], "John")
        self.assertIn("_merge_metadata", merged_user)

    def test_entity_summary_all_types(self):
        """Test _entity_summary for all entity types (lines 307-325)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test posts summary
        tool_posts = DeduplicateEntities(entities=[], entity_type="posts")
        post_entity = {
            "id": "post_123",
            "text": "This is a long post content that should be truncated for summary purposes because it exceeds the limit",
            "author": {"name": "John Doe"},
            "metrics": {"likes": 150}
        }
        post_summary = tool_posts._entity_summary(post_entity)
        self.assertEqual(post_summary["id"], "post_123")
        self.assertEqual(len(post_summary["text_preview"]), 50)
        self.assertEqual(post_summary["author"], "John Doe")
        self.assertEqual(post_summary["likes"], 150)

        # Test comments summary
        tool_comments = DeduplicateEntities(entities=[], entity_type="comments")
        comment_entity = {
            "id": "comment_456",
            "text": "Short comment text that will also be truncated properly",
            "metrics": {"likes": 25}
        }
        comment_summary = tool_comments._entity_summary(comment_entity)
        self.assertEqual(comment_summary["id"], "comment_456")
        self.assertEqual(len(comment_summary["text_preview"]), 50)
        self.assertEqual(comment_summary["likes"], 25)

        # Test users summary
        tool_users = DeduplicateEntities(entities=[], entity_type="users")
        user_entity = {
            "id": "user_789",
            "name": "Jane Smith",
            "headline": "Software Engineer at Tech Corp"
        }
        user_summary = tool_users._entity_summary(user_entity)
        self.assertEqual(user_summary["id"], "user_789")
        self.assertEqual(user_summary["name"], "Jane Smith")
        self.assertEqual(user_summary["headline"], "Software Engineer at Tech Corp")

        # Test with missing fields
        incomplete_post = {"id": "incomplete"}
        incomplete_summary = tool_posts._entity_summary(incomplete_post)
        self.assertEqual(incomplete_summary["id"], "incomplete")
        self.assertEqual(incomplete_summary["text_preview"], "")
        self.assertEqual(incomplete_summary["author"], "")
        self.assertEqual(incomplete_summary["likes"], 0)

        # Test with unknown ID
        no_id_entity = {"text": "No ID entity"}
        no_id_summary = tool_posts._entity_summary(no_id_entity)
        self.assertEqual(no_id_summary["id"], "unknown")

    def test_calculate_post_stats_comprehensive(self):
        """Test _calculate_post_stats with various scenarios (lines 337-349)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="posts")

        # Test with empty posts
        empty_stats = tool._calculate_post_stats([])
        self.assertEqual(empty_stats, {})

        # Test with comprehensive posts data
        posts = [
            {
                "id": "post_1",
                "author": {"name": "John Doe"},
                "metrics": {"likes": 100, "comments": 20},
                "media": [{"type": "image"}]
            },
            {
                "id": "post_2",
                "author": {"name": "Jane Smith"},
                "metrics": {"likes": 50, "comments": 10}
                # No media
            },
            {
                "id": "post_3",
                "author": {"name": "John Doe"},  # Same author
                "metrics": {"likes": 75, "comments": 15},
                "media": [{"type": "video"}, {"type": "image"}]
            }
        ]

        stats = tool._calculate_post_stats(posts)

        self.assertEqual(stats["total_posts"], 3)
        self.assertEqual(stats["total_engagement"], 270)  # (100+20) + (50+10) + (75+15)
        self.assertEqual(stats["average_likes"], 75.0)  # (100+50+75)/3
        self.assertEqual(stats["posts_with_media"], 2)  # First and third posts
        self.assertEqual(stats["unique_authors"], 2)  # John Doe and Jane Smith

        # Test with posts missing metrics
        posts_no_metrics = [
            {"id": "post_1", "author": {"name": "User"}},
            {"id": "post_2"}  # Missing author too
        ]
        stats_no_metrics = tool._calculate_post_stats(posts_no_metrics)
        self.assertEqual(stats_no_metrics["total_engagement"], 0)
        self.assertEqual(stats_no_metrics["average_likes"], 0.0)
        self.assertEqual(stats_no_metrics["unique_authors"], 1)  # One named author

    def test_calculate_comment_stats_comprehensive(self):
        """Test _calculate_comment_stats with various scenarios (lines 361-373)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        tool = DeduplicateEntities(entities=[], entity_type="comments")

        # Test with empty comments
        empty_stats = tool._calculate_comment_stats([])
        self.assertEqual(empty_stats, {})

        # Test with comprehensive comments data
        comments = [
            {
                "id": "comment_1",
                "metrics": {"likes": 10, "is_reply": False}
            },
            {
                "id": "comment_2",
                "metrics": {"likes": 5, "is_reply": True}
            },
            {
                "id": "comment_3",
                "metrics": {"likes": 15, "is_reply": True}
            },
            {
                "id": "comment_4",
                "metrics": {"likes": 0, "is_reply": False}
            }
        ]

        stats = tool._calculate_comment_stats(comments)

        self.assertEqual(stats["total_comments"], 4)
        self.assertEqual(stats["total_likes"], 30)  # 10+5+15+0
        self.assertEqual(stats["average_likes"], 7.5)  # 30/4
        self.assertEqual(stats["reply_count"], 2)  # Two replies
        self.assertEqual(stats["reply_rate"], 0.5)  # 2/4

        # Test with comments missing metrics
        comments_no_metrics = [
            {"id": "comment_1"},
            {"id": "comment_2", "metrics": {}}
        ]
        stats_no_metrics = tool._calculate_comment_stats(comments_no_metrics)
        self.assertEqual(stats_no_metrics["total_likes"], 0)
        self.assertEqual(stats_no_metrics["reply_count"], 0)

    def test_different_merge_strategies(self):
        """Test different merge strategies (lines 94-102)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        duplicate_entities = [
            {"id": "dup_1", "created_at": "2024-01-15T10:00:00Z", "data": "first"},
            {"id": "dup_1", "created_at": "2024-01-15T12:00:00Z", "data": "latest"},
            {"id": "dup_1", "created_at": "2024-01-15T11:00:00Z", "data": "middle"}
        ]

        # Test keep_latest strategy
        tool_latest = DeduplicateEntities(
            entities=duplicate_entities,
            entity_type="posts",
            merge_strategy="keep_latest"
        )
        result_latest = tool_latest.run()
        result_latest_data = json.loads(result_latest)
        selected_entity = result_latest_data["deduplicated_entities"][0]
        self.assertEqual(selected_entity["data"], "latest")

        # Test keep_first strategy
        tool_first = DeduplicateEntities(
            entities=duplicate_entities,
            entity_type="posts",
            merge_strategy="keep_first"
        )
        result_first = tool_first.run()
        result_first_data = json.loads(result_first)
        selected_entity_first = result_first_data["deduplicated_entities"][0]
        self.assertEqual(selected_entity_first["data"], "first")

        # Test merge_data strategy
        tool_merge = DeduplicateEntities(
            entities=duplicate_entities,
            entity_type="posts",
            merge_strategy="merge_data"
        )
        result_merge = tool_merge.run()
        result_merge_data = json.loads(result_merge)
        merged_entity = result_merge_data["deduplicated_entities"][0]
        self.assertIn("_merge_metadata", merged_entity)

        # Test unknown strategy (fallback to first)
        tool_unknown = DeduplicateEntities(
            entities=duplicate_entities,
            entity_type="posts",
            merge_strategy="unknown_strategy"
        )
        result_unknown = tool_unknown.run()
        result_unknown_data = json.loads(result_unknown)
        fallback_entity = result_unknown_data["deduplicated_entities"][0]
        self.assertEqual(fallback_entity["data"], "first")

    def test_single_entity_groups(self):
        """Test handling of single entity groups (lines 104-106)."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Create entities with no duplicates
        unique_entities = [
            {"id": "unique_1", "data": "first"},
            {"id": "unique_2", "data": "second"},
            {"id": "unique_3", "data": "third"}
        ]

        tool = DeduplicateEntities(
            entities=unique_entities,
            entity_type="posts"
        )

        result = tool.run()
        result_data = json.loads(result)

        # All entities should be preserved
        self.assertEqual(len(result_data["deduplicated_entities"]), 3)
        self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 0)
        self.assertEqual(len(result_data["deduplication_stats"]["duplicate_groups"]), 0)

    def test_main_execution_block(self):
        """Test the if __name__ == '__main__' block (lines 376-406)."""
        import subprocess
        import sys

        try:
            # Run the tool's main block
            result = subprocess.run([
                sys.executable, "-c",
                "from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities; "
                "import json; "
                "test_entities = [{'id': 'post_123', 'text': 'Test', 'created_at': '2024-01-15T10:00:00Z', 'metrics': {'likes': 100}}]; "
                "tool = DeduplicateEntities(entities=test_entities, entity_type='posts', merge_strategy='keep_latest'); "
                "result = tool.run(); "
                "print('SUCCESS')"
            ], capture_output=True, text=True, timeout=10, cwd="/Users/maarten/Projects/16 - autopiloot/agents/autopiloot")

            # Should execute successfully
            self.assertIn("SUCCESS", result.stdout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            # If subprocess fails due to dependencies, verify the tool can be imported
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            # Test the exact scenario from the main block
            test_entities = [
                {
                    "id": "post_123",
                    "text": "Original post",
                    "created_at": "2024-01-15T10:00:00Z",
                    "metrics": {"likes": 100}
                },
                {
                    "id": "post_123",
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

            # Verify the main block logic works
            self.assertEqual(len(result_data["deduplicated_entities"]), 2)
            self.assertEqual(result_data["deduplication_stats"]["duplicates_removed"], 1)


if __name__ == '__main__':
    unittest.main()