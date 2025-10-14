"""
Tests for Agency Swarm v1.2.0 Output Guardrails (TASK-AGS-0098)

Tests cover all validation functions in core/guardrails.py:
1. validate_json_output - Generic JSON validation
2. validate_required_fields - Factory for field validators
3. validate_no_errors - Ensures no error field present
4. validate_orchestrator_output - Orchestrator-specific validation
5. validate_scraper_output - Scraper-specific validation
6. validate_summarizer_output - Summarizer-specific validation
7. validate_transcriber_output - Transcriber-specific validation
"""

import unittest
import json
from core.guardrails import (
    validate_json_output,
    validate_required_fields,
    validate_no_errors,
    validate_orchestrator_output,
    validate_scraper_output,
    validate_summarizer_output,
    validate_transcriber_output,
)


class TestValidateJsonOutput(unittest.TestCase):
    """Test generic JSON validation"""

    def test_valid_json_passes(self):
        """Valid JSON should pass validation"""
        valid_json = '{"status": "ok", "data": [1, 2, 3]}'
        result = validate_json_output(valid_json)
        self.assertEqual(result, valid_json)

    def test_valid_json_complex_structure(self):
        """Complex nested JSON should pass"""
        complex_json = '{"a": {"b": {"c": [1, 2, {"d": "e"}]}}}'
        result = validate_json_output(complex_json)
        self.assertEqual(result, complex_json)

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_json_output('not valid json')
        self.assertIn("Output must be valid JSON", str(ctx.exception))

    def test_incomplete_json_raises_error(self):
        """Incomplete JSON should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_json_output('{"key": "value"')  # Missing closing brace
        self.assertIn("Output must be valid JSON", str(ctx.exception))

    def test_empty_object_passes(self):
        """Empty JSON object should pass"""
        result = validate_json_output('{}')
        self.assertEqual(result, '{}')

    def test_empty_array_passes(self):
        """Empty JSON array should pass"""
        result = validate_json_output('[]')
        self.assertEqual(result, '[]')


class TestValidateRequiredFields(unittest.TestCase):
    """Test required fields factory validator"""

    def test_all_fields_present_passes(self):
        """Output with all required fields should pass"""
        validator = validate_required_fields(['name', 'age'])
        valid_output = '{"name": "John", "age": 30, "extra": "field"}'
        result = validator(valid_output)
        self.assertEqual(result, valid_output)

    def test_missing_single_field_raises_error(self):
        """Output missing one required field should raise ValueError"""
        validator = validate_required_fields(['name', 'age'])
        missing_output = '{"name": "John"}'
        with self.assertRaises(ValueError) as ctx:
            validator(missing_output)
        self.assertIn("Missing required fields", str(ctx.exception))
        self.assertIn("age", str(ctx.exception))

    def test_missing_multiple_fields_raises_error(self):
        """Output missing multiple required fields should raise ValueError"""
        validator = validate_required_fields(['name', 'age', 'email'])
        missing_output = '{"name": "John"}'
        with self.assertRaises(ValueError) as ctx:
            validator(missing_output)
        self.assertIn("Missing required fields", str(ctx.exception))
        self.assertIn("age", str(ctx.exception))
        self.assertIn("email", str(ctx.exception))

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError"""
        validator = validate_required_fields(['name'])
        with self.assertRaises(ValueError) as ctx:
            validator('invalid json')
        self.assertIn("Output must be valid JSON", str(ctx.exception))

    def test_empty_required_fields_list(self):
        """Validator with no required fields should pass any valid JSON"""
        validator = validate_required_fields([])
        result = validator('{"any": "data"}')
        self.assertEqual(result, '{"any": "data"}')


