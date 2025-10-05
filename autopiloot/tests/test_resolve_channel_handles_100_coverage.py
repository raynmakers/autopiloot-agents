"""
Comprehensive test suite for ResolveChannelHandles tool targeting 100% coverage.
Tests YouTube channel handle resolution, retry logic, and API error handling.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import sys


# Mock external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.errors': MagicMock(),
    'google': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
    'env_loader': MagicMock(),
    'loader': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create mocks for functions
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value="fake_key")
sys.modules['loader'].load_app_config = MagicMock(return_value={"scraper": {"handles": ["@TestChannel"]}})
sys.modules['loader'].get_config_value = MagicMock(return_value=["@TestChannel"])

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Mock HttpError
class MockHttpError(Exception):
    def __init__(self, resp, content):
        self.resp = resp
        self.content = content
        super().__init__()

sys.modules['googleapiclient.errors'].HttpError = MockHttpError

# Import the tool after mocking
from scraper_agent.tools.resolve_channel_handles import ResolveChannelHandles

# Patch ResolveChannelHandles __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.max_retries = kwargs.get('max_retries', 3)

ResolveChannelHandles.__init__ = patched_init


class TestResolveChannelHandles100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for ResolveChannelHandles."""

    @patch('scraper_agent.tools.resolve_channel_handles.build')
    @patch('scraper_agent.tools.resolve_channel_handles.get_config_value')
    @patch('scraper_agent.tools.resolve_channel_handles.load_app_config')
    def test_successful_handle_resolution(self, mock_config, mock_get_config, mock_build):
        """Test successful channel handle resolution (lines 46-68)."""
        mock_config.return_value = {"scraper": {"handles": ["@TestChannel"]}}
        mock_get_config.return_value = ["@TestChannel"]

        # Mock YouTube API client
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        # Mock search response
        mock_youtube.search().list().execute.return_value = {
            'items': [{
                'snippet': {'channelId': 'UC123456'}
            }]
        }

        # Mock channel details response
        mock_youtube.channels().list().execute.return_value = {
            'items': [{
                'snippet': {
                    'customUrl': '@testchannel'
                }
            }]
        }

        tool = ResolveChannelHandles()
        result = tool.run()
        data = json.loads(result)

        self.assertIn('@TestChannel', data)
        self.assertEqual(data['@TestChannel'], 'UC123456')

    @patch('scraper_agent.tools.resolve_channel_handles.get_config_value')
    @patch('scraper_agent.tools.resolve_channel_handles.load_app_config')
    def test_no_handles_configured(self, mock_config, mock_get_config):
        """Test error when no handles configured (lines 50-51)."""
        mock_config.return_value = {"scraper": {"handles": []}}
        mock_get_config.return_value = []

        tool = ResolveChannelHandles()
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('No handles configured', data['error'])

    @patch('scraper_agent.tools.resolve_channel_handles.build')
    @patch('scraper_agent.tools.resolve_channel_handles.get_config_value')
    @patch('scraper_agent.tools.resolve_channel_handles.load_app_config')
    def test_handle_resolution_failure_continues(self, mock_config, mock_get_config, mock_build):
        """Test that failure on one handle doesn't stop others (lines 62-64)."""
        mock_config.return_value = {"scraper": {"handles": ["@Good", "@Bad"]}}
        mock_get_config.return_value = ["@Good", "@Bad"]

        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        # First handle succeeds, second fails
        def mock_search(*args, **kwargs):
            query = kwargs.get('q', '')
            if '@good' in query.lower():
                return MagicMock(execute=lambda: {'items': [{'snippet': {'channelId': 'UC_GOOD'}}]})
            else:
                raise Exception("API error")

        mock_youtube.search().list.side_effect = mock_search

        mock_youtube.channels().list().execute.return_value = {
            'items': [{'snippet': {'customUrl': '@good'}}]
        }

        tool = ResolveChannelHandles()
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['@Good'], 'UC_GOOD')
        self.assertIn('ERROR', data['@Bad'])

    @patch('scraper_agent.tools.resolve_channel_handles.load_app_config')
    def test_top_level_exception_handling(self, mock_config):
        """Test top-level exception handling (lines 70-71)."""
        mock_config.side_effect = Exception("Config error")

        tool = ResolveChannelHandles()
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('Failed to resolve channel handles', data['error'])

    @patch('scraper_agent.tools.resolve_channel_handles.get_config_value')
    @patch('scraper_agent.tools.resolve_channel_handles.load_app_config')
    def test_handle_normalization(self, mock_config, mock_get_config):
        """Test handle normalization adds @ prefix (lines 80-84)."""
        mock_config.return_value = {"scraper": {"handles": ["TestChannel", "@AlreadyPrefixed"]}}
        mock_get_config.return_value = ["TestChannel", "@AlreadyPrefixed"]

        tool = ResolveChannelHandles()
        handles = tool._load_handles_from_config()

        self.assertEqual(handles, ["@TestChannel", "@AlreadyPrefixed"])

    @patch('scraper_agent.tools.resolve_channel_handles.get_config_value')
    @patch('scraper_agent.tools.resolve_channel_handles.load_app_config')
    def test_load_handles_exception(self, mock_config, mock_get_config):
        """Test load handles exception handling (lines 88-89)."""
        mock_config.side_effect = Exception("Config load error")

        tool = ResolveChannelHandles()

        with self.assertRaises(RuntimeError) as context:
            tool._load_handles_from_config()
        self.assertIn('Failed to load handles from config', str(context.exception))

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_single_handle_search_match(self, mock_time):
        """Test successful handle resolution via search (lines 111-138)."""
        mock_youtube = MagicMock()

        # Mock search response
        mock_youtube.search().list().execute.return_value = {
            'items': [{
                'snippet': {'channelId': 'UC123'}
            }]
        }

        # Mock channel details with custom URL
        mock_youtube.channels().list().execute.return_value = {
            'items': [{
                'snippet': {'customUrl': '@testchannel'}
            }]
        }

        tool = ResolveChannelHandles()
        channel_id = tool._resolve_single_handle(mock_youtube, '@TestChannel')

        self.assertEqual(channel_id, 'UC123')

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_single_handle_fallback_username(self, mock_time):
        """Test fallback to forUsername (lines 141-147)."""
        mock_youtube = MagicMock()

        # Mock empty search response
        mock_youtube.search().list().execute.return_value = {'items': []}

        # Mock successful username lookup
        mock_youtube.channels().list().execute.return_value = {
            'items': [{'id': 'UC_FROM_USERNAME'}]
        }

        tool = ResolveChannelHandles()
        channel_id = tool._resolve_single_handle(mock_youtube, '@OldChannel')

        self.assertEqual(channel_id, 'UC_FROM_USERNAME')

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_single_handle_not_found(self, mock_time):
        """Test handle not found after max retries (lines 150-151)."""
        mock_youtube = MagicMock()

        # Mock empty responses
        mock_youtube.search().list().execute.return_value = {'items': []}
        mock_youtube.channels().list().execute.return_value = {'items': []}

        tool = ResolveChannelHandles(max_retries=0)

        with self.assertRaises(ValueError) as context:
            tool._resolve_single_handle(mock_youtube, '@NotFound')
        self.assertIn('Channel not found', str(context.exception))

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_http_error_retryable(self, mock_time):
        """Test retryable HTTP errors (429, 500) (lines 157-162)."""
        mock_youtube = MagicMock()

        # First call raises 429, second succeeds
        call_count = [0]
        def mock_search(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise MockHttpError(Mock(status=429), b'Rate limit')
            return {'items': [{'snippet': {'channelId': 'UC_RETRY_SUCCESS'}}]}

        mock_youtube.search().list().execute.side_effect = mock_search

        mock_youtube.channels().list().execute.return_value = {
            'items': [{'snippet': {'customUrl': '@test'}}]
        }

        tool = ResolveChannelHandles(max_retries=3)
        channel_id = tool._resolve_single_handle(mock_youtube, '@Test')

        self.assertEqual(channel_id, 'UC_RETRY_SUCCESS')
        mock_time.sleep.assert_called()  # Verify backoff was used

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_http_error_max_retries_exceeded(self, mock_time):
        """Test HTTP error after max retries (lines 163-164)."""
        mock_youtube = MagicMock()

        # Always raise 429
        mock_youtube.search().list().execute.side_effect = MockHttpError(Mock(status=429), b'Rate limit')

        tool = ResolveChannelHandles(max_retries=2)

        with self.assertRaises(RuntimeError) as context:
            tool._resolve_single_handle(mock_youtube, '@Test')
        self.assertIn('API error after', str(context.exception))

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_http_error_non_retryable(self, mock_time):
        """Test non-retryable HTTP errors (lines 166-167)."""
        mock_youtube = MagicMock()

        # Raise 403 (non-retryable)
        mock_youtube.search().list().execute.side_effect = MockHttpError(Mock(status=403), b'Forbidden')

        tool = ResolveChannelHandles()

        with self.assertRaises(RuntimeError) as context:
            tool._resolve_single_handle(mock_youtube, '@Test')
        self.assertIn('YouTube API error', str(context.exception))

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_general_exception_with_retry(self, mock_time):
        """Test general exception with retry (lines 169-172)."""
        mock_youtube = MagicMock()

        # First call raises exception, second succeeds
        call_count = [0]
        def mock_search(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Transient error")
            return {'items': [{'snippet': {'channelId': 'UC_RECOVERED'}}]}

        mock_youtube.search().list().execute.side_effect = mock_search
        mock_youtube.channels().list().execute.return_value = {
            'items': [{'snippet': {'customUrl': '@test'}}]
        }

        tool = ResolveChannelHandles(max_retries=2)
        channel_id = tool._resolve_single_handle(mock_youtube, '@Test')

        self.assertEqual(channel_id, 'UC_RECOVERED')

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_general_exception_max_retries(self, mock_time):
        """Test general exception after max retries (lines 173-174)."""
        mock_youtube = MagicMock()

        mock_youtube.search().list().execute.side_effect = Exception("Persistent error")

        tool = ResolveChannelHandles(max_retries=1)

        with self.assertRaises(RuntimeError) as context:
            tool._resolve_single_handle(mock_youtube, '@Test')
        self.assertIn('Failed to resolve', str(context.exception))

    @patch('scraper_agent.tools.resolve_channel_handles.os.path.exists')
    @patch('scraper_agent.tools.resolve_channel_handles.service_account')
    @patch('scraper_agent.tools.resolve_channel_handles.build')
    def test_initialize_youtube_with_service_account(self, mock_build, mock_sa, mock_exists):
        """Test YouTube client initialization with service account (lines 186-192)."""
        mock_exists.return_value = True
        mock_credentials = MagicMock()
        mock_sa.Credentials.from_service_account_file.return_value = mock_credentials
        mock_build.return_value = MagicMock()

        tool = ResolveChannelHandles()
        client = tool._initialize_youtube_client()

        self.assertIsNotNone(client)
        mock_build.assert_called_with('youtube', 'v3', credentials=mock_credentials)

    @patch('scraper_agent.tools.resolve_channel_handles.os.path.exists')
    @patch('scraper_agent.tools.resolve_channel_handles.build')
    def test_initialize_youtube_with_api_key_fallback(self, mock_build, mock_exists):
        """Test YouTube client initialization with API key fallback (lines 193-197)."""
        mock_exists.return_value = False
        mock_build.return_value = MagicMock()

        tool = ResolveChannelHandles()
        client = tool._initialize_youtube_client()

        self.assertIsNotNone(client)
        mock_build.assert_called_with('youtube', 'v3', developerKey="fake_key")

    @patch('scraper_agent.tools.resolve_channel_handles.get_required_env_var')
    def test_initialize_youtube_exception(self, mock_env):
        """Test YouTube client initialization exception (lines 199-200)."""
        mock_env.side_effect = Exception("Missing API key")

        tool = ResolveChannelHandles()

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_youtube_client()
        self.assertIn('Failed to initialize YouTube client', str(context.exception))

    @patch('scraper_agent.tools.resolve_channel_handles.time')
    def test_resolve_last_attempt_best_match(self, mock_time):
        """Test taking best match on last attempt (lines 137-138)."""
        mock_youtube = MagicMock()

        # Return result without exact match
        mock_youtube.search().list().execute.return_value = {
            'items': [{'snippet': {'channelId': 'UC_BEST_MATCH'}}]
        }

        # Channel details without matching customUrl
        mock_youtube.channels().list().execute.return_value = {
            'items': [{'snippet': {}}]  # No customUrl
        }

        tool = ResolveChannelHandles(max_retries=0)  # Only one attempt
        channel_id = tool._resolve_single_handle(mock_youtube, '@Test')

        self.assertEqual(channel_id, 'UC_BEST_MATCH')


if __name__ == "__main__":
    unittest.main()