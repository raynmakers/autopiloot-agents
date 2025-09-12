"""
Integration tests for idempotency and naming utilities.
Tests the core functionality to ensure no duplicate processing occurs.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from typing import Optional, Dict, Any
from datetime import datetime

# Add the parent directory to the path to enable imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.idempotency import (
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
from config.loader import (
    load_app_config,
    get_max_video_duration,
    get_drive_naming_format,
    get_status_progression,
    ConfigValidationError
)


class TestVideoIdExtraction(unittest.TestCase):
    """Test YouTube video ID extraction from various URL formats."""
    
    def test_extract_video_id_watch_url(self):
        """Test extraction from standard watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id_from_url(url)
        self.assertEqual(video_id, "dQw4w9WgXcQ")
    
    def test_extract_video_id_short_url(self):
        """Test extraction from youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = extract_video_id_from_url(url)
        self.assertEqual(video_id, "dQw4w9WgXcQ")
    
    def test_extract_video_id_embed_url(self):
        """Test extraction from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        video_id = extract_video_id_from_url(url)
        self.assertEqual(video_id, "dQw4w9WgXcQ")
    
    def test_extract_video_id_with_params(self):
        """Test extraction from URL with additional parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s&list=PLtest"
        video_id = extract_video_id_from_url(url)
        self.assertEqual(video_id, "dQw4w9WgXcQ")
    
    def test_extract_video_id_invalid_url(self):
        """Test extraction from invalid URL returns None."""
        self.assertIsNone(extract_video_id_from_url("https://example.com"))
        self.assertIsNone(extract_video_id_from_url(""))
        self.assertIsNone(extract_video_id_from_url(None))
    
    def test_extract_video_id_edge_cases(self):
        """Test edge cases for video ID extraction."""
        # Non-string input
        self.assertIsNone(extract_video_id_from_url(123))
        
        # YouTube URL without video ID
        self.assertIsNone(extract_video_id_from_url("https://www.youtube.com/"))
        
        # Invalid video ID format
        self.assertIsNone(extract_video_id_from_url("https://www.youtube.com/watch?v=invalidid"))


class TestDriveFilenaming(unittest.TestCase):
    """Test Drive filename generation according to naming convention."""
    
    def test_generate_transcript_txt_filename(self):
        """Test generation of transcript text filename."""
        spec: FileNamingSpec = {
            "video_id": "dQw4w9WgXcQ",
            "date_yyyy_mm_dd": "2025-01-27",
            "type": "transcript_txt"
        }
        filename = generate_drive_filename(spec)
        self.assertEqual(filename, "dQw4w9WgXcQ_2025-01-27_transcript_txt.txt")
    
    def test_generate_transcript_json_filename(self):
        """Test generation of transcript JSON filename."""
        spec: FileNamingSpec = {
            "video_id": "test123",
            "date_yyyy_mm_dd": "2025-01-27",
            "type": "transcript_json"
        }
        filename = generate_drive_filename(spec)
        self.assertEqual(filename, "test123_2025-01-27_transcript_json.json")
    
    def test_generate_summary_md_filename(self):
        """Test generation of summary markdown filename."""
        spec: FileNamingSpec = {
            "video_id": "abc456",
            "date_yyyy_mm_dd": "2025-01-27",
            "type": "summary_md"
        }
        filename = generate_drive_filename(spec)
        self.assertEqual(filename, "abc456_2025-01-27_summary_md.md")
    
    def test_generate_summary_json_filename(self):
        """Test generation of summary JSON filename."""
        spec: FileNamingSpec = {
            "video_id": "xyz789",
            "date_yyyy_mm_dd": "2025-01-27",
            "type": "summary_json"
        }
        filename = generate_drive_filename(spec)
        self.assertEqual(filename, "xyz789_2025-01-27_summary_json.json")
    
    def test_date_formatting(self):
        """Test date formatting for filenames."""
        # Test with ISO8601 UTC timestamp
        date_str = get_date_for_filename("2025-01-27T13:45:00Z")
        self.assertEqual(date_str, "2025-01-27")
        
        # Test with None (current date)
        current_date = datetime.utcnow().strftime('%Y-%m-%d')
        self.assertEqual(get_date_for_filename(None), current_date)
        
        # Test with invalid timestamp (should fallback to current date)
        self.assertEqual(get_date_for_filename("invalid"), current_date)


class TestStatusProgression(unittest.TestCase):
    """Test video status progression and processing checks."""
    
    def test_is_video_processed_discovered(self):
        """Test status check for discovered videos."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "discovered"
        }
        
        # Discovered video should be processed for "discovered" status
        self.assertTrue(is_video_processed(video_record, "discovered"))
        
        # But not for higher statuses
        self.assertFalse(is_video_processed(video_record, "transcribed"))
        self.assertFalse(is_video_processed(video_record, "summarized"))
    
    def test_is_video_processed_transcribed(self):
        """Test status check for transcribed videos."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "transcribed"
        }
        
        # Transcribed video should be processed for discovered and transcribed
        self.assertTrue(is_video_processed(video_record, "discovered"))
        self.assertTrue(is_video_processed(video_record, "transcribed"))
        
        # But not for summarized
        self.assertFalse(is_video_processed(video_record, "summarized"))
    
    def test_is_video_processed_summarized(self):
        """Test status check for summarized videos."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "summarized"
        }
        
        # Summarized video should be processed for all statuses
        self.assertTrue(is_video_processed(video_record, "discovered"))
        self.assertTrue(is_video_processed(video_record, "transcribed"))
        self.assertTrue(is_video_processed(video_record, "summarized"))
    
    def test_is_video_processed_none_record(self):
        """Test status check with None record."""
        # None record should not be processed for any status
        self.assertFalse(is_video_processed(None, "discovered"))
        self.assertFalse(is_video_processed(None, "transcribed"))
        self.assertFalse(is_video_processed(None, "summarized"))
    
    def test_is_video_processed_no_status(self):
        """Test status check with record lacking status."""
        video_record: VideoRecord = {
            "video_id": "test123"
        }
        
        # Record without status should not be processed for any status
        self.assertFalse(is_video_processed(video_record, "discovered"))
        self.assertFalse(is_video_processed(video_record, "transcribed"))
        self.assertFalse(is_video_processed(video_record, "summarized"))


