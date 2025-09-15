# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Autopiloot is a production-ready Agency Swarm v1.0.0 multi-agent system for automated YouTube content processing. The system discovers videos, transcribes them via AssemblyAI, generates business-focused summaries, and manages operational monitoring with strict cost controls.

**Key Architecture Pattern**: Event-driven broker architecture where Firestore serves as both data store and event broker, with Firebase Functions v2 for scheduling and automation.

## Common Development Commands

### Testing

```bash
# Run all tests (comprehensive test suite)
python -m unittest discover tests -v

# Run specific test modules
python -m unittest tests.test_config -v           # Configuration tests
python -m unittest tests.test_env_loader -v       # Environment validation tests
python -m unittest tests.test_audit_logger -v     # Audit logging tests (TASK-AUDIT-0041)
python -m unittest tests.test_observability_ops -v # Observability ops suite (TASK-OBS-0040)
python -m unittest tests.test_send_error_alert -v  # Error alerting tests (TASK-OBS-0041)
python -m unittest tests.test_llm_observability -v # LLM observability (TASK-LLM-0007)
python -m unittest tests.test_remove_sheet_row -v # Tool-specific tests
python -m unittest tests.test_get_video_audio_url -v # Audio extraction tests
python -m unittest tests.test_submit_assemblyai_job -v # AssemblyAI job submission tests
python -m unittest tests.test_poll_transcription_job -v # Transcript polling tests
python -m unittest tests.test_store_transcript_to_drive -v # Drive storage tests
python -m unittest tests.test_save_transcript_record -v # Firestore metadata tests

# Test individual tools (each has test block)
python scraper_agent/tools/RemoveSheetRow.py
python transcriber_agent/tools/get_video_audio_url.py
python transcriber_agent/tools/submit_assemblyai_job.py
python transcriber_agent/tools/poll_transcription_job.py
python transcriber_agent/tools/store_transcript_to_drive.py
python transcriber_agent/tools/save_transcript_record.py
python observability_agent/tools/monitor_quota_state.py
python observability_agent/tools/alert_engine.py
python observability_agent/tools/stuck_job_scanner.py

# Validate environment setup
python config/env_loader.py
```

### Agency Operations

```bash
# Run the agency (requires proper .env configuration)
python agency.py

# Deploy Firebase Functions (from autopiloot directory)
firebase deploy --only functions

# Test Firebase Functions locally
firebase emulators:start --only functions,firestore
```

### Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (REQUIRED before running)
cp ../.env.template .env
# Edit .env with actual API keys
```

## High-Level Architecture

### Agency Swarm v1.0.0 Framework

- **Inheritance Pattern**: All tools inherit from `agency_swarm.tools.BaseTool` with Pydantic Field validation
- **Return Convention**: All tool `run()` methods return JSON strings (not Dict objects)
- **Agent Structure**: Each agent is in `{agent_name}/` directory with `tools/` subdirectory
- **Communication Flow**: ScraperAgent (CEO) → TranscriberAgent → SummarizerAgent, with ObservabilityAgent monitoring all
- **Agent Count**: 4 production agents (31 total tools)
- **Complete Architecture**: All 30 planned tasks completed and archived

### Multi-Layer Configuration System

1. **Environment Variables** (`.env`): API keys, credentials, secrets
2. **settings.yaml**: Business rules, thresholds, operational parameters
3. **agency_manifesto.md**: Shared operational standards across all agents
4. **Agent instructions.md**: Agent-specific workflows and guidelines

### Firestore as Event Broker

- **Pattern**: All data mutations flow through Firestore exclusively
- **Collections**: `videos/`, `transcripts/`, `summaries/`, `jobs/transcription/`, `costs_daily/`, `audit_logs/`, `jobs_deadletter/`, `alert_throttling/`
- **Status Progression**: `discovered` → `transcription_queued` → `transcribed` → `summarized`
- **Idempotency**: Document IDs use YouTube video_id as natural key
- **Audit Trail**: All key actions logged to `audit_logs` collection (TASK-AUDIT-0041)

### Reliability & Error Handling Architecture

- **Dead Letter Queue**: Failed operations route to `jobs_deadletter` collection after 3 retries
- **Exponential Backoff**: 60s → 120s → 240s retry delays
- **Quota Management**: YouTube API (10k units/day), AssemblyAI ($5/day budget)
- **Checkpoint System**: `lastPublishedAt` persistence for incremental processing

### Firebase Functions Integration

- **Scheduled**: Daily scraping at 01:00 Europe/Amsterdam via Cloud Scheduler
- **Event-Driven**: Budget monitoring triggered by Firestore document writes
- **Deployment**: Manual via Firebase CLI with service account authentication (functions in services/firebase/)
- **Configuration**: Functions import agency classes directly, reuse environment config

## Critical Implementation Details

### Tool Development Rules

- **NEVER** include API keys as tool parameters - always use environment variables
- **ALWAYS** validate required environment variables in tool initialization
- **ALWAYS** include test block with `if __name__ == "__main__":` in every tool
- **ALWAYS** use JSON string returns from `run()` methods

### Agent Communication Patterns

```python
# Agency chart defines allowed communication flows
agency_chart = [
    scraper_agent,  # CEO can communicate with all
    [scraper_agent, transcriber_agent],  # Workflow pipeline
    [transcriber_agent, summarizer_agent],
    [observability_agent, scraper_agent],  # Monitoring flows
    [observability_agent, transcriber_agent, summarizer_agent],  # Observability monitoring
]
```

### Business Rule Enforcement

- **Duration Limit**: 70 minutes (4200 seconds) maximum video duration
- **Daily Limits**: 10 videos per channel, $5 transcription budget
- **Archive-First**: Google Sheets rows archived before deletion for audit trail
- **Quota Handling**: Graceful degradation when YouTube/AssemblyAI quotas exhausted

### Error Response Format

All tools return consistent JSON error structures:

```python
{
    "error": "error_type",
    "message": "Human-readable description",
    "details": {...}  # Optional additional context
}
```

## ADR and Documentation Maintenance

### Keep Updated

- **ADR.mdc**: Add new ADR entries for significant architectural decisions
- **folder-structure.mdc**: Update when directory structure changes
- Both files in `.cursor/rules/` are source of truth for architecture

### ADR Protocol

1. Read entire ADR.mdc file
2. Calculate next ID (max + 1, zero-padded to 4 digits)
3. Add entry at END of file with proper anchor
4. Update index table (sorted by ID descending)
5. Mark superseded ADRs if applicable

## Testing Strategy

### Tool Testing

- Each tool has standalone test in `if __name__ == "__main__":` block
- Integration tests in `tests/` directory using unittest framework
- Mock external services where appropriate, but prefer real API testing

### Configuration Testing

- `test_config.py`: YAML loading, validation, nested key access
- `test_env_loader.py`: Environment variable validation, API key getters
- Run `python config/env_loader.py` to validate current environment

### Observability Suite Testing (TASK-OBS-0040/0041)

- `test_observability_ops.py`: Comprehensive suite testing all 6 observability tools
- `test_send_error_alert.py`: Error alerting with throttling, module-level imports, mocking patterns
- `test_llm_observability.py`: LLM configuration, token usage tracking, Langfuse integration
- `test_monitor_transcription_budget.py`: Budget monitoring with 80% threshold alerts

### TASK-TRN-0022 Tool Testing

- `test_poll_transcription_job.py`: Tests exponential backoff, timeout handling, status progression
- `test_store_transcript_to_drive.py`: Tests file upload, metadata enhancement, Drive API integration
- `test_save_transcript_record.py`: Tests Firestore transactions, status updates, validation

## Firebase Deployment

### Functions Structure

```
services/firebase/functions/
├── main.py          # Entry points
├── scheduler.py     # Scheduled and event-driven functions
├── core.py          # Utilities
└── requirements.txt # Firebase-specific dependencies
```

### Deployment Commands

```bash
# Deploy functions only
firebase deploy --only functions

# Deploy specific function
firebase deploy --only functions:daily_scraper

# Test locally with emulator
firebase emulators:start
```

## Common Troubleshooting

### Missing Environment Variables

- Check `.env` file exists and contains all variables from `../.env.template`
- Run `python config/env_loader.py` to identify missing variables
- Ensure Google service account file exists at path specified

### Tool Import Errors

- Tool class name must match filename exactly
- Tools must be in `{agent_name}/tools/` directory
- All tools must inherit from `agency_swarm.tools.BaseTool`

### Firestore Connection Issues

- Verify `GCP_PROJECT_ID` environment variable is set
- Check service account has Firestore permissions
- Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to valid JSON file

### Quota Exhaustion

- YouTube: Check `QuotaManager` status, wait for daily reset
- AssemblyAI: Monitor `costs_daily` collection for budget status
- Implement checkpoint-based resume from `lastPublishedAt`

### Observability Monitoring

- Use `monitor_quota_state.py` for real-time YouTube/AssemblyAI quota tracking
- Check `monitor_dlq_trends.py` for dead letter queue anomaly detection
- Run `stuck_job_scanner.py` to identify stale jobs across agent collections
- Generate operational reports with `report_daily_summary.py` (Slack-formatted)
- Track LLM usage and costs with `llm_observability_metrics.py`
- Manage centralized alerting via `alert_engine.py` with throttling and deduplication

### Task and Project Status

- All 30 planned tasks completed and archived in `planning/archive/`
- Production-ready status achieved with comprehensive test coverage (70+ tests)
- Complete ADR documentation in `.cursor/rules/ADR.mdc` (23 architectural decisions)
- Folder structure documented in `.cursor/rules/folder-structure.mdc`
