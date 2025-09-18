"""
Unit tests for GetUserPosts tool.
Tests RapidAPI integration, pagination, error handling, and data processing.
"""

import unittest
import json
from unittest.mock import patch, Mock, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.get_user_posts import GetUserPosts


class TestGetUserPosts(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.tool = GetUserPosts(
            user_urn="alexhormozi",
            page=1,
            max_items=10
        )

        # Mock RapidAPI response
        self.mock_response_data = {
            "data": [
                {
                    "id": "urn:li:activity:12345",
                    "text": "Business growth insights",
                    "author": {
                        "name": "Alex Hormozi",
                        "headline": "CEO at Acquisition.com",
                        "profile_url": "https://linkedin.com/in/alexhormozi"
                    },
                    "metrics": {
                        "likes": 150,
                        "comments": 25,
                        "shares": 10
                    },
                    "created_at": "2024-01-15T10:00:00Z",
                    "media": []
                },
                {
                    "id": "urn:li:activity:12346",
                    "text": "Another business post",
                    "author": {
                        "name": "Alex Hormozi",
                        "headline": "CEO at Acquisition.com",
                        "profile_url": "https://linkedin.com/in/alexhormozi"
                    },
                    "metrics": {
                        "likes": 200,
                        "comments": 30,
                        "shares": 15
                    },
                    "created_at": "2024-01-14T09:00:00Z",
                    "media": [{"type": "image", "url": "https://example.com/image.jpg"}]
                }
            ],
            "pagination": {
                "current_page": 1,
                "total_pages": 5,
                "has_next": True,
                "total_items": 50
            }
        }

    @patch('linkedin_agent.tools.get_user_posts.requests.get')
    @patch('linkedin_agent.tools.get_user_posts.load_environment')
    @patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
    def test_successful_posts_fetch(self, mock_env_var, mock_load_env, mock_requests):
        """Test successful posts fetching from RapidAPI."""
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
        self.assertEqual(len(result_data["posts"]), 2)
        self.assertEqual(result_data["posts"][0]["id"], "urn:li:activity:12345")
        self.assertEqual(result_data["posts"][0]["author"]["name"], "Alex Hormozi")
        self.assertEqual(result_data["posts"][0]["metrics"]["likes"], 150)
        self.assertEqual(result_data["pagination"]["current_page"], 1)
        self.assertTrue(result_data["pagination"]["has_next"])

        # Verify API call
        mock_requests.assert_called_once()
        call_args = mock_requests.call_args
        self.assertIn("linkedin-api8.p.rapidapi.com", call_args[1]["headers"]["X-RapidAPI-Host"])
        self.assertEqual(call_args[1]["headers"]["X-RapidAPI-Key"], "test-api-key")

    @patch('linkedin_agent.tools.get_user_posts.requests.get')
    @patch('linkedin_agent.tools.get_user_posts.load_environment')
    @patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
    def test_api_error_handling(self, mock_env_var, mock_load_env, mock_requests):
        """Test handling of API errors."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 429  # Rate limit
        mock_response.text = "Rate limit exceeded"
        mock_requests.return_value = mock_response

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["error"], "api_error")
        self.assertIn("429", result_data["message"])
        self.assertEqual(result_data["user_urn"], "alexhormozi")

    @patch('linkedin_agent.tools.get_user_posts.requests.get')
    @patch('linkedin_agent.tools.get_user_posts.load_environment')
    @patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
    def test_pagination_parameters(self, mock_env_var, mock_load_env, mock_requests):
        """Test pagination parameter handling."""
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

        # Test with specific pagination
        tool = GetUserPosts(
            user_urn="testuser",
            page=3,
            max_items=50
        )

        result = tool.run()

        # Verify pagination parameters in API call
        call_args = mock_requests.call_args
        params = call_args[1]["params"]
        self.assertEqual(params["page"], 3)

    @patch('linkedin_agent.tools.get_user_posts.requests.get')
    @patch('linkedin_agent.tools.get_user_posts.load_environment')
    @patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
    def test_date_filtering(self, mock_env_var, mock_load_env, mock_requests):
        """Test date filtering functionality."""
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

        # Test with date filters
        tool = GetUserPosts(
            user_urn="testuser",
            since_date="2024-01-01",
            until_date="2024-01-31"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should successfully fetch with date filters
        self.assertEqual(result_data["status"], "success")

        # Verify date parameters in API call
        call_args = mock_requests.call_args
        params = call_args[1]["params"]
        self.assertEqual(params["since_date"], "2024-01-01")
        self.assertEqual(params["until_date"], "2024-01-31")

    @patch('linkedin_agent.tools.get_user_posts.load_environment')
    @patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
    def test_missing_environment_variables(self, mock_env_var, mock_load_env):
        """Test handling of missing environment variables."""
        # Mock missing environment variable
        mock_env_var.side_effect = Exception("Environment variable not found")

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["error"], "environment_error")
        self.assertIn("Environment variable not found", result_data["message"])

    @patch('linkedin_agent.tools.get_user_posts.requests.get')
    @patch('linkedin_agent.tools.get_user_posts.load_environment')
    @patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
    def test_empty_response_handling(self, mock_env_var, mock_load_env, mock_requests):
        """Test handling of empty API responses."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock empty API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [],
            "pagination": {
                "current_page": 1,
                "total_pages": 0,
                "has_next": False,
                "total_items": 0
            }
        }
        mock_requests.return_value = mock_response

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(len(result_data["posts"]), 0)
        self.assertEqual(result_data["pagination"]["total_items"], 0)
        self.assertFalse(result_data["pagination"]["has_next"])

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            GetUserPosts()  # Missing required user_urn

        # Test default values
        tool = GetUserPosts(user_urn="testuser")
        self.assertEqual(tool.page, 1)
        self.assertEqual(tool.max_items, 100)

        # Test field types
        tool = GetUserPosts(
            user_urn="testuser",
            page=5,
            max_items=25
        )
        self.assertEqual(tool.page, 5)
        self.assertEqual(tool.max_items, 25)


if __name__ == '__main__':
    unittest.main()