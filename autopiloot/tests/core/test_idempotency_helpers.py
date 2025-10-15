"""
Unit tests for FirestoreExistenceChecker helpers in core/idempotency.py.

Tests cover:
- transcript_exists() helper
- video_exists() helper
- summary_exists() helper
- has_active_transcription_job() helper
- get_video_data() helper
- get_transcript_data() helper
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock google.cloud modules before importing idempotency
mock_firestore_client = MagicMock()
mock_google_cloud = MagicMock()
mock_firestore_v1 = MagicMock()
mock_base_query = MagicMock()

sys.modules['google'] = mock_google_cloud
sys.modules['google.cloud'] = mock_google_cloud
sys.modules['google.cloud.firestore_v1'] = mock_firestore_v1
sys.modules['google.cloud.firestore_v1.base_query'] = mock_base_query
sys.modules['firestore_client'] = mock_firestore_client

from core.idempotency import FirestoreExistenceChecker


class TestFirestoreExistenceChecker(unittest.TestCase):
    """Test suite for FirestoreExistenceChecker helpers."""

    def setUp(self):
        """Set up test fixtures before each test."""
        self.test_video_id = "dQw4w9WgXcQ"
        self.mock_db = MagicMock()

    def test_transcript_exists_returns_true(self):
        """Test transcript_exists returns True when transcript exists."""
        # Mock document that exists
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.transcript_exists(self.test_video_id, self.mock_db)

        # Verify
        self.assertTrue(result)
        self.mock_db.collection.assert_called_once_with('transcripts')
        self.mock_db.collection.return_value.document.assert_called_once_with(self.test_video_id)

    def test_transcript_exists_returns_false(self):
        """Test transcript_exists returns False when transcript doesn't exist."""
        # Mock document that doesn't exist
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.transcript_exists(self.test_video_id, self.mock_db)

        # Verify
        self.assertFalse(result)

    def test_transcript_exists_handles_exception(self):
        """Test transcript_exists handles exceptions gracefully."""
        # Mock exception during Firestore access
        self.mock_db.collection.side_effect = Exception("Firestore connection error")

        # Test
        result = FirestoreExistenceChecker.transcript_exists(self.test_video_id, self.mock_db)

        # Verify - should return False on error
        self.assertFalse(result)

    def test_video_exists_returns_true(self):
        """Test video_exists returns True when video exists."""
        # Mock document that exists
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.video_exists(self.test_video_id, self.mock_db)

        # Verify
        self.assertTrue(result)
        self.mock_db.collection.assert_called_once_with('videos')

    def test_video_exists_returns_false(self):
        """Test video_exists returns False when video doesn't exist."""
        # Mock document that doesn't exist
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.video_exists(self.test_video_id, self.mock_db)

        # Verify
        self.assertFalse(result)

    def test_summary_exists_returns_true(self):
        """Test summary_exists returns True when summary exists."""
        # Mock document that exists
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.summary_exists(self.test_video_id, self.mock_db)

        # Verify
        self.assertTrue(result)
        self.mock_db.collection.assert_called_once_with('summaries')

    def test_has_active_transcription_job_returns_true(self):
        """Test has_active_transcription_job returns True with job_id when job exists."""
        # Mock existing job
        mock_job = MagicMock()
        mock_job.id = "test_job_123"

        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.get.return_value = [mock_job]  # Return list with one job

        self.mock_db.collection.return_value = mock_query

        # Test
        has_job, job_id = FirestoreExistenceChecker.has_active_transcription_job(
            self.test_video_id, self.mock_db
        )

        # Verify
        self.assertTrue(has_job)
        self.assertEqual(job_id, "test_job_123")
        self.mock_db.collection.assert_called_once_with('jobs_transcription')

    def test_has_active_transcription_job_returns_false(self):
        """Test has_active_transcription_job returns False when no job exists."""
        # Mock no jobs found
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.get.return_value = []  # Empty list

        self.mock_db.collection.return_value = mock_query

        # Test
        has_job, job_id = FirestoreExistenceChecker.has_active_transcription_job(
            self.test_video_id, self.mock_db
        )

        # Verify
        self.assertFalse(has_job)
        self.assertIsNone(job_id)

    def test_has_active_transcription_job_handles_exception(self):
        """Test has_active_transcription_job handles exceptions gracefully."""
        # Mock exception
        self.mock_db.collection.side_effect = Exception("Query error")

        # Test
        has_job, job_id = FirestoreExistenceChecker.has_active_transcription_job(
            self.test_video_id, self.mock_db
        )

        # Verify - should return (False, None) on error
        self.assertFalse(has_job)
        self.assertIsNone(job_id)

    def test_get_video_data_returns_dict(self):
        """Test get_video_data returns dict when video exists."""
        # Mock video data
        video_data = {
            "video_id": self.test_video_id,
            "title": "Test Video",
            "duration_sec": 120,
            "channel_id": "UCtest"
        }

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = video_data

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.get_video_data(self.test_video_id, self.mock_db)

        # Verify
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Test Video")
        self.assertEqual(result["duration_sec"], 120)

    def test_get_video_data_returns_none(self):
        """Test get_video_data returns None when video doesn't exist."""
        # Mock document that doesn't exist
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.get_video_data(self.test_video_id, self.mock_db)

        # Verify
        self.assertIsNone(result)

    def test_get_transcript_data_returns_dict(self):
        """Test get_transcript_data returns dict when transcript exists."""
        # Mock transcript data
        transcript_data = {
            "video_id": self.test_video_id,
            "transcript_text": "This is a test transcript",
            "language": "en"
        }

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = transcript_data

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.get_transcript_data(self.test_video_id, self.mock_db)

        # Verify
        self.assertIsNotNone(result)
        self.assertEqual(result["transcript_text"], "This is a test transcript")
        self.assertEqual(result["language"], "en")

    def test_get_transcript_data_returns_none(self):
        """Test get_transcript_data returns None when transcript doesn't exist."""
        # Mock document that doesn't exist
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_ref = MagicMock()
        mock_ref.get.return_value = mock_doc

        self.mock_db.collection.return_value.document.return_value = mock_ref

        # Test
        result = FirestoreExistenceChecker.get_transcript_data(self.test_video_id, self.mock_db)

        # Verify
        self.assertIsNone(result)

    def test_get_transcript_data_handles_exception(self):
        """Test get_transcript_data handles exceptions gracefully."""
        # Mock exception
        self.mock_db.collection.side_effect = Exception("Database error")

        # Test
        result = FirestoreExistenceChecker.get_transcript_data(self.test_video_id, self.mock_db)

        # Verify - should return None on error
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
