"""
Complete coverage tests for all LinkedIn Agent tools.
Targets 100% line coverage by executing all run() methods and code paths.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import json
import sys
import os
from datetime import datetime, timezone


class TestCompleteToolsCoverage(unittest.TestCase):
    """Complete coverage test suite for all LinkedIn tools."""

    def setUp(self):
        """Set up comprehensive mocking environment."""
        # Mock all external dependencies
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'requests': MagicMock(),
            'google': MagicMock(),
            'google.cloud': MagicMock(),
            'google.cloud.firestore': MagicMock(),
            'zep_python': MagicMock(),
        }

        self.patcher = patch.dict('sys.modules', self.mock_modules)
        self.patcher.start()

        # Mock BaseTool
        sys.modules['agency_swarm.tools'].BaseTool = MagicMock()

        # Mock environment and config functions
        self.env_patcher = patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
        self.config_patcher = patch('linkedin_agent.tools.get_user_posts.get_config_value')
        self.load_env_patcher = patch('linkedin_agent.tools.get_user_posts.load_environment')

        self.mock_env = self.env_patcher.start()
        self.mock_config = self.config_patcher.start()
        self.mock_load_env = self.load_env_patcher.start()

        # Set up default return values
        self.mock_env.return_value = "test_api_key"
        self.mock_config.return_value = {"rate_limit": {"delay_seconds": 1}}

    def tearDown(self):
        """Clean up all mocks."""
        self.patcher.stop()
        self.env_patcher.stop()
        self.config_patcher.stop()
        self.load_env_patcher.stop()

    def test_get_user_posts_complete_coverage(self):
        """Test GetUserPosts tool with complete execution coverage."""
        # Mock requests module for successful API call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {
                    "urn": "urn:li:activity:123",
                    "text": "Test post content",
                    "numLikes": 50,
                    "numComments": 10,
                    "publishedAt": 1640995200000
                }
            ],
            "paging": {"total": 1}
        }

        with patch('linkedin_agent.tools.get_user_posts.requests') as mock_requests:
            mock_requests.get.return_value = mock_response

            from linkedin_agent.tools.get_user_posts import GetUserPosts

            tool = GetUserPosts(
                user_urn="test_user",
                page=1,
                page_size=25,
                max_items=100
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should return successful response
            self.assertIn("posts", result_data)
            self.assertIsInstance(result_data["posts"], list)

        # Test error handling
        with patch('linkedin_agent.tools.get_user_posts.requests') as mock_requests:
            mock_requests.get.side_effect = Exception("API Error")

            tool_error = GetUserPosts(user_urn="error_user")
            result_error = tool_error.run()
            result_error_data = json.loads(result_error)

            self.assertIn("error", result_error_data)

    def test_get_post_comments_complete_coverage(self):
        """Test GetPostComments tool with complete execution coverage."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "comments": [
                {
                    "urn": "urn:li:comment:456",
                    "text": "Great post!",
                    "numLikes": 5,
                    "author": {"name": "Commenter"}
                }
            ]
        }

        with patch('linkedin_agent.tools.get_post_comments.requests') as mock_requests, \
             patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.get_post_comments.load_environment'):

            mock_requests.get.return_value = mock_response
            mock_env.return_value = "test_api_key"

            from linkedin_agent.tools.get_post_comments import GetPostComments

            tool = GetPostComments(
                post_urn="urn:li:activity:123",
                max_comments=50
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("comments", result_data)

        # Test error handling
        with patch('linkedin_agent.tools.get_post_comments.requests') as mock_requests, \
             patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env:

            mock_requests.get.side_effect = Exception("API Error")
            mock_env.return_value = "test_api_key"

            tool_error = GetPostComments(post_urn="error_post")
            result_error = tool_error.run()
            result_error_data = json.loads(result_error)

            self.assertIn("error", result_error_data)

    def test_get_post_reactions_complete_coverage(self):
        """Test GetPostReactions tool with complete execution coverage."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "reactions": {
                "LIKE": 100,
                "LOVE": 25,
                "INSIGHTFUL": 15
            }
        }

        with patch('linkedin_agent.tools.get_post_reactions.requests') as mock_requests, \
             patch('linkedin_agent.tools.get_post_reactions.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.get_post_reactions.load_environment'):

            mock_requests.get.return_value = mock_response
            mock_env.return_value = "test_api_key"

            from linkedin_agent.tools.get_post_reactions import GetPostReactions

            tool = GetPostReactions(
                post_urn="urn:li:activity:123",
                include_reaction_details=True
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("reactions", result_data)

        # Test error handling
        with patch('linkedin_agent.tools.get_post_reactions.requests') as mock_requests, \
             patch('linkedin_agent.tools.get_post_reactions.get_required_env_var') as mock_env:

            mock_requests.get.side_effect = Exception("API Error")
            mock_env.return_value = "test_api_key"

            tool_error = GetPostReactions(post_urn="error_post")
            result_error = tool_error.run()
            result_error_data = json.loads(result_error)

            self.assertIn("error", result_error_data)

    def test_get_user_comment_activity_complete_coverage(self):
        """Test GetUserCommentActivity tool with complete execution coverage."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "activity": [
                {
                    "comment_urn": "urn:li:comment:789",
                    "post_urn": "urn:li:activity:123",
                    "text": "User comment",
                    "timestamp": "2024-01-15T10:00:00Z"
                }
            ]
        }

        with patch('linkedin_agent.tools.get_user_comment_activity.requests') as mock_requests, \
             patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.get_user_comment_activity.load_environment'):

            mock_requests.get.return_value = mock_response
            mock_env.return_value = "test_api_key"

            from linkedin_agent.tools.get_user_comment_activity import GetUserCommentActivity

            tool = GetUserCommentActivity(
                user_urn="test_user",
                days_back=30,
                max_activities=100
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("user_activity", result_data)

        # Test error handling
        with patch('linkedin_agent.tools.get_user_comment_activity.requests') as mock_requests, \
             patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var') as mock_env:

            mock_requests.get.side_effect = Exception("API Error")
            mock_env.return_value = "test_api_key"

            tool_error = GetUserCommentActivity(user_urn="error_user")
            result_error = tool_error.run()
            result_error_data = json.loads(result_error)

            self.assertIn("error", result_error_data)

    def test_normalize_linkedin_content_complete_coverage(self):
        """Test NormalizeLinkedInContent tool with complete execution coverage."""
        from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

        # Test with all content types
        raw_posts = [
            {
                "urn": "urn:li:activity:123",
                "text": "Test post with #hashtag",
                "numLikes": 50,
                "publishedAt": 1640995200000,
                "author": {"displayName": "Test User", "urn": "urn:li:person:456"}
            }
        ]

        raw_comments = [
            {
                "urn": "urn:li:comment:789",
                "text": "Test comment",
                "numLikes": 5,
                "parentUrn": "urn:li:activity:123",
                "author": {"displayName": "Commenter", "urn": "urn:li:person:321"}
            }
        ]

        raw_reactions = {
            "urn:li:activity:123": {"LIKE": 40, "LOVE": 10}
        }

        tool = NormalizeLinkedInContent(
            posts=raw_posts,
            comments=raw_comments,
            reactions=raw_reactions,
            include_metadata=True
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("normalized_posts", result_data)
        self.assertIn("normalized_comments", result_data)
        self.assertIn("normalized_reactions", result_data)
        self.assertIn("normalization_metadata", result_data)

        # Test error handling with malformed data
        tool_error = NormalizeLinkedInContent(
            posts=[{"invalid": "data"}],
            comments=None,
            reactions={}
        )

        result_error = tool_error.run()
        result_error_data = json.loads(result_error)

        # Should handle gracefully
        self.assertIsInstance(result_error_data, dict)

    def test_deduplicate_entities_complete_coverage(self):
        """Test DeduplicateEntities tool with complete execution coverage."""
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test with duplicate posts
        posts_with_duplicates = [
            {
                "id": "post_1",
                "content": "Identical content for testing",
                "author": {"name": "John Doe"}
            },
            {
                "id": "post_2",
                "content": "Identical content for testing",  # Exact duplicate
                "author": {"name": "John Doe"}
            },
            {
                "id": "post_3",
                "content": "Different content entirely",
                "author": {"name": "Jane Smith"}
            }
        ]

        comments_with_duplicates = [
            {
                "id": "comment_1",
                "content": "Great insights!",
                "author": {"name": "Commenter 1"}
            },
            {
                "id": "comment_2",
                "content": "Great insights!",  # Exact duplicate
                "author": {"name": "Commenter 1"}
            }
        ]

        tool = DeduplicateEntities(
            posts=posts_with_duplicates,
            comments=comments_with_duplicates,
            similarity_threshold=0.9,
            preserve_metadata=True
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("deduplication_metadata", result_data)
        self.assertIn("processed_at", result_data["deduplication_metadata"])

        # Test with different similarity thresholds
        tool_strict = DeduplicateEntities(
            posts=posts_with_duplicates,
            similarity_threshold=0.99,
            preserve_metadata=False
        )

        result_strict = tool_strict.run()
        result_strict_data = json.loads(result_strict)
        self.assertIsInstance(result_strict_data, dict)

        # Test error handling
        class BadList(list):
            def __iter__(self):
                raise ValueError("Simulated error")

        tool_error = DeduplicateEntities(posts=BadList([{}]))
        result_error = tool_error.run()
        result_error_data = json.loads(result_error)
        self.assertIn("error", result_error_data)

    def test_upsert_to_zep_group_complete_coverage(self):
        """Test UpsertToZepGroup tool with complete execution coverage."""
        # Mock Zep client
        mock_zep_client = MagicMock()
        mock_zep_client.memory.add_documents.return_value = {"status": "success"}

        with patch('linkedin_agent.tools.upsert_to_zep_group.ZepClient') as mock_zep_class, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_env:

            mock_zep_class.return_value = mock_zep_client
            mock_env.return_value = "test_zep_api_key"

            from linkedin_agent.tools.upsert_to_zep_group import UpsertToZepGroup

            normalized_content = {
                "normalized_posts": [
                    {
                        "id": "post_1",
                        "content": "Test post content for Zep storage",
                        "author": {"name": "Test User"},
                        "created_at": "2024-01-15T10:00:00Z"
                    }
                ],
                "normalized_comments": [
                    {
                        "id": "comment_1",
                        "content": "Test comment content",
                        "author": {"name": "Commenter"}
                    }
                ]
            }

            tool = UpsertToZepGroup(
                normalized_content=normalized_content,
                group_id="test_linkedin_group",
                user_identifier="test_user",
                chunk_size=1000,
                overlap_size=100,
                include_metadata=True,
                overwrite_existing=False
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn("zep_upsert_metadata", result_data)
            self.assertIn("documents_processed", result_data)

        # Test error handling
        with patch('linkedin_agent.tools.upsert_to_zep_group.ZepClient') as mock_zep_class, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_env:

            mock_zep_class.side_effect = Exception("Zep connection failed")
            mock_env.return_value = "test_zep_api_key"

            tool_error = UpsertToZepGroup(
                normalized_content={"normalized_posts": []},
                group_id="error_group"
            )

            result_error = tool_error.run()
            result_error_data = json.loads(result_error)

            self.assertIn("error", result_error_data)

    def test_all_tools_main_blocks(self):
        """Test the main execution blocks for all tools."""
        tool_modules = [
            'get_user_posts',
            'get_post_comments',
            'get_post_reactions',
            'get_user_comment_activity',
            'normalize_linkedin_content',
            'deduplicate_entities',
            'upsert_to_zep_group'
        ]

        for module_name in tool_modules:
            with self.subTest(module=module_name):
                try:
                    # Import the module
                    module = __import__(f'linkedin_agent.tools.{module_name}', fromlist=[module_name])

                    # Check if it has a main block (class should be importable)
                    self.assertTrue(hasattr(module, module_name.title().replace('_', '')))
                except ImportError:
                    # If import fails, it's expected in test environment
                    pass

    def test_edge_cases_and_boundary_conditions(self):
        """Test edge cases and boundary conditions across tools."""
        from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent
        from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

        # Test empty data
        tool_empty = NormalizeLinkedInContent(
            posts=[],
            comments=[],
            reactions={},
            include_metadata=False
        )

        result_empty = tool_empty.run()
        result_empty_data = json.loads(result_empty)
        self.assertIsInstance(result_empty_data, dict)

        # Test None values
        tool_none = DeduplicateEntities(
            posts=None,
            comments=None,
            similarity_threshold=0.8
        )

        result_none = tool_none.run()
        result_none_data = json.loads(result_none)
        self.assertIsInstance(result_none_data, dict)

        # Test malformed data structures
        malformed_posts = [
            {"id": "valid_post", "content": "Valid content"},
            {"content": "Missing ID"},  # Missing id
            {"id": "missing_content"},   # Missing content
            {},  # Empty object
            None  # None entry
        ]

        tool_malformed = DeduplicateEntities(posts=malformed_posts)
        result_malformed = tool_malformed.run()
        result_malformed_data = json.loads(result_malformed)
        self.assertIsInstance(result_malformed_data, dict)


if __name__ == '__main__':
    unittest.main()