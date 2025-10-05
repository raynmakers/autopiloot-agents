"""
Comprehensive test suite for ListRecentUploads tool targeting 100% coverage.
Tests YouTube uploads playlist fetching, checkpoint management, and quota handling.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import sys
from datetime import datetime, timezone, timedelta


# Mock external dependencies before imports
mock_env_loader = MagicMock()
mock_env_loader.get_service_credentials = MagicMock(return_value=None)

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
    'firebase_admin': MagicMock(),
    'firebase_admin.firestore': MagicMock(),
    'env_loader': mock_env_loader,
    'loader': MagicMock(),
    'reliability': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create mocks for functions
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value="fake_key")
sys.modules['env_loader'].env_loader = mock_env_loader
sys.modules['loader'].get_config_value = MagicMock(return_value=None)

# Create QuotaManager mock
class MockQuotaManager:
    def is_service_available(self, service):
        return True
    def record_request(self, service, count):
        pass
    def mark_quota_exhausted(self, service):
        pass
    def get_quota_status(self, service):
        return {'reset_time': '2025-01-28T00:00:00Z'}

sys.modules['reliability'].QuotaManager = MockQuotaManager

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
from scraper_agent.tools.list_recent_uploads import ListRecentUploads

# Patch ListRecentUploads __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.channel_id = kwargs.get('channel_id')
    self.since_utc = kwargs.get('since_utc')
    self.until_utc = kwargs.get('until_utc')
    self.page_size = kwargs.get('page_size', 50)
    self.use_checkpoint = kwargs.get('use_checkpoint', True)

ListRecentUploads.__init__ = patched_init


class TestListRecentUploads100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for ListRecentUploads."""

    def setUp(self):
        """Set up test fixtures."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        self.channel_id = "UCfV36TX5AejfAGIbtwTc7Zw"
        self.since_utc = yesterday.isoformat()
        self.until_utc = now.isoformat()

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_successful_fetch_with_videos(self, mock_build, mock_env, mock_quota):
        """Test successful video fetching (lines 79-132)."""
        # Mock YouTube API client
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_env.return_value = "fake_api_key"

        # Mock quota manager
        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        # Mock channel response
        mock_youtube.channels().list().execute.return_value = {
            'items': [{
                'contentDetails': {
                    'relatedPlaylists': {
                        'uploads': 'UUfV36TX5AejfAGIbtwTc7Zw'
                    }
                }
            }]
        }

        # Mock playlist response
        mock_youtube.playlistItems().list().execute.return_value = {
            'items': [{
                'snippet': {
                    'resourceId': {'videoId': 'vid123'},
                    'title': 'Test Video',
                    'publishedAt': self.until_utc,
                    'channelTitle': 'Test Channel'
                }
            }],
            'nextPageToken': None
        }

        # Mock video details response
        mock_youtube.videos().list().execute.return_value = {
            'items': [{
                'id': 'vid123',
                'snippet': {
                    'title': 'Test Video',
                    'publishedAt': self.until_utc
                },
                'contentDetails': {
                    'duration': 'PT10M30S'
                }
            }]
        }

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc,
            page_size=10,
            use_checkpoint=False
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('items', data)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['video_id'], 'vid123')
        self.assertEqual(data['items'][0]['duration_sec'], 630)

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_quota_exhausted(self, mock_build, mock_env, mock_quota):
        """Test quota exhausted handling (lines 85-90)."""
        mock_build.return_value = MagicMock()
        mock_env.return_value = "fake_api_key"

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = False
        mock_quota_inst.get_quota_status.return_value = {'reset_time': '2025-01-28T00:00:00Z'}
        mock_quota.return_value = mock_quota_inst

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('quota exhausted', data['error'])
        self.assertEqual(data['items'], [])

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_uploads_playlist_not_found(self, mock_build, mock_env, mock_quota):
        """Test handling when uploads playlist not found (lines 95-96)."""
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_env.return_value = "fake_api_key"

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        # Mock empty channel response
        mock_youtube.channels().list().execute.return_value = {'items': []}

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('uploads playlist', data['error'])

    @patch('scraper_agent.tools.list_recent_uploads.FIREBASE_AVAILABLE', True)
    @patch('scraper_agent.tools.list_recent_uploads.firestore')
    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_checkpoint_loading(self, mock_build, mock_env, mock_quota, mock_firestore):
        """Test checkpoint loading and saving (lines 99-120)."""
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_env.return_value = "fake_api_key"

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        # Mock Firestore
        mock_db = MagicMock()
        mock_firestore.client.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'last_published_at': self.since_utc}
        mock_db.collection().document().get.return_value = mock_doc

        # Mock channel response
        mock_youtube.channels().list().execute.return_value = {
            'items': [{
                'contentDetails': {
                    'relatedPlaylists': {
                        'uploads': 'UU123'
                    }
                }
            }]
        }

        # Mock playlist response with new video
        new_video_time = (datetime.fromisoformat(self.since_utc.replace('Z', '+00:00')) + timedelta(hours=1)).isoformat()
        mock_youtube.playlistItems().list().execute.return_value = {
            'items': [{
                'snippet': {
                    'resourceId': {'videoId': 'new_vid'},
                    'title': 'New Video',
                    'publishedAt': new_video_time,
                    'channelTitle': 'Test Channel'
                }
            }],
            'nextPageToken': None
        }

        # Mock video details
        mock_youtube.videos().list().execute.return_value = {
            'items': [{
                'id': 'new_vid',
                'snippet': {
                    'title': 'New Video',
                    'publishedAt': new_video_time
                },
                'contentDetails': {
                    'duration': 'PT5M'
                }
            }]
        }

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc,
            use_checkpoint=True
        )

        result = tool.run()
        data = json.loads(result)

        self.assertTrue(data['checkpoint_updated'])
        self.assertEqual(len(data['items']), 1)

    def test_parse_duration_full(self):
        """Test duration parsing with hours, minutes, seconds (lines 296-306)."""
        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        # Full format
        duration_sec = tool._parse_duration('PT1H30M45S')
        self.assertEqual(duration_sec, 5445)

        # Only minutes and seconds
        duration_sec = tool._parse_duration('PT10M30S')
        self.assertEqual(duration_sec, 630)

        # Only seconds
        duration_sec = tool._parse_duration('PT45S')
        self.assertEqual(duration_sec, 45)

        # Invalid format
        duration_sec = tool._parse_duration('invalid')
        self.assertEqual(duration_sec, 0)

    @patch('scraper_agent.tools.list_recent_uploads.FIREBASE_AVAILABLE', False)
    def test_checkpoint_firebase_unavailable(self):
        """Test checkpoint operations when Firebase unavailable (lines 310-311, 330-331)."""
        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        # Should return None when Firebase unavailable
        checkpoint = tool._load_checkpoint(self.channel_id)
        self.assertIsNone(checkpoint)

        # Should not raise error when saving
        tool._save_checkpoint(self.channel_id, self.until_utc)

    @patch('scraper_agent.tools.list_recent_uploads.FIREBASE_AVAILABLE', True)
    @patch('scraper_agent.tools.list_recent_uploads.firestore')
    def test_checkpoint_loading_no_doc(self, mock_firestore):
        """Test checkpoint loading when document doesn't exist (lines 318-322)."""
        mock_db = MagicMock()
        mock_firestore.client.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection().document().get.return_value = mock_doc

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        checkpoint = tool._load_checkpoint(self.channel_id)
        self.assertIsNone(checkpoint)

    @patch('scraper_agent.tools.list_recent_uploads.FIREBASE_AVAILABLE', True)
    @patch('scraper_agent.tools.list_recent_uploads.firestore')
    def test_checkpoint_loading_exception(self, mock_firestore):
        """Test checkpoint loading exception handling (lines 324-326)."""
        mock_firestore.client.side_effect = Exception("Firestore error")

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        # Should return None on exception, not raise
        checkpoint = tool._load_checkpoint(self.channel_id)
        self.assertIsNone(checkpoint)

    @patch('scraper_agent.tools.list_recent_uploads.FIREBASE_AVAILABLE', True)
    @patch('scraper_agent.tools.list_recent_uploads.firestore')
    def test_checkpoint_saving_exception(self, mock_firestore):
        """Test checkpoint saving exception handling (lines 343-345)."""
        mock_firestore.client.side_effect = Exception("Firestore error")

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        # Should not raise exception
        tool._save_checkpoint(self.channel_id, self.until_utc)

    @patch('scraper_agent.tools.list_recent_uploads.os.path.exists')
    @patch('scraper_agent.tools.list_recent_uploads.env_loader')
    @patch('scraper_agent.tools.list_recent_uploads.service_account')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_initialize_youtube_with_service_account(self, mock_build, mock_env, mock_sa, mock_env_loader, mock_exists):
        """Test YouTube client initialization with service account (lines 354-361)."""
        mock_env.return_value = "fake_api_key"
        mock_env_loader.get_service_credentials.return_value = "/path/to/creds.json"
        mock_exists.return_value = True
        mock_credentials = MagicMock()
        mock_sa.Credentials.from_service_account_file.return_value = mock_credentials
        mock_build.return_value = MagicMock()

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        client = tool._initialize_youtube_client()
        self.assertIsNotNone(client)
        mock_build.assert_called_with('youtube', 'v3', credentials=mock_credentials)

    @patch('scraper_agent.tools.list_recent_uploads.env_loader')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_initialize_youtube_with_api_key(self, mock_build, mock_env, mock_env_loader):
        """Test YouTube client initialization with API key fallback (lines 362-366)."""
        mock_env.return_value = "fake_api_key"
        mock_env_loader.get_service_credentials.side_effect = Exception("No service account")
        mock_build.return_value = MagicMock()

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        client = tool._initialize_youtube_client()
        self.assertIsNotNone(client)
        mock_build.assert_called_with('youtube', 'v3', developerKey="fake_api_key")

    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    def test_initialize_youtube_exception(self, mock_env):
        """Test YouTube client initialization exception (lines 368-369)."""
        mock_env.side_effect = Exception("Missing API key")

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_youtube_client()
        self.assertIn("Failed to initialize YouTube client", str(context.exception))

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_get_uploads_playlist_exception(self, mock_build, mock_env, mock_quota):
        """Test uploads playlist retrieval exception (lines 154-155)."""
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_env.return_value = "fake_api_key"

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        # Mock exception during channel lookup
        mock_youtube.channels().list().execute.side_effect = Exception("API error")

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('Failed to list recent uploads', data['error'])

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_fetch_playlist_with_checkpoint_filtering(self, mock_build, mock_env, mock_quota):
        """Test playlist fetching with checkpoint filtering (lines 164-194)."""
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_env.return_value = "fake_api_key"

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        # Test checkpoint filtering - video before checkpoint
        checkpoint = self.until_utc
        old_video_time = (datetime.fromisoformat(self.since_utc.replace('Z', '+00:00')) - timedelta(hours=1)).isoformat()

        mock_youtube.playlistItems().list().execute.return_value = {
            'items': [{
                'snippet': {
                    'resourceId': {'videoId': 'old_vid'},
                    'title': 'Old Video',
                    'publishedAt': old_video_time,
                    'channelTitle': 'Test'
                }
            }],
            'nextPageToken': None
        }

        videos = tool._fetch_playlist_videos(mock_youtube, 'UU123', checkpoint, mock_quota_inst)
        self.assertEqual(len(videos), 0)

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_fetch_playlist_early_exit(self, mock_build, mock_env, mock_quota):
        """Test early exit when videos outside time window (lines 196-199)."""
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_env.return_value = "fake_api_key"

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        # Video published before since_utc should trigger early exit
        very_old_time = (datetime.fromisoformat(self.since_utc.replace('Z', '+00:00')) - timedelta(days=2)).isoformat()

        mock_youtube.playlistItems().list().execute.return_value = {
            'items': [{
                'snippet': {
                    'resourceId': {'videoId': 'very_old'},
                    'title': 'Very Old Video',
                    'publishedAt': very_old_time,
                    'channelTitle': 'Test'
                }
            }],
            'nextPageToken': None
        }

        videos = tool._fetch_playlist_videos(mock_youtube, 'UU123', None, mock_quota_inst)
        self.assertEqual(len(videos), 0)

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    def test_fetch_playlist_quota_exhausted_during_fetch(self, mock_quota):
        """Test quota exhaustion during playlist fetching (lines 172-173)."""
        mock_youtube = MagicMock()

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.side_effect = [True, False]  # Exhausted on second call
        mock_quota.return_value = mock_quota_inst

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        mock_youtube.playlistItems().list().execute.return_value = {
            'items': [],
            'nextPageToken': 'next_page'
        }

        videos = tool._fetch_playlist_videos(mock_youtube, 'UU123', None, mock_quota_inst)
        self.assertEqual(len(videos), 0)

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    def test_fetch_playlist_http_429_error(self, mock_quota):
        """Test HTTP 429 rate limit error handling (lines 213-215)."""
        mock_youtube = MagicMock()

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        # Create HTTP 429 error
        http_error = MockHttpError(Mock(status=429), b'Rate limit exceeded')
        mock_youtube.playlistItems().list().execute.side_effect = http_error

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        videos = tool._fetch_playlist_videos(mock_youtube, 'UU123', None, mock_quota_inst)
        self.assertEqual(len(videos), 0)
        mock_quota_inst.mark_quota_exhausted.assert_called_with('youtube')

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    def test_fetch_playlist_http_other_error(self, mock_quota):
        """Test HTTP non-429 error handling (lines 216-217)."""
        mock_youtube = MagicMock()

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        # Create HTTP 500 error
        http_error = MockHttpError(Mock(status=500), b'Server error')
        mock_youtube.playlistItems().list().execute.side_effect = http_error

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        with self.assertRaises(RuntimeError) as context:
            tool._fetch_playlist_videos(mock_youtube, 'UU123', None, mock_quota_inst)
        self.assertIn("YouTube API error", str(context.exception))

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    def test_get_video_details_empty_list(self, mock_quota):
        """Test getting video details with empty list (lines 224-225)."""
        mock_youtube = MagicMock()
        mock_quota_inst = MagicMock()

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        detailed = tool._get_video_details(mock_youtube, [], mock_quota_inst)
        self.assertEqual(detailed, [])

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    def test_get_video_details_quota_exhausted(self, mock_quota):
        """Test video details fetching when quota exhausted (lines 234-235)."""
        mock_youtube = MagicMock()
        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = False

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        videos = [{'video_id': 'vid1', 'title': 'Test'}]
        detailed = tool._get_video_details(mock_youtube, videos, mock_quota_inst)
        self.assertEqual(len(detailed), 0)

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    def test_get_video_details_http_429(self, mock_quota):
        """Test video details HTTP 429 error (lines 263-265)."""
        mock_youtube = MagicMock()
        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True

        http_error = MockHttpError(Mock(status=429), b'Rate limit')
        mock_youtube.videos().list().execute.side_effect = http_error

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        videos = [{'video_id': 'vid1', 'title': 'Test'}]
        detailed = tool._get_video_details(mock_youtube, videos, mock_quota_inst)
        self.assertEqual(len(detailed), 0)
        mock_quota_inst.mark_quota_exhausted.assert_called_with('youtube')

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    def test_get_video_details_http_other_error(self, mock_quota):
        """Test video details HTTP non-429 error (lines 266-267)."""
        mock_youtube = MagicMock()
        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True

        http_error = MockHttpError(Mock(status=403), b'Forbidden')
        mock_youtube.videos().list().execute.side_effect = http_error

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        videos = [{'video_id': 'vid1', 'title': 'Test'}]

        with self.assertRaises(RuntimeError) as context:
            tool._get_video_details(mock_youtube, videos, mock_quota_inst)
        self.assertIn("YouTube API error", str(context.exception))

    def test_filter_videos_by_timeframe(self):
        """Test video filtering by timeframe (lines 271-284)."""
        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc
        )

        mid_time = (datetime.fromisoformat(self.since_utc.replace('Z', '+00:00')) + timedelta(hours=12)).isoformat()
        before_time = (datetime.fromisoformat(self.since_utc.replace('Z', '+00:00')) - timedelta(hours=1)).isoformat()
        after_time = (datetime.fromisoformat(self.until_utc.replace('Z', '+00:00')) + timedelta(hours=1)).isoformat()

        videos = [
            {'video_id': '1', 'published_at': mid_time, 'title': 'In range'},
            {'video_id': '2', 'published_at': before_time, 'title': 'Too early'},
            {'video_id': '3', 'published_at': after_time, 'title': 'Too late'},
        ]

        filtered = tool._filter_videos_by_timeframe(videos)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['video_id'], '1')

    @patch('scraper_agent.tools.list_recent_uploads.QuotaManager')
    @patch('scraper_agent.tools.list_recent_uploads.get_required_env_var')
    @patch('scraper_agent.tools.list_recent_uploads.build')
    def test_pagination_with_next_page_token(self, mock_build, mock_env, mock_quota):
        """Test pagination with nextPageToken (lines 181-210)."""
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_env.return_value = "fake_api_key"

        mock_quota_inst = MagicMock()
        mock_quota_inst.is_service_available.return_value = True
        mock_quota.return_value = mock_quota_inst

        tool = ListRecentUploads(
            channel_id=self.channel_id,
            since_utc=self.since_utc,
            until_utc=self.until_utc,
            page_size=10
        )

        # First page with token
        mid_time = (datetime.fromisoformat(self.since_utc.replace('Z', '+00:00')) + timedelta(hours=6)).isoformat()
        mock_youtube.playlistItems().list().execute.side_effect = [
            {
                'items': [{'snippet': {'resourceId': {'videoId': 'v1'}, 'title': 'V1', 'publishedAt': mid_time, 'channelTitle': 'Test'}}],
                'nextPageToken': 'page2'
            },
            {
                'items': [{'snippet': {'resourceId': {'videoId': 'v2'}, 'title': 'V2', 'publishedAt': mid_time, 'channelTitle': 'Test'}}],
                'nextPageToken': None
            }
        ]

        videos = tool._fetch_playlist_videos(mock_youtube, 'UU123', None, mock_quota_inst)
        self.assertEqual(len(videos), 2)


if __name__ == "__main__":
    unittest.main()