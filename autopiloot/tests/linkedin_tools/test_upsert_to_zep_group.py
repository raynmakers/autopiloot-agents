"""
Unit tests for UpsertToZepGroup tool.
Tests Zep integration, document preparation, batch processing, and mock handling.
"""

import unittest
import json
from unittest.mock import patch, Mock, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.upsert_to_zep_group import UpsertToZepGroup


class TestUpsertToZepGroup(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.test_entities = [
            {
                "id": "urn:li:activity:12345",
                "content_hash": "abc123",
                "type": "post",
                "text": "Business growth insights from my experience",
                "author": {
                    "name": "Alex Hormozi",
                    "headline": "CEO at Acquisition.com",
                    "profile_url": "https://linkedin.com/in/alexhormozi"
                },
                "created_at": "2024-01-15T10:00:00Z",
                "normalized_at": "2024-01-15T10:30:00Z",
                "metrics": {
                    "likes": 150,
                    "comments": 25,
                    "shares": 10,
                    "engagement_rate": 0.05
                },
                "media": [
                    {"type": "image", "url": "https://example.com/image.jpg"}
                ]
            },
            {
                "id": "urn:li:comment:11111",
                "content_hash": "def456",
                "type": "comment",
                "text": "Great insights! Thanks for sharing this perspective.",
                "author": {
                    "name": "John Doe",
                    "headline": "Business Consultant",
                    "profile_url": "https://linkedin.com/in/johndoe"
                },
                "created_at": "2024-01-15T11:00:00Z",
                "normalized_at": "2024-01-15T11:30:00Z",
                "metrics": {
                    "likes": 5,
                    "is_reply": False
                },
                "parent_post_id": "urn:li:activity:12345"
            }
        ]

        self.tool = UpsertToZepGroup(
            entities=self.test_entities,
            profile_identifier="alexhormozi",
            content_type="posts",
            batch_size=10
        )

    @patch('linkedin_agent.tools.upsert_to_zep_group.load_environment')
    @patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var')
    @patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value')
    def test_successful_upsert_with_mock_client(self, mock_config, mock_env_var, mock_load_env):
        """Test successful upsert using mock Zep client."""
        # Mock environment and configuration
        mock_env_var.side_effect = lambda var, desc: {
            "ZEP_API_KEY": "test-zep-key"
        }[var]
        mock_config.side_effect = lambda key, default: {
            "linkedin.zep.group_prefix": "linkedin",
            "linkedin.zep.collection_name": "linkedin_content"
        }.get(key, default)

        # Run the tool (will use mock client due to ImportError)
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["group_id"], "linkedin_alexhormozi_posts")
        self.assertEqual(result_data["upsert_results"]["upserted"], 2)
        self.assertEqual(result_data["upsert_results"]["skipped"], 0)
        self.assertEqual(result_data["upsert_results"]["errors"], 0)

        # Check batch info
        batch_info = result_data["batch_info"]
        self.assertEqual(batch_info["total_batches"], 1)
        self.assertEqual(batch_info["batch_size"], 10)
        self.assertEqual(batch_info["total_documents"], 2)

        # Check metadata
        metadata = result_data["metadata"]
        self.assertEqual(metadata["collection_name"], "linkedin_content")
        self.assertEqual(metadata["content_type"], "posts")
        self.assertIn("processed_at", metadata)

    def test_group_name_generation(self):
        """Test automatic group name generation."""
        # Test with profile identifier
        tool = UpsertToZepGroup(
            entities=self.test_entities,
            profile_identifier="alex.hormozi",  # With special chars
            content_type="mixed"
        )

        # Mock dependencies
        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment'), \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value') as mock_config:

            mock_env.return_value = "test-key"
            mock_config.side_effect = lambda key, default: {
                "linkedin.zep.group_prefix": "linkedin",
                "linkedin.zep.collection_name": "linkedin_content"
            }.get(key, default)

            result = tool.run()
            result_data = json.loads(result)

            # Should clean profile identifier
            self.assertEqual(result_data["group_id"], "linkedin_alexhormozi_mixed")

    def test_custom_group_name(self):
        """Test custom group name override."""
        tool = UpsertToZepGroup(
            entities=self.test_entities,
            group_name="custom_linkedin_group",
            content_type="posts"
        )

        # Mock dependencies
        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment'), \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value') as mock_config:

            mock_env.return_value = "test-key"
            mock_config.return_value = "linkedin_content"

            result = tool.run()
            result_data = json.loads(result)

            # Should use custom group name
            self.assertEqual(result_data["group_id"], "custom_linkedin_group")

    def test_hash_based_group_name(self):
        """Test hash-based group name when no profile identifier."""
        tool = UpsertToZepGroup(
            entities=self.test_entities,
            content_type="posts"
            # No profile_identifier or group_name
        )

        # Mock dependencies
        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment'), \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value') as mock_config:

            mock_env.return_value = "test-key"
            mock_config.side_effect = lambda key, default: {
                "linkedin.zep.group_prefix": "linkedin",
                "linkedin.zep.collection_name": "linkedin_content"
            }.get(key, default)

            result = tool.run()
            result_data = json.loads(result)

            # Should generate hash-based name
            group_id = result_data["group_id"]
            self.assertTrue(group_id.startswith("linkedin_"))
            self.assertTrue(group_id.endswith("_posts"))
            # Should contain hash in middle
            parts = group_id.split("_")
            self.assertEqual(len(parts), 3)  # linkedin_{hash}_posts

    def test_document_preparation(self):
        """Test document preparation for Zep format."""
        # Access internal method for testing
        tool = UpsertToZepGroup(
            entities=self.test_entities,
            profile_identifier="testuser"
        )

        documents = tool._prepare_documents(self.test_entities)

        # Should prepare 2 documents
        self.assertEqual(len(documents), 2)

        # Check first document (post)
        post_doc = documents[0]
        self.assertEqual(post_doc["id"], "urn:li:activity:12345")
        self.assertEqual(post_doc["content"], "Business growth insights from my experience")

        # Check metadata
        metadata = post_doc["metadata"]
        self.assertEqual(metadata["type"], "post")
        self.assertEqual(metadata["source"], "linkedin")
        self.assertEqual(metadata["author_name"], "Alex Hormozi")
        self.assertEqual(metadata["likes"], 150)
        self.assertEqual(metadata["comments"], 25)
        self.assertTrue(metadata["has_media"])
        self.assertEqual(metadata["media_types"], ["image"])

        # Check second document (comment)
        comment_doc = documents[1]
        self.assertEqual(comment_doc["id"], "urn:li:comment:11111")
        self.assertEqual(comment_doc["content"], "Great insights! Thanks for sharing this perspective.")

        # Check comment-specific metadata
        comment_metadata = comment_doc["metadata"]
        self.assertEqual(comment_metadata["type"], "comment")
        self.assertEqual(comment_metadata["parent_post_id"], "urn:li:activity:12345")
        self.assertFalse(comment_metadata["is_reply"])

    def test_batch_processing(self):
        """Test batch processing with small batch size."""
        # Create larger entity list
        large_entities = []
        for i in range(25):
            entity = {
                "id": f"urn:li:activity:1234{i}",
                "type": "post",
                "text": f"Post content {i}",
                "author": {"name": f"User {i}"},
                "metrics": {"likes": i * 10}
            }
            large_entities.append(entity)

        tool = UpsertToZepGroup(
            entities=large_entities,
            profile_identifier="testuser",
            batch_size=5  # Small batch size
        )

        # Mock dependencies
        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment'), \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value') as mock_config:

            mock_env.return_value = "test-key"
            mock_config.side_effect = lambda key, default: {
                "linkedin.zep.group_prefix": "linkedin",
                "linkedin.zep.collection_name": "linkedin_content"
            }.get(key, default)

            result = tool.run()
            result_data = json.loads(result)

            # Should process all entities in batches
            self.assertEqual(result_data["upsert_results"]["upserted"], 25)
            self.assertEqual(result_data["batch_info"]["total_batches"], 5)  # 25/5 = 5 batches
            self.assertEqual(result_data["batch_info"]["batch_size"], 5)

    def test_empty_entities_handling(self):
        """Test handling of empty entities list."""
        tool = UpsertToZepGroup(
            entities=[],
            profile_identifier="testuser"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should return error for empty entities
        self.assertEqual(result_data["error"], "no_entities")
        self.assertIn("No entities provided", result_data["message"])

    def test_entities_without_text(self):
        """Test handling of entities without text content."""
        entities_no_text = [
            {
                "id": "urn:li:activity:12345",
                "type": "post",
                # No text field
                "author": {"name": "Test User"},
                "metrics": {"likes": 10}
            },
            {
                "id": "urn:li:activity:12346",
                "type": "post",
                "text": "",  # Empty text
                "author": {"name": "Test User"},
                "metrics": {"likes": 5}
            },
            {
                "id": "urn:li:activity:12347",
                "type": "post",
                "text": "Valid post content",
                "author": {"name": "Test User"},
                "metrics": {"likes": 15}
            }
        ]

        tool = UpsertToZepGroup(
            entities=entities_no_text,
            profile_identifier="testuser"
        )

        # Mock dependencies
        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment'), \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value') as mock_config:

            mock_env.return_value = "test-key"
            mock_config.side_effect = lambda key, default: {
                "linkedin.zep.group_prefix": "linkedin",
                "linkedin.zep.collection_name": "linkedin_content"
            }.get(key, default)

            result = tool.run()
            result_data = json.loads(result)

            # Should only process entities with text content
            self.assertEqual(result_data["upsert_results"]["upserted"], 1)  # Only the valid one
            self.assertEqual(result_data["batch_info"]["total_documents"], 1)

    @patch('linkedin_agent.tools.upsert_to_zep_group.load_environment')
    @patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var')
    def test_environment_error_handling(self, mock_env_var, mock_load_env):
        """Test handling of environment configuration errors."""
        # Mock missing environment variable
        mock_env_var.side_effect = Exception("ZEP_API_KEY not found")

        result = self.tool.run()
        result_data = json.loads(result)

        # Should return error
        self.assertEqual(result_data["error"], "zep_upsert_failed")
        self.assertIn("ZEP_API_KEY not found", result_data["message"])
        self.assertEqual(result_data["entity_count"], 2)
        self.assertEqual(result_data["content_type"], "posts")

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            UpsertToZepGroup()  # Missing required entities

        # Test default values
        tool = UpsertToZepGroup(entities=self.test_entities)
        self.assertEqual(tool.content_type, "mixed")
        self.assertEqual(tool.batch_size, 50)
        self.assertIsNone(tool.group_name)
        self.assertIsNone(tool.profile_identifier)

        # Test field constraints
        tool = UpsertToZepGroup(
            entities=self.test_entities,
            group_name="custom_group",
            profile_identifier="test_user",
            content_type="comments",
            batch_size=25
        )
        self.assertEqual(tool.group_name, "custom_group")
        self.assertEqual(tool.profile_identifier, "test_user")
        self.assertEqual(tool.content_type, "comments")
        self.assertEqual(tool.batch_size, 25)


if __name__ == '__main__':
    unittest.main()