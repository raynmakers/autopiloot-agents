"""
Comprehensive test for get_video_audio_url.py - targeting 75%+ coverage
Tests all paths including YouTube API integration, error handling, and edge cases.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import json
import os
import tempfile

# Mock all external dependencies before imports
sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['yt_dlp'] = MagicMock()
sys.modules['dotenv'] = MagicMock()


class TestGetVideoAudioUrlComprehensive(unittest.TestCase):
    """Comprehensive tests for get_video_audio_url.py achieving 75%+ coverage"""

    def setUp(self):
        """Set up test environment with comprehensive mocking."""
        # Mock pydantic Field
        def mock_field(*args, **kwargs):
            return kwargs.get('default', ...)
        sys.modules['pydantic'].Field = mock_field

        # Mock BaseTool
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

        # Mock dotenv load_dotenv
        sys.modules['dotenv'].load_dotenv = MagicMock()

    def test_successful_remote_url_extraction(self):
        """Test successful remote URL extraction without download."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp extraction
            mock_ydl = MagicMock()
            mock_info = {
                'id': 'dQw4w9WgXcQ',
                'title': 'Test Video',
                'duration': 212,
                'age_limit': 0,
                'is_live': False,
                'formats': [
                    {
                        'acodec': 'mp4a.40.2',
                        'abr': 128,
                        'url': 'https://example.com/audio.m4a',
                        'ext': 'm4a'
                    },
                    {
                        'acodec': 'opus',
                        'abr': 160,
                        'url': 'https://example.com/audio.webm',
                        'ext': 'webm'
                    }
                ]
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                prefer_download=False
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify result structure for remote URL
            self.assertIn('remote_url', result_data)
            self.assertEqual(result_data['remote_url'], 'https://example.com/audio.webm')
            self.assertEqual(result_data['format'], 'webm')
            self.assertEqual(result_data['bitrate'], 160)
            self.assertEqual(result_data['duration'], 212)
            self.assertEqual(result_data['video_id'], 'dQw4w9WgXcQ')

    def test_age_restricted_video_error(self):
        """Test age-restricted video handling (lines 95-100)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with age-restricted video
            mock_ydl = MagicMock()
            mock_info = {
                'age_limit': 18,  # Age-restricted
                'title': 'Age Restricted Video'
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=test")

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'age_restricted')
            self.assertIn('age-restricted', result_data['message'])

    def test_live_stream_error(self):
        """Test live stream handling (lines 102-107)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with live stream
            mock_ydl = MagicMock()
            mock_info = {
                'age_limit': 0,
                'is_live': True,  # Live stream
                'title': 'Live Stream Video'
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=live")

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'live_stream')
            self.assertIn('Live videos are not supported', result_data['message'])

    def test_no_audio_formats_fallback(self):
        """Test fallback when no audio formats available (lines 129-134)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with no audio formats
            mock_ydl = MagicMock()
            mock_info = {
                'id': 'test_id',
                'title': 'Test Video',
                'duration': 100,
                'age_limit': 0,
                'is_live': False,
                'formats': [
                    {
                        'acodec': 'none',  # No audio
                        'vcodec': 'h264',
                        'url': 'https://example.com/video.mp4'
                    }
                ]
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=test")

            result = tool.run()
            result_data = json.loads(result)

            # Should fallback to original video URL
            self.assertIn('remote_url', result_data)
            self.assertEqual(result_data['remote_url'], "https://www.youtube.com/watch?v=test")
            self.assertIn('note', result_data)

    def test_private_video_error(self):
        """Test private video error handling (lines 138-139)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with private video error
            mock_ydl = MagicMock()
            mock_yt_dlp.utils.DownloadError = Exception
            mock_ydl.extract_info.side_effect = Exception("Private video")
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=private")

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'private_video')
            self.assertIn('private', result_data['message'].lower())

    def test_video_unavailable_error(self):
        """Test video unavailable error handling (lines 140-141)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with unavailable video error
            mock_ydl = MagicMock()
            mock_yt_dlp.utils.DownloadError = Exception
            mock_ydl.extract_info.side_effect = Exception("Video unavailable")
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=unavailable")

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'unavailable')
            self.assertIn('unavailable', result_data['message'].lower())

    def test_download_error_fallback(self):
        """Test general download error handling (lines 142-143)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with general download error
            mock_ydl = MagicMock()
            mock_yt_dlp.utils.DownloadError = Exception
            mock_ydl.extract_info.side_effect = Exception("Some download error")
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=error")

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'download_error')
            self.assertIn('Some download error', result_data['message'])

    def test_remote_extraction_silent_fail(self):
        """Test remote extraction silent fail (line 145)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with general exception (not DownloadError)
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = ValueError("Some other error")
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=test")

            # Should silently fail and try local download (which will also fail)
            result = tool.run()
            result_data = json.loads(result)

            # Should fail with both methods
            self.assertIn('error', result_data)
            self.assertIn('both remote and local methods', result_data['error'])

    def test_prefer_download_mode(self):
        """Test prefer_download mode (lines 51-52)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp, \
             patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('os.path.exists') as mock_exists:

            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock tempfile and file operations
            mock_mkdtemp.return_value = '/tmp/test_dir'
            mock_exists.return_value = True

            # Mock yt_dlp for download
            mock_ydl = MagicMock()
            mock_info = {
                'id': 'test_video',
                'title': 'Test Video',
                'duration': 100
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(
                video_url="https://www.youtube.com/watch?v=test",
                prefer_download=True  # Force download mode
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should have attempted download directly
            self.assertIn('local_path', result_data)
            self.assertEqual(result_data['local_path'], '/tmp/test_dir/test_video.mp3')

    def test_local_download_with_alternative_format(self):
        """Test local download with alternative format (lines 189-199)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp, \
             patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('os.path.exists') as mock_exists:

            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock tempfile and file operations
            mock_mkdtemp.return_value = '/tmp/test_dir'

            # Mock file exists calls - mp3 doesn't exist, but m4a does
            def mock_exists_side_effect(path):
                if path.endswith('.mp3'):
                    return False
                elif path.endswith('.m4a'):
                    return True
                return False

            mock_exists.side_effect = mock_exists_side_effect

            # Mock yt_dlp for download
            mock_ydl = MagicMock()
            mock_info = {
                'id': 'test_video',
                'title': 'Test Video',
                'duration': 100
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(
                video_url="https://www.youtube.com/watch?v=test",
                prefer_download=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should find the m4a file
            self.assertIn('local_path', result_data)
            self.assertEqual(result_data['local_path'], '/tmp/test_dir/test_video.m4a')
            self.assertEqual(result_data['format'], 'm4a')

    def test_local_download_file_not_found(self):
        """Test local download when file not found (line 201)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp, \
             patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('os.path.exists') as mock_exists:

            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock tempfile and file operations
            mock_mkdtemp.return_value = '/tmp/test_dir'
            mock_exists.return_value = False  # No files found

            # Mock yt_dlp for download
            mock_ydl = MagicMock()
            mock_info = {
                'id': 'test_video',
                'title': 'Test Video',
                'duration': 100
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(
                video_url="https://www.youtube.com/watch?v=test",
                prefer_download=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should fail with both methods since file not found
            self.assertIn('error', result_data)
            self.assertIn('both remote and local methods', result_data['error'])

    def test_local_download_exception(self):
        """Test local download exception handling (line 203-204)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp to raise exception during download
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = Exception("Download failed")
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(
                video_url="https://www.youtube.com/watch?v=test",
                prefer_download=True
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should fail with both methods
            self.assertIn('error', result_data)
            self.assertIn('both remote and local methods', result_data['error'])

    def test_general_exception_handling(self):
        """Test general exception handling in run method (lines 68-73)."""
        from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

        # Create tool with invalid URL to trigger exception
        tool = GetVideoAudioUrl(video_url="invalid_url")

        # Mock the _extract_remote_url method to raise exception
        with patch.object(tool, '_extract_remote_url', side_effect=Exception("General error")):
            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertIn('Failed to get video audio URL', result_data['error'])
            self.assertIn('General error', result_data['error'])

    def test_main_block_execution(self):
        """Test main block execution for coverage."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp, \
             patch('builtins.print') as mock_print, \
             patch('os.path.exists') as mock_exists, \
             patch('os.remove') as mock_remove:

            # Mock yt_dlp for both test cases
            mock_ydl = MagicMock()
            mock_info = {
                'id': 'dQw4w9WgXcQ',
                'title': 'Test Video',
                'duration': 212,
                'age_limit': 0,
                'is_live': False,
                'formats': [
                    {
                        'acodec': 'mp4a.40.2',
                        'abr': 128,
                        'url': 'https://example.com/audio.m4a',
                        'ext': 'm4a'
                    }
                ]
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            # Mock file operations for download test
            mock_exists.return_value = True
            mock_remove.return_value = None

            # Import should trigger main block
            import transcriber_agent.tools.get_video_audio_url

            # Check that testing messages were printed
            mock_print.assert_called()
            printed_args = [call[0][0] for call in mock_print.call_args_list]
            test_messages = [arg for arg in printed_args if 'Testing GetVideoAudioUrl' in str(arg)]
            self.assertTrue(len(test_messages) > 0)

    def test_audio_format_sorting(self):
        """Test audio format sorting by bitrate (lines 114-116)."""
        with patch('transcriber_agent.tools.get_video_audio_url.yt_dlp') as mock_yt_dlp:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl

            # Mock yt_dlp with multiple audio formats
            mock_ydl = MagicMock()
            mock_info = {
                'id': 'test_id',
                'title': 'Test Video',
                'duration': 100,
                'age_limit': 0,
                'is_live': False,
                'formats': [
                    {
                        'acodec': 'mp4a.40.2',
                        'abr': 64,  # Lower bitrate
                        'url': 'https://example.com/audio_low.m4a',
                        'ext': 'm4a'
                    },
                    {
                        'acodec': 'opus',
                        'abr': 160,  # Higher bitrate - should be selected
                        'url': 'https://example.com/audio_high.webm',
                        'ext': 'webm'
                    },
                    {
                        'acodec': 'mp4a.40.2',
                        'abr': 128,  # Medium bitrate
                        'url': 'https://example.com/audio_med.m4a',
                        'ext': 'm4a'
                    }
                ]
            }
            mock_ydl.extract_info.return_value = mock_info
            mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl

            tool = GetVideoAudioUrl(video_url="https://www.youtube.com/watch?v=test")

            result = tool.run()
            result_data = json.loads(result)

            # Should select the highest bitrate format
            self.assertEqual(result_data['remote_url'], 'https://example.com/audio_high.webm')
            self.assertEqual(result_data['bitrate'], 160)
            self.assertEqual(result_data['format'], 'webm')


if __name__ == "__main__":
    unittest.main()