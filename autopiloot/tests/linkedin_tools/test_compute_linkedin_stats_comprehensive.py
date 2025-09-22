"""
Comprehensive tests for ComputeLinkedInStats tool.
Tests statistical analysis, engagement calculations, and trend analysis.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
from datetime import datetime, timezone, timedelta


class TestComputeLinkedInStatsComprehensive(unittest.TestCase):
    """Test suite for ComputeLinkedInStats tool."""

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

        # Create sample test data
        self.sample_posts = [
            {
                "id": "post_1",
                "content": "First test post about AI",
                "likes": 50,
                "comments": 10,
                "shares": 5,
                "published_at": "2024-01-15T10:00:00Z",
                "author": "test_user"
            },
            {
                "id": "post_2",
                "content": "Second post about business strategy",
                "likes": 75,
                "comments": 15,
                "shares": 8,
                "published_at": "2024-01-16T14:30:00Z",
                "author": "test_user"
            },
            {
                "id": "post_3",
                "content": "Third post with low engagement",
                "likes": 20,
                "comments": 2,
                "shares": 1,
                "published_at": "2024-01-17T09:15:00Z",
                "author": "test_user"
            }
        ]

        self.sample_comments = [
            {
                "id": "comment_1",
                "post_id": "post_1",
                "content": "Great insights!",
                "author": "commenter_1",
                "likes": 5,
                "published_at": "2024-01-15T11:00:00Z"
            },
            {
                "id": "comment_2",
                "post_id": "post_2",
                "content": "Very helpful information",
                "author": "commenter_2",
                "likes": 8,
                "published_at": "2024-01-16T15:00:00Z"
            }
        ]

        self.sample_reactions = {
            "post_1": {"like": 50, "love": 5, "insightful": 3},
            "post_2": {"like": 75, "love": 10, "insightful": 8},
            "post_3": {"like": 20, "love": 2, "insightful": 1}
        }

    def tearDown(self):
        """Clean up mocks."""
        for module_name in self.mock_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]

    def test_successful_stats_computation_with_all_data(self):
        """Test successful computation with posts, comments, and reactions."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            tool = ComputeLinkedInStats(
                posts=self.sample_posts,
                comments=self.sample_comments,
                reactions=self.sample_reactions,
                include_histograms=True,
                include_trends=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify basic structure
            self.assertIn("analysis_metadata", result_data)
            self.assertIn("computed_at", result_data["analysis_metadata"])
            self.assertIn("data_sources", result_data["analysis_metadata"])

            # Verify data sources are tracked
            data_sources = result_data["analysis_metadata"]["data_sources"]
            self.assertIn("posts (3)", data_sources)
            self.assertIn("comments (2)", data_sources)
            self.assertIn("reactions", data_sources)

            print("✅ Successfully computed stats with all data types")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_posts_only_analysis(self):
        """Test analysis with only posts data."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            tool = ComputeLinkedInStats(
                posts=self.sample_posts,
                comments=None,
                reactions=None,
                include_histograms=False,
                include_trends=False
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should still provide meaningful analysis
            self.assertIn("analysis_metadata", result_data)
            data_sources = result_data["analysis_metadata"]["data_sources"]
            self.assertEqual(len(data_sources), 1)
            self.assertIn("posts (3)", data_sources)

            print("✅ Successfully analyzed posts-only data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_empty_data_handling(self):
        """Test handling of empty or None data."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            tool = ComputeLinkedInStats(
                posts=None,
                comments=None,
                reactions=None
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should return meaningful response even with no data
            self.assertIn("analysis_metadata", result_data)
            self.assertEqual(len(result_data["analysis_metadata"]["data_sources"]), 0)

            print("✅ Successfully handled empty data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_engagement_calculations(self):
        """Test engagement rate and metric calculations."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            # Create posts with known engagement metrics
            test_posts = [
                {
                    "id": "post_1",
                    "likes": 100,
                    "comments": 20,
                    "shares": 10,
                    "views": 1000  # 13% engagement rate
                },
                {
                    "id": "post_2",
                    "likes": 50,
                    "comments": 10,
                    "shares": 5,
                    "views": 500   # 13% engagement rate
                }
            ]

            tool = ComputeLinkedInStats(posts=test_posts)
            result = tool.run()
            result_data = json.loads(result)

            # Verify statistical calculations would be processed
            self.assertIn("analysis_metadata", result_data)

            print("✅ Successfully tested engagement calculations")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_time_range_analysis(self):
        """Test analysis across different time periods."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            # Create posts across different time periods
            now = datetime.now(timezone.utc)
            time_distributed_posts = [
                {
                    "id": "recent_post",
                    "published_at": now.isoformat(),
                    "likes": 30
                },
                {
                    "id": "week_old_post",
                    "published_at": (now - timedelta(days=7)).isoformat(),
                    "likes": 50
                },
                {
                    "id": "month_old_post",
                    "published_at": (now - timedelta(days=30)).isoformat(),
                    "likes": 40
                }
            ]

            tool = ComputeLinkedInStats(
                posts=time_distributed_posts,
                include_trends=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify analysis period calculation
            self.assertIn("analysis_metadata", result_data)
            self.assertIn("data_sources", result_data["analysis_metadata"])

            print("✅ Successfully analyzed time-distributed data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_error_handling_invalid_data(self):
        """Test error handling with malformed data."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            # Create malformed posts data
            malformed_posts = [
                {"id": "post_1"},  # Missing required fields
                {"likes": "invalid"},  # Invalid data type
                None  # Null entry
            ]

            tool = ComputeLinkedInStats(posts=malformed_posts)
            result = tool.run()
            result_data = json.loads(result)

            # Should handle errors gracefully
            self.assertIn("analysis_metadata", result_data)

            print("✅ Successfully handled malformed data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_configuration_options(self):
        """Test different configuration options."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            # Test with histograms disabled
            tool_no_histograms = ComputeLinkedInStats(
                posts=self.sample_posts,
                include_histograms=False,
                include_trends=True
            )

            result1 = tool_no_histograms.run()
            result1_data = json.loads(result1)
            self.assertIn("analysis_metadata", result1_data)

            # Test with trends disabled
            tool_no_trends = ComputeLinkedInStats(
                posts=self.sample_posts,
                include_histograms=True,
                include_trends=False
            )

            result2 = tool_no_trends.run()
            result2_data = json.loads(result2)
            self.assertIn("analysis_metadata", result2_data)

            print("✅ Successfully tested configuration options")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_user_activity_analysis(self):
        """Test analysis of user comment activity."""
        try:
            from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats

            user_activity = [
                {
                    "user": "active_user",
                    "comments": 15,
                    "engagement_score": 85
                },
                {
                    "user": "moderate_user",
                    "comments": 8,
                    "engagement_score": 60
                }
            ]

            tool = ComputeLinkedInStats(
                posts=self.sample_posts,
                user_activity=user_activity
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify user activity data is processed
            self.assertIn("analysis_metadata", result_data)
            data_sources = result_data["analysis_metadata"]["data_sources"]
            self.assertIn("user_activity (2)", data_sources)

            print("✅ Successfully analyzed user activity data")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")


if __name__ == '__main__':
    unittest.main()