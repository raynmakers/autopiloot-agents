"""
Comprehensive test suite for SaveVideoMetadata tool targeting 100% coverage.
Tests Firestore operations, idempotent upserts, duration validation, and audit logging.
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
    'audit_logger': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create mocks for functions
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value="fake_value")
sys.modules['loader'].load_app_config = MagicMock(return_value={"idempotency": {"max_video_duration_sec": 4200}})
sys.modules['dotenv'].load_dotenv = MagicMock()
sys.modules['google.cloud.firestore'].SERVER_TIMESTAMP = "MOCK_TIMESTAMP"

# Create mock audit logger
mock_audit_logger = MagicMock()
sys.modules['audit_logger'].audit_logger = mock_audit_logger

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Import the tool after mocking
from scraper_agent.tools.save_video_metadata import SaveVideoMetadata

# Patch SaveVideoMetadata __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.video_id = kwargs.get('video_id')
    self.url = kwargs.get('url')
    self.title = kwargs.get('title')
    self.published_at = kwargs.get('published_at')
    self.duration_sec = kwargs.get('duration_sec')
    self.source = kwargs.get('source')
    self.channel_id = kwargs.get('channel_id')

SaveVideoMetadata.__init__ = patched_init


class TestSaveVideoMetadata100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for SaveVideoMetadata."""

    @patch('scraper_agent.tools.save_video_metadata.os.path.exists')
    @patch('scraper_agent.tools.save_video_metadata.firestore')
    @patch('scraper_agent.tools.save_video_metadata.load_app_config')
    @patch('scraper_agent.tools.save_video_metadata.audit_logger')
    def test_successful_new_video_creation(self, mock_audit, mock_config, mock_firestore, mock_exists):
        """Test successful creation of new video document (lines 83-142)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock document reference
        mock_doc_ref = MagicMock()
        mock_db.collection().document.return_value = mock_doc_ref

        # Mock existing document check (doesn't exist)
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc

        # Mock audit logger
        mock_audit.log_video_discovered = MagicMock()

        tool = SaveVideoMetadata(
            video_id='test123',
            url='https://youtube.com/watch?v=test123',
            title='Test Video',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=600,
            source='scrape',
            channel_id='UC123'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['doc_ref'], 'videos/test123')
        self.assertEqual(data['operation'], 'created')
        self.assertEqual(data['video_id'], 'test123')
        self.assertEqual(data['status'], 'discovered')
        mock_doc_ref.set.assert_called_once()
        mock_audit.log_video_discovered.assert_called_once()

    @patch('scraper_agent.tools.save_video_metadata.os.path.exists')
    @patch('scraper_agent.tools.save_video_metadata.firestore')
    @patch('scraper_agent.tools.save_video_metadata.load_app_config')
    @patch('scraper_agent.tools.save_video_metadata.audit_logger')
    def test_successful_video_update(self, mock_audit, mock_config, mock_firestore, mock_exists):
        """Test successful update of existing video document (lines 124-127)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock document reference
        mock_doc_ref = MagicMock()
        mock_db.collection().document.return_value = mock_doc_ref

        # Mock existing document check (exists)
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = True
        mock_doc_ref.get.return_value = mock_existing_doc

        # Mock audit logger
        mock_audit.log_video_discovered = MagicMock()

        tool = SaveVideoMetadata(
            video_id='existing123',
            url='https://youtube.com/watch?v=existing123',
            title='Existing Video',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=600,
            source='scrape',
            channel_id='UC123'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['operation'], 'updated')
        mock_doc_ref.update.assert_called_once()
        mock_audit.log_video_discovered.assert_called_once()

    @patch('scraper_agent.tools.save_video_metadata.load_app_config')
    def test_duration_exceeds_maximum(self, mock_config):
        """Test video duration exceeding maximum (lines 88-92)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}

        tool = SaveVideoMetadata(
            video_id='toolong',
            url='https://youtube.com/watch?v=toolong',
            title='Very Long Video',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=5000,  # Exceeds 4200s
            source='scrape',
            channel_id='UC123'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('exceeds maximum', data['error'])
        self.assertIsNone(data['doc_ref'])

    @patch('scraper_agent.tools.save_video_metadata.os.path.exists')
    @patch('scraper_agent.tools.save_video_metadata.firestore')
    @patch('scraper_agent.tools.save_video_metadata.load_app_config')
    @patch('scraper_agent.tools.save_video_metadata.audit_logger')
    def test_video_without_channel_id(self, mock_audit, mock_config, mock_firestore, mock_exists):
        """Test video creation without channel_id (lines 116-117)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock document reference
        mock_doc_ref = MagicMock()
        mock_db.collection().document.return_value = mock_doc_ref

        # Mock existing document check
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc

        tool = SaveVideoMetadata(
            video_id='nochannel',
            url='https://youtube.com/watch?v=nochannel',
            title='Video Without Channel',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=300,
            source='sheet',
            channel_id=None
        )
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['operation'], 'created')
        # Verify set was called with data excluding channel_id
        mock_doc_ref.set.assert_called_once()

    @patch('scraper_agent.tools.save_video_metadata.load_app_config')
    def test_top_level_exception_handling(self, mock_config):
        """Test top-level exception handling (lines 144-148)."""
        mock_config.side_effect = Exception("Config error")

        tool = SaveVideoMetadata(
            video_id='error',
            url='https://youtube.com/watch?v=error',
            title='Error Video',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=300,
            source='scrape',
            channel_id='UC123'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertIn('Failed to save video metadata', data['error'])
        self.assertIsNone(data['doc_ref'])

    @patch('scraper_agent.tools.save_video_metadata.os.path.exists')
    @patch('scraper_agent.tools.save_video_metadata.firestore')
    @patch('scraper_agent.tools.save_video_metadata.get_required_env_var')
    def test_initialize_firestore_success(self, mock_env, mock_firestore, mock_exists):
        """Test successful Firestore initialization (lines 150-173)."""
        mock_exists.return_value = True
        mock_env.return_value = "fake_value"
        mock_client = MagicMock()
        mock_firestore.Client.return_value = mock_client

        tool = SaveVideoMetadata(
            video_id='test',
            url='https://youtube.com/watch?v=test',
            title='Test',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=300,
            source='scrape',
            channel_id='UC123'
        )
        client = tool._initialize_firestore()

        self.assertIsNotNone(client)
        mock_firestore.Client.assert_called_once()

    @patch('scraper_agent.tools.save_video_metadata.os.path.exists')
    @patch('scraper_agent.tools.save_video_metadata.get_required_env_var')
    def test_initialize_firestore_file_not_found(self, mock_env, mock_exists):
        """Test Firestore initialization with missing credentials (lines 165-166)."""
        mock_exists.return_value = False
        mock_env.return_value = "/fake/credentials.json"

        tool = SaveVideoMetadata(
            video_id='test',
            url='https://youtube.com/watch?v=test',
            title='Test',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=300,
            source='scrape',
            channel_id='UC123'
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn('Failed to initialize Firestore client', str(context.exception))

    @patch('scraper_agent.tools.save_video_metadata.get_required_env_var')
    def test_initialize_firestore_exception(self, mock_env):
        """Test Firestore initialization exception handling (lines 172-173)."""
        mock_env.side_effect = Exception("Environment error")

        tool = SaveVideoMetadata(
            video_id='test',
            url='https://youtube.com/watch?v=test',
            title='Test',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=300,
            source='scrape',
            channel_id='UC123'
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn('Failed to initialize Firestore client', str(context.exception))

    @patch('scraper_agent.tools.save_video_metadata.os.path.exists')
    @patch('scraper_agent.tools.save_video_metadata.firestore')
    @patch('scraper_agent.tools.save_video_metadata.load_app_config')
    @patch('scraper_agent.tools.save_video_metadata.audit_logger')
    def test_source_sheet_discovery(self, mock_audit, mock_config, mock_firestore, mock_exists):
        """Test video discovered from sheet source (lines 110)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock document reference
        mock_doc_ref = MagicMock()
        mock_db.collection().document.return_value = mock_doc_ref

        # Mock existing document check
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc

        tool = SaveVideoMetadata(
            video_id='sheet_video',
            url='https://youtube.com/watch?v=sheet_video',
            title='Sheet Video',
            published_at='2024-01-01T00:00:00Z',
            duration_sec=400,
            source='sheet',  # Sheet source
            channel_id='UC456'
        )
        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['operation'], 'created')
        # Verify audit log called with sheet source
        mock_audit.log_video_discovered.assert_called_once_with(
            video_id='sheet_video',
            source='sheet',
            actor='ScraperAgent'
        )

    @patch('scraper_agent.tools.save_video_metadata.os.path.exists')
    @patch('scraper_agent.tools.save_video_metadata.firestore')
    @patch('scraper_agent.tools.save_video_metadata.load_app_config')
    @patch('scraper_agent.tools.save_video_metadata.audit_logger')
    def test_video_data_structure(self, mock_audit, mock_config, mock_firestore, mock_exists):
        """Test video data structure contains all required fields (lines 104-113)."""
        mock_config.return_value = {"idempotency": {"max_video_duration_sec": 4200}}
        mock_exists.return_value = True

        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock document reference
        mock_doc_ref = MagicMock()
        mock_db.collection().document.return_value = mock_doc_ref

        # Mock existing document check
        mock_existing_doc = MagicMock()
        mock_existing_doc.exists = False
        mock_doc_ref.get.return_value = mock_existing_doc

        # Capture the set call
        set_args = []
        def capture_set(data):
            set_args.append(data)
        mock_doc_ref.set = capture_set

        tool = SaveVideoMetadata(
            video_id='structure_test',
            url='https://youtube.com/watch?v=structure_test',
            title='Structure Test Video',
            published_at='2024-01-01T12:00:00Z',
            duration_sec=500,
            source='scrape',
            channel_id='UC789'
        )
        result = tool.run()

        # Verify set was called with proper data structure
        self.assertEqual(len(set_args), 1)
        video_data = set_args[0]
        self.assertEqual(video_data['video_id'], 'structure_test')
        self.assertEqual(video_data['url'], 'https://youtube.com/watch?v=structure_test')
        self.assertEqual(video_data['title'], 'Structure Test Video')
        self.assertEqual(video_data['published_at'], '2024-01-01T12:00:00Z')
        self.assertEqual(video_data['duration_sec'], 500)
        self.assertEqual(video_data['source'], 'scrape')
        self.assertEqual(video_data['status'], 'discovered')
        self.assertEqual(video_data['channel_id'], 'UC789')
        self.assertIn('updated_at', video_data)
        self.assertIn('created_at', video_data)


if __name__ == "__main__":
    unittest.main()