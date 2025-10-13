"""
Comprehensive test suite for IndexFullTranscriptToOpenSearch tool.
Tests OpenSearch client initialization, index creation, document indexing, and error handling.
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

# Mock opensearchpy
mock_opensearchpy = MagicMock()
sys.modules['opensearchpy'] = mock_opensearchpy

# Mock tiktoken
mock_tiktoken = MagicMock()
mock_encoding = MagicMock()
mock_encoding.encode = MagicMock(return_value=[1, 2, 3, 4, 5] * 20)
mock_encoding.decode = MagicMock(side_effect=lambda tokens: "Decoded text " * (len(tokens) // 5))
mock_tiktoken.get_encoding = MagicMock(return_value=mock_encoding)
sys.modules['tiktoken'] = mock_tiktoken


class TestIndexFullTranscriptToOpenSearch(unittest.TestCase):
    """Test suite for IndexFullTranscriptToOpenSearch tool."""

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
            'index_full_transcript_to_opensearch.py'
        )
        spec = importlib.util.spec_from_file_location("index_full_transcript_to_opensearch", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.IndexFullTranscriptToOpenSearch

        # Sample test data
        self.sample_transcript = "This is a test transcript. " * 100  # ~700 chars
        self.video_id = "test_video_123"
        self.channel_id = "UCtest123"

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_api_key'
    })
    @patch('importlib.import_module')
    def test_successful_indexing(self, mock_import):
        """Test successful transcript indexing to OpenSearch (lines 71-223)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 1000,
            'rag.zep.transcripts.chunking.overlap_tokens': 100,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500,
            'rag.opensearch.connection.max_retries': 3,
            'rag.opensearch.connection.retry_on_timeout': True
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        # Mock index exists check
        mock_client.indices.exists.return_value = True

        # Mock successful indexing
        mock_client.index.return_value = {'result': 'created'}

        # Create tool instance
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id,
            title="Test Video",
            channel_handle="@TestChannel",
            published_at="2025-10-12T12:00:00Z",
            duration_sec=120
        )

        # Run tool
        result = tool.run()
        data = json.loads(result)

        # Assertions
        self.assertEqual(data['status'], 'indexed')
        self.assertIn('index_name', data)
        self.assertIn('chunk_count', data)
        self.assertIn('indexed_count', data)
        self.assertGreater(data['chunk_count'], 0)
        self.assertEqual(data['indexed_count'], data['chunk_count'])

    @patch.dict(os.environ, {})
    def test_missing_opensearch_host(self):
        """Test graceful skip when OPENSEARCH_HOST is not configured (lines 92-98)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'skipped')
        self.assertIn('OpenSearch not configured', data['message'])

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200'
    })
    def test_missing_authentication(self):
        """Test error when authentication is missing (lines 104-110)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('opensearch_auth_missing', data['error'])

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_api_key'
    })
    def test_chunking_logic(self):
        """Test token-aware chunking logic (lines 254-273)."""
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

        # Verify chunks are valid strings
        for chunk in chunks:
            self.assertIsInstance(chunk, str)
            self.assertGreater(len(chunk), 0)

    def test_token_counting(self):
        """Test token counting method (lines 275-278)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Test token counting
        token_count = tool._count_tokens("This is a test string")

        self.assertIsInstance(token_count, int)
        self.assertGreater(token_count, 0)

    def test_opensearch_client_initialization_with_api_key(self):
        """Test OpenSearch client initialization with API key auth (lines 280-321)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        client = tool._initialize_opensearch_client(
            "https://test.opensearch.com:9200",
            api_key="test_api_key",
            username=None,
            password=None
        )

        self.assertIsNotNone(client)
        mock_opensearchpy.OpenSearch.assert_called_once()

        # Verify auth parameter
        call_kwargs = mock_opensearchpy.OpenSearch.call_args[1]
        self.assertEqual(call_kwargs['http_auth'], ("api_key", "test_api_key"))

    def test_opensearch_client_initialization_with_basic_auth(self):
        """Test OpenSearch client initialization with username/password auth (lines 280-321)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        client = tool._initialize_opensearch_client(
            "https://test.opensearch.com:443",
            api_key=None,
            username="test_user",
            password="test_pass"
        )

        self.assertIsNotNone(client)

        # Verify basic auth
        call_kwargs = mock_opensearchpy.OpenSearch.call_args[1]
        self.assertEqual(call_kwargs['http_auth'], ("test_user", "test_pass"))

    def test_index_creation(self):
        """Test index creation when index doesn't exist (lines 323-355)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.return_value = {'acknowledged': True}

        result = tool._ensure_index_exists(mock_client, "test_index")

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'created')
        mock_client.indices.create.assert_called_once()

        # Verify mappings structure
        call_args = mock_client.indices.create.call_args
        self.assertIn('body', call_args[1])
        self.assertIn('mappings', call_args[1]['body'])

    def test_index_already_exists(self):
        """Test index existence check when index already exists (lines 323-355)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True

        result = tool._ensure_index_exists(mock_client, "test_index")

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'exists')
        mock_client.indices.create.assert_not_called()

    def test_index_creation_error(self):
        """Test error handling during index creation (lines 354-355)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch client with error
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.side_effect = Exception("Index creation failed")

        result = tool._ensure_index_exists(mock_client, "test_index")

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_document_indexing_success(self):
        """Test successful document indexing (lines 357-373)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_client.index.return_value = {'result': 'created'}

        doc = {
            '_id': 'test_doc_1',
            '_index': 'test_index',
            'video_id': self.video_id,
            'chunk_id': 'chunk_1',
            'text': 'Test chunk text',
            'tokens': 10
        }

        result = tool._index_document(mock_client, doc)

        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 'created')
        mock_client.index.assert_called_once()

    def test_document_indexing_error(self):
        """Test error handling during document indexing (lines 372-373)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch client with error
        mock_client = MagicMock()
        mock_client.index.side_effect = Exception("Indexing failed")

        doc = {
            '_id': 'test_doc_1',
            '_index': 'test_index',
            'video_id': self.video_id,
            'text': 'Test chunk'
        }

        result = tool._index_document(mock_client, doc)

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_api_key'
    })
    @patch('importlib.import_module')
    def test_partial_indexing_success(self, mock_import):
        """Test partial indexing when some documents fail (lines 174-191)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 50,
            'rag.zep.transcripts.chunking.overlap_tokens': 10,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500,
            'rag.opensearch.connection.max_retries': 3,
            'rag.opensearch.connection.retry_on_timeout': True
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        # Mock index exists
        mock_client.indices.exists.return_value = True

        # Mock partial success: first doc succeeds, second fails
        mock_client.index.side_effect = [
            {'result': 'created'},
            Exception("Indexing failed")
        ]

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="Short text for two chunks. " * 20,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'partial')
        self.assertGreater(data['error_count'], 0)
        self.assertLess(data['indexed_count'], data['chunk_count'])

    def test_empty_transcript_handling(self):
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

    def test_url_parsing_with_protocol(self):
        """Test URL parsing with https:// protocol (lines 285-290)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch
        mock_opensearchpy.OpenSearch.return_value = MagicMock()

        tool._initialize_opensearch_client(
            "https://opensearch.example.com:9200",
            api_key="test_key",
            username=None,
            password=None
        )

        # Verify host parsing
        call_kwargs = mock_opensearchpy.OpenSearch.call_args[1]
        self.assertEqual(call_kwargs['hosts'][0]['host'], 'opensearch.example.com')
        self.assertEqual(call_kwargs['hosts'][0]['port'], 9200)
        self.assertTrue(call_kwargs['use_ssl'])

    def test_url_parsing_without_protocol(self):
        """Test URL parsing without protocol (defaults to https) (lines 288-298)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        # Mock OpenSearch
        mock_opensearchpy.OpenSearch.return_value = MagicMock()

        tool._initialize_opensearch_client(
            "opensearch.example.com",
            api_key="test_key",
            username=None,
            password=None
        )

        # Verify defaults to HTTPS
        call_kwargs = mock_opensearchpy.OpenSearch.call_args[1]
        self.assertTrue(call_kwargs['use_ssl'])
        self.assertEqual(call_kwargs['hosts'][0]['port'], 443)


if __name__ == '__main__':
    unittest.main()
