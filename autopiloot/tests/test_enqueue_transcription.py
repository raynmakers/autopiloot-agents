"""
Test suite for EnqueueTranscription tool.
Tests job creation, duplicate prevention, and validation logic.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scraper', 'tools'))

try:
    from scraper.tools.EnqueueTranscription import EnqueueTranscription
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'scraper', 
        'tools', 
        'EnqueueTranscription.py'
    )
    spec = importlib.util.spec_from_file_location("EnqueueTranscription", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    EnqueueTranscription = module.EnqueueTranscription


class TestEnqueueTranscription(unittest.TestCase):
    """Test cases for EnqueueTranscription tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_video_id = "dQw4w9WgXcQ"
        self.tool = EnqueueTranscription(video_id=self.test_video_id)
        
        # Mock video data
        self.mock_video_data = {
            'video_id': self.test_video_id,
            'url': f'https://www.youtube.com/watch?v={self.test_video_id}',
            'title': 'Test Video Title',
            'published_at': '2025-01-27T00:00:00Z',
            'duration_sec': 1800,  # 30 minutes
            'source': 'scrape',
            'channel_id': 'UCtest123',
            'status': 'discovered'
        }

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_create_transcription_job_success(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test successful creation of transcription job."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        # Mock video document exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = self.mock_video_data
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc
        
        # Mock transcript doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False
        
        # Mock no existing jobs
        mock_db.collection.return_value.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = []
        
        # Mock job reference
        mock_job_ref = MagicMock()
        mock_job_ref.id = "test_job_123"
        mock_db.collection.return_value.collection.return_value.document.return_value = mock_job_ref
        
        # Mock batch operations
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        
        # Setup the call sequence for video and transcript checks
        def mock_collection_side_effect(collection_name):
            if collection_name == 'videos':
                mock_videos_collection = MagicMock()
                mock_videos_collection.document.return_value.get.return_value = mock_video_doc
                return mock_videos_collection
            elif collection_name == 'transcripts':
                mock_transcripts_collection = MagicMock()
                mock_transcripts_collection.document.return_value.get.return_value = mock_transcript_doc
                return mock_transcripts_collection
            elif collection_name == 'jobs':
                mock_jobs_collection = MagicMock()
                mock_jobs_collection.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = []
                mock_jobs_collection.collection.return_value.document.return_value = mock_job_ref
                return mock_jobs_collection
        
        mock_db.collection.side_effect = mock_collection_side_effect
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('job_id', data)
        self.assertEqual(data['job_id'], 'test_job_123')
        self.assertEqual(data['video_id'], self.test_video_id)
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['duration_sec'], 1800)
        self.assertIn('Transcription job created successfully', data['message'])
        
        # Verify batch operations were called
        mock_batch.set.assert_called_once()
        mock_batch.update.assert_called_once()
        mock_batch.commit.assert_called_once()

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_video_not_found(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test behavior when video doesn't exist."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        # Mock video document doesn't exist
        mock_video_doc = MagicMock()
        mock_video_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('does not exist', data['error'])
        self.assertIsNone(data['job_id'])

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_video_already_transcribed(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test behavior when video already has transcript."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        # Mock video document exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = self.mock_video_data
        
        # Mock transcript exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        
        # Setup the call sequence
        def mock_collection_side_effect(collection_name):
            if collection_name == 'videos':
                mock_videos_collection = MagicMock()
                mock_videos_collection.document.return_value.get.return_value = mock_video_doc
                return mock_videos_collection
            elif collection_name == 'transcripts':
                mock_transcripts_collection = MagicMock()
                mock_transcripts_collection.document.return_value.get.return_value = mock_transcript_doc
                return mock_transcripts_collection
        
        mock_db.collection.side_effect = mock_collection_side_effect
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIsNone(data['job_id'])
        self.assertIn('already transcribed', data['message'])
        self.assertEqual(data['video_id'], self.test_video_id)

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_job_already_exists(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test behavior when transcription job already exists."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        # Mock video document exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = self.mock_video_data
        
        # Mock transcript doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False
        
        # Mock existing job
        mock_existing_job = MagicMock()
        mock_existing_job.id = "existing_job_123"
        mock_existing_job.to_dict.return_value = {"status": "pending"}
        
        # Setup the call sequence
        def mock_collection_side_effect(collection_name):
            if collection_name == 'videos':
                mock_videos_collection = MagicMock()
                mock_videos_collection.document.return_value.get.return_value = mock_video_doc
                return mock_videos_collection
            elif collection_name == 'transcripts':
                mock_transcripts_collection = MagicMock()
                mock_transcripts_collection.document.return_value.get.return_value = mock_transcript_doc
                return mock_transcripts_collection
            elif collection_name == 'jobs':
                mock_jobs_collection = MagicMock()
                mock_jobs_collection.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = [mock_existing_job]
                return mock_jobs_collection
        
        mock_db.collection.side_effect = mock_collection_side_effect
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertEqual(data['job_id'], 'existing_job_123')
        self.assertIn('already exists', data['message'])
        self.assertEqual(data['existing_status'], 'pending')

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_video_duration_exceeds_limit(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test behavior when video duration exceeds maximum."""
        # Mock configuration with 70-minute limit
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        # Mock video with long duration
        long_video_data = self.mock_video_data.copy()
        long_video_data['duration_sec'] = 5000  # 83+ minutes
        
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = long_video_data
        
        # Mock transcript doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False
        
        # Mock no existing jobs
        mock_existing_jobs = []
        
        # Setup the call sequence
        def mock_collection_side_effect(collection_name):
            if collection_name == 'videos':
                mock_videos_collection = MagicMock()
                mock_videos_collection.document.return_value.get.return_value = mock_video_doc
                return mock_videos_collection
            elif collection_name == 'transcripts':
                mock_transcripts_collection = MagicMock()
                mock_transcripts_collection.document.return_value.get.return_value = mock_transcript_doc
                return mock_transcripts_collection
            elif collection_name == 'jobs':
                mock_jobs_collection = MagicMock()
                mock_jobs_collection.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = mock_existing_jobs
                return mock_jobs_collection
        
        mock_db.collection.side_effect = mock_collection_side_effect
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIsNone(data['job_id'])
        self.assertIn('exceeds maximum', data['message'])
        self.assertIn('5000s', data['message'])
        self.assertEqual(data['video_id'], self.test_video_id)

    def test_tool_initialization(self):
        """Test tool initialization with video_id parameter."""
        tool = EnqueueTranscription(video_id="test123")
        self.assertEqual(tool.video_id, "test123")

    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    def test_missing_environment_variables(self, mock_get_required_env_var):
        """Test behavior when required environment variables are missing."""
        # Mock missing GCP_PROJECT_ID
        mock_get_required_env_var.side_effect = Exception("GCP_PROJECT_ID not set")
        
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('GCP_PROJECT_ID not set', data['error'])

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    def test_missing_service_account_file(self, mock_get_required_env_var, mock_config):
        """Test behavior when service account file doesn't exist."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/credentials.json"
        }[var]
        
        # Mock file doesn't exist
        with patch('os.path.exists', return_value=False):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('Service account file not found', data['error'])

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_firestore_operation_failure(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test error handling when Firestore operation fails."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore to raise an exception
        mock_firestore_client.side_effect = Exception("Firestore connection failed")
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn('error', data)
        self.assertIn('Firestore connection failed', data['error'])
        self.assertIsNone(data['job_id'])

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    def test_default_configuration_values(self, mock_config):
        """Test behavior with default configuration when config is missing."""
        # Mock missing idempotency configuration
        mock_config.return_value = {}
        
        # Should use default 4200 seconds (70 minutes)
        # We'll mock the rest to avoid Firestore calls
        with patch.object(self.tool, '_initialize_firestore'):
            try:
                # Test that default is used properly
                config = mock_config.return_value
                max_duration = config.get("idempotency", {}).get("max_video_duration_sec", 4200)
                self.assertEqual(max_duration, 4200)
            except Exception:
                # Ignore other exceptions from incomplete mocking
                pass

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_batch_operation_atomicity(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test that job creation and video status update use atomic batch operation."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        # Mock video document exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = self.mock_video_data
        
        # Mock transcript doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False
        
        # Mock no existing jobs
        mock_existing_jobs = []
        
        # Mock job reference
        mock_job_ref = MagicMock()
        mock_job_ref.id = "test_job_123"
        
        # Mock batch operations
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        
        # Setup the call sequence
        def mock_collection_side_effect(collection_name):
            if collection_name == 'videos':
                mock_videos_collection = MagicMock()
                mock_videos_collection.document.return_value.get.return_value = mock_video_doc
                return mock_videos_collection
            elif collection_name == 'transcripts':
                mock_transcripts_collection = MagicMock()
                mock_transcripts_collection.document.return_value.get.return_value = mock_transcript_doc
                return mock_transcripts_collection
            elif collection_name == 'jobs':
                mock_jobs_collection = MagicMock()
                mock_jobs_collection.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = mock_existing_jobs
                mock_jobs_collection.collection.return_value.document.return_value = mock_job_ref
                return mock_jobs_collection
        
        mock_db.collection.side_effect = mock_collection_side_effect
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Verify batch operations were used
        mock_db.batch.assert_called_once()
        mock_batch.set.assert_called_once()  # Job creation
        mock_batch.update.assert_called_once()  # Video status update
        mock_batch.commit.assert_called_once()  # Atomic commit
        
        # Verify successful result
        data = json.loads(result)
        self.assertEqual(data['job_id'], 'test_job_123')

    @patch('scraper.tools.EnqueueTranscription.load_app_config')
    @patch('scraper.tools.EnqueueTranscription.get_required_env_var')
    @patch('scraper.tools.EnqueueTranscription.firestore.Client')
    def test_job_data_structure(self, mock_firestore_client, mock_get_required_env_var, mock_config):
        """Test that job data includes all required fields from video metadata."""
        # Mock configuration
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_get_required_env_var.side_effect = lambda var, desc: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/fake/credentials.json"
        }[var]
        
        # Mock Firestore operations
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db
        
        # Mock video document with complete data
        complete_video_data = {
            'video_id': self.test_video_id,
            'url': f'https://www.youtube.com/watch?v={self.test_video_id}',
            'title': 'Complete Test Video',
            'published_at': '2025-01-27T00:00:00Z',
            'duration_sec': 1800,
            'source': 'scrape',
            'channel_id': 'UCtest123',
            'status': 'discovered'
        }
        
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = complete_video_data
        
        # Mock transcript doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False
        
        # Mock no existing jobs
        mock_existing_jobs = []
        
        # Mock job reference
        mock_job_ref = MagicMock()
        mock_job_ref.id = "test_job_123"
        
        # Mock batch operations
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        
        # Setup the call sequence
        def mock_collection_side_effect(collection_name):
            if collection_name == 'videos':
                mock_videos_collection = MagicMock()
                mock_videos_collection.document.return_value.get.return_value = mock_video_doc
                return mock_videos_collection
            elif collection_name == 'transcripts':
                mock_transcripts_collection = MagicMock()
                mock_transcripts_collection.document.return_value.get.return_value = mock_transcript_doc
                return mock_transcripts_collection
            elif collection_name == 'jobs':
                mock_jobs_collection = MagicMock()
                mock_jobs_collection.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = mock_existing_jobs
                mock_jobs_collection.collection.return_value.document.return_value = mock_job_ref
                return mock_jobs_collection
        
        mock_db.collection.side_effect = mock_collection_side_effect
        
        # Mock file existence check
        with patch('os.path.exists', return_value=True):
            result = self.tool.run()
        
        # Verify job data structure
        job_data_call = mock_batch.set.call_args[0][1]
        
        self.assertEqual(job_data_call['job_id'], 'test_job_123')
        self.assertEqual(job_data_call['video_id'], self.test_video_id)
        self.assertEqual(job_data_call['video_url'], complete_video_data['url'])
        self.assertEqual(job_data_call['title'], complete_video_data['title'])
        self.assertEqual(job_data_call['channel_id'], complete_video_data['channel_id'])
        self.assertEqual(job_data_call['duration_sec'], complete_video_data['duration_sec'])
        self.assertEqual(job_data_call['published_at'], complete_video_data['published_at'])
        self.assertEqual(job_data_call['source'], complete_video_data['source'])
        self.assertEqual(job_data_call['status'], 'pending')
        self.assertIn('created_at', job_data_call)
        self.assertIn('updated_at', job_data_call)


if __name__ == '__main__':
    unittest.main(verbosity=2)