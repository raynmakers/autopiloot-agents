"""
Unit tests for ComputeLinkedInStats tool.
Tests statistical analysis, engagement metrics, and trend detection.
"""

import unittest
import json
from unittest.mock import patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.compute_linkedin_stats import ComputeLinkedInStats


class TestComputeLinkedInStats(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.test_entities = [
            {
                "id": "urn:li:activity:1",
                "type": "post",
                "text": "Business insights post",
                "created_at": "2024-01-15T10:00:00Z",
                "metrics": {"likes": 100, "comments": 20, "shares": 5, "engagement_rate": 0.05},
                "author": {"name": "Alex Hormozi"}
            },
            {
                "id": "urn:li:activity:2",
                "type": "post",
                "text": "Strategy discussion",
                "created_at": "2024-01-14T10:00:00Z",
                "metrics": {"likes": 200, "comments": 30, "shares": 10, "engagement_rate": 0.08},
                "author": {"name": "Alex Hormozi"}
            },
            {
                "id": "urn:li:comment:1",
                "type": "comment",
                "text": "Great point!",
                "created_at": "2024-01-15T11:00:00Z",
                "metrics": {"likes": 15, "replies": 2},
                "parent_post_id": "urn:li:activity:1"
            }
        ]

        self.tool = ComputeLinkedInStats(
            entities=self.test_entities,
            include_trends=True,
            include_histograms=True
        )

    def test_successful_stats_computation(self):
        """Test successful statistical analysis."""
        result = self.tool.run()
        result_data = json.loads(result)

        # Check overall structure
        self.assertEqual(result_data["status"], "success")
        self.assertIn("engagement_stats", result_data)
        self.assertIn("content_stats", result_data)
        self.assertIn("time_series_stats", result_data)

        # Check engagement statistics
        engagement = result_data["engagement_stats"]
        self.assertIn("average_likes", engagement)
        self.assertIn("total_engagement", engagement)
        self.assertIn("engagement_rate_avg", engagement)

        # Check content statistics
        content = result_data["content_stats"]
        self.assertEqual(content["total_posts"], 2)
        self.assertEqual(content["total_comments"], 1)
        self.assertIn("text_length_avg", content)

    def test_trend_analysis(self):
        """Test trend analysis functionality."""
        result = self.tool.run()
        result_data = json.loads(result)

        # Should include trend analysis when enabled
        self.assertIn("trend_analysis", result_data)
        trends = result_data["trend_analysis"]
        self.assertIn("engagement_trend", trends)
        self.assertIn("posting_frequency", trends)

    def test_histogram_generation(self):
        """Test histogram generation."""
        result = self.tool.run()
        result_data = json.loads(result)

        # Should include histograms when enabled
        self.assertIn("histograms", result_data)
        histograms = result_data["histograms"]
        self.assertIn("likes_distribution", histograms)
        self.assertIn("engagement_rate_distribution", histograms)

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            ComputeLinkedInStats()  # Missing required entities

        # Test default values
        tool = ComputeLinkedInStats(entities=self.test_entities)
        self.assertTrue(tool.include_trends)
        self.assertTrue(tool.include_histograms)


if __name__ == '__main__':
    unittest.main()