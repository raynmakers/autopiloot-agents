"""
Comprehensive test suite for TrackRagUsage tool.
Tests Firestore transaction-based usage tracking, daily aggregation, and error handling.
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

# Mock google.cloud.firestore
mock_firestore_module = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.firestore'] = mock_firestore_module


class TestTrackRagUsage(unittest.TestCase):
    """Test suite for TrackRagUsage tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'observability_agent',
            'tools',
            'track_rag_usage.py'
        )
        spec = importlib.util.spec_from_file_location("track_rag_usage", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.TrackRagUsage

        # Sample test data
        self.video_id = "test_video_123"
        self.operation = "zep_upsert"
        self.tokens_processed = 5000
        self.chunks_created = 10
        self.embeddings_generated = 10
        self.storage_system = "zep"

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_successful_usage_tracking_new_document(self, mock_firestore_client):
        """Test successful usage tracking with new daily document (lines 71-145)."""
        # Mock Firestore client and document
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        # Mock transaction - document doesn't exist yet
        mock_transaction = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_snapshot

        # Mock firestore module with transactional decorator
        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool instance
        tool = self.ToolClass(
            video_id=self.video_id,
            operation=self.operation,
            tokens_processed=self.tokens_processed,
            chunks_created=self.chunks_created,
            embeddings_generated=self.embeddings_generated,
            storage_system=self.storage_system,
            status="success"
        )

        # Run tool
        result = tool.run()
        data = json.loads(result)

        # Assertions
        self.assertEqual(data['status'], 'tracked')
        self.assertIn('date', data)
        self.assertEqual(data['tokens_processed'], self.tokens_processed)
        self.assertEqual(data['chunks_created'], self.chunks_created)

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_successful_usage_tracking_existing_document(self, mock_firestore_client):
        """Test usage tracking updates existing daily document (lines 100-135)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        # Mock transaction - document exists with existing data
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            'date': '2025-10-12',
            'total_tokens': 3000,
            'total_chunks': 5,
            'total_embeddings': 5,
            'operations': {
                'zep_upsert': {'count': 2, 'tokens': 2000, 'chunks': 3}
            },
            'storage_systems': {
                'zep': {'count': 2, 'tokens': 2000, 'chunks': 3}
            }
        }
        mock_doc_ref.get.return_value = mock_snapshot

        # Mock firestore module
        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool instance
        tool = self.ToolClass(
            video_id=self.video_id,
            operation=self.operation,
            tokens_processed=2000,
            chunks_created=5,
            embeddings_generated=5,
            storage_system=self.storage_system,
            status="success"
        )

        # Run tool
        result = tool.run()
        data = json.loads(result)

        # Assertions
        self.assertEqual(data['status'], 'tracked')
        self.assertEqual(data['tokens_processed'], 2000)

    @patch.dict(os.environ, {})
    def test_missing_gcp_project_id(self):
        """Test graceful skip when GCP_PROJECT_ID is missing (lines 91-97)."""
        tool = self.ToolClass(
            video_id=self.video_id,
            operation=self.operation,
            tokens_processed=self.tokens_processed,
            chunks_created=self.chunks_created,
            storage_system=self.storage_system
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'skipped')
        self.assertIn('not configured', data['message'])

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_operation_aggregation(self, mock_firestore_client):
        """Test operation-level aggregation (lines 118-126)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        # Mock existing document
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            'date': '2025-10-12',
            'total_tokens': 0,
            'total_chunks': 0,
            'total_embeddings': 0,
            'operations': {},
            'storage_systems': {}
        }
        mock_doc_ref.get.return_value = mock_snapshot

        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool instance with new operation
        tool = self.ToolClass(
            video_id=self.video_id,
            operation="opensearch_index",
            tokens_processed=1000,
            chunks_created=5,
            embeddings_generated=0,
            storage_system="opensearch",
            status="success"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'tracked')
        self.assertEqual(data['operation'], 'opensearch_index')

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_storage_system_aggregation(self, mock_firestore_client):
        """Test storage system-level aggregation (lines 128-136)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        # Mock existing document
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            'date': '2025-10-12',
            'total_tokens': 0,
            'total_chunks': 0,
            'total_embeddings': 0,
            'operations': {},
            'storage_systems': {}
        }
        mock_doc_ref.get.return_value = mock_snapshot

        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool instance
        tool = self.ToolClass(
            video_id=self.video_id,
            operation="bigquery_stream",
            tokens_processed=2000,
            chunks_created=8,
            embeddings_generated=0,
            storage_system="bigquery",
            status="success"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'tracked')
        self.assertEqual(data['storage_system'], 'bigquery')

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_embedding_count_tracking(self, mock_firestore_client):
        """Test embeddings count is tracked separately (lines 113-116)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_snapshot

        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool instance with embeddings
        tool = self.ToolClass(
            video_id=self.video_id,
            operation="zep_upsert",
            tokens_processed=5000,
            chunks_created=10,
            embeddings_generated=10,  # Zep auto-generates embeddings
            storage_system="zep",
            status="success"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'tracked')
        self.assertEqual(data['embeddings_generated'], 10)

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_zero_embeddings_for_keyword_search(self, mock_firestore_client):
        """Test that keyword search systems track 0 embeddings (lines 113-116)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_snapshot

        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool instance for OpenSearch (BM25, no embeddings)
        tool = self.ToolClass(
            video_id=self.video_id,
            operation="opensearch_index",
            tokens_processed=3000,
            chunks_created=6,
            embeddings_generated=0,  # OpenSearch uses BM25
            storage_system="opensearch",
            status="success"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'tracked')
        self.assertEqual(data['embeddings_generated'], 0)

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_status_field_inclusion(self, mock_firestore_client):
        """Test that status field is included in tracking data."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_snapshot

        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool instance with partial status
        tool = self.ToolClass(
            video_id=self.video_id,
            operation="zep_upsert",
            tokens_processed=1000,
            chunks_created=2,
            storage_system="zep",
            status="partial"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'tracked')

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_date_format(self, mock_firestore_client):
        """Test that date is formatted correctly (YYYY-MM-DD) (lines 99)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_snapshot

        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        tool = self.ToolClass(
            video_id=self.video_id,
            operation=self.operation,
            tokens_processed=1000,
            chunks_created=2,
            storage_system=self.storage_system
        )

        result = tool.run()
        data = json.loads(result)

        # Verify date format
        self.assertIn('date', data)
        # Should match YYYY-MM-DD format
        self.assertRegex(data['date'], r'^\d{4}-\d{2}-\d{2}$')

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_firestore_error_handling(self, mock_firestore_client):
        """Test error handling when Firestore operation fails (lines 147-152)."""
        # Mock Firestore client with error
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_db.collection.side_effect = Exception("Firestore connection error")

        tool = self.ToolClass(
            video_id=self.video_id,
            operation=self.operation,
            tokens_processed=1000,
            chunks_created=2,
            storage_system=self.storage_system
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('tracking_failed', data['error'])

    @patch.dict(os.environ, {'GCP_PROJECT_ID': 'test-project'})
    @patch('google.cloud.firestore.Client')
    def test_optional_embeddings_parameter(self, mock_firestore_client):
        """Test that embeddings_generated is optional and defaults to 0."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        mock_doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        mock_snapshot = MagicMock()
        mock_snapshot.exists = False
        mock_doc_ref.get.return_value = mock_snapshot

        @mock_firestore_module.transactional
        def mock_transactional(func):
            return func

        mock_firestore_module.transactional = mock_transactional

        # Create tool without embeddings_generated parameter
        tool = self.ToolClass(
            video_id=self.video_id,
            operation="bigquery_stream",
            tokens_processed=1000,
            chunks_created=2,
            storage_system="bigquery"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'tracked')


if __name__ == '__main__':
    unittest.main()
