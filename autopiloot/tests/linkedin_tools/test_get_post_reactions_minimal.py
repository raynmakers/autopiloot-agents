"""
Focused test suite for GetPostReactions tool.
Tests core functionality with minimal dependencies.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys
from datetime import datetime, timezone

# Add the linkedin_agent tools directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'linkedin_agent', 'tools'))


class MockBaseTool:
    """Mock BaseTool for testing."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def MockField(default=None, description=""):
    """Mock Field function."""
    return default


class TestGetPostReactionsCore(unittest.TestCase):
    """Test core GetPostReactions functionality."""

    def setUp(self):
        """Set up test fixtures with comprehensive mocking."""
        # Mock all external dependencies
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'requests': MagicMock(),
            'dotenv': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
        }

        # Apply module mocks
        for module_name, mock_module in self.mock_modules.items():
            sys.modules[module_name] = mock_module

        # Set up specific mock objects
        sys.modules['agency_swarm'].tools.BaseTool = MockBaseTool
        sys.modules['pydantic'].Field = MockField

        # Mock requests and its exceptions
        self.mock_requests = MagicMock()
        self.mock_requests.exceptions = MagicMock()
        self.mock_requests.exceptions.Timeout = Exception
        self.mock_requests.exceptions.RequestException = Exception
        sys.modules['requests'] = self.mock_requests

        # Mock environment functions
        self.mock_env_loader = MagicMock()
        sys.modules['env_loader'] = self.mock_env_loader

        # Import the class after mocking
        from get_post_reactions import GetPostReactions
        self.GetPostReactions = GetPostReactions

    def tearDown(self):
        """Clean up mocks."""
        # Remove mocked modules
        for module_name in self.mock_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]

        # Clear any cached imports
        if 'get_post_reactions' in sys.modules:
            del sys.modules['get_post_reactions']

    def test_tool_initialization_basic(self):
        """Test basic tool initialization."""
        post_ids = ["urn:li:activity:123", "urn:li:activity:456"]
        tool = self.GetPostReactions(post_ids=post_ids)

        self.assertEqual(tool.post_ids, post_ids)
        self.assertFalse(tool.include_details)
        self.assertEqual(tool.page, 1)
        self.assertEqual(tool.page_size, 100)

    def test_tool_initialization_custom_params(self):
        """Test tool initialization with custom parameters."""
        post_ids = ["urn:li:activity:789"]
        tool = self.GetPostReactions(
            post_ids=post_ids,
            include_details=True,
            page=2,
            page_size=50
        )

        self.assertEqual(tool.post_ids, post_ids)
        self.assertTrue(tool.include_details)
        self.assertEqual(tool.page, 2)
        self.assertEqual(tool.page_size, 50)

    @patch.dict(os.environ, {
        'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
        'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
    })
    def test_empty_post_ids_error(self):
        """Test error handling for empty post IDs."""
        tool = self.GetPostReactions(post_ids=[])

        # Mock environment functions
        with patch('get_post_reactions.load_environment'), \
             patch('get_post_reactions.get_required_env_var') as mock_env_var:

            mock_env_var.side_effect = lambda key, desc: {
                'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
                'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
            }.get(key, 'default-value')

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data['error'], 'invalid_input')
            self.assertEqual(result_data['message'], 'No post IDs provided')

    @patch.dict(os.environ, {
        'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
        'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
    })
    def test_successful_single_post_fetch(self):
        """Test successful API response processing."""
        post_id = "urn:li:activity:123"
        tool = self.GetPostReactions(post_ids=[post_id])

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "summary": {
                "totalReactions": 150,
                "reactionTypes": {
                    "like": 100,
                    "celebrate": 30,
                    "support": 20
                }
            },
            "views": 3000
        }

        with patch('get_post_reactions.load_environment'), \
             patch('get_post_reactions.get_required_env_var') as mock_env_var, \
             patch('get_post_reactions.requests.get', return_value=mock_response):

            mock_env_var.side_effect = lambda key, desc: {
                'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
                'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
            }.get(key, 'default-value')

            result = tool.run()
            result_data = json.loads(result)

            # Verify response structure
            self.assertIn('reactions_by_post', result_data)
            self.assertIn('aggregate_metrics', result_data)
            self.assertIn('metadata', result_data)

            # Verify post data
            post_data = result_data['reactions_by_post'][post_id]
            self.assertEqual(post_data['total_reactions'], 150)
            self.assertEqual(post_data['breakdown']['like'], 100)
            self.assertEqual(post_data['breakdown']['celebrate'], 30)
            self.assertEqual(post_data['top_reaction'], 'like')
            self.assertEqual(post_data['engagement_rate'], 0.05)  # 150/3000

    @patch.dict(os.environ, {
        'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
        'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
    })
    def test_multiple_posts_aggregation(self):
        """Test aggregation logic for multiple posts."""
        post_ids = ["urn:li:activity:123", "urn:li:activity:456"]
        tool = self.GetPostReactions(post_ids=post_ids)

        # Mock API responses
        responses = [
            Mock(status_code=200, **{
                'json.return_value': {
                    "summary": {
                        "totalReactions": 100,
                        "reactionTypes": {"like": 80, "celebrate": 20}
                    },
                    "views": 2000
                }
            }),
            Mock(status_code=200, **{
                'json.return_value': {
                    "summary": {
                        "totalReactions": 50,
                        "reactionTypes": {"like": 30, "love": 20}
                    },
                    "views": 1000
                }
            })
        ]

        with patch('get_post_reactions.load_environment'), \
             patch('get_post_reactions.get_required_env_var') as mock_env_var, \
             patch('get_post_reactions.requests.get', side_effect=responses), \
             patch('get_post_reactions.time.sleep'):  # Mock sleep for rate limiting

            mock_env_var.side_effect = lambda key, desc: 'test-value'

            result = tool.run()
            result_data = json.loads(result)

            # Verify aggregate metrics
            aggregate = result_data['aggregate_metrics']
            self.assertEqual(aggregate['total_reactions'], 150)  # 100 + 50
            self.assertEqual(aggregate['average_reactions_per_post'], 75.0)
            self.assertEqual(aggregate['posts_with_data'], 2)
            self.assertEqual(aggregate['posts_with_errors'], 0)

            # Verify reaction distribution
            expected_distribution = {"like": 110, "celebrate": 20, "love": 20}
            self.assertEqual(aggregate['reaction_distribution'], expected_distribution)

    @patch.dict(os.environ, {
        'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
        'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
    })
    def test_api_error_handling(self):
        """Test API error response handling."""
        post_id = "urn:li:activity:404"
        tool = self.GetPostReactions(post_ids=[post_id])

        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Post not found"

        with patch('get_post_reactions.load_environment'), \
             patch('get_post_reactions.get_required_env_var') as mock_env_var, \
             patch('get_post_reactions.requests.get', return_value=mock_response):

            mock_env_var.side_effect = lambda key, desc: 'test-value'

            result = tool.run()
            result_data = json.loads(result)

            # Verify error handling
            post_data = result_data['reactions_by_post'][post_id]
            self.assertEqual(post_data['total_reactions'], 0)
            self.assertEqual(post_data['breakdown'], {})
            self.assertEqual(post_data['error'], 'fetch_failed')

    @patch.dict(os.environ, {
        'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
        'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
    })
    def test_rate_limiting_retry_logic(self):
        """Test retry logic for rate-limited responses."""
        post_id = "urn:li:activity:429"
        tool = self.GetPostReactions(post_ids=[post_id])

        # Mock rate limit response followed by success
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {'Retry-After': '1'}

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "summary": {
                "totalReactions": 25,
                "reactionTypes": {"like": 25}
            },
            "views": 500
        }

        with patch('get_post_reactions.load_environment'), \
             patch('get_post_reactions.get_required_env_var') as mock_env_var, \
             patch('get_post_reactions.requests.get', side_effect=[rate_limit_response, success_response]), \
             patch('get_post_reactions.time.sleep') as mock_sleep:

            mock_env_var.side_effect = lambda key, desc: 'test-value'

            result = tool.run()
            result_data = json.loads(result)

            # Verify retry occurred
            mock_sleep.assert_called_with(1)  # Retry-After header value

            # Verify eventual success
            post_data = result_data['reactions_by_post'][post_id]
            self.assertEqual(post_data['total_reactions'], 25)

    def test_process_reactions_method(self):
        """Test the _process_reactions method directly."""
        tool = self.GetPostReactions(post_ids=["test"])

        response_data = {
            "summary": {
                "totalReactions": 75,
                "reactionTypes": {
                    "like": 50,
                    "celebrate": 15,
                    "support": 10
                }
            },
            "views": 1500
        }

        result = tool._process_reactions(response_data, "test_post")

        self.assertEqual(result['total_reactions'], 75)
        self.assertEqual(result['breakdown']['like'], 50)
        self.assertEqual(result['top_reaction'], 'like')
        self.assertEqual(result['engagement_rate'], 0.05)  # 75/1500

    def test_process_reactions_no_views(self):
        """Test _process_reactions when views data is missing."""
        tool = self.GetPostReactions(post_ids=["test"])

        response_data = {
            "summary": {
                "totalReactions": 30,
                "reactionTypes": {"like": 30}
            }
            # No views field
        }

        result = tool._process_reactions(response_data, "test_post")

        self.assertEqual(result['engagement_rate'], 0)

    def test_process_reactions_with_details(self):
        """Test _process_reactions with reactor details."""
        tool = self.GetPostReactions(post_ids=["test"], include_details=True)

        response_data = {
            "summary": {
                "totalReactions": 40,
                "reactionTypes": {"like": 25, "celebrate": 15}
            },
            "views": 800,
            "reactors": [
                {
                    "name": "John Doe",
                    "headline": "Software Engineer",
                    "reactionType": "like",
                    "profileUrl": "https://linkedin.com/in/john"
                },
                {
                    "name": "Jane Smith",
                    "reactionType": "celebrate"
                    # Missing headline and profileUrl to test defaults
                }
            ],
            "pagination": {"hasMore": True}
        }

        result = tool._process_reactions(response_data, "test_post")

        self.assertIn('reactors', result)
        self.assertEqual(len(result['reactors']), 2)
        self.assertEqual(result['reactors'][0]['name'], 'John Doe')
        self.assertEqual(result['reactors'][1]['headline'], '')  # Default value
        self.assertTrue(result['has_more_reactors'])

    @patch.dict(os.environ, {
        'RAPIDAPI_LINKEDIN_HOST': 'test-host.com',
        'RAPIDAPI_LINKEDIN_KEY': 'test-key-123'
    })
    def test_exception_handling(self):
        """Test general exception handling."""
        tool = self.GetPostReactions(post_ids=["test"])

        with patch('get_post_reactions.load_environment'), \
             patch('get_post_reactions.get_required_env_var', side_effect=Exception("Config error")):

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data['error'], 'reactions_fetch_failed')
            self.assertIn('Config error', result_data['message'])
            self.assertEqual(result_data['post_ids'], ["test"])

    def test_make_request_with_retry_success(self):
        """Test _make_request_with_retry method for successful request."""
        tool = self.GetPostReactions(post_ids=["test"])

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}

        with patch('get_post_reactions.requests.get', return_value=mock_response):
            result = tool._make_request_with_retry("http://test.com", {}, {})

            self.assertEqual(result, {"data": "success"})

    def test_make_request_with_retry_failure(self):
        """Test _make_request_with_retry method for failed requests."""
        tool = self.GetPostReactions(post_ids=["test"])

        mock_response = Mock()
        mock_response.status_code = 500

        with patch('get_post_reactions.requests.get', return_value=mock_response), \
             patch('get_post_reactions.time.sleep'):
            result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=1)

            self.assertIsNone(result)


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)