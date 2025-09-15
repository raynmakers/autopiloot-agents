# Core utilities for Autopiloot Agency

# Reliability and error handling
from .reliability import (
    DeadLetterQueue,
    RetryPolicy,
    JobRetryManager
)

# Google Sheets integration
from .sheets import (
    GoogleSheetsClient,
    URLExtractor,
    BackfillProcessor
)

# Idempotency and deduplication
from .idempotency import (
    VideoIDExtractor,
    FilenameGenerator,
    DeduplicationManager,
    StatusTransitionManager
)

# Time utilities
from .time_utils import (
    now,
    to_iso8601_z,
    parse_iso8601_z,
    format_for_firestore,
    format_for_filename,
    format_for_display,
    calculate_exponential_backoff,
    calculate_jittered_backoff,
    get_next_retry_time,
    format_duration_human,
    parse_duration_string,
    get_age_in_seconds,
    is_older_than,
    time_until,
    utcnow  # Legacy compatibility
)

# Slack utilities
from .slack_utils import (
    normalize_channel_name,
    get_channel_for_alert_type,
    format_alert_blocks,
    format_daily_summary_blocks,
    format_table_blocks,
    validate_slack_message,
    create_slack_webhook_payload,
    create_error_alert,
    create_warning_alert,
    create_info_alert,
    create_dlq_alert
)

__all__ = [
    # Reliability
    'DeadLetterQueue',
    'RetryPolicy', 
    'JobRetryManager',
    # Sheets
    'GoogleSheetsClient',
    'URLExtractor',
    'BackfillProcessor',
    # Idempotency
    'VideoIDExtractor',
    'FilenameGenerator',
    'DeduplicationManager',
    'StatusTransitionManager',
    # Time utilities
    'now',
    'to_iso8601_z',
    'parse_iso8601_z',
    'format_for_firestore',
    'format_for_filename',
    'format_for_display',
    'calculate_exponential_backoff',
    'calculate_jittered_backoff',
    'get_next_retry_time',
    'format_duration_human',
    'parse_duration_string',
    'get_age_in_seconds',
    'is_older_than',
    'time_until',
    'utcnow',
    # Slack utilities
    'normalize_channel_name',
    'get_channel_for_alert_type',
    'format_alert_blocks',
    'format_daily_summary_blocks',
    'format_table_blocks',
    'validate_slack_message',
    'create_slack_webhook_payload',
    'create_error_alert',
    'create_warning_alert',
    'create_info_alert',
    'create_dlq_alert'
]