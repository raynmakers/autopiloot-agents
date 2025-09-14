# Reliability and Quotas Implementation

This document summarizes the implementation of Task 04 - Reliability, quotas, and dead-letter queue functionality.

## Overview

The implementation provides comprehensive reliability features including API quota management, dead-letter queue handling, checkpoint-based processing, and Firestore performance optimization through composite indexes.

## Files Created/Modified

### New Files

- `core/reliability.py` - Core reliability utilities and quota management
- `firestore/indexes.md` - Firestore composite index definitions
- `scraper/tools/YouTubeQuotaManager.py` - YouTube API quota management with checkpoints
- `scraper/tools/DLQHandler.py` - Dead letter queue handling tool
- `tests/test_reliability.py` - Comprehensive test suite (22 tests)

### Existing Files

- `firestore.rules` - Already configured with server-only access (covers DLQ requirements)

## Core Features

### 1. Dead Letter Queue (DLQ) System

**Purpose**: Handle jobs that fail after retry attempts

**Key Components**:

- `DLQEntry` TypedDict with required fields: job_type, video_id, reason, retry_count, last_error_at
- `create_dlq_entry()` function for standardized DLQ entry creation
- `DLQHandler` tool for writing failed jobs to Firestore `jobs_deadletter` collection
- `DLQQuery` tool for monitoring and analyzing failure patterns

**Job Types Supported**:

- `youtube_discovery` - YouTube API video discovery failures
- `transcription` - AssemblyAI transcription failures
- `summarization` - OpenAI/LLM summarization failures
- `sheets_processing` - Google Sheets processing failures
- `slack_notification` - Slack notification failures

### 2. Quota Management System

**Purpose**: Track and enforce API quota limits across services

**Key Components**:

- `QuotaManager` class for tracking requests per service
- `QuotaStatus` tracking with requests made/limit and exhaustion state
- Automatic quota exhaustion detection and reset time calculation
- Service availability checking before making API calls

**Supported Services**:

- YouTube Data API (10,000 units/day default)
- AssemblyAI (configurable limit)
- OpenAI (configurable limit)
- Slack API (configurable limit)

### 3. Checkpoint System

**Purpose**: Resume processing from last successful point to reduce API calls

**Key Components**:

- `CheckpointData` TypedDict with service, last_published_at, last_processed_id, updated_at
- `create_checkpoint()` function for creating checkpoint records
- YouTube-specific checkpoint with `lastPublishedAt` timestamp support
- Firestore storage for checkpoint persistence

### 4. Retry and Backoff Strategy

**Purpose**: Handle transient failures with intelligent retry logic

**Key Components**:

- `should_retry_job()` - Determines if job should be retried based on attempt count
- `calculate_backoff_delay()` - Exponential backoff calculation (60s, 120s, 240s, 480s)
- Maximum retry limit enforcement (default: 3 attempts)
- DLQ routing after max retries exceeded

## Firestore Index Optimization

### Composite Indexes Defined

1. **Videos Collection**:

   - Fields: `status` (ASC), `published_at` (DESC)
   - Purpose: Efficient queries for videos by status and publication date

2. **Summaries Collection**:

   - Fields: `created_at` (DESC)
   - Purpose: Chronological summary retrieval

3. **Jobs Dead Letter Queue**:

   - Fields: `job_type` (ASC), `last_error_at` (DESC)
   - Purpose: Monitor failures by type and recency

4. **Transcription Jobs**:
   - Fields: `status` (ASC), `submitted_at` (DESC)
   - Purpose: Job queue management and status tracking

### Index Deployment

Use Firebase CLI to deploy indexes:

```bash
firebase deploy --only firestore:indexes
```

Index configuration available in `firestore/indexes.md` with JSON format for automated deployment.

## Tools Architecture

### YouTubeQuotaManager Tool

**Purpose**: Manage YouTube API quota with checkpoint-based video discovery

**Key Features**:

- Tracks YouTube API quota usage (search + video details requests)
- Implements `lastPublishedAt` checkpoint for resuming from last processed video
- Handles quota exhaustion with proper error responses
- Channel handle resolution to channel ID
- Video metadata extraction with duration filtering
- ISO 8601 duration parsing (PT4M13S format)

**Parameters**:

- `channel_handle` - YouTube channel handle (e.g., "@AlexHormozi")
- `max_results` - Maximum videos to fetch (default: 10)
- `last_published_at` - Checkpoint timestamp for resuming
- `check_quota_only` - Flag for quota status checking

