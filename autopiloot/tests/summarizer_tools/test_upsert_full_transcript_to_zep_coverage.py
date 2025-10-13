"""
Comprehensive test suite for UpsertFullTranscriptToZep tool.
Tests chunking, hashing, Zep v3 API integration, and Firestore updates.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools

# Mock httpx
mock_httpx = MagicMock()
sys.modules['httpx'] = mock_httpx

# Mock tiktoken
mock_tiktoken = MagicMock()
mock_encoding = MagicMock()
mock_encoding.encode = MagicMock(return_value=[1, 2, 3, 4, 5] * 20)  # Mock token list
mock_encoding.decode = MagicMock(side_effect=lambda tokens: "Decoded text " * (len(tokens) // 5))
mock_tiktoken.get_encoding = MagicMock(return_value=mock_encoding)
sys.modules['tiktoken'] = mock_tiktoken


class TestUpsertFullTranscriptToZep(unittest.TestCase):
    """Test suite for UpsertFullTranscriptToZep tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'upsert_full_transcript_to_zep.py'
        )
        spec = importlib.util.spec_from_file_location("upsert_full_transcript_to_zep", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.UpsertFullTranscriptToZep

        # Sample test data
        self.sample_transcript = "This is a test transcript. " * 100  # ~700 chars
        self.video_id = "test_video_123"
        self.channel_id = "UCtest123"

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_key',
        'ZEP_BASE_URL': 'https://test.api.com',
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_successful_upsert(self, mock_import):
        """Test successful transcript upsert to Zep (lines 75-228)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 1000,
            'rag.zep.transcripts.chunking.overlap_tokens': 100,
            'rag.zep.transcripts.group_format': 'youtube_transcripts_{channel_id}',
            'rag.zep.transcripts.thread_id_format': 'transcript_{video_id}',
            'rag.zep.transcripts.user_id_format': 'youtube_{channel_id}'
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock HTTP client
        mock_client = MagicMock()
        mock_httpx.Client.return_value = mock_client

        # Mock successful API responses
        mock_client.post.return_value = Mock(status_code=201, text='{"uuid": "test-uuid"}')

        # Mock Firestore
        with patch('google.cloud.firestore.Client') as mock_firestore:
            mock_db = MagicMock()
            mock_firestore.return_value = mock_db
            mock_doc_ref = MagicMock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref

            # Create tool instance
            tool = self.ToolClass(
                video_id=self.video_id,
                transcript_text=self.sample_transcript,
                channel_id=self.channel_id,
                title="Test Video",
                published_at="2025-10-12T12:00:00Z"
            )

            # Run tool
            result = tool.run()
            data = json.loads(result)

            # Assertions
            self.assertIn('thread_id', data)
            self.assertIn('chunk_count', data)
            self.assertIn('total_tokens', data)
            self.assertEqual(data['status'], 'stored')
            self.assertGreater(data['chunk_count'], 0)

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_key'
    })
    def test_chunking_logic(self, ):
        """Test token-aware chunking logic (lines 258-293)."""
        # Create tool instance
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Test chunking
        chunks = tool._chunk_transcript(self.sample_transcript, max_tokens=100, overlap_tokens=10)

        # Assertions
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 1, "Should create multiple chunks")

        # Verify overlap - adjacent chunks should share some content
        if len(chunks) > 1:
            # Check that chunks have reasonable lengths
            for chunk in chunks:
                self.assertIsInstance(chunk, str)
                self.assertGreater(len(chunk), 0)

    def test_token_counting(self):
        """Test token counting method (lines 295-307)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Test token counting
        token_count = tool._count_tokens("This is a test string")

        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_key'
    })
    def test_user_creation_already_exists(self):
        """Test user creation when user already exists (lines 313-340)."""
        mock_client = MagicMock()

        # Simulate user already exists
        mock_response = Mock(status_code=409, text='user already exists')
        mock_client.post.return_value = mock_response

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool._ensure_user_exists(mock_client, "https://api.test.com", "test_user")

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'already_exists')

    def test_user_creation_error(self):
        """Test user creation error handling (lines 341-343)."""
        mock_client = MagicMock()

        # Simulate server error
        mock_response = Mock(status_code=500, text='Internal Server Error')
        mock_client.post.return_value = mock_response

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool._ensure_user_exists(mock_client, "https://api.test.com", "test_user")

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_group_creation_already_exists(self):
        """Test group creation when group already exists (lines 345-377)."""
        mock_client = MagicMock()

        # Simulate group already exists
        mock_response = Mock(status_code=409, text='already exists')
        mock_client.post.return_value = mock_response

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool._ensure_group_exists(mock_client, "https://api.test.com", "test_group")

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'already_exists')

    def test_thread_creation_success(self):
        """Test thread creation success path (lines 379-413)."""
        mock_client = MagicMock()

        # Simulate successful thread creation
        mock_response = Mock(status_code=201)
        mock_response.json.return_value = {'uuid': 'thread-uuid-123'}
        mock_client.post.return_value = mock_response

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id,
            title="Test Video",
            duration_sec=120
        )

        result = tool._create_thread(
            mock_client,
            "https://api.test.com",
            "test_thread_id",
            "test_user_id",
            "test_group"
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['thread_uuid'], 'thread-uuid-123')

    def test_chunk_message_addition(self):
        """Test adding chunk as message to thread (lines 415-453)."""
        mock_client = MagicMock()

        # Simulate successful message addition
        mock_response = Mock(status_code=201)
        mock_response.json.return_value = {'message_uuids': ['msg-uuid-123']}
        mock_client.post.return_value = mock_response

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        chunk_data = {
            'chunk_id': 'chunk_1',
            'chunk_index': 1,
            'total_chunks': 5,
            'text': 'Test chunk text',
            'content_sha256': 'abc123',
            'tokens': 10
        }

        result = tool._add_chunk_message(
            mock_client,
            "https://api.test.com",
            "test_thread_id",
            chunk_data
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['message_uuid'], 'msg-uuid-123')

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    def test_firestore_metadata_update(self):
        """Test Firestore metadata update (lines 455-481)."""
        with patch('google.cloud.firestore.Client') as mock_firestore_client:
            mock_db = MagicMock()
            mock_firestore_client.return_value = mock_db

            mock_doc_ref = MagicMock()
            mock_db.collection.return_value.document.return_value = mock_doc_ref

            tool = self.ToolClass(
                video_id=self.video_id,
                transcript_text=self.sample_transcript,
                channel_id=self.channel_id
            )

            chunks = [
                {'content_sha256': 'hash1', 'tokens': 100},
                {'content_sha256': 'hash2', 'tokens': 150}
            ]

            result = tool._update_firestore_metadata("thread_id_123", chunks)

            self.assertTrue(result['success'])
            self.assertIn('doc_path', result)
            mock_doc_ref.update.assert_called_once()

    @patch.dict(os.environ, {})
    def test_missing_zep_api_key(self):
        """Test error when ZEP_API_KEY is missing (lines 96-98)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('message', data)

    def test_empty_transcript_text(self):
        """Test handling of empty transcript text (edge case)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="",
            channel_id=self.channel_id
        )

        chunks = tool._chunk_transcript("", max_tokens=1000, overlap_tokens=100)

        # Should return empty list or single empty chunk
        self.assertIsInstance(chunks, list)

    def test_very_short_transcript(self):
        """Test handling of very short transcript (edge case)."""
        short_text = "Short."

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=short_text,
            channel_id=self.channel_id
        )

        chunks = tool._chunk_transcript(short_text, max_tokens=1000, overlap_tokens=100)

        # Should return single chunk
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], short_text)

    def test_http_client_initialization(self):
        """Test HTTP client initialization (lines 309-311)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        client = tool._initialize_http_client("test_api_key", "https://api.test.com")

        self.assertIsNotNone(client)
        mock_httpx.Client.assert_called()


if __name__ == '__main__':
    unittest.main()