class TestValidateNoErrors(unittest.TestCase):
    """Test error field absence validation"""

    def test_no_error_field_passes(self):
        """Output without error field should pass"""
        valid_output = '{"status": "success", "data": "result"}'
        result = validate_no_errors(valid_output)
        self.assertEqual(result, valid_output)

    def test_error_field_present_raises_error(self):
        """Output with error field should raise ValueError"""
        error_output = '{"error": "something went wrong"}'
        with self.assertRaises(ValueError) as ctx:
            validate_no_errors(error_output)
        self.assertIn("Output contains error", str(ctx.exception))
        self.assertIn("something went wrong", str(ctx.exception))

    def test_error_with_message_field(self):
        """Output with error and message should use message in error"""
        error_output = '{"error": "failed", "message": "detailed error message"}'
        with self.assertRaises(ValueError) as ctx:
            validate_no_errors(error_output)
        self.assertIn("detailed error message", str(ctx.exception))

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_no_errors('not json')
        self.assertIn("Output must be valid JSON", str(ctx.exception))


class TestValidateOrchestratorOutput(unittest.TestCase):
    """Test orchestrator-specific validation"""

    def test_valid_success_output_passes(self):
        """Valid orchestrator output with success status should pass"""
        valid_output = '{"status": "success", "action": "dispatch_scraper"}'
        result = validate_orchestrator_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_valid_pending_output_passes(self):
        """Valid orchestrator output with pending status should pass"""
        valid_output = '{"status": "pending", "action": "wait_for_transcription"}'
        result = validate_orchestrator_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_valid_failed_output_passes(self):
        """Valid orchestrator output with failed status should pass"""
        valid_output = '{"status": "failed", "action": "retry_operation"}'
        result = validate_orchestrator_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_valid_delegated_output_passes(self):
        """Valid orchestrator output with delegated status should pass"""
        valid_output = '{"status": "delegated", "action": "forward_to_agent"}'
        result = validate_orchestrator_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_missing_status_field_raises_error(self):
        """Output missing status field should raise ValueError"""
        missing_status = '{"action": "dispatch_scraper"}'
        with self.assertRaises(ValueError) as ctx:
            validate_orchestrator_output(missing_status)
        self.assertIn("missing required fields", str(ctx.exception))
        self.assertIn("status", str(ctx.exception))

    def test_missing_action_field_raises_error(self):
        """Output missing action field should raise ValueError"""
        missing_action = '{"status": "success"}'
        with self.assertRaises(ValueError) as ctx:
            validate_orchestrator_output(missing_action)
        self.assertIn("missing required fields", str(ctx.exception))
        self.assertIn("action", str(ctx.exception))

    def test_invalid_status_value_raises_error(self):
        """Output with invalid status value should raise ValueError"""
        invalid_status = '{"status": "unknown", "action": "dispatch"}'
        with self.assertRaises(ValueError) as ctx:
            validate_orchestrator_output(invalid_status)
        self.assertIn("Invalid status", str(ctx.exception))
        self.assertIn("unknown", str(ctx.exception))

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_orchestrator_output('not json')
        self.assertIn("must be valid JSON", str(ctx.exception))


class TestValidateScraperOutput(unittest.TestCase):
    """Test scraper-specific validation"""

    def test_valid_videos_discovered_passes(self):
        """Valid scraper output with videos_discovered should pass"""
        valid_output = '{"videos_discovered": 5, "channel": "@test"}'
        result = validate_scraper_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_zero_videos_discovered_passes(self):
        """Scraper output with zero videos should pass"""
        zero_output = '{"videos_discovered": 0, "channel": "@test"}'
        result = validate_scraper_output(zero_output)
        self.assertEqual(result, zero_output)

    def test_error_field_passes(self):
        """Scraper output with error field should pass (errors are valid responses)"""
        error_output = '{"error": "quota_exceeded", "message": "YouTube API quota exhausted"}'
        result = validate_scraper_output(error_output)
        self.assertEqual(result, error_output)

    def test_missing_both_fields_raises_error(self):
        """Output missing both videos_discovered and error should raise ValueError"""
        missing_both = '{"channel": "@test"}'
        with self.assertRaises(ValueError) as ctx:
            validate_scraper_output(missing_both)
        self.assertIn("must include 'videos_discovered' count or 'error' field", str(ctx.exception))

    def test_negative_videos_discovered_raises_error(self):
        """Negative videos_discovered should raise ValueError"""
        negative_count = '{"videos_discovered": -1}'
        with self.assertRaises(ValueError) as ctx:
            validate_scraper_output(negative_count)
        self.assertIn("must be non-negative integer", str(ctx.exception))

    def test_non_integer_videos_discovered_raises_error(self):
        """Non-integer videos_discovered should raise ValueError"""
        non_integer = '{"videos_discovered": "five"}'
        with self.assertRaises(ValueError) as ctx:
            validate_scraper_output(non_integer)
        self.assertIn("must be non-negative integer", str(ctx.exception))

    def test_float_videos_discovered_raises_error(self):
        """Float videos_discovered should raise ValueError"""
        float_value = '{"videos_discovered": 5.5}'
        with self.assertRaises(ValueError) as ctx:
            validate_scraper_output(float_value)
        self.assertIn("must be non-negative integer", str(ctx.exception))

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_scraper_output('not json')
        self.assertIn("must be valid JSON", str(ctx.exception))


