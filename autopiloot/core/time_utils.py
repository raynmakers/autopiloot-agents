"""
Time utilities for Autopiloot Agency.
Centralized timezone-aware time handling with consistent ISO 8601 formatting.
"""

import os
from datetime import datetime, timezone
from typing import Optional, Union

# Optional pytz import for enhanced timezone support
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False


def now() -> datetime:
    """
    Get current UTC datetime with timezone awareness.
    
    Returns:
        datetime: Current UTC datetime with timezone info
    """
    return datetime.now(timezone.utc)


def to_iso8601_z(dt: datetime) -> str:
    """
    Convert datetime to ISO 8601 string with 'Z' suffix for UTC.
    
    Args:
        dt: Datetime object to convert
        
    Returns:
        str: ISO 8601 formatted string with 'Z' suffix
        
    Example:
        "2025-09-15T14:30:00Z"
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)
    
    # Format to ISO 8601 with Z suffix
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso8601_z(iso_string: str) -> datetime:
    """
    Parse ISO 8601 string to timezone-aware datetime.
    
    Args:
        iso_string: ISO 8601 formatted string
        
    Returns:
        datetime: Timezone-aware datetime object in UTC
        
    Raises:
        ValueError: If string format is invalid
        
    Example:
        parse_iso8601_z("2025-09-15T14:30:00Z") -> datetime(2025, 9, 15, 14, 30, 0, tzinfo=timezone.utc)
    """
    # Handle various ISO 8601 formats
    formats = [
        '%Y-%m-%dT%H:%M:%SZ',           # 2025-09-15T14:30:00Z
        '%Y-%m-%dT%H:%M:%S.%fZ',        # 2025-09-15T14:30:00.123456Z
        '%Y-%m-%dT%H:%M:%S+00:00',      # 2025-09-15T14:30:00+00:00
        '%Y-%m-%dT%H:%M:%S.%f+00:00',   # 2025-09-15T14:30:00.123456+00:00
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(iso_string, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    
    # Try using fromisoformat for more flexibility
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    
    raise ValueError(f"Unable to parse ISO 8601 datetime: {iso_string}")


def format_for_firestore(dt: datetime) -> str:
    """
    Format datetime for Firestore timestamp compatibility.
    
    Args:
        dt: Datetime object to format
        
    Returns:
        str: Firestore-compatible timestamp string
    """
    return to_iso8601_z(dt)


def format_for_filename(dt: datetime) -> str:
    """
    Format datetime for safe filename usage.
    
    Args:
        dt: Datetime object to format
        
    Returns:
        str: Filename-safe datetime string
        
    Example:
        "20250915_143000"
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)
    
    return dt.strftime('%Y%m%d_%H%M%S')


def format_for_display(dt: datetime, timezone_name: str = 'UTC') -> str:
    """
    Format datetime for user-friendly display.
    
    Args:
        dt: Datetime object to format
        timezone_name: Target timezone for display (default: UTC)
        
    Returns:
        str: Human-readable datetime string
        
    Example:
        "2025-09-15 14:30:00 UTC"
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    if timezone_name != 'UTC' and PYTZ_AVAILABLE:
        try:
            target_tz = pytz.timezone(timezone_name)
            dt = dt.astimezone(target_tz)
        except pytz.UnknownTimeZoneError:
            # Fall back to UTC if timezone is unknown
            timezone_name = 'UTC'
    elif timezone_name != 'UTC':
        # Without pytz, fall back to UTC
        timezone_name = 'UTC'
    
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} {timezone_name}"


def seconds_since_epoch(dt: datetime) -> int:
    """
    Get seconds since Unix epoch for datetime.
    
    Args:
        dt: Datetime object
        
    Returns:
        int: Seconds since Unix epoch
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return int(dt.timestamp())


def from_seconds_since_epoch(seconds: Union[int, float]) -> datetime:
    """
    Create datetime from seconds since Unix epoch.
    
    Args:
        seconds: Seconds since Unix epoch
        
    Returns:
        datetime: Timezone-aware datetime in UTC
    """
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def add_hours(dt: datetime, hours: int) -> datetime:
    """
    Add hours to datetime while preserving timezone.
    
    Args:
        dt: Base datetime
        hours: Hours to add (can be negative)
        
    Returns:
        datetime: New datetime with hours added
    """
    from datetime import timedelta
    return dt + timedelta(hours=hours)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """
    Add minutes to datetime while preserving timezone.
    
    Args:
        dt: Base datetime
        minutes: Minutes to add (can be negative)
        
    Returns:
        datetime: New datetime with minutes added
    """
    from datetime import timedelta
    return dt + timedelta(minutes=minutes)


