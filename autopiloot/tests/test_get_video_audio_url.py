"""
Unit tests for GetVideoAudioUrl tool
Tests TASK-TRN-0020 implementation
"""

import unittest
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the tool module directly to avoid agency_swarm dependency in tests
import importlib.util
tool_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'transcriber_agent', 'tools', 'get_video_audio_url.py'
)
spec = importlib.util.spec_from_file_location("get_video_audio_url", tool_path)
get_video_audio_url_module = importlib.util.module_from_spec(spec)

# Mock agency_swarm before loading the module
with patch.dict('sys.modules', {'agency_swarm': MagicMock(), 'agency_swarm.tools': MagicMock()}):
    spec.loader.exec_module(get_video_audio_url_module)
    GetVideoAudioUrl = get_video_audio_url_module.GetVideoAudioUrl


class TestGetVideoAudioUrl(unittest.TestCase):
    """Test cases for GetVideoAudioUrl tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    @patch('get_video_audio_url.yt_dlp.YoutubeDL')
    def test_extract_remote_url_success(self, mock_ydl_class):
        """Test successful remote URL extraction."""
        # Mock yt-dlp response
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'id': 'dQw4w9WgXcQ',
            'title': 'Test Video',
            'duration': 212,
            'age_limit': 0,
            'is_live': False,
            'formats': [
                {
                    'acodec': 'mp4a.40.2',
                    'ext': 'm4a',
                    'abr': 128,
                    'url': 'https://example.com/audio.m4a'
                },
                {
                    'acodec': 'opus',
                    'ext': 'webm',
                    'abr': 160,
                    'url': 'https://example.com/audio.webm'
                }
            ]
        }
        mock_ydl.extract_info.return_value = mock_info
        
        # Test the tool
        tool = GetVideoAudioUrl(video_url=self.test_video_url)
        result = tool.run()
        
        # Validate result
        data = json.loads(result)
        self.assertIn('remote_url', data)
        self.assertEqual(data['remote_url'], 'https://example.com/audio.webm')  # Higher bitrate
        self.assertEqual(data['format'], 'webm')
        self.assertEqual(data['bitrate'], 160)
        self.assertEqual(data['duration'], 212)
        self.assertEqual(data['video_id'], 'dQw4w9WgXcQ')
    
    @patch('get_video_audio_url.yt_dlp.YoutubeDL')
    def test_age_restricted_video(self, mock_ydl_class):
        """Test handling of age-restricted videos."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'id': 'test123',
            'title': 'Age Restricted Video',
            'age_limit': 18,
            'is_live': False,
            'formats': []
        }
        mock_ydl.extract_info.return_value = mock_info
        
        tool = GetVideoAudioUrl(video_url=self.test_video_url)
        result = tool.run()
        
        data = json.loads(result)
        self.assertEqual(data.get('error'), 'age_restricted')
        self.assertIn('age-restricted', data.get('message', ''))
    
    @patch('get_video_audio_url.yt_dlp.YoutubeDL')
    def test_live_stream_video(self, mock_ydl_class):
        """Test handling of live stream videos."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'id': 'live123',
            'title': 'Live Stream',
            'age_limit': 0,
            'is_live': True,
            'formats': []
        }
        mock_ydl.extract_info.return_value = mock_info
        
        tool = GetVideoAudioUrl(video_url=self.test_video_url)
        result = tool.run()
        
        data = json.loads(result)
        self.assertEqual(data.get('error'), 'live_stream')
        self.assertIn('Live videos', data.get('message', ''))
    
    @patch('get_video_audio_url.yt_dlp.YoutubeDL')
    def test_fallback_to_video_url(self, mock_ydl_class):
        """Test fallback to original video URL when no audio formats found."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_info = {
            'id': 'test456',
            'title': 'No Audio Formats',
            'duration': 180,
            'age_limit': 0,
            'is_live': False,
            'formats': [
                {
                    'acodec': 'none',  # Video only format
                    'ext': 'mp4',
                    'url': 'https://example.com/video.mp4'
                }
            ]
        }
        mock_ydl.extract_info.return_value = mock_info
        
        tool = GetVideoAudioUrl(video_url=self.test_video_url)
        result = tool.run()
        
        data = json.loads(result)
        self.assertIn('remote_url', data)
        self.assertEqual(data['remote_url'], self.test_video_url)
        self.assertIn('note', data)
        self.assertIn('original video URL', data['note'])
    
    @patch('get_video_audio_url.yt_dlp.YoutubeDL')
    def test_private_video_error(self, mock_ydl_class):
        """Test handling of private videos."""
        import yt_dlp
        
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError('Private video')
        
        tool = GetVideoAudioUrl(video_url=self.test_video_url)
        result = tool.run()
        
        data = json.loads(result)
        self.assertIn('error', data)
        self.assertIsNone(data.get('remote_url'))
    
    @patch('get_video_audio_url.tempfile.mkdtemp')
    @patch('get_video_audio_url.os.path.exists')
    @patch('get_video_audio_url.yt_dlp.YoutubeDL')
    def test_local_download_fallback(self, mock_ydl_class, mock_exists, mock_mkdtemp):
        """Test fallback to local download when remote extraction fails."""
        # Mock temporary directory
        mock_mkdtemp.return_value = '/tmp/test_audio'
        
        # First YoutubeDL instance for remote extraction (fails)
        mock_ydl_remote = MagicMock()
        mock_ydl_remote.extract_info.side_effect = Exception("Remote extraction failed")
        
        # Second YoutubeDL instance for local download (succeeds)
        mock_ydl_local = MagicMock()
        mock_info = {
            'id': 'local123',
            'title': 'Local Download Test',
            'duration': 150
        }
        mock_ydl_local.extract_info.return_value = mock_info
        
        # Configure mock to return different instances
        mock_ydl_class.return_value.__enter__.side_effect = [mock_ydl_remote, mock_ydl_local]
        
        # Mock file existence check
        mock_exists.return_value = True
        
        tool = GetVideoAudioUrl(video_url=self.test_video_url)
        result = tool.run()
        
        data = json.loads(result)
        self.assertIn('local_path', data)
        self.assertEqual(data['local_path'], '/tmp/test_audio/local123.mp3')
        self.assertEqual(data['format'], 'mp3')
        self.assertIn('note', data)
        self.assertIn('locally', data['note'])
    
    def test_prefer_download_option(self):
        """Test that prefer_download option skips remote extraction."""
        with patch.object(GetVideoAudioUrl, '_extract_remote_url') as mock_extract:
            with patch.object(GetVideoAudioUrl, '_download_audio_locally') as mock_download:
                mock_download.return_value = {
                    'local_path': '/tmp/audio.mp3',
                    'format': 'mp3'
                }
                
                tool = GetVideoAudioUrl(
                    video_url=self.test_video_url,
                    prefer_download=True
                )
                result = tool.run()
                
                # Should not call remote extraction when prefer_download=True
                mock_extract.assert_not_called()
                mock_download.assert_called_once()
                
                data = json.loads(result)
                self.assertIn('local_path', data)
    
    def test_both_methods_fail(self):
        """Test error handling when both remote and local methods fail."""
        with patch.object(GetVideoAudioUrl, '_extract_remote_url') as mock_extract:
            with patch.object(GetVideoAudioUrl, '_download_audio_locally') as mock_download:
                mock_extract.return_value = None
                mock_download.return_value = None
                
                tool = GetVideoAudioUrl(video_url=self.test_video_url)
                result = tool.run()
                
                data = json.loads(result)
                self.assertIn('error', data)
                self.assertIn('both remote and local methods', data['error'])
                self.assertIsNone(data.get('remote_url'))
                self.assertIsNone(data.get('local_path'))
    
    def test_json_string_return_format(self):
        """Test that tool returns valid JSON string per Agency Swarm v1.0.0."""
        with patch.object(GetVideoAudioUrl, '_extract_remote_url') as mock_extract:
            mock_extract.return_value = {
                'remote_url': 'https://example.com/audio.m4a',
                'format': 'm4a'
            }
            
            tool = GetVideoAudioUrl(video_url=self.test_video_url)
            result = tool.run()
            
            # Should return string, not dict
            self.assertIsInstance(result, str)
            
            # Should be valid JSON
            try:
                data = json.loads(result)
                self.assertIsInstance(data, dict)
            except json.JSONDecodeError:
                self.fail("Tool did not return valid JSON string")


if __name__ == '__main__':
    unittest.main()