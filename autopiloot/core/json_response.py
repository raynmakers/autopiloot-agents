"""
Standard JSON response envelope for Autopiloot tools.

Provides consistent response format across all tools:
{
    "ok": bool,
    "data": any,
    "error": {"code": str, "message": str}
}

This eliminates inconsistent JSON structures and simplifies testing.
"""

import json
from typing import Any, Optional, Dict


def ok(data: Any = None) -> str:
    """
    Create a successful JSON response.

    Args:
        data: Success payload (can be dict, list, str, int, etc.)

    Returns:
        JSON string with ok=True and data field

    Example:
        >>> ok({"video_id": "abc123", "status": "transcribed"})
        '{"ok": true, "data": {"video_id": "abc123", "status": "transcribed"}, "error": null}'
    """
    response = {
        "ok": True,
        "data": data,
        "error": None
    }
    return json.dumps(response)


def fail(message: str, code: str = "ERROR", details: Optional[Dict[str, Any]] = None) -> str:
    """
    Create an error JSON response.

    Args:
        message: Human-readable error description
        code: Error code identifier (default: "ERROR")
        details: Optional additional error context

    Returns:
        JSON string with ok=False and error field

    Example:
        >>> fail("Video not found", code="VIDEO_NOT_FOUND", details={"video_id": "abc123"})
        '{"ok": false, "data": null, "error": {"code": "VIDEO_NOT_FOUND", "message": "Video not found", "details": {"video_id": "abc123"}}}'
    """
    error = {
        "code": code,
        "message": message
    }

    if details:
        error["details"] = details

    response = {
        "ok": False,
        "data": None,
        "error": error
    }
    return json.dumps(response)


def is_ok(json_string: str) -> bool:
    """
    Check if a JSON response indicates success.

    Args:
        json_string: JSON response string

    Returns:
        True if ok=True, False otherwise

    Example:
        >>> is_ok('{"ok": true, "data": null, "error": null}')
        True
    """
    try:
        response = json.loads(json_string)
        return response.get("ok", False)
    except (json.JSONDecodeError, AttributeError):
        return False


def get_data(json_string: str) -> Any:
    """
    Extract data field from JSON response.

    Args:
        json_string: JSON response string

    Returns:
        Data payload if present, None otherwise

    Example:
        >>> get_data('{"ok": true, "data": {"count": 5}, "error": null}')
        {'count': 5}
    """
    try:
        response = json.loads(json_string)
        return response.get("data")
    except (json.JSONDecodeError, AttributeError):
        return None


def get_error(json_string: str) -> Optional[Dict[str, Any]]:
    """
    Extract error field from JSON response.

    Args:
        json_string: JSON response string

    Returns:
        Error dict if present, None otherwise

    Example:
        >>> get_error('{"ok": false, "data": null, "error": {"code": "NOT_FOUND", "message": "Item missing"}}')
        {'code': 'NOT_FOUND', 'message': 'Item missing'}
    """
    try:
        response = json.loads(json_string)
        return response.get("error")
    except (json.JSONDecodeError, AttributeError):
        return None


if __name__ == "__main__":
    print("Testing JSON response helper...")

    # Test successful response
    success = ok({"video_id": "abc123", "status": "transcribed"})
    print(f"\nSuccess response:\n{success}")
    assert is_ok(success)
    assert get_data(success) == {"video_id": "abc123", "status": "transcribed"}
    assert get_error(success) is None

    # Test error response
    error = fail("Video not found", code="VIDEO_NOT_FOUND", details={"video_id": "xyz789"})
    print(f"\nError response:\n{error}")
    assert not is_ok(error)
    assert get_data(error) is None
    error_obj = get_error(error)
    assert error_obj["code"] == "VIDEO_NOT_FOUND"
    assert error_obj["message"] == "Video not found"
    assert error_obj["details"] == {"video_id": "xyz789"}

    # Test response with no data
    empty_success = ok()
    print(f"\nEmpty success:\n{empty_success}")
    assert is_ok(empty_success)
    assert get_data(empty_success) is None

    # Test response with simple data types
    string_response = ok("Operation completed")
    print(f"\nString data:\n{string_response}")
    assert get_data(string_response) == "Operation completed"

    number_response = ok(42)
    print(f"\nNumber data:\n{number_response}")
    assert get_data(number_response) == 42

    list_response = ok([1, 2, 3])
    print(f"\nList data:\n{list_response}")
    assert get_data(list_response) == [1, 2, 3]

    print("\n✓ All JSON response helper tests passed!")