def start_of_day(dt: datetime) -> datetime:
    """
    Get start of day (00:00:00) for given datetime.
    
    Args:
        dt: Source datetime
        
    Returns:
        datetime: Start of day in same timezone
    """
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """
    Get end of day (23:59:59.999999) for given datetime.
    
    Args:
        dt: Source datetime
        
    Returns:
        datetime: End of day in same timezone
    """
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def is_business_hours(dt: datetime, start_hour: int = 9, end_hour: int = 17, timezone_name: str = 'UTC') -> bool:
    """
    Check if datetime falls within business hours.
    
    Args:
        dt: Datetime to check
        start_hour: Business start hour (24-hour format)
        end_hour: Business end hour (24-hour format)
        timezone_name: Timezone for business hours check
        
    Returns:
        bool: True if within business hours
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    if timezone_name != 'UTC' and PYTZ_AVAILABLE:
        try:
            target_tz = pytz.timezone(timezone_name)
            dt = dt.astimezone(target_tz)
        except pytz.UnknownTimeZoneError:
            pass  # Use UTC
    
    # Check if weekday (Monday=0, Sunday=6)
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Check if within business hours
    return start_hour <= dt.hour < end_hour


# Legacy compatibility functions for migration
def utcnow() -> datetime:
    """
    Legacy compatibility function.
    Use now() instead for new code.
    
    Returns:
        datetime: Current UTC datetime
    """
    return now()


def get_timestamp() -> str:
    """
    Legacy compatibility function.
    Use to_iso8601_z(now()) instead for new code.
    
    Returns:
        str: Current timestamp in ISO 8601 format
    """
    return to_iso8601_z(now())


# Environment-specific configurations
def get_default_timezone() -> str:
    """
    Get default timezone from environment or configuration.
    
    Returns:
        str: Default timezone name
    """
    return os.getenv('DEFAULT_TIMEZONE', 'UTC')


def get_business_timezone() -> str:
    """
    Get business timezone from environment or configuration.
    
    Returns:
        str: Business timezone name
    """
    return os.getenv('BUSINESS_TIMEZONE', 'America/New_York')


# Backoff and retry utilities
def calculate_exponential_backoff(
    attempt: int, 
    base_delay: int = 60, 
    max_delay: int = 240, 
    exponential_base: float = 2.0
) -> int:
    """
    Calculate exponential backoff delay for retry attempts.
    
    Args:
        attempt: Attempt number (1-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Exponential multiplier
        
    Returns:
        Delay in seconds for this attempt
        
    Example:
        calculate_exponential_backoff(1) -> 60
        calculate_exponential_backoff(2) -> 120
        calculate_exponential_backoff(3) -> 240 (capped)
    """
    if attempt <= 0:
        return 0
    
    delay = base_delay * (exponential_base ** (attempt - 1))
    return min(int(delay), max_delay)


def calculate_jittered_backoff(
    attempt: int,
    base_delay: int = 60,
    max_delay: int = 240,
    jitter_factor: float = 0.1
) -> int:
    """
    Calculate exponential backoff with jitter to avoid thundering herd.
    
    Args:
        attempt: Attempt number (1-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter_factor: Jitter factor (0.0 to 1.0)
        
    Returns:
        Delay in seconds with jitter applied
    """
    import random
    
    base_backoff = calculate_exponential_backoff(attempt, base_delay, max_delay)
    jitter = base_backoff * jitter_factor * (random.random() - 0.5)
    
    jittered_delay = base_backoff + jitter
    return max(1, min(int(jittered_delay), max_delay))


def get_next_retry_time(
    attempt: int,
    base_time: datetime = None,
    base_delay: int = 60,
    max_delay: int = 240
) -> datetime:
    """
    Get the next retry timestamp using exponential backoff.
    
    Args:
        attempt: Attempt number (1-based)
        base_time: Base time to calculate from (defaults to now)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        
    Returns:
        Next retry timestamp in UTC
    """
    if base_time is None:
        base_time = now()
    
    delay_seconds = calculate_exponential_backoff(attempt, base_delay, max_delay)
    return add_minutes(base_time, delay_seconds // 60)


# Duration formatting utilities
def format_duration_human(seconds: int) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Human-readable duration string
        
    Example:
        format_duration_human(90) -> "1m 30s"
        format_duration_human(3661) -> "1h 1m 1s"
    """
    if seconds < 0:
        return "0s"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def parse_duration_string(duration_str: str) -> int:
    """
    Parse human-readable duration string to seconds.
    
    Args:
        duration_str: Duration string (e.g., "1h 30m", "90s")
        
    Returns:
        Duration in seconds
        
    Raises:
        ValueError: If duration string is invalid
    """
    import re
    
    if not duration_str or not isinstance(duration_str, str):
        raise ValueError("Duration string cannot be empty")
    
    # Pattern to match time components
    pattern = r'(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?'
    match = re.match(pattern, duration_str.strip())
    
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}")
    
    hours, minutes, seconds = match.groups()
    
    total_seconds = 0
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += int(seconds)
    
    if total_seconds == 0:
        raise ValueError(f"No valid time components found in: {duration_str}")
    
    return total_seconds


# Age and elapsed time utilities
def get_age_in_seconds(timestamp: datetime, reference_time: datetime = None) -> int:
    """
    Get age of timestamp in seconds.
    
    Args:
        timestamp: The timestamp to check age of
        reference_time: Reference time (defaults to now)
        
    Returns:
        Age in seconds
    """
    if reference_time is None:
        reference_time = now()
    
    # Ensure both timestamps are timezone-aware
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    
    delta = reference_time - timestamp
    return int(delta.total_seconds())


def is_older_than(timestamp: datetime, max_age_seconds: int, reference_time: datetime = None) -> bool:
    """
    Check if timestamp is older than specified age.
    
    Args:
        timestamp: The timestamp to check
        max_age_seconds: Maximum age in seconds
        reference_time: Reference time (defaults to now)
        
    Returns:
        True if timestamp is older than max_age_seconds
    """
    age = get_age_in_seconds(timestamp, reference_time)
    return age > max_age_seconds


def time_until(target_time: datetime, reference_time: datetime = None) -> int:
    """
    Get seconds until target time.
    
    Args:
        target_time: Target timestamp
        reference_time: Reference time (defaults to now)
        
    Returns:
        Seconds until target time (negative if target is in the past)
    """
    if reference_time is None:
        reference_time = now()
    
    # Ensure both timestamps are timezone-aware
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    
    delta = target_time - reference_time
    return int(delta.total_seconds())