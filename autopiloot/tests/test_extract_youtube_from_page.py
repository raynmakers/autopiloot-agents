"""
Test suite for ExtractYouTubeFromPage tool.
Tests YouTube URL extraction from web pages functionality.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scraper', 'tools'))

try:
    from scraper.tools.extract_youtube_from_page import ExtractYouTubeFromPage
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'scraper', 
        'tools', 
        'extract_youtube_from_page.py'
    )
    spec = importlib.util.spec_from_file_location("extract_youtube_from_page", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ExtractYouTubeFromPage = module.ExtractYouTubeFromPage


class TestExtractYouTubeFromPage(unittest.TestCase):
    """Test cases for ExtractYouTubeFromPage tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_url = "https://example.com/test-page"
        self.tool = ExtractYouTubeFromPage(page_url=self.test_url)

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_extract_from_iframe_embeds(self, mock_get):
        """Test extraction of YouTube URLs from iframe embeds."""
        mock_html = """
        <html>
        <body>
            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" frameborder="0"></iframe>
            <iframe src="https://www.youtube-nocookie.com/embed/jNQXAC9IVRw" frameborder="0"></iframe>
            <iframe src="https://www.example.com/other" frameborder="0"></iframe>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 2)
        
        video_urls = {video['video_url'] for video in data['videos']}
        expected_urls = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        }
        self.assertEqual(video_urls, expected_urls)

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_extract_from_links(self, mock_get):
        """Test extraction of YouTube URLs from anchor tags."""
        mock_html = """
        <html>
        <body>
            <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Video 1</a>
            <a href="https://youtu.be/jNQXAC9IVRw">Video 2</a>
            <a href="https://www.example.com/other">Other Link</a>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 2)
        
        video_urls = {video['video_url'] for video in data['videos']}
        expected_urls = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        }
        self.assertEqual(video_urls, expected_urls)

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_extract_from_meta_tags(self, mock_get):
        """Test extraction of YouTube URLs from meta og:video tags."""
        mock_html = """
        <html>
        <head>
            <meta property="og:video" content="https://www.youtube.com/embed/dQw4w9WgXcQ" />
            <meta property="og:title" content="Test Video" />
        </head>
        <body>Content</body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 1)
        self.assertEqual(data['videos'][0]['video_url'], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_extract_from_script_tags(self, mock_get):
        """Test extraction of YouTube URLs from JavaScript content."""
        mock_html = """
        <html>
        <body>
            <script>
                var videoUrl = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
                embedVideo("https://youtu.be/jNQXAC9IVRw");
            </script>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 2)
        
        video_urls = {video['video_url'] for video in data['videos']}
        expected_urls = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        }
        self.assertEqual(video_urls, expected_urls)

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_extract_from_raw_html(self, mock_get):
        """Test extraction of YouTube URLs from raw HTML text."""
        mock_html = """
        <html>
        <body>
            Check out this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
            And this one: https://youtu.be/jNQXAC9IVRw
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 2)
        
        video_urls = {video['video_url'] for video in data['videos']}
        expected_urls = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        }
        self.assertEqual(video_urls, expected_urls)

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_deduplication_across_sources(self, mock_get):
        """Test that URLs found in multiple places are deduplicated."""
        mock_html = """
        <html>
        <head>
            <meta property="og:video" content="https://www.youtube.com/embed/dQw4w9WgXcQ" />
        </head>
        <body>
            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" frameborder="0"></iframe>
            <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Same Video</a>
            <script>
                var url = "https://youtu.be/dQw4w9WgXcQ";
            </script>
            Check out: https://www.youtube.com/watch?v=dQw4w9WgXcQ
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        # Should deduplicate to single URL despite being found in multiple places
        self.assertEqual(len(data['videos']), 1)
        self.assertEqual(data['videos'][0]['video_url'], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_no_youtube_urls_found(self, mock_get):
        """Test behavior when no YouTube URLs are found."""
        mock_html = """
        <html>
        <body>
            <p>This page has no YouTube videos.</p>
            <a href="https://www.example.com">External link</a>
            <iframe src="https://www.vimeo.com/123456" frameborder="0"></iframe>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 0)
        self.assertEqual(data['summary']['videos_found'], 0)

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_http_error_handling(self, mock_get):
        """Test handling of HTTP errors."""
        mock_get.side_effect = Exception("Connection timeout")
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('Connection timeout', data['error'])
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 0)

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_malformed_html_handling(self, mock_get):
        """Test handling of malformed HTML."""
        mock_html = "<html><body><iframe src='youtube.com/embed/bad-html"  # Malformed
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Should handle malformed HTML gracefully
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertIn('videos', data)
        # BeautifulSoup should still parse what it can

    def test_youtube_url_patterns(self):
        """Test various YouTube URL format recognition."""
        test_html_template = """
        <html><body>
        <a href="{}">Link</a>
        </body></html>
        """
        
        valid_youtube_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/v/dQw4w9WgXcQ",
            "www.youtube.com/watch?v=dQw4w9WgXcQ",
            "youtu.be/dQw4w9WgXcQ",
        ]
        
        for url in valid_youtube_urls:
            with patch('scraper.tools.extract_youtube_from_page.requests.get') as mock_get:
                mock_html = test_html_template.format(url)
                mock_response = MagicMock()
                mock_response.text = mock_html
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                result = self.tool.run()
                data = json.loads(result)
                
                self.assertGreater(len(data['videos']), 0, f"Failed to extract from: {url}")

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_mixed_content_extraction(self, mock_get):
        """Test extraction from page with mixed YouTube and non-YouTube content."""
        mock_html = """
        <html>
        <head>
            <meta property="og:video" content="https://www.youtube.com/embed/video1" />
            <meta property="og:image" content="https://example.com/image.jpg" />
        </head>
        <body>
            <iframe src="https://www.youtube.com/embed/video2" frameborder="0"></iframe>
            <iframe src="https://www.vimeo.com/123456" frameborder="0"></iframe>
            <a href="https://www.youtube.com/watch?v=video3">YouTube Link</a>
            <a href="https://www.example.com/page">Regular Link</a>
            <script>
                var youtube = "https://youtu.be/video4";
                var other = "https://example.com/other";
            </script>
            <p>Check out https://www.youtube.com/watch?v=video5 and https://example.com</p>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        self.assertEqual(len(data['videos']), 5)
        
        # Verify all expected video IDs are present
        video_urls = {video['video_url'] for video in data['videos']}
        expected_urls = {
            "https://www.youtube.com/watch?v=video1",
            "https://www.youtube.com/watch?v=video2", 
            "https://www.youtube.com/watch?v=video3",
            "https://www.youtube.com/watch?v=video4",
            "https://www.youtube.com/watch?v=video5",
        }
        self.assertEqual(video_urls, expected_urls)

    def test_tool_initialization(self):
        """Test tool initialization with parameters."""
        tool = ExtractYouTubeFromPage(page_url="https://example.com/test")
        self.assertEqual(tool.page_url, "https://example.com/test")

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_response_format(self, mock_get):
        """Test that response format matches expected structure."""
        mock_html = """
        <html>
        <body>
            <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" frameborder="0"></iframe>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.tool.run()
        data = json.loads(result)
        
        # Verify response structure
        self.assertIn('videos', data)
        self.assertIn('summary', data)
        
        # Verify summary structure
        self.assertIn('page_url', data['summary'])
        self.assertIn('videos_found', data['summary'])
        self.assertEqual(data['summary']['page_url'], self.test_url)
        self.assertEqual(data['summary']['videos_found'], len(data['videos']))
        
        # Verify video structure
        if data['videos']:
            self.assertIn('video_url', data['videos'][0])

    @patch('scraper.tools.extract_youtube_from_page.requests.get')
    def test_user_agent_header(self, mock_get):
        """Test that proper User-Agent header is sent."""
        mock_html = "<html><body></body></html>"
        mock_response = MagicMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        self.tool.run()
        
        # Verify that requests.get was called with proper headers
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        headers = call_args[1]['headers']
        self.assertIn('User-Agent', headers)
        self.assertIn('Mozilla', headers['User-Agent'])


if __name__ == '__main__':
    unittest.main(verbosity=2)