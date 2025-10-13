"""
Tests for SaveVideoMetadata status-aware deduplication.
Verifies that videos from sheets are skipped if already in pipeline.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys

# Mock all external dependencies before importing tool
mock_base_tool = MagicMock()
mock_field = Mock(return_value=None)

with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(BaseTool=mock_base_tool),
    'pydantic': MagicMock(Field=mock_field),
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'dotenv': MagicMock(),
    'env_loader': MagicMock(get_required_env_var=lambda x, y: 'mock_value'),
    'loader': MagicMock(load_app_config=lambda: {'idempotency': {'max_video_duration_sec': 4200}}),
    'audit_logger': MagicMock()
}):
    # Import tool after mocking
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), '..', '..',
        'scraper_agent', 'tools', 'save_video_metadata.py'
    )
    spec = importlib.util.spec_from_file_location("save_video_metadata", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SaveVideoMetadata = module.SaveVideoMetadata


class TestSaveVideoMetadataDeduplication(unittest.TestCase):
    """Test status-aware deduplication for sheet videos."""

    def _create_mock_firestore(self, video_exists=True, video_status='discovered'):
        """Helper to create mock Firestore with specified video status."""
        mock_doc = Mock()
        mock_doc.exists = video_exists
        if video_exists:
            mock_doc.to_dict.return_value = {
                'video_id': 'test123',
                'status': video_status,
                'source': 'scrape'
            }

        mock_doc_ref = Mock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_doc_ref

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        return mock_db, mock_doc_ref

    def test_sheet_video_skipped_when_transcription_queued(self):
        """Test that sheet video is skipped when video is already in transcription_queued status."""
        mock_db, mock_doc_ref = self._create_mock_firestore(
            video_exists=True,
            video_status='transcription_queued'
        )

        tool = SaveVideoMetadata(
            video_id='test123',
            url='https://www.youtube.com/watch?v=test123',
            title='Test Video',
            published_at='2025-01-15T12:00:00Z',
            duration_sec=1800,
            source='sheet',
            sheet_row_index=5,
            sheet_id='test-sheet-id'
        )

        with patch.object(tool, '_initialize_firestore', return_value=mock_db):
            result = tool.run()

        data = json.loads(result)
        self.assertEqual(data['operation'], 'skipped')
        self.assertEqual(data['status'], 'transcription_queued')
        self.assertIn('already in pipeline', data['message'])
        mock_doc_ref.set.assert_not_called()
        mock_doc_ref.update.assert_not_called()

    def test_sheet_video_skipped_when_transcribed(self):
        """Test that sheet video is skipped when video is already transcribed."""
        mock_db, mock_doc_ref = self._create_mock_firestore(
            video_exists=True,
            video_status='transcribed'
        )

        tool = SaveVideoMetadata(
            video_id='test456',
            url='https://www.youtube.com/watch?v=test456',
            title='Test Video',
            published_at='2025-01-15T12:00:00Z',
            duration_sec=1800,
            source='sheet',
            sheet_row_index=10,
            sheet_id='test-sheet-id'
        )

        with patch.object(tool, '_initialize_firestore', return_value=mock_db):
            result = tool.run()

        data = json.loads(result)
        self.assertEqual(data['operation'], 'skipped')
        self.assertEqual(data['status'], 'transcribed')

    def test_sheet_video_skipped_when_summarized(self):
        """Test that sheet video is skipped when video is already summarized."""
        mock_db, mock_doc_ref = self._create_mock_firestore(
            video_exists=True,
            video_status='summarized'
        )

        tool = SaveVideoMetadata(
            video_id='test789',
            url='https://www.youtube.com/watch?v=test789',
            title='Test Video',
            published_at='2025-01-15T12:00:00Z',
            duration_sec=1800,
            source='sheet',
            sheet_row_index=15,
            sheet_id='test-sheet-id'
        )

        with patch.object(tool, '_initialize_firestore', return_value=mock_db):
            result = tool.run()

        data = json.loads(result)
        self.assertEqual(data['operation'], 'skipped')
        self.assertEqual(data['status'], 'summarized')

    def test_sheet_video_skipped_when_rejected(self):
        """Test that sheet video is skipped when video was rejected as non-business."""
        mock_db, mock_doc_ref = self._create_mock_firestore(
            video_exists=True,
            video_status='rejected_non_business'
        )

        tool = SaveVideoMetadata(
            video_id='test999',
            url='https://www.youtube.com/watch?v=test999',
            title='Test Video',
            published_at='2025-01-15T12:00:00Z',
            duration_sec=1800,
            source='sheet',
            sheet_row_index=20,
            sheet_id='test-sheet-id'
        )

        with patch.object(tool, '_initialize_firestore', return_value=mock_db):
            result = tool.run()

        data = json.loads(result)
        self.assertEqual(data['operation'], 'skipped')
        self.assertEqual(data['status'], 'rejected_non_business')

    def test_sheet_video_processed_when_discovered_status(self):
        """Test that sheet video is processed normally when status is 'discovered'."""
        mock_db, mock_doc_ref = self._create_mock_firestore(
            video_exists=True,
            video_status='discovered'
        )

        tool = SaveVideoMetadata(
            video_id='test111',
            url='https://www.youtube.com/watch?v=test111',
            title='Test Video',
            published_at='2025-01-15T12:00:00Z',
            duration_sec=1800,
            source='sheet',
            sheet_row_index=25,
            sheet_id='test-sheet-id'
        )

        with patch.object(tool, '_initialize_firestore', return_value=mock_db):
            result = tool.run()

        data = json.loads(result)
        self.assertEqual(data['operation'], 'updated')
        mock_doc_ref.update.assert_called_once()

    def test_scrape_source_not_affected_by_deduplication(self):
        """Test that scrape source videos are not affected by status-aware deduplication."""
        mock_db, mock_doc_ref = self._create_mock_firestore(
            video_exists=True,
            video_status='transcription_queued'
        )

        tool = SaveVideoMetadata(
            video_id='test222',
            url='https://www.youtube.com/watch?v=test222',
            title='Test Video',
            published_at='2025-01-15T12:00:00Z',
            duration_sec=1800,
            source='scrape',  # Source is scrape, not sheet
            channel_id='test-channel-id'
        )

        with patch.object(tool, '_initialize_firestore', return_value=mock_db):
            result = tool.run()

        data = json.loads(result)
        # Should process the video normally (not skip)
        self.assertEqual(data['operation'], 'updated')
        mock_doc_ref.update.assert_called_once()

    def test_new_sheet_video_is_created(self):
        """Test that new sheet video is created when video doesn't exist."""
        mock_db, mock_doc_ref = self._create_mock_firestore(
            video_exists=False
        )

        tool = SaveVideoMetadata(
            video_id='test333',
            url='https://www.youtube.com/watch?v=test333',
            title='Test Video',
            published_at='2025-01-15T12:00:00Z',
            duration_sec=1800,
            source='sheet',
            sheet_row_index=30,
            sheet_id='test-sheet-id'
        )

        with patch.object(tool, '_initialize_firestore', return_value=mock_db):
            result = tool.run()

        data = json.loads(result)
        self.assertEqual(data['operation'], 'created')
        mock_doc_ref.set.assert_called_once()


if __name__ == '__main__':
    unittest.main()
