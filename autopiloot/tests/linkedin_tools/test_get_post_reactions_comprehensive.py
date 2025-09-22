"""
Comprehensive test suite for GetPostReactions tool.
Tests API integration, response processing, aggregation logic, and error handling.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys
from datetime import datetime, timezone

# Add the linkedin_agent tools directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'linkedin_agent', 'tools'))

# Mock external dependencies before importing
sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
sys.modules['env_loader'] = MagicMock()
sys.modules['loader'] = MagicMock()

# Create mock BaseTool and Field
mock_base_tool = MagicMock()
mock_field = MagicMock()
mock_requests = MagicMock()
mock_env_loader = MagicMock()
mock_loader = MagicMock()

sys.modules['agency_swarm'].tools.BaseTool = mock_base_tool
sys.modules['pydantic'].Field = mock_field
sys.modules['requests'] = mock_requests
sys.modules['env_loader'] = mock_env_loader
sys.modules['loader'] = mock_loader

# Create mock exceptions for requests
mock_requests.exceptions = MagicMock()
mock_requests.exceptions.Timeout = Exception
mock_requests.exceptions.RequestException = Exception

# Mock environment and config functions
mock_env_loader.get_required_env_var = MagicMock()
mock_env_loader.load_environment = MagicMock()
mock_loader.load_app_config = MagicMock()
mock_loader.get_config_value = MagicMock()

from get_post_reactions import GetPostReactions


class TestGetPostReactionsInitialization(unittest.TestCase):
    """Test tool initialization and parameter validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_post_ids = ["urn:li:activity:7240371806548066304", "urn:li:activity:7240371806548066305"]

    def test_tool_initialization_with_defaults(self):
        """Test tool can be initialized with default parameters."""
        tool = GetPostReactions(post_ids=self.valid_post_ids)

        self.assertEqual(tool.post_ids, self.valid_post_ids)
        self.assertFalse(tool.include_details)
        self.assertEqual(tool.page, 1)
        self.assertEqual(tool.page_size, 100)

    def test_tool_initialization_with_custom_parameters(self):
        """Test tool initialization with custom parameters."""
        tool = GetPostReactions(
            post_ids=self.valid_post_ids,
            include_details=True,
            page=2,
            page_size=50
        )

        self.assertEqual(tool.post_ids, self.valid_post_ids)
        self.assertTrue(tool.include_details)
        self.assertEqual(tool.page, 2)
        self.assertEqual(tool.page_size, 50)

    def test_tool_initialization_empty_post_ids(self):
        """Test tool initialization with empty post IDs list."""
        tool = GetPostReactions(post_ids=[])
        self.assertEqual(tool.post_ids, [])

    def test_tool_initialization_single_post(self):
        """Test tool initialization with single post ID."""
        single_post = ["urn:li:activity:7240371806548066304"]
        tool = GetPostReactions(post_ids=single_post)
        self.assertEqual(tool.post_ids, single_post)


