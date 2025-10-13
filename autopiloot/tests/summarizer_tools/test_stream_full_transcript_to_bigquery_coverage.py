"""
Comprehensive test suite for StreamFullTranscriptToBigQuery tool.
Tests BigQuery client initialization, table creation, metadata-only storage, and error handling.
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

# Mock google.cloud.bigquery
mock_bigquery = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.bigquery'] = mock_bigquery

# Mock tiktoken
mock_tiktoken = MagicMock()
mock_encoding = MagicMock()
mock_encoding.encode = MagicMock(return_value=[1, 2, 3, 4, 5] * 20)
mock_encoding.decode = MagicMock(side_effect=lambda tokens: "Decoded text " * (len(tokens) // 5))
mock_tiktoken.get_encoding = MagicMock(return_value=mock_encoding)
sys.modules['tiktoken'] = mock_tiktoken


class TestStreamFullTranscriptToBigQuery(unittest.TestCase):
    """Test suite for StreamFullTranscriptToBigQuery tool."""

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
            'stream_full_transcript_to_bigquery.py'
        )
        spec = importlib.util.spec_from_file_location("stream_full_transcript_to_bigquery", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.StreamFullTranscriptToBigQuery

        # Sample test data
        self.sample_transcript = "This is a test transcript. " * 100  # ~700 chars
        self.video_id = "test_video_123"
        self.channel_id = "UCtest123"

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project',
        'GOOGLE_APPLICATION_CREDENTIALS': '/fake/path/credentials.json'
    })
    @patch('importlib.import_module')
    def test_successful_streaming(self, mock_import):
        """Test successful transcript streaming to BigQuery (lines 71-224)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 1000,
            'rag.zep.transcripts.chunking.overlap_tokens': 100,
            'rag.bigquery.dataset': 'autopiloot',
            'rag.bigquery.location': 'EU',
            'rag.bigquery.tables.transcript_chunks': 'transcript_chunks',
            'rag.bigquery.write_disposition': 'WRITE_APPEND',
            'rag.bigquery.batch_size': 500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        # Mock dataset
        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset

        # Mock get_dataset (dataset exists)
        mock_client.get_dataset.return_value = mock_dataset

        # Mock table
        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table

        # Mock successful insert
        mock_client.insert_rows_json.return_value = []

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
        self.assertEqual(data['status'], 'streamed')
        self.assertIn('dataset', data)
        self.assertIn('table', data)
        self.assertIn('chunk_count', data)
        self.assertIn('inserted_count', data)
        self.assertGreater(data['chunk_count'], 0)
        self.assertEqual(data['inserted_count'], data['chunk_count'])

    @patch.dict(os.environ, {})
    def test_missing_gcp_project_id(self):
        """Test graceful skip when GCP_PROJECT_ID is not configured (lines 92-98)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'skipped')
        self.assertIn('BigQuery not configured', data['message'])

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_text_snippet_truncation(self, mock_import):
        """Test text_snippet truncation to 256 chars (metadata-only storage) (lines 128-142)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 50,
            'rag.zep.transcripts.chunking.overlap_tokens': 10,
            'rag.bigquery.dataset': 'autopiloot',
            'rag.bigquery.location': 'EU',
            'rag.bigquery.tables.transcript_chunks': 'transcript_chunks'
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        mock_client.get_dataset.return_value = mock_dataset

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table

        # Capture inserted rows
        inserted_rows = []
        def capture_insert(table_ref, rows_to_insert):
            inserted_rows.extend(rows_to_insert)
            return []  # Empty list means success

        mock_client.insert_rows_json.side_effect = capture_insert

        # Create long text that should be truncated
        long_text = "A" * 500  # 500 characters

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=long_text,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        # Verify text_snippet is truncated to 256 chars
        self.assertGreater(len(inserted_rows), 0)
        for row in inserted_rows:
            if row.get('text_snippet'):
                self.assertLessEqual(len(row['text_snippet']), 256,
                                   "text_snippet should be truncated to 256 characters")

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

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_dataset_creation(self, mock_import):
        """Test dataset creation when dataset doesn't exist (lines 226-243)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.bigquery.dataset': 'autopiloot',
            'rag.bigquery.location': 'EU'
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        # Simulate dataset not found
        from google.cloud import bigquery as bigquery_module
        mock_client.get_dataset.side_effect = Exception("Dataset not found")

        # Mock successful dataset creation
        mock_dataset = MagicMock()
        mock_client.create_dataset.return_value = mock_dataset

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="Short text",
            channel_id=self.channel_id
        )

        # Test _ensure_dataset_exists
        result = tool._ensure_dataset_exists(mock_client, 'autopiloot', 'EU')

        self.assertTrue(result['success'])
        mock_client.create_dataset.assert_called_once()

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_table_creation(self, mock_import):
        """Test table creation when table doesn't exist (lines 245-265)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=None)

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        # Mock SchemaField
        mock_bigquery.SchemaField = MagicMock(return_value=MagicMock())
        mock_bigquery.Table = MagicMock(return_value=MagicMock())

        # Simulate table not found
        mock_client.get_table.side_effect = Exception("Table not found")

        # Mock successful table creation
        mock_table = MagicMock()
        mock_client.create_table.return_value = mock_table

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="Short text",
            channel_id=self.channel_id
        )

        # Test _ensure_table_exists
        result = tool._ensure_table_exists(mock_client, 'autopiloot', 'transcript_chunks')

        self.assertTrue(result['success'])
        mock_client.create_table.assert_called_once()

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_idempotency_check_existing_chunks(self, mock_import):
        """Test idempotency check when chunks already exist (lines 144-167)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 1000,
            'rag.zep.transcripts.chunking.overlap_tokens': 100,
            'rag.bigquery.dataset': 'autopiloot',
            'rag.bigquery.tables.transcript_chunks': 'transcript_chunks'
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        mock_client.get_dataset.return_value = mock_dataset

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table

        # Mock query result showing existing chunks
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [
            MagicMock(chunk_count=5)
        ]
        mock_client.query.return_value = mock_query_job

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        # Should skip because chunks already exist
        self.assertEqual(data['status'], 'already_exists')
        self.assertEqual(data['existing_chunks'], 5)

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_partial_insertion_success(self, mock_import):
        """Test partial insertion when some rows fail (lines 175-191)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 50,
            'rag.zep.transcripts.chunking.overlap_tokens': 10,
            'rag.bigquery.dataset': 'autopiloot',
            'rag.bigquery.location': 'EU',
            'rag.bigquery.tables.transcript_chunks': 'transcript_chunks'
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        mock_client.get_dataset.return_value = mock_dataset

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table

        # Mock query result showing no existing chunks
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = []
        mock_client.query.return_value = mock_query_job

        # Mock partial insertion failure
        mock_client.insert_rows_json.return_value = [
            {"index": 1, "errors": [{"reason": "invalid", "message": "Invalid row"}]}
        ]

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="Short text for chunking. " * 20,
            channel_id=self.channel_id
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'partial')
        self.assertGreater(data['error_count'], 0)

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_iso_timestamp_parsing(self, mock_import):
        """Test ISO 8601 timestamp parsing (lines 128-137)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.zep.transcripts.chunking.max_tokens_per_chunk': 1000,
            'rag.zep.transcripts.chunking.overlap_tokens': 100,
            'rag.bigquery.dataset': 'autopiloot',
            'rag.bigquery.tables.transcript_chunks': 'transcript_chunks'
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        mock_dataset = MagicMock()
        mock_client.dataset.return_value = mock_dataset
        mock_client.get_dataset.return_value = mock_dataset

        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table

        mock_query_job = MagicMock()
        mock_query_job.result.return_value = []
        mock_client.query.return_value = mock_query_job

        # Capture inserted rows
        inserted_rows = []
        def capture_insert(table_ref, rows_to_insert):
            inserted_rows.extend(rows_to_insert)
            return []

        mock_client.insert_rows_json.side_effect = capture_insert

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="Short text",
            channel_id=self.channel_id,
            published_at="2025-10-12T15:30:45Z"
        )

        result = tool.run()
        data = json.loads(result)

        # Verify timestamp was parsed and formatted
        self.assertGreater(len(inserted_rows), 0)
        self.assertIn('published_at', inserted_rows[0])
        # Should be formatted as timestamp string
        self.assertIsInstance(inserted_rows[0]['published_at'], str)

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

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    def test_bigquery_client_initialization(self):
        """Test BigQuery client initialization (lines 280-282)."""
        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text=self.sample_transcript,
            channel_id=self.channel_id
        )

        client = tool._initialize_bigquery_client('test-project')

        self.assertIsNotNone(client)
        mock_bigquery.Client.assert_called_with(project='test-project')

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_dataset_already_exists(self, mock_import):
        """Test dataset existence check when dataset already exists."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=None)

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        # Mock dataset exists
        mock_dataset = MagicMock()
        mock_client.get_dataset.return_value = mock_dataset

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="Short text",
            channel_id=self.channel_id
        )

        result = tool._ensure_dataset_exists(mock_client, 'autopiloot', 'EU')

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'exists')
        mock_client.create_dataset.assert_not_called()

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('importlib.import_module')
    def test_table_already_exists(self, mock_import):
        """Test table existence check when table already exists."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=None)

        mock_import.return_value = mock_loader

        # Mock BigQuery client
        mock_client = MagicMock()
        mock_bigquery.Client.return_value = mock_client

        # Mock table exists
        mock_table = MagicMock()
        mock_client.get_table.return_value = mock_table

        tool = self.ToolClass(
            video_id=self.video_id,
            transcript_text="Short text",
            channel_id=self.channel_id
        )

        result = tool._ensure_table_exists(mock_client, 'autopiloot', 'transcript_chunks')

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'exists')
        mock_client.create_table.assert_not_called()


if __name__ == '__main__':
    unittest.main()
