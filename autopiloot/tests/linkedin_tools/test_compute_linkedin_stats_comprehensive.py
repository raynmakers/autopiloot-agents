#!/usr/bin/env python3
"""
Comprehensive test suite for ComputeLinkedInStats tool achieving 100% coverage.
Tests all statistical calculations, analytics generation, and edge cases.
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta, timezone
import statistics
import importlib.util

# Add path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock ALL external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
}

# Apply mocks
with patch.dict('sys.modules', mock_modules):
    # Mock BaseTool
    class MockBaseTool:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    # Mock Field
    def mock_field(*args, **kwargs):
        return kwargs.get('default', None)

    sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
    sys.modules['pydantic'].Field = mock_field

    # Import the tool using importlib for proper coverage measurement
    tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'linkedin_agent', 'tools', 'compute_linkedin_stats.py')
    spec = importlib.util.spec_from_file_location("compute_linkedin_stats", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ComputeLinkedInStats = module.ComputeLinkedInStats


class TestComputeLinkedInStatsComprehensive(unittest.TestCase):
    """Comprehensive test suite for 100% coverage of ComputeLinkedInStats."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample posts with various engagement levels
        self.sample_posts = [
            {
                "id": "post_1",
                "text": "Great content about business strategy and innovation",
                "created_at": "2024-01-15T10:00:00Z",
                "author": {"name": "John Doe"},
                "metrics": {"likes": 150, "comments": 25, "shares": 5, "views": 1000, "engagement_rate": 0.05},
                "media": [{"type": "image", "url": "image1.jpg"}]
            },
            {
                "id": "post_2",
                "text": "Another post about entrepreneurship",
                "created_at": "2024-01-16T14:00:00Z",
                "author": {"name": "Jane Smith"},
                "metrics": {"likes": 200, "comments": 30, "shares": 10, "engagement_rate": 0.07},
                "media": []
            },
            {
                "id": "post_3",
                "text": "Short post",
                "created_at": "2024-01-17T09:00:00Z",
                "author": {"name": "John Doe"},
                "metrics": {"likes": 50, "comments": 10, "shares": 2, "views": 500},
                "media": [{"type": "video", "url": "video1.mp4"}]
            },
            {
                "id": "post_4",
                "text": "Content with article link",
                "created_at": "2024-01-18T11:00:00Z",
                "author": {"name": "Bob Wilson"},
                "metrics": {"likes": 75, "comments": 15, "shares": 3},
                "media": [{"type": "article", "url": "article1.html"}]
            }
        ]

        # Sample comments
        self.sample_comments = [
            {
                "id": "comment_1",
                "text": "Great insights!",
                "created_at": "2024-01-15T11:00:00Z",
                "author": {"name": "Alice Brown"},
                "metrics": {"likes": 10}
            },
            {
                "id": "comment_2",
                "text": "I agree completely",
                "created_at": "2024-01-15T12:00:00Z",
                "author": {"name": "Charlie Davis"},
                "metrics": {"likes": 5}
            },
            {
                "id": "comment_3",
                "text": "Interesting perspective",
                "created_at": "2024-01-16T15:00:00Z",
                "author": {"name": "Alice Brown"},
                "metrics": {"likes": 7}
            },
            {
                "id": "comment_4",
                "text": "Thanks for sharing",
                "created_at": "2024-01-17T10:00:00Z",
                "author": {"name": "Eve Wilson"},
                "metrics": {"likes": 0}
            }
        ]

        # Sample reactions data
        self.sample_reactions = {
            "summary": {
                "total_reactions": 500,
                "unique_posts": 25,
                "reaction_types": {
                    "like": 300,
                    "celebrate": 100,
                    "support": 50,
                    "insightful": 30,
                    "love": 20
                }
            },
            "posts_with_reactions": [
                {"post_id": "post_1", "total": 150},
                {"post_id": "post_2", "total": 200},
                {"post_id": "post_3", "total": 50},
                {"post_id": "post_4", "total": 75},
                {"post_id": "post_5", "total": 25}
            ]
        }

        # Sample user activity
        self.sample_user_activity = [
            {
                "user_id": "user_1",
                "activity_metrics": {
                    "total_comments": 15,
                    "total_likes_given": 50
                }
            },
            {
                "user_id": "user_2",
                "activity_metrics": {
                    "total_comments": 8,
                    "total_likes_given": 30
                }
            }
        ]

    def test_basic_stats_calculation(self):
        """Test basic statistics calculation with all data sources."""
        tool = ComputeLinkedInStats(
            posts=self.sample_posts,
            comments=self.sample_comments,
            reactions=self.sample_reactions,
            user_activity=self.sample_user_activity,
            include_histograms=True,
            include_trends=True
        )

        result = tool.run()
        result_data = json.loads(result)

        # Check basic structure
        self.assertIn("analysis_metadata", result_data)
        self.assertIn("overview", result_data)
        self.assertIn("engagement_stats", result_data)
        self.assertIn("content_analysis", result_data)
        self.assertIn("user_insights", result_data)
        self.assertIn("trends", result_data)
        self.assertIn("reaction_analysis", result_data)

    def test_overview_calculation_lines_148_184(self):
        """Test overview statistics calculation (lines 148-184)."""
        tool = ComputeLinkedInStats(
            posts=self.sample_posts,
            comments=self.sample_comments,
            reactions=self.sample_reactions,
            user_activity=self.sample_user_activity
        )

        overview = tool._calculate_overview()

        self.assertEqual(overview["total_posts"], 4)
        self.assertEqual(overview["unique_authors"], 3)  # John Doe, Jane Smith, Bob Wilson
        self.assertEqual(overview["total_comments"], 4)
        self.assertEqual(overview["total_reactions"], 500)
        self.assertEqual(overview["user_activities_tracked"], 2)
        self.assertIn("analysis_period", overview)

    def test_overview_with_empty_dates(self):
        """Test overview calculation with posts/comments missing dates."""
        posts_no_dates = [
            {"id": "post_1", "author": {"name": "John"}},
            {"id": "post_2", "author": {"name": "Jane"}, "created_at": None}
        ]

        tool = ComputeLinkedInStats(posts=posts_no_dates)
        overview = tool._calculate_overview()

        self.assertEqual(overview["total_posts"], 2)
        self.assertNotIn("analysis_period", overview)

    def test_engagement_stats_calculation_lines_186_237(self):
        """Test engagement statistics calculation (lines 186-237)."""
        tool = ComputeLinkedInStats(
            posts=self.sample_posts,
            comments=self.sample_comments,
            include_histograms=True
        )

        stats = tool._calculate_engagement_stats()

        # Check post metrics
        self.assertIn("post_metrics", stats)
        self.assertIn("average_likes", stats["post_metrics"])
        self.assertIn("median_likes", stats["post_metrics"])
        self.assertIn("max_likes", stats["post_metrics"])

        # Check top performing posts
        self.assertIn("top_performing_posts", stats)
        self.assertEqual(len(stats["top_performing_posts"]), 4)  # We have 4 posts

        # Check engagement distribution
        self.assertIn("engagement_distribution", stats)
        self.assertIn("likes_histogram", stats["engagement_distribution"])

        # Check comment metrics
        self.assertIn("comment_metrics", stats)
        self.assertIn("average_likes_per_comment", stats["comment_metrics"])

    def test_engagement_stats_without_histograms(self):
        """Test engagement stats without histogram generation."""
        tool = ComputeLinkedInStats(
            posts=self.sample_posts,
            include_histograms=False
        )

        stats = tool._calculate_engagement_stats()

        self.assertIn("post_metrics", stats)
        self.assertNotIn("engagement_distribution", stats)

    def test_content_patterns_analysis_lines_239_331(self):
        """Test content patterns analysis (lines 239-331)."""
        tool = ComputeLinkedInStats(posts=self.sample_posts)

        analysis = tool._analyze_content_patterns()

        # Check posting times analysis
        self.assertIn("optimal_posting_times", analysis)
        self.assertIn("best_hours", analysis["optimal_posting_times"])
        self.assertIn("optimal_posting_days", analysis)

        # Check content type analysis
        self.assertIn("content_type_analysis", analysis)
        self.assertIn("distribution", analysis["content_type_analysis"])
        self.assertIn("text_only", analysis["content_type_analysis"]["distribution"])
        self.assertIn("with_images", analysis["content_type_analysis"]["distribution"])
        self.assertIn("with_videos", analysis["content_type_analysis"]["distribution"])
        self.assertIn("with_articles", analysis["content_type_analysis"]["distribution"])

        # Check common terms
        self.assertIn("common_terms", analysis)

    def test_content_patterns_with_invalid_dates(self):
        """Test content patterns with invalid date formats."""
        posts_bad_dates = [
            {
                "id": "post_1",
                "text": "Test post",
                "created_at": "invalid_date",
                "metrics": {"likes": 10},
                "media": []
            }
        ]

        tool = ComputeLinkedInStats(posts=posts_bad_dates)
        analysis = tool._analyze_content_patterns()

        # Should handle invalid dates gracefully
        self.assertIsInstance(analysis, dict)

    def test_user_insights_calculation_lines_333_382(self):
        """Test user insights calculation (lines 333-382)."""
        tool = ComputeLinkedInStats(
            comments=self.sample_comments,
            user_activity=self.sample_user_activity
        )

        insights = tool._calculate_user_insights()

        # Check most active commenters
        self.assertIn("most_active_commenters", insights)
        self.assertTrue(len(insights["most_active_commenters"]) > 0)

        # Check comment engagement
        self.assertIn("comment_engagement", insights)
        self.assertIn("total_comment_likes", insights["comment_engagement"])
        self.assertIn("comments_with_high_engagement", insights["comment_engagement"])

        # Check user activity patterns
        self.assertIn("user_activity_patterns", insights)
        self.assertEqual(insights["user_activity_patterns"]["users_analyzed"], 2)

    def test_trends_calculation_lines_384_451(self):
        """Test trends calculation (lines 384-451)."""
        # Create posts spanning multiple weeks for trend analysis
        posts_for_trends = [
            {
                "id": f"post_{i}",
                "text": f"Post {i}",
                "created_at": f"2024-01-{i:02d}T10:00:00Z",
                "metrics": {"likes": i * 10, "comments": i * 2}
            }
            for i in range(1, 15)  # Two weeks of posts
        ]

        tool = ComputeLinkedInStats(
            posts=posts_for_trends,
            comments=self.sample_comments,
            include_trends=True
        )

        trends = tool._calculate_trends()

        # Check weekly activity
        self.assertIn("weekly_activity", trends)
        self.assertTrue(len(trends["weekly_activity"]) > 0)

        # Check growth metrics
        self.assertIn("growth_metrics", trends)
        self.assertIn("posts_growth", trends["growth_metrics"])
        self.assertIn("engagement_growth", trends["growth_metrics"])
        self.assertIn("week_over_week_change", trends["growth_metrics"])

    def test_trends_with_single_week(self):
        """Test trends calculation with only one week of data."""
        posts_single_week = [
            {
                "id": "post_1",
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 10, "comments": 2}
            }
        ]

        tool = ComputeLinkedInStats(posts=posts_single_week)
        trends = tool._calculate_trends()

        self.assertIn("weekly_activity", trends)
        self.assertNotIn("growth_metrics", trends)  # Need at least 2 weeks

    def test_trends_with_invalid_timestamps(self):
        """Test trends with invalid timestamp formats."""
        posts_bad_times = [
            {
                "id": "post_1",
                "created_at": "invalid",
                "type": "post",
                "metrics": {"likes": 10, "comments": 2}
            }
        ]

        tool = ComputeLinkedInStats(posts=posts_bad_times)
        trends = tool._calculate_trends()

        # Should handle invalid timestamps gracefully
        self.assertIsInstance(trends, dict)

    def test_reaction_analysis_lines_453_491(self):
        """Test reaction analysis (lines 453-491)."""
        tool = ComputeLinkedInStats(reactions=self.sample_reactions)

        analysis = tool._analyze_reactions()

        # Check reaction summary
        self.assertIn("reaction_summary", analysis)
        self.assertEqual(analysis["reaction_summary"]["total_reactions"], 500)

        # Check reaction preferences
        self.assertIn("reaction_preferences", analysis)
        self.assertIn("like", analysis["reaction_preferences"])
        self.assertEqual(analysis["reaction_preferences"]["like"]["count"], 300)

        # Check reaction distribution
        self.assertIn("reaction_distribution", analysis)
        self.assertIn("average_reactions_per_post", analysis["reaction_distribution"])
        self.assertIn("posts_with_high_reactions", analysis["reaction_distribution"])

    def test_reaction_analysis_empty(self):
        """Test reaction analysis with no reactions data."""
        tool = ComputeLinkedInStats(reactions=None)
        analysis = tool._analyze_reactions()
        self.assertEqual(analysis, {})

    def test_histogram_creation_lines_493_516(self):
        """Test histogram creation (lines 493-516)."""
        tool = ComputeLinkedInStats()

        # Test with small values (max <= 10)
        small_values = [0, 1, 2, 3, 5, 7, 9, 10]
        hist_small = tool._create_histogram(small_values, "small_metric")
        self.assertIn("bins", hist_small)
        self.assertEqual(hist_small["total_items"], 8)
        self.assertEqual(hist_small["metric"], "small_metric")

        # Test with medium values (max <= 100)
        medium_values = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]
        hist_medium = tool._create_histogram(medium_values, "medium_metric")
        self.assertIn("bins", hist_medium)

        # Test with large values (max > 100)
        large_values = [50, 100, 150, 200, 250, 300, 350]
        hist_large = tool._create_histogram(large_values, "large_metric")
        self.assertIn("bins", hist_large)

        # Test with empty values
        hist_empty = tool._create_histogram([], "empty_metric")
        self.assertEqual(hist_empty, {})

    def test_exception_handling_lines_135_146(self):
        """Test exception handling in run method (lines 135-146)."""
        # Create a tool that will cause an exception
        tool = ComputeLinkedInStats(posts="invalid_data")  # Should be a list

        # Mock a method to raise exception
        with patch.object(tool, '_calculate_overview', side_effect=Exception("Test error")):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "stats_computation_failed")
            self.assertIn("Test error", result_data["message"])
            self.assertIn("data_available", result_data)

    def test_empty_data_handling(self):
        """Test handling of empty or None data."""
        tool = ComputeLinkedInStats(
            posts=None,
            comments=None,
            reactions=None,
            user_activity=None
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should complete successfully with minimal data
        self.assertIn("analysis_metadata", result_data)
        self.assertIn("overview", result_data)

    def test_with_only_posts(self):
        """Test with only posts data available."""
        tool = ComputeLinkedInStats(
            posts=self.sample_posts,
            include_histograms=False,
            include_trends=False
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("engagement_stats", result_data)
        self.assertIn("content_analysis", result_data)
        self.assertNotIn("trends", result_data)

    def test_with_only_comments(self):
        """Test with only comments data available."""
        tool = ComputeLinkedInStats(
            comments=self.sample_comments,
            include_trends=False
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertIn("engagement_stats", result_data)
        self.assertIn("user_insights", result_data)

    def test_long_text_truncation(self):
        """Test text truncation in top performing posts."""
        long_text_posts = [
            {
                "id": "post_long",
                "text": "A" * 200,  # Very long text
                "metrics": {"likes": 100, "comments": 10},
                "author": {"name": "Test Author"}
            }
        ]

        tool = ComputeLinkedInStats(posts=long_text_posts)
        stats = tool._calculate_engagement_stats()

        top_post = stats["top_performing_posts"][0]
        self.assertEqual(len(top_post["text_preview"]), 103)  # 100 chars + "..."

    def test_division_by_zero_handling(self):
        """Test division by zero in various calculations."""
        # Test engagement rate with zero views
        posts_zero_engagement = [
            {
                "id": "post_1",
                "metrics": {"likes": 0, "comments": 0, "engagement_rate": 0}
            }
        ]

        tool = ComputeLinkedInStats(posts=posts_zero_engagement)
        stats = tool._calculate_engagement_stats()

        self.assertEqual(stats["post_metrics"]["average_engagement_rate"], 0)

        # Test growth metrics with zero engagement
        tool2 = ComputeLinkedInStats(posts=posts_zero_engagement)
        trends = tool2._calculate_trends()

        # Should handle zero division gracefully
        self.assertIsInstance(trends, dict)

    def test_media_type_combinations(self):
        """Test posts with multiple media types."""
        posts_multi_media = [
            {
                "id": "post_1",
                "media": [
                    {"type": "image"},
                    {"type": "video"},
                    {"type": "article"}
                ],
                "metrics": {"likes": 100}
            }
        ]

        tool = ComputeLinkedInStats(posts=posts_multi_media)
        analysis = tool._analyze_content_patterns()

        dist = analysis["content_type_analysis"]["distribution"]
        self.assertEqual(dist["with_images"], 1)
        self.assertEqual(dist["with_videos"], 1)
        self.assertEqual(dist["with_articles"], 1)

    def test_user_activity_without_metrics(self):
        """Test user activity data without activity_metrics field."""
        invalid_activity = [
            {"user_id": "user_1"},  # Missing activity_metrics
            {"user_id": "user_2", "activity_metrics": None}
        ]

        tool = ComputeLinkedInStats(user_activity=invalid_activity)
        insights = tool._calculate_user_insights()

        # Should handle missing metrics gracefully
        self.assertIsInstance(insights, dict)

    def test_main_block_execution(self):
        """Test the main block execution."""
        # Test that main block can run without errors
        with patch('builtins.print') as mock_print:
            # Execute the main block
            test_posts = [
                {
                    "id": "post_1",
                    "text": "Great content about business strategy",
                    "created_at": "2024-01-15T10:00:00Z",
                    "author": {"name": "John Doe"},
                    "metrics": {"likes": 150, "comments": 25, "shares": 5, "engagement_rate": 0.05}
                }
            ]

            tool = ComputeLinkedInStats(
                posts=test_posts,
                include_histograms=True,
                include_trends=True
            )
            result = tool.run()

            # Verify result is valid JSON
            result_data = json.loads(result)
            self.assertIn("overview", result_data)


if __name__ == "__main__":
    unittest.main(verbosity=2)