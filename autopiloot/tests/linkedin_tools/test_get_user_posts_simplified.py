"""
Simplified test for get_user_posts tool targeting coverage.
"""

import unittest
import os
import sys
import json
import importlib.util
from unittest.mock import Mock, MagicMock, patch


class TestGetUserPostsSimplified(unittest.TestCase):
    """Simplified test targeting coverage for get_user_posts.py."""

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
    def test_successful_single_page_fetch(self, mock_import):
        """Test successful single page fetch."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(side_effect=lambda key, desc: {
                    "RAPIDAPI_LINKEDIN_HOST": "linkedin-scraper.p.rapidapi.com",
                    "RAPIDAPI_LINKEDIN_KEY": "test_api_key"
                }[key])
                return mock_env
            elif 'loader' in name:
                mock_loader = MagicMock()
                return mock_loader
            return MagicMock()

        mock_import.side_effect = side_effect

        tool = self.GetUserPosts(user_urn="alexhormozi", page=1, page_size=25)

        # Mock successful API response
        mock_response_data = {
            "data": [
                {"id": "post1", "text": "First post", "likes": 100},
                {"id": "post2", "text": "Second post", "likes": 50}
            ],
            "pagination": {"hasMore": False}
        }

        tool._make_request_with_retry = Mock(return_value=mock_response_data)

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(len(result_data['posts']), 2)
        self.assertEqual(result_data['pagination']['total_fetched'], 2)
        self.assertFalse(result_data['pagination']['has_more'])

    def test_page_size_validation(self):
        """Test page_size validation logic."""
        tool = self.GetUserPosts(user_urn="test", page_size=150)
        # Before running, validation should happen
        # But we need to trigger the validation in run()

        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if 'env_loader' in name:
                    mock_env = MagicMock()
                    mock_env.load_environment = Mock()
                    mock_env.get_required_env_var = Mock(return_value="test_value")
                    return mock_env
                return MagicMock()
            mock_import.side_effect = side_effect

            tool._make_request_with_retry = Mock(return_value={
                "data": [], "pagination": {"hasMore": False}
            })

            # This will trigger the validation in run()
            result = tool.run()

            # Check that page_size was capped during run()
            self.assertEqual(tool.page_size, 100)

    def test_max_items_validation(self):
        """Test max_items validation logic."""
        tool = self.GetUserPosts(user_urn="test", max_items=1500)

        with patch('builtins.__import__') as mock_import:
            def side_effect(name, *args, **kwargs):
                if 'env_loader' in name:
                    mock_env = MagicMock()
                    mock_env.load_environment = Mock()
                    mock_env.get_required_env_var = Mock(return_value="test_value")
                    return mock_env
                return MagicMock()
            mock_import.side_effect = side_effect

            tool._make_request_with_retry = Mock(return_value={
                "data": [], "pagination": {"hasMore": False}
            })

            result = tool.run()
            self.assertEqual(tool.max_items, 1000)

    @patch('builtins.__import__')
    def test_since_parameter_inclusion(self, mock_import):
        """Test since parameter inclusion in metadata."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(return_value="test_value")
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        since_date = "2024-01-01T00:00:00Z"
        tool = self.GetUserPosts(user_urn="testuser", since_iso=since_date)

        tool._make_request_with_retry = Mock(return_value={
            "data": [], "pagination": {"hasMore": False}
        })

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['metadata']['since_filter'], since_date)

    @patch('builtins.__import__')
    @patch('time.sleep')
    def test_multi_page_pagination(self, mock_sleep, mock_import):
        """Test multi-page pagination."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(return_value="test_value")
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        tool = self.GetUserPosts(user_urn="testuser", page_size=5, max_items=12)

        # Mock responses for multiple pages
        responses = [
            {"data": [{"id": f"post{i}"} for i in range(1, 6)], "pagination": {"hasMore": True}},
            {"data": [{"id": f"post{i}"} for i in range(6, 11)], "pagination": {"hasMore": True}},
            {"data": [{"id": f"post{i}"} for i in range(11, 13)], "pagination": {"hasMore": False}}
        ]

        tool._make_request_with_retry = Mock(side_effect=responses)

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(len(result_data['posts']), 12)
        self.assertEqual(result_data['pagination']['total_fetched'], 12)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('builtins.__import__')
    def test_no_response_data_handling(self, mock_import):
        """Test handling when request returns None."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(return_value="test_value")
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        tool = self.GetUserPosts(user_urn="testuser")
        tool._make_request_with_retry = Mock(return_value=None)

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(len(result_data['posts']), 0)
        self.assertEqual(result_data['pagination']['total_fetched'], 0)

    @patch('builtins.__import__')
    def test_empty_posts_response(self, mock_import):
        """Test handling when API returns empty posts list."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(return_value="test_value")
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        tool = self.GetUserPosts(user_urn="testuser")
        tool._make_request_with_retry = Mock(return_value={
            "data": [],  # Empty posts list
            "pagination": {"hasMore": True}
        })

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(len(result_data['posts']), 0)
        self.assertFalse(result_data['pagination']['has_more'])

    @patch('builtins.__import__')
    def test_max_items_limit_during_pagination(self, mock_import):
        """Test max_items limit enforcement during pagination."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(return_value="test_value")
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        tool = self.GetUserPosts(user_urn="testuser", page_size=10, max_items=15)

        # Mock response with more posts than max_items
        tool._make_request_with_retry = Mock(return_value={
            "data": [{"id": f"post{i}"} for i in range(20)],  # 20 posts but max_items=15
            "pagination": {"hasMore": False}
        })

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(len(result_data['posts']), 15)
        self.assertEqual(result_data['pagination']['total_fetched'], 15)

    @patch('builtins.__import__')
    def test_exception_handling(self, mock_import):
        """Test exception handling in run method."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock(side_effect=Exception("Environment error"))
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        tool = self.GetUserPosts(user_urn="testuser")
        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['error'], 'posts_fetch_failed')
        self.assertEqual(result_data['user_urn'], 'testuser')

    def test_http_200_success(self):
        """Test successful HTTP 200 response."""
        tool = self.GetUserPosts(user_urn="testuser")

        # Create real response object
        class MockResponse:
            def __init__(self):
                self.status_code = 200
            def json(self):
                return {"data": [{"id": "post1"}]}

        mock_response = MockResponse()

        with patch('requests.get', return_value=mock_response):
            result = tool._make_request_with_retry("http://test.com", {}, {})

        self.assertEqual(result, {"data": [{"id": "post1"}]})

    @patch('time.sleep')
    def test_rate_limiting_429(self, mock_sleep):
        """Test rate limiting 429 response handling."""
        tool = self.GetUserPosts(user_urn="testuser")

        # Create response objects with proper attributes
        class MockResponse429:
            def __init__(self):
                self.status_code = 429
                self.headers = {"Retry-After": "30"}

        class MockResponse200:
            def __init__(self):
                self.status_code = 200
            def json(self):
                return {"data": []}

        responses = [MockResponse429(), MockResponse200()]

        with patch('requests.get', side_effect=responses):
            result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        mock_sleep.assert_called_with(30)
        self.assertEqual(result, {"data": []})

    @patch('time.sleep')
    def test_server_error_retry(self, mock_sleep):
        """Test server error retry logic."""
        tool = self.GetUserPosts(user_urn="testuser")

        class MockResponse500:
            def __init__(self):
                self.status_code = 502

        with patch('requests.get', return_value=MockResponse500()):
            result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        self.assertEqual(mock_sleep.call_count, 2)
        self.assertIsNone(result)

    @patch('builtins.print')
    def test_client_error_no_retry(self, mock_print):
        """Test client error doesn't retry."""
        tool = self.GetUserPosts(user_urn="testuser")

        class MockResponse403:
            def __init__(self):
                self.status_code = 403
                self.text = "Access forbidden"

        with patch('requests.get', return_value=MockResponse403()):
            result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=3)

        mock_print.assert_called_with("Client error 403: Access forbidden")
        self.assertIsNone(result)

    @patch('time.sleep')
    @patch('builtins.print')
    def test_timeout_exception(self, mock_print, mock_sleep):
        """Test timeout exception handling."""
        tool = self.GetUserPosts(user_urn="testuser")

        with patch('requests.get') as mock_get:
            # Create actual exception classes
            class TimeoutError(Exception):
                pass

            # Mock the module to have proper exception classes
            with patch.dict('sys.modules', {'requests.exceptions': type('', (), {
                'Timeout': TimeoutError,
                'RequestException': Exception
            })}):
                mock_get.side_effect = TimeoutError("Request timed out")

                result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        self.assertEqual(mock_sleep.call_count, 2)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()