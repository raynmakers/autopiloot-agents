"""
Unit tests for GetPostComments tool.
Tests batch comment fetching, nested replies, and data processing.
"""

import unittest
import json
from unittest.mock import patch, Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.get_post_comments import GetPostComments


class TestGetPostComments(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.tool = GetPostComments(
            post_ids=["urn:li:activity:12345", "urn:li:activity:12346"],
            max_comments_per_post=10
        )

        # Mock RapidAPI response for comments
        self.mock_response_data = {
            "data": {
                "urn:li:activity:12345": [
                    {
                        "id": "urn:li:comment:11111",
                        "text": "Great insights!",
                        "author": {
                            "name": "John Doe",
                            "headline": "Business Consultant",
                            "profile_url": "https://linkedin.com/in/johndoe"
                        },
                        "created_at": "2024-01-15T11:00:00Z",
                        "metrics": {
                            "likes": 5,
                            "replies": 2,
                            "is_reply": False
                        },
                        "parent_post_id": "urn:li:activity:12345"
                    },
                    {
                        "id": "urn:li:comment:11112",
                        "text": "Thanks for sharing this",
                        "author": {
                            "name": "Jane Smith",
                            "headline": "Marketing Manager",
                            "profile_url": "https://linkedin.com/in/janesmith"
                        },
                        "created_at": "2024-01-15T12:00:00Z",
                        "metrics": {
                            "likes": 3,
                            "replies": 0,
                            "is_reply": False
                        },
                        "parent_post_id": "urn:li:activity:12345"
                    }
                ],
                "urn:li:activity:12346": [
                    {
                        "id": "urn:li:comment:11113",
                        "text": "Excellent point about strategy",
                        "author": {
                            "name": "Mike Johnson",
                            "headline": "Strategy Consultant",
                            "profile_url": "https://linkedin.com/in/mikejohnson"
                        },
                        "created_at": "2024-01-14T10:00:00Z",
                        "metrics": {
                            "likes": 8,
                            "replies": 1,
                            "is_reply": False
                        },
                        "parent_post_id": "urn:li:activity:12346"
                    }
                ]
            },
            "summary": {
                "total_comments": 3,
                "posts_processed": 2,
                "comments_per_post": {
                    "urn:li:activity:12345": 2,
                    "urn:li:activity:12346": 1
                }
            }
        }

    @patch('linkedin_agent.tools.get_post_comments.requests.post')
    @patch('linkedin_agent.tools.get_post_comments.load_environment')
    @patch('linkedin_agent.tools.get_post_comments.get_required_env_var')
    def test_successful_comments_fetch(self, mock_env_var, mock_load_env, mock_requests):
        """Test successful batch comments fetching."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_response_data
        mock_requests.return_value = mock_response

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(result_data["summary"]["total_comments"], 3)
        self.assertEqual(result_data["summary"]["posts_processed"], 2)

        # Verify comments structure
        comments = result_data["comments"]
        self.assertEqual(len(comments), 3)

        # Check first comment
        first_comment = comments[0]
        self.assertEqual(first_comment["id"], "urn:li:comment:11111")
        self.assertEqual(first_comment["text"], "Great insights!")
        self.assertEqual(first_comment["author"]["name"], "John Doe")
        self.assertEqual(first_comment["metrics"]["likes"], 5)
        self.assertEqual(first_comment["parent_post_id"], "urn:li:activity:12345")

        # Verify API call structure
        mock_requests.assert_called_once()
        call_args = mock_requests.call_args
        self.assertIn("linkedin-api8.p.rapidapi.com", call_args[1]["headers"]["X-RapidAPI-Host"])
        self.assertEqual(call_args[1]["headers"]["X-RapidAPI-Key"], "test-api-key")

        # Check request payload
        payload = json.loads(call_args[1]["data"])
        self.assertEqual(len(payload["post_ids"]), 2)
        self.assertIn("urn:li:activity:12345", payload["post_ids"])
        self.assertIn("urn:li:activity:12346", payload["post_ids"])

    @patch('linkedin_agent.tools.get_post_comments.requests.post')
    @patch('linkedin_agent.tools.get_post_comments.load_environment')
    @patch('linkedin_agent.tools.get_post_comments.get_required_env_var')
    def test_api_error_handling(self, mock_env_var, mock_load_env, mock_requests):
        """Test handling of API errors."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_requests.return_value = mock_response

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["error"], "api_error")
        self.assertIn("500", result_data["message"])
        self.assertEqual(len(result_data["post_ids"]), 2)

    @patch('linkedin_agent.tools.get_post_comments.requests.post')
    @patch('linkedin_agent.tools.get_post_comments.load_environment')
    @patch('linkedin_agent.tools.get_post_comments.get_required_env_var')
    def test_empty_comments_response(self, mock_env_var, mock_load_env, mock_requests):
        """Test handling of posts with no comments."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock empty comments response
        empty_response = {
            "data": {
                "urn:li:activity:12345": [],
                "urn:li:activity:12346": []
            },
            "summary": {
                "total_comments": 0,
                "posts_processed": 2,
                "comments_per_post": {
                    "urn:li:activity:12345": 0,
                    "urn:li:activity:12346": 0
                }
            }
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = empty_response
        mock_requests.return_value = mock_response

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(result_data["summary"]["total_comments"], 0)
        self.assertEqual(len(result_data["comments"]), 0)
        self.assertEqual(result_data["summary"]["posts_processed"], 2)

    @patch('linkedin_agent.tools.get_post_comments.requests.post')
    @patch('linkedin_agent.tools.get_post_comments.load_environment')
    @patch('linkedin_agent.tools.get_post_comments.get_required_env_var')
    def test_batch_size_limits(self, mock_env_var, mock_load_env, mock_requests):
        """Test batch size limitations."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_response_data
        mock_requests.return_value = mock_response

        # Test with large batch (should be chunked)
        large_post_list = [f"urn:li:activity:1234{i}" for i in range(15)]
        tool = GetPostComments(
            post_ids=large_post_list,
            max_comments_per_post=5
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should process successfully (might be chunked internally)
        self.assertEqual(result_data["status"], "success")

        # Verify API was called (potentially multiple times for batching)
        self.assertGreaterEqual(mock_requests.call_count, 1)

    @patch('linkedin_agent.tools.get_post_comments.requests.post')
    @patch('linkedin_agent.tools.get_post_comments.load_environment')
    @patch('linkedin_agent.tools.get_post_comments.get_required_env_var')
    def test_nested_replies_handling(self, mock_env_var, mock_load_env, mock_requests):
        """Test handling of nested comment replies."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock response with nested replies
        nested_response = {
            "data": {
                "urn:li:activity:12345": [
                    {
                        "id": "urn:li:comment:11111",
                        "text": "Original comment",
                        "author": {"name": "John Doe", "headline": "Business Consultant"},
                        "created_at": "2024-01-15T11:00:00Z",
                        "metrics": {"likes": 5, "replies": 1, "is_reply": False},
                        "parent_post_id": "urn:li:activity:12345"
                    },
                    {
                        "id": "urn:li:comment:11112",
                        "text": "Reply to comment",
                        "author": {"name": "Jane Smith", "headline": "Marketing Manager"},
                        "created_at": "2024-01-15T11:30:00Z",
                        "metrics": {"likes": 2, "replies": 0, "is_reply": True},
                        "parent_post_id": "urn:li:activity:12345",
                        "parent_comment_id": "urn:li:comment:11111"
                    }
                ]
            },
            "summary": {
                "total_comments": 2,
                "posts_processed": 1,
                "comments_per_post": {"urn:li:activity:12345": 2}
            }
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = nested_response
        mock_requests.return_value = mock_response

        # Run the tool with include_replies enabled
        tool = GetPostComments(
            post_ids=["urn:li:activity:12345"],
            include_replies=True
        )

        result = tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(len(result_data["comments"]), 2)

        # Find the reply comment
        reply_comment = next((c for c in result_data["comments"] if c["metrics"]["is_reply"]), None)
        self.assertIsNotNone(reply_comment)
        self.assertEqual(reply_comment["text"], "Reply to comment")
        self.assertEqual(reply_comment["parent_comment_id"], "urn:li:comment:11111")

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            GetPostComments()  # Missing required post_ids

        # Test empty post_ids list
        with self.assertRaises(Exception):
            GetPostComments(post_ids=[])

        # Test default values
        tool = GetPostComments(post_ids=["urn:li:activity:12345"])
        self.assertEqual(tool.max_comments_per_post, 20)
        self.assertTrue(tool.include_replies)

        # Test field types and constraints
        tool = GetPostComments(
            post_ids=["urn:li:activity:12345", "urn:li:activity:12346"],
            max_comments_per_post=5,
            include_replies=False
        )
        self.assertEqual(len(tool.post_ids), 2)
        self.assertEqual(tool.max_comments_per_post, 5)
        self.assertFalse(tool.include_replies)


if __name__ == '__main__':
    unittest.main()