class TestValidateSummarizerOutput(unittest.TestCase):
    """Test summarizer-specific validation"""

    def test_valid_summary_passes(self):
        """Valid summarizer output with sufficient summary length should pass"""
        valid_output = '{"summary": "This is a valid summary with enough content to pass validation"}'
        result = validate_summarizer_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_valid_short_summary_passes(self):
        """Valid summarizer output with short_summary should pass"""
        valid_output = '{"short_summary": "Valid short summary text here"}'
        result = validate_summarizer_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_short_summary_raises_error(self):
        """Summary shorter than 10 characters should raise ValueError"""
        short_summary = '{"summary": "short"}'
        with self.assertRaises(ValueError) as ctx:
            validate_summarizer_output(short_summary)
        self.assertIn("must be at least 10 characters", str(ctx.exception))

    def test_empty_summary_raises_error(self):
        """Empty summary should raise ValueError"""
        empty_summary = '{"summary": ""}'
        with self.assertRaises(ValueError) as ctx:
            validate_summarizer_output(empty_summary)
        self.assertIn("must be at least 10 characters", str(ctx.exception))

    def test_whitespace_only_summary_raises_error(self):
        """Whitespace-only summary should raise ValueError"""
        whitespace_summary = '{"summary": "     "}'
        with self.assertRaises(ValueError) as ctx:
            validate_summarizer_output(whitespace_summary)
        self.assertIn("must be at least 10 characters", str(ctx.exception))

    def test_rejected_with_reason_passes(self):
        """Rejected status with reason should pass"""
        valid_rejected = '{"status": "rejected", "reason": "Not business-related content"}'
        result = validate_summarizer_output(valid_rejected)
        self.assertEqual(result, valid_rejected)

    def test_rejected_without_reason_raises_error(self):
        """Rejected status without reason should raise ValueError"""
        rejected_no_reason = '{"status": "rejected"}'
        with self.assertRaises(ValueError) as ctx:
            validate_summarizer_output(rejected_no_reason)
        self.assertIn("must include 'reason' field", str(ctx.exception))

    def test_rejected_empty_reason_raises_error(self):
        """Rejected status with empty reason should raise ValueError"""
        rejected_empty_reason = '{"status": "rejected", "reason": ""}'
        with self.assertRaises(ValueError) as ctx:
            validate_summarizer_output(rejected_empty_reason)
        self.assertIn("must include 'reason' field", str(ctx.exception))

    def test_no_summary_or_rejection_passes(self):
        """Output without summary or rejection should pass (intermediate states)"""
        intermediate_output = '{"status": "processing", "video_id": "abc123"}'
        result = validate_summarizer_output(intermediate_output)
        self.assertEqual(result, intermediate_output)

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_summarizer_output('not json')
        self.assertIn("must be valid JSON", str(ctx.exception))


