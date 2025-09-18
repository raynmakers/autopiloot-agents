"""
Unit tests for NormalizeLinkedInContent tool.
Tests content normalization, schema compliance, and data transformation.
"""

import unittest
import json
from unittest.mock import patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent


class TestNormalizeLinkedInContent(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.raw_posts = [
            {
                "id": "urn:li:activity:12345",
                "text": "Building a successful business requires focus on customer value and operational efficiency.",
                "author": {
                    "name": "Alex Hormozi",
                    "headline": "CEO at Acquisition.com | Business Strategy",
                    "profile_url": "https://linkedin.com/in/alexhormozi",
                    "connections": 500
                },
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {
                    "likes": 1250,
                    "comments": 89,
                    "shares": 45,
                    "reposts": 23
                },
                "media": [
                    {"type": "image", "url": "https://media.licdn.com/image123.jpg"},
                    {"type": "document", "url": "https://media.licdn.com/doc456.pdf"}
                ]
            }
        ]

        self.raw_comments = [
            {
                "id": "urn:li:comment:11111",
                "text": "Excellent insights! This aligns with what we've seen in our industry.",
                "author": {
                    "name": "Sarah Johnson",
                    "headline": "VP of Operations at TechCorp",
                    "profile_url": "https://linkedin.com/in/sarahjohnson"
                },
                "created_at": "2024-01-15T11:30:00Z",
                "metrics": {
                    "likes": 25,
                    "replies": 3,
                    "is_reply": False
                },
                "parent_post_id": "urn:li:activity:12345"
            }
        ]

        self.tool = NormalizeLinkedInContent(
            raw_posts=self.raw_posts,
            raw_comments=self.raw_comments,
            schema_version="1.0"
        )

    def test_successful_normalization(self):
        """Test successful content normalization."""
        result = self.tool.run()
        result_data = json.loads(result)

        # Check overall structure
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(result_data["schema_version"], "1.0")
        self.assertEqual(len(result_data["normalized_entities"]), 2)

        # Check statistics
        stats = result_data["processing_stats"]
        self.assertEqual(stats["total_entities"], 2)
        self.assertEqual(stats["posts_processed"], 1)
        self.assertEqual(stats["comments_processed"], 1)
        self.assertEqual(stats["users_processed"], 1)

        # Validate normalized post
        normalized_post = next((e for e in result_data["normalized_entities"] if e["type"] == "post"), None)
        self.assertIsNotNone(normalized_post)

        self.assertEqual(normalized_post["id"], "urn:li:activity:12345")
        self.assertEqual(normalized_post["type"], "post")
        self.assertIn("content_hash", normalized_post)
        self.assertEqual(normalized_post["text"], self.raw_posts[0]["text"])
        self.assertEqual(normalized_post["created_at"], "2024-01-15T10:00:00Z")
        self.assertIn("normalized_at", normalized_post)

        # Check author normalization
        author = normalized_post["author"]
        self.assertEqual(author["name"], "Alex Hormozi")
        self.assertEqual(author["headline"], "CEO at Acquisition.com | Business Strategy")
        self.assertEqual(author["profile_url"], "https://linkedin.com/in/alexhormozi")

        # Check metrics normalization
        metrics = normalized_post["metrics"]
        self.assertEqual(metrics["likes"], 1250)
        self.assertEqual(metrics["comments"], 89)
        self.assertEqual(metrics["shares"], 45)
        self.assertIn("engagement_rate", metrics)
        self.assertGreater(metrics["engagement_rate"], 0)

        # Check media normalization
        self.assertEqual(len(normalized_post["media"]), 2)
        self.assertEqual(normalized_post["media"][0]["type"], "image")

    def test_engagement_rate_calculation(self):
        """Test engagement rate calculation."""
        # Test the internal method
        post_data = self.raw_posts[0]
        engagement_rate = self.tool._calculate_engagement_rate(post_data)

        # Calculate expected rate: (likes + comments + shares + reposts) / connections
        expected_rate = (1250 + 89 + 45 + 23) / 500
        self.assertAlmostEqual(engagement_rate, expected_rate, places=4)

    def test_engagement_rate_fallback(self):
        """Test engagement rate calculation fallback when no connections data."""
        post_without_connections = {
            "metrics": {"likes": 100, "comments": 10, "shares": 5},
            "author": {"name": "Test User"}  # No connections field
        }

        engagement_rate = self.tool._calculate_engagement_rate(post_without_connections)

        # Should return 0.0 when connections data is not available
        self.assertEqual(engagement_rate, 0.0)

    def test_content_hash_generation(self):
        """Test content hash generation."""
        hash1 = self.tool._generate_content_hash("urn:li:activity:12345", "post")
        hash2 = self.tool._generate_content_hash("urn:li:activity:12345", "post")
        hash3 = self.tool._generate_content_hash("urn:li:activity:54321", "post")

        # Same content should generate same hash
        self.assertEqual(hash1, hash2)

        # Different content should generate different hash
        self.assertNotEqual(hash1, hash3)

        # Hash should be 16 characters
        self.assertEqual(len(hash1), 16)

    def test_comment_normalization(self):
        """Test comment-specific normalization."""
        result = self.tool.run()
        result_data = json.loads(result)

        # Find normalized comment
        normalized_comment = next((e for e in result_data["normalized_entities"] if e["type"] == "comment"), None)
        self.assertIsNotNone(normalized_comment)

        # Check comment-specific fields
        self.assertEqual(normalized_comment["id"], "urn:li:comment:11111")
        self.assertEqual(normalized_comment["type"], "comment")
        self.assertEqual(normalized_comment["parent_post_id"], "urn:li:activity:12345")

        # Check comment metrics
        metrics = normalized_comment["metrics"]
        self.assertEqual(metrics["likes"], 25)
        self.assertEqual(metrics["replies"], 3)
        self.assertFalse(metrics["is_reply"])

    def test_empty_content_handling(self):
        """Test handling of empty content lists."""
        tool = NormalizeLinkedInContent(
            raw_posts=[],
            raw_comments=[],
            schema_version="1.0"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should handle empty content gracefully
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(len(result_data["normalized_entities"]), 0)
        self.assertEqual(result_data["processing_stats"]["total_entities"], 0)

    def test_malformed_content_handling(self):
        """Test handling of malformed content."""
        malformed_posts = [
            {
                "id": "urn:li:activity:12345",
                # Missing required fields like text, author, etc.
                "created_at": "2024-01-15T10:00:00Z"
            },
            {
                # Missing id
                "text": "Post without ID",
                "author": {"name": "Test User"}
            }
        ]

        tool = NormalizeLinkedInContent(
            raw_posts=malformed_posts,
            raw_comments=[],
            schema_version="1.0"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should skip malformed content but not fail completely
        self.assertEqual(result_data["status"], "success")

        # Should report processing issues
        stats = result_data["processing_stats"]
        self.assertGreater(stats["processing_errors"], 0)

    def test_schema_version_validation(self):
        """Test schema version handling."""
        # Test default schema version
        tool_default = NormalizeLinkedInContent(
            raw_posts=self.raw_posts,
            raw_comments=[]
        )
        self.assertEqual(tool_default.schema_version, "1.0")

        # Test custom schema version
        tool_custom = NormalizeLinkedInContent(
            raw_posts=self.raw_posts,
            raw_comments=[],
            schema_version="2.0"
        )
        self.assertEqual(tool_custom.schema_version, "2.0")

        result = tool_custom.run()
        result_data = json.loads(result)
        self.assertEqual(result_data["schema_version"], "2.0")

    def test_user_deduplication(self):
        """Test user deduplication across posts and comments."""
        # Create content with duplicate authors
        duplicate_author_posts = [
            {
                "id": "urn:li:activity:1",
                "text": "Post 1",
                "author": {
                    "name": "John Doe",
                    "profile_url": "https://linkedin.com/in/johndoe",
                    "headline": "Engineer"
                },
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 10}
            },
            {
                "id": "urn:li:activity:2",
                "text": "Post 2",
                "author": {
                    "name": "John Doe",  # Same author
                    "profile_url": "https://linkedin.com/in/johndoe",
                    "headline": "Senior Engineer"  # Updated headline
                },
                "created_at": "2024-01-15T11:00:00Z",
                "metrics": {"likes": 15}
            }
        ]

        tool = NormalizeLinkedInContent(
            raw_posts=duplicate_author_posts,
            raw_comments=[],
            schema_version="1.0"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should have processed 2 posts but only 1 unique user
        stats = result_data["processing_stats"]
        self.assertEqual(stats["posts_processed"], 2)
        self.assertEqual(stats["users_processed"], 1)

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            NormalizeLinkedInContent()  # Missing required fields

        # Test with minimal required fields
        tool = NormalizeLinkedInContent(
            raw_posts=[],
            raw_comments=[]
        )
        self.assertEqual(tool.schema_version, "1.0")  # Default value
        self.assertEqual(len(tool.raw_posts), 0)
        self.assertEqual(len(tool.raw_comments), 0)

        # Test field types
        tool_full = NormalizeLinkedInContent(
            raw_posts=self.raw_posts,
            raw_comments=self.raw_comments,
            schema_version="1.5"
        )
        self.assertEqual(tool_full.schema_version, "1.5")
        self.assertEqual(len(tool_full.raw_posts), 1)
        self.assertEqual(len(tool_full.raw_comments), 1)


if __name__ == '__main__':
    unittest.main()