class TestTranscriptionSkipping(unittest.TestCase):
    """Test logic for skipping transcription based on various conditions."""
    
    def test_should_skip_transcription_no_record(self):
        """Test skipping transcription when no video record exists."""
        self.assertTrue(should_skip_transcription(None))
    
    def test_should_skip_transcription_already_transcribed(self):
        """Test skipping transcription when video already transcribed."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "transcribed",
            "duration_sec": 3000
        }
        
        self.assertTrue(should_skip_transcription(video_record))
    
    def test_should_skip_transcription_already_summarized(self):
        """Test skipping transcription when video already summarized."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "summarized",
            "duration_sec": 3000
        }
        
        self.assertTrue(should_skip_transcription(video_record))
    
    def test_should_skip_transcription_transcript_exists(self):
        """Test skipping transcription when transcript record exists."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "discovered",
            "duration_sec": 3000
        }
        
        transcript_record: TranscriptRecord = {
            "video_id": "test123",
            "transcript_drive_ids": {"txt": "file1", "json": "file2"},
            "digest": "abc123",
            "created_at": "2025-01-27T13:45:00Z"
        }
        
        self.assertTrue(should_skip_transcription(video_record, transcript_record))
    
    def test_should_skip_transcription_too_long(self):
        """Test skipping transcription for videos longer than 70 minutes."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "discovered",
            "duration_sec": 5000  # Over 4200 seconds (70 minutes)
        }
        
        self.assertTrue(should_skip_transcription(video_record))
    
    def test_should_not_skip_transcription_valid(self):
        """Test not skipping transcription for valid videos."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "discovered",
            "duration_sec": 3000  # Under 70 minutes
        }
        
        self.assertFalse(should_skip_transcription(video_record))


class TestSummarizationSkipping(unittest.TestCase):
    """Test logic for skipping summarization based on various conditions."""
    
    def test_should_skip_summarization_no_record(self):
        """Test skipping summarization when no video record exists."""
        self.assertTrue(should_skip_summarization(None))
    
    def test_should_skip_summarization_already_summarized(self):
        """Test skipping summarization when video already summarized."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "summarized"
        }
        
        self.assertTrue(should_skip_summarization(video_record))
    
    def test_should_skip_summarization_summary_exists(self):
        """Test skipping summarization when summary record exists."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "transcribed"
        }
        
        summary_record: SummaryRecord = {
            "video_id": "test123",
            "short": {"zep_doc_id": "zep123", "drive_id": "drive456"},
            "linkage": {"transcript_doc_ref": "ref123"},
            "rag_refs": [],
            "created_at": "2025-01-27T13:45:00Z"
        }
        
        self.assertTrue(should_skip_summarization(video_record, summary_record))
    
    def test_should_skip_summarization_not_transcribed(self):
        """Test skipping summarization when video not yet transcribed."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "discovered"
        }
        
        self.assertTrue(should_skip_summarization(video_record))
    
    def test_should_not_skip_summarization_valid(self):
        """Test not skipping summarization for valid transcribed videos."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "transcribed"
        }
        
        self.assertFalse(should_skip_summarization(video_record))


class TestIdempotencyKeys(unittest.TestCase):
    """Test idempotency key generation."""
    
    def test_create_idempotency_key(self):
        """Test creation of idempotency keys."""
        key = create_idempotency_key("test123", "transcription")
        self.assertEqual(key, "test123:transcription")
        
        key = create_idempotency_key("abc456", "summarization")
        self.assertEqual(key, "abc456:summarization")
    
    def test_idempotency_key_uniqueness(self):
        """Test that different operations create different keys."""
        video_id = "test123"
        key1 = create_idempotency_key(video_id, "transcription")
        key2 = create_idempotency_key(video_id, "summarization")
        
        self.assertNotEqual(key1, key2)
        self.assertEqual(key1, "test123:transcription")
        self.assertEqual(key2, "test123:summarization")


class TestConfigIntegration(unittest.TestCase):
    """Test integration with configuration loader."""
    
    def setUp(self):
        """Set up test configuration."""
        self.test_config = {
            "sheet": "test_sheet_id",
            "scraper": {"handles": ["@test"], "daily_limit_per_channel": 10},
            "llm": {"default": {"model": "gpt-4.1", "temperature": 0.2}},
            "notifications": {"slack": {"channel": "test-channel"}},
            "budgets": {"transcription_daily_usd": 5.0},
            "idempotency": {
                "max_video_duration_sec": 4200,
                "status_progression": ["discovered", "transcribed", "summarized"],
                "drive_naming_format": "{video_id}_{date}_{type}.{ext}"
            }
        }
    
    def test_get_max_video_duration_default(self):
        """Test getting max video duration with default value."""
        config = {}
        duration = get_max_video_duration(config)
        self.assertEqual(duration, 4200)  # Default 70 minutes
    
    def test_get_max_video_duration_configured(self):
        """Test getting max video duration from configuration."""
        duration = get_max_video_duration(self.test_config)
        self.assertEqual(duration, 4200)
    
    def test_get_drive_naming_format_default(self):
        """Test getting Drive naming format with default value."""
        config = {}
        format_str = get_drive_naming_format(config)
        self.assertEqual(format_str, "{video_id}_{date}_{type}.{ext}")
    
    def test_get_drive_naming_format_configured(self):
        """Test getting Drive naming format from configuration."""
        format_str = get_drive_naming_format(self.test_config)
        self.assertEqual(format_str, "{video_id}_{date}_{type}.{ext}")
    
    def test_get_status_progression_default(self):
        """Test getting status progression with default value."""
        config = {}
        progression = get_status_progression(config)
        self.assertEqual(progression, ["discovered", "transcribed", "summarized"])
    
    def test_get_status_progression_configured(self):
        """Test getting status progression from configuration."""
        progression = get_status_progression(self.test_config)
        self.assertEqual(progression, ["discovered", "transcribed", "summarized"])


class TestEndToEndIdempotency(unittest.TestCase):
    """End-to-end tests for idempotency behavior."""
    
    def test_video_processing_flow(self):
        """Test complete video processing flow with idempotency checks."""
        # Start with a discovered video
        video_record: VideoRecord = {
            "video_id": "test123",
            "url": "https://www.youtube.com/watch?v=test123",
            "title": "Test Video",
            "published_at": "2025-01-27T13:45:00Z",
            "channel_id": "channel123",
            "duration_sec": 3000,
            "source": "scrape",
            "status": "discovered",
            "created_at": "2025-01-27T13:45:00Z",
            "updated_at": "2025-01-27T13:45:00Z"
        }
        
        # Should not skip transcription initially
        self.assertFalse(should_skip_transcription(video_record))
        
        # Should skip summarization (not transcribed yet)
        self.assertTrue(should_skip_summarization(video_record))
        
        # Update status to transcribed
        video_record["status"] = "transcribed"
        
        # Should skip transcription now
        self.assertTrue(should_skip_transcription(video_record))
        
        # Should not skip summarization now
        self.assertFalse(should_skip_summarization(video_record))
        
        # Update status to summarized
        video_record["status"] = "summarized"
        
        # Should skip both transcription and summarization
        self.assertTrue(should_skip_transcription(video_record))
        self.assertTrue(should_skip_summarization(video_record))
    
    def test_drive_filename_generation_consistency(self):
        """Test that Drive filenames are generated consistently."""
        video_id = "test123"
        date = "2025-01-27"
        
        # Generate filenames for different types
        txt_spec: FileNamingSpec = {
            "video_id": video_id,
            "date_yyyy_mm_dd": date,
            "type": "transcript_txt"
        }
        
        json_spec: FileNamingSpec = {
            "video_id": video_id,
            "date_yyyy_mm_dd": date,
            "type": "transcript_json"
        }
        
        md_spec: FileNamingSpec = {
            "video_id": video_id,
            "date_yyyy_mm_dd": date,
            "type": "summary_md"
        }
        
        # Generate filenames
        txt_filename = generate_drive_filename(txt_spec)
        json_filename = generate_drive_filename(json_spec)
        md_filename = generate_drive_filename(md_spec)
        
        # Verify naming convention
        expected_prefix = f"{video_id}_{date}_"
        self.assertTrue(txt_filename.startswith(expected_prefix))
        self.assertTrue(json_filename.startswith(expected_prefix))
        self.assertTrue(md_filename.startswith(expected_prefix))
        
        # Verify extensions
        self.assertTrue(txt_filename.endswith(".txt"))
        self.assertTrue(json_filename.endswith(".json"))
        self.assertTrue(md_filename.endswith(".md"))
        
        # Verify uniqueness
        self.assertNotEqual(txt_filename, json_filename)
        self.assertNotEqual(txt_filename, md_filename)
        self.assertNotEqual(json_filename, md_filename)


class TestIdempotencyValidation(unittest.TestCase):
    """Test idempotency validation and error handling."""
    
    def test_invalid_video_status(self):
        """Test handling of invalid video status."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "invalid_status"  # type: ignore
        }
        
        # Should return False for invalid status
        self.assertFalse(is_video_processed(video_record, "discovered"))
        self.assertFalse(is_video_processed(video_record, "transcribed"))
        self.assertFalse(is_video_processed(video_record, "summarized"))
    
    def test_missing_duration_field(self):
        """Test handling of missing duration field."""
        video_record: VideoRecord = {
            "video_id": "test123",
            "status": "discovered"
            # Missing duration_sec field
        }
        
        # Should not skip transcription when duration is missing (defaults to 0)
        self.assertFalse(should_skip_transcription(video_record))
    
    def test_filename_generation_edge_cases(self):
        """Test filename generation with edge case inputs."""
        # Test with special characters in video ID (should be handled gracefully)
        spec: FileNamingSpec = {
            "video_id": "test-123_ABC",
            "date_yyyy_mm_dd": "2025-01-27",
            "type": "transcript_txt"
        }
        filename = generate_drive_filename(spec)
        self.assertEqual(filename, "test-123_ABC_2025-01-27_transcript_txt.txt")
        
        # Test with different date format (edge case)
        spec["date_yyyy_mm_dd"] = "2025-12-31"
        filename = generate_drive_filename(spec)
        self.assertEqual(filename, "test-123_ABC_2025-12-31_transcript_txt.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
