# Firestore Event Contracts

This document defines the standardized schemas for Firestore collections used by the Autopiloot Agency for event-driven coordination and data storage.

## Overview

The Autopiloot Agency uses Firestore as the primary event broker and data store. All agents communicate through well-defined document schemas stored in specific collections.

## Core Collections

### 1. `videos` Collection

Stores discovered video metadata and processing status.

```typescript
interface VideoDocument {
  video_id: string;                    // YouTube video ID (document key)
  title: string;                       // Video title
  description?: string;                // Video description
  published_at: string;                // ISO 8601 timestamp
  channel_id: string;                  // YouTube channel ID
  channel_title: string;               // Channel display name
  duration_sec: number;                // Video duration in seconds
  view_count?: number;                 // View count (if available)
  
  // Processing status
  status: 'discovered' | 'transcription_queued' | 'transcribed' | 'summarized' | 'failed' | 'skipped';
  processing_stage: 'scraping' | 'transcription' | 'summarization' | 'completed';
  
  // Timestamps
  discovered_at: string;               // ISO 8601 timestamp
  updated_at: string;                  // ISO 8601 timestamp
  completed_at?: string;               // ISO 8601 timestamp
  
  // References
  transcript_doc_ref?: string;         // Firestore path to transcript
  summary_doc_ref?: string;            // Firestore path to summary
  
  // Storage references
  drive_refs?: {
    transcript_id?: string;            // Google Drive file ID
    summary_id?: string;               // Google Drive file ID
  };
  
  // External service references
  assemblyai_job_id?: string;          // AssemblyAI transcription job ID
  zep_doc_id?: string;                 // Zep memory document ID
  
  // Metadata
  source: 'channel_scrape' | 'sheet_backfill' | 'manual';
  tags?: string[];                     // Optional tags
  priority?: number;                   // Processing priority (1-10)
  
  // Error tracking
  error_count?: number;                // Number of processing errors
  last_error?: string;                 // Most recent error message
}
```

### 2. `jobs/transcription` Collection

Tracks transcription job status and progress.

```typescript
interface TranscriptionJobDocument {
  job_id: string;                      // Job identifier (document key)
  video_id: string;                    // Associated video ID
  
  // Job details
  status: 'queued' | 'submitted' | 'processing' | 'completed' | 'failed' | 'retrying';
  assemblyai_job_id?: string;          // AssemblyAI job identifier
  
  // Configuration
  audio_url: string;                   // Direct audio stream URL
  duration_sec: number;                // Audio duration
  webhook_url?: string;                // Completion webhook URL
  
  // Cost tracking
  estimated_cost_usd: number;          // Estimated transcription cost
  actual_cost_usd?: number;            // Actual cost (if available)
  
  // Features
  speaker_labels: boolean;             // Speaker diarization enabled
  language_code?: string;              // Target language
  
  // Timestamps
  created_at: string;                  // ISO 8601 timestamp
  updated_at: string;                  // ISO 8601 timestamp
  submitted_at?: string;               // When submitted to AssemblyAI
  completed_at?: string;               // When transcription completed
  
  // Retry tracking
  attempt_count: number;               // Number of attempts
  max_attempts: number;                // Maximum retry attempts
  next_retry_at?: string;              // Next retry timestamp
  
  // Results
  transcript_text?: string;            // Final transcript text
  transcript_json?: object;            // Full transcript with metadata
  confidence?: number;                 // Transcription confidence
  
  // Error tracking
  error_message?: string;              // Error details
  error_type?: 'api_error' | 'timeout' | 'quota_exceeded' | 'invalid_audio';
}
```

### 3. `jobs/summarization` Collection

Tracks summarization job status and progress.

