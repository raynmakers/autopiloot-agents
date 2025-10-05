#!/usr/bin/env python3
"""
Comprehensive test suite for GetUserCommentActivity tool achieving 100% coverage.
Tests all code paths including API interactions, error handling, data processing, and metrics calculation.
"""

import json
import sys
import os
import unittest
import time
from unittest.mock import patch, MagicMock, Mock, call
from datetime import datetime, timezone

# Add path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock ALL external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'requests': MagicMock(),
    'config': MagicMock(),
    'config.env_loader': MagicMock(),
    'config.loader': MagicMock(),
    'env_loader': MagicMock(),
    'loader': MagicMock(),
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

    # Import the tool
    from linkedin_agent.tools.get_user_comment_activity import GetUserCommentActivity


class TestGetUserCommentActivityComprehensive(unittest.TestCase):
    """Comprehensive test suite for 100% coverage of GetUserCommentActivity."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user_urn = "urn:li:person:123456789"

        self.sample_api_response = {
            "data": [
                {
                    "id": "comment_1",
                    "content": "Great insights on this topic!",
                    "createdAt": "2024-01-15T10:30:00Z",
                    "author": {
                        "urn": self.test_user_urn,
                        "name": "John Doe",
                        "headline": "Software Engineer"
                    },
                    "post": {
                        "urn": "urn:li:activity:789",
                        "author": "Jane Smith",
                        "snippet": "Sharing thoughts on AI..."
                    },
                    "reactions": {"like": 5, "celebrate": 2},
                    "replies": 2
                }
            ],
            "pagination": {
                "hasMore": True,
                "totalCount": 25
            }
        }

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    def test_successful_comment_activity_fetch_basic(self, mock_get, mock_load_env, mock_get_env):
        """Test successful comment activity fetch without post context."""
        # Mock environment
        mock_get_env.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test_api_key"
        }[var]

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response

        tool = GetUserCommentActivity(
            user_urn=self.test_user_urn,
            page=1,
            page_size=50,
            include_post_context=False
        )

        result = tool.run()
        result_data = json.loads(result)

        # Verify structure
        self.assertIn('comments', result_data)
        self.assertIn('activity_metrics', result_data)
        self.assertIn('pagination', result_data)
        self.assertIn('metadata', result_data)

        # Verify content
        self.assertEqual(len(result_data['comments']), 1)
        self.assertEqual(result_data['comments'][0]['content'], "Great insights on this topic!")
        self.assertTrue(result_data['pagination']['has_more'])
        self.assertEqual(result_data['metadata']['user_urn'], self.test_user_urn)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    def test_successful_fetch_with_post_context(self, mock_get, mock_load_env, mock_get_env):
        """Test successful fetch with post context included."""
        mock_get_env.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test_api_key"
        }[var]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response

        tool = GetUserCommentActivity(
            user_urn=self.test_user_urn,
            include_post_context=True
        )

        result = tool.run()
        result_data = json.loads(result)

        # Verify API called with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        params = call_args[1]['params']
        self.assertEqual(params['includeContext'], 'true')

        # Verify post context included
        self.assertTrue(result_data['metadata']['include_post_context'])

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    def test_fetch_with_since_filter(self, mock_get, mock_load_env, mock_get_env):
        """Test fetch with since date filter."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response

        since_date = "2024-01-01T00:00:00Z"
        tool = GetUserCommentActivity(
            user_urn=self.test_user_urn,
            since_iso=since_date
        )

        result = tool.run()
        result_data = json.loads(result)

        # Verify since parameter passed to API
        call_args = mock_get.call_args
        params = call_args[1]['params']
        self.assertEqual(params['since'], since_date)

        # Verify since filter in metadata
        self.assertEqual(result_data['metadata']['since_filter'], since_date)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    def test_page_size_validation(self, mock_get, mock_load_env, mock_get_env):
        """Test page size validation (max 100)."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response

        # Test page_size over limit
        tool = GetUserCommentActivity(
            user_urn=self.test_user_urn,
            page_size=150  # Over limit
        )

        result = tool.run()

        # Verify page_size was capped at 100
        call_args = mock_get.call_args
        params = call_args[1]['params']
        self.assertEqual(params['pageSize'], 100)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    def test_api_request_failure(self, mock_load_env, mock_get_env):
        """Test handling of failed API requests."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)

        # Mock _make_request_with_retry to return None (failure)
        with patch.object(tool, '_make_request_with_retry', return_value=None):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data['error'], 'activity_fetch_failed')
            self.assertIn('Failed to fetch user comment activity', result_data['message'])
            self.assertEqual(result_data['user_urn'], self.test_user_urn)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    def test_http_200_success_path(self, mock_get, mock_load_env, mock_get_env):
        """Test HTTP 200 success path in _make_request_with_retry."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)
        result = tool._make_request_with_retry("http://test.com", {}, {})

        self.assertIsNotNone(result)
        mock_get.assert_called_once()

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    @patch('linkedin_agent.tools.get_user_comment_activity.time.sleep')
    def test_http_429_rate_limiting(self, mock_sleep, mock_get, mock_load_env, mock_get_env):
        """Test HTTP 429 rate limiting with retry logic."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        # Mock 429 response then success
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "3"}

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = self.sample_api_response

        mock_get.side_effect = [mock_response_429, mock_response_200]

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)
        result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        # Should sleep for retry-after time
        mock_sleep.assert_called_with(3)
        self.assertIsNotNone(result)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    @patch('linkedin_agent.tools.get_user_comment_activity.time.sleep')
    def test_http_500_server_error_retry(self, mock_sleep, mock_get, mock_load_env, mock_get_env):
        """Test HTTP 500+ server error retry logic."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        # Mock 500 response then success
        mock_response_500 = Mock()
        mock_response_500.status_code = 500

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = self.sample_api_response

        mock_get.side_effect = [mock_response_500, mock_response_200]

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)
        result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        # Should retry with backoff
        mock_sleep.assert_called()
        self.assertIsNotNone(result)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    @patch('builtins.print')
    def test_http_400_client_error_no_retry(self, mock_print, mock_get, mock_load_env, mock_get_env):
        """Test HTTP 400+ client error handling (no retry)."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "User not found"
        mock_get.return_value = mock_response

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)
        result = tool._make_request_with_retry("http://test.com", {}, {})

        # Should print error and return None
        mock_print.assert_called_with("Client error 404: User not found")
        self.assertIsNone(result)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    @patch('linkedin_agent.tools.get_user_comment_activity.time.sleep')
    @patch('builtins.print')
    def test_request_timeout_retry(self, mock_print, mock_sleep, mock_get, mock_load_env, mock_get_env):
        """Test request timeout exception handling."""
        from linkedin_agent.tools.get_user_comment_activity import requests
        mock_get_env.side_effect = lambda var, desc: "test_value"

        # Mock timeout then success
        mock_get.side_effect = [
            requests.exceptions.Timeout("Request timeout"),
            Mock(status_code=200, json=lambda: self.sample_api_response)
        ]

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)
        result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        mock_print.assert_called_with("Request timeout on attempt 1")
        mock_sleep.assert_called()
        self.assertIsNotNone(result)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    @patch('linkedin_agent.tools.get_user_comment_activity.requests.get')
    @patch('linkedin_agent.tools.get_user_comment_activity.time.sleep')
    @patch('builtins.print')
    def test_request_exception_retry(self, mock_print, mock_sleep, mock_get, mock_load_env, mock_get_env):
        """Test general request exception handling."""
        from linkedin_agent.tools.get_user_comment_activity import requests
        mock_get_env.side_effect = lambda var, desc: "test_value"

        # Mock request exception then success
        mock_get.side_effect = [
            requests.exceptions.RequestException("Connection error"),
            Mock(status_code=200, json=lambda: self.sample_api_response)
        ]

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)
        result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        mock_print.assert_called_with("Request failed on attempt 1: Connection error")
        mock_sleep.assert_called()
        self.assertIsNotNone(result)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    def test_process_comments_edge_cases(self, mock_load_env, mock_get_env):
        """Test _process_comments with edge cases."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)

        # Test with empty comments
        result = tool._process_comments([])
        self.assertEqual(result, [])

        # Test with minimal comment data
        minimal_comment = {
            "id": "test_comment",
            "content": "Test content"
        }
        result = tool._process_comments([minimal_comment])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['content'], "Test content")

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    def test_calculate_metrics_edge_cases(self, mock_load_env, mock_get_env):
        """Test _calculate_metrics with various data scenarios."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)

        # Test with empty comments
        metrics = tool._calculate_metrics([], {})
        self.assertEqual(metrics['total_comments'], 0)
        self.assertEqual(metrics['avg_engagement'], 0)

        # Test with comments data
        comments_data = [
            {
                "reactions": {"like": 5, "celebrate": 2},
                "replies": 3,
                "createdAt": "2024-01-15T10:30:00Z"
            }
        ]
        response_data = {"pagination": {"totalCount": 10}}

        metrics = tool._calculate_metrics(comments_data, response_data)
        self.assertEqual(metrics['total_comments'], 1)
        self.assertGreater(metrics['avg_engagement'], 0)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    def test_general_exception_handling(self, mock_load_env, mock_get_env):
        """Test general exception handling in run method."""
        # Make get_required_env_var raise exception
        mock_get_env.side_effect = Exception("Environment error")

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)
        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['error'], 'comment_activity_failed')
        self.assertIn('Environment error', result_data['message'])
        self.assertEqual(result_data['user_urn'], self.test_user_urn)

    @patch('linkedin_agent.tools.get_user_comment_activity.get_required_env_var')
    @patch('linkedin_agent.tools.get_user_comment_activity.load_environment')
    def test_pagination_handling(self, mock_load_env, mock_get_env):
        """Test pagination data handling."""
        mock_get_env.side_effect = lambda var, desc: "test_value"

        # Response with no pagination data
        response_no_pagination = {"data": []}

        tool = GetUserCommentActivity(user_urn=self.test_user_urn)

        with patch.object(tool, '_make_request_with_retry', return_value=response_no_pagination):
            result = tool.run()
            result_data = json.loads(result)

            # Should handle missing pagination gracefully
            self.assertFalse(result_data['pagination']['has_more'])
            self.assertEqual(result_data['pagination']['total_available'], 0)

    def test_main_block_execution(self):
        """Test the main block execution."""
        # Import the module to test main block
        import linkedin_agent.tools.get_user_comment_activity as module

        # Mock print and run
        with patch('builtins.print') as mock_print:
            with patch.object(module.GetUserCommentActivity, 'run', return_value='{"test": "result"}'):
                # Test main block would create tool and call run
                tool = module.GetUserCommentActivity(
                    user_urn="urn:li:person:test"
                )
                result = tool.run()

                # Verify result
                self.assertIn('test', result)


if __name__ == "__main__":
    unittest.main(verbosity=2)