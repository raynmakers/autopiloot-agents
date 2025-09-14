"""
Integration tests for reliability utilities.
Tests quota management, DLQ handling, and checkpoint functionality.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add core directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from reliability import (
    create_dlq_entry, should_retry_job, calculate_backoff_delay,
    create_quota_status, is_quota_exhausted, get_next_reset_time,
    create_checkpoint, should_pause_for_quota, get_resume_time,
    QuotaManager, format_error_for_dlq, DLQEntry, QuotaStatus, CheckpointData
)


class TestReliabilityUtilities(unittest.TestCase):
    """Test cases for reliability utility functions."""
    
    def test_create_dlq_entry_basic(self):
        """Test basic DLQ entry creation."""
        entry = create_dlq_entry(
            job_type="transcription",
            video_id="dQw4w9WgXcQ",
            reason="API quota exceeded",
            retry_count=2
        )
        
        self.assertEqual(entry["job_type"], "transcription")
        self.assertEqual(entry["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(entry["reason"], "API quota exceeded")
        self.assertEqual(entry["retry_count"], 2)
        self.assertTrue(entry["last_error_at"].endswith("Z"))
        
        # Verify timestamp is recent
        error_time = datetime.fromisoformat(entry["last_error_at"].replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=error_time.tzinfo)
        self.assertLess((now - error_time).total_seconds(), 5)
    
    def test_create_dlq_entry_with_details(self):
        """Test DLQ entry creation with error details."""
        error_details = {"status_code": 403, "api_error": "quotaExceeded"}
        
        entry = create_dlq_entry(
            job_type="youtube_discovery",
            video_id="abc123",
            reason="Quota limit reached",
            retry_count=1,
            error_details=error_details
        )
        
        self.assertEqual(entry["job_type"], "youtube_discovery")
        self.assertEqual(entry["video_id"], "abc123")
        self.assertEqual(entry["retry_count"], 1)
        self.assertEqual(entry["error_details"], error_details)
    
    def test_should_retry_job_logic(self):
        """Test retry decision logic."""
        # Should retry for counts below max
        self.assertTrue(should_retry_job(0, 3))  # First attempt
        self.assertTrue(should_retry_job(1, 3))  # Second attempt
        self.assertTrue(should_retry_job(2, 3))  # Third attempt
        
        # Should not retry when max reached
        self.assertFalse(should_retry_job(3, 3))  # Fourth attempt
        self.assertFalse(should_retry_job(4, 3))  # Beyond max
        
        # Edge cases
        self.assertFalse(should_retry_job(0, 0))  # No retries allowed
        self.assertTrue(should_retry_job(0, 1))   # One retry allowed
    
    def test_calculate_backoff_delay(self):
        """Test exponential backoff calculation."""
        test_cases = [
            (0, 60, 60),    # First retry: base delay
            (1, 60, 120),   # Second retry: 2x base
            (2, 60, 240),   # Third retry: 4x base
            (3, 60, 480),   # Fourth retry: 8x base
            (0, 30, 30),    # Different base delay
            (2, 30, 120),   # 4x base with different base
        ]
        
        for retry_count, base_delay, expected in test_cases:
            with self.subTest(retry_count=retry_count, base_delay=base_delay):
                result = calculate_backoff_delay(retry_count, base_delay)
                self.assertEqual(result, expected)
    
    def test_create_quota_status(self):
        """Test quota status creation."""
        quota = create_quota_status(
            service="youtube",
            requests_made=850,
            requests_limit=1000,
            quota_exhausted=False
        )
        
        self.assertEqual(quota["service"], "youtube")
        self.assertEqual(quota["requests_made"], 850)
        self.assertEqual(quota["requests_limit"], 1000)
        self.assertFalse(quota["quota_exhausted"])
        self.assertIsNone(quota["reset_time"])
    
    def test_is_quota_exhausted_by_flag(self):
        """Test quota exhaustion check by explicit flag."""
        # Quota marked as exhausted
        exhausted_quota = create_quota_status(
            service="youtube",
            requests_made=500,
            requests_limit=1000,
            quota_exhausted=True
        )
        
        self.assertTrue(is_quota_exhausted(exhausted_quota))
        
        # Quota not marked as exhausted
        available_quota = create_quota_status(
            service="youtube",
            requests_made=500,
            requests_limit=1000,
            quota_exhausted=False
        )
        
        self.assertFalse(is_quota_exhausted(available_quota))
    
    def test_is_quota_exhausted_by_limit(self):
        """Test quota exhaustion check by request limit."""
        # At limit
        at_limit_quota = create_quota_status(
            service="youtube",
            requests_made=1000,
            requests_limit=1000,
            quota_exhausted=False
        )
        
        self.assertTrue(is_quota_exhausted(at_limit_quota))
        
        # Over limit
        over_limit_quota = create_quota_status(
            service="youtube",
            requests_made=1100,
            requests_limit=1000,
            quota_exhausted=False
        )
        
        self.assertTrue(is_quota_exhausted(over_limit_quota))
        
        # Under limit
        under_limit_quota = create_quota_status(
            service="youtube",
            requests_made=800,
            requests_limit=1000,
            quota_exhausted=False
        )
        
        self.assertFalse(is_quota_exhausted(under_limit_quota))
    
    def test_is_quota_exhausted_with_reset_time(self):
        """Test quota exhaustion with reset time consideration."""
        # Future reset time - still exhausted
        future_reset = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        future_quota = create_quota_status(
            service="youtube",
            requests_made=1000,
            requests_limit=1000,
            quota_exhausted=True,
            reset_time=future_reset
        )
        
        self.assertTrue(is_quota_exhausted(future_quota))
        
        # Past reset time - should be available
        past_reset = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        past_quota = create_quota_status(
            service="youtube",
            requests_made=1000,
            requests_limit=1000,
            quota_exhausted=True,
            reset_time=past_reset
        )
        
        self.assertFalse(is_quota_exhausted(past_quota))
    
    def test_get_next_reset_time(self):
        """Test next reset time calculation."""
        reset_time_str = get_next_reset_time("youtube")
        
        # Should be valid ISO8601 format
        reset_time = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
        
        # Should be in the future
        now = datetime.utcnow().replace(tzinfo=reset_time.tzinfo)
        self.assertGreater(reset_time, now)
        
        # Should be within next 25 hours (allowing for timezone differences)
        max_expected = now + timedelta(hours=25)
        self.assertLess(reset_time, max_expected)
        
        # Should be at midnight (hour=0, minute=0, second=0)
        self.assertEqual(reset_time.hour, 0)
        self.assertEqual(reset_time.minute, 0)
        self.assertEqual(reset_time.second, 0)
    
    def test_create_checkpoint(self):
        """Test checkpoint creation."""
        checkpoint = create_checkpoint(
            service="youtube",
            last_published_at="2025-01-27T10:00:00Z",
            last_processed_id="dQw4w9WgXcQ"
        )
        
        self.assertEqual(checkpoint["service"], "youtube")
        self.assertEqual(checkpoint["last_published_at"], "2025-01-27T10:00:00Z")
        self.assertEqual(checkpoint["last_processed_id"], "dQw4w9WgXcQ")
        self.assertTrue(checkpoint["updated_at"].endswith("Z"))
        
        # Verify timestamp is recent
        update_time = datetime.fromisoformat(checkpoint["updated_at"].replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=update_time.tzinfo)
        self.assertLess((now - update_time).total_seconds(), 5)
    
    def test_create_checkpoint_minimal(self):
        """Test checkpoint creation with minimal data."""
        checkpoint = create_checkpoint(service="assemblyai")
        
        self.assertEqual(checkpoint["service"], "assemblyai")
        self.assertIsNone(checkpoint["last_published_at"])
        self.assertIsNone(checkpoint["last_processed_id"])
        self.assertTrue(checkpoint["updated_at"].endswith("Z"))
    
    def test_should_pause_for_quota(self):
        """Test quota pause decision logic."""
        # Should pause when quota exhausted
        exhausted_quota = create_quota_status(
            service="youtube",
            requests_made=1000,
            requests_limit=1000,
            quota_exhausted=True
        )
        
        self.assertTrue(should_pause_for_quota(exhausted_quota))
        
        # Should not pause when quota available
        available_quota = create_quota_status(
            service="youtube",
            requests_made=500,
            requests_limit=1000,
            quota_exhausted=False
        )
        
        self.assertFalse(should_pause_for_quota(available_quota))
    
    def test_get_resume_time(self):
        """Test resume time calculation."""
        # No reset time - should return None
        no_reset_quota = create_quota_status(
            service="youtube",
            requests_made=500,
            requests_limit=1000,
            quota_exhausted=False
        )
        
        self.assertIsNone(get_resume_time(no_reset_quota))
        
        # With reset time - should return parsed datetime
        reset_time_str = "2025-01-28T00:00:00Z"
        with_reset_quota = create_quota_status(
            service="youtube",
            requests_made=1000,
            requests_limit=1000,
            quota_exhausted=True,
            reset_time=reset_time_str
        )
        
        resume_time = get_resume_time(with_reset_quota)
        self.assertIsNotNone(resume_time)
        # Convert to UTC format for comparison
        expected_time = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
        self.assertEqual(resume_time, expected_time)
    
    def test_format_error_for_dlq(self):
        """Test error formatting for DLQ entries."""
        # Basic exception
        try:
            raise ValueError("Test error message")
        except Exception as e:
            error_msg = format_error_for_dlq(e, {})
            self.assertEqual(error_msg, "ValueError: Test error message")
        
        # Exception with context
        try:
            raise ConnectionError("Network timeout")
        except Exception as e:
            context = {"video_id": "abc123", "attempt": 3}
            error_msg = format_error_for_dlq(e, context)
            expected = "ConnectionError: Network timeout | Context: video_id=abc123, attempt=3"
            self.assertEqual(error_msg, expected)


class TestQuotaManager(unittest.TestCase):
    """Test cases for QuotaManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.quota_manager = QuotaManager()
    
    def test_track_request_new_service(self):
        """Test tracking requests for a new service."""
        quota = self.quota_manager.track_request("youtube", 1000)
        
        self.assertEqual(quota["service"], "youtube")
        self.assertEqual(quota["requests_made"], 1)
        self.assertEqual(quota["requests_limit"], 1000)
        self.assertFalse(quota["quota_exhausted"])
    
    def test_track_request_existing_service(self):
        """Test tracking multiple requests for existing service."""
        # First request
        quota1 = self.quota_manager.track_request("youtube", 1000)
        self.assertEqual(quota1["requests_made"], 1)
        
        # Second request
        quota2 = self.quota_manager.track_request("youtube", 1000)
        self.assertEqual(quota2["requests_made"], 2)
        
        # Quota status should be the same object
        self.assertIs(quota1, quota2)
    
    def test_track_request_quota_exhaustion(self):
        """Test quota exhaustion detection."""
        # Track requests up to limit
        for i in range(3):
            quota = self.quota_manager.track_request("test_service", 3)
            if i < 2:
                self.assertFalse(quota["quota_exhausted"])
            else:
                self.assertTrue(quota["quota_exhausted"])
                self.assertIsNotNone(quota["reset_time"])
    
    def test_is_service_available_new_service(self):
        """Test service availability for new service."""
        self.assertTrue(self.quota_manager.is_service_available("new_service"))
    
    def test_is_service_available_within_limit(self):
        """Test service availability within quota limit."""
        self.quota_manager.track_request("youtube", 1000)
        self.assertTrue(self.quota_manager.is_service_available("youtube"))
    
    def test_is_service_available_exhausted(self):
        """Test service availability when quota exhausted."""
        # Exhaust quota
        for _ in range(3):
            self.quota_manager.track_request("limited_service", 3)
        
        self.assertFalse(self.quota_manager.is_service_available("limited_service"))
    
    def test_get_quota_info_existing(self):
        """Test getting quota info for existing service."""
        original_quota = self.quota_manager.track_request("youtube", 1000)
        retrieved_quota = self.quota_manager.get_quota_info("youtube")
        
        self.assertIs(original_quota, retrieved_quota)
    
    def test_get_quota_info_nonexistent(self):
        """Test getting quota info for non-existent service."""
        quota_info = self.quota_manager.get_quota_info("nonexistent")
        self.assertIsNone(quota_info)


if __name__ == "__main__":
    unittest.main(verbosity=2)