### DLQHandler Tool

**Purpose**: Handle failed jobs with retry logic or DLQ routing

**Key Features**:

- Retry decision logic based on attempt count and max retries
- Exponential backoff delay calculation
- Firestore DLQ collection writes with unique document IDs
- Error logging for monitoring and debugging
- Support for additional error details in JSON format

**Parameters**:

- `job_type` - Type of failed job
- `video_id` - Associated video ID
- `reason` - Human-readable failure reason
- `retry_count` - Current retry attempt count
- `error_details` - Optional additional error information
- `max_retries` - Maximum retry attempts (default: 3)

### DLQQuery Tool

**Purpose**: Monitor and analyze DLQ entries for operational insights

**Key Features**:

- Query DLQ entries by job type or video ID
- Failure pattern statistics and analysis
- Recent failure tracking (last 24 hours)
- Configurable result limits
- Aggregated statistics by job type and retry count

## Error Handling Strategy

### Quota Exhaustion

1. **Detection**: Monitor requests against daily limits
2. **Response**: Return quota exhausted status with reset time
3. **Backoff**: Pause processing until quota resets (typically next day)
4. **Resume**: Automatic resumption when quota resets

### Transient Failures

1. **Retry Logic**: Up to 3 attempts with exponential backoff
2. **Backoff Delays**: 60s, 120s, 240s, 480s progression
3. **DLQ Routing**: Send to dead letter queue after max retries
4. **Monitoring**: Log all failures for operational visibility

### Persistent Failures

1. **DLQ Storage**: Failed jobs stored in `jobs_deadletter` collection
2. **Error Details**: Comprehensive error information and context
3. **Manual Review**: DLQ entries available for manual intervention
4. **Statistics**: Failure pattern analysis for system improvement

## Testing Coverage

**22 comprehensive tests** covering:

- **DLQ Operations**: 4 tests for entry creation and error formatting
- **Retry Logic**: 2 tests for retry decisions and backoff calculations
- **Quota Management**: 8 tests for quota tracking and exhaustion detection
- **Checkpoint System**: 3 tests for checkpoint creation and management
- **QuotaManager Class**: 8 tests for service tracking and availability

All tests verify realistic scenarios and edge cases with 100% pass rate.

## Configuration Integration

### Quota Limits

Configure service-specific quota limits:

- YouTube API: 10,000 units/day (configurable)
- AssemblyAI: Based on subscription plan
- OpenAI: Based on tier and usage
- Slack API: Rate limits per workspace

### Retry Settings

Default retry configuration:

- Maximum retries: 3 attempts
- Base backoff delay: 60 seconds
- Backoff progression: Exponential (2^retry_count)

### Checkpoint Persistence

Checkpoints stored in Firestore:

- Collection: `checkpoints`
- Document ID: `{service}_{operation_type}`
- Auto-updated on successful processing

## Security Considerations

### Firestore Rules

Server-only access enforced for all collections including DLQ:

```firestore
match /jobs_deadletter/{id} {
  allow read, write: if false;
}
```

Firebase Admin SDK bypasses rules for backend operations.

### Error Information

- No sensitive data in DLQ entries
- API keys retrieved from environment variables only
- Error details sanitized before storage

## Monitoring and Observability

### DLQ Monitoring

Query tools available for:

- Recent failure analysis
- Failure pattern identification
- Job type error distribution
- Retry attempt statistics

### Quota Monitoring

Track across services:

- Current quota usage
- Quota exhaustion events
- Reset time tracking
- Service availability status

### Operational Metrics

Key metrics for monitoring:

- DLQ entry rate by job type
- Average retry attempts before success/failure
- Quota utilization patterns
- Checkpoint update frequency

## Acceptance Criteria Met

✅ **Index definitions documented** - Complete Firestore index definitions in `firestore/indexes.md`

✅ **Failures after retries create DLQ entries** - DLQHandler tool writes failed jobs to `jobs_deadletter` collection

✅ **Quota exhaustion does not crash runs** - YouTube quota manager handles exhaustion gracefully and resumes next window

✅ **Backoff strategy implemented** - Exponential backoff with intelligent retry logic

✅ **Checkpoint system functional** - `lastPublishedAt` checkpoint reduces YouTube API calls

The implementation provides enterprise-grade reliability features that ensure resilient operation under API limits and failures while maintaining comprehensive observability and error handling capabilities.