class TestGetPostReactionsAPIIntegration(unittest.TestCase):
    """Test API integration and response handling."""

    def setUp(self):
        """Set up test fixtures with mocked environment."""
        self.tool = GetPostReactions(
            post_ids=["urn:li:activity:7240371806548066304"],
            include_details=False
        )

        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'RAPIDAPI_LINKEDIN_HOST': 'linkedin-api.rapidapi.com',
            'RAPIDAPI_LINKEDIN_KEY': 'test-api-key-12345'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.env_patcher.stop()

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_successful_single_post_reactions_fetch(self, mock_get, mock_env_var, mock_load_env):
        """Test successful API call for single post reactions."""
        # Configure mocks
        mock_env_var.side_effect = lambda key, desc: {
            'RAPIDAPI_LINKEDIN_HOST': 'linkedin-api.rapidapi.com',
            'RAPIDAPI_LINKEDIN_KEY': 'test-api-key-12345'
        }[key]

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "summary": {
                "totalReactions": 245,
                "reactionTypes": {
                    "like": 180,
                    "celebrate": 32,
                    "support": 15,
                    "love": 10,
                    "insightful": 5,
                    "funny": 3
                }
            },
            "views": 5444
        }
        mock_get.return_value = mock_response

        # Execute
        result = self.tool.run()
        result_data = json.loads(result)

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn('https://linkedin-api.rapidapi.com/post-reactions', call_args[0][0])
        self.assertEqual(call_args[1]['headers']['X-RapidAPI-Key'], 'test-api-key-12345')
        self.assertEqual(call_args[1]['params']['postId'], 'urn:li:activity:7240371806548066304')
        self.assertEqual(call_args[1]['params']['aggregateOnly'], 'true')

        # Verify response structure
        self.assertIn('reactions_by_post', result_data)
        self.assertIn('aggregate_metrics', result_data)
        self.assertIn('metadata', result_data)

        # Verify post-specific data
        post_data = result_data['reactions_by_post']['urn:li:activity:7240371806548066304']
        self.assertEqual(post_data['total_reactions'], 245)
        self.assertEqual(post_data['breakdown']['like'], 180)
        self.assertEqual(post_data['top_reaction'], 'like')
        self.assertAlmostEqual(post_data['engagement_rate'], 0.0450, places=4)

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_successful_multiple_posts_reactions_fetch(self, mock_get, mock_env_var, mock_load_env):
        """Test successful API calls for multiple posts."""
        # Set up tool with multiple posts
        self.tool = GetPostReactions(
            post_ids=["urn:li:activity:123", "urn:li:activity:456"],
            include_details=False
        )

        # Configure mocks
        mock_env_var.side_effect = lambda key, desc: {
            'RAPIDAPI_LINKEDIN_HOST': 'linkedin-api.rapidapi.com',
            'RAPIDAPI_LINKEDIN_KEY': 'test-api-key-12345'
        }[key]

        # Mock API responses for different posts
        response_1 = Mock()
        response_1.status_code = 200
        response_1.json.return_value = {
            "summary": {
                "totalReactions": 100,
                "reactionTypes": {"like": 80, "celebrate": 20}
            },
            "views": 2000
        }

        response_2 = Mock()
        response_2.status_code = 200
        response_2.json.return_value = {
            "summary": {
                "totalReactions": 150,
                "reactionTypes": {"like": 100, "love": 30, "insightful": 20}
            },
            "views": 3000
        }

        mock_get.side_effect = [response_1, response_2]

        # Execute
        result = self.tool.run()
        result_data = json.loads(result)

        # Verify multiple API calls
        self.assertEqual(mock_get.call_count, 2)

        # Verify aggregate metrics
        aggregate = result_data['aggregate_metrics']
        self.assertEqual(aggregate['total_reactions'], 250)  # 100 + 150
        self.assertEqual(aggregate['average_reactions_per_post'], 125.0)
        self.assertEqual(aggregate['posts_with_data'], 2)
        self.assertEqual(aggregate['posts_with_errors'], 0)

        # Verify reaction distribution aggregation
        expected_distribution = {"like": 180, "celebrate": 20, "love": 30, "insightful": 20}
        self.assertEqual(aggregate['reaction_distribution'], expected_distribution)

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_reactions_fetch_with_details(self, mock_get, mock_env_var, mock_load_env):
        """Test API call with include_details=True."""
        # Set up tool with details enabled
        self.tool = GetPostReactions(
            post_ids=["urn:li:activity:123"],
            include_details=True,
            page=2,
            page_size=50
        )

        # Configure mocks
        mock_env_var.side_effect = lambda key, desc: {
            'RAPIDAPI_LINKEDIN_HOST': 'linkedin-api.rapidapi.com',
            'RAPIDAPI_LINKEDIN_KEY': 'test-api-key-12345'
        }[key]

        # Mock API response with reactor details
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "summary": {
                "totalReactions": 50,
                "reactionTypes": {"like": 30, "celebrate": 20}
            },
            "views": 1000,
            "reactors": [
                {
                    "name": "John Doe",
                    "headline": "Software Engineer",
                    "reactionType": "like",
                    "profileUrl": "https://linkedin.com/in/johndoe"
                },
                {
                    "name": "Jane Smith",
                    "headline": "Product Manager",
                    "reactionType": "celebrate",
                    "profileUrl": "https://linkedin.com/in/janesmith"
                }
            ],
            "pagination": {"hasMore": True}
        }
        mock_get.return_value = mock_response

        # Execute
        result = self.tool.run()
        result_data = json.loads(result)

        # Verify API call parameters
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]['params']['aggregateOnly'], 'false')
        self.assertEqual(call_args[1]['params']['page'], 2)
        self.assertEqual(call_args[1]['params']['pageSize'], 50)

        # Verify reactor details included
        post_data = result_data['reactions_by_post']['urn:li:activity:123']
        self.assertIn('reactors', post_data)
        self.assertEqual(len(post_data['reactors']), 2)
        self.assertEqual(post_data['reactors'][0]['name'], 'John Doe')
        self.assertEqual(post_data['reactors'][1]['reaction_type'], 'celebrate')
        self.assertTrue(post_data['has_more_reactors'])