```typescript
interface SummarizationJobDocument {
  job_id: string;                      // Job identifier (document key)
  video_id: string;                    // Associated video ID
  transcript_doc_ref: string;          // Reference to transcript document
  
  // Job details
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'retrying';
  
  // Configuration
  summary_type: 'short' | 'detailed' | 'executive';
  max_length?: number;                 // Maximum summary length
  focus_areas?: string[];              // Specific focus topics
  
  // LLM details
  model_used: string;                  // LLM model identifier
  prompt_id: string;                   // Prompt template ID
  prompt_version: string;              // Prompt version
  
  // Timestamps
  created_at: string;                  // ISO 8601 timestamp
  updated_at: string;                  // ISO 8601 timestamp
  completed_at?: string;               // When summarization completed
  
  // Token usage
  input_tokens: number;                // Tokens consumed for input
  output_tokens: number;               // Tokens generated for output
  estimated_cost_usd: number;          // Estimated API cost
  
  // Results
  summary: {
    bullets: string[];                 // Key bullet points
    key_concepts: string[];            // Important concepts
    executive_summary?: string;        // Executive summary paragraph
  };
  
  // Storage references
  drive_refs: {
    short_summary_id: string;          // Google Drive file ID
    detailed_summary_id?: string;      // Google Drive file ID (if applicable)
  };
  
  // External service references
  zep_doc_id?: string;                 // Zep memory document ID
  zep_collection: string;              // Zep collection name
  
  // Error tracking
  attempt_count: number;               // Number of attempts
  error_message?: string;              // Error details
}
```

### 4. `audit_logs` Collection

Comprehensive audit trail for compliance and debugging.

```typescript
interface AuditLogDocument {
  log_id: string;                      // Unique log identifier (document key)
  
  // Event classification
  event_type: 'agent_action' | 'api_call' | 'data_access' | 'error' | 'policy_enforcement';
  action: string;                      // Specific action taken
  outcome: 'success' | 'failure' | 'partial' | 'skipped';
  
  // Context
  agent_name: string;                  // Agent that performed action
  tool_name?: string;                  // Tool that was executed
  user_id?: string;                    // User context (if applicable)
  session_id?: string;                 // Session identifier
  
  // Timing
  timestamp: string;                   // ISO 8601 timestamp
  duration_ms?: number;                // Action duration
  
  // Data
  resource_type?: string;              // Type of resource accessed
  resource_id?: string;                // Specific resource identifier
  data_summary?: string;               // Summary of data involved
  
  // API details
  api_endpoint?: string;               // External API called
  api_method?: string;                 // HTTP method
  api_response_code?: number;          // Response status code
  
  // Cost tracking
  tokens_used?: number;                // LLM tokens consumed
  api_cost_usd?: number;               // API cost incurred
  
  // Compliance
  sensitive_data: boolean;             // Contains sensitive information
  retention_period_days: number;       // How long to retain this log
  
  // Error details
  error_message?: string;              // Error description
  error_code?: string;                 // Error classification
  stack_trace?: string;                // Technical error details
  
  // Metadata
  tags?: string[];                     // Classification tags
  correlation_id?: string;             // Related log correlation
  parent_log_id?: string;              // Parent operation log
}
```

### 5. `jobs_deadletter` Collection

Dead letter queue for failed jobs requiring manual intervention.

```typescript
interface DeadLetterJobDocument {
  job_id: string;                      // Original job identifier (document key)
  original_collection: string;         // Source collection (e.g., "jobs/transcription")
  
  // Failure details
  failure_reason: string;              // Why the job failed
  failure_type: 'max_retries' | 'fatal_error' | 'quota_exceeded' | 'manual_intervention';
  final_error: string;                // Last error message
  
  // Original job data
  job_type: string;                    // Type of job that failed
  job_payload: object;                 // Original job configuration
  
  // Failure history
  total_attempts: number;              // Number of retry attempts
  first_failure_at: string;           // ISO 8601 timestamp
  last_attempt_at: string;             // ISO 8601 timestamp
  moved_to_dlq_at: string;             // ISO 8601 timestamp
  
  // Context
  video_id?: string;                   // Associated video (if applicable)
  agent_name: string;                  // Agent that owned the job
  
  // Resolution tracking
  dlq_status: 'pending' | 'investigating' | 'resolved' | 'abandoned';
  assigned_to?: string;                // Person investigating
  resolution_notes?: string;           // Investigation notes
  resolved_at?: string;                // Resolution timestamp
  
  // Recovery options
  can_retry: boolean;                  // Whether job can be retried
  retry_after?: string;                // Earliest retry timestamp
  manual_steps_required?: string[];    // Manual intervention needed
  
  // Metadata
  priority: 'low' | 'medium' | 'high' | 'critical';
  tags?: string[];                     // Classification tags
  escalation_level: number;            // Escalation priority (1-5)
}
```