class TestValidateTranscriberOutput(unittest.TestCase):
    """Test transcriber-specific validation"""

    def test_valid_output_passes(self):
        """Valid transcriber output with both required fields should pass"""
        valid_output = '{"transcript_id": "abc123", "video_id": "xyz789"}'
        result = validate_transcriber_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_valid_output_with_extra_fields_passes(self):
        """Valid transcriber output with additional fields should pass"""
        valid_output = '{"transcript_id": "abc123", "video_id": "xyz789", "duration": 300, "status": "completed"}'
        result = validate_transcriber_output(valid_output)
        self.assertEqual(result, valid_output)

    def test_missing_transcript_id_raises_error(self):
        """Output missing transcript_id should raise ValueError"""
        missing_transcript_id = '{"video_id": "xyz789"}'
        with self.assertRaises(ValueError) as ctx:
            validate_transcriber_output(missing_transcript_id)
        self.assertIn("Transcriber output validation failed", str(ctx.exception))
        self.assertIn("transcript_id", str(ctx.exception))

    def test_missing_video_id_raises_error(self):
        """Output missing video_id should raise ValueError"""
        missing_video_id = '{"transcript_id": "abc123"}'
        with self.assertRaises(ValueError) as ctx:
            validate_transcriber_output(missing_video_id)
        self.assertIn("Transcriber output validation failed", str(ctx.exception))
        self.assertIn("video_id", str(ctx.exception))

    def test_missing_both_fields_raises_error(self):
        """Output missing both required fields should raise ValueError"""
        missing_both = '{"status": "completed"}'
        with self.assertRaises(ValueError) as ctx:
            validate_transcriber_output(missing_both)
        self.assertIn("Transcriber output validation failed", str(ctx.exception))

    def test_invalid_json_raises_error(self):
        """Invalid JSON should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_transcriber_output('not json')
        self.assertIn("Transcriber output validation failed", str(ctx.exception))


class TestGuardrailsIntegration(unittest.TestCase):
    """Integration tests for guardrails in agent workflows"""

    def test_orchestrator_complete_workflow(self):
        """Test complete orchestrator workflow with guardrails"""
        # Success path
        success_output = json.dumps({
            "status": "success",
            "action": "dispatch_scraper",
            "details": "Initiated scraping for 3 channels"
        })
        result = validate_orchestrator_output(success_output)
        self.assertEqual(result, success_output)

        # Failure path should raise
        with self.assertRaises(ValueError):
            validate_orchestrator_output('{"status": "invalid"}')

    def test_scraper_complete_workflow(self):
        """Test complete scraper workflow with guardrails"""
        # Success with videos
        success_output = json.dumps({
            "videos_discovered": 10,
            "channel": "@AlexHormozi",
            "source": "youtube"
        })
        result = validate_scraper_output(success_output)
        self.assertEqual(result, success_output)

        # Error response
        error_output = json.dumps({
            "error": "quota_exceeded",
            "message": "YouTube API quota exhausted"
        })
        result = validate_scraper_output(error_output)
        self.assertEqual(result, error_output)

    def test_transcriber_complete_workflow(self):
        """Test complete transcriber workflow with guardrails"""
        # Success path
        success_output = json.dumps({
            "transcript_id": "trans_abc123",
            "video_id": "video_xyz789",
            "drive_url": "https://drive.google.com/...",
            "duration_seconds": 1800
        })
        result = validate_transcriber_output(success_output)
        self.assertEqual(result, success_output)

    def test_summarizer_complete_workflow(self):
        """Test complete summarizer workflow with guardrails"""
        # Success with summary
        success_output = json.dumps({
            "summary": "This video discusses advanced business strategies including customer acquisition, retention, and scaling operations effectively.",
            "short_summary": "Advanced business strategies for growth",
            "video_id": "xyz789"
        })
        result = validate_summarizer_output(success_output)
        self.assertEqual(result, success_output)

        # Rejection with reason
        rejected_output = json.dumps({
            "status": "rejected",
            "reason": "Video content is not business-related",
            "video_id": "xyz789"
        })
        result = validate_summarizer_output(rejected_output)
        self.assertEqual(result, rejected_output)


if __name__ == '__main__':
    unittest.main()
