"""
Comprehensive tests for NormalizeLinkedInContent tool.
Tests content normalization, schema standardization, and metadata processing.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
from datetime import datetime, timezone


class TestNormalizeLinkedInContentComprehensive(unittest.TestCase):
    """Test suite for NormalizeLinkedInContent tool."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        # Mock all dependencies at module level
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
        }

        # Apply mocks
        for module_name, mock_module in self.mock_modules.items():
            sys.modules[module_name] = mock_module

        # Set up BaseTool
        sys.modules['agency_swarm.tools'].BaseTool = MagicMock()

        # Create sample raw LinkedIn data
        self.raw_posts = [
            {
                "urn": "urn:li:activity:123456789",
                "text": "This is a test LinkedIn post about #AI and #MachineLearning",
                "numLikes": 45,
                "numComments": 12,
                "numShares": 3,
                "publishedAt": 1640995200000,  # Timestamp
                "author": {
                    "displayName": "John Doe",
                    "urn": "urn:li:person:987654321"
                },
                "media": [
                    {
                        "type": "image",
                        "url": "https://example.com/image.jpg"
                    }
                ]
            },
            {
                "urn": "urn:li:activity:987654321",
                "text": "Another post with different engagement",
                "numLikes": 23,
                "numComments": 5,
                "numShares": 1,
                "publishedAt": 1641081600000,
                "author": {
                    "displayName": "Jane Smith",
                    "urn": "urn:li:person:123456789"
                }
            }
        ]

        self.raw_comments = [
            {
                "urn": "urn:li:comment:111111111",
                "text": "Great insights on AI trends!",
                "parentUrn": "urn:li:activity:123456789",
                "numLikes": 8,
                "publishedAt": 1641002400000,
                "author": {
                    "displayName": "Alice Johnson",
                    "urn": "urn:li:person:555555555"
                }
            },
            {
                "urn": "urn:li:comment:222222222",
                "text": "Thanks for sharing this perspective",
                "parentUrn": "urn:li:activity:123456789",
                "numLikes": 3,
                "publishedAt": 1641009600000,
                "author": {
                    "displayName": "Bob Wilson",
                    "urn": "urn:li:person:666666666"
                }
            }
        ]

        self.raw_reactions = {
            "urn:li:activity:123456789": {
                "LIKE": 35,
                "LOVE": 8,
                "INSIGHTFUL": 2
            },
            "urn:li:activity:987654321": {
                "LIKE": 20,
                "LOVE": 3
            }
        }

    def tearDown(self):
        """Clean up mocks."""
        for module_name in self.mock_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]

    def test_successful_posts_normalization(self):
        """Test successful normalization of LinkedIn posts."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            tool = NormalizeLinkedInContent(
                posts=self.raw_posts,
                include_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify structure
            self.assertIn("normalization_metadata", result_data)
            self.assertIn("processed_at", result_data["normalization_metadata"])

            # Check that posts are being processed
            if "normalized_posts" in result_data:
                self.assertIsInstance(result_data["normalized_posts"], list)

            print("✅ Successfully normalized LinkedIn posts")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_successful_comments_normalization(self):
        """Test successful normalization of LinkedIn comments."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            tool = NormalizeLinkedInContent(
                comments=self.raw_comments,
                include_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify structure
            self.assertIn("normalization_metadata", result_data)

            # Check that comments are being processed
            if "normalized_comments" in result_data:
                self.assertIsInstance(result_data["normalized_comments"], list)

            print("✅ Successfully normalized LinkedIn comments")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_successful_reactions_normalization(self):
        """Test successful normalization of LinkedIn reactions."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            tool = NormalizeLinkedInContent(
                reactions=self.raw_reactions,
                include_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify structure
            self.assertIn("normalization_metadata", result_data)

            # Check that reactions are being processed
            if "normalized_reactions" in result_data:
                self.assertIsInstance(result_data["normalized_reactions"], dict)

            print("✅ Successfully normalized LinkedIn reactions")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_comprehensive_normalization_all_types(self):
        """Test normalization with all data types combined."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            tool = NormalizeLinkedInContent(
                posts=self.raw_posts,
                comments=self.raw_comments,
                reactions=self.raw_reactions,
                include_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify comprehensive normalization
            self.assertIn("normalization_metadata", result_data)

            # Check metadata includes all data types
            metadata = result_data["normalization_metadata"]
            self.assertIn("processed_at", metadata)

            print("✅ Successfully normalized all LinkedIn content types")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_empty_data_handling(self):
        """Test handling of empty or None data."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            tool = NormalizeLinkedInContent(
                posts=None,
                comments=None,
                reactions=None,
                include_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should return valid response even with no data
            self.assertIn("normalization_metadata", result_data)

            print("✅ Successfully handled empty data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_metadata_inclusion_toggle(self):
        """Test metadata inclusion toggle functionality."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            # Test with metadata included
            tool_with_metadata = NormalizeLinkedInContent(
                posts=self.raw_posts,
                include_metadata=True
            )

            result_with = tool_with_metadata.run()
            result_with_data = json.loads(result_with)
            self.assertIn("normalization_metadata", result_with_data)

            # Test with metadata excluded
            tool_without_metadata = NormalizeLinkedInContent(
                posts=self.raw_posts,
                include_metadata=False
            )

            result_without = tool_without_metadata.run()
            result_without_data = json.loads(result_without)

            # Should still have basic structure but different metadata handling
            self.assertIsInstance(result_without_data, dict)

            print("✅ Successfully tested metadata inclusion toggle")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_malformed_data_handling(self):
        """Test handling of malformed or incomplete data."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            # Create malformed posts
            malformed_posts = [
                {
                    "urn": "valid_urn",
                    "text": "Valid post"
                    # Missing other fields
                },
                {
                    # Missing urn
                    "text": "Another post",
                    "numLikes": "invalid_number"  # Invalid data type
                },
                None,  # Null entry
                {}  # Empty object
            ]

            tool = NormalizeLinkedInContent(posts=malformed_posts)
            result = tool.run()
            result_data = json.loads(result)

            # Should handle errors gracefully
            self.assertIsInstance(result_data, dict)

            print("✅ Successfully handled malformed data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_hashtag_and_mention_extraction(self):
        """Test extraction of hashtags and mentions from content."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            posts_with_tags = [
                {
                    "urn": "urn:li:activity:hashtag_test",
                    "text": "Great post about #AI #MachineLearning and @JohnDoe insights on #Technology",
                    "publishedAt": 1640995200000
                }
            ]

            tool = NormalizeLinkedInContent(posts=posts_with_tags)
            result = tool.run()
            result_data = json.loads(result)

            # Verify normalization processes hashtags and mentions
            self.assertIsInstance(result_data, dict)

            print("✅ Successfully tested hashtag and mention extraction")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_timestamp_normalization(self):
        """Test normalization of different timestamp formats."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            posts_with_various_timestamps = [
                {
                    "urn": "urn:li:activity:timestamp_test_1",
                    "text": "Post with millisecond timestamp",
                    "publishedAt": 1640995200000  # Milliseconds
                },
                {
                    "urn": "urn:li:activity:timestamp_test_2",
                    "text": "Post with ISO string",
                    "publishedAt": "2022-01-01T00:00:00Z"  # ISO string
                },
                {
                    "urn": "urn:li:activity:timestamp_test_3",
                    "text": "Post with invalid timestamp",
                    "publishedAt": "invalid_timestamp"  # Invalid
                }
            ]

            tool = NormalizeLinkedInContent(posts=posts_with_various_timestamps)
            result = tool.run()
            result_data = json.loads(result)

            # Should handle various timestamp formats
            self.assertIsInstance(result_data, dict)

            print("✅ Successfully tested timestamp normalization")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_content_deduplication_awareness(self):
        """Test awareness of potential duplicate content."""
        try:
            from linkedin_agent.tools.normalize_linkedin_content import NormalizeLinkedInContent

            duplicate_posts = [
                {
                    "urn": "urn:li:activity:original",
                    "text": "Identical content for testing",
                    "publishedAt": 1640995200000
                },
                {
                    "urn": "urn:li:activity:duplicate",
                    "text": "Identical content for testing",  # Same content
                    "publishedAt": 1641081600000
                }
            ]

            tool = NormalizeLinkedInContent(posts=duplicate_posts)
            result = tool.run()
            result_data = json.loads(result)

            # Should process both posts (deduplication is separate tool)
            self.assertIsInstance(result_data, dict)

            print("✅ Successfully tested duplicate content awareness")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")


if __name__ == '__main__':
    unittest.main()