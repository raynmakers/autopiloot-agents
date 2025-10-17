"""
Unit tests for core/json_response.py standard JSON envelope helper.
Tests ok(), fail(), is_ok(), get_data(), and get_error() functions.
"""

import unittest
import json
import sys
import os

# Add core directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.json_response import ok, fail, is_ok, get_data, get_error


class TestJsonResponse(unittest.TestCase):
    """Test standard JSON response envelope functions."""

    def test_ok_with_dict_data(self):
        """Test ok() with dictionary data."""
        result = ok({"video_id": "abc123", "status": "transcribed"})
        data = json.loads(result)

        self.assertTrue(data["ok"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["data"]["video_id"], "abc123")
        self.assertEqual(data["data"]["status"], "transcribed")

    def test_ok_with_list_data(self):
        """Test ok() with list data."""
        result = ok([1, 2, 3, 4, 5])
        data = json.loads(result)

        self.assertTrue(data["ok"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["data"], [1, 2, 3, 4, 5])

    def test_ok_with_string_data(self):
        """Test ok() with string data."""
        result = ok("Operation completed successfully")
        data = json.loads(result)

        self.assertTrue(data["ok"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["data"], "Operation completed successfully")

    def test_ok_with_number_data(self):
        """Test ok() with numeric data."""
        result = ok(42)
        data = json.loads(result)

        self.assertTrue(data["ok"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["data"], 42)

    def test_ok_with_no_data(self):
        """Test ok() with no data (None)."""
        result = ok()
        data = json.loads(result)

        self.assertTrue(data["ok"])
        self.assertIsNone(data["error"])
        self.assertIsNone(data["data"])

    def test_ok_with_nested_data(self):
        """Test ok() with deeply nested data structure."""
        nested_data = {
            "user": {
                "profile": {
                    "name": "John",
                    "stats": {"videos": 10, "followers": 1000}
                }
            }
        }
        result = ok(nested_data)
        data = json.loads(result)

        self.assertTrue(data["ok"])
        self.assertEqual(data["data"]["user"]["profile"]["name"], "John")
        self.assertEqual(data["data"]["user"]["profile"]["stats"]["videos"], 10)

    def test_fail_with_message_only(self):
        """Test fail() with message only (default code)."""
        result = fail("Operation failed")
        data = json.loads(result)

        self.assertFalse(data["ok"])
        self.assertIsNone(data["data"])
        self.assertEqual(data["error"]["code"], "ERROR")
        self.assertEqual(data["error"]["message"], "Operation failed")
        self.assertNotIn("details", data["error"])

    def test_fail_with_custom_code(self):
        """Test fail() with custom error code."""
        result = fail("Video not found", code="VIDEO_NOT_FOUND")
        data = json.loads(result)

        self.assertFalse(data["ok"])
        self.assertIsNone(data["data"])
        self.assertEqual(data["error"]["code"], "VIDEO_NOT_FOUND")
        self.assertEqual(data["error"]["message"], "Video not found")

    def test_fail_with_details(self):
        """Test fail() with error details."""
        result = fail(
            "Transcription failed",
            code="TRANSCRIPTION_ERROR",
            details={"video_id": "xyz789", "retry_count": 3}
        )
        data = json.loads(result)

        self.assertFalse(data["ok"])
        self.assertEqual(data["error"]["code"], "TRANSCRIPTION_ERROR")
        self.assertEqual(data["error"]["message"], "Transcription failed")
        self.assertEqual(data["error"]["details"]["video_id"], "xyz789")
        self.assertEqual(data["error"]["details"]["retry_count"], 3)

    def test_fail_with_complex_details(self):
        """Test fail() with complex nested error details."""
        result = fail(
            "Configuration error",
            code="CONFIG_ERROR",
            details={
                "file": "settings.yaml",
                "errors": [
                    {"line": 10, "message": "Invalid syntax"},
                    {"line": 25, "message": "Missing required field"}
                ]
            }
        )
        data = json.loads(result)

        self.assertFalse(data["ok"])
        self.assertEqual(len(data["error"]["details"]["errors"]), 2)
        self.assertEqual(data["error"]["details"]["errors"][0]["line"], 10)

    def test_is_ok_with_success_response(self):
        """Test is_ok() correctly identifies success response."""
        success = ok({"key": "value"})
        self.assertTrue(is_ok(success))

    def test_is_ok_with_error_response(self):
        """Test is_ok() correctly identifies error response."""
        error = fail("Something went wrong")
        self.assertFalse(is_ok(error))

    def test_is_ok_with_invalid_json(self):
        """Test is_ok() handles invalid JSON gracefully."""
        invalid = "not valid json {"
        self.assertFalse(is_ok(invalid))

    def test_is_ok_with_malformed_response(self):
        """Test is_ok() handles response without ok field."""
        malformed = json.dumps({"data": "test", "error": None})
        self.assertFalse(is_ok(malformed))

    def test_get_data_from_success_response(self):
        """Test get_data() extracts data from success response."""
        success = ok({"count": 5, "items": ["a", "b", "c"]})
        data = get_data(success)

        self.assertIsNotNone(data)
        self.assertEqual(data["count"], 5)
        self.assertEqual(len(data["items"]), 3)

    def test_get_data_from_error_response(self):
        """Test get_data() returns None for error response."""
        error = fail("Error occurred")
        data = get_data(error)

        self.assertIsNone(data)

    def test_get_data_with_invalid_json(self):
        """Test get_data() handles invalid JSON gracefully."""
        invalid = "not valid json"
        data = get_data(invalid)

        self.assertIsNone(data)

    def test_get_error_from_error_response(self):
        """Test get_error() extracts error from error response."""
        error = fail("Operation failed", code="OP_FAILED", details={"reason": "timeout"})
        error_obj = get_error(error)

        self.assertIsNotNone(error_obj)
        self.assertEqual(error_obj["code"], "OP_FAILED")
        self.assertEqual(error_obj["message"], "Operation failed")
        self.assertEqual(error_obj["details"]["reason"], "timeout")

    def test_get_error_from_success_response(self):
        """Test get_error() returns None for success response."""
        success = ok({"data": "value"})
        error_obj = get_error(success)

        self.assertIsNone(error_obj)

    def test_get_error_with_invalid_json(self):
        """Test get_error() handles invalid JSON gracefully."""
        invalid = "not valid json"
        error_obj = get_error(invalid)

        self.assertIsNone(error_obj)

    def test_envelope_structure_consistency(self):
        """Test that envelope structure is consistent across all responses."""
        success = ok({"test": "data"})
        error = fail("Test error")

        success_data = json.loads(success)
        error_data = json.loads(error)

        # Both should have same keys
        self.assertEqual(set(success_data.keys()), {"ok", "data", "error"})
        self.assertEqual(set(error_data.keys()), {"ok", "data", "error"})

    def test_json_serializable_output(self):
        """Test that all outputs are valid JSON."""
        test_cases = [
            ok({"key": "value"}),
            ok([1, 2, 3]),
            ok("string"),
            ok(42),
            ok(None),
            fail("Error message"),
            fail("Error", code="CODE"),
            fail("Error", code="CODE", details={"key": "value"})
        ]

        for test_case in test_cases:
            # Should not raise exception
            parsed = json.loads(test_case)
            # Should be able to serialize back to JSON
            reserialized = json.dumps(parsed)
            self.assertIsInstance(reserialized, str)

    def test_error_code_types(self):
        """Test various error code naming conventions."""
        codes = [
            "ERROR",
            "VIDEO_NOT_FOUND",
            "TRANSCRIPTION_FAILED",
            "API_QUOTA_EXCEEDED",
            "CONFIGURATION_ERROR"
        ]

        for code in codes:
            result = fail("Test error", code=code)
            data = json.loads(result)
            self.assertEqual(data["error"]["code"], code)

    def test_empty_details(self):
        """Test fail() with empty details dict."""
        result = fail("Error", code="ERR", details={})
        data = json.loads(result)

        # Empty details dict is NOT included (falsy value)
        self.assertNotIn("details", data["error"])

    def test_special_characters_in_message(self):
        """Test messages with special characters and unicode."""
        messages = [
            "Error: file not found @ /path/to/file.txt",
            "Failed with 100% certainty",
            "Unicode test: café, naïve, 日本語",
            'Message with "quotes" and \'apostrophes\''
        ]

        for message in messages:
            result = fail(message)
            data = json.loads(result)
            self.assertEqual(data["error"]["message"], message)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