### 6. `run_events` Collection

Daily run coordination and status tracking.

```typescript
interface RunEventDocument {
  run_id: string;                      // Daily run identifier (document key, format: YYYY-MM-DD)
  
  // Run planning
  planned_videos: number;              // Number of videos planned for processing
  planned_budget_usd: number;          // Planned budget allocation
  planned_start_time: string;          // ISO 8601 timestamp
  planned_end_time?: string;           // ISO 8601 timestamp
  
  // Execution tracking
  status: 'planned' | 'running' | 'completed' | 'failed' | 'paused';
  started_at?: string;                 // ISO 8601 timestamp
  completed_at?: string;               // ISO 8601 timestamp
  
  // Progress counters
  discovered: number;                  // Videos discovered
  transcription_queued: number;        // Videos queued for transcription
  transcribed: number;                 // Videos successfully transcribed
  summarized: number;                  // Videos successfully summarized
  failed: number;                      // Videos that failed processing
  skipped: number;                     // Videos skipped (duplicates, etc.)
  dlq: number;                         // Videos moved to dead letter queue
  
  // Resource utilization
  budget_used_usd: number;             // Actual budget consumed
  api_calls_made: number;              // Total API calls
  tokens_consumed: number;             // Total LLM tokens used
  
  // Quality metrics
  success_rate: number;                // Percentage of successful completions
  average_processing_time_sec: number; // Average time per video
  
  // Error summary
  error_categories: {
    [category: string]: number;        // Error counts by category
  };
  
  // Agent performance
  agent_stats: {
    [agent_name: string]: {
      actions_taken: number;
      errors: number;
      avg_response_time_ms: number;
    };
  };
  
  // Policy enforcement
  quota_limits_hit: string[];          // Which quotas were reached
  policies_enforced: string[];         // Which policies were applied
  
  // Metadata
  triggered_by: 'schedule' | 'manual' | 'backfill';
  configuration_snapshot: object;      // Config state at run time
  notes?: string;                      // Manual notes about the run
}
```

## Event Patterns

### Status Transitions

Valid status transitions for video processing:

```
discovered → transcription_queued → transcribed → summarized
     ↓              ↓                    ↓           ↓
   failed         failed               failed     failed
     ↓              ↓                    ↓           ↓
   skipped       (retry)              (retry)    (retry)
```

### Retry Policies

- **Transcription Jobs**: 3 attempts with exponential backoff (60s → 120s → 240s)
- **Summarization Jobs**: 3 attempts with exponential backoff (30s → 60s → 120s)
- **API Calls**: 5 attempts with exponential backoff (10s → 20s → 40s → 80s → 160s)

### Cost Tracking

All monetary amounts are stored in USD with 4 decimal places for accuracy.

### Timestamp Format

All timestamps use ISO 8601 format with UTC timezone: `YYYY-MM-DDTHH:MM:SSZ`

## Usage Guidelines

1. **Atomicity**: Each document update should be atomic to prevent race conditions
2. **Indexing**: Create composite indexes for common query patterns
3. **Retention**: Implement data retention policies based on audit requirements
4. **Monitoring**: Set up alerts for unusual patterns in error rates or costs
5. **Validation**: Validate all document writes against these schemas

## Security Considerations

- Sensitive data (API keys, personal information) should never be stored in these collections
- Use Firestore security rules to restrict access based on service account permissions
- Audit logs should be write-only for most agents, read-only for observability
- Dead letter queue access should be restricted to administrators

## Version History

- **v1.0** (2025-09-15): Initial schema definition
- **v1.1** (TBD): Schema evolution as requirements change

For questions about these contracts, consult the Autopiloot Agency documentation or the engineering team.