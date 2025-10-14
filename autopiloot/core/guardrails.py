"""
Output Guardrails for Agency Swarm Agents

Provides validation functions for agent outputs with automatic retry on failures.
Part of Agency Swarm v1.2.0 upgrade (TASK-AGS-0098).

All guardrail functions follow the OutputGuardrail signature:
    Callable[[str], str] - Takes output string, returns validated output or raises ValueError
"""

import json
import logging
from typing import List, Callable

logger = logging.getLogger(__name__)


def validate_json_output(output: str) -> str:
    """
    Ensure output is valid JSON.

    Args:
        output: Agent output string to validate

    Returns:
        str: The validated output (unchanged if valid)

    Raises:
        ValueError: If output is not valid JSON

    Example:
        >>> validate_json_output('{"status": "ok"}')
        '{"status": "ok"}'
        >>> validate_json_output('invalid json')  # Raises ValueError
    """
    try:
        json.loads(output)
        return output
    except json.JSONDecodeError as e:
        raise ValueError(f"Output must be valid JSON. Error: {e}")


def validate_required_fields(required_fields: List[str]) -> Callable[[str], str]:
    """
    Factory function that creates a validator for required JSON fields.

    Args:
        required_fields: List of field names that must be present in JSON output

    Returns:
        Callable[[str], str]: Validation function that checks for required fields

    Example:
        >>> validator = validate_required_fields(['status', 'message'])
        >>> validator('{"status": "ok", "message": "done"}')  # OK
        >>> validator('{"status": "ok"}')  # Raises ValueError - missing 'message'
    """
    def validator(output: str) -> str:
        try:
            data = json.loads(output)
            missing = [f for f in required_fields if f not in data]
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
            return output
        except json.JSONDecodeError:
            raise ValueError("Output must be valid JSON")

    return validator


def validate_no_errors(output: str) -> str:
    """
    Ensure output doesn't contain an 'error' field.

    Useful for catching tool errors that should be retried.

    Args:
        output: Agent output string to validate

    Returns:
        str: The validated output (unchanged if valid)

    Raises:
        ValueError: If output contains an 'error' field

    Example:
        >>> validate_no_errors('{"status": "ok"}')
        '{"status": "ok"}'
        >>> validate_no_errors('{"error": "failed", "message": "timeout"}')  # Raises ValueError
    """
    try:
        data = json.loads(output)
        if 'error' in data:
            error_msg = data.get('message', data['error'])
            raise ValueError(f"Output contains error: {error_msg}")
        return output
    except json.JSONDecodeError:
        raise ValueError("Output must be valid JSON")


def validate_orchestrator_output(output: str) -> str:
    """
    Orchestrator-specific validation for agent outputs.

    Validates:
    - Output is valid JSON
    - Contains required fields: 'status', 'action'
    - Status is one of: 'success', 'pending', 'failed', 'delegated'

    Args:
        output: Orchestrator agent output string

    Returns:
        str: The validated output (unchanged if valid)

    Raises:
        ValueError: If output fails validation with specific error message

    Example:
        >>> validate_orchestrator_output('{"status": "success", "action": "dispatch_scraper"}')
        '{"status": "success", "action": "dispatch_scraper"}'
        >>> validate_orchestrator_output('{"status": "invalid"}')  # Raises ValueError
    """
    try:
        data = json.loads(output)

        # Check required fields
        required = ['status', 'action']
        missing = [f for f in required if f not in data]
        if missing:
            raise ValueError(f"Orchestrator output missing required fields: {missing}")

        # Validate status values
        valid_statuses = ['success', 'pending', 'failed', 'delegated']
        if data['status'] not in valid_statuses:
            raise ValueError(
                f"Invalid status '{data['status']}'. Must be one of: {valid_statuses}"
            )

        return output
    except json.JSONDecodeError as e:
        raise ValueError(f"Orchestrator output must be valid JSON. Error: {e}")


def validate_scraper_output(output: str) -> str:
    """
    Scraper-specific validation for agent outputs.

    Validates:
    - Output is valid JSON
    - Contains either 'videos_discovered' count or 'error'
    - If videos_discovered present, must be non-negative integer

    Args:
        output: Scraper agent output string

    Returns:
        str: The validated output (unchanged if valid)

    Raises:
        ValueError: If output fails validation with specific error message

    Example:
        >>> validate_scraper_output('{"videos_discovered": 5, "channel": "@test"}')
        '{"videos_discovered": 5, "channel": "@test"}'
        >>> validate_scraper_output('{"videos_discovered": -1}')  # Raises ValueError
    """
    try:
        data = json.loads(output)

        # Must have either videos_discovered or error
        if 'videos_discovered' not in data and 'error' not in data:
            raise ValueError(
                "Scraper output must include 'videos_discovered' count or 'error' field"
            )

        # If videos discovered, must be non-negative integer
        if 'videos_discovered' in data:
            count = data['videos_discovered']
            if not isinstance(count, int) or count < 0:
                raise ValueError(
                    f"videos_discovered must be non-negative integer, got: {count} ({type(count).__name__})"
                )

        return output
    except json.JSONDecodeError as e:
        raise ValueError(f"Scraper output must be valid JSON. Error: {e}")


