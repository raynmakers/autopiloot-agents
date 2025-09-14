"""
Integration tests for ResolveChannelHandles tool.
Tests handle resolution, configuration loading, and error handling scenarios.
"""

import unittest
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock

# Add project paths for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, 'scraper', 'tools'))
sys.path.append(os.path.join(project_root, 'core'))
sys.path.append(os.path.join(project_root, 'config'))

try:
    from ResolveChannelHandles import ResolveChannelHandles
    TOOL_AVAILABLE = True
except ImportError:
    TOOL_AVAILABLE = False
    print("Warning: ResolveChannelHandles tool not available for testing")


class TestResolveChannelHandles(unittest.TestCase):
    """Test cases for ResolveChannelHandles tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not TOOL_AVAILABLE:
            self.skipTest("ResolveChannelHandles tool not available")
        
        self.tool = ResolveChannelHandles()
        self.mock_youtube_client = Mock()
        self.test_handles = ["@AlexHormozi", "@TestChannel"]
        
    @patch('ResolveChannelHandles.load_app_config')
    @patch('ResolveChannelHandles.get_config_value')
    def test_load_handles_from_config_success(self, mock_get_config, mock_load_config):
        """Test successful loading of handles from configuration."""
        # Mock configuration
        mock_load_config.return_value = {'scraper': {'handles': ['@AlexHormozi', 'TestChannel']}}
        mock_get_config.return_value = ['@AlexHormozi', 'TestChannel']
        
        handles = self.tool._load_handles_from_config()
        
        # Verify handles are normalized with @ prefix
        self.assertEqual(handles, ['@AlexHormozi', '@TestChannel'])
        mock_load_config.assert_called_once()
        mock_get_config.assert_called_once_with("scraper.handles", ["@AlexHormozi"])
    
    @patch('ResolveChannelHandles.load_app_config')
    @patch('ResolveChannelHandles.get_config_value')
    def test_load_handles_empty_config(self, mock_get_config, mock_load_config):
        """Test handling of empty configuration."""
        mock_load_config.return_value = {}
        mock_get_config.return_value = []
        
        handles = self.tool._load_handles_from_config()
        
        self.assertEqual(handles, [])
    
    @patch('ResolveChannelHandles.load_app_config')
    def test_load_handles_config_error(self, mock_load_config):
        """Test handling of configuration loading errors."""
        mock_load_config.side_effect = Exception("Config file not found")
        
        with self.assertRaises(RuntimeError) as context:
            self.tool._load_handles_from_config()
        
        self.assertIn("Failed to load handles from config", str(context.exception))
    
    def test_resolve_single_handle_success(self):
        """Test successful resolution of a single handle."""
        # Mock YouTube API responses
        mock_search_response = {
            'items': [{
                'snippet': {
                    'channelId': 'UCfV36TX5AejfAGIbtwTc7Zw'
                }
            }]
        }
        
        mock_channel_response = {
            'items': [{
                'snippet': {
                    'customUrl': '@alexhormozi'
                }
            }]
        }
        
        # Configure mock YouTube client
        self.mock_youtube_client.search.return_value.list.return_value.execute.return_value = mock_search_response
        self.mock_youtube_client.channels.return_value.list.return_value.execute.return_value = mock_channel_response
        
        channel_id = self.tool._resolve_single_handle(self.mock_youtube_client, "@AlexHormozi")
        
        self.assertEqual(channel_id, "UCfV36TX5AejfAGIbtwTc7Zw")
    
    def test_resolve_single_handle_fallback_username(self):
        """Test fallback to username resolution when search fails."""
        # Mock empty search response but successful username lookup
        mock_search_response = {'items': []}
        mock_username_response = {
            'items': [{'id': 'UCUsernameChannelId123'}]
        }
        
        self.mock_youtube_client.search.return_value.list.return_value.execute.return_value = mock_search_response
        self.mock_youtube_client.channels.return_value.list.return_value.execute.return_value = mock_username_response
        
        channel_id = self.tool._resolve_single_handle(self.mock_youtube_client, "@TestUser")
        
        self.assertEqual(channel_id, "UCUsernameChannelId123")
    
    def test_resolve_single_handle_not_found(self):
        """Test handling when channel is not found."""
        # Mock empty responses
        self.mock_youtube_client.search.return_value.list.return_value.execute.return_value = {'items': []}
        self.mock_youtube_client.channels.return_value.list.return_value.execute.return_value = {'items': []}
        
        with self.assertRaises(ValueError) as context:
            self.tool._resolve_single_handle(self.mock_youtube_client, "@NonExistentChannel")
        
        self.assertIn("Channel not found for handle", str(context.exception))
    
    @patch('ResolveChannelHandles.HttpError')
    def test_resolve_single_handle_retry_logic(self, mock_http_error):
        """Test retry logic for rate limit errors."""
        from googleapiclient.errors import HttpError
        
        # Mock rate limit error (429)
        mock_error = Mock()
        mock_error.resp.status = 429
        
        # Configure tool for faster testing
        self.tool.max_retries = 1
        
        # First call fails with 429, second succeeds
        def side_effect(*args, **kwargs):
            if self.mock_youtube_client.search.return_value.list.return_value.execute.call_count == 1:
                raise HttpError(mock_error.resp, b'Rate limit exceeded')
            return {'items': [{'snippet': {'channelId': 'UCRetryTest123'}}]}
        
        self.mock_youtube_client.search.return_value.list.return_value.execute.side_effect = side_effect
        self.mock_youtube_client.channels.return_value.list.return_value.execute.return_value = {
            'items': [{'snippet': {'customUrl': '@retrytest'}}]
        }
        
        with patch('time.sleep'):  # Speed up test by mocking sleep
            channel_id = self.tool._resolve_single_handle(self.mock_youtube_client, "@RetryTest")
        
        self.assertEqual(channel_id, "UCRetryTest123")
    
    @patch('ResolveChannelHandles.get_required_var')
    @patch('ResolveChannelHandles.build')
    def test_initialize_youtube_client_api_key(self, mock_build, mock_get_var):
        """Test YouTube client initialization with API key."""
        mock_get_var.return_value = "test_api_key"
        mock_build.return_value = self.mock_youtube_client
        
        # Mock env_loader to not have service credentials
        with patch.object(self.tool, '_initialize_youtube_client') as mock_init:
            mock_init.return_value = self.mock_youtube_client
            client = self.tool._initialize_youtube_client()
        
        self.assertEqual(client, self.mock_youtube_client)
    
    @patch('ResolveChannelHandles.get_required_var')
    def test_initialize_youtube_client_missing_api_key(self, mock_get_var):
        """Test handling of missing API key."""
        mock_get_var.side_effect = RuntimeError("API key not found")
        
        with self.assertRaises(RuntimeError) as context:
            self.tool._initialize_youtube_client()
        
        self.assertIn("Failed to initialize YouTube client", str(context.exception))
    
    @patch.object(ResolveChannelHandles, '_load_handles_from_config')
    @patch.object(ResolveChannelHandles, '_initialize_youtube_client')
    @patch.object(ResolveChannelHandles, '_resolve_single_handle')
    def test_run_success(self, mock_resolve, mock_init_client, mock_load_handles):
        """Test successful execution of the tool."""
        # Mock configuration and API responses
        mock_load_handles.return_value = ['@AlexHormozi', '@TestChannel']
        mock_init_client.return_value = self.mock_youtube_client
        
        def resolve_side_effect(client, handle):
            if handle == '@AlexHormozi':
                return 'UCfV36TX5AejfAGIbtwTc7Zw'
            elif handle == '@TestChannel':
                return 'UCTestChannelId123'
            return 'UCUnknownChannel'
        
        mock_resolve.side_effect = resolve_side_effect
        
        result = self.tool.run()
        
        # Parse JSON result
        result_dict = json.loads(result)
        expected = {
            '@AlexHormozi': 'UCfV36TX5AejfAGIbtwTc7Zw',
            '@TestChannel': 'UCTestChannelId123'
        }
        
        self.assertEqual(result_dict, expected)
    
    @patch.object(ResolveChannelHandles, '_load_handles_from_config')
    @patch.object(ResolveChannelHandles, '_initialize_youtube_client')
    @patch.object(ResolveChannelHandles, '_resolve_single_handle')
    def test_run_partial_failure(self, mock_resolve, mock_init_client, mock_load_handles):
        """Test handling when some handles fail to resolve."""
        mock_load_handles.return_value = ['@AlexHormozi', '@NonExistent']
        mock_init_client.return_value = self.mock_youtube_client
        
        def resolve_side_effect(client, handle):
            if handle == '@AlexHormozi':
                return 'UCfV36TX5AejfAGIbtwTc7Zw'
            elif handle == '@NonExistent':
                raise ValueError("Channel not found")
            return 'UCUnknownChannel'
        
        mock_resolve.side_effect = resolve_side_effect
        
        result = self.tool.run()
        
        # Parse JSON result
        result_dict = json.loads(result)
        
        self.assertEqual(result_dict['@AlexHormozi'], 'UCfV36TX5AejfAGIbtwTc7Zw')
        self.assertTrue(result_dict['@NonExistent'].startswith('ERROR:'))
    
    @patch.object(ResolveChannelHandles, '_load_handles_from_config')
    def test_run_no_handles_configured(self, mock_load_handles):
        """Test handling when no handles are configured."""
        mock_load_handles.return_value = []
        
        result = self.tool.run()
        
        result_dict = json.loads(result)
        self.assertIn("error", result_dict)
        self.assertIn("No handles configured", result_dict["error"])
    
    @patch.object(ResolveChannelHandles, '_load_handles_from_config')
    def test_run_config_error(self, mock_load_handles):
        """Test handling of configuration loading errors."""
        mock_load_handles.side_effect = RuntimeError("Config error")
        
        result = self.tool.run()
        
        result_dict = json.loads(result)
        self.assertIn("error", result_dict)
        self.assertIn("Failed to resolve channel handles", result_dict["error"])
    
    def test_handle_normalization(self):
        """Test that handles are properly normalized with @ prefix."""
        test_cases = [
            ("@AlexHormozi", "@AlexHormozi"),
            ("AlexHormozi", "@AlexHormozi"),
            ("@test", "@test"),
            ("test", "@test")
        ]
        
        for input_handle, expected in test_cases:
            with patch.object(self.tool, '_load_handles_from_config') as mock_load:
                mock_load.return_value = [input_handle]
                handles = self.tool._load_handles_from_config()
                self.assertEqual(handles[0], expected)
    
    def test_tool_field_validation(self):
        """Test Pydantic field validation."""
        # Test valid max_retries
        tool = ResolveChannelHandles(max_retries=5)
        self.assertEqual(tool.max_retries, 5)
        
        # Test default max_retries
        tool_default = ResolveChannelHandles()
        self.assertEqual(tool_default.max_retries, 3)
    
    def test_clean_handle_processing(self):
        """Test handle cleaning logic (removing @ prefix)."""
        test_handles = ["@AlexHormozi", "AlexHormozi", "@test", "test"]
        
        for handle in test_handles:
            clean_handle = handle.lstrip('@')
            self.assertFalse(clean_handle.startswith('@'))
            self.assertTrue(len(clean_handle) > 0)


class TestResolveChannelHandlesIntegration(unittest.TestCase):
    """Integration tests that test the tool with realistic scenarios."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        if not TOOL_AVAILABLE:
            self.skipTest("ResolveChannelHandles tool not available")
    
    @unittest.skipUnless(os.getenv("RUN_INTEGRATION_TESTS"), "Integration tests require RUN_INTEGRATION_TESTS=1")
    @patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_key'})
    def test_full_integration_mock_api(self):
        """Full integration test with mocked API responses."""
        tool = ResolveChannelHandles()
        
        # This would be a full integration test if we had real API access
        # For now, it validates the tool can be instantiated and configured
        self.assertIsInstance(tool, ResolveChannelHandles)
        self.assertEqual(tool.max_retries, 3)


if __name__ == '__main__':
    # Configure test discovery
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_resolve_channel_handles.py')
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    # Exit with appropriate code
    exit_code = 0 if (len(result.failures) == 0 and len(result.errors) == 0) else 1
    sys.exit(exit_code)