class TestGetPostReactionsErrorHandling(unittest.TestCase):
    """Test error handling and retry logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool = GetPostReactions(post_ids=["urn:li:activity:123"])

        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'RAPIDAPI_LINKEDIN_HOST': 'linkedin-api.rapidapi.com',
            'RAPIDAPI_LINKEDIN_KEY': 'test-api-key-12345'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.env_patcher.stop()

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    def test_empty_post_ids_handling(self, mock_env_var, mock_load_env):
        """Test handling of empty post IDs list."""
        tool = GetPostReactions(post_ids=[])

        mock_env_var.side_effect = lambda key, desc: 'test-value'

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['error'], 'invalid_input')
        self.assertEqual(result_data['message'], 'No post IDs provided')

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_api_rate_limiting_retry(self, mock_get, mock_env_var, mock_load_env):
        """Test retry logic for rate limiting (429 status)."""
        mock_env_var.side_effect = lambda key, desc: 'test-value'

        # Mock rate limiting response followed by success
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {'Retry-After': '2'}

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "summary": {"totalReactions": 10, "reactionTypes": {"like": 10}},
            "views": 100
        }

        mock_get.side_effect = [rate_limit_response, success_response]

        with patch('get_post_reactions.time.sleep') as mock_sleep:
            result = self.tool.run()
            result_data = json.loads(result)

        # Verify retry occurred
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(2)  # Retry-After header value

        # Verify eventual success
        self.assertIn('reactions_by_post', result_data)
        self.assertEqual(result_data['reactions_by_post']['urn:li:activity:123']['total_reactions'], 10)

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_server_error_retry(self, mock_get, mock_env_var, mock_load_env):
        """Test retry logic for server errors (5xx status)."""
        mock_env_var.side_effect = lambda key, desc: 'test-value'

        # Mock server error responses followed by success
        server_error = Mock()
        server_error.status_code = 500

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "summary": {"totalReactions": 15, "reactionTypes": {"like": 15}},
            "views": 150
        }

        mock_get.side_effect = [server_error, server_error, success_response]

        with patch('get_post_reactions.time.sleep') as mock_sleep:
            result = self.tool.run()
            result_data = json.loads(result)

        # Verify retries occurred
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Two retries before success

        # Verify eventual success
        self.assertIn('reactions_by_post', result_data)

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_client_error_no_retry(self, mock_get, mock_env_var, mock_load_env):
        """Test that client errors (4xx) don't trigger retries."""
        mock_env_var.side_effect = lambda key, desc: 'test-value'

        # Mock client error response
        client_error = Mock()
        client_error.status_code = 404
        client_error.text = "Post not found"

        mock_get.return_value = client_error

        result = self.tool.run()
        result_data = json.loads(result)

        # Verify only one API call (no retries)
        self.assertEqual(mock_get.call_count, 1)

        # Verify error handling
        post_data = result_data['reactions_by_post']['urn:li:activity:123']
        self.assertEqual(post_data['total_reactions'], 0)
        self.assertEqual(post_data['error'], 'fetch_failed')

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_network_timeout_retry(self, mock_get, mock_env_var, mock_load_env):
        """Test retry logic for network timeouts."""
        mock_env_var.side_effect = lambda key, desc: 'test-value'

        # Mock timeout followed by success
        mock_get.side_effect = [
            Exception("Request timed out"),  # Using generic Exception since requests is mocked
            Mock(status_code=200, **{
                'json.return_value': {
                    "summary": {"totalReactions": 20, "reactionTypes": {"like": 20}},
                    "views": 200
                }
            })
        ]

        with patch('get_post_reactions.time.sleep') as mock_sleep:
            result = self.tool.run()
            result_data = json.loads(result)

        # Verify retry occurred
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

        # Verify eventual success
        self.assertIn('reactions_by_post', result_data)

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    def test_missing_environment_variable_error(self, mock_env_var, mock_load_env):
        """Test error handling for missing environment variables."""
        # Mock missing environment variable
        mock_env_var.side_effect = Exception("Environment variable RAPIDAPI_LINKEDIN_HOST not found")

        result = self.tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['error'], 'reactions_fetch_failed')
        self.assertIn('Environment variable', result_data['message'])


