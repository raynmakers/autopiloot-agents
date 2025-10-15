"""
Unit tests for core/time_utils.py standardized timestamp handling.

Tests cover:
- now() function
- to_iso8601_z() formatting
- parse_iso8601_z() parsing
- Round-trip conversions
"""

import unittest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.time_utils import now, to_iso8601_z, parse_iso8601_z


class TestTimeUtils(unittest.TestCase):
    """Test suite for time_utils helpers."""

    def test_now_returns_utc_datetime(self):
        """Test now() returns timezone-aware UTC datetime."""
        current_time = now()

        # Verify it's a datetime object
        self.assertIsInstance(current_time, datetime)

        # Verify it has timezone info
        self.assertIsNotNone(current_time.tzinfo)

        # Verify it's UTC
        self.assertEqual(current_time.tzinfo, timezone.utc)

    def test_to_iso8601_z_formats_correctly(self):
        """Test to_iso8601_z() produces correct ISO 8601 format with Z suffix."""
        # Test with a known datetime
        dt = datetime(2025, 10, 15, 14, 30, 45, tzinfo=timezone.utc)
        iso_string = to_iso8601_z(dt)

        # Verify format
        self.assertEqual(iso_string, "2025-10-15T14:30:45Z")

        # Verify ends with Z
        self.assertTrue(iso_string.endswith('Z'))

    def test_to_iso8601_z_handles_naive_datetime(self):
        """Test to_iso8601_z() assumes UTC for naive datetimes."""
        # Naive datetime (no timezone info)
        dt_naive = datetime(2025, 10, 15, 14, 30, 45)
        iso_string = to_iso8601_z(dt_naive)

        # Should format as if it were UTC
        self.assertEqual(iso_string, "2025-10-15T14:30:45Z")

    def test_parse_iso8601_z_basic_format(self):
        """Test parse_iso8601_z() parses basic Z-suffix format."""
        iso_string = "2025-10-15T14:30:45Z"
        dt = parse_iso8601_z(iso_string)

        # Verify it's a datetime object
        self.assertIsInstance(dt, datetime)

        # Verify it's timezone-aware
        self.assertIsNotNone(dt.tzinfo)

        # Verify it's UTC
        self.assertEqual(dt.tzinfo, timezone.utc)

        # Verify values
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 10)
        self.assertEqual(dt.day, 15)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.second, 45)

    def test_parse_iso8601_z_with_microseconds(self):
        """Test parse_iso8601_z() parses format with microseconds."""
        iso_string = "2025-10-15T14:30:45.123456Z"
        dt = parse_iso8601_z(iso_string)

        # Verify microseconds
        self.assertEqual(dt.microsecond, 123456)

    def test_parse_iso8601_z_with_plus_offset(self):
        """Test parse_iso8601_z() parses +00:00 offset format."""
        iso_string = "2025-10-15T14:30:45+00:00"
        dt = parse_iso8601_z(iso_string)

        # Should convert to UTC
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(dt.hour, 14)

    def test_round_trip_conversion(self):
        """Test round-trip conversion: now() → to_iso8601_z() → parse_iso8601_z()."""
        # Get current time
        original_dt = now()

        # Convert to ISO string
        iso_string = to_iso8601_z(original_dt)

        # Parse back to datetime
        parsed_dt = parse_iso8601_z(iso_string)

        # Verify they match (within 1 second due to microsecond truncation in strftime)
        time_diff = abs((original_dt - parsed_dt).total_seconds())
        self.assertLess(time_diff, 1.0)

    def test_round_trip_with_known_datetime(self):
        """Test round-trip with a known datetime value."""
        # Known datetime
        original_dt = datetime(2025, 10, 15, 14, 30, 45, tzinfo=timezone.utc)

        # Convert to ISO string
        iso_string = to_iso8601_z(original_dt)

        # Parse back
        parsed_dt = parse_iso8601_z(iso_string)

        # Verify exact match
        self.assertEqual(original_dt, parsed_dt)

    def test_parse_iso8601_z_raises_on_invalid(self):
        """Test parse_iso8601_z() raises ValueError for invalid input."""
        invalid_strings = [
            "not a date",
            "2025-99-99T99:99:99Z",
            ""
        ]

        for invalid_string in invalid_strings:
            with self.subTest(invalid_string=invalid_string):
                with self.assertRaises(ValueError):
                    parse_iso8601_z(invalid_string)

    def test_multiple_iso_formats(self):
        """Test parse_iso8601_z() handles multiple ISO 8601 variants."""
        test_cases = [
            ("2025-10-15T14:30:45Z", 2025, 10, 15, 14, 30, 45),
            ("2025-10-15T14:30:45.123456Z", 2025, 10, 15, 14, 30, 45),
            ("2025-10-15T14:30:45+00:00", 2025, 10, 15, 14, 30, 45),
            ("2025-10-15T14:30:45.123456+00:00", 2025, 10, 15, 14, 30, 45),
        ]

        for iso_string, year, month, day, hour, minute, second in test_cases:
            with self.subTest(iso_string=iso_string):
                dt = parse_iso8601_z(iso_string)
                self.assertEqual(dt.year, year)
                self.assertEqual(dt.month, month)
                self.assertEqual(dt.day, day)
                self.assertEqual(dt.hour, hour)
                self.assertEqual(dt.minute, minute)
                self.assertEqual(dt.second, second)
                self.assertEqual(dt.tzinfo, timezone.utc)

    def test_consistency_across_calls(self):
        """Test that to_iso8601_z produces consistent output for same input."""
        dt = datetime(2025, 10, 15, 14, 30, 45, tzinfo=timezone.utc)

        iso1 = to_iso8601_z(dt)
        iso2 = to_iso8601_z(dt)

        self.assertEqual(iso1, iso2)


if __name__ == "__main__":
    unittest.main()
