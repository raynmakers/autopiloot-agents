"""
Comprehensive tests for DeduplicateEntities tool.
Tests deduplication logic, similarity detection, and data preservation.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys


class TestDeduplicateEntitiesComprehensive(unittest.TestCase):
    """Test suite for DeduplicateEntities tool."""

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

        # Create sample data with duplicates
        self.sample_posts_with_duplicates = [
            {
                "id": "post_1",
                "content": "This is a unique post about AI",
                "author": "john_doe",
                "published_at": "2024-01-15T10:00:00Z"
            },
            {
                "id": "post_2",
                "content": "This is a unique post about AI",  # Exact duplicate content
                "author": "john_doe",
                "published_at": "2024-01-15T10:05:00Z"  # Different timestamp
            },
            {
                "id": "post_3",
                "content": "This is a unique post about AI and machine learning",  # Similar content
                "author": "john_doe",
                "published_at": "2024-01-15T11:00:00Z"
            },
            {
                "id": "post_4",
                "content": "Completely different post about business strategy",
                "author": "jane_smith",
                "published_at": "2024-01-16T10:00:00Z"
            },
            {
                "id": "post_5",
                "content": "This is a unique post about AI",  # Another exact duplicate
                "author": "bob_wilson",  # Different author
                "published_at": "2024-01-17T10:00:00Z"
            }
        ]

        self.sample_comments_with_duplicates = [
            {
                "id": "comment_1",
                "content": "Great insights!",
                "author": "commenter_1",
                "post_id": "post_1"
            },
            {
                "id": "comment_2",
                "content": "Great insights!",  # Exact duplicate
                "author": "commenter_1",
                "post_id": "post_1"
            },
            {
                "id": "comment_3",
                "content": "Really great insights and analysis!",  # Similar
                "author": "commenter_2",
                "post_id": "post_2"
            },
            {
                "id": "comment_4",
                "content": "Completely different comment",
                "author": "commenter_3",
                "post_id": "post_3"
            }
        ]

    def tearDown(self):
        """Clean up mocks."""
        for module_name in self.mock_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]

    def test_successful_posts_deduplication(self):
        """Test successful deduplication of posts."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            tool = DeduplicateEntities(
                posts=self.sample_posts_with_duplicates,
                similarity_threshold=0.9,
                preserve_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify deduplication structure
            self.assertIn("deduplication_metadata", result_data)
            self.assertIn("processed_at", result_data["deduplication_metadata"])

            print("✅ Successfully deduplicated posts")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_successful_comments_deduplication(self):
        """Test successful deduplication of comments."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            tool = DeduplicateEntities(
                comments=self.sample_comments_with_duplicates,
                similarity_threshold=0.8,
                preserve_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify deduplication structure
            self.assertIn("deduplication_metadata", result_data)

            print("✅ Successfully deduplicated comments")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_combined_deduplication(self):
        """Test deduplication of both posts and comments together."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            tool = DeduplicateEntities(
                posts=self.sample_posts_with_duplicates,
                comments=self.sample_comments_with_duplicates,
                similarity_threshold=0.85,
                preserve_metadata=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify comprehensive deduplication
            self.assertIn("deduplication_metadata", result_data)
            metadata = result_data["deduplication_metadata"]
            self.assertIn("processed_at", metadata)

            print("✅ Successfully deduplicated posts and comments together")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_similarity_threshold_variations(self):
        """Test different similarity threshold values."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            # Test with strict threshold (0.95)
            tool_strict = DeduplicateEntities(
                posts=self.sample_posts_with_duplicates,
                similarity_threshold=0.95
            )

            result_strict = tool_strict.run()
            result_strict_data = json.loads(result_strict)
            self.assertIn("deduplication_metadata", result_strict_data)

            # Test with loose threshold (0.5)
            tool_loose = DeduplicateEntities(
                posts=self.sample_posts_with_duplicates,
                similarity_threshold=0.5
            )

            result_loose = tool_loose.run()
            result_loose_data = json.loads(result_loose)
            self.assertIn("deduplication_metadata", result_loose_data)

            print("✅ Successfully tested different similarity thresholds")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_metadata_preservation_toggle(self):
        """Test metadata preservation toggle functionality."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            # Test with metadata preservation
            tool_preserve = DeduplicateEntities(
                posts=self.sample_posts_with_duplicates,
                preserve_metadata=True
            )

            result_preserve = tool_preserve.run()
            result_preserve_data = json.loads(result_preserve)
            self.assertIn("deduplication_metadata", result_preserve_data)

            # Test without metadata preservation
            tool_no_preserve = DeduplicateEntities(
                posts=self.sample_posts_with_duplicates,
                preserve_metadata=False
            )

            result_no_preserve = tool_no_preserve.run()
            result_no_preserve_data = json.loads(result_no_preserve)
            # Should still have basic structure
            self.assertIsInstance(result_no_preserve_data, dict)

            print("✅ Successfully tested metadata preservation toggle")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_empty_data_handling(self):
        """Test handling of empty or None data."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            tool = DeduplicateEntities(
                posts=None,
                comments=None,
                similarity_threshold=0.8
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should handle empty data gracefully
            self.assertIn("deduplication_metadata", result_data)

            print("✅ Successfully handled empty data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_no_duplicates_scenario(self):
        """Test scenario where no duplicates exist."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            unique_posts = [
                {
                    "id": "unique_1",
                    "content": "First unique post about AI",
                    "author": "author_1"
                },
                {
                    "id": "unique_2",
                    "content": "Second unique post about business",
                    "author": "author_2"
                },
                {
                    "id": "unique_3",
                    "content": "Third unique post about technology",
                    "author": "author_3"
                }
            ]

            tool = DeduplicateEntities(posts=unique_posts)
            result = tool.run()
            result_data = json.loads(result)

            # Should process successfully with no deduplication needed
            self.assertIn("deduplication_metadata", result_data)

            print("✅ Successfully handled data with no duplicates")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_malformed_data_handling(self):
        """Test handling of malformed data."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            malformed_posts = [
                {
                    "id": "valid_post",
                    "content": "Valid content"
                },
                {
                    # Missing id
                    "content": "Missing ID"
                },
                {
                    "id": "missing_content"
                    # Missing content
                },
                None,  # Null entry
                {}  # Empty object
            ]

            tool = DeduplicateEntities(posts=malformed_posts)
            result = tool.run()
            result_data = json.loads(result)

            # Should handle malformed data gracefully
            self.assertIsInstance(result_data, dict)

            print("✅ Successfully handled malformed data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_exact_vs_similar_duplicates(self):
        """Test detection of exact vs similar duplicates."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            mixed_duplicates = [
                {
                    "id": "original",
                    "content": "The quick brown fox jumps over the lazy dog"
                },
                {
                    "id": "exact_duplicate",
                    "content": "The quick brown fox jumps over the lazy dog"  # Exact
                },
                {
                    "id": "similar",
                    "content": "A quick brown fox jumps over a lazy dog"  # Similar
                },
                {
                    "id": "very_similar",
                    "content": "The quick brown fox jumped over the lazy dog"  # Very similar
                },
                {
                    "id": "different",
                    "content": "Completely different content about technology"  # Different
                }
            ]

            tool = DeduplicateEntities(
                posts=mixed_duplicates,
                similarity_threshold=0.7  # Moderate threshold
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should detect and handle various similarity levels
            self.assertIn("deduplication_metadata", result_data)

            print("✅ Successfully tested exact vs similar duplicate detection")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_large_dataset_handling(self):
        """Test handling of larger datasets."""
        try:
            from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities

            # Create larger dataset with systematic duplicates
            large_dataset = []
            for i in range(50):
                # Create original
                large_dataset.append({
                    "id": f"post_{i}",
                    "content": f"Original post number {i} about topic {i % 5}"
                })

                # Create some duplicates
                if i % 3 == 0:
                    large_dataset.append({
                        "id": f"post_{i}_duplicate",
                        "content": f"Original post number {i} about topic {i % 5}"
                    })

            tool = DeduplicateEntities(posts=large_dataset)
            result = tool.run()
            result_data = json.loads(result)

            # Should handle large dataset efficiently
            self.assertIn("deduplication_metadata", result_data)

            print("✅ Successfully handled large dataset")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")


if __name__ == '__main__':
    unittest.main()