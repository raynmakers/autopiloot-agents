"""
Unit tests for GetUserCommentActivity tool.
Tests user engagement tracking and networking behavior analysis.
"""

import unittest
import json
from unittest.mock import patch, Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.get_user_comment_activity import GetUserCommentActivity


class TestGetUserCommentActivity(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.tool = GetUserCommentActivity(
            user_urn="alexhormozi",
            max_activities=50,
            include_post_context=True
        )

    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    def test_successful_activity_fetch(self, mock_env_var, mock_load_env, mock_requests):
        """Test successful user comment activity fetching."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock successful API response
        mock_response_data = {
            "activities": [
                {
                    "comment_id": "urn:li:comment:11111",
                    "text": "Great insights on business strategy",
                    "created_at": "2024-01-15T10:00:00Z",
                    "post_context": {
                        "post_id": "urn:li:activity:12345",
                        "post_author": "John Doe",
                        "post_text": "Building successful companies..."
                    },
                    "metrics": {"likes": 25, "replies": 3}
                }
            ],
            "summary": {
                "total_activities": 1,
                "unique_posts_commented": 1,
                "average_engagement": 28.0
            }
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_requests.return_value = mock_response

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(result_data["summary"]["total_activities"], 1)

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            GetUserCommentActivity()  # Missing required user_urn

        # Test default values
        tool = GetUserCommentActivity(user_urn="testuser")
        self.assertEqual(tool.max_activities, 100)
        self.assertTrue(tool.include_post_context)


if __name__ == '__main__':
    unittest.main()