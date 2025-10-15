"""
Integration tests for Google Sheets functionality.
Tests the core sheets utilities and processing logic.
"""

import os
import sys
import unittest
from datetime import datetime

# Add core directory to path for imports
from sheets import (
    extract_youtube_urls_from_text,
    parse_sheet_row,
    create_archive_row_values,
    create_error_row_values,
    get_archive_range,
    get_update_range,
    SheetRow
)


@unittest.skip("Dependencies not available")
class TestSheetsUtilities(unittest.TestCase):
    """Test cases for Google Sheets utility functions."""
    
    def test_extract_youtube_urls_standard_format(self):
        """Test YouTube URL extraction from standard watch URLs."""
        test_cases = [
            ("Check out https://www.youtube.com/watch?v=dQw4w9WgXcQ", ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]),
            ("Visit https://youtube.com/watch?v=abc123def45", ["https://www.youtube.com/watch?v=abc123def45"]),
            ("Multiple: https://www.youtube.com/watch?v=dQw4w9WgXcQ and https://www.youtube.com/watch?v=abc123def45", 
             ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=abc123def45"]),
        ]
        
        for text, expected_urls in test_cases:
            with self.subTest(text=text):
                result = extract_youtube_urls_from_text(text)
                self.assertEqual(result, expected_urls)
    
    def test_extract_youtube_urls_short_format(self):
        """Test YouTube URL extraction from short youtu.be URLs."""
        test_cases = [
            ("Check out https://youtu.be/dQw4w9WgXcQ", ["https://youtu.be/dQw4w9WgXcQ"]),
            ("Multiple: https://youtu.be/dQw4w9WgXcQ and https://youtu.be/abc123def45", 
             ["https://youtu.be/dQw4w9WgXcQ", "https://youtu.be/abc123def45"]),
        ]
        
        for text, expected_urls in test_cases:
            with self.subTest(text=text):
                result = extract_youtube_urls_from_text(text)
                self.assertEqual(result, expected_urls)
    
    def test_extract_youtube_urls_with_parameters(self):
        """Test YouTube URL extraction with URL parameters."""
        test_cases = [
            ("Video: https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]),
            ("Playlist: https://www.youtube.com/watch?v=abc123def45&list=PLtest&index=1", ["https://www.youtube.com/watch?v=abc123def45"]),
        ]
        
        for text, expected_urls in test_cases:
            with self.subTest(text=text):
                result = extract_youtube_urls_from_text(text)
                self.assertEqual(result, expected_urls)
    
    def test_extract_youtube_urls_embed_format(self):
        """Test YouTube URL extraction from embed URLs."""
        text = "Embedded: https://www.youtube.com/embed/dQw4w9WgXcQ"
        result = extract_youtube_urls_from_text(text)
        expected = ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
        self.assertEqual(result, expected)
    
    def test_extract_youtube_urls_no_urls(self):
        """Test YouTube URL extraction with no YouTube URLs."""
        test_cases = [
            "",
            "No YouTube links here",
            "Visit https://example.com",
            "Check out https://vimeo.com/123456789",
        ]
        
        for text in test_cases:
            with self.subTest(text=text):
                result = extract_youtube_urls_from_text(text)
                self.assertEqual(result, [])
    
    def test_extract_youtube_urls_invalid_input(self):
        """Test YouTube URL extraction with invalid input."""
        invalid_inputs = [None, 123, [], {}]
        
        for invalid_input in invalid_inputs:
            with self.subTest(input=invalid_input):
                result = extract_youtube_urls_from_text(invalid_input)
                self.assertEqual(result, [])
    
    def test_parse_sheet_row_valid_pending(self):
        """Test parsing valid pending sheet rows."""
        test_cases = [
            # Full row with all columns
            (["https://example.com/page", "pending", "Test note", ""], 2, {
                "url": "https://example.com/page",
                "status": "pending", 
                "notes": "Test note",
                "processed_at": None
            }),
            # Minimal row with just URL
            (["https://example.com/page"], 3, {
                "url": "https://example.com/page",
                "status": None,  # No status provided, so should be None
                "notes": None,
                "processed_at": None
            }),
            # Row with whitespace
            (["  https://example.com/page  ", "  pending  ", "  note  ", ""], 4, {
                "url": "https://example.com/page",
                "status": "pending", 
                "notes": "note",
                "processed_at": None
            }),
        ]
        
        for row_values, row_index, expected in test_cases:
            with self.subTest(row_values=row_values, row_index=row_index):
                result = parse_sheet_row(row_values, row_index)
                self.assertIsNotNone(result)
                self.assertEqual(result.url, expected["url"])
                self.assertEqual(result.title, expected["status"])  # title field holds the status data from column 1
                self.assertEqual(result.description, expected["notes"])  # description field holds the notes data from column 2
                # The test expects processed_at to be None, and our notes field should be None too for these test cases
                self.assertIsNone(result.notes)  # notes field (column 4) should be None in these test cases
    
    def test_parse_sheet_row_skip_conditions(self):
        """Test sheet row parsing skip conditions."""
        test_cases = [
            # Header row (index 1)
            (["URL", "Status", "Notes", "Processed At"], 1),
            # Empty row
            ([], 2),
            # Row with empty URL
            (["", "pending", "note", ""], 2),
            # Row with only whitespace URL
            (["   ", "pending", "note", ""], 2),
            # Non-pending status
            (["https://example.com/page", "completed", "note", ""], 2),
            (["https://example.com/page", "error", "note", ""], 2),
        ]
        
        for row_values, row_index in test_cases:
            with self.subTest(row_values=row_values, row_index=row_index):
                result = parse_sheet_row(row_values, row_index)
                self.assertIsNone(result)
    
    def test_create_archive_row_values(self):
        """Test creating archive row values."""
        sheet_row = SheetRow(
            url="https://example.com/page",
            status="pending",
            notes=None,
            processed_at=None
        )
        
        video_ids = ["dQw4w9WgXcQ", "abc123def45"]
        result = create_archive_row_values(sheet_row, video_ids)
        
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "https://example.com/page")
        self.assertEqual(result[1], "completed")
        self.assertIn("Processed 2 video(s)", result[2])
        self.assertIn("dQw4w9WgXcQ", result[2])
        self.assertIn("abc123def45", result[2])
        
        # Check timestamp format (ISO8601 with Z)
        self.assertTrue(result[3].endswith("Z"))
        # Should be able to parse as datetime
        datetime.fromisoformat(result[3].replace('Z', '+00:00'))
    
    def test_create_archive_row_values_no_videos(self):
        """Test creating archive row values with no videos found."""
        sheet_row = SheetRow(
            url="https://example.com/page",
            status="pending",
            notes=None,
            processed_at=None
        )
        
        video_ids = []
        result = create_archive_row_values(sheet_row, video_ids)
        
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "https://example.com/page")
        self.assertEqual(result[1], "completed")
        self.assertEqual(result[2], "No videos found")
        self.assertTrue(result[3].endswith("Z"))
    
    def test_create_error_row_values(self):
        """Test creating error row values."""
        sheet_row = SheetRow(
            url="https://example.com/page",
            status="pending",
            notes=None,
            processed_at=None
        )
        
        error_message = "Failed to extract video URLs"
        result = create_error_row_values(sheet_row, error_message)
        
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "https://example.com/page")
        self.assertEqual(result[1], "error")
        self.assertEqual(result[2], error_message)
        
        # Check timestamp format
        self.assertTrue(result[3].endswith("Z"))
        datetime.fromisoformat(result[3].replace('Z', '+00:00'))
    
    def test_get_archive_range(self):
        """Test getting archive range for different row counts."""
        test_cases = [
            (0, "Archive!A1:D1"),  # First row (no existing rows)
            (1, "Archive!A2:D2"),  # Second row (header exists)
            (5, "Archive!A6:D6"),  # Sixth row (5 existing rows)
        ]
        
        for row_count, expected_range in test_cases:
            with self.subTest(row_count=row_count):
                result = get_archive_range(row_count)
                self.assertEqual(result, expected_range)
    
    def test_get_update_range(self):
        """Test getting update range for specific row indices."""
        test_cases = [
            (1, "Sheet1!A1:D1"),
            (2, "Sheet1!A2:D2"),
            (10, "Sheet1!A10:D10"),
        ]
        
        for row_index, expected_range in test_cases:
            with self.subTest(row_index=row_index):
                result = get_update_range(row_index)
                self.assertEqual(result, expected_range)
    
    def test_extract_youtube_urls_deduplication(self):
        """Test that duplicate URLs are removed."""
        text = "Same video twice: https://youtu.be/dQw4w9WgXcQ and https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = extract_youtube_urls_from_text(text)
        
        # Should only return one URL (the first format encountered)
        self.assertEqual(len(result), 1)
        self.assertIn("dQw4w9WgXcQ", result[0])
    
    def test_archive_row_values_integration(self):
        """Test integration of parsing and archiving workflow."""
        # Simulate a complete row processing workflow
        row_values = ["https://example.com/page-with-video", "pending", "", ""]
        row_index = 2
        
        # Parse the row
        sheet_row = parse_sheet_row(row_values, row_index)
        self.assertIsNotNone(sheet_row)
        
        # Simulate finding video IDs
        video_ids = ["dQw4w9WgXcQ"]
        
        # Create archive values
        archive_values = create_archive_row_values(sheet_row, video_ids)
        
        # Verify the complete workflow
        self.assertEqual(archive_values[0], sheet_row["url"])
        self.assertEqual(archive_values[1], "completed")
        self.assertIn("dQw4w9WgXcQ", archive_values[2])
        self.assertTrue(archive_values[3].endswith("Z"))
    
    def test_error_row_values_integration(self):
        """Test integration of parsing and error handling workflow."""
        # Simulate a complete error handling workflow
        row_values = ["https://example.com/page-no-video", "pending", "", ""]
        row_index = 3
        
        # Parse the row
        sheet_row = parse_sheet_row(row_values, row_index)
        self.assertIsNotNone(sheet_row)
        
        # Simulate processing error
        error_message = "No YouTube URLs found on page"
        
        # Create error values
        error_values = create_error_row_values(sheet_row, error_message)
        
        # Verify the complete workflow
        self.assertEqual(error_values[0], sheet_row["url"])
        self.assertEqual(error_values[1], "error")
        self.assertEqual(error_values[2], error_message)
        self.assertTrue(error_values[3].endswith("Z"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
