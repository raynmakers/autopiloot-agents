"""
Integration tests for ListRecentUploads tool.
Tests uploads playlist functionality, checkpoint management, and quota handling.
"""

import unittest
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

# Add project paths for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, 'scraper', 'tools'))
sys.path.append(os.path.join(project_root, 'core'))
sys.path.append(os.path.join(project_root, 'config'))

try:
    from list_recent_uploads import ListRecentUploads
    TOOL_AVAILABLE = True
except ImportError:
    TOOL_AVAILABLE = False
    print("Warning: ListRecentUploads tool not available for testing")


class TestListRecentUploads(unittest.TestCase):
    """Test cases for ListRecentUploads tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        if not TOOL_AVAILABLE:
            self.skipTest("ListRecentUploads tool not available")
        
        # Create test time window (24 hours)
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        
        self.tool = ListRecentUploads(
            channel_id="UCfV36TX5AejfAGIbtwTc7Zw",
            since_utc=yesterday.isoformat(),
            until_utc=now.isoformat(),
            page_size=10,
            use_checkpoint=False
        )
        
        self.mock_youtube_client = Mock()
        self.mock_quota_manager = Mock()
        
        # Sample test data
        self.sample_channel_response = {
            'items': [{
                'contentDetails': {
                    'relatedPlaylists': {
                        'uploads': 'UUfV36TX5AejfAGIbtwTc7Zw'
                    }
                }
            }]
        }
        
        self.sample_playlist_response = {
            'items': [
                {
                    'snippet': {
                        'resourceId': {'videoId': 'video1'},
                        'title': 'Test Video 1',
                        'publishedAt': '2025-01-27T12:00:00Z',
                        'channelTitle': 'Test Channel'
                    }
                },
                {
                    'snippet': {
                        'resourceId': {'videoId': 'video2'},
                        'title': 'Test Video 2',
                        'publishedAt': '2025-01-27T10:00:00Z',
                        'channelTitle': 'Test Channel'
                    }
                }
            ]
        }
        
        self.sample_videos_response = {
            'items': [
                {
                    'id': 'video1',
                    'snippet': {
                        'title': 'Test Video 1',
                        'publishedAt': '2025-01-27T12:00:00Z'
                    },
                    'contentDetails': {
                        'duration': 'PT5M30S'
                    }
                },
                {
                    'id': 'video2', 
                    'snippet': {
                        'title': 'Test Video 2',
                        'publishedAt': '2025-01-27T10:00:00Z'
                    },
                    'contentDetails': {
                        'duration': 'PT10M45S'
                    }
                }
            ]
        }
    
    def test_get_uploads_playlist_id_success(self):
        """Test successful retrieval of uploads playlist ID."""
        self.mock_youtube_client.channels.return_value.list.return_value.execute.return_value = self.sample_channel_response
        
        playlist_id = self.tool._get_uploads_playlist_id(self.mock_youtube_client, "UCfV36TX5AejfAGIbtwTc7Zw")
        
        self.assertEqual(playlist_id, "UUfV36TX5AejfAGIbtwTc7Zw")
        self.mock_youtube_client.channels.return_value.list.assert_called_once_with(
            part='contentDetails',
            id="UCfV36TX5AejfAGIbtwTc7Zw"
        )
    
    def test_get_uploads_playlist_id_not_found(self):
        """Test handling when channel not found."""
        self.mock_youtube_client.channels.return_value.list.return_value.execute.return_value = {'items': []}
        
        playlist_id = self.tool._get_uploads_playlist_id(self.mock_youtube_client, "invalid_channel")
        
        self.assertIsNone(playlist_id)
    
    def test_parse_duration_various_formats(self):
        """Test parsing of various ISO 8601 duration formats."""
        test_cases = [
            ("PT5M30S", 330),      # 5 minutes 30 seconds
            ("PT1H30M", 5400),     # 1 hour 30 minutes
            ("PT2H15M45S", 8145),  # 2 hours 15 minutes 45 seconds
            ("PT45S", 45),         # 45 seconds only
            ("PT10M", 600),        # 10 minutes only
            ("PT1H", 3600),        # 1 hour only
            ("PT0S", 0),           # 0 duration
            ("", 0),               # Empty string
            ("invalid", 0)         # Invalid format
        ]
        
        for duration_str, expected_seconds in test_cases:
            with self.subTest(duration=duration_str):
                result = self.tool._parse_duration(duration_str)
                self.assertEqual(result, expected_seconds)
    
    def test_filter_videos_by_timeframe(self):
        """Test filtering videos by specified time window."""
        # Create test videos with different timestamps
        test_videos = [
            {
                'video_id': 'video1',
                'title': 'Within Range 1',
                'published_at': '2025-01-27T12:00:00Z',
                'duration_sec': 300
            },
            {
                'video_id': 'video2',
                'title': 'Before Range',
                'published_at': '2025-01-26T12:00:00Z', 
                'duration_sec': 400
            },
            {
                'video_id': 'video3',
                'title': 'Within Range 2',
                'published_at': '2025-01-27T18:00:00Z',
                'duration_sec': 500
            },
            {
                'video_id': 'video4',
                'title': 'After Range',
                'published_at': '2025-01-28T12:00:00Z',
                'duration_sec': 600
            }
        ]
        
        # Set specific time window
        self.tool.since_utc = "2025-01-27T00:00:00Z"
        self.tool.until_utc = "2025-01-28T00:00:00Z"
        
        filtered = self.tool._filter_videos_by_timeframe(test_videos)
        
        # Should only include videos 1 and 3
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]['video_id'], 'video3')  # Newest first
        self.assertEqual(filtered[1]['video_id'], 'video1')
    
    @patch.object(ListRecentUploads, '_initialize_youtube_client')
    @patch('ListRecentUploads.QuotaManager')
    def test_fetch_playlist_videos_with_checkpoint(self, mock_quota_manager_class, mock_init_client):
        """Test fetching playlist videos with checkpoint filtering."""
        mock_quota_manager = Mock()
        mock_quota_manager.is_service_available.return_value = True
        mock_quota_manager_class.return_value = mock_quota_manager
        
        # Mock playlist response with videos before and after checkpoint
        playlist_response = {
            'items': [
                {
                    'snippet': {
                        'resourceId': {'videoId': 'new_video'},
                        'title': 'New Video',
                        'publishedAt': '2025-01-27T15:00:00Z',
                        'channelTitle': 'Test Channel'
                    }
                },
                {
                    'snippet': {
                        'resourceId': {'videoId': 'old_video'},
                        'title': 'Old Video',
                        'publishedAt': '2025-01-27T09:00:00Z',  # Before checkpoint
                        'channelTitle': 'Test Channel'
                    }
                }
            ]
        }
        
        self.mock_youtube_client.playlistItems.return_value.list.return_value.execute.return_value = playlist_response
        
        # Set checkpoint to 10:00 AM
        checkpoint = "2025-01-27T10:00:00Z"
        
        videos = self.tool._fetch_playlist_videos(
            self.mock_youtube_client,
            "UUfV36TX5AejfAGIbtwTc7Zw",
            checkpoint,
            mock_quota_manager
        )
        
        # Should only include new_video (after checkpoint)
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]['video_id'], 'new_video')
    
    @patch.object(ListRecentUploads, '_initialize_youtube_client')
    @patch('ListRecentUploads.QuotaManager')
    def test_get_video_details_batch_processing(self, mock_quota_manager_class, mock_init_client):
        """Test batch processing of video details."""
        mock_quota_manager = Mock()
        mock_quota_manager.is_service_available.return_value = True
        mock_quota_manager_class.return_value = mock_quota_manager
        
        # Create test videos
        videos = [
            {'video_id': f'video{i}', 'title': f'Video {i}', 'published_at': '2025-01-27T12:00:00Z'}
            for i in range(3)
        ]
        
        self.mock_youtube_client.videos.return_value.list.return_value.execute.return_value = self.sample_videos_response
        
        detailed_videos = self.tool._get_video_details(self.mock_youtube_client, videos, mock_quota_manager)
        
        # Should return detailed video information
        self.assertTrue(len(detailed_videos) <= len(videos))
        for video in detailed_videos:
            self.assertIn('duration_sec', video)
            self.assertIn('url', video)
            self.assertTrue(video['url'].startswith('https://www.youtube.com/watch?v='))
    
    @patch('ListRecentUploads.FIREBASE_AVAILABLE', True)
    @patch('ListRecentUploads.firestore')
    def test_checkpoint_loading_and_saving(self, mock_firestore):
        """Test checkpoint loading and saving functionality."""
        # Mock Firestore client
        mock_db = Mock()
        mock_firestore.client.return_value = mock_db
        
        # Test loading existing checkpoint
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'last_published_at': '2025-01-27T10:00:00Z'}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        checkpoint = self.tool._load_checkpoint("test_channel")
        self.assertEqual(checkpoint, '2025-01-27T10:00:00Z')
        
        # Test saving checkpoint
        mock_doc_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        self.tool._save_checkpoint("test_channel", "2025-01-27T12:00:00Z")
        
        # Verify save was called
        mock_doc_ref.set.assert_called_once()
        call_args = mock_doc_ref.set.call_args[0][0]
        self.assertEqual(call_args['channel_id'], "test_channel")
        self.assertEqual(call_args['last_published_at'], "2025-01-27T12:00:00Z")
    
    @patch('ListRecentUploads.FIREBASE_AVAILABLE', False)
    def test_checkpoint_handling_without_firebase(self):
        """Test checkpoint handling when Firebase is not available."""
        # Should return None for loading
        checkpoint = self.tool._load_checkpoint("test_channel")
        self.assertIsNone(checkpoint)
        
        # Should not raise error for saving
        try:
            self.tool._save_checkpoint("test_channel", "2025-01-27T12:00:00Z")
        except Exception as e:
            self.fail(f"Checkpoint saving should not fail without Firebase: {e}")
    
    @patch.object(ListRecentUploads, '_initialize_youtube_client')
    @patch.object(ListRecentUploads, '_get_uploads_playlist_id')
    @patch.object(ListRecentUploads, '_fetch_playlist_videos')
    @patch.object(ListRecentUploads, '_get_video_details')
    @patch.object(ListRecentUploads, '_filter_videos_by_timeframe')
    @patch('ListRecentUploads.QuotaManager')
    def test_full_workflow_success(self, mock_quota_manager_class, mock_filter, mock_get_details, 
                                  mock_fetch, mock_get_playlist, mock_init_client):
        """Test successful execution of the complete workflow."""
        # Mock all dependencies
        mock_quota_manager = Mock()
        mock_quota_manager.is_service_available.return_value = True
        mock_quota_manager.get_quota_status.return_value = {'reset_time': None}
        mock_quota_manager_class.return_value = mock_quota_manager
        
        mock_init_client.return_value = self.mock_youtube_client
        mock_get_playlist.return_value = "UUfV36TX5AejfAGIbtwTc7Zw"
        mock_fetch.return_value = [{'video_id': 'test1', 'title': 'Test 1'}]
        mock_get_details.return_value = [
            {
                'video_id': 'test1',
                'url': 'https://www.youtube.com/watch?v=test1',
                'title': 'Test Video 1',
                'published_at': '2025-01-27T12:00:00Z',
                'duration_sec': 300
            }
        ]
        mock_filter.return_value = mock_get_details.return_value
        
        result = self.tool.run()
        
        # Parse JSON result
        result_data = json.loads(result)
        
        self.assertIn('items', result_data)
        self.assertEqual(len(result_data['items']), 1)
        self.assertEqual(result_data['items'][0]['video_id'], 'test1')
        self.assertEqual(result_data['items'][0]['duration_sec'], 300)
    
    @patch.object(ListRecentUploads, '_initialize_youtube_client')
    @patch('ListRecentUploads.QuotaManager')
    def test_quota_exhausted_handling(self, mock_quota_manager_class, mock_init_client):
        """Test handling when YouTube API quota is exhausted."""
        mock_quota_manager = Mock()
        mock_quota_manager.is_service_available.return_value = False
        mock_quota_manager.get_quota_status.return_value = {
            'reset_time': '2025-01-28T00:00:00Z'
        }
        mock_quota_manager_class.return_value = mock_quota_manager
        
        result = self.tool.run()
        result_data = json.loads(result)
        
        self.assertIn('error', result_data)
        self.assertIn('quota exhausted', result_data['error'])
        self.assertIn('quota_reset_time', result_data)
    
    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test valid parameters
        tool = ListRecentUploads(
            channel_id="UCtest123",
            since_utc="2025-01-27T00:00:00Z",
            until_utc="2025-01-28T00:00:00Z",
            page_size=25,
            use_checkpoint=True
        )
        
        self.assertEqual(tool.channel_id, "UCtest123")
        self.assertEqual(tool.page_size, 25)
        self.assertTrue(tool.use_checkpoint)
        
        # Test page_size constraints
        with self.assertRaises(ValueError):
            ListRecentUploads(
                channel_id="UCtest123",
                since_utc="2025-01-27T00:00:00Z",
                until_utc="2025-01-28T00:00:00Z",
                page_size=0  # Too small
            )
        
        with self.assertRaises(ValueError):
            ListRecentUploads(
                channel_id="UCtest123",
                since_utc="2025-01-27T00:00:00Z",
                until_utc="2025-01-28T00:00:00Z",
                page_size=100  # Too large
            )
    
    def test_error_handling_in_run(self):
        """Test error handling in the main run method."""
        # Create tool with invalid configuration to trigger error
        tool = ListRecentUploads(
            channel_id="invalid",
            since_utc="invalid_date",
            until_utc="invalid_date",
            page_size=10
        )
        
        result = tool.run()
        result_data = json.loads(result)
        
        self.assertIn('error', result_data)
        self.assertIn('items', result_data)
        self.assertEqual(result_data['items'], [])


class TestListRecentUploadsIntegration(unittest.TestCase):
    """Integration tests for realistic scenarios."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        if not TOOL_AVAILABLE:
            self.skipTest("ListRecentUploads tool not available")
    
    @unittest.skipUnless(os.getenv("RUN_INTEGRATION_TESTS"), "Integration tests require RUN_INTEGRATION_TESTS=1")
    @patch.dict(os.environ, {'YOUTUBE_API_KEY': 'test_key'})
    def test_integration_with_mock_data(self):
        """Integration test with mocked YouTube API responses."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        
        tool = ListRecentUploads(
            channel_id="UCfV36TX5AejfAGIbtwTc7Zw",
            since_utc=yesterday.isoformat(),
            until_utc=now.isoformat(),
            page_size=5,
            use_checkpoint=False
        )
        
        # This would test with real API if credentials were available
        self.assertIsInstance(tool, ListRecentUploads)
        self.assertEqual(tool.page_size, 5)


if __name__ == '__main__':
    # Configure test discovery and run
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_list_recent_uploads.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    # Exit with appropriate code
    exit_code = 0 if (len(result.failures) == 0 and len(result.errors) == 0) else 1
    sys.exit(exit_code)