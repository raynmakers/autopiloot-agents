"""
Comprehensive test suite for EnqueueTranscription tool targeting 100% coverage.
Tests job creation, duplicate prevention, duration validation, and Firestore operations.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import sys


# Mock external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'dotenv': MagicMock(),
    'env_loader': MagicMock(),
    'loader': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create mocks for functions
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value="fake_value")
sys.modules['loader'].load_app_config = MagicMock(return_value={"idempotency": {"max_video_duration_sec": 4200}})
sys.modules['dotenv'].load_dotenv = MagicMock()
sys.modules['google.cloud.firestore'].SERVER_TIMESTAMP = "MOCK_TIMESTAMP"

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Import the tool after mocking
from scraper_agent.tools.enqueue_transcription import EnqueueTranscription

# Patch EnqueueTranscription __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.video_id = kwargs.get('video_id')

EnqueueTranscription.__init__ = patched_init


class TestEnqueueTranscription100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for EnqueueTranscription."""

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.firestore')
    @patch('scraper_agent.tools.enqueue_transcription.load_app_config')
    def test_successful_job_creation(self, mock_config, mock_firestore, mock_exists):
        """Test successful transcription job creation (lines 52-144)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock video document
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            'url': 'https://youtube.com/watch?v=test123',
            'title': 'Test Video',
            'channel_id': 'UC123',
            'duration_sec': 600,
            'published_at': '2024-01-01T00:00:00Z',
            'source': 'scrape'
        }
        mock_db.collection().document().get.return_value = mock_video_doc

        # Mock transcript check (doesn't exist)
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False
        mock_db.collection().document().get.side_effect = [mock_video_doc, mock_transcript_doc]

        # Mock existing jobs check (no existing jobs)
        mock_db.collection().collection().where().where().limit().get.return_value = []

        # Mock job reference
        mock_job_ref = MagicMock()
        mock_job_ref.id = 'job_123'
        mock_db.collection().collection().document.return_value = mock_job_ref

        # Mock batch
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch

        tool = EnqueueTranscription(video_id='test123')
        result = tool.run()
        data = json.loads(result)

        self.assertIn('job_id', data)
        self.assertEqual(data['video_id'], 'test123')
        self.assertEqual(data['status'], 'pending')
        mock_batch.commit.assert_called_once()

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.firestore')
    @patch('scraper_agent.tools.enqueue_transcription.load_app_config')
    def test_video_not_found(self, mock_config, mock_firestore, mock_exists):
        """Test error when video doesn't exist (lines 64-68)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        mock_video_doc = MagicMock()
        mock_video_doc.exists = False
        mock_db.collection().document().get.return_value = mock_video_doc

        tool = EnqueueTranscription(video_id='nonexistent')
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('does not exist', data['error'])
        self.assertIsNone(data['job_id'])

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.firestore')
    @patch('scraper_agent.tools.enqueue_transcription.load_app_config')
    def test_video_already_transcribed(self, mock_config, mock_firestore, mock_exists):
        """Test skipping when transcript already exists (lines 72-79)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock video exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'duration_sec': 600}

        # Mock transcript exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True

        mock_db.collection().document().get.side_effect = [mock_video_doc, mock_transcript_doc]

        tool = EnqueueTranscription(video_id='already_transcribed')
        result = tool.run()
        data = json.loads(result)

        self.assertIsNone(data['job_id'])
        self.assertIn('already transcribed', data['message'])

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.firestore')
    @patch('scraper_agent.tools.enqueue_transcription.load_app_config')
    def test_duplicate_job_prevention(self, mock_config, mock_firestore, mock_exists):
        """Test duplicate job prevention (lines 82-95)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock video exists
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'duration_sec': 600}

        # Mock transcript doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False

        mock_db.collection().document().get.side_effect = [mock_video_doc, mock_transcript_doc]

        # Mock existing job
        mock_existing_job = MagicMock()
        mock_existing_job.id = 'existing_job_123'
        mock_existing_job.to_dict.return_value = {'status': 'pending'}
        mock_db.collection().collection().where().where().limit().get.return_value = [mock_existing_job]

        tool = EnqueueTranscription(video_id='has_job')
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['job_id'], 'existing_job_123')
        self.assertIn('already exists', data['message'])
        self.assertEqual(data['existing_status'], 'pending')

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.firestore')
    @patch('scraper_agent.tools.enqueue_transcription.load_app_config')
    def test_duration_exceeds_maximum(self, mock_config, mock_firestore, mock_exists):
        """Test skipping when duration exceeds maximum (lines 97-104)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock video with excessive duration
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {'duration_sec': 5000}  # Exceeds 4200

        # Mock transcript doesn't exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False

        mock_db.collection().document().get.side_effect = [mock_video_doc, mock_transcript_doc]

        # Mock no existing jobs
        mock_db.collection().collection().where().where().limit().get.return_value = []

        tool = EnqueueTranscription(video_id='too_long')
        result = tool.run()
        data = json.loads(result)

        self.assertIsNone(data['job_id'])
        self.assertIn('exceeds maximum', data['message'])

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.firestore')
    @patch('scraper_agent.tools.enqueue_transcription.load_app_config')
    def test_batch_write_operations(self, mock_config, mock_firestore, mock_exists):
        """Test atomic batch write operations (lines 124-136)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            'url': 'https://youtube.com/watch?v=test',
            'title': 'Test',
            'duration_sec': 300,
            'published_at': '2024-01-01T00:00:00Z',
            'source': 'scrape'
        }

        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False

        mock_db.collection().document().get.side_effect = [mock_video_doc, mock_transcript_doc]
        mock_db.collection().collection().where().where().limit().get.return_value = []

        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch

        mock_job_ref = MagicMock()
        mock_job_ref.id = 'job_456'
        mock_db.collection().collection().document.return_value = mock_job_ref

        tool = EnqueueTranscription(video_id='test')
        result = tool.run()

        # Verify batch operations
        mock_batch.set.assert_called_once()
        mock_batch.update.assert_called_once()
        mock_batch.commit.assert_called_once()

    @patch('scraper_agent.tools.enqueue_transcription.load_app_config')
    def test_exception_handling(self, mock_config):
        """Test top-level exception handling (lines 146-150)."""
        mock_config.side_effect = Exception("Config error")

        tool = EnqueueTranscription(video_id='test')
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('Failed to enqueue transcription', data['error'])
        self.assertIsNone(data['job_id'])

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.firestore')
    def test_initialize_firestore_success(self, mock_firestore, mock_exists):
        """Test successful Firestore initialization (lines 152-171)."""
        mock_exists.return_value = True
        mock_client = MagicMock()
        mock_firestore.Client.return_value = mock_client

        tool = EnqueueTranscription(video_id='test')
        client = tool._initialize_firestore()

        self.assertIsNotNone(client)
        mock_firestore.Client.assert_called_once()

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    def test_initialize_firestore_file_not_found(self, mock_exists):
        """Test Firestore initialization with missing credentials (lines 167-168)."""
        mock_exists.return_value = False

        tool = EnqueueTranscription(video_id='test')

        with self.assertRaises(FileNotFoundError) as context:
            tool._initialize_firestore()
        self.assertIn('Service account file not found', str(context.exception))

    @patch('scraper_agent.tools.enqueue_transcription.os.path.exists')
    @patch('scraper_agent.tools.enqueue_transcription.get_required_env_var')
    def test_initialize_firestore_exception(self, mock_env, mock_exists):
        """Test Firestore initialization exception handling (lines 173-174)."""
        mock_exists.return_value = True
        mock_env.side_effect = Exception("Environment error")

        tool = EnqueueTranscription(video_id='test')

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn('Failed to initialize Firestore client', str(context.exception))


if __name__ == "__main__":
    unittest.main()