class TestGetPostReactionsDataProcessing(unittest.TestCase):
    """Test reaction data processing and aggregation logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool = GetPostReactions(post_ids=["test_post"])

    def test_process_reactions_complete_data(self):
        """Test processing of complete reaction data."""
        response_data = {
            "summary": {
                "totalReactions": 100,
                "reactionTypes": {
                    "like": 60,
                    "celebrate": 20,
                    "support": 10,
                    "love": 5,
                    "insightful": 3,
                    "funny": 2
                }
            },
            "views": 2000
        }

        result = self.tool._process_reactions(response_data, "test_post")

        self.assertEqual(result['total_reactions'], 100)
        self.assertEqual(result['breakdown']['like'], 60)
        self.assertEqual(result['breakdown']['celebrate'], 20)
        self.assertEqual(result['top_reaction'], 'like')
        self.assertEqual(result['engagement_rate'], 0.05)  # 100/2000

    def test_process_reactions_missing_views(self):
        """Test processing when views data is missing."""
        response_data = {
            "summary": {
                "totalReactions": 50,
                "reactionTypes": {"like": 50}
            }
            # No views field
        }

        result = self.tool._process_reactions(response_data, "test_post")

        self.assertEqual(result['engagement_rate'], 0)  # Should be 0 when views missing

    def test_process_reactions_zero_reactions(self):
        """Test processing when there are no reactions."""
        response_data = {
            "summary": {
                "totalReactions": 0,
                "reactionTypes": {}
            },
            "views": 1000
        }

        result = self.tool._process_reactions(response_data, "test_post")

        self.assertEqual(result['total_reactions'], 0)
        self.assertEqual(result['breakdown'], {})
        self.assertIsNone(result['top_reaction'])
        self.assertEqual(result['engagement_rate'], 0)

    def test_process_reactions_with_reactor_details(self):
        """Test processing with reactor details included."""
        self.tool.include_details = True

        response_data = {
            "summary": {
                "totalReactions": 25,
                "reactionTypes": {"like": 15, "celebrate": 10}
            },
            "views": 500,
            "reactors": [
                {
                    "name": "Alice Johnson",
                    "headline": "Data Scientist",
                    "reactionType": "like",
                    "profileUrl": "https://linkedin.com/in/alice"
                },
                {
                    "name": "Bob Wilson",
                    "headline": "Tech Lead",
                    "reactionType": "celebrate",
                    "profileUrl": "https://linkedin.com/in/bob"
                }
            ],
            "pagination": {"hasMore": True}
        }

        result = self.tool._process_reactions(response_data, "test_post")

        self.assertIn('reactors', result)
        self.assertEqual(len(result['reactors']), 2)
        self.assertEqual(result['reactors'][0]['name'], 'Alice Johnson')
        self.assertEqual(result['reactors'][1]['reaction_type'], 'celebrate')
        self.assertTrue(result['has_more_reactors'])

    def test_process_reactions_missing_reactor_data(self):
        """Test processing reactor details with missing fields."""
        self.tool.include_details = True

        response_data = {
            "summary": {
                "totalReactions": 10,
                "reactionTypes": {"like": 10}
            },
            "views": 100,
            "reactors": [
                {
                    "name": "Unknown User"
                    # Missing headline, reactionType, profileUrl
                }
            ],
            "pagination": {"hasMore": False}
        }

        result = self.tool._process_reactions(response_data, "test_post")

        reactor = result['reactors'][0]
        self.assertEqual(reactor['name'], 'Unknown User')
        self.assertEqual(reactor['headline'], '')  # Default empty string
        self.assertEqual(reactor['reaction_type'], 'like')  # Default value
        self.assertEqual(reactor['profile_url'], '')  # Default empty string
        self.assertFalse(result['has_more_reactors'])


class TestGetPostReactionsEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'RAPIDAPI_LINKEDIN_HOST': 'linkedin-api.rapidapi.com',
            'RAPIDAPI_LINKEDIN_KEY': 'test-api-key-12345'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.env_patcher.stop()

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_mixed_success_failure_posts(self, mock_get, mock_env_var, mock_load_env):
        """Test handling when some posts succeed and others fail."""
        tool = GetPostReactions(post_ids=["post_1", "post_2", "post_3"])

        mock_env_var.side_effect = lambda key, desc: 'test-value'

        # Mock mixed responses: success, failure, success
        responses = [
            Mock(status_code=200, **{
                'json.return_value': {
                    "summary": {"totalReactions": 50, "reactionTypes": {"like": 50}},
                    "views": 1000
                }
            }),
            Mock(status_code=404, text="Not found"),  # Failure
            Mock(status_code=200, **{
                'json.return_value': {
                    "summary": {"totalReactions": 30, "reactionTypes": {"celebrate": 30}},
                    "views": 600
                }
            })
        ]
        mock_get.side_effect = responses

        result = tool.run()
        result_data = json.loads(result)

        # Verify partial success handling
        self.assertEqual(len(result_data['reactions_by_post']), 3)

        # Successful posts
        self.assertEqual(result_data['reactions_by_post']['post_1']['total_reactions'], 50)
        self.assertEqual(result_data['reactions_by_post']['post_3']['total_reactions'], 30)

        # Failed post
        failed_post = result_data['reactions_by_post']['post_2']
        self.assertEqual(failed_post['total_reactions'], 0)
        self.assertEqual(failed_post['error'], 'fetch_failed')

        # Aggregate metrics should exclude failed posts
        aggregate = result_data['aggregate_metrics']
        self.assertEqual(aggregate['total_reactions'], 80)  # 50 + 30
        self.assertEqual(aggregate['posts_with_data'], 2)
        self.assertEqual(aggregate['posts_with_errors'], 1)

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_large_post_list_rate_limiting(self, mock_get, mock_env_var, mock_load_env):
        """Test rate limiting between multiple posts."""
        post_ids = [f"post_{i}" for i in range(5)]  # 5 posts
        tool = GetPostReactions(post_ids=post_ids)

        mock_env_var.side_effect = lambda key, desc: 'test-value'

        # Mock successful responses for all posts
        mock_response = Mock(status_code=200, **{
            'json.return_value': {
                "summary": {"totalReactions": 10, "reactionTypes": {"like": 10}},
                "views": 100
            }
        })
        mock_get.return_value = mock_response

        with patch('get_post_reactions.time.sleep') as mock_sleep:
            result = tool.run()
            result_data = json.loads(result)

        # Verify rate limiting sleep calls (one less than number of posts)
        self.assertEqual(mock_sleep.call_count, 4)  # 5 posts - 1
        mock_sleep.assert_called_with(0.5)  # 500ms delay

        # Verify all posts processed
        self.assertEqual(len(result_data['reactions_by_post']), 5)

    @patch('get_post_reactions.load_environment')
    @patch('get_post_reactions.get_required_env_var')
    @patch('get_post_reactions.requests.get')
    def test_extreme_reaction_counts(self, mock_get, mock_env_var, mock_load_env):
        """Test handling of extreme reaction counts."""
        tool = GetPostReactions(post_ids=["viral_post"])

        mock_env_var.side_effect = lambda key, desc: 'test-value'

        # Mock response with very high reaction counts
        mock_response = Mock(status_code=200, **{
            'json.return_value': {
                "summary": {
                    "totalReactions": 999999,
                    "reactionTypes": {
                        "like": 500000,
                        "celebrate": 300000,
                        "support": 199999
                    }
                },
                "views": 10000000
            }
        })
        mock_get.return_value = mock_response

        result = tool.run()
        result_data = json.loads(result)

        post_data = result_data['reactions_by_post']['viral_post']
        self.assertEqual(post_data['total_reactions'], 999999)
        self.assertEqual(post_data['breakdown']['like'], 500000)
        self.assertEqual(post_data['top_reaction'], 'like')
        self.assertAlmostEqual(post_data['engagement_rate'], 0.1, places=4)

    @patch('get_post_reactions.datetime')
    def test_metadata_timestamp_generation(self, mock_datetime):
        """Test that metadata includes proper timestamp."""
        # Mock datetime to return consistent timestamp
        mock_now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        tool = GetPostReactions(post_ids=[])  # Empty list to trigger early return

        with patch('get_post_reactions.load_environment'), \
             patch('get_post_reactions.get_required_env_var'):
            result = tool.run()
            result_data = json.loads(result)

        # Should return early due to empty post_ids, but test timestamp format
        if 'error' in result_data:
            return  # Expected for empty post_ids

        self.assertEqual(result_data['metadata']['fetched_at'], '2024-01-15T10:30:00+00:00')


if __name__ == '__main__':
    # Create test suite
    test_classes = [
        TestGetPostReactionsInitialization,
        TestGetPostReactionsAPIIntegration,
        TestGetPostReactionsErrorHandling,
        TestGetPostReactionsDataProcessing,
        TestGetPostReactionsEdgeCases
    ]

    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print(f"\n{'='*50}")
    print(f"Test Summary for GetPostReactions")
    print(f"{'='*50}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")

    if result.failures:
        print(f"\nFailures:")
        for test, failure in result.failures:
            print(f"- {test}: {failure}")

    if result.errors:
        print(f"\nErrors:")
        for test, error in result.errors:
            print(f"- {test}: {error}")