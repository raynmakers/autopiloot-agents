"""
Comprehensive test coverage for GetUserPosts tool targeting missing lines.
Targets specific lines: 89, 107, 123, 128-129, 143, 161, 194, 198-201, 205-212, 215-223
"""

import unittest
import sys
import os
import json
import importlib.util
from unittest.mock import Mock, patch, MagicMock
import requests
import time


class TestGetUserPostsComprehensiveCoverage(unittest.TestCase):
    """
    Comprehensive coverage tests for GetUserPosts tool.
    Focuses on missing coverage lines for error handling and edge cases.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with proper mocking and imports."""
        # Define all mock modules
        mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'requests': MagicMock(),
        }

        # Mock Pydantic Field
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)

        with patch.dict('sys.modules', mock_modules):
            # Create mock BaseTool
            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
            sys.modules['pydantic'].Field = mock_field

            # Import using importlib for proper coverage
            tool_path = os.path.join(os.path.dirname(__file__), '..', '..',
                                   'linkedin_agent', 'tools', 'get_user_posts.py')
            spec = importlib.util.spec_from_file_location("get_user_posts", tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.GetUserPosts = module.GetUserPosts

    @patch('builtins.__import__')
    def test_max_items_limit_validation_line_89(self, mock_import):
        """Test max_items validation with value > 1000 (line 89)."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(side_effect=lambda key, desc: {
                    "RAPIDAPI_LINKEDIN_HOST": "linkedin-api1.p.rapidapi.com",
                    "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
                }[key])
                return mock_env
            elif 'loader' in name:
                return MagicMock()
            return MagicMock()

        mock_import.side_effect = side_effect

        tool = self.GetUserPosts(
            user_urn="alexhormozi",
            max_items=1500  # Exceeds 1000 limit
        )

        # Mock successful response
        mock_response_data = {
            "data": [{"id": "post1", "text": "Test post"}],
            "pagination": {"hasMore": False}
        }
        tool._make_request_with_retry = Mock(return_value=mock_response_data)

        result = tool.run()
        result_data = json.loads(result)

        # Verify max_items was clamped to 1000 (line 89 executed)
        self.assertEqual(tool.max_items, 1000)
        self.assertIn("posts", result_data)

    def test_since_iso_parameter_usage_line_107(self):
        """Test since_iso parameter adds to params (line 107)."""
        tool = self.GetUserPosts(
            user_urn="alexhormozi",
            since_iso="2024-01-01T00:00:00Z"
        )

        with patch('get_user_posts.requests.get') as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"id": "post1", "text": "Test post"}],
                "pagination": {"hasMore": False}
            }
            mock_get.return_value = mock_response

            result = tool.run()
            result_data = json.loads(result)

            # Verify since parameter was added to request
            args, kwargs = mock_get.call_args
            params = kwargs['params']
            self.assertEqual(params['since'], "2024-01-01T00:00:00Z")

            # Verify since_filter in metadata (line 161)
            self.assertEqual(result_data["metadata"]["since_filter"], "2024-01-01T00:00:00Z")

    def test_empty_response_data_handling_line_123(self):
        """Test handling when response_data is None/empty (line 123)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch.object(tool, '_make_request_with_retry') as mock_request:
            # Return None to trigger line 123 break
            mock_request.return_value = None

            result = tool.run()
            result_data = json.loads(result)

            # Should have empty posts array
            self.assertEqual(result_data["posts"], [])
            self.assertEqual(result_data["pagination"]["total_fetched"], 0)

    def test_empty_page_posts_handling_lines_128_129(self):
        """Test handling when page_posts is empty (lines 128-129)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch.object(tool, '_make_request_with_retry') as mock_request:
            # Return response with empty data array
            mock_request.return_value = {
                "data": [],  # Empty posts array
                "pagination": {"hasMore": True}
            }

            result = tool.run()
            result_data = json.loads(result)

            # Should stop pagination (has_more = False) and break (line 129)
            self.assertEqual(result_data["posts"], [])
            self.assertEqual(result_data["pagination"]["total_fetched"], 0)
            self.assertFalse(result_data["pagination"]["has_more"])

    def test_rate_limiting_delay_line_143(self):
        """Test rate limiting delay between pages (line 143)."""
        tool = self.GetUserPosts(user_urn="alexhormozi", max_items=50)

        with patch.object(tool, '_make_request_with_retry') as mock_request:
            with patch('get_user_posts.time.sleep') as mock_sleep:
                # Mock two pages of responses
                mock_request.side_effect = [
                    {
                        "data": [{"id": f"post{i}", "text": f"Post {i}"} for i in range(25)],
                        "pagination": {"hasMore": True}
                    },
                    {
                        "data": [{"id": f"post{i}", "text": f"Post {i}"} for i in range(25, 30)],
                        "pagination": {"hasMore": False}
                    }
                ]

                result = tool.run()
                result_data = json.loads(result)

                # Verify sleep was called for rate limiting (line 143)
                mock_sleep.assert_called_with(1)
                self.assertEqual(len(result_data["posts"]), 30)

    def test_successful_response_line_194(self):
        """Test successful HTTP 200 response handling (line 194)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch('get_user_posts.requests.get') as mock_get:
            # Mock successful 200 response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"id": "post1", "text": "Test post"}],
                "pagination": {"hasMore": False}
            }
            mock_get.return_value = mock_response

            # Call _make_request_with_retry directly to hit line 194
            result = tool._make_request_with_retry(
                "https://test.com",
                {"X-RapidAPI-Key": "test"},
                {"urn": "alexhormozi"}
            )

            # Should return the JSON data (line 194)
            self.assertIsNotNone(result)
            self.assertEqual(result["data"][0]["id"], "post1")

    def test_rate_limiting_retry_logic_lines_198_201(self):
        """Test HTTP 429 rate limiting with retry-after handling (lines 198-201)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch('get_user_posts.requests.get') as mock_get:
            with patch('get_user_posts.time.sleep') as mock_sleep:
                # Mock 429 response then success
                mock_response_429 = Mock()
                mock_response_429.status_code = 429
                mock_response_429.headers = {"Retry-After": "5"}

                mock_response_200 = Mock()
                mock_response_200.status_code = 200
                mock_response_200.json.return_value = {"data": []}

                mock_get.side_effect = [mock_response_429, mock_response_200]

                # Call _make_request_with_retry to hit lines 198-201
                result = tool._make_request_with_retry(
                    "https://test.com",
                    {"X-RapidAPI-Key": "test"},
                    {"urn": "alexhormozi"}
                )

                # Verify sleep was called with min(retry_after, 60) (line 199)
                mock_sleep.assert_called_with(5)
                self.assertIsNotNone(result)

    def test_server_error_retry_lines_205_207(self):
        """Test server error (5xx) retry logic (lines 205-207)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch('get_user_posts.requests.get') as mock_get:
            with patch('get_user_posts.time.sleep') as mock_sleep:
                # Mock 500 server error then success
                mock_response_500 = Mock()
                mock_response_500.status_code = 500

                mock_response_200 = Mock()
                mock_response_200.status_code = 200
                mock_response_200.json.return_value = {"data": []}

                mock_get.side_effect = [mock_response_500, mock_response_200]

                # Call _make_request_with_retry to hit lines 205-207
                result = tool._make_request_with_retry(
                    "https://test.com",
                    {"X-RapidAPI-Key": "test"},
                    {"urn": "alexhormozi"}
                )

                # Verify sleep was called for server error retry (line 205)
                mock_sleep.assert_called_with(1)
                self.assertIsNotNone(result)

    def test_client_error_no_retry_lines_210_212(self):
        """Test client error (4xx) handling without retry (lines 210-212)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch('get_user_posts.requests.get') as mock_get:
            with patch('builtins.print') as mock_print:
                # Mock 404 client error
                mock_response = Mock()
                mock_response.status_code = 404
                mock_response.text = "Not Found"
                mock_get.return_value = mock_response

                # Call _make_request_with_retry to hit lines 210-212
                result = tool._make_request_with_retry(
                    "https://test.com",
                    {"X-RapidAPI-Key": "test"},
                    {"urn": "alexhormozi"}
                )

                # Should return None for client errors (line 212)
                self.assertIsNone(result)
                # Should print error message (line 211)
                mock_print.assert_called_with("Client error 404: Not Found")

    def test_request_timeout_handling_lines_215_217(self):
        """Test request timeout exception handling (lines 215-217)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch('get_user_posts.requests.get') as mock_get:
            with patch('get_user_posts.time.sleep') as mock_sleep:
                with patch('builtins.print') as mock_print:
                    # Mock timeout then success
                    mock_get.side_effect = [
                        requests.exceptions.Timeout("Request timeout"),
                        Mock(status_code=200, json=lambda: {"data": []})
                    ]

                    # Call _make_request_with_retry to hit lines 215-217
                    result = tool._make_request_with_retry(
                        "https://test.com",
                        {"X-RapidAPI-Key": "test"},
                        {"urn": "alexhormozi"}
                    )

                    # Should print timeout message (line 215)
                    mock_print.assert_called_with("Request timeout on attempt 1")
                    # Should sleep for retry (line 216)
                    mock_sleep.assert_called()
                    # Should eventually succeed
                    self.assertIsNotNone(result)

    def test_request_exception_handling_lines_219_221(self):
        """Test general request exception handling (lines 219-221)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch('get_user_posts.requests.get') as mock_get:
            with patch('get_user_posts.time.sleep') as mock_sleep:
                with patch('builtins.print') as mock_print:
                    # Mock RequestException then success
                    mock_get.side_effect = [
                        requests.exceptions.RequestException("Connection error"),
                        Mock(status_code=200, json=lambda: {"data": []})
                    ]

                    # Call _make_request_with_retry to hit lines 219-221
                    result = tool._make_request_with_retry(
                        "https://test.com",
                        {"X-RapidAPI-Key": "test"},
                        {"urn": "alexhormozi"}
                    )

                    # Should print exception message (line 219)
                    mock_print.assert_called_with("Request failed on attempt 1: Connection error")
                    # Should sleep for retry (line 220)
                    mock_sleep.assert_called()
                    # Should eventually succeed
                    self.assertIsNotNone(result)

    def test_all_retries_exhausted_line_223(self):
        """Test when all retry attempts are exhausted (line 223)."""
        tool = self.GetUserPosts(user_urn="alexhormozi")

        with patch('get_user_posts.requests.get') as mock_get:
            with patch('get_user_posts.time.sleep'):
                # Mock persistent server errors
                mock_response = Mock()
                mock_response.status_code = 500
                mock_get.return_value = mock_response

                # Call _make_request_with_retry to exhaust retries
                result = tool._make_request_with_retry(
                    "https://test.com",
                    {"X-RapidAPI-Key": "test"},
                    {"urn": "alexhormozi"},
                    max_retries=2  # Use small number for faster test
                )

                # Should return None after all retries exhausted (line 223)
                self.assertIsNone(result)
                # Should have called requests.get max_retries times
                self.assertEqual(mock_get.call_count, 2)


if __name__ == '__main__':
    unittest.main()