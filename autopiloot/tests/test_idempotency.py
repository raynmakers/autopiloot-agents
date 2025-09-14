"""
Integration tests for idempotency utilities.
Tests video ID extraction, filename generation, status management, and skip logic.
"""

import os
import sys
import unittest
from datetime import datetime
from typing import Optional

# Add core directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'core'))
from idempotency import (
    extract_video_id_from_url,
    generate_drive_filename,
    is_video_processed,
    should_skip_transcription,
    should_skip_summarization,
    get_date_for_filename,
    create_idempotency_key,
    VideoRecord,
    TranscriptRecord,
    SummaryRecord,
    FileNamingSpec,
    VideoStatus
)


class TestIdempotencyUtilities(unittest.TestCase):
    """Test cases for idempotency utilities."""
    
    def test_extract_video_id_standard_url(self):
        """Test video ID extraction from standard YouTube URLs."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/watch?v=abc123def45", "abc123def45"),
            ("http://www.youtube.com/watch?v=XYZ7890abcd", "XYZ7890abcd"),
        ]
        
        for url, expected_id in test_cases:
            with self.subTest(url=url):
                result = extract_video_id_from_url(url)
                self.assertEqual(result, expected_id)
    
    def test_extract_video_id_short_url(self):
        """Test video ID extraction from short YouTube URLs."""
        test_cases = [
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://youtu.be/abc123def45", "abc123def45"),
            ("https://youtu.be/XYZ7890abcd", "XYZ7890abcd"),
        ]
        
        for url, expected_id in test_cases:
            with self.subTest(url=url):
                result = extract_video_id_from_url(url)
                self.assertEqual(result, expected_id)
    
    def test_extract_video_id_embed_url(self):
        """Test video ID extraction from embed YouTube URLs."""
        test_cases = [
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://youtube.com/embed/abc123def45", "abc123def45"),
        ]
        
        for url, expected_id in test_cases:
            with self.subTest(url=url):
                result = extract_video_id_from_url(url)
                self.assertEqual(result, expected_id)
    
    def test_extract_video_id_with_parameters(self):
        """Test video ID extraction from URLs with additional parameters."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?list=PLtest&v=abc123def45&index=1", "abc123def45"),
            ("https://www.youtube.com/watch?feature=share&v=XYZ7890abcd", "XYZ7890abcd"),
        ]
        
        for url, expected_id in test_cases:
            with self.subTest(url=url):
                result = extract_video_id_from_url(url)
                self.assertEqual(result, expected_id)
    
    def test_extract_video_id_invalid_urls(self):
        """Test video ID extraction from invalid or non-YouTube URLs."""
        invalid_urls = [
            "",
            None,
            "not a url",
            "https://example.com",
            "https://www.youtube.com/watch",
            "https://www.youtube.com/watch?v=",
            "https://vimeo.com/123456789",
            "https://www.youtube.com/watch?v=short",
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                result = extract_video_id_from_url(url)
                self.assertIsNone(result)
    
    def test_generate_drive_filename_transcript_txt(self):
        """Test filename generation for transcript text files."""
        spec: FileNamingSpec = {
            "video_id": "dQw4w9WgXcQ",
            "date_yyyy_mm_dd": "2025-01-27",
            "type": "transcript_txt"
        }
        
        result = generate_drive_filename(spec)
        expected = "dQw4w9WgXcQ_2025-01-27_transcript_txt.txt"
        self.assertEqual(result, expected)
    
    def test_generate_drive_filename_transcript_json(self):
        """Test filename generation for transcript JSON files."""
        spec: FileNamingSpec = {
            "video_id": "abc123def456",
            "date_yyyy_mm_dd": "2025-02-15",
            "type": "transcript_json"
        }
        
        result = generate_drive_filename(spec)
        expected = "abc123def456_2025-02-15_transcript_json.json"
        self.assertEqual(result, expected)
    
    def test_generate_drive_filename_summary_md(self):
        """Test filename generation for summary markdown files."""
        spec: FileNamingSpec = {
            "video_id": "XYZ789",
            "date_yyyy_mm_dd": "2025-03-10",
            "type": "summary_md"
        }
        
        result = generate_drive_filename(spec)
        expected = "XYZ789_2025-03-10_summary_md.md"
        self.assertEqual(result, expected)
    
    def test_generate_drive_filename_summary_json(self):
        """Test filename generation for summary JSON files."""
        spec: FileNamingSpec = {
            "video_id": "test123",
            "date_yyyy_mm_dd": "2025-12-31",
            "type": "summary_json"
        }
        
        result = generate_drive_filename(spec)
        expected = "test123_2025-12-31_summary_json.json"
        self.assertEqual(result, expected)
    
    def test_is_video_processed_none_record(self):
        """Test video processing check with None record."""
        result = is_video_processed(None, "discovered")
        self.assertFalse(result)
    
    def test_is_video_processed_no_status(self):
        """Test video processing check with record missing status."""
        record: VideoRecord = {"video_id": "test"}
        result = is_video_processed(record, "discovered")
        self.assertFalse(result)
    
    def test_is_video_processed_status_progression(self):
        """Test video processing check with status progression."""
        test_cases = [
            # Current status: discovered
            ({"video_id": "test", "status": "discovered"}, "discovered", True),
            ({"video_id": "test", "status": "discovered"}, "transcribed", False),
            ({"video_id": "test", "status": "discovered"}, "summarized", False),
            
            # Current status: transcribed
            ({"video_id": "test", "status": "transcribed"}, "discovered", True),
            ({"video_id": "test", "status": "transcribed"}, "transcribed", True),
            ({"video_id": "test", "status": "transcribed"}, "summarized", False),
            
            # Current status: summarized
            ({"video_id": "test", "status": "summarized"}, "discovered", True),
            ({"video_id": "test", "status": "summarized"}, "transcribed", True),
            ({"video_id": "test", "status": "summarized"}, "summarized", True),
        ]
        
        for record_data, target_status, expected in test_cases:
            with self.subTest(current=record_data.get("status"), target=target_status):
                record: VideoRecord = record_data
                result = is_video_processed(record, target_status)
                self.assertEqual(result, expected)
    
    def test_should_skip_transcription_none_record(self):
        """Test transcription skip logic with None record."""
        result = should_skip_transcription(None)
        self.assertTrue(result)
    
    def test_should_skip_transcription_already_transcribed(self):
        """Test transcription skip logic for already transcribed videos."""
        record: VideoRecord = {
            "video_id": "test",
            "status": "transcribed",
            "duration_sec": 3000
        }
        
        result = should_skip_transcription(record)
        self.assertTrue(result)
    
    def test_should_skip_transcription_already_summarized(self):
        """Test transcription skip logic for already summarized videos."""
        record: VideoRecord = {
            "video_id": "test",
            "status": "summarized", 
            "duration_sec": 3000
        }
        
        result = should_skip_transcription(record)
        self.assertTrue(result)
    
    def test_should_skip_transcription_transcript_exists(self):
        """Test transcription skip logic when transcript record exists."""
        video_record: VideoRecord = {
            "video_id": "test",
            "status": "discovered",
            "duration_sec": 3000
        }
        
        transcript_record: TranscriptRecord = {
            "video_id": "test",
            "transcript_drive_ids": {"txt": "file1", "json": "file2"},
            "digest": "abc123",
            "created_at": "2025-01-27T10:00:00Z"
        }
        
        result = should_skip_transcription(video_record, transcript_record)
        self.assertTrue(result)
    
    def test_should_skip_transcription_duration_too_long(self):
        """Test transcription skip logic for videos longer than 70 minutes."""
        record: VideoRecord = {
            "video_id": "test",
            "status": "discovered",
            "duration_sec": 5000  # > 4200 seconds (70 minutes)
        }
        
        result = should_skip_transcription(record)
        self.assertTrue(result)
    
    def test_should_skip_transcription_should_process(self):
        """Test transcription skip logic for videos that should be processed."""
        record: VideoRecord = {
            "video_id": "test",
            "status": "discovered",
            "duration_sec": 3000  # < 4200 seconds
        }
        
        result = should_skip_transcription(record)
        self.assertFalse(result)
    
    def test_should_skip_summarization_none_record(self):
        """Test summarization skip logic with None record."""
        result = should_skip_summarization(None)
        self.assertTrue(result)
    
    def test_should_skip_summarization_already_summarized(self):
        """Test summarization skip logic for already summarized videos."""
        record: VideoRecord = {
            "video_id": "test",
            "status": "summarized"
        }
        
        result = should_skip_summarization(record)
        self.assertTrue(result)
    
    def test_should_skip_summarization_summary_exists(self):
        """Test summarization skip logic when summary record exists."""
        video_record: VideoRecord = {
            "video_id": "test",
            "status": "transcribed"
        }
        
        summary_record: SummaryRecord = {
            "video_id": "test",
            "short": {"zep_doc_id": "zep123", "drive_id": "drive123", "prompt_id": "prompt1"},
            "linkage": {"transcript_doc_ref": "ref1", "transcript_drive_id_txt": "txt1", "transcript_drive_id_json": "json1"},
            "rag_refs": ["ref1", "ref2"],
            "created_at": "2025-01-27T10:00:00Z"
        }
        
        result = should_skip_summarization(video_record, summary_record)
        self.assertTrue(result)
    
    def test_should_skip_summarization_not_transcribed(self):
        """Test summarization skip logic for videos not yet transcribed."""
        record: VideoRecord = {
            "video_id": "test",
            "status": "discovered"
        }
        
        result = should_skip_summarization(record)
        self.assertTrue(result)
    
    def test_should_skip_summarization_should_process(self):
        """Test summarization skip logic for videos that should be processed."""
        record: VideoRecord = {
            "video_id": "test",
            "status": "transcribed"
        }
        
        result = should_skip_summarization(record)
        self.assertFalse(result)
    
    def test_get_date_for_filename_with_iso_timestamp(self):
        """Test date extraction from ISO8601 timestamps."""
        test_cases = [
            ("2025-01-27T13:45:00Z", "2025-01-27"),
            ("2025-12-31T23:59:59Z", "2025-12-31"),
            ("2025-06-15T00:00:00Z", "2025-06-15"),
        ]
        
        for timestamp, expected_date in test_cases:
            with self.subTest(timestamp=timestamp):
                result = get_date_for_filename(timestamp)
                self.assertEqual(result, expected_date)
    
    def test_get_date_for_filename_invalid_timestamp(self):
        """Test date extraction with invalid timestamps falls back to current date."""
        invalid_timestamps = [
            "invalid",
            "2025-13-45",  # Invalid month/day
            "not a timestamp",
            "",
        ]
        
        current_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        for timestamp in invalid_timestamps:
            with self.subTest(timestamp=timestamp):
                result = get_date_for_filename(timestamp)
                self.assertEqual(result, current_date)
    
    def test_get_date_for_filename_none_timestamp(self):
        """Test date extraction with None timestamp uses current date."""
        current_date = datetime.utcnow().strftime('%Y-%m-%d')
        result = get_date_for_filename(None)
        self.assertEqual(result, current_date)
    
    def test_create_idempotency_key(self):
        """Test idempotency key generation."""
        test_cases = [
            ("dQw4w9WgXcQ", "transcription", "dQw4w9WgXcQ:transcription"),
            ("abc123", "summarization", "abc123:summarization"),
            ("video_id", "operation", "video_id:operation"),
        ]
        
        for video_id, operation, expected in test_cases:
            with self.subTest(video_id=video_id, operation=operation):
                result = create_idempotency_key(video_id, operation)
                self.assertEqual(result, expected)
    
    def test_video_status_type_constraints(self):
        """Test that VideoStatus type accepts only valid values."""
        # This is more of a documentation test since TypedDict doesn't enforce at runtime
        valid_statuses = ["discovered", "transcribed", "summarized"]
        
        for status in valid_statuses:
            # These should all be valid VideoStatus values
            record: VideoRecord = {
                "video_id": "test",
                "status": status
            }
            self.assertIn(status, valid_statuses)
    
    def test_drive_filename_spec_type_constraints(self):
        """Test FileNamingSpec type constraints."""
        valid_types = ["transcript_txt", "transcript_json", "summary_md", "summary_json"]
        
        for file_type in valid_types:
            spec: FileNamingSpec = {
                "video_id": "test",
                "date_yyyy_mm_dd": "2025-01-27",
                "type": file_type
            }
            filename = generate_drive_filename(spec)
            self.assertIn(file_type, filename)
    
    def test_integration_full_workflow(self):
        """Test integration of multiple idempotency functions in a workflow."""
        # Start with a YouTube URL
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id_from_url(url)
        self.assertEqual(video_id, "dQw4w9WgXcQ")
        
        # Create a video record
        video_record: VideoRecord = {
            "video_id": video_id,
            "status": "discovered",
            "duration_sec": 3000,
            "published_at": "2025-01-27T13:45:00Z"
        }
        
        # Check if we should skip transcription (should be False for new video)
        should_skip = should_skip_transcription(video_record)
        self.assertFalse(should_skip)
        
        # Generate transcript filename
        date = get_date_for_filename(video_record.get("published_at"))
        transcript_spec: FileNamingSpec = {
            "video_id": video_id,
            "date_yyyy_mm_dd": date,
            "type": "transcript_txt"
        }
        transcript_filename = generate_drive_filename(transcript_spec)
        self.assertEqual(transcript_filename, "dQw4w9WgXcQ_2025-01-27_transcript_txt.txt")
        
        # Create idempotency key for transcription
        transcription_key = create_idempotency_key(video_id, "transcription")
        self.assertEqual(transcription_key, "dQw4w9WgXcQ:transcription")
        
        # Simulate transcription completion - update status
        video_record["status"] = "transcribed"
        
        # Now transcription should be skipped
        should_skip_transcript = should_skip_transcription(video_record)
        self.assertTrue(should_skip_transcript)
        
        # But summarization should not be skipped
        should_skip_summary = should_skip_summarization(video_record)
        self.assertFalse(should_skip_summary)
        
        # Generate summary filename
        summary_spec: FileNamingSpec = {
            "video_id": video_id,
            "date_yyyy_mm_dd": date,
            "type": "summary_md"
        }
        summary_filename = generate_drive_filename(summary_spec)
        self.assertEqual(summary_filename, "dQw4w9WgXcQ_2025-01-27_summary_md.md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