def validate_summarizer_output(output: str) -> str:
    """
    Summarizer-specific validation for agent outputs.

    Validates:
    - Output is valid JSON
    - If summary/short_summary present, must be at least 10 characters
    - If status='rejected', must include 'reason' field

    Args:
        output: Summarizer agent output string

    Returns:
        str: The validated output (unchanged if valid)

    Raises:
        ValueError: If output fails validation with specific error message

    Example:
        >>> validate_summarizer_output('{"summary": "This is a valid summary text"}')
        '{"summary": "This is a valid summary text"}'
        >>> validate_summarizer_output('{"summary": "short"}')  # Raises ValueError
    """
    try:
        data = json.loads(output)

        # If summary generated, must have required length
        if 'summary' in data or 'short_summary' in data:
            summary_text = data.get('summary') or data.get('short_summary')
            if not summary_text or len(summary_text.strip()) < 10:
                raise ValueError(
                    f"Summary must be at least 10 characters, got {len(summary_text.strip()) if summary_text else 0}"
                )

        # If rejected, must have reason
        if data.get('status') == 'rejected':
            if 'reason' not in data or not data['reason']:
                raise ValueError(
                    "Rejected videos must include 'reason' field with explanation"
                )

        return output
    except json.JSONDecodeError as e:
        raise ValueError(f"Summarizer output must be valid JSON. Error: {e}")


def validate_transcriber_output(output: str) -> str:
    """
    Transcriber-specific validation for agent outputs.

    Validates:
    - Output is valid JSON
    - Contains required fields: 'transcript_id', 'video_id'

    Args:
        output: Transcriber agent output string

    Returns:
        str: The validated output (unchanged if valid)

    Raises:
        ValueError: If output fails validation with specific error message

    Example:
        >>> validate_transcriber_output('{"transcript_id": "abc123", "video_id": "xyz789"}')
        '{"transcript_id": "abc123", "video_id": "xyz789"}'
        >>> validate_transcriber_output('{"transcript_id": "abc123"}')  # Raises ValueError
    """
    required_fields = ['transcript_id', 'video_id']
    validator = validate_required_fields(required_fields)

    try:
        return validator(output)
    except ValueError as e:
        # Re-raise with transcriber-specific context
        raise ValueError(f"Transcriber output validation failed: {e}")


def validate_handoff_reminder(reminder: str) -> str:
    """
    Validate handoff reminder is appropriate length and format.

    Agency Swarm v1.1.0+ handoff reminders are system messages injected
    during agent transitions to reinforce policies and context.

    Args:
        reminder: Handoff reminder text to validate

    Returns:
        str: The validated reminder text (stripped)

    Raises:
        ValueError: If reminder is invalid

    Example:
        >>> validate_handoff_reminder("Check budget before proceeding")
        'Check budget before proceeding'
        >>> validate_handoff_reminder("")  # Raises ValueError
    """
    if not reminder or not isinstance(reminder, str):
        raise ValueError("Handoff reminder must be non-empty string")

    # Strip whitespace
    reminder = reminder.strip()

    if len(reminder) == 0:
        raise ValueError("Handoff reminder cannot be empty or whitespace only")

    # Check length (reminders should be concise to avoid token overhead)
    if len(reminder) > 500:
        logger.warning(
            f"Handoff reminder is long ({len(reminder)} chars). "
            "Consider shortening to reduce token overhead."
        )

    # Check for overly prescriptive language
    if reminder.lower().startswith("you must") or reminder.lower().startswith("you should"):
        logger.warning(
            "Handoff reminder uses directive language ('you must', 'you should'). "
            "Consider rephrasing positively for better agent autonomy."
        )

    return reminder


if __name__ == "__main__":
    # Test the guardrail functions
    print("Testing Output Guardrails")
    print("=" * 50)

    # Test validate_json_output
    print("\n1. Testing validate_json_output:")
    try:
        result = validate_json_output('{"status": "ok"}')
        print(f"   ✓ Valid JSON passed: {result}")
    except ValueError as e:
        print(f"   ✗ Unexpected error: {e}")

    try:
        validate_json_output('invalid json')
        print("   ✗ Invalid JSON should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Invalid JSON caught: {e}")

    # Test validate_orchestrator_output
    print("\n2. Testing validate_orchestrator_output:")
    try:
        result = validate_orchestrator_output('{"status": "success", "action": "dispatch"}')
        print(f"   ✓ Valid orchestrator output passed")
    except ValueError as e:
        print(f"   ✗ Unexpected error: {e}")

    try:
        validate_orchestrator_output('{"status": "invalid_status", "action": "dispatch"}')
        print("   ✗ Invalid status should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Invalid status caught: {e}")

    # Test validate_scraper_output
    print("\n3. Testing validate_scraper_output:")
    try:
        result = validate_scraper_output('{"videos_discovered": 5}')
        print(f"   ✓ Valid scraper output passed")
    except ValueError as e:
        print(f"   ✗ Unexpected error: {e}")

    try:
        validate_scraper_output('{"videos_discovered": -1}')
        print("   ✗ Negative count should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Negative count caught: {e}")

    # Test validate_summarizer_output
    print("\n4. Testing validate_summarizer_output:")
    try:
        result = validate_summarizer_output('{"summary": "This is a valid summary with enough text"}')
        print(f"   ✓ Valid summarizer output passed")
    except ValueError as e:
        print(f"   ✗ Unexpected error: {e}")

    try:
        validate_summarizer_output('{"summary": "short"}')
        print("   ✗ Short summary should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Short summary caught: {e}")

    print("\n" + "=" * 50)
    print("All guardrail tests completed!")
